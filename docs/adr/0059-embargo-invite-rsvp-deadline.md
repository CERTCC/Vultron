---
status: accepted-provisional
date: 2026-08-12
deciders: Vultron maintainers
consulted: Vultron maintainers
informed: Vultron contributors
---

# Carry the Embargo Invite RSVP Deadline on `Invite.end_time`

## Context and Problem Statement

An embargo invitation can sit unanswered indefinitely. The protocol has no
bounded commitment window, so a coordinator waiting on one non-responsive
invitee cannot tell whether the invite is still live, and coordination stalls
without anyone having decided anything.

A deadline mechanism is in fact already specified. CM-18-002 defines the
**pocket veto**: `INVITED → DECLINED` MAY be driven by timer expiry on "a
configurable policy window (default: 7 days)." That window is *receiver-local
and implicit* — nothing about it appears on the wire, so the two parties have
no shared instant at which the invite lapses. It is also entirely unimplemented:
`PEC_Trigger.DECLINE` is fired from exactly two sites
(`vultron/core/behaviors/embargo/announce_teardown_tree.py`,
`vultron/core/services/embargo_lifecycle.py`), both explicit-`Reject` paths. No
timer exists.

The question is therefore not "should invites expire" — that is settled — but
**where the deadline lives and who is authoritative about it**.

Source: IDEA-2066, under epic #2088 (Protocol vocabulary extension).

## Decision Drivers

- Both parties MUST be able to compute the same lapse instant, ideally without
  exchanging any additional message. An invitee who never responds is by
  definition the party least likely to send a notification.
- No new AS2 noun or verb should be required. Epic #2088 is vocabulary
  extension, not vocabulary invention.
- The existing pocket veto must be *reconciled*, not duplicated. Two parallel
  notions of "the invite timed out" would drift.
- A deadline is coercive if unbounded downward: an artificially short window
  weaponises the mechanism to exclude a participant who had no realistic
  chance to answer.
- Being liberal in what is accepted serves CVD outcomes. An invitee who answers
  late is still volunteering to coordinate; the protocol should not eject them.
- No scheduler or Sentinel runtime exists in production, so the design must not
  depend on one.

## Considered Options

- **Activity-level `Invite.end_time`** — use the AS2 field the activity already
  inherits, on the invitation itself.
- **Object-level RSVP field on `EmbargoEvent`** — add a new field (e.g.
  `rsvp_by`) to the embargo object carried as the invite's `object_`.
- **Receiver-local policy only** — implement CM-18-002 as written and put
  nothing on the wire.
- **A dedicated RSVP/expiry activity type** — a new message announcing the
  deadline separately from the invitation.

## Decision Outcome

Chosen option: **activity-level `Invite.end_time`**.

`as_Object.end_time` (`vultron/wire/as2/vocab/base/objects/base.py`) is
inherited by `as_Activity` and therefore by every Vultron activity, so the
field already exists and needs no extension. On an Activity, AS2 `end_time`
already means "this activity is valid until" — an RSVP-by deadline is the
idiomatic reading, not a repurposing.

Note that the embargo invitation is an **`as_Invite`**, not an `as_Offer`:
`em_propose_embargo_activity()` (`vultron/wire/as2/factories/embargo.py`)
returns `as_Invite`, and `InviteToEmbargoOnCasePattern`
(`vultron/wire/as2/extractor/_instances.py`) matches
`activity_=TAtype.INVITE, object_=AOtype.EVENT, context_=VULNERABILITY_CASE`.
IDEA-2066 was framed as `Offer.end_time`; the mechanism is unchanged but the
field is on the Invite. The generic semantic — activity-level `end_time` on a
response-soliciting activity means "respond by" — applies to both `Invite` and
`Offer`; only `Invite(EmbargoEvent)` is normatively enforced for now, because
it is the only place the domain currently has a timeout concept.

The decision has five parts:

1. **Field and meaning.** `Invite.end_time` is the RSVP-by deadline for the
   invitation. It is distinct from `Invite.object_.end_time`, which is the
   embargo's own expiry. When `Invite.end_time` is absent, the CM-18-002
   policy window applies, preserving current behaviour.

2. **Authority.** The wire value is authoritative when present; the local
   policy window is the fallback. The pocket veto is not a second mechanism —
   it is this mechanism with the deadline left implicit.

