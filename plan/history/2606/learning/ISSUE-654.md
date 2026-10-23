---
source: ISSUE-654
timestamp: '2026-06-11T18:34:41.385633+00:00'
title: Surrogate-key resolution must treat ambiguous matches as errors
type: learning
---

## 2026-06-08 ISSUE-654 — Surrogate-key routing collision handling

- Surrogate-key resolution must treat ambiguous matches as errors, not
  first-match wins; otherwise actor/case lookups become non-deterministic when
  multiple canonical IDs share a tail segment.
- Case-key resolution should continue to short-key fallback even when
  `dl.read(key)` returns a non-case object; otherwise non-case IDs can shadow
  valid case keys and produce false 404/validation failures.

**Promoted**: 2026-06-11 — captured in `notes/codebase-structure.md` §
"Surrogate-Key Routing Collision Handling" and `AGENTS.md` pitfalls.
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
