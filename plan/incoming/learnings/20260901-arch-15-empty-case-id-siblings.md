---
title: CheckCaseStatusIdempotencyNode and AppendCaseStatusToCaseNode lack ARCH-15-001 guard for empty case_id
type: learning
timestamp: 2026-09-01
source: ISSUE-2966
signal: concern
---

In `add_case_status_tree.py` line 114, `case_id = request.case_id or ""` coerces None to
empty string, which is then passed directly to `CheckCaseStatusIdempotencyNode` and
`AppendCaseStatusToCaseNode`. Both nodes call `self.datalayer.read_case(self.case_id)` and
fail with `"Case '' not found"` — the same opaque ARCH-15-001 anti-pattern fixed in
`EmitCaseStatusUpdateNode` by ISSUE-2966. Those nodes do not yet have an early guard that
returns FAILURE with a diagnostic when case_id is absent/empty.
