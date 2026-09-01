---
title: Core-to-Wire Rendering Port
status: active
description: >
  Why core needs wire-shaped JSON at all, why `alias_generator=to_camel` on core
  types was the wrong way to get it, and the driven-port seam that replaces it.
  Covers the five consumers of the old core-side aliasing, the reject-guard
  required before any flat-field shim is deleted, and the failure modes to watch
  for during implementation.
related_specs:
  - architecture.yaml (ARCH-12-003, ARCH-20)
  - case-ledger-processing.yaml (CLP-07-001, CLP-07-006, CLP-07-009, CLP-07-010)
  - status-dimension-objects.yaml (SDO-03-003, SDO-03-005)
  - datalayer.yaml (DL-05-001)
related_notes:
  - notes/wire-core-boundary.md
related_adrs:
  - ADR-0017
  - ADR-0036
  - ADR-0062
  - ADR-0063
  - ADR-0081
---

# Core-to-Wire Rendering Port

Source: CONCERN-2260. Supersedes the known-deviation posture of #1991.

> **Mechanism revised by ADR-0081.** The decision recorded here — render core
> objects through a driven port rather than by aliasing core types — stands
> unchanged. Two things about the *implementation* change:
>
> 1. The adapter no longer resolves the wire counterpart with
>    `VOCABULARY.get(type(obj).__name__)`. That lookup depended on the bare-name
>    collision between the wire and core registries; it now goes through the
>    declarative pairing registry (ARCH-23-001).
> 2. The adapter no longer calls `wire_cls.from_core(obj)`. Projection moves off
>    the wire classes into translator modules on the adapter side (ARCH-12-005 as
>    amended), so that wire classes carry no domain knowledge.
>
> Note also that this port only ever addressed the **core→wire** direction of
> ARCH-01-001. The wire→core direction was still being served by core
> duck-typing `getattr(obj, "to_core", None)`; ADR-0081 adds the mirror-image
> `WireParsePort`. See [notes/wire-core-boundary.md](wire-core-boundary.md).

## The legitimate need

Core code needs wire-shaped (AS2 camelCase) JSON in exactly one situation:
building `CaseLedgerEntry.payloadSnapshot` values.

That is not an accident of implementation. The case ledger wraps *things that
were received or sent to/from the case manager in the course of managing the
case*, and those things are by definition wire-shaped. The specs say so
directly:

- **CLP-07-001** — the snapshot MUST be the verbatim AS2 activity that was
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
`VultronService`, `VultronApplication`, `VultronGroup`, `CoreActorCollection`.

This violated ARCH-12-003 (a MUST). Less obviously, **it did not work**. Core and
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
reach the wire shape, the mechanism is in the wrong layer.** The wire branch
already owns the authoritative projection (`from_core()`); anything that
duplicates part of it will drift.

## The seam

A driven port, per ARCH-01-004 and the `SyncActivityPort` precedent.

- **Port**: `vultron/core/ports/wire_render.py`, a `typing.Protocol` with
  `render(obj) -> dict[str, Any]`.
- **Adapter**: `vultron/adapters/driven/wire_render/as2.py` — looks the core
  `type_` up in the wire vocabulary, calls that class's `from_core()`, dumps with
  `by_alias=True, exclude_none=True`.
- **Injection**: a `wire_render_port` parameter on `BTBridge.__init__`, published
  to the blackboard under `wire_render_port`, exactly as `sync_port` is
  (`vultron/core/behaviors/bridge.py:107,185-190`).

`render()` **raises `VultronValidationError`** when no wire counterpart exists
(ARCH-20-003). Do not add a core-shaped fallback: a snapshot that is silently
core-shaped is indistinguishable from a correct one at the call site, and is
exactly what CLP-07-009 exists to prevent.

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
| 1 | `core/behaviors/case/ledger_snapshots.py` (`obj_to_inline_dict`, `build_add_participant_status_snapshot`) | Dumped core objects `by_alias=True` for CaseActor-synthesized bootstrap snapshots; hand-patched `consent` → `emConsentState`. Only caller is `case_proposal_received_tree.py`. |
| 2 | `core/use_cases/_helpers.py` (`_inline_snapshot_reference_value`) | Dumped `dl.read()` results `by_alias=True` for CLP-07-006 inlining. `dl.read()` returns **core** objects per DL-05-001, so the alias generator was doing the wire projection here too. |
| 3 | `adapters/driving/fastapi/routers/actors/_routes.py` (`get_actor`, siblings) | `AS2JSONResponse(cls.model_validate(data).model_dump(mode="json", by_alias=True, exclude_none=True))` where `cls` is a **core** actor class — so core aliases shaped an externally-visible AS2 actor document. Must route through `as_*` classes (ARCH-20-006). |
| 4 | `vultron/demo/utils.py` | Same pattern, demo-only. |
| 5 | `core/behaviors/status/nodes/dimension_filter.py` (`_to_core_status`) | **Depends on the shim, not the alias generator.** Dumps a wire status `by_alias=True` and revalidates it through core `ParticipantStatus`, relying on `_migrate_flat_fields` to accept flat `rmState`. Its own docstring says so. Must become `to_core()` (ARCH-20-007). Added by ADR-0061, so it post-dates CONCERN-2260 — re-enumerate before implementing. |

