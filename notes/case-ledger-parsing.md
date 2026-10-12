---
title: Case Ledger JSONL Parsing — State Extraction and Tolerant Parsing Patterns
status: active
kind: guidance
description: >
  Rules for consumers of case-ledger JSONL: search every nesting layer and every
  live spelling of RM/EM/VF/D/PXA state, tolerate one malformed row, and
  partition multi-case logs by case.
related_specs:
  - specs/case-ledger-processing.yaml
  - specs/demo-report.yaml
related_notes:
  - notes/case-ledger-authority.md
  - notes/sync-ledger-replication.md
relevant_packages:
  - vultron/core/behaviors/sync
  - vultron/demo/report.py
  - test/ci/invariants/common.py
---

# Case Ledger JSONL Parsing — State Extraction and Tolerant Parsing Patterns

The reference implementation is `vultron/demo/report.py` (`_candidate_dicts`,
`_dimension_state`); `test/ci/invariants/common.py` holds the invariant-side
accessors. Reuse them instead of writing a new walker.

## Search Every Layer and Every Spelling

A dimension state in a `payloadSnapshot` can sit at several depths and in several
spellings, all of which occur in real devlogs. A consumer that misses one reports
`None` for every affected row (#2232).

- **Depth**: the snapshot root, `object` / `object_` (an `Add` activity), a
  nested `caseStatus` / `case_status`, and each item of a case's
  `caseStatuses` list.
- **Spelling**: the bare value (`{"rm": "ACCEPTED"}`, ADR-0099), the one-key
  mapping (`{"rm": {"state": "ACCEPTED"}}`, ADR-0036), and the flat legacy keys
  (`rmState`, `rm_state`). Logs older than ADR-0075's VF/D split carry
  `vfd_state`, which nothing translates.

Confirm the current shape with `model_dump(by_alias=True)` on the status model
instead of guessing.

## Tolerate One Bad Row

One malformed entry must degrade one timeline row, not abort the report through
the `ReportError` boundary:

- A corrupt `logIndex` coerces to a fallback (for example `-1`).
- `payloadSnapshot.actor` may be an inline object; take its `id`
  (DRPT-02-003).

## Partition Multi-Case Logs (DRPT-02-006)

`log_index` restarts at 0 per case, and actor directory names (`finder`,
`vendor`) recur across demos. So group by `case_id` first, order by
`(case_id, log_index)`, and compute replica-presence per case. A merged timeline
interleaves `0, 0, 1, 1, …` and collapses same-named actors into one column.
