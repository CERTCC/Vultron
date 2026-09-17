---
source: CONCERN-3295
timestamp: '2026-09-17T17:02:23.220346+00:00'
title: Undocumented defensive code has twice masked a defect
type: learning
---

Two witnesses established that undocumented permissive/defensive code in this
codebase (a bare `except Exception` in `vultron/wire/as2/parser.py`, ISSUE-3217;
a failed-lookup `return <arbitrary Service>` in
`vultron/core/behaviors/sync/nodes/replay.py`, ISSUE-3192) each masked a single
bug-shaped cause rather than handling a real compatibility case. The absence of a
rationale comment is itself the signal.

**Resolved**: 2026-09-17 — the instrumentation methodology and the two-witness
watch-claim are promoted to `notes/testing-pitfalls.md` (§ "Instrument a
Permissive Fallback and Count What It Absorbs"). The claim is captured as a
watch-item (not yet a normative rule) per BW-07-005; the proposed repo-wide
inventory of undocumented permissive paths and a possible CS-series ratchet are
recorded there as a deferred Open Question.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3328>
