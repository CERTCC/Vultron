---
stakeholder_type: [platform-developer]
level: 400
---

# Embargo Lifecycle

An embargo is an agreement that Participants will not disclose a vulnerability before an agreed moment.
The protocol tracks it twice, at two different scopes, and almost every mistake in this area comes from conflating them.

This page explains the two-scope model, the negotiation steps and what each one commits, where the judgment sits, and the one condition that overrides every other consideration.

---

## Two scopes, not one state

The case carries **one** embargo, and each Participant carries its **own stance** toward it.

| Scope | What it tracks | States |
|---|---|---|
| Embargo Management (EM) | The case's embargo — one per case | `NONE`, `PROPOSED`, `ACTIVE`, `REVISE`, `EXITED` |
| Participant Embargo Consent (PEC) | One Participant's commitment to it | `UNBOUND`, `INVITED`, `SIGNATORY`, `LAPSED`, `DECLINED` |

The distinction is not bookkeeping.
"The case is under embargo" and "this Participant is bound by it" are different facts, and a case routinely holds both at once: an active embargo with one Participant who declined it.
A Participant's `embargo_adherence` is derived from its consent state and is true only at `SIGNATORY`, so the two can never drift apart ([ADR-0056](../../../adr/0056-embargo-adherence-computed-field.md)).

`UNBOUND` is the state most often misread.
It means *not bound by any embargo terms* — not "has not answered yet."
An actor may accept or decline directly from it, with no intervening invitation ([ADR-0048](../../../adr/0048-pec-no-embargo-is-absence-not-pre-consent.md), [ADR-0091](../../../adr/0091-rename-pec-no-embargo-to-unbound.md), CM-18-003).

---

## What starts it

Four different things put an actor on this path.

**Case creation.** A case begins embargoed.
When a case is opened with no explicit proposal on the table, the receiving side applies its published default and the case goes straight to `EM.ACTIVE` — not `EM.PROPOSED` (EP-04-001).
The intermediate `PROPOSED` state is never persisted or observable (EP-04-002).
This is why a normal case trace shows no proposal exchange at all: submitting a report without a counter-proposal is tacit acceptance of the receiver's default.

**A local decision to negotiate.** The `propose_embargo`, `propose_embargo_revision`, and `terminate_embargo` triggers.

**An inbound overture.** Either an Embargo Proposal (EP) carrying terms, or an `Invite(EmbargoEvent)` asking one actor for its consent.
These are the two flows the response decision handles, and they resolve at different scopes: answering an EP moves the case's EM state, answering an invitation moves only that Participant's PEC state (EMB-15).

