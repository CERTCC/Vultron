## 9. Participant Embargo Consent (PEC) State Machine [N]

An embargo binds the participants who agreed to it.
Embargo Management ([§7 Embargo Management (EM) State Machine](tracking-models.md#7-embargo-management-em-state-machine-n)) records whether the case has an embargo.
It cannot record who has agreed, because that answer differs per participant.
Participant Embargo Consent records it.

This distinction has practical consequences.
A participant invited to a case that already has an active embargo has not yet agreed to anything.
The CASE_MANAGER does not send that participant embargoed content until the participant agrees ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)).
A participant that declines is still in the case and still receives the negotiation traffic ([§9.5 Embargo Traffic Reaches Non-Signatories](tracking-models.md#95-embargo-traffic-reaches-non-signatories)).
The case-level embargo state cannot express either position.

Consent is per participant, but the CASE_MANAGER writes it.
The CASE_MANAGER records consent on the participant's record in the case, next to the participant's other case state.

!!! note "Informative: provenance"
    The original protocol design had four state machines and no consent machine.
    This machine emerged during implementation, when the case-level embargo state could not distinguish "no embargo exists" from "this participant has not yet agreed".
    This machine is normative here, because correct embargo behavior cannot be specified without it.

### 9.1 States

Consent applies to specific terms.
A participant therefore has one **consent row** for every entry in the case's embargo register ([§7 Embargo Management (EM) State Machine](tracking-models.md#7-embargo-management-em-state-machine-n)), and each row holds one of the five states below.
A row answers one question: what has this participant said about this one embargo?
A participant can therefore be bound by the embargo in force and have already agreed to a proposed revision of it, on two different rows.

{% include-markdown "./includes/_pec-states-table.md" %}

Every row is written.
Proposing an embargo writes an `UNINVITED` row for it on every current participant.
Creating a participant record writes an `UNINVITED` row for every entry already in the register.
No state is read from a missing row.
A missing row is a defect, and an attempt to read one raises an error.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-18-001", "CM-10-001"))
```

A participant that joins late stays `UNINVITED` on embargoes that are no longer in force.
That participant is invited only to the embargo in force and to open revisions.

`UNINVITED` and `DECLINED` both leave the participant unbound by the embargo that the row answers.
They are distinct states, because it matters whether the participant gave an answer.
The lapsed read stops at a `DECLINED` row and passes over an `UNINVITED` row ([§9.3 Signatory and Lapsed](tracking-models.md#93-signatory-and-lapsed)).
The CASE_MANAGER relays an open proposal to a joiner only while the joiner's row for that proposal is `UNINVITED`.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-006", "EP-09-011"))
```

`INVITED` carries the invitation's respond-by deadline, the **RSVP deadline**, on the row itself ([§9.4 Deadlines and the Pocket Veto](tracking-models.md#94-deadlines-and-the-pocket-veto)).
Each deadline belongs to one invitation.
A participant can therefore hold several `INVITED` rows with different deadlines.
When one deadline passes, it times out only its own row.

{% include-markdown "../../topics/process_models/em/pec_state_machine_diagram.md" %}

!!! info "See also"
    - [Embargo Lifecycle](../../topics/behavior_logic/use-cases/embargo-lifecycle.md)

### 9.2 Transitions and Guards

Five triggers drive each row.
**INVITE** records an invitation.
**AGREE** and **DECLINE** record an answer.
**TIME_OUT** fires when the RSVP deadline of an invitation passes with no answer.
**CARRY_OVER** agrees for a participant when the case owner activates a revision that asks nothing new of that participant.

| Trigger | From | To |
|---|---|---|
| `INVITE` | `UNINVITED`, `DECLINED`, `TIMED_OUT` | `INVITED` |
| `AGREE` | `UNINVITED`, `INVITED`, `DECLINED`, `TIMED_OUT` | `AGREED` |
| `DECLINE` | `UNINVITED`, `INVITED`, `AGREED`, `TIMED_OUT` | `DECLINED` |
| `TIME_OUT` | `INVITED` | `TIMED_OUT` |
| `CARRY_OVER` | every state except `AGREED` | `AGREED` |

No other trigger is valid from any state.
A row for an embargo whose register entry is final (`REJECTED`, `SUPERSEDED`, `CANCELLED` or `TERMINATED`) accepts no trigger.
The consent given to an embargo that is no longer in play therefore stays frozen as it stood.

`AGREED` refuses `INVITE`.
A new request does not undo consent that a participant already gave.
If the terms change after a participant agrees, that participant is invited on its row for the new embargo.
This invitation leaves its `AGREED` row for the old embargo unchanged.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-18-003", "CM-18-004"))
```

`AGREE` and `DECLINE` are valid directly from `UNINVITED`.
Consent does not always come through an invitation.
A finder that opens a case for its own finding and sets its default embargo received no invitation from anybody.
A reporter consents by reporting.
A required `INVITED` step on these paths would make the case history record an invitation that did not happen.

A repeated answer is not a transition.
When a participant sends the same answer to the same invitation again, the CASE_MANAGER changes nothing, records nothing in the case ledger and sends nothing, whatever activity id the repeat carries.
A different answer is a new answer, and the table above applies to it.
A participant that declined and then agrees has changed its answer, so its row moves directly to `AGREED`, with no new invitation.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-13-005"))
```

None of `DECLINED`, `TIMED_OUT` and `AGREED` is terminal.
A `DECLINED` or `TIMED_OUT` row can be invited again, and this re-invitation makes renegotiation possible.
An `AGREED` row can be declined.
What ends the life of a row is its register entry reaching a final status, not any state of the row.

### 9.3 Signatory and Lapsed

Two positions a participant can hold are not states.
Each position is a read of the participant's rows and the case's register.
Neither position is stored or drawn on the state machine.

| Read | Definition |
|---|---|
| **Signatory** | The participant's row for the register's `ACTIVE` entry is `AGREED`. |
| **Lapsed** | An entry is `ACTIVE`, the participant's row for it is neither `AGREED` nor `DECLINED`, and, following `replaces` back from the `ACTIVE` entry, the first entry whose row is `AGREED` or `DECLINED` has an `AGREED` row. |

With no `ACTIVE` entry nobody is a signatory and nobody has lapsed.
After an embargo is terminated, no entry is `ACTIVE`, so the termination writes no row.
The position of every participant follows from the register alone.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-18-001", "MSM-07-006"))
```

After the case is public, an exploit is public or attacks are observed, abandoning an open proposal also writes no row.
The CASE_MANAGER cancels the proposal with a `Reject` if it received the proposal, or with an `Undo` if it made the proposal itself.
Then the CASE_MANAGER withdraws each invitation that it relayed for the proposal, with an `Undo`.
Each row for the canceled proposal is frozen as it stood.

The CASE_MANAGER's `Reject` is its abandonment, not its consent.
A CASE_MANAGER that has a stake in an embargo therefore records its own answer as its own update of the row, never as a `Reject`.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("EMB-16-001"))
```

A participant lapses when the case owner activates a revision that ends later than the embargo that the participant agreed to, and the participant has not agreed to the revision.
The participant did agree, but the embargo in force has since become something that the participant did not agree to.
Only the embargoes that were once in force are on the `replaces` chain.
Agreement to a proposal that never took effect therefore gives the participant nothing to lapse from.
A participant that withdrew from a later embargo has a `DECLINED` row on the chain.
That participant has not lapsed when a further revision replaces that later embargo.

!!! warning "Lapsed is neither the proposal state nor the deadline state"
    A revision that is only proposed lapses nobody.
    A revision that ends no later than the accepted terms also lapses nobody.
    A participant that lets an invitation deadline pass reaches `TIMED_OUT` on that invitation's row, not lapsed.
    A lapse is not timer-based and has no transition of its own.
    A lapsed participant is re-invited on an `INVITED` row for the embargo in force, and the deadline attaches to that invitation.

A revision does not move anyone's consent to the embargo in force until it takes effect.
While a revision is only proposed, the prior embargo is in force and every signatory to it remains one.
The proposer's row for the revision is `AGREED`, because proposing terms is consenting to them.
Every other participant gets an `UNINVITED` row for the revision.
A signatory that agrees to the revision records that agreement on the revision's row.
A signatory that declines the revision refuses those terms and nothing more, on that row only.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("EP-05-002", "MSM-07-003", "MSM-07-004"))
```

A signatory withdraws by leaving the embargo in force with `Leave(EmbargoEvent)`, not by rejecting an invitation to it.
The withdrawal declines the signatory's row for the embargo in force.
The withdrawal also declines each open proposal's row that the signatory had agreed to, because every open proposal is a revision of the embargo that the signatory is leaving.
A `Reject` of the active embargo from an `AGREED` row is refused with a reported reason.
The case owner does not leave an embargo.
The case owner ends an embargo by terminating it.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("MSM-07-010", "VAM-05-011"))
```

Only the case owner's decision changes the embargo on the case.
The answers of the other participants inform that decision.
When the owner activates a revision, the direction of the change decides what happens to the consent of the signatories to the old terms:

- A revision that ends **no later than** the terms it replaces asks nothing new of anyone who agreed to the old terms, because agreeing to N days is agreeing to every shorter period.
  The CASE_MANAGER applies `CARRY_OVER` to the revision's row of every participant whose row for the replaced embargo is `AGREED`.
  This rule includes a `DECLINED` row for the revision.
- A revision that ends **later** asks for more than they promised.
  No row is written.
  By the definition above, a signatory to the old terms whose row for the revision is not `AGREED` has lapsed.

In both cases, a participant that already holds an `AGREED` row for the revision is a signatory to the revision by lookup.
This is true for the proposer and for an early acceptor.
Only signatories to the old terms are carried over.
A participant that had lapsed from an earlier embargo stays lapsed until it is re-invited or agrees.
If the activation makes the invitation of an `INVITED` participant stale, that participant is re-invited to the current terms, as in [§9.4 Deadlines and the Pocket Veto](tracking-models.md#94-deadlines-and-the-pocket-veto).
If the owner rejects the revision instead, the old terms stand and nobody's consent changes.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("EP-09-005", "MSM-07-008", "MSM-07-009", "EP-05-001", "MSM-07-005"))
```

### 9.4 Deadlines and the Pocket Veto

An embargo invitation does not stay open indefinitely.
If a participant neither agrees nor declines before the RSVP deadline, its row for that invitation moves to `TIMED_OUT`.
This move is the **pocket veto**.
The protocol does not treat silence as assent, because proceeding on an unanswered invitation would assert an agreement that the participant never gave.
The protocol also does not record silence as a refusal.
Only an explicit refusal reaches `DECLINED`.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-18-002", "CM-28-004", "MSM-07-007"))
```

The deadline is explicit or defaulted:

- An embargo invitation can carry its own `endTime`, giving an explicit respond-by instant.
  When present, this `endTime` takes precedence over the policy window.
- When the invitation has no `endTime`, a policy window applies.
  The default window is 7 days.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-28-001", "CM-28-002", "EP-07-001"))
```

In both cases, two rules later in this section set a lower bound and an upper bound on the result.
The explicit `endTime` takes precedence over the policy window, but neither one escapes the minimum window or the embargo-end ceiling.
The pocket veto is the implicit form of this one mechanism, not a second mechanism alongside it.

!!! warning "One invitation carries two different end times"
    The invitation's `endTime` is the **respond-by** deadline for the invitee.
    The embargo event nested inside the invitation has its own `endTime`, which is when the **embargo** would expire.
    They sit one nesting level apart and mean different things.

    An implementation that reads the embargo's expiry as the RSVP deadline will hold invitations open for the entire embargo period.
    An implementation that reads the RSVP deadline as the embargo expiry will end embargoes days after they were agreed.

**Recording the deadline.**
When the CASE_MANAGER relays an invitation, it sets the Invite's `endTime` and records the deadline on the invitee's `INVITED` row for the invited embargo.
Every replica records the same deadline by copying the CASE_MANAGER's ledger entry for that row.
A participant does not derive or store a deadline when it receives an Invite.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-28-012", "CM-28-013"))
```

**Enforcing the deadline.**
Only the CASE_MANAGER enforces the deadline.
It records each expiry as its own ledger entry, and a replica learns of the expiry from that entry, never by computing it.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-28-003", "CM-28-014", "CM-28-009"))
```

!!! note "Informative: when the CASE_MANAGER checks deadlines"
    The reference implementation enforces the deadline lazily.
    When the CASE_MANAGER next handles the case, it compares each deadline against its own clock, so no scheduler or timer service is needed.

    Before it commits the case owner's decision on a proposal, whenever it processes any other received embargo activity for the case, and whenever it runs an embargo trigger of its own, it expires every `INVITED` row whose deadline has passed and whose embargo is an open proposal or the embargo in force.
    A row of a replaced, rejected, canceled or ended embargo is frozen, so the sweep skips it.
    The sweep runs after the activity's sender has been admitted and before the activity's own refusals.
    An expiry is therefore recorded even when the activity is then refused.

**A minimum window applies.**
The minimum respond-by window is the lesser of a configured window, 72 hours by default, and the time remaining in the embargo the invitation concerns.
An inviting actor does not send an invitation whose deadline is shorter than the minimum.
A receiver that gets one anyway extends the deadline to the minimum, and does not reject the invitation for this reason.
A too-short deadline is the proposer's error, and a refusal of the invitation would penalize the invitee for that error.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("EP-07-002", "EP-07-003", "EP-07-004"))
```

**A deadline does not outlive its embargo.**
A respond-by deadline never falls after the end of the embargo it concerns.
If a computed deadline, whether from the invitation's explicit `endTime` or from the policy window, would fall after that end, it is clamped down to the embargo's end.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("EP-07-006", "CM-28-011"))
```

An invitee needs to be able to answer while there is still something to answer about.
For example, a participant is invited to a 24-hour embargo with no explicit `endTime`, and the policy window is 7 days.
The participant's inaction would be recorded as a time-out on day 7, six days after the embargo ended.
This example is why the minimum window above is relative, not absolute.
A 12-hour embargo grants a 12-hour answer window.
That window is not an unreasonably short deadline when 12 hours is the whole embargo.

**A late acceptance is not refused.**
The CASE_MANAGER does not refuse a late accept on deadline grounds.
Three cases apply:

- If the accepted terms are the case's current embargo, the CASE_MANAGER records the accept exactly as an on-time accept.
  Its entry is the accept itself, and a `TIMED_OUT` or `DECLINED` row moves to `AGREED` directly.
- If the terms are stale, the CASE_MANAGER relays a fresh invitation carrying the current terms, on behalf of their proposer.
- If no embargo remains, the accept changes nothing.
  The CASE_MANAGER records no entry, sends no reply and leaves the rows unchanged.
  The participant keeps its place in the case either way.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("EMB-17-001", "EMB-17-002", "EMB-17-003", "EMB-17-004", "EMB-17-008"))
```

**A time-out and a refusal reach different states.**
Silence records `TIMED_OUT`.
An explicit refusal records `DECLINED`.
The case ledger also distinguishes them, because it holds either the refusal that was sent or the CASE_MANAGER's record of the expiry.
But every reader of the consent rows can tell the two states apart without the ledger.
Both can be invited again, and both move to `AGREED` directly on a late accept of the current terms.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-28-005"))
```

### 9.5 Embargo Traffic Reaches Non-Signatories

Embargo consent gates case **content**.
It does not gate the negotiation about the embargo itself.

The CASE_MANAGER delivers embargo meta-protocol activities addressed to a participant directly (an embargo `Invite` and its responses) to that participant, even when that participant declined, timed out or lapsed.
These activities are not ledger fan-out, which the content gate holds back from non-signatories.
A participant cannot agree to revised terms that nobody told it about.
A participant that declined the original terms can still accept the revision.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-10-005"))
```

Only case content (report details, fix status, sensitive notes) is gated on being a signatory ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)).

