## 9. Participant Embargo Consent (PEC) State Machine [N]

An embargo binds the participants who agreed to it.
Embargo Management ([§7 Embargo Management (EM) State Machine](tracking-models.md#7-embargo-management-em-state-machine-n)) records whether the case has an embargo; it cannot record who has agreed, because that answer differs per participant.
Participant Embargo Consent records it.

The distinction has practical force.
A participant invited to a case that already has an active embargo has not yet agreed to anything, and the CASE_MANAGER must not send it embargoed content until it has ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)).
A participant that declines is still in the case and still receives the negotiation traffic ([§9.5 Embargo Traffic Reaches Non-Signatories](tracking-models.md#95-embargo-traffic-reaches-non-signatories)).
Neither position is expressible in the case-level embargo state.

Consent is per participant, but the CASE_MANAGER writes it: it is recorded on the participant's record in the case, alongside the participant's other case state.

!!! note "Informative: provenance"
    The original protocol design had four state machines and no consent machine.
    This one emerged during implementation, when the case-level embargo state proved unable to distinguish "no embargo exists" from "this participant has not yet agreed".
    It is normative here, because correct embargo behavior cannot be specified without it.

### 9.1 States

Consent is given to specific terms, so a participant has one **consent row** for every entry in the case's embargo register ([§7 Embargo Management (EM) State Machine](tracking-models.md#7-embargo-management-em-state-machine-n)), and each row holds one of the five states below (CM-18-001).
A row answers one question: what has this participant said about this one embargo?
A participant can therefore be bound by the embargo in force and have already agreed to a proposed revision of it, on two different rows.

{% include-markdown "./includes/_pec-states-table.md" %}

Every row is written.
Proposing an embargo writes an `UNINVITED` row for it on every current participant, and creating a participant record writes an `UNINVITED` row for every entry already in the register (CM-18-001).
No state is read from a missing row: a missing row is a defect, and reading one raises.
A participant that joins late stays `UNINVITED` on embargoes that are no longer in force; it is invited only to the embargo in force and to open revisions (CM-11-006, EP-09-011).

`UNINVITED` and `DECLINED` both leave the participant unbound by the embargo the row answers, but they are distinct states, because whether the participant gave an answer matters.
The lapsed read stops at a `DECLINED` row and passes over an `UNINVITED` one ([§9.3 Signatory and Lapsed](tracking-models.md#93-signatory-and-lapsed)), and an open proposal is relayed to a joiner only while its row for that proposal is `UNINVITED` (CM-18-001, EP-09-011).

`INVITED` carries the invitation's respond-by deadline, the **RSVP deadline**, on the row itself (CM-28-013).
The deadline belongs to one invitation, so a participant can hold several `INVITED` rows with different deadlines, and one passing times out only its own row.

{% include-markdown "../../topics/process_models/em/pec_state_machine_diagram.md" %}

!!! info "See also"
    - [Embargo Lifecycle](../../topics/behavior_logic/use-cases/embargo-lifecycle.md)

### 9.2 Transitions and Guards

Five triggers drive each row (CM-18-003).
**INVITE** records an invitation, **AGREE** and **DECLINE** record an answer, **TIME_OUT** fires when an invitation's RSVP deadline passes unanswered, and **CARRY_OVER** agrees for a participant when the case owner activates a revision that asks nothing new of it.

| Trigger | From | To |
|---|---|---|
| `INVITE` | `UNINVITED`, `DECLINED`, `TIMED_OUT` | `INVITED` |
| `AGREE` | `UNINVITED`, `INVITED`, `DECLINED`, `TIMED_OUT` | `AGREED` |
| `DECLINE` | `UNINVITED`, `INVITED`, `AGREED`, `TIMED_OUT` | `DECLINED` |
| `TIME_OUT` | `INVITED` | `TIMED_OUT` |
| `CARRY_OVER` | every state except `AGREED` | `AGREED` |

No other trigger is valid from any state, and an implementation rejects one as a protocol error (CM-18-009).
A row for an embargo whose register entry is final (`REJECTED`, `SUPERSEDED`, `CANCELLED` or `TERMINATED`) accepts no trigger at all, so the consent given to an embargo that is no longer in play is frozen as it stood (CM-18-003).

`AGREED` refuses `INVITE`.
Consent already given is not undone by asking again (CM-18-004).
A participant whose terms have since changed is invited on its row for the new embargo, which leaves its `AGREED` row for the old one alone.

`AGREE` and `DECLINE` are valid directly from `UNINVITED`.
Consent does not always arrive through an invitation: a finder that opens a case for its own finding and sets its default embargo was invited by nobody, and a reporter consents by reporting.
The case history MUST NOT record an invitation that did not happen (ADR-0048).

A repeated answer is not a transition.
When a participant sends the same answer to the same invitation again, the CASE_MANAGER changes nothing, records nothing in the case ledger and sends nothing, whatever the repeat's activity id (CM-13-005).
A different answer is a new answer, and the table above applies to it.
A participant that declined and then agrees has changed its answer, so its row moves to `AGREED` directly, without being invited again.

None of `DECLINED`, `TIMED_OUT` and `AGREED` is terminal.
A `DECLINED` or `TIMED_OUT` row can be invited again, which is what makes renegotiation possible, and an `AGREED` row can be declined.
What ends a row's life is its register entry reaching a final status, not any state of the row.

### 9.3 Signatory and Lapsed

Two positions a participant can hold are not states.
Each is a read of the participant's rows and the case's register, and neither is stored or drawn on the state machine (CM-18-001).

| Read | Definition |
|---|---|
| **Signatory** | The participant's row for the register's `ACTIVE` entry is `AGREED`. |
| **Lapsed** | An entry is `ACTIVE`, the participant's row for it is neither `AGREED` nor `DECLINED`, and, following `replaces` back from the `ACTIVE` entry, the first entry whose row is `AGREED` or `DECLINED` has an `AGREED` row. |

With no `ACTIVE` entry nobody is a signatory and nobody has lapsed.
After an embargo is terminated no entry is `ACTIVE`, so the termination writes no row: every participant's position follows from the register alone (CM-18-016, MSM-07-006).
Abandoning an open proposal once the case is public, an exploit is public or attacks are observed writes no row either (EMB-16-001).
The CASE_MANAGER cancels the proposal with its `Reject` of the proposal it received, or its `Undo` of one it made itself, and then withdraws each invitation it relayed for the proposal with an `Undo`.
Each row for the canceled proposal is frozen as it stood.
The CASE_MANAGER's `Reject` is its abandonment, not its consent, so a CASE_MANAGER that has a stake in an embargo records its own answer as its own update of the row and never as a `Reject` (MSM-07-004).

A participant lapses when the case owner activates a revision that ends later than the embargo the participant agreed to, and the participant has not agreed to the revision.
It did agree, and the embargo in force has since become something it did not agree to.
Only the embargoes that were once in force sit on the `replaces` chain, so agreeing to a proposal that never took effect binds nothing to lapse from.
A participant that withdrew from a later embargo has a `DECLINED` row on the chain, and has not lapsed when a further revision replaces that one.

!!! warning "Lapsed is neither the proposal state nor the deadline state"
    A merely proposed revision lapses nobody, and neither does a revision that ends no later than the accepted terms.
    A participant that lets an invitation deadline pass reaches `TIMED_OUT` on that invitation's row, not lapsed.
    A lapse is not timer-based and has no transition of its own: a lapsed participant is re-invited, on an `INVITED` row for the embargo in force, and the deadline attaches to that invitation (CM-18-002).

A revision does not move anyone's consent to the embargo in force until it takes effect (EP-05-002).
While a revision is only proposed, the prior embargo is in force and every signatory to it remains one.
The proposer's row for the revision is `AGREED`, because proposing terms is consenting to them, and every other participant gets an `UNINVITED` row for it.
A signatory that agrees to the revision records that on the revision's row, and one that declines it refuses those terms and nothing more, on that row only (MSM-07-003, MSM-07-004).

A signatory withdraws by leaving the embargo in force with `Leave(EmbargoEvent)`, not by rejecting an invitation to it (MSM-07-010).
The withdrawal declines its row for the embargo in force and every open proposal's row it had agreed to, because every open proposal is a revision of the embargo it is leaving.
A `Reject` of the active embargo from an `AGREED` row is refused with a reported reason (MSM-07-004).
The case owner does not leave an embargo; it ends one by terminating it.

Only the case owner's decision changes the embargo on the case; the other participants' answers inform it (EP-09-005).
When the owner activates a revision, the direction of the change decides what happens to the consent of the signatories to the old terms (EP-05-001, MSM-07-005):

- A revision that ends **no later than** the terms it replaces asks nothing new of anyone who agreed to the old terms, since agreeing to N days is agreeing to every shorter period.
  The CASE_MANAGER applies `CARRY_OVER` to the revision's row of every participant whose row for the replaced embargo is `AGREED`, a `DECLINED` row for the revision included.
- A revision that ends **later** asks for more than they promised.
  No row is written: a signatory to the old terms whose row for the revision is not `AGREED` has lapsed, by the definition above.

Either way, a participant already holding an `AGREED` row for the revision is its signatory by lookup, whether it is the proposer or an early acceptor.
Only signatories to the old terms are carried over.
A participant that had lapsed from an earlier embargo stays lapsed until it is re-invited or agrees.
An `INVITED` participant whose invitation the activation has made stale is re-invited to the current terms, as in [§9.4 Deadlines and the Pocket Veto](tracking-models.md#94-deadlines-and-the-pocket-veto) (EMB-17-003).
If the owner rejects the revision instead, the old terms stand and nobody's consent changes (MSM-07-009).

### 9.4 Deadlines and the Pocket Veto

An embargo invitation does not stay open indefinitely.
A participant that neither agrees nor declines before the RSVP deadline has its row for that invitation moved to `TIMED_OUT`, the **pocket veto** (CM-18-002).
Silence is not treated as assent, because proceeding on an unanswered invitation would mean asserting agreement the participant never gave.
Nor is it recorded as a refusal: `DECLINED` is reached only by an explicit refusal (CM-28-004).

The deadline may be explicit or defaulted:

- An embargo invitation MAY carry its own `endTime`, giving an explicit respond-by instant.
  Where present, it takes precedence over the policy window (CM-28-001, CM-28-002).
- Where absent, a configurable policy window applies.
  The default window is 7 days.

Either way the result is bounded below and above by the two rules further down this section: the explicit `endTime` takes precedence over the policy window, but neither escapes the minimum window or the embargo-end ceiling.
The pocket veto is the implicit form of this one mechanism, not a second mechanism alongside it.

!!! warning "One invitation carries two different end times"
    The invitation's `endTime` is the **respond-by** deadline for the invitee.
    The embargo event nested inside the invitation has its own `endTime`, which is when the **embargo** would expire.
    They sit one nesting level apart and mean different things.

    An implementation that reads the embargo's expiry as the RSVP deadline will hold invitations open for the entire embargo period.
    One that reads the RSVP deadline as the embargo expiry will tear down embargoes days after they were agreed.

**Recording the deadline.**
When the CASE_MANAGER relays an invitation, it sets the Invite's `endTime` and records the deadline on the invitee's `INVITED` row for the invited embargo (CM-28-012, CM-28-013).
Every replica records the same deadline by copying the CASE_MANAGER's ledger entry for that row.
A participant does not derive or store a deadline on receipt of an Invite.

**Enforcing the deadline.**
The CASE_MANAGER enforces it, and only the CASE_MANAGER (CM-28-003, CM-28-014).
It does so lazily: when it next handles the case, it compares each deadline against its own clock, so no scheduler or timer service is required (CM-28-007, CM-28-008).
Before it commits the case owner's decision on a proposal, whenever it processes any other received embargo activity for the case, and whenever it runs an embargo trigger of its own, it expires every `INVITED` row whose deadline has passed and whose embargo is an open proposal or the embargo in force (CM-28-015).
A row of a replaced, rejected, canceled or ended embargo is frozen and is not swept.
The sweep runs after the activity's sender has been admitted and before the activity's own refusals, so an expiry is recorded even when the activity is then refused.

**A minimum window applies.**
The CASE_MANAGER MUST enforce a minimum respond-by window.
The minimum is the lesser of a configured window, 72 hours by default, and the time remaining in the embargo the invitation concerns (EP-07-002).
Where an invitation carries a shorter deadline, the CASE_MANAGER MUST extend the deadline to that minimum.
It MUST NOT reject the invitation for this reason: a too-short deadline is the proposer's error, and refusing the invitation would penalize the invitee for it.

**A deadline may not outlive its embargo.**
The CASE_MANAGER MUST NOT let a respond-by deadline fall after the end of the embargo it concerns (CM-28-011).
Where a computed deadline would, whether it came from the invitation's explicit `endTime` or from the policy window, the CASE_MANAGER MUST clamp it down to the embargo's end.

An invitee must be able to answer while there is still something to answer about.
Invite a participant to a 24-hour embargo with no explicit `endTime` and a 7-day policy window, and its inaction would be recorded as a time-out on day 7, six days after the embargo ended.
This is why the minimum window above is relative rather than absolute: a 12-hour embargo grants a 12-hour answer window, and that is not an unreasonably short deadline when 12 hours is the whole embargo.

**A late acceptance is not refused.**
The CASE_MANAGER MUST NOT refuse a late accept on deadline grounds (EMB-17-001).
Three cases apply:

- If the terms it accepts are the case's current embargo, the CASE_MANAGER records the accept exactly as an on-time accept: its entry is the accept itself, and a `TIMED_OUT` or `DECLINED` row moves to `AGREED` directly (EMB-17-002).
- If the terms are stale, the CASE_MANAGER relays a fresh invitation carrying the current terms, on behalf of their proposer (EMB-17-003).
- If no embargo remains, the accept changes nothing: the CASE_MANAGER records no entry, sends no reply and leaves the rows unchanged; the participant keeps its place in the case either way (EMB-17-004, EMB-17-008).

**A time-out and a refusal reach different states.**
Silence records `TIMED_OUT`; an explicit refusal records `DECLINED`.
The case ledger distinguishes them too, holding either the refusal that was sent or the CASE_MANAGER's record of the expiry (CM-28-005, CM-28-009), but every reader of the consent rows can tell them apart without consulting it.
Both can be invited again, and both move to `AGREED` directly on a late accept of the current terms.

### 9.5 Embargo Traffic Reaches Non-Signatories

Embargo consent gates case **content**.
It does not gate the negotiation about the embargo itself.

The CASE_MANAGER MUST deliver embargo meta-protocol activities addressed to a participant directly (an embargo `Invite` and its responses) to that participant even when it declined, timed out or lapsed; they are not ledger fan-out, which the content gate holds back from non-signatories (CM-10-005).
A participant cannot agree to revised terms it was never told about, and one that declined the original terms may well accept the revision.

Only case content (report details, fix status, sensitive notes) is gated on being a signatory ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)).

### 9.6 Embargo Adherence

Whether a participant is currently bound by the embargo is a single yes-or-no question, and the protocol answers it from the consent rows: a participant is bound exactly when it is a signatory, that is, when its row for the register's `ACTIVE` entry is `AGREED` (CM-18-001).

This is a derived fact, not an independent one.
An implementation MUST NOT record adherence as a value that can be set separately from the rows it reports, because the two would then be able to disagree, and a case that reports a participant as bound while its rows say otherwise has no correct reading.

A change of consent MUST be made either by applying a consent trigger through the transitions of [§9.2 Transitions and Guards](tracking-models.md#92-transitions-and-guards), or by copying the row a ledger entry carries after checking its starting state, through the one apply function the CASE_MANAGER and every replica share, so that every change is a valid one and is recorded as such (CM-18-005).
The CASE_MANAGER commits every consent row it changes as its own `Update(EmbargoConsent)` ledger entry, or `Create(EmbargoConsent)` for a row it brings into existence, after the entry of the act that caused it (CLP-07-013, EP-09-007).
Where the act's own activity states the row, such as a participant's `Accept(Invite(EmbargoEvent))` or, for the case owner's own row, its `Accept(EmbargoEvent, target=Case)` activating an embargo, that entry is the row's entry.

!!! note "Informative: how the reference implementation does this"
    The reference implementation exposes adherence as a computed lookup over the stored consent rows and the register, so there is no separate field to fall out of step.
    Any mechanism with that property satisfies the requirement above.

### 9.7 Gating Full Case Delivery

Before the CASE_MANAGER delivers full case content (`Announce(VulnerabilityCase)` carrying report details, vulnerability description, and sensitive notes), **both** conditions MUST hold for the recipient:

1. The participant is **admitted to the case**: its RM state is at least Received.
2. The participant is a **signatory to the active embargo** (its row for the active embargo is `AGREED`), **OR** no embargo is in force (EM is not `ACTIVE` or `REVISE`).

!!! note "Recall: report management states"
    {% include-markdown "./includes/_rm-states-table.md" %}

    Full definitions are in [§6.1 States](tracking-models.md#61-states).

!!! warning "The gate is admission plus consent — not completed triage"
    It is tempting to read condition 1 as `RM.ACCEPTED`.
    That reading is wrong and self-defeating: an invitee is at `RM.RECEIVED` from the stub Invite and stays there after `Accept(Invite)`, and reaches `ACCEPTED` only *after* receiving the full case and running its triage cycle ([§6.3 Per-Participant RM Tracking](tracking-models.md#63-per-participant-rm-tracking)).
    Requiring `ACCEPTED` before delivery would mean a participant could never obtain the case it needs in order to reach the state that gates it.

    **Embargo consent — not RM progress — is the substantive gate on case content.**
    The ordering is: admit the participant at `RM.RECEIVED`, resolve embargo consent, then deliver the full case.

This matters to [§10 Model Interactions and Cascade Rules](interactions.md#10-model-interactions-and-cascade-rules-n)'s cascade ordering: `Accept(Invite)` agrees to any active embargo on the joiner's row for it, which is what allows delivery to proceed immediately rather than waiting on a separate consent round-trip.
A joiner whose row for the active embargo is `DECLINED` stays declined, because joining is not an answer to the embargo.

---
