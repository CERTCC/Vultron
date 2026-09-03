---
status: accepted
date: 2026-09-02
deciders: Allen D. Householder
consulted: Vultron protocol maintainers
informed: Vultron contributors
---

# Report Every Violation, Reject the Batch — and the Emit/Receive Dispositions Are Postel's Maxim

## Context and Problem Statement

A `ParticipantStatus` write carries several independent state machines at once:
`rm`, `vf`, `d` and `pxa`. A single request can therefore be invalid in more than
one way simultaneously. Every validator on the emit path stops at the first
problem it finds and reports only that one:

- `ValidateTriggerTransitionsNode.update()` checks RM, VF, D, VF-role, PXA and
  then the cross-machine entailments, returning `FAILURE` at the first failing
  check.
- `CreateParticipantStatusNode.update()` runs `_check_vf_precondition`,
  `_check_d_precondition`, `_check_pxa_precondition` and
  `_check_compound_transition`, likewise returning at the first.
- `cross_machine_violations()` already returns *every* violated entailment as a
  list, and both callers discard all but element zero.

The caller — a human or an agent driving the `add-participant-status` trigger —
therefore fixes one dimension, resubmits, and is told about the next one. The
request is atomic, so nothing partial was accepted, which means the round trip
bought no progress. Reported as ISSUE-2112.

Two questions are entangled in that report, and separating them is most of this
decision:

1. **Should the write be rejected as a unit?** Yes, and it already is.
2. **Does rejecting as a unit license reporting only one reason?** No — but the
   codebase asserted that it does. `_validate_entailments`' docstring read
   "Emitting is all-or-nothing, so the first violation is enough to refuse the
   whole trigger," and `cross_machine_violations()` justified its ordering so
   that "a caller that reports only the first violation reports the same one it
   always did."

The second inference is the actual defect. Atomicity is a statement about what
gets *written*; it says nothing about what gets *reported*.

A third question surfaced while investigating and is settled here because
leaving it implicit is what invited the confusion: the receive path deliberately
does the *opposite* of the emit path, and nothing recorded why the two differ.

## Decision Drivers

- Atomicity and diagnostic completeness are independent properties. Conflating
  them is what produced the fix-one-resubmit loop.
- Postel's maxim (ISSUE-2229, the liberal-accept epic): be conservative in what
  you send, liberal in what you accept. The emit and receive paths are the two
  halves of that sentence, not an inconsistency to be reconciled.
- A single-dimension error frequently entails further violations. Reporting four
  problems where one fix clears three is a different failure of the same kind.
- The transition and role predicates were implemented twice — once in
  `ValidateTriggerTransitionsNode`, once in `CreateParticipantStatusNode` — with
  byte-identical message text. That violates ARCH-15-004 and is a live drift
  hazard, and it is the reason a clean per-site fix was not available.
- `CreateParticipantStatusNode` has production call sites that reach it without
  passing through `ValidateTriggerTransitionsNode` (`develop_fix.py`,
  `deploy_fix.py`, `close_case_effect.py`, and two in `leave.py`). For those,
  the write-node checks are the *only* validation, exactly as BTND-10-001's
  rationale anticipated.
- ISSUE-2906 established that the durable fix for two paths enforcing different
  subsets of a rule set is to compose the set once and have both call it —
  sharing the individual predicates is not enough.

## Considered Options

- **Keep fail-fast; document it and pin it with a test.** The resolution option
  originally recommended in ISSUE-2112.
- **Aggregate within each validator independently.**
- **Extract one shared evaluator returning every violation; both validators call
  it and report the full list.**
- **Aggregate across the whole trigger validation stack**, including the sibling
  role-guard nodes.

## Decision Outcome

Chosen option: **extract one shared evaluator returning every violation; both
validators call it and report the full list.**

### Reject the batch

The emit path stays all-or-nothing. Any violation refuses the entire write; no
dimension of a rejected request is persisted. This is unchanged, and it is now
stated as a property in its own right rather than inferred from the shape of the
code.

### Report every violation

A single shared evaluator — `participant_transition_violations()`, modelled on
the existing `cross_machine_violations()` — evaluates the per-dimension
transition rules, the role gates and the cross-machine entailments, and returns
every violated rule. Both `ValidateTriggerTransitionsNode` and
`CreateParticipantStatusNode` call it and report the whole list.

Both aggregating cannot double-report: on the trigger path the guard node fails
first and the enclosing `Sequence` aborts before the write node runs. On the
five paths that bypass the guard, the write node is the only reporter.

### Label derived violations

Violations are classified by the dimensions they read:

- A **single-dimension** rule — a transition check or a role gate — is always
  reported as root.
- A **multi-dimension** rule — a cross-machine entailment or the compound CS
  transition — is reported as *derived* when any dimension it reads already
  carries a single-dimension violation, and as *root* otherwise.

The derived case is a consequence of an error already reported. The root case is
the genuinely interesting one: every dimension moved legally on its own and the
*combination* is impossible.

The test is dimension overlap, not a rule-to-rule dependency graph. A new rule
is classified correctly by construction, so the labelling cannot go stale as the
rule set grows.

### Surface the list, do not make callers parse a string

`VultronValidationError` gains a `violations` list, following
`DemoFailureError`'s existing `failures` shape, and renders the full list
through `__str__`. Each entry carries the rule's `message`, the `dimensions` the
rule reads, and its root/derived classification. The FastAPI translation adds a
`details` array to the 422 body alongside the existing `message`. Callers that
want individual violations read `details`; callers that want a human-readable
summary keep reading `message`.