Two further sites hand-write camelCase into snapshot dicts, the same
anti-pattern as the `consent` → `emConsentState` patch and equally covered by
CLP-07-010:

- `core/behaviors/status/nodes/dimension_filter.py` `_build_patch` —
  `patch["caseStatus"] = {"emState": ..., "pxaState": ...}`
- `core/behaviors/case/nodes/accept_invite.py` `_build_snapshot` — a
  hand-built `{"type": "Add", ...}` fallback dict in the `else` branch

The pattern replicates: each new snapshot-producing site reinvents a little
wire spelling. That is the argument for the port, and it is why the fix has to
land in one pass rather than site by site.

> **Before implementing, re-run the enumeration.** `grep -rn 'by_alias=True'
> vultron/core/` and check each hit's subject. Sites that dump an
> *already-wire* object (a received `request.activity`, a reconstituted
> `create_activity`, `raw_proposal`) are fine and out of scope — ARCH-20-001 is
> deliberately scoped to core-*branch* objects for exactly this reason. The
> list above was accurate at ADR-0061; this area is under active change.

Also vestigial: `CoreActor.to_json()` (`core/models/actor.py:76-77`) dumps
`by_alias=True` and has no callers in `vultron/`. Delete it — an
always-available bypass of the port seam will be picked up by the next agent who
needs camelCase (ARCH-20-005).

`build_activity_payload_snapshot` in `core/use_cases/_helpers.py` is **not** in
this list and should be left alone: it captures a received activity verbatim
(CLP-07-001) by duck-typing, so core needs no wire import and no rendering. It
is the model the rest of the snapshot path should converge toward — synthesis is
only needed where there is no received activity to capture, i.e. case-proposal
bootstrap.

## Deleting a flat-field shim: the guard is mandatory

