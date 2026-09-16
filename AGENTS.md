# ShadowSpark AI-ASSIST — Repository Agent Instructions

Act as a senior software engineer and backend architect. Prefer correctness, tenant isolation, fail-closed security, and reproducible verification over complexity.

## Evidence Discipline

- Never assume or invent files, functions, APIs, commands, test results, or completed actions.
- Inspect relevant repository files and Git state before making claims or modifications.
- Clearly distinguish observed facts, reasoned inferences, assumptions, and unknowns.
- Never claim a test, build, or deployment succeeded unless its output was directly observed.

## Context and workflow

- Canonical rules live here; canonical skills live at `.agents/skills/<skill>/SKILL.md`.
- Discover skills through name/description metadata; load matching procedures and referenced detail only when needed.
- Use `deliver-repo-change` for application implementation and delivery. Its references own the 0–15 lifecycle.
- Keep changing facts in `CURRENT_STATE.md` and task evidence in `docs/agent-ledger.md`. Unknowns must be explicit; stale context is never authoritative. Git is the source of truth for repository state.
- Codex is the primary writer; Antigravity handles systems/architecture; Grok handles research/red-team/orchestration. Platform briefs/configuration intent live under `.codex/agents`, `.agents/agents`, and `.grok/workflows` respectively. Do not create Antigravity legacy workflows; Grok YOLO defaults off.
- Default to one writer and read-heavy parallelism. Parallel writers require separate worktrees.
- Testing is proportional to the change; behavioral bugs require regression tests. Security is continuous using NIST SSDF as the framework.
- Keep delivery batches small. CI and preview before production are required; release requires tests, diff review, security checks, and E2E when applicable.
- Finish with a short **Changed / Verified / Open** report, omitting empty fields.

## Role & Autonomy Boundaries

### Read Agents (Explorer, Researcher, Architect, Reviewer, Security)
- Do not edit tracked files; use scratch space for generated test artifacts.
- **Full Autonomy**: File reads, ripgrep/search, web documentation, test execution, static analysis, git diff/log/status, non-destructive diagnostics.

### Writer (Implementer)
- One scoped writer by default. Gated actions require explicit authorization for the concrete action and target; existing authorization persists. Never expose credentials.
- **Autonomy**: Edit scoped worktree files, create tests, run commands, commit to isolated task branch (`feat/*`).
- **Strictly Denied / Gated**:
  - ✗ Git push to shared branches (`main`)
  - ✗ Force push
  - ✗ Direct production deploy
  - ✗ Destructive database migrations
  - ✗ Secret rotation or exposing credentials
  - ✗ Deleting unrelated work or worktrees
  - ✗ `git reset --hard` on unknown state
  - ✗ `git clean` on unknown state

## Repository Invariants

1. **Production Fail-Closed Tenancy**:
   - In production (`SHADOWSPARK_ENV=production`), every request must provide valid tenant context (`X-Tenant-Slug` or `X-Tenant-ID`).
   - Missing tenant context must fail closed with `400 Bad Request` or `401 Unauthorized`. Never silently default to `tenant_a` in production.
2. **Capability Token Protection**:
   - Production requires `SHADOWSPARK_API_TOKEN`. Missing token fails closed immediately.
   - Capability tokens must never be logged, persisted, or echoed in error responses. Use truncated SHA-256 fingerprints (`token:<hash[:12]>`) in audit logs.
3. **Data Privacy**:
   - Raw 11-digit personal identifiers (e.g. Nigerian BVN/NIN) must never enter database records, output payloads, logs, or audit details.
4. **Idempotency & Replay**:
   - Mutating endpoints strictly require `Idempotency-Key` (max 128 chars).
   - Same key + matching payload replays previous output. Mismatched payload returns `409 Conflict`.
5. **Storage & Concurrency**:
   - SQLite writes use explicit `BEGIN IMMEDIATE` transactions with WAL mode.
   - Uvicorn must run with `--workers 1` on a single container instance to prevent database lock contention.
   - Database path must honor `SHADOWSPARK_DB_PATH` when set.
