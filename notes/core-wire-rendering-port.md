---
title: Core-to-Wire Rendering Port
status: active
kind: guidance
description: >
  Why core needs wire-shaped JSON at all, why core-side renderings with per-field
  patches are the wrong way to get it, and the driven-port seam core uses
  instead. Under ADR-0099 the port is the `CoreObject`'s own `by_alias` dump;
  core logic never dumps `by_alias` itself (ARCH-20-001, empty baseline in
  `test_core_by_alias_dumps.py`), and every received use case and trigger is
  given the port. Also: why `extra="forbid"` is the only guard for dropped flat
  fields, why persisted rows are unaffected, and why no wire class subclasses a
  core root.
related_specs:
  - architecture.yaml (ARCH-01-004, ARCH-12-001, ARCH-12-002, ARCH-12-003,
    ARCH-20-001, ARCH-20-002, ARCH-20-003, ARCH-20-005, ARCH-20-006, ARCH-21-002,
    ARCH-25-002 through ARCH-25-005)
  - vocabulary-model.yaml (VM-10-001, VM-08-002, VM-08-003)
  - case-ledger-processing.yaml (CLP-07-006, CLP-07-009, CLP-07-010, CLP-07-011,
    CLP-09-002)
  - status-dimension-objects.yaml (SDO-03-003, SDO-03-005)
  - datalayer.yaml (DL-05-001)
  - sync-ledger-replication.yaml (SYNC-02-003)
related_notes:
  - notes/wire-core-boundary.md
  - notes/vocabulary-registry.md
  - notes/wire-artifact-immutability.md
  - notes/sync-ledger-replication.md
related_adrs:
  - ADR-0063
  - ADR-0099
  - ADR-0107
---

# Core-to-Wire Rendering Port

Core logic obtains wire-shaped JSON through a driven port (`WireRenderPort`,
`vultron/core/ports/wire_render.py`), never by dumping or patching its own objects
(ADR-0063). Under ADR-0099 the adapter behind the port is
the core object's own `by_alias` dump, because core types carry the AS2 spelling
themselves (ARCH-25-002).

## The legitimate need

Core needs wire-shaped (AS2 camelCase) JSON in one situation: building
`CaseLedgerEntry.payloadSnapshot` values. The ledger wraps things received or sent
in managing the case, which are wire-shaped by definition: the snapshot MUST be
the asserted AS2 activity or a deterministic canonical normalization of it
(CLP-07-011), with nested objects inlined in full (CLP-07-006), so a receiver can
reconstitute it. camelCase is correct there; the question is only *how* it is
produced.

**When a core-side mechanism needs a per-field patch to reach the wire shape, the
mechanism is in the wrong layer.** A hand-patched snapshot dict (writing
`emConsentState` or `caseStatus` keys by hand) is a partial reimplementation of
the projection that drifts from it, and leaves every other nested type
unreconstitutable (CLP-07-010).

## The seam

A driven port, per ARCH-01-004 and the `SyncActivityPort` precedent.

- **Port**: `vultron/core/ports/wire_render.py`, `render(obj) -> dict[str, Any]`.
- **Adapter**: `vultron/adapters/driven/wire_render/as2.py`, returning
  `model_dump(by_alias=True, exclude_none=True, mode="json")`. No registry lookup,
  no `from_core()` (ARCH-20-002): aliases come from `CoreObject`'s
  `alias_generator=to_camel`, `@context` from its `by_alias` serializer, in
  exactly one place (VM-10).
- **Injection**: `BTBridge(wire_render_port=...)` publishes it to the blackboard,
  as `sync_port` is. A `DataLayerActionWithPorts` node calls
  `_require_wire_render_port()`, which raises `VultronWiringError` if absent.
