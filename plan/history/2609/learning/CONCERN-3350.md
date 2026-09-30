---
source: CONCERN-3350
timestamp: '2026-09-30T18:24:24.565995+00:00'
title: CS-05-002 "last resort" lazy imports measure as habit, not cycle breaks — PLC0415
  to be enabled
type: learning
---

## Concern

`specs/code-style.yaml` CS-05-002 states that when circular dependencies cannot
be resolved by reorganization, lazy initialization is to be used **as a last
resort**. A measurement taken while planning #2199 contradicts that framing:
ruff's `PLC0415` (`import-outside-top-level`) reports function-local imports
across `vultron/` and `test/` at a scale that makes the pattern routine rather
than exceptional. It is by a wide margin the single largest rule category in the
tree — larger than every genuine finding class combined.

The exact count is recorded in ADR-0094 with its measurement date (MS-16-001
forbids restating drifting counts here).

## Why this matters

CS-05-002 is a `MUST`-adjacent structural constraint that agents read as
authoritative when deciding whether a lazy import is acceptable. If the codebase
has thousands of them, one of two things is true, and the project does not
currently know which:

1. **The spec is describing an aspiration, not the design.** Function-local
   imports are in fact the accepted idiom here, and CS-05-002's "last resort"
   language is stale. In that case the spec should be reworded so agents stop
   treating each new lazy import as a concession.
2. **The spec is right and the codebase has drifted.** There is a large latent
   import-cycle problem that lazy imports have been papering over, and the real
   fix is structural — module reorganization, not import placement.

Either way, the current state is the bad one: a spec that reads as a strong
constraint while practice ignores it at scale teaches agents that the CS-*
requirements are advisory. That is the failure mode the spec corpus exists to
prevent.

## What this is not

This is **not** a request to enable `PLC0415`. #2199 deliberately excludes it,
with this issue cited as the reason, and that exclusion is correct regardless of
how this Concern resolves. Enabling the rule before the question is answered
would either bury the tree in noise or force thousands of mechanical rewrites
with no agreed target state.

## Suggested resolution path

- Sample the function-local imports and classify them: genuine cycle breaks,
  optional/heavy dependencies deferred for import time, and plain habit.
- If cycle breaks dominate, this becomes an architecture item (which module
  boundaries are cyclic, and why).
- If habit dominates, amend CS-05-002 to describe actual practice and consider
  enabling `PLC0415` with a scoped `per-file-ignores` for the legitimate cases.

## Reference

- Surfaced while planning #2199 (adopt ruff)
- Decision record: ADR-0094
- Spec: `specs/code-style.yaml` CS-05-002

**Resolved**: 2026-09-30 — implementation tracked in #3949 (enable `PLC0415`, hoist habit imports in `vultron/`, exempt `test/`, mark the genuine cycle breaks) and #3950 (remove the genuine import cycles behind every marker). Docs PR: <https://github.com/CERTCC/Vultron/pull/3948>. Spec: `specs/code-style.yaml` (CS-05-002 amended; CS-05-005, CS-05-006 added). Notes: `notes/lint-tooling.md`.

**Finding**: hoisting every function-local import in `vultron/` to module level and importing every module showed that only ten files genuinely break a cycle; the rest were habit, and most of the tree-wide total is test-local imports the requirement was never about. The spec was right; the gap was enforcement.
