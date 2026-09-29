---
status: accepted
date: 2026-09-29
deciders: [adh, Claude Sonnet 4.6, Claude Fable 5.1]
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

The first version of this ADR (2026-09-17) answered the second question with
"lapse-on-propose is correct".  Concern #3884 (2026-09-29) reopened it with
evidence that answer had not weighed, and the ADR was revised in place rather
than superseded: it was twelve days old and nothing depended on the
lapse-timing section.  The evidence:

- **A rejected revision stranded every signatory.**  EJ returned EM to `ACTIVE`
  under the old terms, no trigger restored `LAPSED → SIGNATORY`, and the
  `LAPSED → DECLINED` timer was never implemented (lapse detection handles only
  `INVITED`, and a deadline is written only on `INVITE`).  Participants who had
  agreed to the embargo still in force stayed `LAPSED` indefinitely.
- **Adherence disagreed with content gating.**  `embargo_adherence` read false
  for a participant still bound by the active embargo and still receiving
  embargoed content, because the content gate keys on `accepted_embargo_ids`
  containing the *active* embargo's id (CM-10-004), not on PEC state.  The
  scalar and the list disagreed about who was a signatory, and the list was the
  one the system believed.
- **The proposer lapsed too**, and had to accept their own proposal to recover.
- **The owner declined themself.**  `reject_embargo_invite()` applied `DECLINE`
  to the rejecting actor's own record even when that actor was the owner
  rejecting a revision in order to *keep* the standing embargo.
- **The cascade ran in one store only.**  No received path drives a replica's EM
  to `REVISE` on an inbound revision, so when a non-owner proposed, the
  CASE_MANAGER's authoritative record never lapsed anyone.

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
- Consent is given to specific terms — an `EmbargoEvent` — and
  `CaseParticipant.accepted_embargo_ids` already records it per embargo
  (CM-10-001).  The scalar PEC state answers one question: is this participant
  bound by the *active* embargo?
- A participant cannot lapse until the embargo on the case differs from the one
  they agreed to.  While a revision is merely proposed the prior embargo is
  still in force and every signatory to it is still bound by it
- Agreeing to N days is agreeing to every shorter period.  An embargo that ends
  no later than the one a participant accepted asks nothing new of them — the
  same containment that makes shortest-wins safe (EP-04-003) and lets
  termination reset consent without asking anyone
- Only the case owner's Accept or Reject changes the embargo on the case
  (MSM-07-003, MSM-07-004).  Other participants' answers inform that decision;
  they do not make it

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
received side (participant rejects the active embargo) and the trigger side
(participant voluntarily terminates their embargo compliance, per VP-13-007).

### Lapse-timing: consent is per embargo; lapse fires when longer terms activate

