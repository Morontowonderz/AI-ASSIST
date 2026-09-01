import json
import sqlite3

import pytest

from shadowspark_api.database import Database, IdempotencyConflict


OUTPUT = {
    "schema_version": "shadowspark.compliance_review_brief.v1.1.1",
    "status": "complete",
    "exception_id": "ex_a_021",
    "summary": "Evidence requires operator review.",
    "evidence": [],
    "recommendations": {"action": "abstain", "rationale": "insufficient evidence"},
    "risk_flags": ["LLM01:2026"],
    "confidence": "self_reported",
    "sor_status_unchanged": True,
}


def test_initialize_enables_foreign_keys_and_wal(tmp_path):
    db = Database(tmp_path / "state.db")
    db.initialize()
    with db._connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_store_brief_creates_queue_and_round_trips(tmp_path):
    db = Database(tmp_path / "state.db")
    db.initialize()
    stored = db.store_brief("tenant_a", "idem-1", "hash-1", "ex_a_021", OUTPUT,
                            request_id="req-1", key_id="ss_test_redacted", brief_id="brief-1")
    assert stored.brief_id == "brief-1"
    review = db.get_review("brief-1", "tenant_a")
    assert review["queue_state"] == "pending_review"
    assert review["output"] == OUTPUT
    assert review["annotations"] == []


def test_idempotency_conflict_is_explicit(tmp_path):
    db = Database(tmp_path / "state.db")
    db.initialize()
    db.store_brief("tenant_a", "idem-1", "hash-1", "ex_a_021", OUTPUT,
                   request_id="req-1", key_id="ss_test_redacted", brief_id="brief-1")
    with pytest.raises(IdempotencyConflict):
        db.store_brief("tenant_a", "idem-1", "hash-2", "ex_a_022", OUTPUT,
                       request_id="req-2", key_id="ss_test_redacted", brief_id="brief-2")


def test_annotation_updates_only_local_queue_state(tmp_path):
    db = Database(tmp_path / "state.db")
    db.initialize()
    db.store_brief("tenant_a", "idem-1", "hash-1", "ex_a_021", OUTPUT,
                   request_id="req-1", key_id="ss_test_redacted", brief_id="brief-1")
    db.append_annotation("brief-1", "tenant_a", "operator-1", "reviewed",
                         request_id="req-2", key_id="ss_test_redacted", annotation_id="ann-1")
    review = db.get_review("brief-1", "tenant_a")
    assert review["queue_state"] == "annotated"
    assert review["output"] == OUTPUT
    assert review["sor_status_unchanged"] is True
    assert review["annotations"][0]["annotation"] == "reviewed"


def test_review_is_tenant_scoped(tmp_path):
    db = Database(tmp_path / "state.db")
    db.initialize()
    db.store_brief("tenant_a", "idem-1", "hash-1", "ex_a_021", OUTPUT,
                   request_id="req-1", key_id="ss_test_redacted", brief_id="brief-1")
    assert db.get_review("brief-1", "tenant_b") is None


def test_database_bytes_contain_no_raw_credentials_or_identifiers(tmp_path):
    db = Database(tmp_path / "state.db")
    db.initialize()
    db.store_brief("tenant_a", "idem-1", "hash-1", "ex_a_021", OUTPUT,
                   request_id="req-1", key_id="ss_test_redacted", brief_id="brief-1")
    db.record_denied("req-2", "tenant_a", "ss_test_redacted", "hash", "auth_denied",
                     detail={"authorization": "Bearer ss_test_redacted"})
    db.append_annotation("brief-1", "tenant_a", "operator-1", "synthetic review note",
                         request_id="req-3", key_id="ss_test_redacted", annotation_id="ann-1")
    for path in (db.path, db.path.with_name(db.path.name + "-wal")):
        if path.exists():
            raw = path.read_bytes()
            assert b"Bearer ss_test_redacted" not in raw
            assert b"22222222222" not in raw
