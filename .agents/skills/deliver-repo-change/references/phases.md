# Delivery phases

| Phase | Action and evidence |
| --- | --- |
| 0 ROUTE | Identify task, scope, applicable skills, authorization, and local-versus-release intent. |
| 1 RECOVER | Inspect pwd, branch, HEAD, status, worktrees, runtime, and installed dependency versions. Verify relevant current-state facts. |
| 2 DECOMPOSE | Identify independent domains, dependencies, shared interfaces, and writer ownership. |
| 3 PARALLEL DISCOVERY | Assign bounded explorer, researcher, and security questions in parallel; collect source evidence and explicit unknowns. |
| 4 CONTRACT | Freeze requirements, interfaces, schema/error semantics, acceptance criteria, and exclusions in the task record. Architect resolves cross-domain conflicts. |
| 5 RED | For behavioral bugs, reproduce the bug with a failing regression test. For other changes, choose proportional checks; explain any skip. |
| 6 WRITE | One bounded implementer applies the minimal scoped change in an isolated task worktree. |
| 7 GREEN | Run targeted tests and relevant regressions; resolve failures. |
| 8 REVIEW | Parallel correctness and security review of the same diff/revision. Only the implementer applies fixes; rerun affected checks. |
| 9 VERIFY | Run full suite and configured lint/types/build checks as applicable, plus a credential scan. Record absent tooling and actual commands/results. Verify CI for delivery; unknown CI is not passing CI. |
| 10 DIFF | Inspect final scope, whitespace, status, credentials, generated artifacts, and contract compliance. |
| 11 COMMIT | Stage named task files; create a small atomic commit on the isolated task branch. Record its revision. |
| 12 PREVIEW / STAGING | When delivery is requested and authorized, deploy the reviewed revision to a non-production target; record target and revision. |
| 13 E2E | Verify applicable user flows and negative/access-control cases against that revision with isolated test data. Inspect scripts before using them against a live target. |
| 14 RELEASE | Require passing tests/CI, diff review, security check, applicable E2E, and preview evidence. Prepare concrete revision, target, impact, and rollback; obtain any missing production authorization before release. |
| 15 CHECKPOINT | Update current facts and ledger with evidence, skipped/gated stages, remaining unknowns, and next action. |

A task that does not request delivery skips deployment/release stages with a reason. Checkpoint documentation can receive a separate commit on the isolated branch; do not rewrite published history to add a checkpoint.

Security is continuous across discovery, contract, implementation, review, and release. Use NIST SSDF as the requested framework; do not claim certification or compliance merely because this procedure exists. Load authoritative framework detail on demand when a task requires a specific mapping.
