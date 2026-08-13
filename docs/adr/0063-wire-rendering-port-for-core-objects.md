---
status: accepted
date: 2026-08-13
deciders: Allen Householder
consulted: Claude Code (planning agent for CONCERN-2260)
informed: Vultron contributors
---

# Render Core Objects to Wire JSON Through a Driven Port; Remove `alias_generator` From All Core-Branch Types

## Context and Problem Statement

Eight `CoreObject` subclasses set `model_config = ConfigDict(alias_generator=to_camel)`:
`ParticipantStatus`, `CaseStatus`, `VultronPerson`, `VultronOrganization`,
`VultronService`, `VultronApplication`, `VultronGroup`, and
`CoreActorCollection`. ARCH-12-003 forbids exactly this — `alias_generator=to_camel`
is a wire-specific concern and core-branch types MUST NOT carry it. The
violation has been tracked as a known deviation (#1991) behind an
`xfail(strict=False)` ratchet in `test/architecture/test_hierarchy_invariants.py`
for long enough that downstream code came to depend on it.

`ParticipantStatus` compounds the problem with a `_migrate_flat_fields`
`model_validator(mode="before")` that accepts flat wire spellings
(`rm_state`/`rmState`, `vfd_state`/`vfdState`, `em_consent_state`/`emConsentState`)
and rewrites them into the ADR-0036 dimension objects. SDO-03-003 says the old
flat enum fields MUST NOT be retained as aliases or shim properties after the
dimension migration — so this shim violates a MUST-level requirement
independently of ARCH-12-003.

The reason the alias generator is load-bearing rather than merely wrong is that
core code needs camelCase JSON for one specific purpose: building
`CaseLedgerEntry.payloadSnapshot` values. The case ledger's purpose is to wrap
"things that were received or sent to/from the case manager in the course of
managing the case", and those are by definition wire-shaped. CLP-07-001 requires
the snapshot to be the verbatim AS2 activity or a deterministic canonical
normalization of it, and CLP-01-003/CLP-01-004 make the ledger the replication
substrate that receivers project into their own replica. A payload snapshot must
therefore be valid wire JSON that a receiver can reconstitute — camelCase is
correct *there*.

So core reached for the nearest thing that produced camelCase: it set
`alias_generator` on the core class and called `model_dump(by_alias=True)`. That
is a wire concern implemented by mutating the domain model, and it does not even
work correctly: `build_add_participant_status_snapshot` in
`vultron/core/behaviors/case/ledger_snapshots.py` has to hand-patch
`consent` → `emConsentState` after the dump, because a core `model_dump` cannot
produce the wire's flat `emConsentState` field from the nested `PecDimension`.
That hand-patch is a partial, drifting reimplementation of
`as_ParticipantStatus.from_core()`.

Two additional consumers depend on the same core-side aliasing:
`_inline_snapshot_reference_value` in `vultron/core/use_cases/_helpers.py`
(CLP-07-006 inline nesting of `dl.read()` results, which are core objects per
DL-05-001), and `GET /actors/{id}` in
`vultron/adapters/driving/fastapi/routers/actors/_routes.py`, which dumps a
**core** actor class with `by_alias=True` straight into an `AS2JSONResponse`.

A fifth consumer depends on the *shim* rather than the alias generator:
`FilterParticipantStatusDimensionsNode._to_core_status` (added by ADR-0061)
normalises a wire status by dumping it `by_alias=True` and revalidating through
core `ParticipantStatus`, and its docstring names the dependency outright — "the
core model's `_migrate_flat_fields` validator accepts that shape, so a
dump-and-revalidate normalises both". The shim and that idiom have to retire
together.

The hand-patching is likewise not confined to one site: `_build_patch` in the
same module writes `patch["caseStatus"] = {"emState": ..., "pxaState": ...}`,
and `accept_invite.py`'s `_build_snapshot` hand-builds a wire-spelled fallback
dict. Every new snapshot-producing site reinvents a little wire spelling, which
is the strongest evidence that the capability is missing rather than misplaced.

The question is not "how does core get camelCase" but "whose job is it to render
a wire representation".

## Decision Drivers

- ARCH-12-003 (core MUST NOT carry `alias_generator=to_camel`) and SDO-03-003
  (no flat-field shims) are both MUST-level and both currently violated.
- CLP-07-001 requires payload snapshots to be valid, receiver-reconstitutable
  wire JSON; ADR-0017's two-branch hierarchy already assigns wire shape to the
  `as_*` branch, which has correct `from_core()` projections.
- ARCH-01-001 forbids `core/` importing `wire/`; ARCH-01-004 says such
  violations are remediated via driven ports rather than by relaxing the rule.
- Piecemeal remediation of this area has repeatedly produced issue propagation
  (#1991 → #2232 → #2260 → #2268). A partial fix that leaves some of the eight
  classes aliased keeps the ratchet alive and keeps the asymmetry documented in
  `CaseParticipant._reject_wire_spelled_keys` true.
- The projection capability is reusable: emitters, sync fan-out, and AS2 HTTP
  responses all need core → wire rendering.
- Removing the shim is unsafe without a guard. `extra="ignore"` is the Pydantic
  default, so deleting `_migrate_flat_fields` would make a flat `rm_state` key
  *silently dropped*, defaulting `rm.state` to `RM.START` — precisely the #2232
  defect class, and an ARCH-15-001/002 violation (silent `None` and fake
  `SUCCESS` are the same bug).

## Considered Options

- **Amend ARCH-12-003** to permit `alias_generator` on core types that have wire
  counterparts.
- **Let core import the wire layer** for this one purpose (rendering what was
  received on the wire).
- **Driven port for core → wire rendering** (`WireRenderPort`), implemented by an
  AS2 adapter that owns `from_core()` + `by_alias` dumping; remove
  `alias_generator` from all eight classes and delete the flat-field shim behind
  a rejecting guard.
- **Narrow fix**: leave the port out, keep `alias_generator` on
  `ParticipantStatus` only, and remediate the other seven.

## Decision Outcome

Chosen option: **"Driven port for core → wire rendering"**, applied to all eight
classes in one change rather than incrementally.

Concretely:

1. **New driven port** `vultron/core/ports/wire_render.py` declaring a
   `typing.Protocol` (matching `SyncActivityPort` / `ActivityEmitter` style):

   ```python
   @runtime_checkable
   class WireRenderPort(Protocol):
       def render(self, obj: Any) -> dict[str, Any]: ...
   ```

   `render()` returns wire-shaped JSON (camelCase, `exclude_none=True`) for a
   core domain object. It raises `VultronValidationError` when no wire
   counterpart exists, rather than falling back to a core-shaped dump — a
   silently core-shaped snapshot is the failure mode this ADR exists to remove
   (ARCH-15-002).

2. **AS2 adapter** `vultron/adapters/driven/wire_render/as2.py` implements it by
   looking the core `type_` up in the wire vocabulary, calling the wire class's
   `from_core()`, and dumping with `by_alias=True, exclude_none=True`. All
   knowledge of camelCase spelling, flat `emConsentState`, and the AS2 `@context`
   lives here.

3. **Port injection** follows the existing pattern: a `wire_render_port`
   parameter on `BTBridge.__init__`, published to the blackboard under
   `wire_render_port`, and passed through `execute_with_setup()`. Use-case
   helpers that build snapshots take it as an argument.

4. **`ledger_snapshots.py` is reduced to the port call.** `obj_to_inline_dict`
   and the `consent` → `emConsentState` hand-patch are deleted; the synthesizers
   that remain (case-proposal bootstrap, where no received activity exists to
   capture verbatim) build a core object and hand it to the port.
   `_inline_snapshot_reference_value` renders `dl.read()` results through the
   same port, which fixes CLP-07-006 inlining for every type rather than only
   for types that happen to be aliased.

5. **`alias_generator` is removed from all eight classes**, and
   `_migrate_flat_fields` is deleted. Each de-aliased class gains a rejecting
   `model_validator(mode="before")` built on the existing
   `reject_wire_spelled_keys` mechanism in
   `vultron/core/models/_wire_spelling.py`, extended to cover the flat wire field
   names (`rm_state`/`rmState`, `vfd_state`/`vfdState`,
   `em_consent_state`/`emConsentState`) so that a wire-shaped payload raises
   instead of being silently dropped. `_to_core_status` in
   `behaviors/status/nodes/dimension_filter.py` is converted from
   dump-and-revalidate to the `to_core()` boundary projection at the same time,
   since the guard would otherwise make it raise (ARCH-20-007).

6. **Actor HTTP responses are routed through wire projections.** `GET /actors/{id}`
   and its sibling routes render via the `as_*` actor classes instead of dumping
   a core actor with `by_alias=True`. The vestigial `CoreActor.to_json()` (no
   callers) is removed.

7. **The ratchet is retired.** The `xfail` on
   `test_no_core_object_has_to_camel_alias_generator` becomes a plain passing
   assertion, and #1991 is closed. The known-deviation paragraph in
   `CaseParticipant._reject_wire_spelled_keys`'s docstring is rewritten, because
   ARCH-12-003 then does hold throughout that subtree.

**Persisted rows are unaffected.** `Record.from_obj` calls
`obj.model_dump(mode="json", serialize_as_any=True)` with no `by_alias`, so rows
are already snake_case. Removing `alias_generator` does not change the persisted
key shape, and no persistence-schema migration is implied. The reject-guards
raise `VultronValidationError`, which `DataLayer._from_row` already catches and
routes into `_wire_object_from_row` → `_project_wire_row_to_core`
(ADR-0062, #2232), so a wire-shaped legacy row still reads back correctly.

### Consequences

- Good, because ARCH-12-003 and SDO-03-003 both become true, verifiable, and
  test-enforced rather than ratcheted.
- Good, because wire spelling has exactly one home. The
  `consent` → `emConsentState` hand-patch — a partial `from_core()` living in
  core — disappears instead of drifting further.
- Good, because CLP-07-006 inline snapshots become correct for all nested types,
  not just the aliased ones; today a non-aliased nested object is inlined in
  core shape and a receiver cannot reconstitute it.
- Good, because the port is reusable by emitters and sync fan-out, which need
  the same rendering.
- Bad, because it is a wide change: eight model classes, a new port and adapter,
  BT plumbing, ledger snapshot construction, and the actor HTTP routes. It
  touches the ledger write path, which is hash-chained.
- Bad, because every BT execution path that builds a payload snapshot must now
  have the port injected. A path that forgets it fails loudly (by design) rather
  than degrading to a core-shaped snapshot, so the cost surfaces as test
  failures during implementation rather than as silent wire-shape drift.
- Neutral, because the canonical commit stays exactly where it is. CLP-09-002
  forbids bare canonical commits and CLP-10-005..008 constrain `execute()`, so
  only entry *rendering* moves behind the port; the role-gated commit remains in
  `CommitCaseLedgerEntryNode`.

## Validation

- `test_no_core_object_has_to_camel_alias_generator` passes without `xfail`.
- A new architecture test asserts no `CoreObject` subclass declares an
  `alias_generator`, and that no core module dumps with `by_alias=True`.
- A round-trip test asserts that for each core type with a wire counterpart,
  `WireRenderPort.render(core_obj)` equals
  `as_X.from_core(core_obj).model_dump(by_alias=True, exclude_none=True)`, and
  that the result revalidates through `as_X.model_validate` (CLP-07-001
  reconstitutability).
- A test asserts `ParticipantStatus.model_validate({"rm_state": "RECEIVED"})`
  raises `VultronValidationError` rather than silently yielding `RM.START`.
- Existing CM-18-006 assertions continue to hold: the wire projection, not the
  core alias, is what produces `emConsentState`/`embargoAdherence`.

## Pros and Cons of the Options

### Amend ARCH-12-003 to permit `alias_generator` on core types

- Good, because it is the smallest possible change.
- Bad, because it legitimises the shape duality that produced #2232: the same
  `type_` accepting two key spellings means whichever class reads a row decides
  what the data means.
- Bad, because it does not fix the `consent` → `emConsentState` hand-patch, which
  exists precisely because core aliasing *cannot* produce the wire shape. The
  amendment would sanction a mechanism that is already insufficient.

### Let core import the wire layer for this purpose

- Good, because it is direct and needs no injection plumbing; the argument that
  "core is reflecting what was received on the wire" is genuinely reasonable.
- Neutral, because ARCH-01-001 exists to keep domain logic replaceable, and
  rendering a snapshot is arguably not domain logic.
- Bad, because ARCH-01-004 already establishes driven ports as the remediation
  for exactly this situation, and a one-off exemption is not testable — an
  allow-listed import becomes an unbounded one.
- Bad, because it forgoes reuse: emitters and the AS2 HTTP routes need the same
  rendering, and a port serves all three.

### Narrow fix: `ParticipantStatus` keeps its alias; remediate the other seven

- Good, because it is much smaller and lower-risk in the ledger write path.
- Bad, because it leaves the ratchet in place, so #1991 cannot close and the
  documented asymmetry in `CaseParticipant` stays true.
- Bad, because the class that keeps the alias is the one where the alias is
  *demonstrably broken* (the hand-patch), so the narrow fix retains the worst
  instance.
- Bad, on stated project experience: incremental remediation of this area
  generated #1991 → #2232 → #2260 → #2268, each fix creating the conditions for
  the next report.

## More Information

- Source concern: #2260. Closes the long-standing violation tracked in #1991.
- Related: #2232 (wire-shaped rows on the DataLayer read path, fixed by
  ADR-0062), #2268 (the thirteen remaining wire-shadowing types on the write
  path, not in scope here).
- ADR-0017 establishes the two-branch hierarchy this decision leans on;
  ADR-0036 establishes the dimension objects whose flat predecessors the shim
  keeps alive; ADR-0062 establishes the persistence-boundary normalisation that
  makes the reject-guards recoverable.
- No data migration is required: this code has no production deployment and no
  stale rows exist.

Generated spec requirements: `architecture.yaml` ARCH-20-001 through
ARCH-20-007; `case-ledger-processing.yaml` CLP-07-009 and CLP-07-010;
`status-dimension-objects.yaml` SDO-03-005.
