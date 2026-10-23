---
title: CLP-14 runtime checks unwired at chain.py call site
type: learning
timestamp: "2026-08-28T00:00:00Z"
source: ISSUE-2679
signal: concern
---

`_validate_canonical_entry` now accepts `case_published` and enforces CLP-14
timestamp invariants when it is provided, but the production call site in
`CreateLogEntryNode.update()` (`chain.py` line ~300) does NOT pass
`case_published`. Runtime enforcement therefore only fires when a caller
explicitly opts in; the chain commit path leaves CLP-14-002, -003, -006,
-007, and -008 to the post-hoc conformance harness.

Root cause: existing integration-test payload snapshots (in
`test_guarded_commit_tree.py`, `test_case_proposal_received_tree.py`, etc.)
do not include a `published` field. Wiring `case_published` into the call
site causes CLP-14-002 to reject those snapshots, breaking ~30 tests.
Fixing properly requires either adding `published` to all test payload
fixtures or making CLP-14-002 conditional on payload having the field.

Follow-up issue needed: "Wire case_published into CreateLogEntryNode.update()
call to_validate_canonical_entry; update test fixtures to include published
in payload snapshots."

## Audit disposition (2026-09-02)

Filed as #3043.
