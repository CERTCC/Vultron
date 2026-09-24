---
title: Domain Object Validation — Strict vs. Loose Boundaries
status: active
description: >
  Where in the pipeline domain objects transition from "loose" (possibly
  None/unresolved fields) to "strict" (all required fields guaranteed),
  and how helpers must fail fast when strict guarantees are violated.
related_specs:
  - specs/architecture.yaml (ARCH-10-001, ARCH-15-001 through ARCH-15-004,
    ARCH-21-001 through ARCH-21-005)
  - specs/case-management.yaml (CM-23-012, CM-27-001 through CM-27-003)
  - specs/participant-role-management.yaml (PRM-03-003)
  - specs/error-handling.yaml (EH-05-002, EH-07-001 through EH-07-003)
  - specs/code-style.yaml (CS-23-001)
  - specs/behavior-tree-node-design.yaml (BTND-10-001 through BTND-10-006)
  - specs/received-status-handling.yaml (RSH-05-001, RSH-05-002, RSH-05-020, RSH-05-022)
related_notes:
  - notes/architecture-hexagonal.md
  - notes/bt-integration.md
  - notes/wire-core-boundary.md
  - notes/bt-pitfalls.md
  - notes/case-state-model.md
---

# Domain Object Validation — Strict vs. Loose Boundaries

## The Strict/Loose Distinction

Domain objects in Vultron move through two zones:

- **Loose zone**: Objects freshly deserialized from the wire or DataLayer.
  Optional fields may be `None`, IDs may be unresolved strings or inline
  objects, and required-field invariants have not yet been checked in
  context.
- **Strict zone**: Objects that have been validated and are ready for
  domain logic. All fields required for the current operation are
  non-None and of the expected type.

