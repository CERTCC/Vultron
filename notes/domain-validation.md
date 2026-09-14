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
  - specs/behavior-tree-node-design.yaml (BTND-10-001 through BTND-10-003)
  - specs/received-status-handling.yaml (RSH-05-001, RSH-05-002)
related_notes:
  - notes/architecture-hexagonal.md
  - notes/bt-integration.md
  - notes/wire-core-boundary.md
  - notes/bt-pitfalls.md
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

### Exception: shape guards live in `models/_wire_spelling.py`

`vultron/core/models/_helpers.py` cannot import from `vultron.core.states` —
that is a circular import through `states/__init__.py`. Shape guards tend to
grow state references (a guard that knows about `rm` eventually wants `RM`), so
they live in `vultron/core/models/_wire_spelling.py` instead of being colocated
with `_as_id()` and friends. This is a deliberate deviation from the rule above,
not an oversight; it exists so the cycle cannot be reintroduced by the next
guard that needs a state enum.

**Scheduled removal**: ARCH-12-003 as amended by ADR-0082 puts `extra="forbid"`
on all core-branch types, which subsumes these guards and deletes
`_wire_spelling.py` — see [notes/wire-core-boundary.md](wire-core-boundary.md).
Until that lands the guidance above is current; do not pre-emptively relocate.

The trap: `states/rm.py`'s own imports look clean (logging, enum, transitions,
`states.common`), so inspecting the target module tells you nothing. The cycle
runs through the package `__init__.py` — `models/base.py` imports `_helpers`,
which triggers `states/__init__.py`, which pulls `states/cs.py` → `states/common.py`
→ back into `models/base.py` while it is still partially initialised. The error
looks like a missing symbol in `models.base`, not a cycle.

### Type-specific canonical readers live with their type

A helper that reads one dimension of one model type (e.g. `participant_status_rm_state`)
belongs in the same module as that type (`vultron/core/models/participant_status.py`),
not in `_helpers.py`. Two reasons:

1. It cannot go to `_helpers.py` if it needs a state enum (see above).
2. Colocating the canonical reader with the type keeps the authorship contract
   clear: the module that defines a type owns its read semantics.

The distinction from shape guards in `_wire_spelling.py`: shape guards are
cross-cutting (they need to know about the core/wire boundary across multiple
types); canonical readers are type-specific. Cross-cutting → `_wire_spelling.py`;
type-specific → the type's own module.

BT-node-level wrappers that combine multiple readers (e.g. `read_rm_states()`)
live in `vultron/core/behaviors/helpers.py`, which has no circular-import
restriction (it is below use-cases, above models, and can import from either).

---

## Shape Guards: One Canonical Reader per Dimension (#2232)

`ParticipantStatus` exists in two incompatible shapes: core nests
`rm: RmDimension` / `vfd: VfdDimension` (SDO-03-002, ADR-0036), while the wire
projection carries flat `rm_state` / `vfd_state`. Reading a dimension off the
wrong shape yields `None` — which every reader then quietly substituted an
initial state for, resetting the participant's ladder (#2264).

**Read a dimension only through its canonical reader.** Both live in
`vultron/core/models/participant_status.py`:

| Reader | Returns | Raises |
|---|---|---|
| `participant_status_rm_state(status)` | the `RM` state | `VultronValidationError` on a non-core shape |
| `participant_status_vfd_state(status)` | the `CS_vfd` state | `VultronValidationError` on a non-core shape |

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

The mirror-image guard is `reject_wire_spelled_keys()` in
`vultron/core/models/_wire_spelling.py`: a core type validated against a
wire-spelled (camelCase) payload drops every snake-only key in silence, because
Pydantic v2 ignores unknown keys. It is computed per exact class, so a
`CaseParticipant` role subclass that adds a field is covered without any
registration step. (Superseded direction: ARCH-12-003's `extra="forbid"` clause
replaces this guard — see [notes/wire-core-boundary.md](wire-core-boundary.md).)

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

Whether the receive path *should* also be all-or-nothing is a genuinely open
question, tracked separately. ADR-0061's standing argument against it: a
refusal in one dimension carries no information about the others, and the
pre-existing all-or-nothing behaviour silently destroyed accepted state and
killed embargo teardown.

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
outside the evaluator, each with a reason; the unresolved consolidation is #3111.

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
site advances exactly one named actor (the leaver, or the case actor closing its
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

## Summary of Named Silent-Failure Sites (CONCERN-1360)

| Site | Old behavior | New behavior |
|---|---|---|
| `_as_id()` in `embargo_lifecycle.py` | Duplicate copy | Removed; moved to `core.models._helpers` (#1428) |
| `_find_case_manager_*` (3 copies) | 3 independent copies returning `None` | 1 canonical function in `use_cases/_helpers`; others removed |
| `_extract_case_id()` in dispatcher | Returns `None`; activity silently not indexed | Raises `UnroutableActivityError` |
| `CommitCaseLedgerEntryNode.update()` | Returns `Status.SUCCESS` on missing `case_id` | Returns `Status.FAILURE` |
| `_read_case_obj()` in communication.py | Swallows `KeyError`; no diagnostic | Sets `feedback_message`; caller returns `Status.FAILURE` |

See `specs/architecture.yaml` ARCH-15-001 through ARCH-15-004 for
normative requirements derived from this concern.

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

## Pitfall: Pydantic `model_fields` Is Not Available Inside `__init_subclass__`

`cls.model_fields` is populated by Pydantic's metaclass *after*
`__init_subclass__` returns. Accessing it inside `__init_subclass__` returns an
empty dict for the class being defined (though parent-class fields may be
present). To inspect a class's own fields at subclass-registration time, read
`cls.__annotations__` directly for declared annotations, or defer field
inspection to a `model_post_init` or a class-level
`@model_validator(mode="before")`.

Source: ISSUE-2294

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
