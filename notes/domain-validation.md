---
title: Domain Object Validation — Strict vs. Loose Boundaries
status: active
kind: guidance
description: >
  Where domain objects move from "loose" (possibly None/unresolved fields) to
  "strict" (required fields guaranteed), how helpers fail fast, how mutation
  bypasses validation, how status writes are validated (one composed evaluator,
  every violation reported), and Pydantic/Python pitfalls that silently mask
  invalid state.
related_specs:
  - specs/architecture.yaml (ARCH-10-001, ARCH-12-001, ARCH-12-003, ARCH-15-001,
    ARCH-15-002, ARCH-15-004, ARCH-18-005, ARCH-20-008, ARCH-21-001 through ARCH-21-004,
    ARCH-25-003)
  - specs/case-management.yaml (CM-01-001, CM-18-005, CM-23-001, CM-27-001
    through CM-27-003, CM-31-001)
  - specs/case-ledger-processing.yaml (CLP-07-002)
  - specs/rm-behavior.yaml (RMB-14-004, RMB-14-005)
  - specs/participant-role-management.yaml (PRM-03-003)
  - specs/error-handling.yaml (EH-05-002, EH-07-001 through EH-07-003)
  - specs/code-style.yaml (CS-23-001)
  - specs/behavior-tree-node-design.yaml (BTND-10-001 through BTND-10-003)
  - specs/received-status-handling.yaml (RSH-09-001 through RSH-09-004)
  - specs/message-validation.yaml (MV-11-001 through MV-11-005)
related_notes:
  - notes/architecture-hexagonal.md
  - notes/bt-integration.md
  - notes/wire-core-boundary.md
  - notes/bt-pitfalls.md
  - notes/case-state-model.md
  - notes/participant-embargo-consent.md
  - notes/case-ledger-authority.md
  - notes/architecture-ratchet-corpus.md
  - notes/lifecycle-staged-types.md
  - notes/status-dimension-objects.md
  - notes/testing-pitfalls.md
  - notes/predicates-rule-layer.md
---

# Domain Object Validation — Strict vs. Loose Boundaries

## The Strict/Loose Distinction

- **Loose zone**: objects freshly deserialized from the wire or DataLayer.
  Optional fields may be `None`, IDs may be unresolved strings or inline objects.
- **Strict zone**: objects ready for domain logic; every field the operation
  needs is non-None and of the expected type.

