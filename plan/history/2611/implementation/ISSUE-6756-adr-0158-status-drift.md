---
source: ISSUE-6756-adr-0158-status-drift
timestamp: '2026-11-20T15:12:18.993984+00:00'
title: Move ADR-0158 from accepted-provisional to accepted (status drift)
type: implementation
---

Bugfix for #6756. PR: https://github.com/CERTCC/Vultron/pull/6764

ADR-0158 was last updated on 2026-10-23, so by 2026-11-20 it was past day 28,
which puts it in lifecycle epoch 3 (MS-14-007). Its status stayed at
`accepted-provisional`, so the scheduled ADR Status Drift report flagged it.
The cause was elapsed time, not a code defect: a status moves forward only by
a commit (MS-14-022).

Outcome:

- `docs/adr/0158-...md`: `status: accepted-provisional` -> `accepted`.
  `updated` and `revision` are unchanged (MS-14-024).
- `docs/adr/index.md` regenerated with `adr-index --write`.
- `python -m vultron.metadata.adr.lifecycle --report-drift` now prints nothing
  and exits 0, so the drift report is clean.

