---
source: CONCERN-2776
timestamp: '2026-09-16T18:49:45.564559+00:00'
title: audit behavior logic documentation for accuracy against reference implementation
type: learning
---

## Summary

During PR #2765 review, a question arose: does `docs/topics/behavior_logic/` still
accurately reflect the protocol as implemented in the reference implementation?

## Findings

An audit of `docs/topics/behavior_logic/` (24 pages) against the RMB, EMB, and CSB
spec families revealed:

**Status: mostly current, two concrete gaps.**

The PR-4 doc-update pass (planned in `notes/behavioral-conformance-specs.md`) was
substantially completed: 21 of 24 pages have Requirements sections with spec ID
citations; all base spec groups (RMB-01–14, EMB-01–13, CSB-01–14) are cited.

**Gap 1:** 12 newer spec groups have no doc coverage — RMB-15, EMB-14–19,
CSB-15–19. These were added after the initial doc update pass. Implementation
tracked in #3275.

**Gap 2:** The existing pages document the original design BTs from the legacy
`vultron/bt/` simulator, not behaviors as implemented in `vultron/core/behaviors/`.
Readers wanting the actual implementation have no reference. The `markdown-exec`
MkDocs plugin (already configured) + `py_trees.display.unicode_tree()` enables
auto-generated reference pages. Implementation tracked in #3276.

**Gap 3 (minor):** 3 pages (`msg_other_bt.md`, `acquire_exploit_bt.md`,
`id_assignment_bt.md`) have no Requirements section; they cover legacy simulator
behaviors with no normative spec group. These get legacy-design admonitions in #3276.

**Resolved**: 2026-09-16 — implementation tracked in #3275, #3276.
