# ShadowSpark Compliance Review V1

Read-only, fixture-backed FastAPI pilot for the Compliance Review exception brief.

## Run locally

```text
./.venv/bin/python -m pytest -q
./.venv/bin/uvicorn shadowspark_api.app:app --host 127.0.0.1 --port 8000
```

Use `Authorization: Bearer ss_test_redacted` and an `Idempotency-Key`. The SQLite path is
`SHADOWSPARK_DB_PATH` when set, otherwise `./data/shadowspark.db`.

This slice has no network calls, real model, execute tools, Temporal workflow, or production
personal data. The fixture runner remains vendored under `vendor/` and is regression-tested.