- **Reach**: every received use case gets the port, because every received tree
  ends in a guarded ledger commit whose snapshot is an AS2 rendering. The inbox
  dispatcher wraps each port factory with `with_received_baseline_ports()`
  (`inbox_port_factories.py`), which also supplies `SyncActivityPort`
  (SYNC-02-003). Triggers get it through `RegistryTriggerDispatcher` and
  `SvcBTTriggerBase` (#3930). A use case without one fails closed at its first
  commit.

`render()` raises `VultronValidationError` only when the object is not a
`CoreObject` (a bare `CoreRecord` has no AS2 spelling, ARCH-20-003). **Never add a
core-shaped fallback**: a silently core-shaped snapshot is indistinguishable from
a correct one at the call site, which is what CLP-07-009 prevents.

The port is not ledger-specific: emitters, sync fan-out and the AS2 HTTP routes
need the same rendering. HTTP routes serve only a `CoreObject` or `as_Base`, and
`AS2JSONResponse` refuses anything else (ARCH-20-006).

### What did *not* move

Only *rendering* sits behind the port. The canonical commit stays in the
role-gated `CommitCaseLedgerEntryNode` (CLP-09-002). If you are designing "a
ledger-writing adapter", stop and re-read CLP-09.

### No new `by_alias` dumps in core

`test/architecture/test_core_by_alias_dumps.py` holds `by_alias=True` calls under
`vultron/core/` to an empty baseline (ARCH-20-005). Do not reopen it because a
subject is "already wire-shaped": `request.activity` in a received handler is the
extractor's core-branch `VultronActivity`, not the wire object that arrived. Where
core holds an AS2 form, it gets it from the adapter that built it (the
trigger-activity port returns `(activity_id, activity_blob)`, VM-08-003) or by
rendering the core activity.

`build_activity_payload_snapshot` (`core/use_cases/_snapshot_helpers.py`)
snapshots that rebuilt `VultronActivity`, a chosen subset of the inbound fields.
It is the "canonical normalization" branch of CLP-07-011, not the received
evidence VM-08-002 seals (see `notes/wire-artifact-immutability.md` § "Received
Evidence"; #3742).

## Dropped flat fields: `extra="forbid"` is the guard

`ParticipantStatus` and `CaseStatus` carry no flat-field shim
(`_migrate_flat_fields`, SDO-03-003). The flat keys (`rmState`,
`emConsentState`, …) are the AS2 spelling of each dimension field (ARCH-25-005),
accepted through `AliasChoices` as several spellings of one declared field.

A key matching no field must raise, never be dropped: under Pydantic's default
`extra="ignore"` a lost `rm_state` silently resets `rm.state` to `RM.START`, a
whole RM ladder lost with no error (#2232). `CoreObject`'s `extra="forbid"`
(ARCH-12-003) is the guarantee SDO-03-005 requires. Do not add a per-class
`model_validator(mode="before")` reject-guard for those keys; SDO-03-005 forbids
it.

## Persisted rows are not affected

`Record.from_obj` dumps without `by_alias`, so persisted rows are snake_case and
carry no `@context`. The inherited `alias_generator` never implies a
persistence-schema migration. Check it rather than trusting a claim either way:
dump `Record.from_obj(ParticipantStatus(...)).data_` and look at the keys.

## The `as_Object.model_config` override is gone, and why

**Rule:** never make a wire class subclass `CoreRecord` or `CoreObject` to reuse a
field or hook. `as_Base` stands on `pydantic.BaseModel` directly (ARCH-12-001)
and core has exactly two roots (ARCH-12-002); with no cross-branch inheritance,
`validate_assignment` from `CoreRecord` has no MRO path to leak into the wire
branch (ARCH-21-002), so `as_Object` needs no override to cancel it.

Ratchets: `test_wire_vocabulary_inherits_nothing_from_core` and `TestCoreRoots`
in `test/architecture/test_hierarchy_invariants.py`,
`test_core_roots_are_not_shared_with_the_wire_branch` in
`test/architecture/test_validate_assignment_ratchet.py`, and
`test_as_base_stands_directly_on_base_model` in
`test/wire/as2/vocab/base/test_wire_base_hierarchy.py`.