*Revised 2026-09-29 (Concern #3884).  This section originally confirmed
lapse-on-propose.  That reading is withdrawn.*

A participant cannot lapse until the embargo on the case differs from the one
they agreed to.  While revision B is merely proposed, embargo A is still in
force, every signatory to A is still bound by A, and nothing about their
consent has changed.  Therefore:

1. **A revision proposal (`ACTIVE → REVISE`) changes nobody's consent state.**
   `propose_embargo()` performs no PEC cascade.  Signatories stay `SIGNATORY`
   and `embargo_adherence` stays true, which agrees with the content gate:
   the active embargo is still A and A is still in their list.
2. **Proposing B is consent to B.**  The proposer's `accepted_embargo_ids`
   gains B at proposal time, so a proposer cannot lapse at activation of their
   own terms.
3. **A signatory's Accept or Reject of proposed B is about B only.**  Accept
   adds B to their list; their state does not change, because they were and
   remain a signatory to A.  Reject leaves them a signatory to A; B is simply
   absent from their list.  A participant who is *not yet* a signatory
   (`INVITED`, `UNBOUND`, `LAPSED`) records an Accept of B in their list with
   no state change, and a Reject of B as `DECLINE` (MSM-07-004): they hold no
   consent to A that the refusal could leave intact.  Only the case owner's
   Accept or Reject moves the shared EM machine; other participants' answers
   inform the owner's decision.
4. **Activation is where consent is re-evaluated, and it is asymmetric.**  When
   the owner activates B in place of A (`REVISE → ACTIVE`, `active_embargo`
   changes from A to B):
    - If B ends **no later than** A, every signatory to A is carried over as a
      signatory to B: B is added to their `accepted_embargo_ids` and their
      state is unchanged.  Nobody lapses.  Their consent to A already covers B.
    - If B ends **later than** A, every `SIGNATORY` whose list lacks B moves to
      `LAPSED` via the `REVISE` trigger.  Those who accepted B stay
      `SIGNATORY`.
    - In either arm, a participant in any other state (`INVITED`, `UNBOUND`,
      `LAPSED`) whose list already contains B moves to `SIGNATORY` via
      `ACCEPT`: it has accepted the embargo now in force.
    - Only signatories to A are carried over.  A participant already `LAPSED`
      when B activates stays `LAPSED` until re-invited or until it accepts B;
      a participant `INVITED` to A whose invitation B has made stale is handled
      by the stale-terms re-invite path (reference spec §9.4, EMB-17).

    The cascade runs in `STRICT` and `OBSERVED` modes alike, as the termination
    reset does.
5. **Owner rejection of B (EJ) touches no one's consent.**  EM returns to
   `ACTIVE` under A; no participant's state or list changes — the owner's
   included.

`LAPSED` therefore means: *was a signatory to the previous active embargo; the
active embargo was replaced by longer terms this participant has not accepted.*
The PEC transition table is unchanged — `REVISE` is still valid only from
`SIGNATORY`, and `SIGNATORY → INVITED` remains invalid (CM-18-004).  Only the
moment the trigger fires moves, from the proposal to the owner's activation.

The `LAPSED → DECLINED` timer path (formerly in CM-18-002) is removed.  Nothing
stalls on a lapsed participant — they are already excluded from embargoed
content by the gate — there is no invitation to derive a deadline from, and
re-inviting them (`LAPSED → INVITED`) gives them a deadline through `INVITED`.

### `SIGNATORY → DECLINED` is withdrawal from the *active* embargo

The transition this ADR added stands, with a narrower trigger condition.  A
signatory reaches `DECLINED` by rejecting the **active** embargo — the
`Reject(Invite(EmbargoEvent))` names the embargo currently in force.  That is
consent withdrawal (VP-13-007, VP-13-008).  Rejecting a *proposed* revision is
not withdrawal and does not apply `DECLINE` to a signatory (point 3 above).

Option 1 was rejected: it would add an EM lifecycle step to the reject handler
solely to route through `LAPSED`, and under the revised lapse timing there is
no cascade on the proposal path for the reject handler to mirror.

Option 3 was rejected: the state is reachable in practice, and even if it
were not, the model should be correct rather than relying on a timing invariant
that is not enforced.

### Consequences

- Good, because a `SIGNATORY` rejecting the active embargo now correctly
  reaches `DECLINED` on both trigger and received paths
- Good, because a rejected revision strands nobody, `embargo_adherence` agrees
  with the content gate throughout `REVISE`, and the scalar state and
  `accepted_embargo_ids` agree about who is a signatory to the active embargo
- Good, because VP-13-007 and VP-13-008 (communicate intent to terminate
  compliance) become expressible at the PEC level without a workaround
- Good, because the received-side reject tree requires no EM lifecycle step —
  a single `DECLINE` trigger suffices
- Good, because `LAPSED` retains a precise meaning: automatic, set when the
  active embargo is replaced by longer terms the participant has not accepted,
  never a refusal and never a proposal-time state
- Bad, because a `SIGNATORY` can now reach `DECLINED` without passing through
  `LAPSED`; code that assumes "SIGNATORY can only leave via LAPSED" must be
  re-checked.  No such code was found in the sweep at the time of writing.
- Bad, because on the shorter-revision arm an embargo id enters a participant's
  `accepted_embargo_ids` without an explicit Accept from them.  Implied consent
  has precedent — the reporter is seeded `SIGNATORY` at creation (CM-14-005)
  and submitting a report while a proposal is pending is acceptance
  (VP-06-007) — but CM-10-001's "explicitly accepted" now reads as "accepted,
  explicitly or by containment"
- Bad, because the reject operation must know which embargo the Reject names
  relative to the active one.  A Reject naming an embargo that is neither
  active nor proposed on the case is a protocol error, not a consent change

## Validation

- Unit tests asserting `DECLINE` succeeds from `SIGNATORY` → `DECLINED`
- `test_reject_from_signatory_is_refused_not_applied` renamed to
  `test_reject_from_signatory_transitions_to_declined` and updated to assert
  the invitee reaches `PEC.DECLINED`
- A new test for the trigger-side path: `SIGNATORY` calling
  `EmbargoLifecycle.reject_embargo_invite()` on the **active** embargo
  transitions to `DECLINED`; the same call naming a *proposed* revision leaves
  the signatory unchanged
- `propose_embargo()` from `ACTIVE` reports no participant changes and adds
  the proposed id to the proposer's `accepted_embargo_ids`
- Owner acceptance of a revision that ends no later than the active embargo
  carries every signatory over; one that ends later lapses exactly the
  signatories whose list lacks it; owner rejection of a revision changes no
  participant record
- An end-to-end `ACTIVE → REVISE → ACTIVE` test by acceptance (shorter and
  longer) and by rejection, asserting every participant's consent state and
  `accepted_embargo_ids` after each step
- `grep` sweep over `apply_pec_transition(PEC_Trigger.DECLINE)` and
  `apply_pec_transition(PEC_Trigger.REVISE)` call sites to confirm no caller
  assumes `SIGNATORY` cannot reach `DECLINED` directly

## More Information

- Concern: #3142 (filed from learning entry `20260902-2762-reject-from-signatory-pec-gap.md`)
- Revised by Concern #3884 (2026-09-29): lapse timing moved from proposal to
  activation of longer terms; `SIGNATORY → DECLINED` narrowed to rejection of
  the active embargo.  Amends CM-18-001, CM-18-002, CM-18-003, CM-18-004,
  MSM-07-003, MSM-07-004, MSM-07-005, MSM-07-007, EP-05-001 and EP-05-002;
  CM-10-001 and CM-10-003 now read "accepted, explicitly or by containment".
  Blocks #3836 and #3863.
- Parent epic: #3125 (Embargo lifecycle protocol correctness)
- Related: ADR-0048 (PEC `NO_EMBARGO` means absence of embargo),
  ADR-0091 (rename `PEC.NO_EMBARGO` to `UNBOUND`)
- Open question: whether `UNBOUND` and `DECLINED` should collapse into one state
  (both mean "not bound by any embargo terms"; they differ only in provenance).
  See `docs/reference/vultron-spec/_oq-pec-unbound-declined-collapse.md`.
- VP-13-007 / VP-13-008: the normative spec entries that motivate trigger-side
  consent withdrawal as a first-class protocol action
- Generated spec requirements: `specs/case-management.yaml` CM-18-001,
  CM-18-002, CM-18-003 (PEC transition table updated to include
  `SIGNATORY → DECLINED`; lapse timing), CM-18-004;
  `specs/message-semantics-mapping.yaml` MSM-07-003, MSM-07-004, MSM-07-005;
  `specs/embargo-policy.yaml` EP-05-001, EP-05-002
