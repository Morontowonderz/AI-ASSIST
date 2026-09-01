from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from .database import Database, IdempotencyConflict
from vendor import runner


class ComplianceService:
    def __init__(self, database: Database, fixture_dir: str | Path):
        self.db = database
        self.db.initialize()
        self.fixture_dir = Path(fixture_dir)
        self._fixtures = {
            "ex_a_021": "case_21_whatsapp_injection.json",
            "tenant_b:ex_009": "case_09_cross_tenant.json",
            "ex_a_011": "case_11_bvn_in_notes.json",
            "ex_a_013": "case_13_budget_trip.json",
        }

    def _fixture(self, exception_id: str) -> dict:
        name = self._fixtures.get(exception_id)
        if not name:
            raise KeyError(exception_id)
        return runner.load_case(self.fixture_dir / name)

    def create_brief(self, tenant_id: str, exception_id: str, idempotency_key: str,
                     request_id: str, key_id: str) -> dict:
        request = {"tenant_id": tenant_id, "exception_id": exception_id}
        request_hash = self.db.request_hash(request)
        existing = self.db.find_idempotent(tenant_id, idempotency_key)
        if existing:
            if existing.request_hash != request_hash:
                raise IdempotencyConflict("idempotency key reused with different request")
            return {"brief_id": existing.brief_id, "output": existing.output, "tool_trace": [], "replayed": True}
        try:
            case = self._fixture(exception_id)
        except KeyError:
            raise
        output_result = runner.run_case(case)
        output = output_result["output"]
        if output["status"] in {"blocked", "error"}:
            self.db.record_denied(request_id, tenant_id, key_id,
                                  hashlib.sha256(exception_id.encode()).hexdigest(),
                                  f"case_{case['case_id']}_denied")
            return {"brief_id": None, "output": output, "tool_trace": output_result["tool_trace"], "replayed": False}
        stored = self.db.store_brief(tenant_id, idempotency_key, request_hash, exception_id,
                                     output, request_id=request_id, key_id=key_id)
        return {"brief_id": stored.brief_id, "output": output, "tool_trace": output_result["tool_trace"], "replayed": False}

    def get_review(self, tenant_id: str, brief_id: str) -> dict | None:
        return self.db.get_review(brief_id, tenant_id)

    def annotate(self, tenant_id: str, brief_id: str, operator_id: str, annotation: str,
                 request_id: str, key_id: str) -> dict | None:
        return self.db.append_annotation(brief_id, tenant_id, operator_id, annotation,
                                         request_id=request_id, key_id=key_id)
