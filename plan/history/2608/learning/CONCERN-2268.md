---
source: CONCERN-2268
timestamp: '2026-08-19T19:10:55.902818+00:00'
title: 13 wire vocabulary classes still shadow a CORE_VOCABULARY type on the write
  path
type: learning
---

## Concern

Wire vocabulary `type_` values are *bare* names (`"CaseParticipant"`), not `as_`-prefixed, so the only write-path shape guard in `Record.from_obj` — `if obj.type_.startswith("as_")` — never fires for them. Measured during #2232: **15** wire classes have a `type_` that is also a key in `CORE_VOCABULARY`:

```text
CaseLedgerEntry, CaseParticipant, CaseReference, CaseStatus, EmbargoEvent,
EmbargoPolicy, ParticipantStatus, VulnerabilityCase, VulnerabilityRecord,
VulnerabilityReport, VultronApplication, VultronGroup, VultronOrganization,
VultronPerson, VultronService
```

Each can be written into a core-typed DataLayer row in the *wire* field shape, so whichever class reads the row back decides what the data means.

Issue #2232 fixed **2** of them — `CaseParticipant` and `ParticipantStatus` — by normalising via `to_core()` at the persistence boundary (`_NORMALIZE_WIRE_TO_CORE` in `vultron/adapters/driven/db_record.py`). Those two were prioritised because their shapes are *structurally* incompatible: core nests `rm: RmDimension` where wire carries a flat `rm_state`, so a wire-shaped row silently yielded `None` for `status.rm.state`.

The remaining **13** are unfixed. They are lower-severity today only because their wire and core shapes happen to differ by key spelling rather than by nesting — that is a coincidence, not an invariant.

**Resolved**: 2026-08-19 — implementation tracked in #2401, #2402. Structural Idea: #2403.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2400>.
Spec: `specs/datalayer.yaml` (DL-05-005).