`ParticipantStatus._migrate_flat_fields` accepts `rm_state`/`rmState`,
`vfd_state`/`vfdState`, `em_consent_state`/`emConsentState` and rewrites them
into the ADR-0036 dimension objects. It violates **SDO-03-003** ("MUST NOT be
retained as aliases or shim properties") independently of ARCH-12-003, so it has
to go.

**Do not delete it on its own.** Pydantic v2 defaults to `extra="ignore"`, so a
flat `rm_state` key would then be *silently discarded* and `rm.state` would
default to `RM.START` — a whole RM ladder lost with no error. That is the #2232
defect class and an ARCH-15-001/ARCH-15-002 violation. This is codified as
**SDO-03-005**.

The guard mechanism already exists: `reject_wire_spelled_keys` in
`vultron/core/models/_wire_spelling.py`, used by
`CaseParticipant._reject_wire_spelled_keys`. Extend it to cover the retired flat
field names, then add a `model_validator(mode="before")` to each de-aliased
class.

Raising is safe on the read path: `VultronValidationError` is already caught by
`DataLayer._from_row`, which falls back to `_wire_object_from_row` →
`_project_wire_row_to_core` → `to_core()` (ADR-0062, commit `b4406b2b`). A
wire-shaped row still reads back with the correct core shape.

## Persisted rows are not affected

`Record.from_obj` calls `obj.model_dump(mode="json", serialize_as_any=True)` —
**no `by_alias`** (`vultron/adapters/driven/db_record.py:367-369`). Persisted
rows are therefore already snake_case. Removing `alias_generator` does not change
the persisted key shape and implies **no persistence-schema migration**.

CONCERN-2260 was filed on the assumption that it would, and that assumption is
false. If you are re-deriving this, verify it the same way rather than trusting
either the issue or this note: dump `Record.from_obj(ParticipantStatus(...)).data_`
and look at the keys.

## Do not re-read CM-18-006 as requiring the core alias

CM-18-006 constrains the consent/`emConsentState` relationship and looks at first
glance like it depends on core-side aliasing. It does not.
`as_ParticipantStatus.from_core(core).model_dump(by_alias=True)` yields
`emConsentState = SIGNATORY` and `embargoAdherence = True`; the *core* dump yields
`emConsentState = None`. The wire projection is what satisfies the spec, so
CM-18-006 needs no amendment — and it is evidence for the port, not against it.

## DRPT-02-008 needs no amendment either, and must not be pruned

CONCERN-2260 named DRPT-02-008 alongside CM-18-006 as an interacting
requirement. It obliges the demo-report extractor to read `pec_state` from
either the ADR-0036 dimension object (`{"consent": {"state": ...}}`) or any of
four legacy flat spellings (`emConsentState`, `em_consent_state`,
`embargoConsentState`, `embargo_consent_state`). Nothing in this work changes
that, for two reasons:

- The extractor is a **dict reader**, not a model consumer. `_dimension_state`
  in `vultron/demo/report.py:542-557` walks candidate dicts straight off the
  `payloadSnapshot`; it never validates through core `ParticipantStatus`. The
  reject-guards constrain what the *core model* accepts on the way in, so they
  are invisible to it.
- The two shapes DRPT-02-008 cares about most both stay reachable. CLP-07-009
  makes every snapshot wire-shaped, and the wire shape carries the flat
  `emConsentState` the extractor already handles; the dimension-object form
  still arrives from core-shaped historical dumps.

So do **not** treat the flat-spelling branches as dead code to delete while
implementing #2289. Narrowing what the core model accepts is not a licence to
narrow what a downstream reader tolerates — the extractor parses artefacts of
unknown vintage, and DRPT-02-008 is still a MUST.

## `as_Object.model_config` Override Is Load-Bearing Infrastructure

(ISSUE-2294, 2026-08-19)

`as_Object` in `vultron/wire/as2/vocab/base/objects/base.py` carries an
explicit `model_config = ConfigDict(validate_assignment=False)`. This is
**not** cosmetic: it blocks the cross-branch MRO inheritance path that
would otherwise propagate `validate_assignment=True` (set by
`ValidatedAssignmentMixin` on `VultronObject`) to all 65 wire vocabulary
classes — violating ARCH-12-002, which requires the wire branch to remain
lenient for inbound AS2 data.

Pydantic v2 merges `model_config` dicts in MRO order with the most-derived
class winning, so the `as_Object` override cancels the inherited `True` at
the wire boundary.

**Rule:** any future change to `VultronObject.model_config` MUST also update
`as_Object.model_config` if the change should not propagate to wire classes.
Do not remove or simplify the `as_Object` config override without tracing
the full MRO impact across `as_Base`, `VultronObject`, and all 65 wire
subclasses.

The broader fragility — cross-branch MRO coupling at `as_Object` — is
tracked by issues #2288/#2289 (the `alias_generator=to_camel` contamination,
same root cause). Full resolution requires completing the ADR-0017
wire→core separation.

## Once this lands

- The `xfail(strict=False)` on `test_no_core_object_has_to_camel_alias_generator`
  in `test/architecture/test_hierarchy_invariants.py` becomes a plain passing
  assertion, and **#1991 closes**.
- The known-deviation paragraph in `CaseParticipant._reject_wire_spelled_keys`'s
  docstring must be rewritten. It currently says, correctly for today, "Do not
  restate ARCH-12-003 as though it held throughout this subtree; it does not
  yet." After this work it *does*, and the nested `ParticipantStatus` no longer
  accepts `rmState`.
- `VultronPerson`'s docstring claim that it is 'Registered in
  `VOCABULARY["Person"]`' is stale — the six core actor classes are in
  `CORE_VOCABULARY` only. Fix it while you are in the file.
- The write-path shadowing-type work tracked by issues #2268 and #2402 is
  **done**: `_NORMALIZE_WIRE_TO_CORE` in `db_record.py` now covers all fifteen
  shadowing types, including the five actor types. Do not restate a "remaining"
  count. ADR-0081 deletes that gate entirely once `extra="forbid"` lands
  (ARCH-12-003).
