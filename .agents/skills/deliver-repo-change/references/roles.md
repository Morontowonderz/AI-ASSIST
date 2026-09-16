# Roles and autonomy

Read agents: **explorer**, **researcher**, **architect**, **reviewer**, and **security**. They may autonomously read files, grep/search, consult documentation, run tests/static analysis, inspect git diff/log/status, and perform non-destructive diagnostics. They do not edit tracked files. Test artifacts belong in scratch space; inspect unfamiliar commands for live side effects and avoid auto-fix modes.

The **implementer** may edit scoped worktree files, create tests, run task-related commands, and commit to an isolated task branch. One writer is the default. Parallel writers require separate Git worktrees and explicit non-overlapping ownership. Preserve pre-existing changes.

Gated actions: shared-branch pushes, force pushes, production deploys, destructive DB migrations, secret rotation, deleting unrelated work, and `git reset --hard` or `git clean` on unknown state. Require explicit authorization for the concrete action/target. Establish unknown Git state before considering cleanup. Never expose credentials. Existing authorization applies only within its scope.

Prepare a reviewable artifact and evidence before requesting missing approval. A role or phase does not expand authorization. Read agents return findings, paths/source links, evidence, and unknowns to the coordinator; only the implementer applies changes.

Platform routing: Codex is primary writer; Antigravity owns systems/architecture work; Grok owns research/red-team/workflow orchestration. Role briefs are descriptive instructions, not executable runtime registrations. Do not enable Grok YOLO mode by default or create Antigravity legacy workflows.
