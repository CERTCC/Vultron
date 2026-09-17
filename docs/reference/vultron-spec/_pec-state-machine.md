## 9. Participant Embargo Consent (PEC) State Machine [N]

An embargo binds the participants who agreed to it. Embargo Management
([§7](index.md#7-embargo-management-em-state-machine-n)) records whether the case
has an embargo; it cannot record who has agreed, because that answer differs per
participant. Participant Embargo Consent records it.

The distinction has practical force. A participant invited to a case that already
has an active embargo has not yet agreed to anything, and the CASE_MANAGER must
not send it embargoed content until it has
([§9.7](index.md#97-gating-full-case-delivery)). A participant that declines is
still in the case and still receives the negotiation traffic
([§9.5](index.md#95-embargo-traffic-reaches-non-signatories)). Neither
position is expressible in the case-level embargo state.

Consent is per participant, but the CASE_MANAGER writes it: it is recorded on the
case, alongside the participant's other case state.

!!! note "Informative: provenance"
    The original protocol design had four state machines and no consent machine.
    This one emerged during implementation, when the case-level embargo state
    proved unable to distinguish "no embargo exists" from "this participant has
    not yet agreed". It is normative here, because correct embargo behavior cannot
    be specified without it.

### 9.1 States

Each participant has one consent state, recording its position on the case's current
embargo terms.

{% include-markdown "./includes/_pec-states-table.md" %}

{% include-markdown "../../topics/process_models/em/pec_state_machine_diagram.md" %}

!!! info "See also"
    - [Participant Embargo Consent](../../topics/process_models/em/participant-embargo-consent.md)

### 9.2 Transitions and Guards

Five triggers drive the machine. **Invite** extends an invitation, **accept** and
**decline** record the participant's answer, **revise** fires when the case
embargo enters Revised, and **reset** fires when it enters Exited.

| From | Trigger | To |
|---|---|---|
| Unbound | invite | Invited |
| Unbound | accept | Signatory |
| Unbound | decline | Declined |
| Invited | accept | Signatory |
| Invited | decline | Declined |
| Invited | deadline passes | Declined |
| Signatory | revise | Lapsed |
| Lapsed | invite | Invited |
| Lapsed | accept | Signatory |
| Lapsed | decline | Declined |
| Lapsed | deadline passes | Declined |
| Declined | invite | Invited |
| any state | reset | Unbound |

Equivalently, by trigger: invite is valid from Unbound, Lapsed and Declined;
accept and decline are each valid from Unbound, Invited and Lapsed; revise is
valid only from Signatory; reset is valid from any state.

Neither Lapsed nor Declined is terminal. A participant in either can be invited
again, which is what makes renegotiation possible.

!!! warning "Lapsed is not the deadline state"
    Lapsed is reached only from Signatory, and only by the revise trigger. It
    means the participant did agree, and the terms it agreed to have since
    changed.

    A participant that lets a deadline pass reaches **Declined**, not Lapsed —
    from Invited and from Lapsed alike. Both timer paths end in Declined.

### 9.3 What Unbound Means

Unbound means there is no embargo in scope for this participant. It does not
mean "has not yet agreed".

That reading matters because consent does not always arrive through an
invitation. A finder who opens a case for its own finding and sets its default
embargo was invited by nobody. A reporter's consent is expressed by submitting the
report. In both cases the participant is a signatory without any invitation having
been sent, and the case history MUST NOT record an invitation that did not happen.

Two consequences follow:

- Accept and decline are valid directly from Unbound. No invitation is
  required.
- The transition from Signatory to Invited MUST be rejected. Consent already
  given cannot be withdrawn by re-inviting the participant; if the terms change,
  the revise trigger lapses the consent instead.

Unbound is also the state every participant returns to when an embargo ends,
which is independent evidence for the absence reading: reset fires when the
embargo goes away, not when an answer is pending.

### 9.4 Deadlines and the Pocket Veto

An embargo invitation does not stay open indefinitely. A participant that neither
accepts nor declines before the deadline is recorded as having declined — the
**pocket veto**. Silence is treated as refusal rather than assent, because
proceeding on an unanswered invitation would mean asserting agreement the
participant never gave.

The deadline may be explicit or defaulted:

- An embargo invitation MAY carry its own `endTime`, giving an explicit
  respond-by instant. Where present, it is authoritative.
- Where absent, a configurable policy window applies. The default window is
  7 days.

The pocket veto is the implicit form of this one mechanism, not a second
mechanism alongside it.

!!! warning "One invitation carries two different end times"
    The invitation's `endTime` is the **respond-by** deadline for the invitee.
    The embargo event nested inside the invitation has its own `endTime`, which
    is when the **embargo** would expire. They sit one nesting level apart and
    mean different things.

    An implementation that reads the embargo's expiry as the RSVP deadline will
    hold invitations open for the entire embargo period. One that reads the RSVP
    deadline as the embargo expiry will tear down embargoes days after they were
    agreed.

**Enforcing the deadline.** The CASE_MANAGER enforces it. It does so lazily: when
it next handles the case, it compares the deadline against the current time. No
scheduler or timer service is required.

**A minimum window applies.** The CASE_MANAGER MUST enforce a minimum respond-by
window, by default 72 hours. Where an invitation carries a shorter deadline, the
CASE_MANAGER MUST extend the deadline to the minimum. It MUST NOT reject the
invitation for this reason: a too-short deadline is the proposer's error, and
refusing the invitation would penalize the invitee for it.

**A late acceptance is not refused.** The CASE_MANAGER MUST NOT refuse a late
accept on deadline grounds. Three cases apply. If the terms it accepts are still
current, the CASE_MANAGER records the consent. If the terms are stale, the
CASE_MANAGER sends a fresh invitation carrying the current terms. If no embargo
remains, the CASE_MANAGER records the accept as a no-op; the participant keeps its
place in the case either way.

**A lapse and a refusal reach the same state.** Both record Declined. The case
history distinguishes them — it holds the decline that was sent, or the absence of
any answer — but the consent machine does not, because nothing in the protocol
treats the two differently. Both can be invited again.

### 9.5 Embargo Traffic Reaches Non-Signatories

Embargo consent gates case **content**. It does not gate the negotiation about the
embargo itself.

The CASE_MANAGER MUST deliver embargo meta-protocol messages — invitations, the
accepts and rejects answering them, and terminations — to every participant,
including those at Declined and Lapsed. A participant cannot agree to revised
terms it was never told about, and one that declined the original terms may well
accept the revision.

Only case content — report details, fix status, sensitive notes — is gated on
Signatory status ([§9.7](index.md#97-gating-full-case-delivery)).

### 9.6 Embargo Adherence

Whether a participant is currently bound by the embargo is a single yes-or-no
question, and the protocol answers it from the consent state: a participant is
bound exactly when its consent state is Signatory.

This is a derived fact, not an independent one. An implementation MUST NOT record
adherence as a value that can be set separately from the consent state it
reports, because the two would then be able to disagree — and a case that reports
a participant as bound while its consent state says otherwise has no correct
reading.

A change of consent MUST be made by applying a consent trigger through the
transitions of [§9.2](index.md#92-transitions-and-guards), so that every change is
a valid one and is recorded as such.

!!! note "Informative: how the reference implementation does this"
    The reference implementation exposes adherence as a computed property derived
    from the stored consent state, so there is no separate field to fall out of
    step. Any mechanism with that property satisfies the requirement above.

### 9.7 Gating Full Case Delivery

Before the CASE_MANAGER delivers full case content
(`Announce(VulnerabilityCase)` carrying report details, vulnerability
description, and sensitive notes), **both** conditions MUST hold for the
recipient:

1. The participant is **admitted to the case** — its RM state is at least
   Received.
2. The participant is a **signatory to the active embargo**
   (`embargo_adherence = True`), **OR** there is no active embargo
   (`EM.NONE`).

!!! note "Recall: report management states"
    {% include-markdown "./includes/_rm-states-table.md" %}

    Full definitions are in [§6.1](index.md#61-states).

!!! warning "The gate is admission plus consent — not completed triage"
    It is tempting to read condition 1 as `RM.ACCEPTED`. That reading is wrong
    and self-defeating: an invitee is recorded at `RM.RECEIVED` on
    `Accept(Invite)`, and reaches `ACCEPTED` only *after* receiving the full case
    and running its triage cycle ([§6.3](index.md#63-per-participant-rm-tracking)). Requiring `ACCEPTED` before delivery
    would mean a participant could never obtain the case it needs in order to
    reach the state that gates it.

    **Embargo consent — not RM progress — is the substantive gate on case
    content.** The ordering is: admit the participant at `RM.RECEIVED`, resolve
    embargo consent, then deliver the full case.

This matters to [§10](index.md#10-model-interactions-and-cascade-rules-n)'s cascade ordering: `Accept(Invite)` implies consent
to any active embargo, which is what allows delivery to proceed immediately rather
than waiting on a separate consent round-trip.

---