The boundary is a series of **fail-fast checkpoints** at the entry to each
domain operation, not one conversion. Pydantic construction enforces structural
invariants (ARCH-10-001); runtime helpers enforce relational ones ("this case has
a CASE_MANAGER with a resolvable actor ID"). Checkpoints:

1. **Use-case `execute()` entry**: required inputs non-None before any work.
2. **BT node `update()` entry**: a missing blackboard key returns
   `Status.FAILURE`.
3. **Helper boundaries**: a helper that needs a non-None value raises at once.

**Never return `Status.SUCCESS` when a required input is absent** (ARCH-15). The
subtree cannot produce its effect, and `SUCCESS` silently drops protocol
behavior: ledger entries not written, broadcasts not sent.

### Lenient helpers stay lenient

`_as_id()` returns `None` for `None` because many callers probe optional fields
(`case.active_embargo`). Do not make it raise. The strict guarantee lives in the
caller:

```python
manager_id = _as_id(participant.attributed_to)
if manager_id is None:
    raise VultronValidationError("CASE_MANAGER participant has no attributed_to")
```

### A missing case ID is the handler's refusal, not a dispatcher error

The dispatcher routes by semantics alone and extracts no case ID. A received event
that names no case reaches its handler, which refuses it with a `HandlerResult`
(HP-05-002). Do not add a routing exception for it: the handler already knows which
field must carry the case.

## Canonical Helper Locations

- Layer-neutral utilities with no dependency above `models/` go in
  `vultron/core/models/_helpers.py`, importable by every layer (`_as_id()`).
- Helpers that need ports, state machines or use-case logic go in
  `vultron/core/use_cases/_helpers.py`.
- A reader of one dimension of one type lives with the type
  (`participant_status_rm_state` in `core/models/participant_status.py`): the
  module that defines a type owns its read semantics.
- BT-level wrappers combining readers (`read_rm_states()`) go in
  `vultron/core/behaviors/helpers.py`.

Never keep a duplicate copy elsewhere; import from the canonical location.

**`core/models/_helpers.py` cannot import `vultron.core.states`.** The cycle runs
through the package `__init__.py` (`models/base.py` → `_helpers` →
`states/__init__.py` → `states/cs.py` → `states/common.py` → `models/base.py`), so
the target module's own imports look clean, and the error shows as a missing
symbol in `models.base`, not a cycle. A helper needing a state enum goes with its
type.

Unknown-key rejection is not a helper: it is `extra="forbid"` on `CoreRecord`
(ARCH-12-003). Never add a per-class reject-guard (SDO-03-005;
`test/architecture/test_core_extra_forbid.py`). See
[wire-core-boundary.md](wire-core-boundary.md) for what `forbid` does and does not
reject, and for the inbound unknown-key rule (MV-11).

## Shape Guards: One Canonical Reader per Dimension (#2232)

**Read a `ParticipantStatus` dimension only through its canonical reader** in
`vultron/core/models/participant_status.py`: `participant_status_rm_state()`,
`participant_status_vf_state()`, `participant_status_d_state()`. Each raises
`VultronValidationError` on a non-core shape.

The reason: a `getattr` chain on the wrong shape yields `None`, and a reader that
substitutes the initial state silently resets the participant's ladder (#2264).
Absence and shape mismatch are different outcomes: an **empty** status list is a
legitimate absence callers check for; a status with no usable dimension must raise
(ARCH-15-001, ARCH-15-002).

**At a wire→core ingress boundary, skip rather than raise.** An embedded object
that is not a core participant is the sender's defect and must not cost the
receiver the whole case. `_project_to_core_participant()`
(`core/services/case_replica_seeding.py`) skips it with an ERROR, using an
`isinstance` check, never a duck-typed `to_core()` (ARCH-20-008). A strict reader
without that guard aborts the received-case tree on every inbound `Announce`.

## Post-Construction Mutation: Three Doors, One Lock (#2261)

Pydantic validates at **construction** only. The value the constructor rejects
is accepted through two other doors:

```python
case = VulnerabilityCase(case_participants=[wire_obj])  # ValidationError
case.case_participants = [wire_obj]                     # accepted
case.case_participants.append(wire_obj)                 # accepted
```

The two remedies close different doors:

- `validate_assignment=True` closes assignment. It does nothing for `append`.
- `append` is closed by prohibition plus canonical mutators plus a ratchet
  (CM-27-001): `add_case_status()` (CM-27-003), `add_participant_status()`
  (PRM-03-003), `add_participant()`. The roster has no deleting mutator: removal
  calls `CaseParticipant.record_removal()` and keeps the record (CM-31-001).

### Where `validate_assignment` goes, and where it must not

| Layer | `validate_assignment` | Why |
|---|---|---|
| Core models, via `CoreRecord`'s `ValidatedAssignmentMixin` | **on** (ARCH-21-001) | Readers depend on the shape guarantee |
| Wire (`vultron/wire/`) | **never** (ARCH-21-002, ARCH-21-003) | Inbound data is legitimately loose |

The wire branch is lenient structurally: `as_Base` does not subclass a core root
(ARCH-12-001), so the flag has no MRO path into it. Never reintroduce a shared
root or make a wire class inherit a core root to reuse a field. Cost is
immaterial (about 1 µs per scalar assignment; collection assignment re-validates
all N items). Decision: ADR-0064; ratchet:
`test/architecture/test_validate_assignment_ratchet.py`.

### Pitfall: never assign to `self` in a `mode="after"` validator

`validate_assignment` re-runs **every** `mode="after"` validator on each
assignment, so a validator writing to `self` re-enters itself; unguarded, it
recurses until `RecursionError`, which masks every other failure (ARCH-21-004).

```python
# Wrong: assignment re-runs this validator.
@model_validator(mode="after")
def _set_role(self) -> ExampleParticipant:
    self.case_roles = []
    ...

# Right: derive before validation, so the derived value is itself validated.
@model_validator(mode="before")
@classmethod
def _set_role(cls, data: Any) -> Any:
    ...
```

Writing through `self.__dict__["field"]` stops the recursion but leaves the value
unvalidated; do not. Wire validators are exempt only because the wire branch
never enables the flag.

## Rejecting as a Unit Does Not License Reporting One Reason (#2112)

**Atomicity and diagnostic completeness are independent.** A boundary that
refuses its whole input MUST still report every violation it can recognise
(EH-07-001, BTND-10-002). Because nothing partial was accepted, a caller told one
reason at a time gains nothing: it fixes one dimension, resubmits, and hears the
next. Fail-fast is right for a *write*, wrong for a *diagnostic* (ADR-0086).

### The emit/receive asymmetry is Postel's maxim, not an inconsistency

| | Trigger / emit path | Receive path |
|---|---|---|
| Entry point | `ValidateTriggerTransitionsNode` | `CheckParticipantStatusAcceptableNode` |
| Admits | Valid adjacent steps only | Any forward move, non-adjacent included; omitted dimensions |
| Disposition | Any violation refuses the write | Any violation refuses the whole status |
| Source | BTND-10-001, ADR-0086 | RSH-09-001, RSH-09-003, ADR-0107 |
| Postel | Conservative in what you send | Liberal in what you accept |

Do **not** "fix" the admitted moves to match: the receive path stays liberal in
what it admits, because RM is self-declaratory (ADR-0121) and a peer may advance
several steps between messages (CSB-16-001). Both paths refuse whole, though:
the receive path never records part of a status, because that records one
nobody sent (RSH-09-001, decided under #4451). The cost is that a
correct P/X/A observation sent beside a regressing RM is refused with it; the
refusal notice names every reason, so the sender corrects and resends
(RSH-09-002). A refused receive returns `HandlerResult.refused`, written as a
`rejected` `InboxOutcome` (ADR-0095).

On the emit side, `ParticipantStatus(previous_rm_state=...)` refuses a backward
RM step at construction; `force_rm_state=True` is the bootstrap-only override
(RMB-14-005).

### Root vs. derived violations

Classify by dimension overlap (EH-07-002), so one fix does not hide under a wall
of errors:

- A rule reading **one** dimension is always **root**.
- A rule reading **several** is **derived** if any dimension it reads already
  carries a single-dimension violation, and **root** otherwise.

Dimension overlap, not a rule dependency graph, classifies a new rule correctly
by construction.

### Compose the rule set, don't just share the predicates

Two nodes validating the same write MUST call **one** evaluator that returns
every violation, not the same predicates (BTND-10-002). Shared predicates still
let each caller pick a different subset, which is how the guard and the write
node diverged.

- The evaluator is `participant_transition_violations()`
  (`vultron/core/states/participant_transitions.py`), reached through
  `validate_participant_status_write()`
  (`behaviors/case/nodes/participant/common.py`), which also renders
  `feedback_message` and writes `result_out["error"]`.
- `test/architecture/test_participant_status_validation.py` fails any node that
  names an individual predicate; its `_DECLARED_EXCLUSIONS` lists sites outside
  the evaluator, each with a reason.
- It covers RM, VF, D and case-level P/X/A only. PEC is not a status dimension:
  consent moves only through `CaseParticipant.apply_pec_transition()`
  (CM-18-005, ADR-0122).

**The write node keeps its own checks** (BTND-10-003). `CreateParticipantStatusNode`
is reached from `develop_fix.py`, `deploy_fix.py` and the Leave closure writer
without passing through the guard; there its checks are the only validation. On
the trigger path the guard fails first, so nothing is double-reported.

**Bound blast radius by reachability where the rules are pure functions over
enums.** The RM↔VF and RM↔D entailments (CSB-18-001) cannot fire on legal data,
because a fix-ready `vf` or deployed `d` requires having passed `ACCEPTED` and RM
never walks back. The VF↔D entailment (CSB-17-001) is RM-independent and refuses
`(vf, D)` and `(Vf, D)` at any RM state; those states are already corrupt. Scope
such a bound to the rules that actually read the dimension.

### Pitfall: an omitted dimension is reset, not left alone

`ParticipantStatus` re-seeds `vf` for a VENDOR and `d` for a DEPLOYER at their
**initial** state when the field is omitted
(`_enforce_role_dimension_invariant`). A status built with only `rm` rewinds a
vendor's fix-ready path. Any `ParticipantStatus(...)` construction MUST carry the
participant's current `vf`/`d` forward, as `CreateParticipantStatusNode` does, but
only while the role is still held: `cvd_role` is recomputed from current roles,
and a carried path the role list denies contradicts itself (ADR-0075).

General rule: **a model that auto-seeds a field turns "omit it" into "reset it";
one that does not turns it into "drop it".** Check every constructor call of a
type with seeding validators (`_init_participant_status_if_empty`,
`_seed_accepted_status`). Tests place a participant at an RM state with
`advance_participant_rm` (`test/support/participant_status.py`), which carries
the same paths forward.

### Pitfall: a forced promotion runs after validation

`CreateParticipantStatusNode._apply_ac1_promotions()` applies SM-09-001's forced
promotions (`pXa→PXa`, `pXA→PXA`, `vP→VP`) **after** the evaluator runs, and the
promoted values are persisted. "One evaluator governs every write" does not mean
"everything persisted was validated". The promotion is unreachable for an
unlicensed dimension only because the VF and D role gates cover every asserted
value (#3135). **If you add a route by which a participant acquires a dimension
its role does not license, you reopen this.**

### RM closure walks the table; only the CASE_MANAGER walks it

- **Closure goes through the RM table, never an override** (ADR-0114,
  RMB-14-004/005). RM closes from *Received* (`R → C`); from *Valid* it is written
  as `V → D → C`. CASE_MANAGER closure sites use `RMClosureWriter`
  (`case/nodes/participant/rm_closure.py`), which walks `rm_closure_path()` with
  adjacency validation in force. `test/architecture/test_rm_closure_no_force.py`
  pins that `force_rm_state` remains only on bootstrap writes (ARCH-18-005). If a
  new closure path seems to need the override, the table or the path is wrong.
- **A replica never walks `rm_closure_path()`** (#4091). It would walk from its own
  possibly stale stored state and write a step no ledger entry backs. The
  CASE_MANAGER ledgers a `close_case` entry for the received `Leave`, then one
  `add_participant_status_to_participant` entry per transition (CM-23-001); a
  replica applies those status entries, and `close_case` changes no RM state on
  replay. The Leave record commits the `closure_steps` its advance wrote, never
  re-derived from history. Pinned by
  `test/architecture/test_replica_never_walks_rm_closure_path.py`.
- **Closure advances exactly one named actor**: the leaver, or the CASE_MANAGER
  closing its own lifecycle on owner Leave (ADR-0051). A participant that never
  sent `Leave` keeps its last RM state.

### Surfacing a violation list

`VultronValidationError` carries violations as structured data and renders the
whole set in `__str__` (EH-07-003). The HTTP translation adds a `details` array
beside `message` (EH-05-002), so clients need not parse a joined string.
`SvcBTTriggerBase.execute()` re-raises the exception at `result_out["error"]`, so
a guard node only needs `result_out`. Aggregation stays within one node, so
BT-13-001's first-failing-leaf contract is unaffected.

`details` is absent when a single-violation sibling guard fails first
(`CheckNotSoleObserverVfdNode`, `CheckDeployerRoleNode`): `execute()` then builds
a generic error from `get_failure_reason(tree)`. That conforms (EH-05-002 needs
`details` only for more than one violation); never write a client that assumes
`details` is present.

## Broad `except Exception` Is a Masking Smell (CONCERN-3295, CS-23-001)

A blanket `except Exception` around domain logic is more likely to mask a defect
than handle a real case; the tell is a missing rationale. In #3217 a parser
fallback that read as a compatibility shim fired 52 times from one layering bug.

For every broad catch outside the sanctioned boundary, do **one** of:

1. **Narrow** it to the types you expect.
2. **Delete** it and let the error propagate.
3. **Justify** it, only at a genuine framework boundary: narrowest covering type
   plus an inline comment stating what it guards and why.

**The one sanctioned broad-catch boundary is a BT node's `update()`**, which
converts an unexpected error into `Status.FAILURE` (BT-HELPER-01,
[bt-pitfalls.md](bt-pitfalls.md)). Even that can defeat the bridge's
`internal_error` detection ([bt-integration.md](bt-integration.md)). Other
boundaries (`BTBridge` execution, py_trees `setup()`/`initialise()`) are listed
in the enforcing test's `_DECLARED_EXCLUSIONS`, one reason each, as a pinned
exemption set (ARCH-18-005). Ratchet:
`test/architecture/test_no_broad_except_outside_bt_update.py`.

### When you cannot tell whether a fallback is load-bearing

For any silent-degradation branch (broad `except`, `or <default>`, `return None`
or an arbitrary value on a failed lookup), do not guess from the code. Instrument
it: log the `(class, keys, error)` reaching the branch, run the **full** suite,
and group by cause (#3217).

- **One cause**: the tolerance masks a bug. Fix the cause, delete the tolerance.
- **Many causes**: a genuine compatibility surface. Narrow it and document what it
  absorbs.

Fix the masked causes **before** removing the tolerance, or every absorbed case
becomes a hard failure.

## Pitfall: `getattr(obj, name, default)` Does Not Catch `ValueError`

Three-argument `getattr` suppresses only `AttributeError`. A property that raises
`ValueError` (`VulnerabilityCase.current_status` with no materialised status)
propagates through it. Where a property may raise on partially initialised data:

```python
try:
    current_status = case.current_status
except (AttributeError, ValueError):
    current_status = None
```

**`NotImplementedError` from a property is a programming error: do not catch
it.** `ValueError` means the data is invalid (treat as absence at the calling
boundary); `NotImplementedError` means an adapter is incomplete. Converting it to
`VultronValidationError` misdiagnoses a broken adapter as bad data. A port
property callers rely on for routing MUST NOT raise `NotImplementedError`
(`CasePersistence.actor_id`, CM-01-001).

## Pitfall: Inside `__init_subclass__`, `model_fields` Reports the *Parent's* Fields

Pydantic rebuilds `cls.model_fields` *after* `__init_subclass__` returns. Inside
it, the dict holds the **parent's** fields, so a presence check succeeds and
returns a silently wrong value (a child's `type_` default reads as the parent's
`None`, #2982).

To inspect a class's own declarations at registration time, read the raw
namespace: `cls.__dict__["type_"]` (a `FieldInfo` when assigned via `Field(...)`)
and `cls.__dict__["__annotations__"]`. After construction Pydantic strips field
definitions from `cls.__dict__`, so only `model_fields` answers then. Code that
must work in both contexts needs both paths
(`vultron/wire/as2/vocab/base/registry.py::declared_wire_type`); otherwise defer
inspection to `model_post_init` or a `mode="before"` validator.

## Pitfall: `mode="before"` Validators Run in Reverse Definition Order

With several `@model_validator(mode="before")` on one model, the last-defined
runs first. An ordering dependency between them is invisible top to bottom and
loses data silently: a seeding validator that runs first fills an empty default,
and the one that should have read the supplied value sees the key present and
skips it (#2662).

Either merge the dependent validators into one, or guard the later-running one
against every form of the value the earlier-running one may set, so it seeds
only when *no* form is present. Same silent-reset family as
[Shape Guards](#shape-guards-one-canonical-reader-per-dimension-2232).
