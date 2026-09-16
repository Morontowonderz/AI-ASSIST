---
name: ai-assist-persistence-sqlite
description: >-
  Procedures and operational rules for SQLite state management, WAL configuration,
  transactional atomicity, Render persistent disk requirements, and concurrency bounds.
---

# AI-ASSIST Persistence & SQLite Runbook

Use this skill when modifying database schemas, configuring storage paths, tuning transaction isolation, or managing Render persistent disks.

## Persistence Architecture

1. **Storage Path**:
   - Resolved via `SHADOWSPARK_DB_PATH` environment variable, defaulting to `./data/shadowspark.db`.
2. **SQLite PRAGMAs**:
   - `PRAGMA foreign_keys=ON`: Enforces cascading deletes and reference integrity.
   - `PRAGMA busy_timeout=5000`: Allows 5-second wait before database locked errors.
   - `PRAGMA journal_mode=WAL`: Write-Ahead Logging allows concurrent readers alongside writers.
3. **Transactional Boundaries**:
   - State mutations use explicit `BEGIN IMMEDIATE` transactions to prevent write lock race conditions.
   - Atomic brief creation writes to `briefs`, `review_queue`, and `audit_events` in a single transaction.
4. **Data Sanitization (`_safe`)**:
   - Data written to SQLite is pre-scanned. Standalone 11-digit numbers (BVN/NIN) or `Bearer ` tokens raise `ValueError` before persistence.
5. **Runtime Concurrency Bounds**:
   - **Worker Limit**: Must run with `--workers 1` on Uvicorn. Multi-process SQLite writing causes lock contention.
   - **Instance Limit**: Must deploy to a single container instance (no horizontal autoscaling on SQLite).
   - **Render Disk**: Render Web Services are ephemeral; a Persistent Disk must be mounted at the database directory.

## Verification Commands

```bash
# Run database schema and transaction tests
./.venv/bin/python -m pytest tests/test_database.py -v
```
