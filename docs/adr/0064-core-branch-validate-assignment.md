---
status: accepted
date: 2026-08-13
deciders: Vultron maintainers
consulted: Vultron maintainers
informed: Vultron contributors
---

# Enforce Post-Construction Type Safety on the Core Branch Only, in Three Ratcheted Steps

## Context and Problem Statement

Pydantic v2 validates a model at **construction**. `VultronBase.model_config` is
`ConfigDict(populate_by_name=True)` and does not set `validate_assignment`, so
validation stops the moment an object exists. The same value the constructor
rejects is silently accepted through two other doors:

```python
case = VulnerabilityCase(case_participants=[wire_obj])  # ValidationError
case.case_participants = [wire_obj]                     # accepted
case.case_participants.append(wire_obj)                 # accepted
```

This matters because the core and wire branches (ADR-0017) carry structurally
incompatible shapes for the same concepts. A wire-shaped object in a core-typed
field does not raise when read — it reads as *absent*, and readers substitute an
initial state, silently resetting a participant's RM ladder. That is the failure
mode of #2232 / #2264, and it is the same class of defect as #2233, which had
seven Demo Integration scenarios red on `main` at the time of writing.

ADR-0062 already closed the two boundaries where wire data crosses into
persistence: normalisation at ingress and again at the persistence boundary.
What remains unenforced is the **in-memory** invariant — nothing stops code
already inside the core from planting a wrong-shaped object in a typed field.

The obvious remedy is `validate_assignment=True` on `VultronBase`. It was
measured, and it does not work as-is.

## Decision Drivers

- The invariant should hold whichever door a value arrives through.
- `VultronBase` is shared by *both* branches (ARCH-12-001), and ARCH-12-002
  requires it to stay lenient for the wire branch — inbound wire data is
  legitimately loose.
- Whatever we adopt must be measurable and reviewable in increments; a change
  that touches every domain object cannot land as one diff.
- Progress must be visible and drift-proof across multiple issues and weeks.
- Re-validation cost on BT tick loops and ledger replay was unquantified.

### What the measurements showed

