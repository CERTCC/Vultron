---
stakeholder_type: [platform-developer]
level: 400
page_type: explanation
subject: protocol
introduces: [Embargo Consent, Pocket Veto]
description: >
  Triggers `propose_embargo`, `accept_embargo`, `reject_embargo`, and `terminate_embargo`: negotiating, joining, revising, and ending an embargo.
---

# Embargo Lifecycle

{% include-markdown "../../../includes/specification_governs.md" %}

An embargo is an agreement that Participants will not disclose a vulnerability before an agreed moment.
The protocol tracks it twice, at two different scopes.
Almost every mistake in this area comes from confusing the two scopes.

This page explains the two-scope model, the negotiation steps and what each one commits, where the judgment sits, and the one condition that overrides every other consideration.

---

## Two scopes, not one state

The case carries **one** embargo, and each Participant carries its **own stance** toward it.

| Scope | What it tracks | States |
|---|---|---|
| Embargo Management (EM) | The case's embargo — one per case, computed from the case's embargo register | `NONE`, `PROPOSED`, `ACTIVE`, `REVISE`, `EXITED` |
| Participant Embargo Consent (PEC) | One Participant's answer to each embargo in the register | one row per embargo: `UNINVITED`, `INVITED`, `AGREED`, `DECLINED`, `TIMED_OUT` |

The distinction is not bookkeeping.
"The case is under embargo" and "this Participant is bound by it" are different facts.
A case routinely holds both at once: an active embargo with one Participant who declined it.
The case keeps one embargo register entry for every embargo ever proposed on it.
The EM state is a read of the entries' statuses ([§7.1.1 The Embargo Register in the specification](../../../reference/vultron-spec/tracking-models.md#711-the-embargo-register)).
A Participant is a signatory when its consent row for the register's `ACTIVE` entry is `AGREED`.
Signatory status is a lookup, not a second record, so the embargo and the Participant's position can never drift apart ([ADR-0122](../../../adr/0122-per-embargo-participant-consent.md)).
A Participant has lapsed when it agreed to an embargo that has since been replaced by one it has not agreed to.
Lapsed status is also read from the rows and the register, and it needs three conditions (CM-18-001):

- An entry is `ACTIVE`.
- The Participant's row for that entry is neither `AGREED` nor `DECLINED`.
- On the chain of replaced embargoes back from that entry, the first row that is `AGREED` or `DECLINED` is `AGREED`.

Neither signatory nor lapsed is a consent state.

Every row is written.
Proposing an embargo gives every current Participant an `UNINVITED` row for it (CM-18-001).
A new Participant record gets an `UNINVITED` row for every embargo already in the register (CM-18-001).
`UNINVITED` means *not asked about this embargo*, not "has not answered yet".
A missing row is a defect: a read of a missing row raises an error.
An actor may agree or decline directly from `UNINVITED`, without an invitation first ([ADR-0048](../../../adr/0048-pec-no-embargo-is-absence-not-pre-consent.md), CM-18-003).

---

## What starts it

Five different things put an actor on this path.

**Case creation.** A case begins embargoed.
When a case opens with no explicit proposal, the receiving side applies its published default.
The case then goes straight to `EM.ACTIVE`, not `EM.PROPOSED` (EP-04-001).
The intermediate `PROPOSED` state is never stored, and no actor can observe it (EP-04-002).
For this reason, a normal case trace shows no proposal exchange at all.
A report submitted without a counter-proposal tacitly accepts the receiver's default.

**A local decision to negotiate.** The `propose_embargo`, `propose_embargo_revision`, and `terminate_embargo` triggers.

**An inbound overture.** Either an Embargo Proposal (EP) carrying terms, or an `Invite(EmbargoEvent)` asking one actor for its consent.
These are the two flows the response decision handles (EMB-15).
An answer to an invitation is an `Accept` or `Reject` of the `Invite(EmbargoEvent)`.
The answer is always the sender's own consent.
It moves only the row of the sender, even when the sender is the case owner (MSM-07-003, MSM-07-004).
The case's embargo moves only when the case owner decides it, with `Accept(EmbargoEvent)[target=VulnerabilityCase]` or `Reject(EmbargoEvent)[target=VulnerabilityCase]` (MSM-07-008, MSM-07-009).