The existing plumbing carries this end to end with one change:
`SvcBTTriggerBase.execute()` already re-raises whatever exception it finds at
`result_out["error"]`, so the guard node needs only to be passed `result_out` —
which the write node already receives.

### The emit/receive asymmetry is Postel's maxim

The trigger path is what an actor *sends*, so it is conservative: reject the
whole batch and say everything that is wrong with it. The receive path is what
an actor *accepts*, so it is liberal: adjudicate each dimension independently and
carry the participant's current value forward for the refused ones (ADR-0061,
RSH-05-001, RSH-05-002).

These are the two halves of one principle applied to opposite sides of the wire,
not a contradiction. Anyone reading one path and inferring the other's
disposition from it will be wrong.

Whether the receive path *should* also be all-or-nothing is a live question and
is tracked separately rather than settled here. ADR-0061's drivers — a refusal
in one dimension carries no information about the others, and the pre-existing
all-or-nothing behaviour silently destroyed accepted state and killed embargo
teardown — remain the standing argument against changing it.

### Consequences

- Good, because a caller learns everything wrong with a request in one round
  trip instead of one problem per submission.
- Good, because the transition and role predicates have exactly one
  implementation, so the two validators can no longer drift apart (ARCH-15-004).
- Good, because `details` gives callers a stable structured surface. ISSUE-2112
  specifically noted that a change to check order silently alters which error
  surfaces for callers parsing the message string; that fragility goes away.
- Good, because the root/derived split keeps thoroughness from degrading into a
  wall of consequential errors.
- Good, because the five call sites that bypass the trigger guard get the same
  diagnostics as the trigger path. **Correction (#3050):** this was asserted to
  cost nothing, and for VF, D and PXA it does not. It is not true for RM. Giving
  the write node the whole rule set made it validate RM for the first time, and
  three of those sites — `close_case_effect.py` and both in `leave.py` — stamp a
  departing participant `RM.CLOSED` from whatever rung its RM machine is on,
  which the RM machine does not permit. They carry a documented `force_rm_state`
  exemption suppressing only the RM rule; whether case closure should force
  participant RM state at all is tracked as ISSUE-3106.
- Bad, because `message` content changes for multi-violation failures, so any
  test or log assertion matching the single-error text needs updating.
- Bad, because EH-05-001 gains an optional field, which is a public-surface
  change to every Vultron error response, not only this endpoint.
- Neutral, because the aggregation is confined to one node per path. The sibling
  role-guard nodes (`CheckNotSoleObserverVfdNode`, `CheckDeployerRoleNode`) still
  short-circuit the `Sequence` and cannot co-report; BT-13-001's
  first-failing-leaf contract is unchanged and needs no amendment.

## Validation

Unit tests assert that a request invalid in two dimensions reports both; that a
root multi-dimension violation (both dimensions individually legal, the pair
impossible) is labelled root; that the same violation is labelled derived when
one of its dimensions independently failed; that nothing is persisted in any of
these cases; and that the 422 body carries one `details` entry per violation.

An architecture ratchet asserts that neither validator calls the individual
`violation_*` / `is_valid_*` predicates directly, following the ISSUE-2906
pattern — composing the rule set is what makes divergence impossible rather than
merely fixed.

## Pros and Cons of the Options

### Keep fail-fast; document it and pin it with a test

- Good, because it is the cheapest possible change.
- Bad, because it entrenches the fix-one-resubmit loop as intended behaviour.
- Bad, because it leaves the ARCH-15-004 duplication in place.

### Aggregate within each validator independently

- Good, because it needs no new module and no shared type.
- Bad, because each validator enforces a different overlapping subset, so the
  two report different things for the same request depending on which path
  reached them.
- Bad, because it leaves duplicated predicates with identical message text —
  the drift hazard survives the fix.

### Extract one shared evaluator returning every violation

- Good, because it fixes the diagnostics and the duplication in one coherent
  change, addressing the reason the diagnostics were awkward to fix.
- Good, because it reuses `cross_machine_violations()`' established shape rather
  than inventing a parallel one.
- Neutral, because the write node keeps its own validation call rather than
  becoming a thin delegate; BTND-10-001 requires the write boundary to be
  fail-closed independently of guard coverage.

### Aggregate across the whole trigger validation stack

- Good, because it is the most complete answer to "report everything".
- Bad, because the role guards are siblings in a `memory=False` `Sequence`,
  which short-circuits by design; collecting across them requires restructuring
  the tree.
- Bad, because it requires amending BT-13-001, which mandates retrieving the
  failure reason via a depth-first walk to the first failing leaf.

## More Information

- ISSUE-2112 — the concern this decision resolves.
- ISSUE-2229 — liberal-accept epic (Postel's maxim).
- ADR-0061 — per-dimension partial accept on the receive path; the other half of
  the maxim.
- ISSUE-2255 — the receive path's own diagnostics gap: a sender is never told
  which dimension was refused.
- ARCH-15-004 — exactly one canonical copy of each domain helper.
- BTND-10-001 — write-boundary validation is required independently of upstream
  guard coverage, which is why the write node keeps its checks.
- BT-13-001 — first-failing-leaf failure reporting; unchanged by this decision.

Generated spec requirements: `error-handling.yaml` EH-05-002 and EH-07-001
through EH-07-003; `behavior-tree-node-design.yaml` BTND-10-002 and BTND-10-003.
