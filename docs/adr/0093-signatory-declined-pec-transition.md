---
status: accepted
date: 2026-09-17
deciders: [adh, Claude Sonnet 4.6]
stakeholder_type: [project-contributor]
---

# ADR-0093: `DECLINE` Is Legal from `SIGNATORY` — Consent Withdrawal Is a First-Class PEC Action

## Context and Problem Statement

The Participant Embargo Consent (PEC) state machine defines `DECLINE` as valid
only from `UNBOUND | INVITED | LAPSED`.  A participant who is `SIGNATORY` to
an active embargo cannot legally reach `DECLINED` directly.

This creates a concrete reachability gap on the **received side**.  When a
`SIGNATORY` participant rejects an embargo revision proposal, the received-side
reject tree (`reject_invite_to_embargo_tree`) issues `PEC_Trigger.DECLINE`.
Because the received path runs no EM lifecycle node, nothing moves the participant
from `SIGNATORY` to `LAPSED` first.  `PecDimension.transition()` raises
`VultronInvalidStateTransitionError`; `BTBridge` catches it and returns `FAILURE`
(logged at `ERROR` with a traceback); the ledger receipt commits but the consent
change is dropped.  The participant stays `SIGNATORY` after explicitly rejecting.

The test `test_reject_from_signatory_is_refused_not_applied` pinned this as
"current behavior, not endorsed."

The gap also has a **trigger-side dimension**.  VP-13-007 and VP-13-008 require
that a participant who changes their intent to comply with an active embargo
communicate that change.  There is currently no legal trigger-side PEC path for
a `SIGNATORY` to withdraw consent outside of a revision cycle.

Concern #3142 identifies two intertwined issues:

1. **Received-side reachability gap** (the concrete bug): a `SIGNATORY` rejecting
   a revision has no legal PEC path to `DECLINED`.
2. **Lapse-timing question**: the trigger-side `_cascade_pec_revise()` lapses
   `SIGNATORY → LAPSED` when EM enters `REVISE` (revision *proposed*).  The
   concern asks whether lapse should fire only when a revision is *accepted*
   (when the active embargo actually changes).

## Decision Drivers

- `DECLINED` from `SIGNATORY` is the natural expression of "I explicitly
  withdraw my consent"; blocking it forces fail-closed behavior that drops
  stated protocol intent
- VP-13-007 and VP-13-008 require communicating intent to terminate compliance;
  the `SIGNATORY → DECLINED` path is the PEC mechanism for doing so
- `LAPSED` is an *automatic* state reached when revision terms change under
  a participant; `DECLINED` is *volitional* — the participant said no
- The `LAPSED` distinction is load-bearing (content gating, meta-protocol
  delivery, re-invitation) and MUST NOT be collapsed into `DECLINED`
- The received-side fix must not require running an EM lifecycle node on the
  reject path (which would couple the reject handler to the revision-cascade)
- Lapse-timing: lapse-on-propose is the correct semantics — when EM enters
  `REVISE`, the revision terms have not yet been accepted but the prior consent
  no longer covers them; `LAPSED` correctly models "waiting to re-consent"

## Considered Options

1. **Mirror the trigger-side cascade on the received reject path** — add a
   `_cascade_pec_revise`-equivalent step before `DECLINE` in the reject tree,
   so `SIGNATORY → LAPSED → DECLINED`.
2. **Add `SIGNATORY → DECLINED` to the PEC transition table** — make consent
   withdrawal a first-class PEC action (chosen).
3. **Declare the scenario unreachable in practice** — argue that on any well-formed
   replica the trigger-side cascade will have run first, so a `SIGNATORY` reaching
   the reject handler is impossible.

## Decision Outcome

**Chosen option: add `SIGNATORY → DECLINED` to the PEC transition table (Option 2).**

A `SIGNATORY` who explicitly rejects is exercising consent withdrawal, not
a lapse triggered by a terms change.  The transition is valid on both the
received side (participant rejects a revision proposal) and the trigger side
(participant voluntarily terminates their embargo compliance, per VP-13-007).

### Lapse-timing: lapse-on-propose is correct

The trigger-side `_cascade_pec_revise()` (SIGNATORY → LAPSED when EM enters
REVISE) is confirmed as correct behavior and is not changed by this ADR.
Rationale: `LAPSED` means "you agreed to the prior embargo terms; a revision
is now proposed; those prior terms no longer cover what is being negotiated."
The current embargo remains in force (`is_em_embargo_active(REVISE) == True`)
and the participant has not yet seen the new terms — they are waiting to
re-consent, not actively refusing.  Lapse-on-propose correctly captures that
position.

Option 1 was therefore rejected: mirroring the cascade on the received path
would add an EM lifecycle step to the reject handler solely to pass through
`LAPSED` before reaching `DECLINED` — an indirection that the direct
`SIGNATORY → DECLINED` transition makes unnecessary.

Option 3 was rejected: the state is reachable in practice, and even if it
were not, the model should be correct rather than relying on a timing invariant
that is not enforced.

### Consequences

- Good, because a `SIGNATORY` rejecting a revision now correctly reaches
  `DECLINED` on both trigger and received paths
- Good, because VP-13-007 and VP-13-008 (communicate intent to terminate
  compliance) become expressible at the PEC level without a workaround
- Good, because the received-side reject tree requires no EM lifecycle step —
  a single `DECLINE` trigger suffices
- Good, because `LAPSED` retains its precise meaning: automatic lapse when
  terms change, not explicit refusal
- Bad, because a `SIGNATORY` can now reach `DECLINED` without passing through
  `LAPSED`; code that assumes "SIGNATORY can only leave via LAPSED" must be
  re-checked.  No such code was found in the sweep at the time of writing.

## Validation

- Unit tests asserting `DECLINE` succeeds from `SIGNATORY` → `DECLINED`
- `test_reject_from_signatory_is_refused_not_applied` renamed to
  `test_reject_from_signatory_transitions_to_declined` and updated to assert
  the invitee reaches `PEC.DECLINED`
- A new test for the trigger-side path: `SIGNATORY` calling
  `EmbargoLifecycle.reject_embargo_invite()` transitions to `DECLINED`
- `grep` sweep over `apply_pec_transition(PEC_Trigger.DECLINE)` and
  `apply_pec_transition(PEC_Trigger.REVISE)` call sites to confirm no caller
  assumes `SIGNATORY` cannot reach `DECLINED` directly

## More Information

- Concern: #3142 (filed from learning entry `20260902-2762-reject-from-signatory-pec-gap.md`)
- Parent epic: #3125 (Embargo lifecycle protocol correctness)
- Related: ADR-0048 (PEC `NO_EMBARGO` means absence of embargo),
  ADR-0091 (rename `PEC.NO_EMBARGO` to `UNBOUND`)
- Open question: whether `UNBOUND` and `DECLINED` should collapse into one state
  (both mean "not bound by any embargo terms"; they differ only in provenance).
  See `docs/reference/vultron-spec/_oq-pec-unbound-declined-collapse.md`.
- VP-13-007 / VP-13-008: the normative spec entries that motivate trigger-side
  consent withdrawal as a first-class protocol action
- Generated spec requirements: `specs/case-management.yaml` CM-18-003 (PEC
  transition table updated to include `SIGNATORY → DECLINED`)
