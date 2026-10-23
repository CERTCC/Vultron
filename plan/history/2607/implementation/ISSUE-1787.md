---
source: ISSUE-1787
timestamp: '2026-07-29T21:02:29.907460+00:00'
title: CREATE_CASE_PROPOSAL phrase regression tests
type: implementation
---

**Issue:** #1787 — CREATE_CASE_PROPOSAL phrase had an unused `{target}` slot
that rendered as a trailing em-dash (`"Vendor proposed a case to —"`).

**Root cause:** The registry phrase `"{actor} proposed a case to {target}"`
referenced a `{target}` slot, but `create_case_proposal_activity` builds a
`Create(as_CaseProposal)` with no `target` field, so the slot always fell back
to the em-dash placeholder in `vultron/demo/report.py`.

**State on arrival:** The code fix (phrase → `"{actor} proposed a new case"`)
had already landed on `main` in commit `f415f83a` via a docs/learn PR that
carried no `Closes #1787` footer, so the issue stayed open with no regression
guard.

**Fix:** Added two regression tests — a root-cause guard in
`test/test_semantic_registry.py` asserting the phrase carries no `{target}`
slot, and a symptom-level render test in `test/demo/test_report.py` asserting
`CaseTimelineEvent.summary` produces `"Vendor proposed a new case"` with no
`"—"`. Both fail on the old phrase and pass on current `main`. The existing
SE-07 phrase tests could not catch this because they fill every slot via a
`defaultdict`. Recorded two learnings (process-issue + concern).

**PR:** <https://github.com/CERTCC/Vultron/pull/1828>
