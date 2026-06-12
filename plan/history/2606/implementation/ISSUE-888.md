---
source: ISSUE-888
timestamp: '2026-06-12T13:06:57.153342+00:00'
title: Remove events field and record_event() from wire-layer VulnerabilityCase
type: implementation
---

## Issue #888 — Remove events field and record_event() from wire-layer VulnerabilityCase

Removed the duplicate `events: list[CaseEvent]` field and `record_event()` method
from the wire-layer `VulnerabilityCase` class. These were a layer-boundary violation:
wire-layer objects were accumulating domain state that belongs only in the core model.

**Changes:**

- Removed `CaseEvent` import, `events` field, and `record_event()` from
  `vultron/wire/as2/vocab/objects/vulnerability_case.py`
- Removed `events` and `record_event()` from `CaseModel` Protocol in `protocols.py`
- Removed `hasattr(obj, 'record_event')` from `is_case_model()` TypeGuard
- Removed `record_event()` calls from 7 BT/use-case call sites across
  embargo, case setup, participant, and received-actor modules
- Simplified `verification.py`: participant presence already validated via
  `actor_participant_index`
- Updated tests to use behavioral assertions (participant index, active_embargo,
  tree success) instead of the removed `case.events` field

**Outcome:** 3412 passed, 14 skipped, 3 xfailed in 57s. All 4 linters pass.
Core `VulnerabilityCase` retains `events`/`record_event()` (issue #792 handles
core removal). Wire-layer `from_core()` unaffected via Pydantic `extra='ignore'`.

PR: [#922](https://github.com/CERTCC/Vultron/pull/922)
