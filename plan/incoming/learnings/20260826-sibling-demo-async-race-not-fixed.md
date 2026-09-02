---
title: "6 sibling demo scenarios have same async race window as fcv-reject (#2390)"
type: learning
timestamp: "2026-08-26T00:00:00Z"
source: ISSUE-2390
signal: concern
---

The `_phase_sync_verification` fix (wait_for_case_on_container +
wait_for_contiguous_ledger_coverage before the notes phase) was added only to
`fcv_reject_demo.py`. The following 6 sibling scenarios call
`participant_adds_note_to_case` in chained note-reply sequences and are subject to
the same race window when Finder/Coordinator has not yet replicated all ledger entries:

- `fv_demo.py`
- `fcv_demo.py`
- `fvv_demo.py`
- `fvcv_extension_demo.py`
- `fvcv_handoff_demo.py`
- `fcvcv_demo.py`

These received `Optional[as_Note]` type-safety fixes in this PR but not behavioral
async-race mitigations. Each should have a Bug issue filed and a
`_phase_sync_verification` (or equivalent) added before its notes phase.
