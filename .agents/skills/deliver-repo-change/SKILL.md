---
name: deliver-repo-change
description: Coordinate ShadowSpark application features, behavioral fixes, and requested releases through phased discovery, one bounded writer, independent review, and evidence-based delivery. Excludes documentation-only maintenance.
---

# Deliver a repository change

Read root `AGENTS.md` and recover relevant facts from `CURRENT_STATE.md`, checking them against Git and source. Read [the phase procedure](references/phases.md) when executing delivery and [role boundaries](references/roles.md) before dispatching agents.

Follow phases 0–15 in order. Testing is change-proportional; behavioral bugs require a reproducible failing regression test before the fix. Mark inapplicable checks and stages as skipped with a reason. Do not turn a local task into an unrequested deployment.

Use parallel read-heavy discovery and independent correctness/security review where useful. One implementer owns scoped edits by default. Parallel writers require separate worktrees and non-overlapping ownership. If delegation is unavailable, report that limitation rather than claiming independent review.

Freeze requirements and interfaces before implementation. If evidence changes the contract, record the change and repeat affected verification. Keep commits small. CI is required for delivery; local test success does not establish CI success.

Checkpoint changing facts in `CURRENT_STATE.md` and append evidence to `docs/agent-ledger.md`. Return a short **Changed / Verified / Open** report. Existing explicit authorization persists; phase transitions never grant permission for gated actions.
