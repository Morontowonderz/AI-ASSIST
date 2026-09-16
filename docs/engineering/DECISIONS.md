# ShadowSpark AI-ASSIST — Architecture Decision Records (ADRs)

## ADR 001: Fail-Closed Tenant Context in Production

- **Status**: Accepted & Implemented (Commit `661ce7d`)
- **Context**:
  Previously, `shadowspark_api/auth.py` defaulted missing or empty tenant identities to `"tenant_a"` regardless of environment. In production, this allowed un-namespaced requests to leak or access `tenant_a` data silently.
- **Decision**:
  In production (`SHADOWSPARK_ENV=production`), omitting or passing an empty `X-Tenant-Slug` or `X-Tenant-ID` header raises `AuthenticationError("tenant identifier required in production")`, returning `401 Unauthorized`. In test and local development environments (`SHADOWSPARK_ENV!=production`), the default to `"tenant_a"` is retained to preserve test determinism.
- **Consequences**:
  - Positive: Eliminates multi-tenant data leakage in production.
  - Requirement: Upstream clients (e.g., `shadowspark-production`) must pass `X-Tenant-Slug` or `X-Tenant-ID` on all production requests.

---

## ADR 002: Dynamic Database Path Configuration via `SHADOWSPARK_DB_PATH`

- **Status**: Accepted & Implemented (Commit `661ce7d`)
- **Context**:
  The application factory defaulted to `./data/shadowspark.db` and ignored the documented `SHADOWSPARK_DB_PATH` environment variable. On Render, ephemeral root disks lose all SQLite database state across container deployments or restarts unless mounted to a Render Persistent Disk.
- **Decision**:
  Both `create_app(db_path=...)` and the root module instance `app = create_app()` resolve `SHADOWSPARK_DB_PATH` if provided:
  ```python
  resolved_db_path = db_path if db_path is not None else os.environ.get("SHADOWSPARK_DB_PATH", "./data/shadowspark.db")
  ```
- **Consequences**:
  - Positive: Operators can point the SQLite database file to a mounted persistent volume (`/opt/render/project/src/data/shadowspark.db`) without modifying code.

---

## ADR 003: Review Queue Listing with Server-Side Pagination and State Filtering

- **Status**: Accepted & Implemented (Commit `db9d309`)
- **Context**:
  The initial implementation only exposed `GET /v1/review-queue/{brief_id}`, requiring clients to know `brief_id` in advance. Operators had no mechanism to browse pending reviews.
- **Decision**:
  Implement `GET /v1/review-queue` supporting:
  - Query parameters: `limit` (integer, default 50, bounded 1-100), `offset` (integer, default 0, bounded >= 0), and optional `state` (`pending_review` or `annotated`).
  - Strict tenant filtering: `WHERE q.tenant_id = ?`.
  - Ordered descending by `q.created_at`.
  - Schema returns `ReviewQueueListResponse` with item summaries and total count.
- **Consequences**:
  - Positive: Frontend review consoles can render paginated tables of pending reviews.

---

## ADR 004: Strict Idempotency Key Validation and Payload Binding

- **Status**: Accepted & Implemented (Commit `9a796b6`, `661ce7d`)
- **Context**:
  Mutating operations (`POST /v1/compliance-review-brief` and `POST /v1/review-queue/{brief_id}/annotations`) in distributed environments risk duplicate execution or partial writes during network retries.
- **Decision**:
  - Mandate `Idempotency-Key` header on all mutating POST requests (max length 128 characters). Missing key returns `400 Bad Request`.
  - Compute SHA-256 hash of canonical request payload (`Database.request_hash(payload)`).
  - Check `(tenant_id, idempotency_key)` tuple:
    - If key matches and payload hash matches: replay original response (`201 Created` or `200 OK`, with `replayed: true`).
    - If key matches and payload hash differs: raise `409 Conflict`.
  - For annotations, enforce unique partial index `uq_annotations_tenant_brief_idem`.
- **Consequences**:
  - Positive: Guarantees exact-once execution and prevents duplicate brief creation and duplicate annotation entries.

---

## ADR 005: Single Uvicorn Worker Process Model for SQLite WAL Concurrency

- **Status**: Accepted
- **Context**:
  SQLite write transactions use file locking. Multi-worker Uvicorn processes or horizontal container replicas competing for write locks across shared network or local files can encounter `sqlite3.OperationalError: database is locked`.
- **Decision**:
  - Enforce single worker process (`--workers 1`) and single container replica.
  - Enable WAL journal mode (`PRAGMA journal_mode=WAL`), foreign keys (`PRAGMA foreign_keys=ON`), and `PRAGMA busy_timeout=5000`.
  - Use `BEGIN IMMEDIATE` for all write transactions.
- **Consequences**:
  - Positive: Eliminates multi-process write contention and lock contention.
  - Note: If throughput requirements scale beyond a single node in future phases, PostgreSQL migration should be adopted.

---

## ADR 006: Non-Disclosure of Sensitive Identifiers & Key Fingerprinting

- **Status**: Accepted
- **Context**:
  Compliance reviews may contain national identity numbers (BVN, NIN) or raw capability tokens which must not be leaked into audit tables, exception responses, or server logs.
- **Decision**:
  - Enforce `_RAW_ID` regex check on exception inputs (`(?<!\d)\d{11}(?!\d)`). Any raw 11-digit identifier triggers `422 Unprocessable Entity`.
  - In `shadowspark_api/auth.py`, derive a SHA-256 key fingerprint (`token:<sha256(token)[:12]>`) rather than logging or storing the raw secret.
  - Before writing to SQLite, `_safe()` asserts that payloads do not contain `_RAW_ID` matches or `Bearer ` substrings.
