---
source: CONCERN-3917
timestamp: '2026-10-01T17:14:00.168939+00:00'
title: add_object_to_case queues an Add with no recipients
type: learning
---

## Observation

`TriggerActivityPort.add_object_to_case(actor, object_id, case_id)` takes no recipients, and `add_object_trigger_bt` queues the resulting `Add(object, target=case)` on the actor's outbox via `UpdateActorOutbox`. The sealed body therefore carries no `to:`, and the outbox handler refuses it with `VultronOutboxToFieldMissingError` (OX-08-001/003) on every attempt until it dead-letters (OX-13-002).

Found while auditing every trigger-port method for sealed-body completeness (#2655): the audit had to exempt this one method from its "recipients present" check because the port signature cannot supply any. The same held before the sealed-body change — `_validate_to_field` refused the re-read record for the same reason — so this is pre-existing, not a regression.

## Why it matters

The `trigger/add-object-to-case` route (TRIG-10-001) reports 202 and the activity is recorded, but nothing ever reaches a participant. Either the port method should take recipients (the case participants, as `add_note_to_case` does) or the trigger should not queue the activity at all.

## Where

- `vultron/core/ports/trigger_activity.py::add_object_to_case`
- `vultron/adapters/driven/trigger_activity_adapter/cases.py::add_object_to_case`
- `vultron/core/behaviors/case/add_object_trigger_tree.py`
- `test/adapters/driven/trigger_activity_adapter/test_sealed_body_audit.py` (the exemption)

Governing specs: OX-08-001, OX-08-003, TRIG-10-001

---

Resolved: 2026-10-01 — implementation tracked in #4041, #4042.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4040>

- #4041: the trigger's `Add` is addressed only to the CASE_MANAGER
  (PCR-08-005), and an object type no receive pattern routes as
  `Add(object, case)` is refused with 422 (TRIG-10-001).
- #4042: ledger fan-out applies the CM-10-004 embargo content gate. It pauses
  non-signatories and backfills them in log order once admitted
  (CM-10-005, CM-10-006).

Spec: `specs/triggerable-behaviors.yaml` (TRIG-10-001),
`specs/case-management.yaml` (CM-10-005, CM-10-006)
Notes: `notes/participant-embargo-consent.md`,
`notes/sync-ledger-replication.md`
