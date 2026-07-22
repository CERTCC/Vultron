---
title: Demo report tool must partition the timeline by case_id, not merge everything under devlogs/
type: learning
timestamp: 2026-07-22T00:00:00Z
source: PR-1604
---

## Observation

The demo report tool (`vultron/demo/report.py`) originally followed DRPT-01-002
(recursively glob `**/*-case-ledger.jsonl` under the input dir, default
`devlogs/`) and DRPT-02-004 (merge all discovered entries into one timeline,
dedup by `entry_hash`, order by `log_index`) literally. Those two requirements
are only coherent when the input directory holds exactly **one case's**
replicas. In practice `devlogs/` accumulates `devlogs/{demo}/{actor}/…` across
multiple demo runs, so the default invocation can span several cases.

Consequences observed before the fix:

- `log_index` restarts at 0 per case, so two cases interleave as
  `0,0,1,1,…` in the merged timeline.
- Same-named actor directories (`finder`, `vendor`) recur across demos and
  collapse into one presence column, so the replica-presence matrix conflates
  unrelated cases.
- Dedup-by-`entry_hash` is unaffected (hashes are case-unique), so this is a
  presentation/semantics gap, not data corruption.

CI masks it (each demo-integration job starts with a fresh `devlogs/`), so the
green pipeline did not surface it — it only bites a developer running multiple
demos locally against the default root.

## How to apply

- This surfaced as a **spec gap**, not just a code bug: the fix required
  amending the spec (added DRPT-02-006, `refines` DRPT-02-004, spec version
  1.1.0 → 1.2.0) *and* the code, because DRPT-02-004's "single canonical
  timeline" is well-defined only within one case.
- Any consumer that merges case-ledger JSONL across a directory tree MUST carry
  `case_id` on its distilled model and group by it first (`(case_id, log_index)`
  ordering), compute presence per case, and render one section per case.
- Root-cause the tolerant-parsing story too: `from_raw` must coerce a corrupt
  `logIndex` (`int(...)` → `_coerce_int`) and a non-string `payloadSnapshot.actor`
  (inline actor object → `_actor_uri`) so one malformed field degrades a single
  row rather than escaping as an uncaught traceback past the `ReportError`
  boundary. See [[20260722-ledger-jsonl-dimension-state-shapes]] for the
  companion state-extraction shapes and
  [[20260722-test-demo-tests-auto-marked-integration]] for running the tests.
