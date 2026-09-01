# ShadowSpark FastAPI + SQLite Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fixture-only, read-only FastAPI service with SQLite-backed idempotency, review queue, annotations, and audit around the verified ShadowSpark V1.1.1 runner.

**Architecture:** Keep the verified runner and four fixtures in an immutable `vendor` boundary. A thin service layer performs capability admission, pre-fetch tenancy authorization, idempotency, runner execution, verification, and transactional persistence; FastAPI only maps HTTP to those interfaces. SQLite owns local review state and never changes an external system of record.

**Tech Stack:** Python 3.12, FastAPI 0.141.1, Pydantic 2.13.5, Uvicorn 0.52.4, HTTPX 0.28.1, SQLite, pytest 9.1.1.

**Spec:** `/mnt/c/Users/wonde/Documents/Codex/2026-09-01/review-recent-changes/docs/superpowers/specs/2026-09-01-shadowspark-fastapi-sqlite-design.md`

## Global Constraints

- One job only: read-only Compliance Review exception brief.
- Runtime tools remain `read_exception`, `read_policy`, and `read_verification_receipt`.
- Receipt keys remain `provider`, `check_type`, `result_code`, `ts`, and `correlation_id` only.
- Recommendation actions remain `request_evidence`, `escalate`, `no_change`, or `abstain`.
- The test capability is tenant/environment/scope metadata, not human identity.
- Cross-tenant denial occurs before fixture lookup and runner dispatch.
- Raw BVN/NIN never enters API output, SQLite, logs, audit details, prompts, embeddings, or memory.
- Annotation is untrusted local review text; it never enters runner input and never changes stored brief JSON or SoR state.
- No model, embeddings, Qdrant, customer data, Temporal, background worker, execute tool, or Railway deployment.
- Use `UV_CONCURRENT_INSTALLS=1`; do not replace the existing virtual environment.
- The directory has no Git metadata, so each task ends with explicit red/green evidence rather than a commit.

---

### Task 1: Vendor the verified core and establish regression compatibility

**Files:**
- Create mechanically: `vendor/runner.py`
- Create mechanically: `vendor/case_21_whatsapp_injection.json`
- Create mechanically: `vendor/case_09_cross_tenant.json`
- Create mechanically: `vendor/case_11_bvn_in_notes.json`
- Create mechanically: `vendor/case_13_budget_trip.json`
- Create: `vendor/__init__.py`
- Create mechanically then patch imports: `tests/test_runner_regression.py`

**Interfaces:**
- Consumes: verified V1.1.1 runner release files.
- Produces: `from vendor import runner` and the existing 20 regression tests.

- [ ] **Step 0: Install the one missing test dependency**

Run `UV_CONCURRENT_INSTALLS=1 uv pip install --python .venv/bin/python pytest==9.1.1`. FastAPI, Pydantic, Uvicorn, and HTTPX are already installed and must not be reinstalled.

- [ ] **Step 1: Write the failing vendor regression import**

Create `tests/test_runner_regression.py` from the verified runner tests, change the import to `from vendor import runner`, and point `FIXTURE_DIR` to `vendor`. Run collection before copying the vendor core.

- [ ] **Step 2: Verify RED**

Run `/home/wonde/ai-engineer/.venv/bin/python -m pytest tests/test_runner_regression.py -q`. Expected: collection fails because `vendor.runner` does not exist.

- [ ] **Step 3: Vendor exact verified files**

Copy the runner and four JSON fixtures from `/mnt/c/Users/wonde/Documents/Codex/2026-09-01/review-recent-changes/deployments/shadowspark-v1.1.1`, add an empty `vendor/__init__.py`, and compare source and destination SHA-256 values.

- [ ] **Step 4: Verify GREEN**

Run the regression file. Expected: 20 passed.

### Task 2: Capability admission

**Files:**
- Create: `tests/test_auth.py`
- Create: `shadowspark_api/__init__.py`
- Create: `shadowspark_api/auth.py`

**Interfaces:**
- Produces: `Principal`, `AuthenticationError`, `authenticate(authorization: str | None) -> Principal`, `require_scope(principal, scope) -> None`.

- [ ] **Step 1: Write failing capability tests**

Tests assert missing/malformed/unknown Bearer values fail; `Bearer ss_test_redacted` returns tenant `tenant_a`, environment `test`, key ID `ss_test_redacted`, and both frozen scopes; and scope failure does not reveal token content.

- [ ] **Step 2: Verify RED**

Run the auth test file. Expected: import failure because `shadowspark_api.auth` does not exist.

- [ ] **Step 3: Implement minimal capability admission**

Use `hmac.compare_digest` against the test placeholder and return a frozen dataclass. Error messages are generic and never contain the supplied header.

- [ ] **Step 4: Verify GREEN**

Run the auth tests and regression tests.

### Task 3: SQLite state boundary

**Files:**
- Create: `tests/test_database.py`
- Create: `shadowspark_api/database.py`

**Interfaces:**
- Produces: `Database`, `IdempotencyConflict`, `StoredBrief`, `initialize()`, `find_idempotent()`, `store_brief()`, `record_denied()`, `get_review()`, and `append_annotation()`.

