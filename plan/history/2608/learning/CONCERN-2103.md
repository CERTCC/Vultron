---
source: CONCERN-2103
timestamp: '2026-08-24T17:41:23.873720+00:00'
title: 'ADR + enum change: rename OTHER role to Observer (circulation blocker for
  draft spec)'
type: learning
---

## Concern

`docs/reference/draft-vultron-spec.md` Open Question #6: renaming the `OTHER`
role to **Observer** needs an ADR, and the enum change needs to be carried into
the implementation. The PR #2078 body names this as a circulation blocker.

## Relationship to #2093

These are deliberately distinct, and the draft says so: *"renaming without
settling what an Observer is only relabels the ambiguity."*

- **#2093** — what an Observer *is*: admission path and content scope
- **this issue** — the `OTHER` → Observer rename decision plus the enum change

## Resolution

**Resolved**: 2026-08-24

At planning time, all three scope items were already complete:

- **ADR recording the rename decision** → ADR-0057 accepted 2026-08-11
- **Enum change (`OTHER` → `OBSERVER`) and all call sites** → #2192 closed
- **Open Question #6 struck** → already struck (`~~Observer rename ADR~~`)

Remaining gap: §7.3.1 `†`-footnote still contained stale text ("implementation
tracked in a separate issue") pointing to the now-closed #2192. Removed in the
docs PR below.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2519>
