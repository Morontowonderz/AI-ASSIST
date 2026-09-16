---
name: ai-assist-idempotency
description: >-
  Runbook for tenant-scoped mutation idempotency, canonical SHA-256 payload hashing,
  replay semantics, and 409 conflict detection in AI-ASSIST.
---

# AI-ASSIST Idempotency Runbook

Use this skill when auditing, adding, or modifying mutating endpoints, idempotency key verification, replay caching, or conflict handling.

## Idempotency Architecture

1. **Mandatory Idempotency Keys**:
   - Mutating routes require `Idempotency-Key` header (`1 <= len <= 128`):
     - `POST /v1/compliance-review-brief`
     - `POST /v1/review-queue/{brief_id}/annotations`
   - Missing or oversized keys fail immediately with `400 Bad Request ("Idempotency-Key required")`.
2. **Tenant Scoping & Database Constraints**:
   - `briefs` table: `UNIQUE(tenant_id, idempotency_key)`
   - `annotations` table: `CREATE UNIQUE INDEX IF NOT EXISTS uq_annotations_tenant_brief_idem ON annotations(tenant_id, brief_id, idempotency_key) WHERE idempotency_key IS NOT NULL`
3. **Payload Binding**:
   - Brief generation: Bound to canonical SHA-256 JSON hash of `{"tenant_id": tenant_id, "exception_id": exception_id}`.
   - Annotation append: Bound to exact string equality of `annotation`.
4. **Replay vs. Conflict Behavior**:
   - **Matching Key + Matching Payload**:
     - Brief: returns stored brief payload with `replayed: true` (HTTP 201).
     - Annotation: re-fetches review queue entry without inserting duplicate row (HTTP 200).
   - **Matching Key + Mismatched Payload**:
     - Aborts immediately with `409 Conflict ("idempotency key conflict")`.

## Verification Commands

```bash
# Run idempotency unit and API tests
./.venv/bin/python -m pytest tests/test_api.py -k "idempotency" -v
./.venv/bin/python -m pytest tests/test_service.py -v
./.venv/bin/python -m pytest tests/test_database.py -k "idempotent" -v
```