- [ ] **Step 1: Write failing database tests**

Tests use a temporary database and assert schema creation; WAL/foreign-key configuration; atomic brief plus queue storage; same-key/same-hash replay; same-key/different-hash conflict; tenant-filtered review reads; annotation append; byte-identical brief JSON after annotation; and absence of Authorization values and `22222222222` from the database file.

- [ ] **Step 2: Verify RED**

Run the database tests. Expected: import failure because `shadowspark_api.database` does not exist.

- [ ] **Step 3: Implement the minimal database adapter**

Use parameterized SQLite statements, one connection per operation, foreign keys, WAL, a 5-second busy timeout, explicit transactions, JSON canonicalization, unique `(tenant_id, idempotency_key)`, and constrained queue states.

- [ ] **Step 4: Verify GREEN**

Run database, auth, and regression tests.

### Task 4: Runner orchestration service

**Files:**
- Create: `tests/test_service.py`
- Create: `shadowspark_api/service.py`

**Interfaces:**
- Consumes: `Principal`, `Database`, `vendor.runner`, four fixture files.
- Produces: `FixtureRepository`, `ComplianceBriefService`, `BriefResult`, `NotFoundOrUnauthorized`, `VerificationFailure`.

- [ ] **Step 1: Write failing service tests**

Tests assert a foreign tenant reference returns before repository lookup; unknown and foreign references share one exception; Case 21 completes with injection flag; Case 11 output/database omit the synthetic identifier; Case 13 stops before the third tool and reports HTTP status 429; replay avoids a second runner invocation; changed-body key reuse conflicts; successful execution creates one queue row; and a failed runner score creates no brief.

- [ ] **Step 2: Verify RED**

Run the service tests. Expected: import failure because `shadowspark_api.service` does not exist.

- [ ] **Step 3: Implement minimal orchestration**

Hash the canonical request, authorize tenant-prefixed references before repository access, resolve only the three authorized synthetic fixture IDs, check idempotency before running, execute the vendored runner, require `score.passed is True`, persist verified output transactionally, and expose 200 or 429 without retry.

- [ ] **Step 4: Verify GREEN**

Run service, database, auth, and regression tests.

### Task 5: FastAPI transport and operator annotation

**Files:**
- Create: `tests/test_api.py`
- Create: `shadowspark_api/schemas.py`
- Create: `shadowspark_api/app.py`

**Interfaces:**
- Produces: `create_app(db_path=None, fixture_dir=None) -> FastAPI`, module `app`, and the four approved endpoints.

- [ ] **Step 1: Write failing API tests**

Tests assert the health contract; strict request bodies; 11-digit identifier rejection; `401` capability failures; generic cross-tenant/unknown `404`; Case 21 `200`; Case 13 `429`; idempotent replay and `409` conflict; tenant-filtered queue read; required separate operator ID; annotation length bound; stored brief/SoR immutability; and no raw test Authorization header in SQLite.

- [ ] **Step 2: Verify RED**

Run the API tests. Expected: import failure because `shadowspark_api.app` does not exist.

- [ ] **Step 3: Implement schemas and routes**

Use Pydantic `extra="forbid"`, bounded strings, a validator rejecting standalone 11-digit identifiers, FastAPI dependencies for capability admission, exact HTTP error mapping, and annotation handling that never calls the runner.

- [ ] **Step 4: Verify GREEN**

Run the complete test suite. Expected: all tests pass with no warnings.

### Task 6: Runtime contract, local smoke test, and release package

**Files:**
- Create: `requirements.txt`
- Create: `railway.json`
- Create: `.gitignore`
- Create: `README.md`
- Create mechanically: `dist/shadowspark_fastapi_sqlite_v1.zip`
- Create: `dist/shadowspark_fastapi_sqlite_v1.sha256`

**Interfaces:**
- Consumes: completed package and tests.
- Produces: local run command, non-executed Railway start/health configuration, verified ZIP, and checksum.

- [ ] **Step 1: Record the observed compatible dependencies**

Record FastAPI 0.141.1, Pydantic 2.13.5, Uvicorn 0.52.4, HTTPX 0.28.1, and pytest 9.1.1 in the release requirements.

- [ ] **Step 2: Add runtime and staging configuration**

Set the Railway start command to `uvicorn shadowspark_api.app:app --host 0.0.0.0 --port $PORT`, health path `/healthz`, and bounded restart policy. Document that `railway up` is not executed and SQLite staging requires one replica plus `/app/data` volume.

- [ ] **Step 3: Run full verification**

Run `.venv/bin/python -m compileall -q shadowspark_api vendor tests`, `.venv/bin/python -m pytest -q`, start Uvicorn on `127.0.0.1` using a temporary database, request `/healthz`, stop the local process, and verify the database contains no forbidden identifier or Authorization header.

- [ ] **Step 4: Build and clean-room test the release**

Create the ZIP without `.venv`, caches, databases, or credentials. Verify safe archive paths and exact allowlisted members, extract to a temporary directory, run its complete tests with the existing virtual environment, and compute SHA-256.