The boundary is not a single conversion step — it is a series of
**fail-fast checkpoints** at the entry to each domain operation.
Pydantic model construction (ARCH-10-001) enforces structural
invariants. Runtime helpers enforce relational invariants (e.g., "this
case has a Case Manager participant with a resolvable actor ID").

---

## Conversion Points

Objects transition from loose to strict at:

1. **Use-case `execute()` entry** — required inputs (case ID, actor ID,
   activity) must be non-None before any DataLayer mutation.
2. **BT node `update()` entry** — blackboard keys expected to be present
   must be verified; missing keys return `Status.FAILURE` (not
   `Status.SUCCESS`) so the BT sequence propagates failure correctly.
3. **Helper function boundaries** — helpers that require a non-None result
   from a field access must check and raise immediately. Helpers whose
   callers may legitimately pass `None` must remain lenient.

---

## Pattern: Fail Fast at the Conversion Point

When a helper or node requires a non-None value, check it explicitly
and raise or return `FAILURE` immediately:

```python
# In a helper that requires a valid ID
case_id = _as_id(case)
if case_id is None:
    raise VultronValidationError(
        f"Cannot process case with no resolvable id (got {case!r})"
    )

# In a BT node update() that requires a blackboard key
case_obj = self._read_case_obj()
if case_obj is None:
    self.feedback_message = f"{self.name}: 'create_case_obj' not on blackboard"
    return Status.FAILURE
```

**Never return `Status.SUCCESS` when a required input is absent.** A
missing required value means the subtree cannot produce its intended
effect; returning `SUCCESS` misleads the BT sequence and silently drops
protocol behavior (ledger entries not written, broadcasts not sent,
routing never attempted).

---

## Pattern: Lenient Helpers Remain Lenient

`_as_id()` is intentionally lenient — it returns `None` when the input
is `None` because many callers legitimately probe optional fields (e.g.,
`case.active_embargo` is `None` when no embargo is active). Do **not**
make `_as_id()` raise.

The strict guarantee lives in the **caller**, not in the helper:

```python
# Lenient use — None is a valid outcome
active_embargo_id = _as_id(case.active_embargo)  # may be None

# Strict use — None means something went wrong
manager_id = _as_id(participant.attributed_to)
if manager_id is None:
    raise VultronValidationError("CASE_MANAGER participant has no attributed_to")
```

---

## Canonical Helper Locations

Layer-neutral utilities with no dependencies above `models/` belong in
`vultron/core/models/_helpers.py` — the bottom of the hexagonal stack,
safely importable by **all** layers (`behaviors/`, `use_cases/`, `services/`,
`adapters/`). Examples: `_as_id()`, `_report_phase_status_id()`.

Higher-level helpers that depend on ports, state machines, or use-case
logic belong in `vultron/core/use_cases/_helpers.py`. Examples:
`_idempotent_create`, `update_participant_rm_state`, `add_activity_to_outbox`.

Duplicate copies in other modules MUST NOT be maintained — import from the
canonical location instead.
`behaviors/status/nodes/broadcast.py` was deleted in #1378 after its only
content (`_find_case_manager_id`) was consolidated into `_resolve_case_manager_id`.

### Exception: cross-cutting guards cannot live in `_helpers.py`

`vultron/core/models/_helpers.py` cannot import from `vultron.core.states` —
that is a circular import through `states/__init__.py`. A guard that knows about
`rm` eventually wants `RM`, so a cross-cutting shape guard could not be
colocated with `_as_id()` and friends.

**Retired (#2940).** The guard this exception was written for —
`reject_wire_spelled_keys` in `vultron/core/models/_wire_spelling.py`, used by
`CaseParticipant._reject_wire_spelled_keys` — **is deleted**, and with it the
module. `CoreObject` now sets `extra="forbid"` (ARCH-12-003), which subsumes it:
an unknown key raises from Pydantic itself, needs no per-class registration, and
covers every core type rather than the one that opted in. SDO-03-005 makes this
binding — the guarantee MUST be `extra="forbid"`, and a per-class
`model_validator(mode="before")` reject-guard for those keys "MUST NOT be added
or retained for this purpose". Do not reintroduce one; a grep ratchet in
`test/architecture/test_core_extra_forbid.py` enforces that.

The circular-import trap the exception documented is still real and still bites,
so keep it in mind for any *new* cross-cutting helper: `states/rm.py`'s own
imports look clean (logging, enum, transitions, `states.common`), so inspecting
the target module tells you nothing. The cycle runs through the package
`__init__.py` — `models/base.py` imports `_helpers`, which triggers
`states/__init__.py`, which pulls `states/cs.py` → `states/common.py` → back into
`models/base.py` while it is still partially initialised. The error looks like a
missing symbol in `models.base`, not a cycle.

### Type-specific canonical readers live with their type

A helper that reads one dimension of one model type (e.g. `participant_status_rm_state`)
belongs in the same module as that type (`vultron/core/models/participant_status.py`),
not in `_helpers.py`. Two reasons:

1. It cannot go to `_helpers.py` if it needs a state enum (see above).
2. Colocating the canonical reader with the type keeps the authorship contract
   clear: the module that defines a type owns its read semantics.

The distinction from a cross-cutting shape guard: a shape guard has to know about
the core/wire boundary across multiple types, whereas a canonical reader is
type-specific. Since #2940 the cross-cutting half is not a helper at all — it is
`extra="forbid"` on `CoreObject` — so the only routing decision left is
type-specific → the type's own module.

BT-node-level wrappers that combine multiple readers (e.g. `read_rm_states()`)
live in `vultron/core/behaviors/helpers.py`, which has no circular-import
restriction (it is below use-cases, above models, and can import from either).

---

## Shape Guards: One Canonical Reader per Dimension (#2232)

`ParticipantStatus` exists in two incompatible shapes: core nests
`rm: RmDimension` / `vf: VfDimension` / `d: DDimension` (SDO-03-002, ADR-0036, ADR-0075), while the wire
projection carries flat `rm_state` / `vf_state` / `d_state`. Reading a dimension off the
wrong shape yields `None` — which every reader then quietly substituted an
initial state for, resetting the participant's ladder (#2264).

**Read a dimension only through its canonical reader.** All live in
`vultron/core/models/participant_status.py`:

| Reader | Returns | Raises |
|---|---|---|
| `participant_status_rm_state(status)` | the `RM` state | `VultronValidationError` on a non-core shape |
| `participant_status_vf_state(status)` | the `CS_vf` state or `None` | `VultronValidationError` on a non-core shape |
| `participant_status_d_state(status)` | the `CS_d` state or `None` | `VultronValidationError` on a non-core shape |

```python
# Wrong — a wire-shaped status degrades to the initial state, silently.
rm_dim = getattr(status, "rm", None)
state = getattr(rm_dim, "state", None)
if not isinstance(state, RM):
    state = RM.START

# Right — absence and shape mismatch are different outcomes.
state = participant_status_rm_state(status)
```

This is the strict/loose rule applied to *shape*: an **empty** status list is a
legitimate absence and callers must handle it (check `participant_statuses`
before calling); a status that exists but exposes no usable dimension is a shape
mismatch and must raise (ARCH-15-001, ARCH-15-002).

**Where a raise is wrong.** At a wire→core ingress boundary, a wire-shaped
status is *legitimate inbound data*, not a corrupt row. Those sites must
**project** before reading — `as_ParticipantStatus.to_core()`, or
`_project_to_core_participant()` in
`vultron/core/use_cases/received/case/_helpers.py` — rather than let the reader
raise. Making the reader strict without projecting at ingress first aborted the
entire received-case behavior tree on every inbound `Announce`, which is how the
first fix for #2232 regressed.

The mirror-image concern is a core type validated against a wire-spelled
payload. Pydantic v2 ignores unknown keys by default, so every snake-only key
was dropped in silence. Since #2940 that is handled by `extra="forbid"` on
`CoreObject` (ARCH-12-003) rather than by the per-class
`reject_wire_spelled_keys()` guard, which is deleted. Note the narrower scope of
what `forbid` actually rejects: *unknown* keys. A flat `rm_state`/`rmState` on
`ParticipantStatus` or `CaseStatus` is still accepted, because those spellings
are declared `AliasChoices` and are interpreted rather than dropped — removing
them is #2288/#2289. See [notes/wire-core-boundary.md](wire-core-boundary.md).

---

## Post-Construction Mutation: Three Doors, One Lock (#2261)

Pydantic v2 validates a model at **construction**. Nothing else. The same value
the constructor rejects is silently accepted through two other doors:

```python
case = VulnerabilityCase(case_participants=[wire_obj])  # ValidationError
case.case_participants = [wire_obj]                     # accepted
case.case_participants.append(wire_obj)                 # accepted
```

Combine that with the shape duality above and you get the #2232 / #2264 failure:
a wire-shaped object in a core-typed field does not raise when read — it reads as
*absent*, so the reader substitutes an initial state and the participant's ladder
silently resets.

**The two remedies are different mechanisms, because they close different
doors.** `validate_assignment=True` closes the assignment door. It does
*nothing* for `append` — an in-place list mutation is not an attribute
assignment, so Pydantic never observes it. That door is closed by prohibition
plus canonical mutators plus an architecture ratchet (CM-27-001, PRM-03-003),
the same way PRM-03-001 closed it for `case_roles`. The established canonical
mutators are `add_case_status()` (on `VulnerabilityCase`, CM-27-003) and
`add_participant_status()` (on `CaseParticipant`, PRM-03-003), alongside the
existing `add_participant()` / `remove_participant()` for `case_participants`.

### Where `validate_assignment` goes — and where it must not

| Layer | `validate_assignment` | Why |
|---|---|---|
| Core models (`vultron/core/models/`) | **on** (ARCH-21-001) | Core fields carry a shape guarantee that readers depend on |
| `VultronBase` | **never** (ARCH-21-002) | Shared base of both branches; `as_Base` inherits it (ARCH-12-001/002) |
| Wire (`vultron/wire/`) | **never** (ARCH-21-003) | Inbound data is legitimately loose; strictness belongs at the projection |

Setting the flag on `VultronBase` is the one-line fix that looks right and is
not. It contradicts ARCH-12-002 and, when measured, produced the largest blast
radius of any variant (747 failed, 423 errors).

### Pitfall: never assign to `self` in a `mode="after"` validator

This is the trap that makes the whole change non-trivial, and it is invisible
from reading the model:

```python
# Wrong — with validate_assignment on, this recurses until the stack is gone.
@model_validator(mode="after")
def _set_role(self) -> FinderParticipant:
    self.case_roles = []          # assignment re-runs this validator...
    self.add_role(CVDRole.FINDER)
    return self

# Right — derive before validation, so the derived value is itself validated.
@model_validator(mode="before")
@classmethod
def _set_role(cls, data: Any) -> Any:
    ...
```

`validate_assignment` re-runs **every** `mode="after"` validator on each
assignment, so a validator that writes to `self` re-enters itself. A guarded one
(`if self.name is None: self.name = ...`) terminates at depth 2; an unguarded one
never terminates. Enabling the flag before this rule holds aborts 400+ tests with
`RecursionError` **and nothing else** — the recursion masks every real type
failure, so the actual blast radius cannot be measured until the validators are
fixed. ARCH-21-004 makes this a MUST NOT for `vultron/core/`.

Writing the field through `self.__dict__["field"]` was considered and rejected:
it stops the recursion but leaves the derived value unvalidated, trading one
silent hole for a smaller one.

Wire-layer validators are **exempt by design** — the wire branch never enables
the flag, so they cannot re-enter. Twelve of them still assign to `self`. If the
wire branch ever gains `validate_assignment`, this trap returns.

### Cost

Scalar attribute assignment measured **475 ns → 1464 ns** (3.1×, ~1 µs
absolute) — immaterial for BT tick loops. Collection fields are O(N) per
assignment: assigning `case_participants` re-validates all N items. Step 2
(issue #2294, AC-6) benchmarked `list[FakeParticipant]` reassignment and found
**3.8× overhead at N=100 (~3 µs absolute)** — O(N) confirmed, within the
acceptable range.

See ADR-0064 for the decision and the three-step rollout, and
`test/architecture/test_validate_assignment_ratchet.py` for the enumerated
backlogs that track it.

---

## Routing Failures vs. Validation Failures

Two distinct error types are used for fail-fast signals:

- **`VultronValidationError`** (`vultron/errors.py`) — a domain object
  or request fails a required invariant (missing field, wrong type).
- **`UnroutableActivityError`** (`vultron/errors.py`) — an inbound
  activity cannot be routed to a case because no case ID could be
  extracted from the event. This is a routing failure, not a data
  validation failure. The dispatcher caller MUST handle it explicitly
  rather than silently dropping the activity.

```python
# Dispatcher site: raise, don't return None
if case_id is None:
    raise UnroutableActivityError(
        activity_id=event.id_,
        reason="No case_id attribute found on event",
    )
```

---

## Rejecting as a Unit Does Not License Reporting One Reason (#2112)

**Atomicity and diagnostic completeness are independent properties.** A
validation boundary that refuses its whole input MUST still report every
violation it can recognise in that input (EH-07-001, BTND-10-002). The
inference "we reject atomically, so the first violation is enough" is wrong
and was written into the code twice before ADR-0086 removed it — once in
`ValidateTriggerTransitionsNode._validate_entailments`, once in
`composite_state_violations()`' ordering rationale.

The reason it is wrong: because the rejection *is* atomic, nothing partial was
accepted, so a caller told one reason at a time gains nothing from the round
trip. It fixes one dimension, resubmits, and is told about the next. Fail-fast
is the right disposition for a *write*; it is the wrong disposition for a
*diagnostic*.

### The emit/receive asymmetry is Postel's maxim, not an inconsistency

The two `ParticipantStatus` validation paths do deliberately opposite things,
and reading one will mislead you about the other:

| | Trigger / emit path | Receive path |
|---|---|---|
| Entry point | `ValidateTriggerTransitionsNode` | `FilterParticipantStatusDimensionsNode` |
| Disposition | Fail-closed: any violation refuses the whole write | Per-dimension partial accept: refused dimensions carry the current value forward, others land |
| Normative source | BTND-10-001, ADR-0086 | ADR-0061, RSH-05-001, RSH-05-002 |
| Postel's half | Conservative in what you send | Liberal in what you accept |

Both halves come from the liberal-accept epic (ISSUE-2229). Do **not** "fix"
one to match the other. If you think one is wrong, the question is which half
of the maxim applies at that boundary, not which path is inconsistent.

**The receive path stays liberal — this question is settled (CONCERN-3040).**
The arguments for all-or-nothing were examined and rejected on two grounds:

1. *RM is self-declaratory* (ADR-0084): the CASE_MANAGER has no independent
   knowledge of a participant's RM state. If a sender asserts `rm=VALID` while
   the ledger records `ACCEPTED`, the ledger is merely stale — the participant
   knows their own state. The CASE_MANAGER cannot correct a self-report.

2. *PXA dimensions are external observational facts, not self-declared process
   state.* A threat sentinel may correctly observe `exploit=public` while
   carrying a stale RM value. Refusing the whole message means the embargo
   continues past the point of public exploit code. That is a protocol safety
   failure.

Impossible dimension combinations (RM↔VF, RM↔D, VF↔D) are already refused
outright by the cross-machine entailment check (RSH-05-020); partial-accept
does not let them through.

Both gaps are now closed (ISSUE-3199):

- *Sender-feedback*: a wholly-refused receive BT now raises
  `VultronStatusAssertionRefusedError`, which the inbox `DispatchNode` catches
  and writes as a `rejected` `InboxOutcome`.  Senders can distinguish
  partial-accept (`"processed"`) from total refusal (`"rejected"`).
- *Emit-side object-level validation*: `ParticipantStatus` carries optional
  `previous_rm_state` / `force_rm_state` constructor fields; when
  `previous_rm_state` is supplied the model's `mode="after"` validator refuses
  backward RM steps at construction time, with `force_rm_state=True` as the
  sanctioned override (same semantics as
  `CreateParticipantStatusNode.force_rm_state`).  `CreateParticipantStatusNode`
  now passes `previous_rm_state=context.current_rm` (when not force-closing) to
  get construction-time double-checking on top of the existing BT validation.

This closes ISSUE-2255 (sender-feedback diagnostics).

### Root vs. derived violations

Reporting everything unranked trades one failure for its mirror image: a wall
of errors where one fix clears most of them. Classify by dimension overlap
(EH-07-002):

- A rule reading **one** dimension (a transition check, a role gate) is always
  **root**.
- A rule reading **more than one** dimension (a cross-machine entailment, the
  compound CS transition) is **derived** when any dimension it reads already
  carries a single-dimension violation, and **root** otherwise.

The root multi-dimension case is the informative one: every dimension moved
legally on its own and the *combination* is impossible. Use dimension overlap
rather than a rule-to-rule dependency graph — a newly added rule is then
classified correctly by construction, so the labelling cannot go stale.

### Compose the rule set, don't just share the predicates

Two nodes validating the same write must call **one** evaluator that returns
every violation, not the same individual predicates (BTND-10-002). Sharing
predicates still lets each caller pick a different subset — which is exactly
what happened: only the guard evaluated the cross-machine entailments, only
the write node evaluated the compound CS transition, and both duplicated the
VF/D/PXA transition checks and role gates with byte-identical message text
(an ARCH-15-004 violation). `composite_state_violations()` is the existing
instance of the right shape; see also
[bt-integration.md](bt-integration.md) and the ISSUE-2906 lesson that
composing the set — not sharing its members — is what makes divergence
impossible rather than merely fixed.

**The write node keeps its own checks** (BTND-10-003). Do not reduce it to a
delegate that assumes the guard ran: `CreateParticipantStatusNode` is reached
from `develop_fix.py`, `deploy_fix.py`, `close_case_effect.py` and two sites
in `leave.py` without passing through the guard, and for those paths its
checks are the only validation. This does not double-report on the trigger
path — the guard fails first and the enclosing `Sequence` aborts before the
write node ticks.

The composed evaluator is `participant_transition_violations()` in
`vultron/core/states/participant_transitions.py`; both nodes reach it through
`validate_participant_status_write()` in
`behaviors/case/nodes/participant/common.py`, which also owns the
`feedback_message` rendering and the `result_out["error"]` write. The
`test/architecture/test_participant_status_validation.py` ratchet fails any node
that names an individual predicate instead, and discovers the population of
validators structurally rather than from a list — which is how it found the two
writers below. Its `_DECLARED_EXCLUSIONS` records the sites that legitimately sit
outside the evaluator, each with a reason.

### There were seven writers, and four were invisible (#3111, ADR-0089)

CONCERN-3111 recorded two writers outside the evaluator. Scoping it found seven
that append a ladder rung or write the marker record. The four the ratchet could
not see are the important part:

| Writer | Validates | Ratchet sees it? |
|---|---|---|
| `CreateParticipantStatusNode` | the whole rule set | yes |
| `CaseParticipant.append_rm_state()` | RM adjacency only | declared |
| `_ReportPhaseRMTransition._write_latch()` | RM adjacency only | declared |
| `as_CaseParticipant.append_rm_state()` | RM adjacency only | **no** — wire twin, see below |
| `common.py::_get_or_create_accepted_status()` | **nothing** | **no** |
| `owner.py::_build_owner_initial_status()` | **nothing** | **no** |
| `case_proposal_received_tree.py::_build_bootstrap_statuses()` | **nothing** | **no** |

Count the writers, not the `ParticipantStatus(...)` calls: the seven above
exclude the constructor-seeding validators
(`CaseParticipant._init_participant_status_if_empty`, and
`_set_accepted_status` on `ReporterParticipant` and `FinderReporterParticipant`
— see the seeding-validator pitfall below), the demo seeder in
`demo/helpers/seeding.py`, and the wire→core extractor in
`wire/as2/extractor/_builders.py`. Those construct a status but do not advance a
participant's ladder.

**The detector's gate was the hole.**
`test_no_undeclared_participant_status_validator` flagged a module only when it
*both* named a member predicate *and* constructed a dimension object. A writer
that validates nothing names no predicate, so it was never flagged — the
detector caught partial validators and missed wholly-unvalidated ones. Under
ADR-0089 the gate is construction alone: **any** module that builds a participant
dimension is in the population. Validating less no longer buys invisibility.

**The wire twin escapes both gates, and needs its own trigger.**
`as_CaseParticipant.append_rm_state()` is in neither `_VALIDATING_NODE_MODULES`
nor `_DECLARED_EXCLUSIONS` — the ratchet has no reference to `vultron/wire/` at
all. It names `is_valid_rm_transition`, so the *old* gate's predicate half
matches, but it builds `as_ParticipantStatus` from flat fields (`rm_state=`)
rather than a dimension object, so the construction half never fires. Widening
the gate to construction alone does not reach it either, for the same reason. The
wire projection's construction shape has to be added to the trigger set
explicitly, or "every writer is visible" stays false for the wire layer.

The general lesson: when a structural ratchet keys on evidence of *doing the
right thing badly*, the code that does nothing at all is outside its reach. Key
on the write, not on the check.

### `ParticipantStatus` had two jobs; the earlier one moves out

Most `ParticipantStatus` records are rungs on a participant's ladder, in
`CaseParticipant.participant_statuses`. `_ReportPhaseRMTransition` wrote a
*standalone* record under a deterministic id from `(actor, report, rm_state)`,
and callers asked "does that id exist?" to mean "has this step happened?" It
existed because RM state starts at report receipt and the case may not exist
yet — or ever: a receiver may declare a bare report `INVALID` or `CLOSED` and
never propose a case.

The two jobs were already entangled, which is why "separate lifecycle" was the
wrong reading:

- `_build_owner_initial_status()` reused the marker's **id** for the
  participant's first ladder rung, so marker and rung became one record.
- `_get_or_create_accepted_status()` assigned directly to the stored record
  (`existing.cvd_role = …`, `existing.consent = …`, `existing.context = …`) and
  saved it — the post-construction mutation door documented above — and created
  the record outright when absent.

ADR-0089 resolves it by relocation rather than by adding a rule: the pre-case RM
state becomes a field on `VultronReportCaseLink`, which ADR-0041 already created
for exactly that window, and the marker plus `_report_phase_status_id()`,
`report_phase_context()` and `_current_report_phase_rm_state()` are deleted.
`ParticipantStatus` is then ladder-only with one writer, and the writer always
has a case — so no fourth ADR-0087 disposition is needed.

**Do not reach for the writer from inside another node (BTND-10-004).** Five
sites used to build `CreateParticipantStatusNode` inside their own `update()`
and call `node.update()` directly — six such calls, because `develop_fix.py`
builds it once in a shared `_make_status_node()` helper and ticks it from two
places. That skips `setup()` and the tick cycle, and two of the sites
(`deploy_fix.py`, and `develop_fix.py` on both of its calls) wrapped it in
`try/except`, which is the swallowing shape
[bt-pitfalls.md](bt-pitfalls.md) § "Always Check
`BTBridge.execute_with_setup` Return Value" warns about. The node is always a
real tree child. The architecture ratchet
`test/architecture/test_participant_status_validation.py` (AC-9) fails any
`update()` body that re-introduces this construction.

**One mechanism per input (BTND-10-005).** `case_id` is always the blackboard
port (`CaseIdInputPortMixin`) — the only mechanism that works in received trees,
where the case is found at tick time by dereferencing the report; trees that
know it at build time seed `/case_id` through
`BTBridge.execute_with_setup(**context_data)`. The *subject* actor is always an
explicit argument, never a fallback to the blackboard `actor_id`, because the
blackboard actor is the *executing* actor and conflating the two was #2300.
`CreateParticipantStatusNode.__init__` deliberately has no `case_id` parameter;
the ratchet (AC-9) fails any constructor signature that adds one.

### The entailments cannot fire on an RM-only advance (measured)

CONCERN-3111 declined to act partly on an "unmeasured blast radius": routing an
RM-only write through the whole rule set makes the cross-machine entailments
read the *effective* `vf`/`d` for the first time. Enumerating
`composite_state_violations()` over every `(RM, vf, d)` triple settles it, and
the answer is zero on legal data.

Be precise about which rule carries the RM guard. The two **RM-coupled**
entailments — RM↔VF and RM↔D (CSB-18-001) — fire only when the F bit or D bit is
set **and** RM is not in `{ACCEPTED, DEFERRED, CLOSED}`. The **VF↔D** entailment
(CSB-17-001) is RM-independent: `violation_vf_d_entailment()` takes only
`(vf, d)`, and `composite_state_violations()` calls it unconditionally. So "RM is
`ACCEPTED`" buys immunity from two of the three rules, not from all three.

For the RM-coupled pair, reachability closes it: `VALID` is reachable only from
`RECEIVED` or `INVALID`; `INVALID` only from `RECEIVED`; `RECEIVED` only from
`START`. Holding a fix-ready `vf` requires having passed `ACCEPTED`, and RM never
walks back to `RECEIVED`. So no legal state presents a fix-ready or deployed
value at the targets where those two rules could bite.

What remains refusable — at **any** RM state, since this is the RM-independent
rule — is `(vf, D)` and `(Vf, D)`: deployed before ready. Those states are
already corrupt; refusing them is a fix, and repairing them is the receive path's
job (RSH-05-020). Note the shape of this argument: the blast radius was bounded
by *reachability*, not by running the suite. Prefer that where the rule set is a
pure function over enums — but scope the bound to the rules that actually read
the dimension you are bounding on.

The import cycle CONCERN-3111 predicted is real —
`models/case_participant.py` → `states/participant_transitions.py` →
`predicates/participants.py` → back — but it is **moot** under ADR-0089, because
the model no longer validates anything. It is also breakable, in two steps: the
`CaseParticipant` import in `predicates/participants.py` is annotation-only and
belongs under the `TYPE_CHECKING` block already present in that file — but that
module has no `from __future__ import annotations`, and its uses are *unquoted*
function annotations, which Python evaluates when the `def` runs. Move the import
and quote those annotations (or add the future import); moving it alone raises
`NameError` at import time.

### Pitfall: an RM-only append resets the vendor and deployer paths

`ParticipantStatus` re-seeds `vf` for a VENDOR and `d` for a DEPLOYER at their
**initial** state when the field is omitted
(`ParticipantStatus._enforce_role_dimension_invariant`). So a status built with
only `rm` does not leave those dimensions alone — it silently rewinds them:

```python
# vendor at vf=VF (fix ready)
participant.append_rm_state(RM.CLOSED, actor, context)
# -> latest status now reads vf=vf (vendor unaware); the fix un-happened
```

`CaseParticipant.append_rm_state()` did exactly this until #3134. Any writer that
appends a `ParticipantStatus` MUST carry the participant's current `vf`/`d`
forward, the way `CreateParticipantStatusNode` does. This is the #2264 rule —
absence and an initial value are different things — and omission is the third
door onto it, alongside assignment and `append`.

Carry a path forward **only while its role is still held.** `cvd_role` on the new
snapshot is recomputed from the participant's current roles, so carrying a
dimension whose role has since been dropped produces a snapshot asserting a path
its own role list denies (ADR-0075).

The wire twin `as_CaseParticipant.append_rm_state()` had the same omission in a
worse shape: `as_ParticipantStatus` has no seeding validator, so omission
**dropped** the dimension rather than rewinding it. Both were fixed together
(#3134) — when a core mutator and its wire counterpart both build a status, fix
both or the rule has a live counter-example one directory over (ARCH-15-004).

The general shape: **a model that auto-seeds a field on construction turns
"omit it" into "reset it"; one that does not turns it into "drop it".** Neither is
"leave it alone." Check every constructor call for a type with `mode="before"`
seeding validators.

ADR-0089 removed both `append_rm_state()` mutators — the core one on
`CaseParticipant` and its wire twin on `as_CaseParticipant` — so the two named
counter-examples no longer exist. But the rule is about *constructor calls*, not
about those methods, and it still binds every `ParticipantStatus(...)` site.
`_init_participant_status_if_empty` (core, seeds `RM.START`) and
`_set_accepted_status` (on `ReporterParticipant` and
`FinderReporterParticipant`, seeds `RM.ACCEPTED`) are still live seeding
validators. `_set_accepted_status` was two byte-identical copies — a
copy-paste duplicate and an ARCH-15-004 / CS-22-001 violation in its own right;
ADR-0089 de-duplicated them into the shared module-level `_seed_accepted_status`
helper that both validators now delegate to.

Test arrange sites that used to call `append_rm_state()` to place a participant
at an RM state now go through the `advance_participant_rm` helper in
`test/support/participant_status.py`, which appends through the public
`add_participant_status()` door (PRM-03-003) and reproduces the same vendor/
deployer carry-forward.

### Pitfall: a forced promotion runs after validation

`CreateParticipantStatusNode._apply_ac1_promotions()` applies SM-09-001's forced
promotions (`pXa→PXa`, `pXA→PXA`, `vP→VP`) **after**
`participant_transition_violations()` has run, and it is the promoted values that
get persisted. So the evaluator does not see everything that lands:
`_EffectiveStates`' docstring says as much. Do not read "one evaluator governs
every `ParticipantStatus` write" as "everything persisted was validated."

That gap was live. A non-VENDOR could assert `vf` (the role gate covered only
`{Vf, VF}`), and any later write with a public-aware `pxa` promoted it to `Vf` —
a value the same actor is refused if it asserts it directly. Fixed by closing the
*first* link: the VF role gate now covers **every** asserted `vf` value, so a
non-VENDOR cannot put anything on the vendor path and the promotion has nothing
ungated to advance (#3135). That also removes a drift between the two dimensions
— `_d_violations` had gated every asserted `d` since #2963, and `vf` had not.

The promotion itself is still not role-gated. It is unreachable rather than
guarded, which is a weaker guarantee: **if you add another route by which a
participant can acquire a dimension its role does not license, you reopen this.**
The receive path's carry-forward and any new model mutator are the places to
watch.

### Pitfall: composing the set exposed a non-adjacent RM write at the close sites

Giving the write node the *whole* rule set made it validate RM for the first
time, and three call sites surfaced: `close_case_effect.py` and both sites in
`leave.py` stamp a departing actor `RM.CLOSED` regardless of the rung its RM
machine is on. `RM.CLOSED` is reachable by adjacency only from `ACCEPTED`,
`INVALID` or `DEFERRED`, so from an earlier rung this write is non-adjacent —
which the emit-side adjacency rule (BTND-10-001) would otherwise refuse, and
which was invisible while the write node ignored RM. ADR-0086 predicted the
bypass sites would gain trigger-path diagnostics "at no additional cost"; for RM
that is not true.

Those sites carry a `force_rm_state=True` exemption that suppresses **only** the
RM adjacency rule, pinned to that exact list by the ratchet above so it can only
shrink. Do not add users, and do not read the exemption as "closure may write
whatever it likes": every other rule still applies.

**Resolved (CM-23-012, [#3106](https://github.com/CERTCC/Vultron/issues/3106)):**
the override is *sanctioned*, not a standing violation. A `Leave` is the
departing actor's own self-declaratory closure act (ADR-0084), so advancing
*that single actor* to `RM.CLOSED` regardless of rung is legitimate
self-declaration — the RM adjacency rule is a report-handling invariant that a
case-level `Leave` legitimately overrides. The scope is the key constraint: each
site advances exactly one named actor (the leaver, or the CASE_MANAGER closing its
own lifecycle on owner Leave, ADR-0051). Closure **never** force-advances a
non-leaving ("bystander") participant — a participant that never sent `Leave`
has made no closure declaration, so it retains its last RM state when the case
closes around it ("the library closed before every book was returned"). The demo
scenarios' "all participants `RM.CLOSED`" milestone (DEMOMA-07-003) is reached
because every participant closes its own handling through the protocol, not
because closure pushes them there.

### Surfacing a violation list

`VultronValidationError` carries the violations as structured data and renders
the whole set in `__str__` (EH-07-003), following `DemoFailureError`'s shape
(`vultron/errors.py`, DEMOCI-01-003). The HTTP translation adds a `details`
array to the body alongside `message` (EH-05-002), so callers are not forced
to parse a joined string — a fragility #2112 named explicitly, since a change
to internal check order silently alters which error surfaces.

The plumbing already exists: `SvcBTTriggerBase.execute()` re-raises whatever
exception it finds at `result_out["error"]`, so a guard node needs only to be
passed `result_out`. Aggregation stays *within* one node per path, so
BT-13-001's first-failing-leaf contract (`BTBridge.get_failure_reason`) is
unaffected — sibling guard nodes in a `memory=False` `Sequence` still
short-circuit and cannot co-report.

**`details` is not present on every validation rejection**, and that is a
consequence of the previous paragraph rather than a gap. Only the composed
evaluator populates `result_out["error"]` with a violation-carrying exception.
The sibling role guards that run *before* it in
`add_participant_status_trigger_tree` — `CheckNotSoleObserverVfdNode` and
`CheckDeployerRoleNode` — do not, so when one of them fails,
`SvcBTTriggerBase.execute()` falls through to a generic `VultronValidationError`
built from `get_failure_reason(tree)` and the 422 body has no `details` key.
EH-05-002 only mandates `details` for a response reporting more than one
violation, and those guards report one, so this conforms — but do not write a
client that assumes `details` is always there. A visible consequence: because
`CheckDeployerRoleNode` fires first, the evaluator's own DEPLOYER gate never gets
to report on the trigger path, only on the five paths that bypass the guard.

---

## Broad `except Exception` Is a Masking Smell (CONCERN-3295, CS-23-001)

A blanket `except Exception` (or a bare `except:`) around domain logic is,
in this codebase, more likely to be **masking a defect** than handling a
real case. The tell is the absence of a rationale: a genuine compatibility
surface tends to get explained, because the author had a specific input in
mind. Two witnesses established the pattern:

- **#3217** — `vultron/wire/as2/parser.py` wrapped nested inline validation
  in `except Exception: return expanded`. It read as a compatibility shim for
  bare-ID / partial-stub inline objects. Instrumented, it fired **52 times**
  with exactly **one** cause: a wire/core layering fault (ARCH-22-001) that
  flattened every inline actor to a bare `as_Link`. The tolerance was
  concealing a bug, not absorbing legitimate input.
- **#3192** — `_find_case_actor` returned the **first arbitrary `Service`** in
  the store on a failed lookup, so `FindCaseActorNode` reported `SUCCESS` and
  published a case-actor address belonging to a *different case*. Again one
  bug-shaped cause, again undocumented.

### The rule: narrow, delete, or justify

For every `except Exception` outside the sanctioned boundary below, do **one**
of:

1. **Narrow** it to the specific exception type(s) you actually expect
   (`except KeyError`, `except (ValidationError, ValueError)`), so an
   unexpected error surfaces loudly instead of being absorbed.
2. **Delete** it and let the error propagate, if nothing legitimately needs
   catching there.
3. **Justify** it — only at a genuine framework/execution boundary — by
   narrowing to the narrowest covering type *and* adding an inline comment
   stating what it guards and why.

**The one sanctioned broad-catch boundary is a BT node's `update()` method**,
where converting an unexpected error into `Status.FAILURE` is the documented
node contract (BT-HELPER-01, see [bt-pitfalls.md](bt-pitfalls.md)). Note that
even an `update()`-level catch can *defeat* the bridge's `internal_error`
detection (see [bt-integration.md](bt-integration.md)); the `update()`
exemption is about where a broad catch is *permitted*, not a claim that it is
always harmless.

Other genuine boundaries — the `BTBridge` execution boundary
(`behaviors/bridge.py`), py_trees `setup()`/`initialise()` — keep their broad
catch but are enumerated in the enforcing test's `_DECLARED_EXCLUSIONS`
allow-list, one reason per entry, and the list can only shrink.

### When you cannot tell whether a fallback is load-bearing

This applies to any silent-degradation branch — a broad `except`, an
`or <default>`, or a `return None`/arbitrary value on a failed lookup — not
only to broad catches. Do **not** reason about it from the code and the commit
message alone; that is a coin-flip. Use the instrument-and-count method from
issue #3217: log the `(class, keys, error)` reaching the branch, run the
**full** suite, and group the results by cause. A **single** cause usually means the
tolerance is masking a bug (fix the root cause, delete the tolerance); **many**
causes mean it is a genuine compatibility surface (narrow it and document what
it absorbs). The count also reveals the *order* a fix must land in: removing the
tolerance before fixing its causes turns every currently-absorbed case into a
hard failure, so the masked bug must be fixed first (in #3217, wire type
resolution had to be restricted before the `parser.py` fallback could go). This
is one cheap instrumented run and it replaces a coin-flip guess. Any masked
defect found this way is itself a new witness for the pattern.

**Enforcement**: CS-23-001 disallows broad `except Exception` in `vultron/`
outside the `update()` boundary;
`test/architecture/test_no_broad_except_outside_bt_update.py` is the AST
ratchet for `vultron/core/behaviors/`.

---

## Pitfall: `getattr(obj, name, default)` Does Not Catch `ValueError`

Python's three-argument `getattr` suppresses only `AttributeError`. If a
property getter raises `ValueError` — as `VulnerabilityCase.current_status`
does when `case_statuses` has no materialised entries — the default is
**never returned** and the `ValueError` propagates.

The `getattr(case, "current_status", None)` idiom is therefore a latent bug
wherever a property may raise.

**Pattern — safe property access when a property may raise:**

```python
try:
    current_status = case.current_status
except (AttributeError, ValueError):
    current_status = None
```

Use `except (AttributeError, ValueError)` rather than a bare `except` so that
unexpected exception types still surface. Apply this pattern at BT node or
use-case entry points wherever a case property is accessed on an
object that may be only partially initialised (e.g., freshly constructed
from a DataLayer read before all derived fields are available).

Source: ISSUE-1455 — three call sites fixed across BT nodes and use cases.

### Contrast: `NotImplementedError` from a Property Is a Programming Error

`ValueError` and `NotImplementedError` look similar but have opposite
implications at a port boundary:

| Exception | Meaning | Correct response |
|---|---|---|
| `ValueError` | Property is implemented; current data state is invalid | Catch at the calling boundary; treat as absence |
| `NotImplementedError` | Property has no implementation | **Do not catch** — let it propagate as an unambiguous adapter-incomplete signal |

`getattr(obj, "actor_id", None)` suppresses only `AttributeError`. If
`actor_id` is a property that raises `NotImplementedError`, the default
is never returned and the exception propagates — by design. Catching it and
converting it to `VultronValidationError("no receiving actor")` would produce
a misleading diagnosis: callers see a data-problem error when the real issue
is an unimplemented adapter.

**Port contract rule** (from `CasePersistence.actor_id`, CM-01-001): a port
property that callers rely on for routing MUST NOT raise `NotImplementedError`.
Implementations that do are broken adapters, and the propagation of the
exception is the correct signal for catching that during development and testing.

Source: ISSUE-2668 — port contract clarified and regression test added.

## Pitfall: Inside `__init_subclass__`, `model_fields` Reports the *Parent's* Fields

`cls.model_fields` is rebuilt by Pydantic's metaclass *after*
`__init_subclass__` returns. Inside it, the dict holds whatever the **parent**
class had — which is the dangerous part, and worse than the dict being empty:

```python
class _Child(_Parent):                       # _Parent: type_: str | None = None
    type_: Literal["ChildProbe"] = Field(default="ChildProbe", ...)
# inside __init_subclass__:  len(cls.model_fields) == 29
#                            cls.model_fields["type_"].default is None   ← parent's
```

So a presence check (`if "type_" in cls.model_fields`) **succeeds** and hands
back a value that is silently wrong, rather than raising the way an empty dict
would. Measured on #2982, where `WIRE_TYPE_MAP` keys are derived from the
declared `type_` default at registration time: reading `model_fields` there gives
every class its parent's `None` and collapses the whole registry onto the
class-name fallback.

To inspect a class's **own** declarations at subclass-registration time, read the
raw class namespace — `cls.__dict__["type_"]` for a declared default (a
`FieldInfo` when assigned via `Field(...)`, the bare value otherwise) and
`cls.__dict__["__annotations__"]` for annotations. Note the mirror-image trap:
Pydantic *strips* field definitions out of `cls.__dict__` once the class is
built, so after construction only `model_fields` has the answer. Code that must
work in both contexts needs both paths — see
`vultron/wire/as2/vocab/base/registry.py::declared_wire_type`. Otherwise defer
inspection to `model_post_init` or a class-level
`@model_validator(mode="before")`.

Source: ISSUE-2294, sharpened by ISSUE-2982

## Pitfall: `mode="before"` Validators Run in Reverse Definition Order

When a Pydantic v2 model declares multiple `@model_validator(mode="before")`
validators, they execute in **reverse definition order** — the last-defined
validator runs first. Two before-validators with an ordering dependency are a
silent-data-loss trap, because the dependency is invisible from reading the
model top to bottom.

`ParticipantStatus` hit exactly this
(`vultron/core/models/participant_status.py`): `_enforce_role_dimension_invariant`
is defined *after* `_migrate_flat_fields`, so it ran *first*, saw `data["vf"]`
absent, seeded `data["vf"] = {}`, and `_migrate_flat_fields` then found the key
already present and skipped flat-key migration — a `vf_state=CS_vf.Vf` passed at
construction was silently reset to the initial state.

**How to apply:** when two `mode="before"` validators on the same model have an
ordering dependency, either (a) merge them into a single validator, or (b) guard
the later-running (earlier-defined) one against data the first-running
(later-defined) one has already set — e.g. check for the flat keys (`vf_state`,
`vfState`, `d_state`, `dState`) before seeding an empty dict, so the invariant
only seeds when *no* form of the value is present in the raw data. This is the
same silent-reset family as the shape-guard pitfall above ([Shape Guards](#shape-guards-one-canonical-reader-per-dimension-2232)):
an absent-looking dimension quietly substituted for a real one.

*Source: ISSUE-2662 — reverse-order regression fixed in `ParticipantStatus`.*
