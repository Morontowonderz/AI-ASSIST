---
name: ai-assist-render-e2e-ci
description: >-
  Procedures for local test suite execution, pytest environment isolation,
  CI workflows, and live Render deployment verification with scripts/render_e2e.sh.
---

# AI-ASSIST Render & CI/E2E Runbook

Use this skill when running the full test suite, updating CI pipelines, or verifying live Render deployments.

## Verification Procedures

1. **Local Test Suite**:
   - Run the complete test suite within the local virtual environment:
     ```bash
     ./.venv/bin/python -m pytest -v
     ```
   - All tests must pass with zero failures.
2. **Pytest Environment Isolation**:
   - [`tests/conftest.py`](file:///home/moronto/Documents/GitHub/AI-ASSIST/tests/conftest.py) defines an autouse `isolate_auth_env` fixture stripping shell environment variables (`SHADOWSPARK_ENV`, `SHADOWSPARK_API_TOKEN`) so developer environment settings do not pollute deterministic test runs.
3. **Vendored Regression Suite**:
   - [`tests/test_runner_regression.py`](file:///home/moronto/Documents/GitHub/AI-ASSIST/tests/test_runner_regression.py) asserts 20 baseline vendor runner invariants against the 4 static test fixtures in `vendor/`.
4. **Live Render Verification**:
   - Run the 6-stage automated verification script against the deployed service:
     ```bash
     SHADOWSPARK_API_TOKEN="<production_token>" \
     BASE_URL="https://shadowspark-ai-api.onrender.com" \
     ./scripts/render_e2e.sh
     ```
   - Stages verified:
     - Stage 1: `GET /healthz` -> 200
     - Stage 2: Missing Auth `POST /v1/compliance-review-brief` -> 401
     - Stage 3: Authenticated `POST /v1/compliance-review-brief` with Idempotency-Key -> 201
     - Stage 4: `GET /v1/review-queue/{brief_id}` -> 200 (`pending_review`)
     - Stage 5: `POST /v1/review-queue/{brief_id}/annotations` with Idempotency-Key -> 200 (`annotated`)
     - Stage 6: Re-fetch `GET /v1/review-queue/{brief_id}` -> 200 (`annotated`)
