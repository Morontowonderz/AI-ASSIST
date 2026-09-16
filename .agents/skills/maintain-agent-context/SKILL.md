---
name: maintain-agent-context
description: Maintain this repository's AGENTS.md, skill instructions, references, and CURRENT_STATE.md when adding or reorganizing agent context or importing a GitHub skill. Use for agent-context maintenance, not ordinary application changes.
---

# Maintain agent context

1. Read the user's requested change and the affected context files. Check source files for any repository facts being added or updated.
2. For file placement or a GitHub import, read [references/context-layout.md](references/context-layout.md). Do not load unrelated skills or references.
3. Keep invariant rules in root `AGENTS.md`, selection metadata in skill frontmatter, procedures in `SKILL.md`, conditional detail in `references/`, and changing facts in root `CURRENT_STATE.md`.
4. Make the smallest useful edit. Keep each fact in one authoritative place and link to it when needed. Do not move detailed procedures into the always-loaded rules.
5. Check frontmatter, relative links, referenced paths, and factual claims. If a skill validator is available, run it on changed skills. Documentation changes alone do not require application tests.
6. Report **Changed**, **Verified**, and any **Open** items, including an unresolved GitHub source or unverified behavior.
