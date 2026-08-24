---
title: "CreateAndPersistCaseActivityNode: only create_case_obj catches NoDataAvailable"
type: learning
timestamp: "2026-08-22T00:45:00Z"
source: ISSUE-1886
signal: concern
---

`CreateAndPersistCaseActivityNode.initialise()` catches `NoDataAvailable` only
for the `create_case_obj` port (test-driven: the fail-fast test asserts
`feedback_message` contains `"create_case_obj"`). The `create_case_addressees`
port is called without a try/except, so if it is absent the exception propagates
unhandled — the BT execution fails with an exception rather than returning
`Status.FAILURE` with a diagnostic `feedback_message`.

For consistency with the ARCH-15-001 pattern (all required-port reads either
set `feedback_message` on missing data or are guarded in `update()`) the other
required ports in `initialise()` should be wrapped the same way in a follow-up.
