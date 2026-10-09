---
title: Core-to-Wire Rendering Port
status: active
description: >
  Why core needs wire-shaped JSON at all, why core-side renderings with per-field
  patches were the wrong way to get it, and the driven-port seam core uses
  instead. Under ADR-0099 the port is the `CoreObject`'s own `by_alias` dump,
  with the `alias_generator=to_camel` and `@context` serializer inherited from
  `CoreObject`; core logic never dumps `by_alias` itself (ARCH-20-001, held to an
  empty baseline by `test_core_by_alias_dumps.py` since #3930), and every
  received use case and trigger is given the port. Covers the five consumers of the
  old core-side aliasing, the `extra="forbid"` guard that stands in for any
  flat-field reject-guard, and why persisted rows are unaffected.
related_specs:
  - architecture.yaml (ARCH-12-001, ARCH-12-002, ARCH-12-003, ARCH-18-002, ARCH-20,
    ARCH-20-001, ARCH-20-002, ARCH-20-003, ARCH-20-004, ARCH-20-006, ARCH-21-002)
  - vocabulary-model.yaml (VM-10-001, VM-08-002)
  - case-ledger-processing.yaml (CLP-07-011, CLP-07-006, CLP-07-009, CLP-07-010)
  - status-dimension-objects.yaml (SDO-03-003, SDO-03-005)
  - datalayer.yaml (DL-05-001)
  - sync-ledger-replication.yaml (SYNC-02-002, SYNC-02-003)
related_notes:
  - notes/wire-core-boundary.md
  - notes/vocabulary-registry.md
  - notes/wire-artifact-immutability.md
  - notes/sync-ledger-replication.md
related_adrs:
  - ADR-0017
  - ADR-0036
  - ADR-0062
  - ADR-0063
  - ADR-0082
  - ADR-0099
  - ADR-0107
---

# Core-to-Wire Rendering Port

Source: CONCERN-2260. Supersedes the known-deviation posture of #1991.

> **The decision stands; the ADR-0082 mechanism it named is superseded by
> [ADR-0099](../docs/adr/0099-one-object-model-as2-is-a-serialization.md).**
> Core logic obtains wire-shaped JSON through a driven port rather than by dumping
> or patching its own objects; that is unchanged and still correct. What changed
> is what the adapter does behind the port, and that core types now carry the AS2
> spelling themselves (ADR-0099 detail 2):
>
> 1. **The pairing registry is cancelled.** ADR-0082 was going to replace
>    `VOCABULARY.get(type(obj).__name__)` with a declarative pairing registry
>    (ARCH-23-001, #2937). ADR-0099 removes the second hierarchy instead, so there
>    is no counterpart to resolve. The port has collapsed to the core object's own
>    `model_dump(by_alias=True, exclude_none=True, mode="json")`, with `@context`
>    supplied by `CoreObject`'s `by_alias` serializer (ARCH-20-002). **ARCH-20-003**
>    has been amended to match: the port raises only when the object is not a
>    `CoreObject`; a missing wire counterpart is the normal case, not an error.
> 2. **The adapter-side translators are cancelled too.** ARCH-12-005's relocation
>    of `from_core`/`to_core` off the wire classes has nothing to relocate to.
>    Projection stays where it is until the paired classes are deleted, then goes
>    away with them.
> 3. **`@context` comes from the core serializer, not delivery.** ADR-0099 first
>    had the delivery step supply it; as built (#3490, recorded as an amendment in
>    the ADR) `CoreObject`'s serializer emits it on every `by_alias=True` dump. It
>    is supplied in exactly one place (VM-10), any `by_alias` dump of a core object
>    is complete AS2, and a persistence dump without `by_alias` carries none.
> 4. **`WireParsePort` (#2938) was rejected, not deferred.** This port only ever
>    addressed the **core→wire** direction of ARCH-01-001, and ADR-0082 proposed a
>    mirror-image `WireParsePort` for wire→core. ADR-0099 rejected it on three
>    grounds: it does not exist, its own AC-2 requires the pairing registry above,
>    and its single-method shape has no store access, so it could only fabricate
>    placeholders. `rehydrate()` owns ID-to-object materialisation instead
>    (VM-06-007).
>
> ADR-0082's *diagnosis* is still worth reading; only its remedy is replaced. See
> [notes/wire-core-boundary.md](wire-core-boundary.md).

## The legitimate need

Core code needs wire-shaped (AS2 camelCase) JSON in exactly one situation:
building `CaseLedgerEntry.payloadSnapshot` values.

That is not an accident of implementation. The case ledger wraps *things that
were received or sent to/from the case manager in the course of managing the
case*, and those things are by definition wire-shaped. The specs say so
directly:

- **CLP-07-011** — the snapshot MUST be the verbatim AS2 activity that was
  asserted, or a deterministic canonical normalization of it.
- **CLP-01-003 / CLP-01-004** — the ledger is the replication substrate;
  receivers project entries into their own replica.
- **CLP-07-006** — nested protocol objects MUST be embedded inline as full
  objects, not as ID strings requiring an out-of-band lookup.

Put together: a payload snapshot must be valid wire JSON that a receiver can
reconstitute. camelCase is *correct* there. The mistake was never "core produced
camelCase"; it was *how*.

## The wrong mechanism, and why it was worse than it looked

Eight `CoreObject` subclasses carried `model_config = ConfigDict(alias_generator=to_camel)`
so that core could call `model_dump(by_alias=True)`:

`ParticipantStatus`, `CaseStatus`, `VultronPerson`, `VultronOrganization`,
`VultronService`, `VultronApplication`, `VultronGroup`, `CoreActorCollection`
(since deleted as vestigial, #3563).

This violated ARCH-12-003 as it was then written; ADR-0099 detail 2 later
rewrote that requirement so every `CoreObject` inherits the generator on purpose.
The generator was never the real defect. Less obviously, **it did not work**. Core and
wire `ParticipantStatus` differ *structurally*, not just by spelling: core nests
`consent: PecDimension`, the wire shape carries a flat `emConsentState`. An alias
generator cannot bridge that, so `build_add_participant_status_snapshot` in
`vultron/core/behaviors/case/ledger_snapshots.py` hand-patched the dumped dict:

```python
if "consent" in status_dict and "emConsentState" not in status_dict:
    pec_state = status_dict.pop("consent", {}).get("state")
    if pec_state is not None:
        status_dict["emConsentState"] = pec_state
```

That is a partial reimplementation of `as_ParticipantStatus.from_core()` living
in core, covering one field of one type. Every *other* nested type was inlined in
whatever shape its core class happened to dump — so CLP-07-006 inlining was
silently unreconstitutable for anything that was not one of the eight aliased
classes.

The lesson generalises: **when a core-side mechanism needs a per-field patch to
reach the wire shape, the mechanism is in the wrong layer.** At the time the
wire branch owned the authoritative projection (`from_core()`), so anything
that duplicated part of it would drift. Under ADR-0099 the core object's own
`by_alias` dump is that projection, and the same lesson applies to it.

## The seam

A driven port, per ARCH-01-004 and the `SyncActivityPort` precedent.

- **Port**: `vultron/core/ports/wire_render.py`, a `typing.Protocol` with
  `render(obj) -> dict[str, Any]`.
- **Adapter**: `vultron/adapters/driven/wire_render/as2.py` — returns the
  object's own `model_dump(by_alias=True, exclude_none=True, mode="json")`. No
  `WIRE_TYPE_MAP` lookup and no `from_core()` (ARCH-20-002): the aliases come
  from `CoreObject`'s `alias_generator=to_camel`, and `@context` from its
  `by_alias` serializer.
- **Injection**: a `wire_render_port` parameter on `BTBridge.__init__`, published
  to the blackboard under `wire_render_port`, exactly as `sync_port` is
  (`vultron/core/behaviors/bridge.py`). Every `DataLayerActionWithPorts` node
  reads it as an optional input port and calls `_require_wire_render_port()`
  when it needs a rendering, which raises `VultronWiringError` if it is absent.
- **Reach**: *every* received use case gets the port, because every received
  tree ends in a guarded ledger commit whose snapshot is an AS2 rendering. The
  inbox dispatcher wraps each semantic's port factory with
  `with_received_baseline_ports()` (`inbox_port_factories.py`), and a use case
  that is not handed one fails closed at its first commit rather than dumping.
  The same wrapper gives every semantic the `SyncActivityPort`, because that
  commit is also fanned out (SYNC-02-003, #4113). Trigger
  use cases get it through `RegistryTriggerDispatcher` (built by
  `get_trigger_dispatcher` with an `As2WireRenderAdapter`) and
  `SvcBTTriggerBase` (#3930, #3833).
  Before #3930 only `CREATE_CASE_PROPOSAL` and `CLOSE_CASE` were given the port,
  so the snapshot path fell back to a core-side dump everywhere else.

`render()` **raises `VultronValidationError`** only when the object is not a
`CoreObject` — a bare `CoreRecord` (an offer or dead-letter record) or any
other model, none of which has an AS2 spelling (ARCH-20-003). Do not add a
core-shaped fallback: a snapshot that is silently core-shaped is
indistinguishable from a correct one at the call site, and is exactly what
CLP-07-009 exists to prevent.

The port is deliberately not ledger-specific. Emitters, sync fan-out, and the
AS2 HTTP routes all need the same rendering.

### What did *not* move

Only *rendering* moves behind the port. The canonical commit stays in the
role-gated `CommitCaseLedgerEntryNode`: **CLP-09-002** forbids bare canonical
commits from any production call site outside the guarded composition, and
CLP-10-005..008 constrain `execute()`. Moving the commit itself into an adapter
would breach both. If you find yourself designing "a ledger-writing adapter",
stop and re-read CLP-09.

## The five consumers of the old aliasing

Anyone touching this must account for all five. Rows 1, 2 and 5 are in core;
rows 3 and 4 are outside it and were the surprise. Row 5 depends on the *shim*
rather than the alias generator, and appeared after the planning baseline — see
the re-enumeration warning below.

| # | Site | What it did |
|---|---|---|
| 1 | `core/behaviors/case/ledger_snapshots.py` (`obj_to_inline_dict`, `build_add_participant_status_snapshot`) | Dumped core objects `by_alias=True` for CASE_MANAGER-synthesized bootstrap snapshots; hand-patched `consent` → `emConsentState`. Callers are `nodes/proposal_ledger.py` and `nodes/leave/record.py`. |
| 2 | `core/use_cases/_helpers.py` (`_inline_snapshot_reference_value`) | Dumped `dl.read()` results `by_alias=True` for CLP-07-006 inlining. `dl.read()` returns **core** objects per DL-05-001, so the alias generator was doing the wire projection here too. |
| 3 | `adapters/driving/fastapi/routers/actors/_routes.py` (`get_actor`, siblings) | `AS2JSONResponse(cls.model_validate(data).model_dump(mode="json", by_alias=True, exclude_none=True))` where `cls` is a **core** actor class — so core aliases shaped an externally-visible AS2 actor document. Resolved: under ADR-0099 detail 3 the core actor class *is* the AS2 class, so its own `by_alias` dump is the document; ARCH-20-006 now forbids serving any model that is not a `CoreObject` or `as_Base`, and `AS2JSONResponse` refuses one. |
| 4 | `vultron/demo/utils.py` | Same pattern, demo-only. |
| 5 | `core/behaviors/status/nodes/dimension_filter.py` (`_to_core_status`) | **Depended on the shim, not the alias generator.** Dumped a wire status `by_alias=True` and revalidated it through core `ParticipantStatus`, relying on `_migrate_flat_fields` to accept flat `rmState` (ARCH-20-007). Resolved: under ADR-0099 detail 3 the wire status *is* `ParticipantStatus`, so the function is now a bare `isinstance` check — no dump, no `to_core()` (ARCH-20-008, #3840). Added by ADR-0061, so it post-dated CONCERN-2260. |

One further site hand-writes camelCase into a snapshot dict, the same
anti-pattern as the `consent` → `emConsentState` patch and equally covered by
CLP-07-010:

- `core/behaviors/status/nodes/dimension_filter.py` `_build_patch` —
  `patch["caseStatus"] = {"emState": ..., "pxaState": ...}`

The pattern replicates: each new snapshot-producing site reinvents a little
wire spelling. That is the argument for the port, and it is why the fix has to
land in one pass rather than site by site.

> **The enumeration is closed (#3930).** `test/architecture/test_core_by_alias_dumps.py`
> counts `by_alias=True` calls under `vultron/core/` per file against a baseline
> that is now empty, so a new site fails the ratchet. Do not reopen it on the
> grounds that a subject is "already wire-shaped": the activity a received
> handler holds (`request.activity`) is the extractor's core-branch
> `VultronActivity`, not the wire object that arrived, and `create_activity` is a
> core `VultronCreateCaseActivity`. Where core genuinely holds a wire object — a
> stored outbound `Add(CaseParticipant)`, a received proposal's inline
> `as_CaseProposal` — it gets the AS2 form from the adapter that built it (the
> trigger-activity port returns `(activity_id, activity_blob)`, VM-08-003) or by rendering
> the core activity that carries it. The list above was accurate at ADR-0061.

Also vestigial: `CoreActor.to_json()` (`core/models/actor.py:76-77`) dumps
`by_alias=True` and has no callers in `vultron/`. Delete it — an
always-available bypass of the port seam will be picked up by the next agent who
needs camelCase (ARCH-20-005).

`build_activity_payload_snapshot` in `core/use_cases/_snapshot_helpers.py` does
not capture what arrived. What it snapshots is the extractor's rebuilt
`VultronActivity`, which keeps a chosen subset of the inbound fields, so the
receive-side snapshot is the "deterministic canonical normalization" branch of
CLP-07-011, not its "verbatim" one, and it is not the received evidence VM-08-002
seals (see `notes/wire-artifact-immutability.md` § "Received Evidence",
ISSUE-3947). Because that `VultronActivity` is a core-branch object, it renders
through the port like every other snapshot, and so do the stored objects it
inlines under CLP-07-006 (#3930). ADR-0107 step 5 (#3742) replaces the rendering
with that evidence recorded unchanged, deleting this site.

## Deleting a flat-field shim: the guard is mandatory

`ParticipantStatus._migrate_flat_fields` accepts `rm_state`/`rmState`,
`vf_state`/`vfState`, `d_state`/`dState`, `em_consent_state`/`emConsentState`
and rewrites them into the ADR-0036 / ADR-0075 dimension objects. It violates **SDO-03-003** ("MUST NOT be
retained as aliases or shim properties") independently of ARCH-12-003, so it has
to go.

**Do not delete it on its own.** Pydantic v2 defaults to `extra="ignore"`, so a
flat `rm_state` key would then be *silently discarded* and `rm.state` would
default to `RM.START` — a whole RM ladder lost with no error. That is the #2232
defect class and an ARCH-15-001/ARCH-15-002 violation. This is codified as
**SDO-03-005**.

**The guard is already in place, and it is not a reject-guard (#2940).**
`CoreObject` sets `extra="forbid"` (ARCH-12-003), so a key that matches no field
under any accepted spelling has nowhere to land and Pydantic raises by itself.
The inherited `alias_generator` does not weaken this: it adds the one AS2
spelling of each *declared* field, not a place for unknown keys. This is
what SDO-03-005 now requires: the guarantee MUST be `extra="forbid"`, and a
per-class `model_validator(mode="before")` reject-guard for those keys "MUST NOT
be added or retained for this purpose". The former mechanism
(`reject_wire_spelled_keys` in `vultron/core/models/_wire_spelling.py`, used by
`CaseParticipant._reject_wire_spelled_keys`) was **deleted** in #2940 — do not
revive it.

The flat dimension spellings are a separate matter, and are *kept*, not
retired. #2289 planned to remove `alias_generator` and then the `AliasChoices`
entries; it was closed as superseded by ADR-0099 (as was #2288, the same plan
for the actor classes), whose detail 5 makes each
dimension serialize to its bare state value. The flat key (`rmState`,
`emConsentState`, ...) is now the AS2 spelling of the dimension field itself, so
`AliasChoices` on `ParticipantStatus`/`CaseStatus` accepts the flat, snake_case
and field-name forms of one declared field. That is several spellings of a known
field, not an unknown key, so `extra="forbid"` is unaffected. What SDO-03-005
still forbids is a hand-written translator: `_migrate_flat_fields` is gone.

Raising is safe on the read path: `VultronValidationError` is already caught by
`DataLayer._from_row`, which falls back to `_wire_object_from_row` →
`_project_wire_row_to_core` → `to_core()` (ADR-0062, commit `b4406b2b`). A
wire-shaped row still reads back with the correct core shape.

## Persisted rows are not affected

`Record.from_obj` calls `obj.model_dump(mode="json", serialize_as_any=True)` —
**no `by_alias`** (`vultron/adapters/driven/db_record.py:367-369`). Persisted
rows are therefore snake_case. The `alias_generator` every `CoreObject` inherits
does not change the persisted key shape, and `@context` is emitted only on a
`by_alias` dump, so it never reaches a stored row either. Neither implies a
**persistence-schema migration**.

CONCERN-2260 was filed on the assumption that core-side aliasing changed the
persisted shape, and that assumption is false. If you are re-deriving this,
verify it the same way rather than trusting either the issue or this note:
dump `Record.from_obj(ParticipantStatus(...)).data_` and look at the keys.

## CM-18-006 and DRPT-02-008 no longer bear on the port

They once looked like reasons to keep core-side aliasing: CM-18-006 constrained the
consent/`emConsentState` relationship, and DRPT-02-008 obliged the demo-report
extractor to read `pec_state` from a snapshot. Both are moot since ADR-0122.
`ParticipantStatus` carries no consent, CM-18-006 now says consent is reproduced from
the ledger entry of the causing activity, and DRPT-02-008 (with -014 and -015) was
removed along with the report's PEC column. The port argument above stands on its own.

## The `as_Object.model_config` override is gone, and why

(ISSUE-2294, 2026-08-19; retired by ADR-0099 detail 4)

`as_Object` used to carry `model_config = ConfigDict(validate_assignment=False)`
to cancel the `validate_assignment=True` the wire branch would otherwise have
inherited from the shared core root through the MRO. That override is no longer
needed, and `as_Object.model_config` is now just `ConfigDict(frozen=True)`.

The reason is structural, not a changed Pydantic rule: `as_Base` now stands on
`pydantic.BaseModel` directly and inherits nothing from core (ARCH-12-001).
Core has exactly two roots, `CoreRecord` and `CoreObject(CoreRecord)`
(ARCH-12-002), and `validate_assignment` lives on `CoreRecord` through
`ValidatedAssignmentMixin`. With no cross-branch inheritance there is no MRO
path for the flag to leak along, so there is nothing to cancel (ARCH-21-002).
The same change retired the `_is_core_branch` sentinel and the #2416 guard in
the core `__init_subclass__` hooks, which existed only because wire classes
used to inherit the core root.

**Rule:** do not make any wire class subclass `CoreRecord` or `CoreObject` to
reuse a field or hook. That would reintroduce the leak this section used to
guard against. Ratchets: `test_wire_vocabulary_inherits_nothing_from_core`
and `TestCoreRoots` in `test/architecture/test_hierarchy_invariants.py`,
`test_core_roots_are_not_shared_with_the_wire_branch` in
`test/architecture/test_validate_assignment_ratchet.py`, and
`test_as_base_stands_directly_on_base_model` in
`test/wire/as2/vocab/base/test_wire_base_hierarchy.py`.
