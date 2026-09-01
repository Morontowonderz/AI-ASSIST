"""Small, tenant-scoped SQLite state boundary for the V1 review queue."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_RAW_ID = re.compile(r"(?<!\d)\d{11}(?!\d)")


class IdempotencyConflict(Exception):
    pass


@dataclass(frozen=True)
class StoredBrief:
    brief_id: str
    tenant_id: str
    idempotency_key: str
    request_hash: str
    exception_id: str
    output: dict
    queue_state: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: object) -> None:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    if _RAW_ID.search(text) or "Bearer " in text:
        raise ValueError("sensitive identifier or credential cannot be persisted")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS briefs (
                  brief_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
                  exception_id TEXT NOT NULL, output_json TEXT NOT NULL,
                  created_at TEXT NOT NULL, UNIQUE(tenant_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS review_queue (
                  brief_id TEXT PRIMARY KEY REFERENCES briefs(brief_id) ON DELETE CASCADE,
                  tenant_id TEXT NOT NULL,
                  state TEXT NOT NULL CHECK(state IN ('pending_review','annotated')),
                  sor_status_unchanged INTEGER NOT NULL CHECK(sor_status_unchanged=1),
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS annotations (
                  annotation_id TEXT PRIMARY KEY,
                  brief_id TEXT NOT NULL REFERENCES briefs(brief_id) ON DELETE CASCADE,
                  tenant_id TEXT NOT NULL, operator_id TEXT NOT NULL,
                  annotation TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                  event_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                  tenant_id TEXT NOT NULL, key_id TEXT NOT NULL,
                  event TEXT NOT NULL, outcome TEXT NOT NULL,
                  object_ref_hash TEXT, detail_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def request_hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def find_idempotent(self, tenant_id: str, idempotency_key: str) -> StoredBrief | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM briefs WHERE tenant_id=? AND idempotency_key=?", (tenant_id, idempotency_key)).fetchone()
        return self._brief(row) if row else None

    def store_brief(self, tenant_id: str, idempotency_key: str, request_hash: str,
                    exception_id: str, output: dict, *, request_id: str, key_id: str,
                    brief_id: str | None = None) -> StoredBrief:
        _safe(output)
        brief_id = brief_id or f"brief_{uuid.uuid4().hex}"
        created = _now()
        encoded = json.dumps(output, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM briefs WHERE tenant_id=? AND idempotency_key=?", (tenant_id, idempotency_key)).fetchone()
            if existing:
                conn.execute("ROLLBACK")
                if existing["request_hash"] != request_hash:
                    raise IdempotencyConflict("idempotency key reused with different request")
                return self._brief(existing)
            conn.execute("INSERT INTO briefs VALUES (?,?,?,?,?,?,?)", (brief_id, tenant_id, idempotency_key, request_hash, exception_id, encoded, created))
            conn.execute("INSERT INTO review_queue VALUES (?,?,?,?,?,?)", (brief_id, tenant_id, "pending_review", 1, created, created))
            conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, request_id, tenant_id, key_id, "brief_created", "complete", None, "{}", created))
            conn.execute("COMMIT")
        return StoredBrief(brief_id, tenant_id, idempotency_key, request_hash, exception_id, output, "pending_review")

    def record_denied(self, request_id: str, tenant_id: str, key_id: str, object_ref_hash: str,
                      event: str, detail: dict | None = None) -> None:
        safe_detail = dict(detail or {})
        if "authorization" in safe_detail:
            safe_detail["authorization"] = "[redacted]"
        detail_json = json.dumps(safe_detail, sort_keys=True, separators=(",", ":"))
        _safe(detail_json)
        with self._connect() as conn:
            conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, request_id, tenant_id, key_id, event, "blocked", object_ref_hash, detail_json, _now()))

    def get_review(self, brief_id: str, tenant_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT b.*, q.state, q.sor_status_unchanged, q.created_at AS q_created, q.updated_at FROM briefs b JOIN review_queue q ON q.brief_id=b.brief_id WHERE b.brief_id=? AND b.tenant_id=? AND q.tenant_id=?", (brief_id, tenant_id, tenant_id)).fetchone()
            if not row:
                return None
            annotations = conn.execute("SELECT annotation_id, operator_id, annotation, created_at FROM annotations WHERE brief_id=? AND tenant_id=? ORDER BY created_at", (brief_id, tenant_id)).fetchall()
        return {"brief_id": row["brief_id"], "tenant_id": row["tenant_id"], "exception_id": row["exception_id"], "output": json.loads(row["output_json"]), "queue_state": row["state"], "sor_status_unchanged": bool(row["sor_status_unchanged"]), "annotations": [dict(a) for a in annotations], "created_at": row["q_created"], "updated_at": row["updated_at"]}

    def append_annotation(self, brief_id: str, tenant_id: str, operator_id: str, annotation: str,
                          *, request_id: str, key_id: str, annotation_id: str | None = None) -> dict | None:
        _safe(annotation)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute("SELECT 1 FROM review_queue WHERE brief_id=? AND tenant_id=?", (brief_id, tenant_id)).fetchone()
            if not exists:
                conn.execute("ROLLBACK")
                return None
            now = _now()
            conn.execute("INSERT INTO annotations VALUES (?,?,?,?,?,?)", (annotation_id or uuid.uuid4().hex, brief_id, tenant_id, operator_id, annotation, now))
            conn.execute("UPDATE review_queue SET state='annotated', updated_at=? WHERE brief_id=? AND tenant_id=?", (now, brief_id, tenant_id))
            conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, request_id, tenant_id, key_id, "annotation_added", "complete", brief_id, "{}", now))
            conn.execute("COMMIT")
        return self.get_review(brief_id, tenant_id)

    @staticmethod
    def _brief(row: sqlite3.Row) -> StoredBrief:
        return StoredBrief(row["brief_id"], row["tenant_id"], row["idempotency_key"], row["request_hash"], row["exception_id"], json.loads(row["output_json"]), "pending_review")
