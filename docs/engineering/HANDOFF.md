# ShadowSpark AI-ASSIST — Integration Handoff for Codex

**Status**: `AI_ASSIST_CONTRACT_GATE=READY`  
**Author**: Antigravity (Lead Backend & Systems Engineer)  
**Target Consumer**: Codex (Primary Writer for `shadowspark-production`)  
**Consumer Workspace**: `/home/moronto/Documents/Codex/2026-09-14/re/work/shadowspark-production`  
**Consumer Branch**: `feat/ai-assist-adapter`  

---

## 1. Overview & Gate Declaration

All backend prerequisites, architectural invariants, fail-closed tenancy controls, persistent database path handling, and the review queue listing API have been implemented, verified, and committed locally to `AI-ASSIST` (`feat/multi-tenant-isolation`, HEAD `db9d309`).

The backend API contract is frozen at **v1.1.0**.

---

## 2. API Contract Summary for Client Adapter

The frontend adapter in `shadowspark-production` should interact with the following endpoints:

### Endpoints

1. **`POST /v1/compliance-review-brief`**:
   - Creates or replays a compliance brief.
   - Headers required: `Authorization`, `X-Tenant-Slug` (or `X-Tenant-ID`), `Idempotency-Key`.
   - Body: `{"exception_id": "string", "tenant_id": "string"}` (optional `tenant_id` must match header if provided).
   - Expected status: `201 Created` (with `{"brief_id": "...", "output": { ... }, "replayed": bool}`).

2. **`GET /v1/review-queue`**:
   - Lists review queue items for the tenant.
   - Headers required: `Authorization`, `X-Tenant-Slug` (or `X-Tenant-ID`).
   - Query params: `limit` (default 50), `offset` (default 0), `state` (optional: `pending_review` or `annotated`).
   - Expected status: `200 OK` (with `{"items": [...], "total": int, "limit": int, "offset": int}`).

3. **`GET /v1/review-queue/{brief_id}`**:
   - Retrieves a specific review queue entry, including stored brief output and annotations.
   - Headers required: `Authorization`, `X-Tenant-Slug` (or `X-Tenant-ID`).
   - Expected status: `200 OK` (with `ReviewQueueResponse`).

4. **`POST /v1/review-queue/{brief_id}/annotations`**:
   - Appends an audit annotation to a review queue entry.
   - Headers required: `Authorization`, `X-Tenant-Slug` (or `X-Tenant-ID`), `Idempotency-Key`.
   - Body: `{"annotation": "string"}` (1 to 2000 characters).
   - Expected status: `200 OK` (with updated `ReviewQueueResponse`).

---

## 3. Required Client Header Invariants

All outbound requests from `shadowspark-production` to `AI-ASSIST` MUST supply:
1. **Bearer Token**: `Authorization: Bearer <SHADOWSPARK_API_TOKEN>`
2. **Tenant Header**: `X-Tenant-Slug: <tenant_id>` (or `X-Tenant-ID: <tenant_id>`).
   *Note: Omitting this in production causes immediate `401 Unauthorized` fail-closed error.*
3. **Idempotency Key**: `Idempotency-Key: <uuid-v4>` on all POST requests.
   *Note: Omitting this causes `400 Bad Request`.*

---

## 4. Expected Error Status Codes

- `400 Bad Request`: Validation failure or missing `Idempotency-Key`.
- `401 Unauthorized`: Missing or invalid Bearer token, or missing tenant header in production.
- `403 Forbidden`: Insufficient scope (e.g. attempting to annotate without `compliance:review` scope).
- `404 Not Found`: Resource does not exist, or belongs to another tenant.
- `409 Conflict`: Reusing an `Idempotency-Key` with a different payload or annotation content.
- `422 Unprocessable Entity`: Exception ID or request payload contains raw 11-digit national identity numbers.
- `429 Too Many Requests`: Triggered if upstream compliance budget trips (`LLM06:2026`).

---

## 5. Live Deployment Status & Next Action for Release

- The live Render deployment at `https://shadowspark-ai-api.onrender.com` is running v1.1.0 (`e438562`).
- PR #2 (`feat/multi-tenant-isolation`) is merged into `main` and live deployment is confirmed.
- `scripts/render_e2e.sh` has verified live E2E behavior across all 6 verification stages.
- `ADAPTER_WRITE_GATE` is **OPEN**. The consumer adapter in `shadowspark-production` is verified with all 35 Vitest tests passing against the frozen contract.
