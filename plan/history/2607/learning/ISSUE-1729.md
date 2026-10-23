---
title: Concern — CREATE_CASE_PROPOSAL phrase produces trailing "to —" without activity target
type: learning
timestamp: "2026-07-28T00:00:00Z"
source: ISSUE-1729
signal: concern
---

The phrase `"{actor} proposed a case to {target}"` for `CREATE_CASE_PROPOSAL` will render as e.g. `"Vendor proposed a case to —"` when no activity target URI was extracted from the wire payload. This is inconsistent with other case-level phrases that avoid `{target}` slots.

Determine whether `CREATE_CASE_PROPOSAL` activities always carry an activity target in practice. If not, either make the phrase defensive (drop `{target}` slot) or document the required slot in the registry entry. Track as a Concern issue.

**Promoted**: 2026-07-28 — bug fixed in vultron/semantic_registry/case.py (phrase changed); tracked as ISSUE-1787.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1790>0>0>0>0>0>0>.
