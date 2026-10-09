## 9. Participant Embargo Consent (PEC) State Machine [N]

An embargo binds the participants who agreed to it. Embargo Management
([§7 Embargo Management (EM) State Machine](tracking-models.md#7-embargo-management-em-state-machine-n)) records whether the case
has an embargo; it cannot record who has agreed, because that answer differs per
participant. Participant Embargo Consent records it.

The distinction has practical force. A participant invited to a case that already
has an active embargo has not yet agreed to anything, and the CASE_MANAGER must
not send it embargoed content until it has
([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)). A participant that declines is
still in the case and still receives the negotiation traffic
([§9.5 Embargo Traffic Reaches Non-Signatories](tracking-models.md#95-embargo-traffic-reaches-non-signatories)). Neither
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

Each participant's position on the case's current embargo terms is one of the states below.
Consent is given to specific terms, so an implementation records one consent row per participant and embargo (`INVITED`, `ACCEPTED`, `DECLINED`, `EXPIRED`) and derives the position from the rows and the embargo in force.
`SIGNATORY` is an accepted row for the active embargo, and `LAPSED` and `UNBOUND_EXITED` are read from the rows and the case rather than written (ADR-0122).
A participant can therefore be a signatory to the active embargo and have already accepted a proposed revision of it.

{% include-markdown "./includes/_pec-states-table.md" %}

{% include-markdown "../../topics/process_models/em/pec_state_machine_diagram.md" %}

!!! info "See also"
    - [Embargo Lifecycle](../../topics/behavior_logic/use-cases/embargo-lifecycle.md)

### 9.2 Transitions and Guards

Six triggers drive the machine.
**Invite** extends an invitation, **accept** and **decline** record the participant's answer, **revise** fires when the case owner activates revised terms that end later than the terms a signatory accepted, **expire** fires when an invitation's deadline passes unanswered, and **exit** fires when the embargo enters Exited.

| From | Trigger | To |
|---|---|---|
| Unbound | invite | Invited |
| Unbound | accept | Signatory |
| Unbound | decline | Declined |
| Invited | accept | Signatory |
| Invited | decline | Declined |
| Invited | expire (deadline passes) | Expired |
| Signatory | revise | Lapsed |
| Signatory | decline | Declined |
| Lapsed | invite | Invited |
| Lapsed | accept | Signatory |
| Lapsed | decline | Declined |
| Declined | invite | Invited |
| Expired | invite | Invited |
| Expired | accept | Signatory |
| Expired | decline | Declined |
| any state but Unbound (exited) | exit | Unbound (exited) |

Equivalently, by trigger: invite is valid from Unbound, Lapsed, Declined and Expired; accept is valid from Unbound, Invited, Lapsed and Expired; decline is valid from Unbound, Invited, Lapsed, Signatory and Expired; revise is valid only from Signatory; expire is valid only from Invited; exit is valid from every state except Unbound (exited).

None of Lapsed, Declined and Expired is terminal.
A participant in any of them can be invited again, which is what makes renegotiation possible.
Unbound (exited) is terminal and accepts no trigger: an embargo that has entered Exited has no outgoing transition, so a participant whose embargo was terminated cannot be invited back into it.

A revision does not move a signatory until it takes effect.
While a revision is only proposed, the prior embargo is still in force and every signatory to it remains Signatory; the proposer is recorded as having accepted the terms it proposed.
A signatory that accepts the proposed terms records that acceptance and stays Signatory to the embargo in force.
A signatory that declines the proposed terms refuses them and nothing more: it stays Signatory, because only declining the **active** embargo is withdrawal.
Only the case owner's accept or reject changes the embargo on the case; the other participants' answers inform that decision.

When the owner activates the revision, consent is re-evaluated against the new terms, and the direction of the change matters.
A revision that ends **no later than** the terms it replaces asks nothing new of anyone who agreed to the old terms, since agreeing to N days is agreeing to every shorter period; every signatory is carried over as a signatory to the new terms.
A revision that ends **later** asks for more than they promised; every signatory that has not accepted it moves to Lapsed by the revise trigger, and those that did accept it stay Signatory.
In either case a participant in any other state that had already accepted the revision becomes Signatory to it, because it has accepted the embargo now in force.
Only signatories to the old terms are carried over: a participant already Lapsed stays Lapsed until it is invited again or accepts, and an Invited participant whose invitation the activation has made stale is handled as in [§9.4 Deadlines and the Pocket Veto](tracking-models.md#94-deadlines-and-the-pocket-veto).
If the owner rejects the revision instead, the old terms stand and nobody's consent changes.

!!! warning "Lapsed is neither the proposal state nor the deadline state"
    Lapsed is reached only from Signatory, and only by the revise trigger.
    That trigger fires when the case owner *activates* longer terms the participant has not accepted, never when a revision is merely proposed and never when the revision ends no later than the accepted terms.
    It means the participant did agree, and the embargo in force has since become something it did not agree to.

    A participant that lets an invitation deadline pass reaches **Expired**, not Lapsed.
    A Lapsed participant has no deadline until it is invited again.

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
- The transition from Signatory to Invited MUST be rejected.
  Consent already given cannot be withdrawn by re-inviting the participant; if longer terms the participant has not accepted take effect, the revise trigger lapses the consent instead.

Unbound is the initial state only.
When an embargo ends, every participant moves to the terminal Unbound (exited) instead: Unbound can be invited and a terminated embargo cannot be renegotiated, so the two must be different states.

### 9.4 Deadlines and the Pocket Veto

An embargo invitation does not stay open indefinitely.
A participant that neither accepts nor declines before the deadline is recorded as Expired — the **pocket veto**.
Silence is not treated as assent, because proceeding on an unanswered invitation would mean asserting agreement the participant never gave.
Nor is it recorded as a refusal: Declined is reached only by an explicit decline.

The deadline may be explicit or defaulted:

- An embargo invitation MAY carry its own `endTime`, giving an explicit
  respond-by instant. Where present, it takes precedence over the policy window.
- Where absent, a configurable policy window applies. The default window is
  7 days.

Either way the result is bounded below and above by the two rules further down
this section: the explicit `endTime` takes precedence over the policy window, but
neither escapes the minimum window or the embargo-end ceiling.

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
window. The minimum is the lesser of a configured window, 72 hours by default, and
the time remaining in the embargo the invitation concerns. Where an invitation
carries a shorter deadline, the CASE_MANAGER MUST extend the deadline to that
minimum. It MUST NOT reject the invitation for this reason: a too-short deadline is
the proposer's error, and refusing the invitation would penalize the invitee for it.

**A deadline may not outlive its embargo.** The CASE_MANAGER MUST NOT let a
respond-by deadline fall after the end of the embargo it concerns. Where a computed
deadline would — whether it came from the invitation's explicit `endTime` or from
the policy window — the CASE_MANAGER MUST clamp it down to the embargo's end.

An invitee must be able to answer while there is still something to answer about.
Invite a participant to a 24-hour embargo with no explicit `endTime` and a 7-day policy window records their inaction as an expiry on day 7 — six days after the embargo ended.
This is why the minimum window above is relative rather than absolute: a 12-hour embargo grants a 12-hour answer window, and that is not an unreasonably short deadline when 12 hours is the whole embargo.

**A late acceptance is not refused.** The CASE_MANAGER MUST NOT refuse a late accept on deadline grounds.
Three cases apply.
If the terms it accepts are still current, the CASE_MANAGER records the consent: an Expired participant becomes Signatory directly, and a Declined one is invited again first, because accept is not valid from Declined.
If the terms are stale, the CASE_MANAGER sends a fresh invitation carrying the current terms.
If no embargo remains, the CASE_MANAGER records the accept as a no-op; the participant keeps its place in the case either way.

**An expiry and a refusal reach different states.** Silence records Expired; an explicit decline records Declined.
The case history distinguishes them too — it holds the decline that was sent, or the CASE_MANAGER's record of the expiry — but every reader of the consent state can tell them apart without consulting it.
Both can be invited again; only Expired accepts a late accept directly.

### 9.5 Embargo Traffic Reaches Non-Signatories

Embargo consent gates case **content**. It does not gate the negotiation about the
embargo itself.

The CASE_MANAGER MUST deliver embargo meta-protocol messages — invitations, the accepts and rejects answering them, and terminations — to every participant, including those at Declined, Expired and Lapsed.
A participant cannot agree to revised terms it was never told about, and one that declined the original terms may well accept the revision.

Only case content — report details, fix status, sensitive notes — is gated on
Signatory status ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)).

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
transitions of [§9.2 Transitions and Guards](tracking-models.md#92-transitions-and-guards), so that every change is
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
   (an accepted consent row for the active embargo), **OR** there is no active embargo
   (`EM.NONE`).

!!! note "Recall: report management states"
    {% include-markdown "./includes/_rm-states-table.md" %}

    Full definitions are in [§6.1 States](tracking-models.md#61-states).

!!! warning "The gate is admission plus consent — not completed triage"
    It is tempting to read condition 1 as `RM.ACCEPTED`. That reading is wrong
    and self-defeating: an invitee is at `RM.RECEIVED` from the stub
    Invite and stays there after `Accept(Invite)`, and reaches `ACCEPTED` only *after* receiving the full case
    and running its triage cycle ([§6.3 Per-Participant RM Tracking](tracking-models.md#63-per-participant-rm-tracking)). Requiring `ACCEPTED` before delivery
    would mean a participant could never obtain the case it needs in order to
    reach the state that gates it.

    **Embargo consent — not RM progress — is the substantive gate on case
    content.** The ordering is: admit the participant at `RM.RECEIVED`, resolve
    embargo consent, then deliver the full case.

This matters to [§10 Model Interactions and Cascade Rules](interactions.md#10-model-interactions-and-cascade-rules-n)'s cascade ordering: `Accept(Invite)` implies consent
to any active embargo, which is what allows delivery to proceed immediately rather
than waiting on a separate consent round-trip.

---
