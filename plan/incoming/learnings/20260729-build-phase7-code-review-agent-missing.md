---
title: build Phase 7 references a code-review agent type that does not exist
type: learning
timestamp: 2026-07-29
source: ISSUE-1775
signal: tooling-issue
---

## What happened

The `build` skill Phase 7 ("Pre-PR Code Review") instructs the agent to
"Invoke the `code-review` agent against the current branch diff vs `main`."
No agent type named `code-review` (or `code-reviewer`) exists in this
environment's agent registry. The available types are: `claude`,
`claude-code-guide`, `Explore`, `general-purpose`, `Plan`,
`statusline-setup`.

## Workaround applied

Spawned a `general-purpose` agent with an explicit review prompt encoding the
ADR-0041 acceptance criteria and the codebase's validation invariants
(`_validate_canonical_entry`, `_CASE_AUTHORED_SIGNATURES`,
`_store_embedded_participants`). The review surfaced two real FAIL findings
that were fixed before the PR opened, so the phase's intent was met — but the
skill's literal instruction cannot be followed as written.

## Suggested fix

Either (a) register a dedicated `code-review` agent type, or (b) update the
`build` skill Phase 7 to invoke the `/code-review` (or `/review`) skill, or to
spawn a `general-purpose` agent with a standard review prompt. The current
wording causes an "Agent type not found" failure that a strict reading of the
skill cannot recover from.