3. **Enforcement.** The CaseActor (`CVDRole.CASE_MANAGER`) enforces expiry, by
   lazy evaluation: lapse is derived from `(end_time, now)` whenever PEC state
   is read or an `Accept`/`Reject` is processed. This requires no scheduler.
   The `EmbargoTimerExpired` Sentinel (#1893) is an optional proactive
   accelerator, never a prerequisite.

4. **Late `Accept` is not refused.** If the accepted embargo is still
   compatible with the case's current embargo, the CaseActor honours it even
   after `end_time`. If it is incompatible, the CaseActor issues a **fresh
   invite carrying the current embargo** rather than rejecting: the late
   accepter has signalled willingness to engage, so the protocol keeps them and
   re-syncs their terms. If no current embargo exists (EM `EXITED` or `NONE`),
   the `Accept` is acknowledged as a no-op on embargo state and the actor's case
   participation MUST NOT be dropped — following the EMB-07-003 precedent for
   post-terminal messages.

5. **No new PEC state.** A lapsed invite records `DECLINED`, the same as an
   explicit refusal. Nothing branches on the difference: re-invite
   (`DECLINED → INVITED`), content gating, and meta-protocol delivery treat the
   two identically. The distinction is provenance, and the canonical ledger
   already carries it — a `Reject(Invite)` entry versus a CaseActor-authored
   lapse entry. Encoding it as state would put path history in the machine and
   re-expand the table ADR-0048 simplified.

Abuse mitigation: a minimum RSVP window is specified, and a receiver that gets
a sub-floor deadline **clamps it up to the floor** rather than rejecting the
invite. Clamping keeps both parties deterministic and makes a coercively short
deadline ineffective rather than fatal — rejecting outright would hand the
sender a way to get their own invite discarded.

### Consequences

- Good, because lapse becomes computable by both parties from a shared field,
  with no message exchange and no scheduler.
- Good, because no new AS2 noun or verb is introduced.
- Good, because CM-18-002's unimplemented timer gains a concrete, testable
  definition instead of remaining aspirational.
- Good, because the liberal late-`Accept` rule means a deadline never silently
  ejects a willing participant.
- Bad, because `end_time` now carries two distinct meanings one nesting level
  apart in the same JSON document (`Invite.end_time` = RSVP-by,
  `Invite.object_.end_time` = embargo expiry). This is the principal
  implementation hazard and is called out in CM-27 and in
  `notes/participant-embargo-consent.md`.
- Bad, because lazy evaluation means a lapse is recorded when someone next
  looks, not at the instant it occurs. Ledger entry ordering can therefore trail
  the deadline. Acceptable while the derived state is correct on read; the #1893
  Sentinel narrows the window if it is ever a problem.
- Neutral, because the minimum-window floor is a policy number chosen without
  operational data. It is configurable and expected to be tuned.

## Validation

- Spec conformance tests for CM-27, EP-07, and EMB-17.
- A test asserting `Invite.end_time` and `Invite.object_.end_time` are read
  independently and never conflated on a single invitation.
- A test that a sub-floor deadline is clamped, not rejected.
- A test that a late `Accept` with an incompatible embargo produces a fresh
  invite rather than a rejection, and that case participation survives.

This ADR is `accepted-provisional`: the direction is ratified, but nothing
implements it yet. Details — in particular the floor value and the exact
compatibility predicate for a late `Accept` — are expected to converge once the
implementation Tasks land. Revise this ADR in place if they do not hold.

## Pros and Cons of the Options

### Activity-level `Invite.end_time`

- Good, because the field already exists on every activity via `as_Object`.
- Good, because "activity valid until" is the idiomatic AS2 reading.
- Good, because re-invites work naturally: each `Invite` carries its own
  independent `end_time`, so a second invitation can set a different deadline
  with no ambiguity about which one applies.
- Bad, because it puts a second `end_time` meaning in the same payload as the
  embargo's own `end_time`.

### Object-level RSVP field on `EmbargoEvent`

- Good, because a distinct field name would eliminate the collision outright.
- Bad, because the deadline is a property of *this invitation*, not of the
  embargo. The same embargo can be offered to several actors with different
  deadlines, and to one actor twice.
- Bad, because it requires extending a Vultron object type — more work, and it
  writes invitation bookkeeping into the shared embargo object.
- Bad, because `EmbargoEvent.end_time` already exists and means embargo expiry,
  so the object would carry two deadline fields with subtly different jobs.

### Receiver-local policy only

- Good, because it requires no wire change at all.
- Bad, because the two parties cannot agree on when the invite lapsed, which is
  the actual coordination problem.
- Bad, because the inviter cannot communicate urgency, which is the operational
  need motivating IDEA-2066.

### A dedicated RSVP/expiry activity type

- Good, because it separates the two `end_time` meanings completely.
- Bad, because it invents a new message type for data that fits on the
  invitation itself.
- Bad, because it introduces a delivery-ordering problem: the deadline could
  arrive before or after the invitation it governs.

## More Information

- IDEA-2066 (source), epic #2088 (Protocol vocabulary extension).
- #1893 — `EmbargoTimerExpired` Sentinel, the optional proactive accelerator.
- ADR-0048 — PEC `NO_EMBARGO` is absence, not pre-consent; the precedent for
  simplifying the PEC table rather than adding states.
- ADR-0019 — the canonical ledger as the history mechanism, which is why lapse
  provenance lives there rather than in a PEC state.
- `notes/participant-embargo-consent.md` § "RSVP Deadlines on Embargo Invites".
- CS-13-001 through CS-13-005 govern UTC handling for all datetimes involved.
- Deferred from this decision: an explicit rescind mechanism
  (`Undo(Invite(EmbargoEvent))`). `as_Undo` already exists in the vocabulary
  (`vultron/wire/as2/vocab/base/objects/activities/transitive.py`), but adding a
  rescind verb to the message catalog, its pattern, extractor entry, and use
  case is a distinct design activity. Tracked as its own Idea under epic #2088.

Generated spec requirements: `case-management.yaml` CM-27,
`embargo-policy.yaml` EP-07, `em-behavior.yaml` EMB-17. CM-18-002 is amended to
reference CM-27 so the pocket veto and the explicit deadline remain one
mechanism.