**A deadline passing.** An invitation carries a respond-by instant, and an unanswered invitation eventually becomes a refusal — see [Inaction is an answer](#inaction-is-an-answer) below.

---

## The mechanical path

Every EM transition runs through one service.
A behavior tree node never assigns `case.current_status.em` and saves the case as a shortcut (EMB-18-001).
The reason is that a transition is not a field write.
It has to be validated against the state machine, and a failed validation must stop the node rather than log a warning and write anyway (EMB-18-002).

The transitions themselves are small and fixed:

| Message received | Precondition | Result |
|---|---|---|
| Embargo Proposal (EP) | `EM.NONE` | `EM.PROPOSED`, acknowledge (EMB-01-001) |
| Embargo Acceptance (EA) | `EM.PROPOSED` | `EM.ACTIVE`, acknowledge (EMB-02-001) |
| Embargo Rejection (ER) | `EM.PROPOSED` | back to `EM.NONE`, acknowledge (EMB-06-001) |
| Embargo Revision (EV) | `EM.ACTIVE` | `EM.REVISE`; the active embargo stays in force (EMB-03-001) |
| Embargo Termination (ET) | `EM.ACTIVE` or `EM.REVISE` | `EM.EXITED`, immediately |

`EM.REVISE` is worth a second look.
A revision under negotiation does not suspend the embargo — the existing terms remain binding until the revision is accepted.
That is what makes renegotiation safe, and it is why the recommended practice is to accept and then revise rather than to counter-propose.

---

## Which messages move consent

Consent has no messages of its own (MSM-07-001).
Every Participant Embargo Consent transition is a side effect of an EM activity, an internal cascade, or a deadline, and the case manager records it; a Participant never declares its own consent state.

| Activity | Effect on the case's EM state | Effect on consent |
|---|---|---|
| Embargo Proposal (EP), `Invite(Event)` on the case | `NONE` to `PROPOSED`; a further proposal leaves it `PROPOSED` | the invited Participant moves from `UNBOUND`, `DECLINED` or `LAPSED` to `INVITED` (MSM-07-002) |
| Embargo Acceptance (EA) or Embargo Revision Acceptance (EC), `Accept(Invite(Event))` | from the case owner: `PROPOSED` (EA) or `REVISE` (EC) to `ACTIVE` | the accepting Participant moves to `SIGNATORY` (MSM-07-003) |
| Embargo Rejection (ER), `Reject(Invite(Event))` | from the case owner: `PROPOSED` to `NONE` | the rejecting Participant moves to `DECLINED` (MSM-07-004) |
| Embargo Revision Rejection (EJ), `Reject(Invite(Event))` | from the case owner: `REVISE` back to `ACTIVE`; the prior terms stand | the rejecting Participant moves to `DECLINED` (MSM-07-004) |
| Embargo Revision (EV) | `ACTIVE` to `REVISE` | every `SIGNATORY` moves to `LAPSED`, with no further message (MSM-07-005) |
| Embargo Termination (ET) | `ACTIVE` or `REVISE` to `EXITED` | every Participant returns to `UNBOUND`, with no further message (MSM-07-006) |
| Invitation deadline passes | none | `INVITED` or `LAPSED` moves to `DECLINED`, recorded in the case ledger (MSM-07-007) |

One activity can therefore move both scopes at once: an Accept from the case owner activates the embargo *and* makes the owner a signatory.
A `SIGNATORY` that rejects is withdrawing its own consent: its record moves to `DECLINED` ([§9.2](../../../reference/vultron-spec/index.md#92-transitions-and-guards)), and the case's embargo does not change, because only the case owner's reject moves EM (MSM-07-004).
The full consent transition table is in [§9.2 of the specification](../../../reference/vultron-spec/index.md#92-transitions-and-guards).

---

## The condition that overrides everything

If the vulnerability is public, an exploit is public, or attacks have been observed, there is nothing left to embargo.

This is not a preference the negotiation weighs.
It is mandatory, and it applies at every point in the lifecycle:

- A proposal MUST be refused with ER, regardless of any other assessment (EMB-01-002).
- An EA MUST NOT move the case to `ACTIVE`; the actor emits ER instead (EMB-02-002).
- An EV arriving while the case is public MUST produce ET — terminate now, do not negotiate (EMB-03-003).
- An actor sitting at `EM.PROPOSED` that *observes* the case go public MUST abandon the proposal, return to `EM.NONE`, and emit ER (EMB-16-001).
- An actor at `EM.EXITED` MUST NOT seek or accept a new embargo for a public case (EMB-13-002).

EMB-16-001 is the one implementations forget, because it is not triggered by a message.
Nothing arrives to prompt it.
The actor's own state changed, and the obligation follows from that.

---

## Where judgment enters

This is the richest call-out surface in the protocol, because almost every embargo question is a policy question.
Each point below names its capability shape from the [ADR-0024](../../../adr/0024-coordination-agent-taxonomy.md) taxonomy, and each is answered by an injected backend rather than by logic inside the tree ([ADR-0025](../../../adr/0025-call-out-point-abstraction-layer.md)).
Their service contracts are catalogued in the [Capability Model](../../capability_model/index.md#embargo-management).

**Deciding to negotiate.** `WantToProposeEmbargo` (Evaluator) asks whether to propose at all; `SelectEmbargoOfferTerms` (Composer) asks what terms; `StopProposingEmbargo` (Evaluator) asks whether to give up after a refusal.
Their deterministic defaults differ, and the differences encode a recommended posture: propose by default, and do not give up by default.

**Responding to an overture.** `EvaluateEmbargoProposal` (Evaluator) asks whether the terms are acceptable.
Its default is to accept (EMB-15-001, EMB-15-005) — the protocol's position is that a well-formed overture deserves agreement unless there is a reason otherwise.

`WillingToCounterEmbargoProposal` (Evaluator) asks whether to counter instead. Its default is *not* to counter (EMB-15-003), which is the same recommendation in a different form: accept and then revise, rather than trade proposals. Countering introduces no new mechanism — it re-uses the ordinary proposal path and leaves the case at `PROPOSED`.

**Staying in.** `CurrentEmbargoAcceptable` (Evaluator) asks whether the active embargo is still acceptable as circumstances change.

**Getting out early.** `ExitEmbargoWhenFixReady`, `ExitEmbargoWhenDeployed`, and `ExitEmbargoForOtherReason` (all Evaluators) each ask whether a condition now warrants ending the embargo.
All three default to *no*, and the defaults are ordered.
A fix being deployed is a more plausible reason to exit than a fix merely being ready, and "some other reason" is the least plausible of all.
An implementer reading only the code sees three similar nodes; the probabilities are where the editorial judgment is recorded.

**Authorizing the response.** Deciding how the *case* responds to an overture is not every Participant's call.
The response seam puts a case-owner check first: when the deciding actor holds `CVDRole.CASE_OWNER`, its stated response is authoritative and no approval is sought (EMB-15-002, EMB-15-006).
A non-owner — typically a case manager handling the overture on the owner's behalf — routes through `CaseOwnerApprovesEmbargoResponse` (Evaluator, EMB-15-007).

**Reacting to the outcome.** `OnEmbargoAccept`, `OnEmbargoReject`, and `OnEmbargoExit` are Actuators.
They are notification and integration hooks that fire after the transition and confirm a side effect, producing nothing the protocol reads.

!!! note "A default is not a requirement"

    Every "defaults to accept" above describes the stub backend a deployment gets
    when it wires nothing (BT-23-001). None of them is a protocol obligation to
    accept. The one place the protocol *does* mandate an answer is the
    public/exploit/attacks condition, and that is enforced independently of any
    call-out outcome (EMB-15-004).

---

## Inaction is an answer

An `Invite(EmbargoEvent)` carries a respond-by instant, and silence past it is treated as a refusal — the **pocket veto**.
A Participant at `INVITED` or `LAPSED` that does not answer within the window moves to `DECLINED`.

The window has two forms and they are one mechanism, not two ([ADR-0065](../../../adr/0065-embargo-invite-rsvp-deadline.md)).
When the invitation carries an explicit `Invite.end_time`, that value governs (CM-28-002).
When it does not, the policy default applies — seven days, measured from the invitation's `published` timestamp (EP-07-001).

There is a floor. An inviting actor must not send a window shorter than the configured minimum, defaulting to 72 hours (EP-07-002).
A receiving actor that gets one anyway clamps the deadline up to the minimum and logs the clamp; it does **not** reject the invitation as malformed (EP-07-003, EP-07-004, EP-07-005).
Refusing a too-short invitation would punish the invitee for the inviter's error.

A late `Accept` is never refused merely for being late (EMB-17-001).
The case manager instead asks whether the accepted embargo is still the case's current one, and the three answers are all different:

| What the late Accept refers to | What the case manager does |
|---|---|
| The case's current embargo | Honor it; record the Participant as SIGNATORY, exactly as for an on-time Accept (EMB-17-002) |
| A superseded embargo | Send a fresh invitation carrying the current terms. Do **not** record consent to terms the actor never saw (EMB-17-003, EMB-17-005) |
| An embargo the case no longer has | Acknowledge as a no-op. Do not invite, and do not remove the actor from the case (EMB-17-004, EMB-17-007, EMB-17-008) |

Note what none of the three rows does: remove the accepting actor.
Answering late is not a protocol violation.

---

## What the case learns

Embargo messages route through the case manager like every other case-scoped message (PCR-08-001).
A Participant does not announce its embargo stance to the other Participants itself.

Teardown is the exception worth naming, because its addressing is prescribed.
The `Announce(EmbargoEvent)` that follows a teardown must be authored by the actor holding `CVDRole.CASE_MANAGER` and addressed to every Participant *except* the announcing actor — never to the case manager itself (EMB-19-001).
When the case manager is the only Participant, the announcement is skipped rather than sent with an empty recipient list (EMB-19-002).

On entering `EM.EXITED`, Participant consent states are reset to reflect that the embargo has ended (EMB-13-001).
The embargo is over for everyone at once, which is the one thing about the EM scope that is genuinely global.

---

## What conformance requires

| Requirement | Obligation |
|---|---|
| [EMB-01-002](../../../reference/specs/protocol.md#emb-01) | A proposal MUST be refused with ER when the case is public, exploited, or attacked |
| [EMB-02-002](../../../reference/specs/protocol.md#emb-02) | An EA MUST NOT activate an embargo on a public case; emit ER |
| [EMB-03-001](../../../reference/specs/protocol.md#emb-03) | An EV in `EM.ACTIVE` MUST move to `EM.REVISE`, leaving the active embargo in force |
| [EMB-06-001](../../../reference/specs/protocol.md#emb-06) | An ER in `EM.PROPOSED` MUST return the case to `EM.NONE` |
| [EMB-13-002](../../../reference/specs/protocol.md#emb-13) | An actor at `EM.EXITED` MUST NOT accept a new embargo for a public case |
| [EMB-15-002](../../../reference/specs/protocol.md#emb-15) | The response seam MUST bypass approval when the deciding actor is the case owner |
| [EMB-16-001](../../../reference/specs/protocol.md#emb-16) | An actor at `EM.PROPOSED` observing the case go public MUST abandon the proposal and emit ER |
| [EMB-17-001](../../../reference/specs/protocol.md#emb-17) | A late `Accept` MUST NOT be refused solely because the deadline passed |
| [EMB-18-001](../../../reference/specs/architecture.md#emb-18) | Every EM transition MUST route through the embargo lifecycle service |
| [EMB-19-001](../../../reference/specs/protocol.md#emb-19) | A teardown announcement MUST be authored by the case manager and exclude it from the recipients |
| [EP-04-001](../../../reference/specs/protocol.md#ep-04) | A default embargo applied at case creation MUST produce `EM.ACTIVE`, not `EM.PROPOSED` |
| [EP-07-003](../../../reference/specs/protocol.md#ep-07) | A sub-minimum RSVP deadline MUST be clamped up, not rejected |

---

## Further reading

- [Embargo Management Behaviors](../em_bt.md) — the original design trees for proposal, evaluation, and termination
- [Propose case](propose-case.md) — where the default embargo comes from
- [Embargo Management Handlers](../../../reference/behaviors/em_handlers.md) — the trees the reference implementation builds today
- [EM Process Model](../../process_models/em/index.md) — the case-level embargo model, with its [formal definition](../../process_models/em/formal_model.md)
- [Glossary](../../../reference/glossary.md) — Participant, call-out point, capability shape, embargo consent