### 9.6 Embargo Adherence

Whether a participant is currently bound by the embargo is a single yes-or-no question.
The protocol answers this question from the consent rows.
A participant is bound exactly when it is a signatory, that is, when its row for the register's `ACTIVE` entry is `AGREED` ([§9.3 Signatory and Lapsed](tracking-models.md#93-signatory-and-lapsed)).

This is a derived fact, not an independent one.
Adherence is not recorded as a value that can be set separately from the rows it reports.
Such a value and the rows could then disagree.
A case that reports a participant as bound while its rows say otherwise has no correct reading.

Every change of consent is one of two kinds, so that every change is a valid one and is recorded as such:

- a consent trigger applied through the transitions of [§9.2 Transitions and Guards](tracking-models.md#92-transitions-and-guards)
- a copy of the row that a ledger entry carries, after a check of its starting state, made the same way by the CASE_MANAGER and by every replica

The CASE_MANAGER commits every consent row that it changes as its own `Update(EmbargoConsent)` ledger entry.
For a row that it brings into existence, the entry is `Create(EmbargoConsent)`.
Each such entry comes after the entry of the act that caused the change.
When the act's own activity states the row, the act's entry is also the row's entry.
Examples are a participant's `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])` or, for the case owner's own row, its `Accept(EmbargoEvent)[target=VulnerabilityCase]` that activates an embargo.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CLP-07-013", "CM-23-016"))
```

!!! note "Informative: how the reference implementation does this"
    The reference implementation exposes adherence as a computed lookup over the stored consent rows and the register, so there is no separate field that can disagree with the rows.
    Any mechanism with that property gives the same reading.

### 9.7 Gating Full Case Delivery

Before the CASE_MANAGER delivers full case content (`Announce(VulnerabilityCase)` carrying report details, vulnerability description, and sensitive notes), the recipient is an **active participant**:

1. The participant has **joined the case**: the case initialization sequence seated it, or it accepted the stub Invite, and it has not been removed.
2. The participant is a **signatory to the active embargo** (its row for the active embargo is `AGREED`), **or** no embargo is in force (EM is not `ACTIVE` or `REVISE`).

Content stops for a participant whose closure the ledger records, after the entries that record its own closure.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-10-004", "CM-17-005", "CM-23-004"))
```

!!! note "Recall: report management states"
    {% include-markdown "./includes/_rm-states-table.md" %}

    Full definitions are in [§6.1 States](tracking-models.md#61-states).

!!! warning "The gate is joining plus consent — not RM progress"
    It is tempting to read the gate as an RM state: `RM.ACCEPTED`, or `RM.RECEIVED` as "admitted".
    Both readings are wrong.

    An invitee is at `RM.RECEIVED` from the stub Invite, before it has answered, and is still inert.
    Being in the case's participant list at `RM.RECEIVED` is therefore not entitlement to case content.

    The invitee reaches `ACCEPTED` only *after* it receives the full case and runs its triage cycle ([§6.3 Per-Participant RM Tracking](tracking-models.md#63-per-participant-rm-tracking)).
    If delivery required `ACCEPTED`, a participant could never obtain the case that it needs to reach the state that gates delivery.

    **Joining and embargo consent — not RM progress — are the gate on case content.**
    The ordering is: the invitee accepts the stub Invite, which joins the case and agrees to any active embargo it has not declined, and then the CASE_MANAGER delivers the full case.

This gate matters to the cascade ordering of [§11 Model Interactions and Cascade Rules](interactions.md#11-model-interactions-and-cascade-rules-n).
`Accept(Invite)` agrees to any active embargo on the joiner's row for that embargo, unless that row is `DECLINED`.
This agreement lets delivery proceed immediately, with no wait for a separate consent round-trip.
A joiner whose row for the active embargo is `DECLINED` stays declined, because an explicit refusal outranks the consent that joining implies.
That joiner is in the case but inert until it changes its answer.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-001"))
```

---
