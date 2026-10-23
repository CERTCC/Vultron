---
source: ISSUE-727
timestamp: '2026-06-04T16:43:06.410750+00:00'
title: Migrate VulnerabilityReport, VulnerabilityRecord, CaseLogEntry to CoreObject
type: implementation
---

## Issue #727 — Refactor #699 step 4: migrate VulnerabilityReport + VulnerabilityRecord + CaseLogEntry to core

Step 4 of 7 in the #699 domain-object migration epic.

### What was done

- **`VulnerabilityReport`** (`core/models/report.py`): renamed from
  `VultronReport(VultronObject)`, now inherits `CoreObject`. Auto-registers in
  `CORE_VOCABULARY`. Backward-compat alias `VultronReport = VulnerabilityReport`
  preserved so the ~30 existing importers need no changes.
- **`VulnerabilityRecord`** (`core/models/vulnerability_record.py`): new module;
  `VulnerabilityRecord(CoreObject)` with `name` (required), `aliases`, and `url`
  fields. Mirrors the wire class that previously had no core counterpart.
- **`CaseLogEntry`** (`core/models/case_log_entry.py`): renamed from
  `VultronCaseLogEntry(VultronObject)`, now inherits `CoreObject`. The
  `model_validator` that auto-computes `id_` from `case_id/log_index` is
  preserved. Backward-compat alias `VultronCaseLogEntry = CaseLogEntry` keeps
  all existing importers working. Note: distinct from `case_log.CaseLogEntry`
  (in-memory hash-chain record).
- **Wire layer** (`wire/as2/vocab/objects/`): all three wire files updated to
  import core types under `CoreXxx` aliases; `VulnerabilityRecord` gained
  `from_core`/`to_core` methods it previously lacked; all three `to_core()`
  methods explicitly pop `context_` (wire/JSON-LD `@context` concern) before
  constructing the core domain object.
- **`vultron_types.py`**: exports `VulnerabilityReport` alongside `VultronReport`.
- **Tests**: `test_core_object.py` updated — `VultronReport` removed from the
  "not yet migrated" sentinel; positive `CORE_VOCABULARY` assertions added for
  all three new `CoreObject` subclasses.

### Key design note

`CoreObject.context_` is the JSON-LD `@context` field. Popping it in `to_core()`
prevents the wire value (`"https://www.w3.org/ns/activitystreams"`) from leaking
into the domain object, keeping the hexagonal boundary clean.

PR: [#775](https://github.com/CERTCC/Vultron/pull/775)
