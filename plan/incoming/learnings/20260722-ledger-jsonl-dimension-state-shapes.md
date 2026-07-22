---
title: Case-ledger JSONL state extraction must handle three nesting shapes plus flat legacy spellings
type: learning
timestamp: 2026-07-22T00:00:00Z
source: ISSUE-1307
---

## Observation

When distilling RM/EM/VFD/PXA state from a case-ledger entry's
`payloadSnapshot` (as the demo report tool does), the state may live in any of
several shapes that all appear in real devlogs:

- **ADR-0036 dimension objects** on a `ParticipantStatus`/`CaseStatus`:
  `{"rm": {"state": "ACCEPTED"}, "vfd": {"state": "VFd"}}`,
  `{"em": {"state": "ACTIVE"}, "pxa": {"state": "Pxa"}}`.
- **Legacy flat wire spellings**: `{"rmState": "CLOSED", "vfdState": "VFD"}`
  (and snake `rm_state`/`vfd_state`). The status models' `_migrate_flat_fields`
  validators accept these, so historical logs contain them.
- **Nested under an `Add` activity**: the status object is often
  `payloadSnapshot["object"]` (or `object_`), and a `CaseStatus` may itself be
  nested under `payloadSnapshot["object"]["caseStatus"]`.

The robust approach is a small recursive "candidate dicts" collector that walks
`object`/`object_`/`caseStatus`/`case_status` from the snapshot root, then a
per-dimension extractor that checks `{key: {"state": ...}}` first and falls
back to each flat alias. This mirrors the defensive accessors already in
`test/ci/test_case_ledger_invariants.py` (`_participant_status_identity_and_rm`,
`_cs_observations_from_snap`) but generalises them for a single dimension.

## How to apply

Any new consumer of case-ledger JSONL (reports, invariant checks, dashboards)
should reuse this three-shape + flat-alias tolerance rather than assuming the
current serialization. Confirm real shapes by dumping
`ParticipantStatus`/`CaseStatus` with `model_dump(by_alias=True)` — the
dimension objects serialize as `{"rm": {"state": ...}}`, not flat `rmState`.
See [[20260722-test-demo-tests-auto-marked-integration]] for how to actually
run the resulting tests.