Against `origin/main` (baseline: 2 pre-existing unrelated failures, #2274):

| Variant | FAILED | ERROR | Failure types |
|---|---|---|---|
| `validate_assignment` on `VultronBase` | 747 | 423 | **879 × `RecursionError`, nothing else** |
| `validate_assignment` on `CoreObject` | 398 | 268 | **403 × `RecursionError`, nothing else** |

Not one type-strictness failure was visible in either variant. The cause is
uniform: `validate_assignment` re-runs every `mode="after"` model validator on
each assignment, so a validator that writes to `self` re-enters itself. Twenty
three core validators do this (plus twelve in the wire branch). Guarded ones
terminate at depth 2; unguarded ones — `FinderParticipant._set_role`,
`ReporterParticipant._set_accepted_status`, `as_EmbargoEvent.set_name` and
others — recurse until the stack is gone. The recursion **masks** the real blast
radius, which therefore cannot be measured until the validators are fixed.

Two further findings shaped the decision:

- **`validate_assignment` does not close the append door at all.**
  `list.append` is not an attribute assignment, so Pydantic never observes it.
  A separate mechanism is required regardless.
- **Cost is not the obstacle.** Scalar attribute assignment measured
  475 ns → 1464 ns (3.1×, ~1 µs absolute) — immaterial for BT tick loops. The
  open question is collection fields, where assigning `case_participants`
  re-validates all N items.

## Considered Options

Four decisions were made, each with alternatives rejected.

### A — Overall strategy

- Three ordered steps: fix validators, then flip the core branch, then close the
  append door **(chosen)**
- Abandon `validate_assignment`; rely on architecture ratchet tests alone
- One big-bang PR doing all of it
- Close #2261 as won't-fix, since ADR-0062 covers the concrete defect

### B — Where the flag goes

- A core-only mixin applied to every core model **(chosen)**
- `CoreObject` only, accepting the gaps
- Per-class opt-in on the highest-risk types
- `VultronBase` — everything, core and wire

### C — How validators are made assignment-safe

- Ban self-assignment in `mode="after"`; derive in `mode="before"` **(chosen)**
- Sanction `self.__dict__["field"] = value` as an escape hatch
- A re-entry guard flag on the model
- Case-by-case mix of `mode="before"` and the escape hatch

### D — How the append door is closed

- Spec prohibition + canonical mutators + AST ratchet **(chosen)**
- Frozen/tuple collection fields
- A validating sequence wrapper type
- Ratchet now, wrapper later if it proves insufficient

## Decision Outcome

**A — Three ordered steps**, because the measured recursion wall makes any
single-PR approach unreviewable, and because the true type-strictness blast
radius is unknowable until step 1 lands. Each step is independently valuable:
step 1 is a correctness-neutral refactor, step 3 shares no files with the others
and runs in parallel.

**B — A core-only mixin**, applied to the ten root classes from which all 103
core models descend. `VultronBase` is excluded permanently, not deferred: it is
the shared base and `as_Base` inherits it, so setting the flag there violates
ARCH-12-002 and produced the worst measured result. `CoreObject`-only was
rejected because 16 core models sit outside it — including all five dimension
objects (`RmDimension`, `VfdDimension`, `EmDimension`, `PxaDimension`,
`PecDimension`), which are precisely the types implicated in #2232. Per-class
opt-in was rejected because an opt-in list rots: the default stays unsafe and
every new model is unprotected unless someone remembers.

**C — Derive in `mode="before"`**, because the derived value is then validated
normally. The `__dict__` escape hatch would trade one silent hole for a smaller
one — it writes the field unvalidated and does not update `model_fields_set` —
and a rule of the form "MUST NOT, except where noted" needs its own allowlist,
which weakens the ratchet. Scope is `vultron/core/` only; the wire branch's
twelve equivalent validators are **exempt by design**, because the wire branch
never gets `validate_assignment` and therefore cannot recurse.

**D — Spec prohibition, canonical mutators, and an AST ratchet**, because this
exact pattern is already proven in-repo: PRM-03-001 plus
`test_participant_case_roles.py` drove direct `case_roles` mutation in
`vultron/` to **zero** sites. `add_participant()` and `remove_participant()`
already exist. Frozen collections would be a breaking change across ~142
test-side mutation sites; a validating sequence wrapper is a novel type with
serialization and copy semantics to maintain, and no evidence yet that the
static scan is insufficient.

### Ratcheting across the steps

Work spanning three issues loses coherence, and this repo has direct evidence of
how: the `strict=False` xfails for #1991 and #1992 have sat green-and-ignored
since they were filed. A non-strict xfail keeps passing after the work is done,
so it never tells anyone to remove it, and it gives no partial-progress signal.

`test/architecture/test_validate_assignment_ratchet.py` therefore lands with
this decision, before any implementation, carrying three **exact-set backlogs**:
23 self-assigning validators, 10 mixin targets, 3 collection-mutation modules.
Each is asserted with `==`, so it fails if the backlog grows **and** if an entry
is fixed without being ticked off. Each has a companion `xfail(strict=True)`
goal test: when the last entry goes, the goal test XPASSes, which fails the
build and forces the marker to be deleted. The #1991 and #1992 markers were
converted to the same shape in the same change.

### Consequences

- Good, because the invariant becomes enforced rather than documented, and the
  #2232 class of silent state reset becomes a loud failure.
- Good, because the plan is encoded in CI from day one; neither drift nor
  completion can go unnoticed, and partial progress is visible as a shrinking
  set.
- Good, because ARCH-12-002 is preserved and asserted by a test, so a future
  "finish the job" PR cannot quietly move the flag onto the shared base.
- Bad, because 23 validators must be rewritten before any type safety is gained
  — real work with no user-visible benefit.
- Bad, because the type-strictness blast radius remains unknown until step 1
  lands, so step 2 cannot be sized in advance.
- Bad, because the append door stays open until step 3, and the static scan
  cannot see a mutation computed at runtime.
- Neutral: the wire branch keeps its twelve self-assigning validators. If it
  ever gains `validate_assignment`, this trap returns; the exemption is recorded
  here deliberately rather than left implicit.

## Validation

- `test/architecture/test_validate_assignment_ratchet.py` — three exact-set
  backlogs, three strict goal tests, plus `test_detectors_are_not_vacuous`,
  `test_shared_base_is_never_a_target` and
  `test_wire_branch_does_not_enable_validate_assignment`. The heaviest scan runs
  in 0.55 s.
- The ratchet was verified in both directions before merge: injecting a new
  mutation site fails the exact-set test, and neutralising all three backlog-3
  sites turns the goal test into `[XPASS(strict)]` → FAILED, proving the
  completion path forces cleanup.
- Step 2 carries an acceptance criterion to benchmark a BT tick loop and a
  ledger replay, quantifying the O(N) collection-field cost and stating the
  threshold above which the placement would be narrowed.

## More Information

Generated spec entries: ARCH-21-001 through ARCH-21-005
(`specs/architecture.yaml`), CM-27-001 through CM-27-003
(`specs/case-management.yaml`), PRM-03-003
(`specs/participant-role-management.yaml`).

Source: issue #2261 (Concern), planned under Epic #2229.
Related: ADR-0017 (two-branch hierarchy), ADR-0036 (dimension objects),
ADR-0062 (normalisation at ingress and persistence), issue #2232 (the shape
duality), issue #2268 (remaining shadowing types), issues #1991 / #1992 (the
xfail markers repaired here).
Guidance: `notes/domain-validation.md`.
