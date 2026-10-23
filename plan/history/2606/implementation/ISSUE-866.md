---
source: ISSUE-866
timestamp: '2026-06-22T20:02:29.346842+00:00'
title: 'FUZZ-07: Port report-to-others workflow fuzzer nodes'
type: implementation
---

## Issue #866 — FUZZ-07: Port report-to-others workflow fuzzer nodes

Ported all 21 report-to-others workflow fuzzer nodes from the legacy
`vultron/bt/report_management/fuzzer/report_to_others.py` to
`vultron/demo/fuzzer/report_management/report_to_others.py` using
py_trees class inheritance on the probabilistic base types introduced
in FUZZ-01.

**Nodes ported**: HaveReportToOthersCapability, AllPartiesKnown,
IdentifyVendors, IdentifyCoordinators, IdentifyOthers,
NotificationsComplete, ChooseRecipient, RemoveRecipient,
RecipientEffortExceeded, PolicyCompatible, FindContact, RcptNotInQrmS,
SetRcptQrmR, TotalEffortLimitMet, MoreVendors, MoreCoordinators,
MoreOthers, InjectParticipant, InjectVendor, InjectCoordinator,
InjectOther.

Each node has a semantic docstring with Automation potential per
BT-16-003. InjectVendor/InjectCoordinator/InjectOther inherit from
InjectParticipant. IdentifyVendors/IdentifyCoordinators use
SuccessOrRunning (never FAILURE). 147 unit tests added in
`test/fuzzer/report_management/test_report_to_others.py`.

PR: [#1115](https://github.com/CERTCC/Vultron/pull/1115)