**A deadline passing.** An invitation carries a respond-by instant.
An unanswered invitation eventually times out.
A time-out is not a refusal, as [Inaction is an answer](#inaction-is-an-answer) below explains.

**An end time passing.** An embargo in force does not end by itself when its end time passes.
The case manager ends it with the reason `END_TIME_REACHED` the next time it handles the case.
That handling can be for an incoming message or for one of its own triggers, so no scheduler is needed.
The end-time check runs as part of the message or trigger handling.
It runs after the case manager confirms that the sender may send the message or trigger, so a sender with no standing in the case cannot end the embargo.
A request to end the embargo early made after its end time is also recorded as `END_TIME_REACHED`.
See [When the End Time Passes](../../process_models/em/early_termination.md#when-the-end-time-passes).

---

## The mechanical path

Every EM transition runs through one of two paths: the embargo lifecycle service, or the single function that applies a committed ledger entry.
The case manager and every replica share that function (ADR-0124).
Termination and activation take the second path.
The case manager first commits the `Remove` or the owner's `Accept`, and then applies it.
The `Accept` records the whole activation, including the supersession of the replaced embargo and the owner's own agreement.
After the `Accept`, each signatory carried over to shorter terms gets its own ledger entry.

The case manager records an invitation that expires unanswered in the same way.
It commits the expiry, then the participant's changed consent, and only then writes those changes.
A behavior tree node never assigns `case.current_status.em` and saves the case as a shortcut (EMB-18-001).
This rule exists because a transition is not a field write.
Each transition has to pass validation against the state machine.
A failed validation must stop the node, not log a warning and write anyway (EMB-18-002).

A case also never names an embargo whose record its store does not hold (EMB-18-003).
Activation of an embargo reads two records: the record it activates and the record it replaces.
If either read fails, the activation refuses before any write.
A sender carries the embargo record inline with the case.
A receiver stores that record before the case that names it.
A receiver therefore refuses, and does not store, a case that names an embargo the receiver lacks.

A receiver refuses an inline embargo record whose context is neither the case nor one of its reports.
This check stops a sender from planting one case's embargo under the id of another case.
The receiver checks the record it already holds under that id in the same way.
This check applies whether the case or ledger entry carries the embargo inline or names it only by id (EMB-18-004).
An embargo whose context is one of the case's own reports counts as the case's, because a reporter's proposal names its report until the case exists (EP-04-009).

A receiver also checks who sent each embargo message before it changes anything (ADR-0115).
The case manager takes a proposal only from an active participant, and takes an acceptance or rejection only from the actor the recorded invitation was addressed to.
It takes a message that creates, adds or removes an embargo record only from the case owner or from itself.
Every other participant takes an embargo message only from the case manager.
A message from any other sender is refused and changes no state.

Each message that changes the case's embargo is one step on the embargo register, and the EM state follows from the register.
Every step must move EM along a transition of the EM state machine.
A step that would not is refused, and nothing is written (EMB-18-005, EMB-18-006).
The transitions themselves are small and fixed:

| Message received | Register step | EM result |
|---|---|---|
| Embargo Proposal (EP), `Invite(EmbargoEvent)` | a new `PROPOSED` entry | `NONE` to `PROPOSED` (EMB-01-001); stays `PROPOSED` or `REVISE` for a further proposal |
| Embargo Revision (EV), `Invite(EmbargoEvent)` | a new `PROPOSED` entry | `ACTIVE` to `REVISE`; the active embargo stays in force (EMB-03-001) |
| Embargo Acceptance (EA) or Revision Acceptance (EC), the case owner's `Accept(EmbargoEvent)[target=VulnerabilityCase]` | the named entry becomes `ACTIVE`, superseding any entry in force | to `ACTIVE` once no other proposal is open, otherwise to or staying at `REVISE` (EMB-02-001) |
| Embargo Rejection (ER) or Revision Rejection (EJ), the case owner's `Reject(EmbargoEvent)[target=VulnerabilityCase]` | the named entry becomes `REJECTED` | `PROPOSED` to `NONE`, or `REVISE` to `ACTIVE`, once no other proposal is open; otherwise unchanged (EMB-06-001) |
| Embargo Termination (ET), `Remove(EmbargoEvent)` | the `ACTIVE` entry becomes `TERMINATED`, and every open proposal `CANCELLED` | `ACTIVE` or `REVISE` to `EXITED`, immediately |

The formal protocol has each receiver acknowledge these messages with EK.
In this implementation, the case manager's commit and announcement of the received activity is that acknowledgment, and no EK message exists (EP-09-009, MSM-02-009).

`EM.REVISE` is worth a second look.
A revision under negotiation does not suspend the embargo.
The existing terms remain binding until the case owner accepts the revision, and every signatory to them remains a signatory.
This continuity makes renegotiation safe.
It is also why the recommended practice is to accept and then revise, not to counter-propose.

---

## Which messages move consent

Consent has no messages of its own (MSM-07-001).
Every Participant Embargo Consent change is a side effect of an EM activity or a deadline.
The case manager records each change.
A Participant never declares its own consent state.

| Activity | Effect on the case's EM state | Effect on consent |
|---|---|---|
| Embargo Proposal (EP) or Revision (EV), `Invite(EmbargoEvent)` on the case | `NONE` to `PROPOSED`, or `ACTIVE` to `REVISE`; a further proposal leaves it where it is | every other Participant gets an `UNINVITED` row for the proposed embargo, the proposer's row is `AGREED`, because proposing terms is consenting to them, and no row for the embargo in force changes (CM-18-001, MSM-07-005, EP-05-002) |
| A relayed `Invite(EmbargoEvent)` to one Participant | none | the invitee's row for that embargo moves from `UNINVITED`, `DECLINED` or `TIMED_OUT` to `INVITED`, carrying the invitation's RSVP deadline; a signatory asked about a revision keeps its `AGREED` row for the embargo in force (MSM-07-002, EP-09-004, CM-28-013) |
| `Accept(Invite(EmbargoEvent))`, from any Participant, the case owner included | none | the sender's row for those terms becomes `AGREED`; that makes it a signatory only once they are the embargo in force (MSM-07-003) |
| `Reject(Invite(EmbargoEvent))`, from any Participant, the case owner included | none | the sender's row for those terms becomes `DECLINED`; refused from an `AGREED` row for the embargo in force, because withdrawal is `Leave(EmbargoEvent)` (MSM-07-004, MSM-07-010) |
| The case owner's `Accept(EmbargoEvent)[target=VulnerabilityCase]` (EA, or EC for a revision) | to `ACTIVE`, or to `REVISE` while another proposal stays open | the owner's row for the activated embargo becomes `AGREED` unless it already is; a revision that ends no later than the embargo it replaces carries over every Participant whose row for the replaced embargo is `AGREED`, and one that ends later writes nothing, so a signatory that has not agreed to it has lapsed (MSM-07-005, MSM-07-008) |
| The case owner's `Reject(EmbargoEvent)[target=VulnerabilityCase]` (ER, or EJ for a revision) | `PROPOSED` to `NONE`, or `REVISE` to `ACTIVE` with the prior terms standing, once no other proposal is open; once public disclosure, a public exploit or an attack is known, the rejection of the last open revision is followed in the same act by the case manager's termination (ET, EMB-04-002), so the revision ends `REJECTED` and the embargo `TERMINATED` | none, the owner's included (MSM-07-009) |
| Withdrawal, `Leave(EmbargoEvent)` of the embargo in force | none | the withdrawing Participant's `AGREED` row for the embargo in force becomes `DECLINED`, as does every row it had marked `AGREED` for an open revision; the embargo stays in force for everyone else (MSM-07-010) |
| Embargo Termination (ET), `Remove(EmbargoEvent)` | `ACTIVE` or `REVISE` to `EXITED` | none is written: with no `ACTIVE` entry nobody is a signatory, and no message is sent for consent (MSM-07-006) |
| Invitation deadline passes | none | that invitation's `INVITED` row moves to `TIMED_OUT`, recorded in the case ledger (MSM-07-007) |

One activity can therefore move both scopes at once: the case owner's `Accept(EmbargoEvent)[target=VulnerabilityCase]` activates the embargo *and* makes the owner a signatory.

Only the case manager records an answer.
A Participant that receives an Accept or Reject meant for the case manager refuses it.
A Reject of terms that are neither in force nor still proposed is refused, not recorded.

Sometimes an Invite asks a Participant about the embargo already in force.
One example is a Participant that received a relayed proposal that was activated before the Participant answered.
Another example is a lapsed signatory.
That Participant answers the Invite by naming that Invite (EP-09-012).

A signatory leaves the embargo in force with `Leave(EmbargoEvent)`, not with a Reject.
The case manager refuses a signatory's Reject of the active embargo (MSM-07-004, MSM-07-010).
A signatory that rejects a *proposed* revision refuses only those terms.
It stays a signatory to the embargo in force.
In both cases, the case's embargo does not change, because an answer to an Invite changes no embargo register entry (MSM-07-003, MSM-07-004).

The protocol-level view of consent is in [§9.2 Transitions and Guards in the specification](../../../reference/vultron-spec/tracking-models.md#92-transitions-and-guards).

---

## What each act commits

The case manager records every change it makes to the embargo register or to a consent row in the case ledger before the case changes (CLP-07-013, [ADR-0124](../../../adr/0124-case-is-a-projection-of-its-ledger.md)).
One ledger entry records one activity and its object.
An act therefore commits its own entry first.

Each other object the act changes then follows as its own case manager entry, in the order the case manager changes them.
For embargo acts, those other objects are consent rows.
Each is a `Create(EmbargoConsent)` for a new row or an `Update(EmbargoConsent)` for a changed one, and it carries the row in full.
A register change is never an entry of its own: the act's own activity carries it.

The case manager makes every decision before the first commit: who is invited, which signatories carry over, which proposals a termination cancels.
It checks the whole act against a copy of the case, commits the entries, and only then writes the case.
A refused act commits nothing.
An act whose entry fails to commit changes nothing.

| Act | What the act's own entry records | What follows, one entry per row |
|---|---|---|
| Proposal or revision, `Invite(EmbargoEvent)` on the case | the new embargo, now proposed | a `Create(EmbargoConsent)` for every Participant: the proposer's row `AGREED`, because proposing terms is consenting to them, and every other row `UNINVITED` |
| Relayed invitation, `Invite(EmbargoEvent)` to one Participant | no register change | an `Update(EmbargoConsent)` moving the invitee's row to `INVITED`, with its respond-by deadline (CM-28-013) |
| Case manager's own answer to a proposal, by its policy or by its own `accept` or `reject` request | no register change, and no `Accept` or `Reject` is sent | an `Update(EmbargoConsent)` for the case manager's own row, `AGREED` or `DECLINED` (MSM-07-004) |
| Participant's answer, `Accept` or `Reject` of `Invite(EmbargoEvent)` | the row the answer states, `AGREED` or `DECLINED` | nothing: the answer is that row's entry |
| Owner's activation, `Accept(EmbargoEvent)[target=VulnerabilityCase]` | the activation, the supersession of the embargo it replaces, and the owner's own `AGREED` row | an `Update(EmbargoConsent)` for each signatory carried over to terms that end no later (EP-05-001) |
| Owner's rejection, `Reject(EmbargoEvent)[target=VulnerabilityCase]` | the rejected proposal | nothing |
| Abandonment once the case is public: the case manager's `Reject(Invite(EmbargoEvent))` of a proposal it received, or its `Undo(Invite(EmbargoEvent))` of one it sent itself | the canceled proposal | an `Undo(Invite(EmbargoEvent))` of each invitation the case manager relayed for that proposal, which changes nothing more |
| Withdrawal, `Leave(EmbargoEvent)` | no register change | an `Update(EmbargoConsent)` moving the withdrawing Participant's row for the embargo in force to `DECLINED`, and one for each open revision it had agreed to (MSM-07-010) |
| Termination, `Remove(EmbargoEvent)` | the end of the embargo in force and the cancellation of every open proposal (EP-08-004) | nothing: a termination writes no consent row (MSM-07-006) |
| Invitation deadline passes | the expiry of that invitation (CM-28-009) | an `Update(EmbargoConsent)` moving the row to `TIMED_OUT` |
| Late `Accept` of the current embargo | the `Accept` itself, as for an on-time `Accept`: the row it states, `AGREED` | nothing: the `Accept` is that row's entry |
| Late `Accept` of a superseded embargo | the fresh invitation, relayed on behalf of the current embargo's proposer | an `Update(EmbargoConsent)` moving the row to `INVITED`, with its deadline |
| Late `Accept` of an embargo the case no longer has | nothing: the `Accept` changes nothing, so no entry is committed (EMB-17-004) | nothing |
| Stub invitation re-sent after the embargo changed | the replacement invitation | an `Update(EmbargoConsent)` moving the invitee's row for the embargo in force to `INVITED`; with no embargo in force, nothing |

A Participant joining through its stub invitation agrees to the embargo in force with that same `Accept`, so the joiner's `AGREED` row has no entry of its own either.
A joiner that had already declined that embargo keeps its `DECLINED` row: an explicit refusal outranks the consent that joining implies (CM-11-001).

Every replica, and the case manager itself, uses one shared apply function to copy each register step and consent row that an entry carries (CM-23-016).
That includes the row a Participant's own answer states, such as a joiner's `AGREED` or `DECLINED` row from its reply to the stub invitation.
That function checks that the entry fits the case as it stands, then writes what the entry carries.
It runs no embargo lifecycle logic, creates no ids, and reads no clock.

An entry that does not fit is held as a gap until the missing entries arrive.
The gap is never patched over.
As a result, a store rebuilt from the case manager's ledger alone holds the same participant records, consent rows and embargo register as the case manager.

The `Remove` entry carries what ended the embargo: `EARLY` or `END_TIME_REACHED`.
For an early end, it also carries the structured cause, such as a threat signal.
A replica copies both onto its own register, so its record of the termination matches the case manager's.

When the owner rejects the last open revision after the case went public, the case manager records the rejection and then ends the embargo in the same act (EMB-04-002, MSM-07-009).
The ledger holds two entries: the `Reject`, which leaves the revision `REJECTED`, and then the case manager's own `Remove`, which leaves the embargo `TERMINATED` with the threat signals as its cause.
A replica copies both entries in order and decides nothing.
If the termination is refused, neither entry is committed.

---

## The condition that overrides everything

If the vulnerability is public, an exploit is public, or attacks have been observed, there is nothing left to embargo.

This condition is not a preference that the negotiation weighs.
It is mandatory, and it applies at every point in the lifecycle:

- A proposal MUST be refused with ER, regardless of any other assessment (EMB-01-002, EMB-01-007).
- An EA MUST NOT move the case to `ACTIVE`.
  The actor emits ER instead (EMB-02-002).
- An EV arriving while the case is public MUST be refused, not adopted (EMB-03-003).
  The embargo ends because the case is public, not because the proposal arrived.
  The proposal is at most how the actor notices.
- An actor sitting at `EM.PROPOSED` that *observes* the case go public MUST abandon the proposal, return to `EM.NONE`, and emit ER (EMB-16-001).
  The case manager makes that abandonment for the case.
  Its committed entries notify everyone else.
  It rejects each proposal it received with `Reject(Invite(EmbargoEvent))`, which cancels the proposal.
  It then withdraws each invitation it relayed for that proposal with `Undo(Invite(EmbargoEvent))`.
  When the case manager made the proposal itself, withdrawing that proposal with `Undo(Invite(EmbargoEvent))` is the cancel.
  A replica tells the case manager's `Reject` from a Participant's `Reject` by its sender.
  A `Reject` from the case manager cancels the proposal.
  A `Reject` from a Participant declines it.
  Only the case owner, or the case manager it delegates to, decides that abandonment.
  Any other participant's status report already tells the case manager that the case went public.
  That participant therefore sends no ER as the abandonment.
  The case manager would read such an ER as that participant declining the proposal (EMB-16-002).
  That rule covers only proposals already open on the case.
  A participant still answers with ER when it *receives* a proposal, Invite or revision while it believes the case is public, as the first item above requires (EMB-01-002).
- An actor at `EM.EXITED` MUST NOT seek or accept a new embargo for a public case (EMB-13-002).

EMB-16-001 is the rule that implementations forget, because no message triggers it.
Nothing arrives to prompt it.
The actor's own state changed, and the obligation follows from that.

---

## Where judgment enters

The embargo lifecycle is the richest call-out surface in the protocol, because almost every embargo question is a policy question.
Each point below names its capability shape from the [ADR-0024](../../../adr/0024-coordination-agent-taxonomy.md) taxonomy.
An injected backend answers each point, and logic inside the tree does not ([ADR-0025](../../../adr/0025-call-out-point-abstraction-layer.md)).
Their service contracts are cataloged in the [Capability Model](../../capability_model/index.md#embargo-management).

**Deciding to negotiate.** `WantToProposeEmbargo` (Evaluator) asks whether to propose at all.
`SelectEmbargoOfferTerms` (Composer) asks what terms to propose.
`StopProposingEmbargo` (Evaluator) asks whether to give up after a refusal.
Their deterministic defaults differ, and the differences encode a recommended posture: propose by default, and do not give up by default.

**Responding to an overture.** `EvaluateEmbargoProposal` (Evaluator) asks whether the terms are acceptable.
Its default is to accept (EMB-15-001, EMB-15-005).
The protocol's position is that a well-formed overture deserves agreement unless there is a reason against it.

`WillingToCounterEmbargoProposal` (Evaluator) asks whether to counter instead.
Its default is *not* to counter (EMB-15-003).
This default is the same recommendation in a different form: accept and then revise, rather than trade proposals.
Countering introduces no new mechanism.
It reuses the ordinary proposal path and leaves the case at `PROPOSED`.

**Staying in.** `CurrentEmbargoAcceptable` (Evaluator) asks whether the active embargo is still acceptable as circumstances change.

**Getting out early.** `ExitEmbargoWhenFixReady`, `ExitEmbargoWhenDeployed`, and `ExitEmbargoForOtherReason` (all Evaluators) each ask whether a condition now warrants ending the embargo.
All three default to *no*, and the defaults are ordered.
A fix being deployed is a more plausible reason to exit than a fix merely being ready, and "some other reason" is the least plausible of all.
An implementer who reads only the code sees three similar nodes.
The probabilities record the editorial judgment.
When an Evaluator says *yes*, the node after it records the termination's cause: `FIX_DEPLOYED`, `FIX_READY` with the Vendors whose fix is ready, or `OTHER` (EMB-14-001, EMB-14-004).
When no Vendor's fix is ready, the `FIX_READY` branch fails, and the tree tries the next reason.
The termination message and the ended embargo's register entry record that cause.

**Authorizing the response.** Deciding how the *case* responds to an overture is not every Participant's call.
The response seam puts a case-owner check first.
When the deciding actor holds `CVDRole.CASE_OWNER`, its stated response is authoritative, and the seam seeks no approval (EMB-15-002, EMB-15-006).
A non-owner routes through `CaseOwnerApprovesEmbargoResponse` (Evaluator, EMB-15-007).
This non-owner is typically a case manager that handles the overture for the owner.

**Reacting to the outcome.** `OnEmbargoAccept`, `OnEmbargoReject`, and `OnEmbargoExit` are Actuators.
They are notification and integration hooks that fire after the transition and confirm a side effect.
They produce nothing that the protocol reads.

!!! note "A default is not a requirement"

    Every "defaults to accept" above describes the stub backend that a deployment gets when it wires nothing (BT-23-001).
    None of them is a protocol obligation to accept.
    The one place where the protocol *does* mandate an answer is the public/exploit/attacks condition.
    That condition is enforced independently of any call-out outcome (EMB-15-004, EMB-15-008).

---

## Inaction is an answer

An `Invite(EmbargoEvent)` carries a respond-by instant.
Silence past that instant ends the invitation, which is the **pocket veto**.
When a Participant with an `INVITED` row does not answer within the window, its row moves to `TIMED_OUT`, not `DECLINED`.
Silence is not a decision, and `DECLINED` records only an explicit refusal (CM-28-004, [ADR-0118](../../../adr/0118-pec-expired-and-unbound-exited-states.md)).
The deadline belongs to one invitation and is recorded on that invitation's `INVITED` row.
A Participant can therefore hold several open invitations with different deadlines.
When one deadline passes, it times out only its own row (CM-28-013).

The window has two forms, but they are one mechanism, not two ([ADR-0065](../../../adr/0065-embargo-invite-rsvp-deadline.md)).
When the invitation carries an explicit `Invite.end_time`, that value governs (CM-28-002).
When it does not, the policy default applies: seven days, measured from the invitation's `published` timestamp (EP-07-001).
The case manager stamps `Invite.end_time` on every invitation it relays.
It then records the invitee's `INVITED` consent row, deadline included, as its own ledger entry right after the Invite's entry.
Every replica copies that row from the entry (CM-28-012, CM-28-013).
A Participant that receives an invitation derives no deadline of its own.

There is a floor.
An inviting actor must not send a window shorter than the minimum (EP-07-002).
The minimum defaults to 72 hours (EP-07-002) and is configurable (EP-07-008).
As the actor that stamps the relayed invitation, the case manager clamps a too-short window up to the minimum and logs the clamp.
It does **not** reject the proposal as malformed (EP-07-003, EP-07-004, EP-07-005).
Refusing a too-short invitation would punish the invitee for the inviter's error.

There is also a ceiling: the deadline never falls after the invited embargo ends (EP-07-006, CM-28-011).
A deadline past that end is lowered to the end, and the clamp is logged.
This rule applies whether the deadline was sent explicitly or computed from the policy window.
The floor gives way to the ceiling: the minimum is 72 hours or the time left in the embargo, whichever is shorter (EP-07-002).
On day 28 of a 30-day embargo, the invitee has until day 30 to answer, not seven days.

The case manager runs no timer.
It notices a passed deadline the next time it handles an embargo activity for the case.
At that point it moves each overdue `INVITED` row on an open proposal or the embargo in force to `TIMED_OUT`, and records each move in the case ledger (CM-28-015).
It does so before it records the case owner's decision on a proposal, and before every other embargo activity it receives or sends.
The case owner learns of each expiry from that ledger entry, so it decides on the embargo knowing who never answered.

The case manager checks for overdue invitations only after it knows that the sender may send the activity.
It checks before it judges the activity itself, so the expiry is recorded even when the case manager then refuses the activity.
There is one exception.
Sometimes the case manager refuses an Invite or an `Accept` because the vulnerability is already public, exploited or attacked (EMB-02-002).
In that case, it does not check for overdue invitations, and the next embargo activity that it admits does the check.

A late `Accept` is never refused merely for being late (EMB-17-001).
Instead, the case manager asks whether the accepted embargo is still the case's current one.
The three possible answers are all different:

| What the late Accept refers to | What the case manager does |
|---|---|
| The case's current embargo | Honor it; record the `Accept` exactly as an on-time Accept, so the Participant's consent row moves to `AGREED` directly from `TIMED_OUT` or `DECLINED`, since a Participant that accepts after declining has changed its answer (EMB-17-002) |
| A superseded embargo | Send a fresh invitation carrying the current terms, relayed like any other on behalf of the current embargo's proposer. Do **not** record consent to terms the actor never saw (EMB-17-003, EMB-17-005) |
| An embargo the case no longer has | Nothing: the `Accept` changes nothing, so record no entry, send no reply, and change no consent. Do not invite, and do not remove the actor from the case (EMB-17-004, EMB-17-007, EMB-17-008) |

None of the three rows removes the accepting actor.
Answering late is not a protocol violation.

---

## What the case learns

Embargo messages route through the case manager like every other case-scoped message (PCR-08-001).
A Participant does not announce its embargo stance to the other Participants itself.

Teardown is the exception worth naming, because its addressing is prescribed.
The `Announce(EmbargoEvent)` that follows a teardown the Case Owner asked for must be authored by the actor holding `CVDRole.CASE_MANAGER`.
It must be addressed to every active Participant *except* the announcing actor, and never to the case manager itself (EMB-19-001).
A Closed Participant is left out, as it is from all case content (CM-23-004).
A teardown the case manager starts itself, including one at the embargo's end time, sends no announcement.
When the case manager is the only Participant, the announcement is skipped rather than sent with an empty recipient list (EMB-19-002).

On entering `EM.EXITED`, no Participant is bound by an embargo any more, and no later invitation can bind one (EMB-13-001, MSM-07-006).
No consent row is written for this: the register holds no `ACTIVE` entry, and the register is the fact.
The embargo is over for everyone at once, which is the one thing about the EM scope that is genuinely global.

### The case status EM copy is read-only

A `CaseStatus` carries one EM copy — a stamped read of the case's embargo register.
That copy is **read-only**: `CaseStatus.em` is a frozen field and `EmDimension` is a frozen model (SDO-03-006, EMB-18-001).
Every in-place write path raises a `ValidationError` at runtime: `status.em = …`, `status.em.state = …`, and the retired flat spelling `status.em_state = …`, which `CaseStatus` no longer defines (SDO-03-003).

The only writer is the case itself.
Its embargo register can change through any `EmbargoLifecycle` operation or through the function that applies a committed entry.
When the register changes, the case replaces its current status with the copy that `CaseStatus.with_em` makes, which carries the new `EmDimension`.
The copy's `name` label is derived again from its states, so it never names the EM it replaced.
Nothing else may write that copy.
A status with a different EM state is built by construction or by `CaseStatus.with_em`.
Assignment through an existing instance always raises.

---

## What conformance requires

| Requirement | Obligation |
|---|---|
| [EMB-01-002](../../../reference/vultron-spec/requirements/state-behavior.md#emb-01-002) | A proposal MUST NOT be accepted when the case is public, exploited, or attacked |
| [EMB-01-007](../../../reference/vultron-spec/requirements/state-behavior.md#emb-01-007) | Its addressee MUST answer it with ER; an Invite naming its terms by URI only gets its ER once the terms are fetched |
| [EMB-02-002](../../../reference/vultron-spec/requirements/state-behavior.md#emb-02-002) | An EA MUST NOT activate an embargo on a public case; emit ER |
| [EMB-03-001](../../../reference/vultron-spec/requirements/state-behavior.md#emb-03-001) | An EV in `EM.ACTIVE` MUST move to `EM.REVISE`, leaving the active embargo in force |
| [EMB-06-001](../../../reference/vultron-spec/requirements/state-behavior.md#emb-06-001) | An ER in `EM.PROPOSED` MUST return the case to `EM.NONE` when it rejects the last open proposal, and leave it `PROPOSED` while another is open |
| [EMB-13-002](../../../reference/vultron-spec/requirements/state-behavior.md#emb-13-002) | An actor at `EM.EXITED` MUST NOT accept a new embargo for a public case |
| [EMB-15-002](../../../reference/specs/project.md#emb-15-002) | The response seam MUST bypass approval when the deciding actor is the case owner |
| [EMB-16-001](../../../reference/vultron-spec/requirements/state-behavior.md#emb-16-001) | An actor at `EM.PROPOSED` observing the case go public MUST abandon the proposal and emit ER |
| [EMB-16-002](../../../reference/vultron-spec/requirements/state-behavior.md#emb-16-002) | A participant that is not the case manager MUST NOT emit ER as that abandonment or write it itself; it still answers what it receives under EMB-01-002 |
| [EMB-17-001](../../../reference/vultron-spec/requirements/state-behavior.md#emb-17-001) | A late `Accept` MUST NOT be refused solely because the deadline passed |
| [EMB-18-001](../../../reference/specs/architecture.md#emb-18-001) | Every EM transition MUST route through the embargo lifecycle service or the function that applies a committed entry |
| [EMB-18-003](../../../reference/specs/architecture.md#emb-18-003) | A case MUST NOT name an embargo whose record its store does not hold |
| [EMB-19-001](../../../reference/vultron-spec/requirements/state-behavior.md#emb-19-001) | A teardown announcement MUST be authored by the case manager and exclude it from the recipients |
| [EP-04-001](../../../reference/vultron-spec/requirements/state-behavior.md#ep-04-001) | A default embargo applied at case creation MUST produce `EM.ACTIVE`, not `EM.PROPOSED` |
| [EP-07-003](../../../reference/vultron-spec/requirements/state-behavior.md#ep-07-003) | A sub-minimum RSVP deadline MUST be clamped up, not rejected |

---

## Further reading

- [Embargo Management Behaviors](../em_bt.md) — the original design trees for proposal, evaluation, and termination
- [Propose case](propose-case.md) — where the default embargo comes from
- [Embargo Management Handlers](../../../reference/behaviors/em_handlers.md) — the trees the reference implementation builds today
- [EM Process Model](../../process_models/em/index.md) — the case-level embargo model, with its [formal definition](../../process_models/em/formal_model.md)
- [Glossary](../../../reference/glossary.md) — Participant, call-out point, capability shape, embargo consent
