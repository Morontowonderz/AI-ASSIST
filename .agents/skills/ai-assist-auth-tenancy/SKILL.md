---
name: ai-assist-auth-tenancy
description: >-
  Procedures and invariants for capability token admission, production fail-closed tenancy,
  X-Tenant-Slug/ID validation, scope enforcement, and cross-tenant data masking in AI-ASSIST.
---

# AI-ASSIST Authentication & Multi-Tenancy Runbook

Use this skill when auditing, testing, or updating authentication, tenant identification, scope checks, or cross-tenant security boundaries.

## Security Architecture & Invariants

1. **Bearer Capability Token**:
   - Every protected route requires `Authorization: Bearer <token>`.
   - In production (`SHADOWSPARK_ENV=production`), `SHADOWSPARK_API_TOKEN` is mandatory. Missing or blank token fails closed with `401 Unauthorized`.
   - Token validation uses constant-time comparison: `hmac.compare_digest(token, expected_token)`.
   - Raw tokens must never be exposed, logged, or stored. Derive non-sensitive truncated SHA-256 fingerprints (`token:<hash[:12]>`) for audit logging.
2. **Fail-Closed Production Tenancy**:
   - Production requests **must** specify tenant identity via `X-Tenant-Slug` or `X-Tenant-ID`.
   - Validated against slug regex: `^[a-z0-9][a-z0-9_-]{0,63}$`.
   - If tenant context is missing in production, request must fail closed (`400 Bad Request` or `401 Unauthorized`).
   - In test/dev mode without headers, fallback to `tenant_a` is permitted for deterministic local runner testing.
3. **Cross-Tenant Masking**:
   - Cross-tenant brief reads or foreign-tenant exception IDs must return `404 Not Found` indistinguishable from nonexistent entities.
   - Body `tenant_id` must match header tenant; mismatches return `400 Bad Request`.
4. **Scope Checks**:
   - Brief generation & inspection requires `compliance:read`.
   - Operator review annotation requires `compliance:review`.

## Verification Commands

```bash
# Run isolated auth unit tests
./.venv/bin/python -m pytest tests/test_auth.py -v

# Run API-level tenant isolation tests
./.venv/bin/python -m pytest tests/test_api.py -k "tenant" -v
```
