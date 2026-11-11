---
description: >
  The answer to "Vultron doesn't do X": every decision the protocol leaves to
  your organization is a call-out point where your own system plugs in.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 300
page_type: explanation
subject: protocol
---

# Capability Model

{% include-markdown "../../includes/specification_governs.md" %}

Vultron does not decide whether a report is credible, how urgent a case is, or when an advisory is ready to publish.
Each of those decisions is a **call-out point**: a place where the protocol stops and asks a system you run.
This page answers the objection "Vultron doesn't do X" by naming, for each X, the call-out point where your system does it.
It then describes the four shapes a call-out point can take, the Sentinel call-in pattern, and a catalog of every named capability, generated from the code.

---

## Vultron doesn't do X: your system does

Every objection below is true, and each is true by design.
The protocol coordinates the case; the judgment, the data, and the side effects come from your systems.

| "Vultron doesn't…" | Where your system plugs in | Shape |
|---|---|---|
| judge whether a report is credible or valid | [EvaluateReportCredibility, EvaluateReportValidity](#report-validation) | Evaluator |
| prioritize cases | [EvaluateCasePriority](#report-prioritization), the natural home for a Stakeholder-Specific Vulnerability Categorization (SSVC) decision | Evaluator |
| decide which cases to host for others | [EvaluateCaseProposal](#case-admission) | Evaluator |
| set or accept embargo terms | [SelectEmbargoOfferTerms, EvaluateEmbargoProposal](#embargo-management) | Evaluator |
| assign Common Vulnerabilities and Exposures (CVE) IDs | [IdAssigned, InScope, AssignId](#cve-vulnerability-id-assignment) | Retriever, Evaluator, Composer |
| develop or deploy fixes | [CreateFix](#fix-development), [DeployFix](#fix-and-mitigation-deployment) | Composer, Evaluator |
| know whether an exploit exists | [HaveExploit, FindExploit](#exploit-management) | Retriever |
| write or publish advisories | [DraftAdvisoryArtifact, ReviewAdvisoryDraft, SubmitAdvisoryArtifact](#publication) | Composer, Evaluator, Actuator |
| know who else belongs in the case | a [Sentinel](#the-sentinel-call-in-pattern) that calls `suggest-actor-to-case`, or [IdentifyVendors, IdentifyCoordinators, InjectParticipant](#reporting-to-others) in the simulator | Retriever, Actuator |
| watch threat feeds | [MonitorAttacks, MonitorExploits, MonitorPublicReports](#threat-monitoring), or a [Sentinel](#the-sentinel-call-in-pattern) that reports what it sees | Retriever |
| update your ticketing system | [OnAccept, OnDefer](#report-prioritization) and [PreCloseAction](#leaving-a-case) | Actuator |

The plug-in seam is the same in every row.
During development and simulation, each call-out point is filled by a **fuzzer node**: a stub that returns a random success or failure.
You replace the stub with a **capability implementation** that answers the question for real.
[Wiring a Capability into the Reference Implementation](../../howto/wire_capability.md) walks through that replacement for one call-out point.

---

## Why the protocol asks instead of deciding

Much of the Coordinated Vulnerability Disclosure (CVD) process is mechanical: send a message, record a state, wait for a reply.
Vultron automates that part with [behavior trees (BTs)](../behavior_logic/index.md), which run as protocol activities arrive.

The remaining steps need judgment that depends on your organization's policy, data, and tools.
A protocol that made those decisions would impose one organization's policy on every participant.
So the BT reaches a call-out point, asks, and continues with the answer.

The line falls between two kinds of decision.
A **mechanical** decision reads recorded state and applies a rule: is this participant already in the Valid state, does this case exist in this actor's store, does the state machine permit this transition.
Two conformant implementations reach the same answer, because the rule and the inputs are both fixed.
A **delegated** decision has no answer in the record: whether a report is credible, whether embargo terms are acceptable, whether a vulnerability merits a CVE identifier.
The protocol marks where the decision is made and defines what an answer looks like, but it does not supply the answer.
Two conformant implementations may legitimately differ here; every call-out point is a delegated decision.

!!! note "A question for another actor is never a call-out point"

    A call-out point asks a service *you* run, so it is answered while the BT is still running (BT-18-011).
    A question that needs a **decision from another actor in the case** is never a call-out point (BT-18-014).
    It is a **protocol ask**: the actor sends a request, finishes, and acts on the reply when it arrives ([ADR-0080](../../adr/0080-protocol-asks-not-suspended-behaviors.md)).
    An example is whether the Case Owner permits a change to the case's agreed state.
    No service can answer that on the owner's behalf, and the answer may take days.
    A call-out point in its place could only ever answer *no*, because no answer exists when the BT asks.
    See [Protocol Event Flow](../protocol_flow.md#when-an-actor-must-ask-permission).

---

## The two integration surfaces

An external service interacts with Vultron in one of two directions.

**Call-out**: Vultron calls *you*.
The BT reaches a call-out point, packages the question as a structured payload, and waits for a structured answer.
Your service decides and responds.

**Call-in**: you call *Vultron*.
Your service monitors something outside the case, such as a timer, a threat feed, or a deployment system.
When a condition is met, it calls a Vultron trigger, and Vultron acts on it.

Every capability uses the call-out surface.
The call-in surface belongs to the [Sentinel call-in pattern](#the-sentinel-call-in-pattern) and to any other external system that acts on a case.

---

## Three-level taxonomy

Every call-out point fits a three-level hierarchy:

**Shape** → **Capability** → **Capability implementation**

| Level | What it is | Example |
|---|---|---|
| **Shape** | The abstract type of interaction: what the service receives, what it returns, and how the BT uses the result | Evaluator |
| **Capability** | A specific named call-out point with its own input and output contract | `EvaluateCveEligibility` |
| **Capability implementation** | The concrete service you build that fulfills a capability at runtime | A microservice that applies the CVE Numbering Authority (CNA) Operational Rules and returns pass or fail |

Think of the shape as a job description, the capability as the open role, and your implementation as the service hired into that role.

Some capabilities are sub-steps of a larger workflow.
For example, `EvaluateCveEligibility` is a step within the broader [ID assignment](#cve-vulnerability-id-assignment) workflow.
Most capabilities are not nested.

!!! note "Design decisions"
    The taxonomy is defined in [ADR-0024](../../adr/0024-coordination-agent-taxonomy.md), and [ADR-0097](../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md) reduces it to four shapes.
    The factory-injection pattern is defined in [ADR-0025](../../adr/0025-call-out-point-abstraction-layer.md).

---

## Every answer is yes, no or error

Whatever its shape, a capability gives one answer each time the BT asks: a verdict of *yes*, *no* or *error*, and the data its capability declares for that verdict ([ADR-0183](../../adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md)).

- *Yes* carries the capability's declared outputs.
  The BT writes them to its shared state and goes on.
- *No* is a decision against the request.
  It carries a refusal payload: a human-readable reason at minimum, and any structured refusal fields the capability declares.
  The BT writes the payload to the declared refusal keys and takes its "declined" path.
- *Error* means the capability could not decide or act.
  It carries diagnostics for the logs only.
  The BT does not judge the message: the message stays in holding, and the next delivery asks again.

One place in the reference implementation, the call-out seam, turns the answer into BT behavior.
No BT reads the answer itself, so a BT still branches only on success and failure.

**When to answer error instead of no.**
Answer *no* only for a decision you made about this request, because the BT treats it as permanent.
An unreachable service, a rejected credential, a timeout, or a side effect you cannot confirm is *error*.
A capability that answers *no* for an outage turns the outage into a permanent refusal, such as a case proposal declined for good because the policy service was down.

The [Wiring a Capability](../../howto/wire_capability.md#a-backend-answers-yes-no-or-error) guide shows the answer in code.

---

## The four shapes

There are exactly four capability shapes (BT-18-013).
The normative contracts are in [Annex G Capability Shapes in the protocol specification](../../reference/vultron-spec/annex-g-capability-shapes.md#annex-g-capability-shapes-i); this section explains how each one behaves.

### Evaluator

**You receive:** a situation, such as case context, report details, or embargo terms.
**You return:** a structured recommendation, typically a decision plus optional reasoning.
**The BT uses it to:** gate what happens next.

If you answer *yes* with "needs revision," the BT routes to the revision branch.
If you answer *no*, with your reason, the pipeline stops.
*No* is the only way to stop it: an Evaluator that answers *yes* with a "rejected" value in its output does not block the next step (BT-18-007).
The BT does not care whether the judgment came from a human reviewer, a rules engine, or a large language model (LLM); it needs a structured answer it can act on.

Evaluators carry human-level judgment.
Examples are assessing whether a report is credible, deciding whether an embargo proposal is acceptable, and checking whether a vulnerability meets CVE assignment criteria.

### Retriever

**You receive:** a query.
**You return:** structured facts the BT needs to proceed.
**The BT uses it to:** supply inputs for downstream steps.

Retrievers are data lookups.
Examples are whether a CVE ID already exists for this vulnerability, whether a public exploit database lists an exploit, and what the current SSVC decision is for this case.
A yes-or-no question the protocol asks is also a Retriever, never a Sentinel.
When the case or the actor's own records already hold the fact, the tree reads it there and does not ask the Retriever (BT-18-039).
A Retriever is asked only for what the case and the actor's records do not already hold, so any cache of what it fetches is the Retriever's own (BT-18-029).

Most Retrievers can be wired directly to an API or database without human involvement.

### Composer

**You receive:** context, such as case details, draft content, and constraints.
**You return:** a content artifact, such as a document, report body, advisory text, or fix description.
**The BT uses it to:** pass the artifact to the next stage, such as review or publication.

The Composer writes its output into the BT's shared state, the **blackboard**, so later steps can read it.
Examples are drafting a security advisory, writing a vulnerability report body, and preparing a fix description.

!!! tip "Composer vs. Actuator"
    If your service *generates* a document, it is a Composer.
    If it *submits* that document to a publication platform, it is an Actuator.

### Actuator

**You receive:** a trigger, a signal that something should happen, with the one target it acts on and an idempotency id.
**You return:** *yes* when the side effect is confirmed, *no* when you decided not to act, and *error* when you could not confirm it; never a content artifact.
**The BT uses it to:** confirm that a side effect was executed.

Actuators fire side effects in external systems.
Examples are posting an embargo acceptance to a collaboration platform, submitting an advisory to a publication pipeline, and updating a ticket when a report is closed.
Each call acts on one target, and a re-run of the same act gives the call the same idempotency id, so an Actuator that keys its side effect on that id never repeats it ([Wiring a Capability](../../howto/wire_capability.md#an-actuator-acts-on-one-target-and-is-safe-to-repeat)).

---

## The Sentinel call-in pattern

A **Sentinel** is not a capability shape (BT-18-013, [ADR-0097](../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md)).
It watches a condition over time and, when the condition is met, acts on its own initiative.
The protocol never asks it anything, so it has no call-out point, no blackboard contract, and no backend factory.

The discriminator is *who initiates*, not where the information comes from.
A capability is asked and answers within the tick that asks.
A Sentinel decides for itself that the moment has come.

A Sentinel takes one of two forms:

- a case **Participant**, typically holding the `CVDRole.OBSERVER` role, that learns case state through ordinary ledger replication (`Announce(CaseLedgerEntry)`) and acts by sending ordinary protocol messages, visible to every participant;
- operator-side machinery with no case identity, which drives one actor through its [call-in triggers](#call-in-triggers) and is invisible to the case.

Examples are an embargo timer that calls `terminate-embargo` when the agreed end date passes, a threat-feed monitor that reports active attacks, and a deployment monitor that reports a fix as deployed.
A Sentinel is a long-running monitor, so building one needs different infrastructure from building a call-out responder: a way to observe, a decision rule, and something to call.

---

## Capability hierarchy

The catalog below lists every named capability, by domain.
Use it to identify which capability you are building toward.

Every entry is a call-out point: Vultron asks, and your capability answers.
A Sentinel never appears here, because it is a call-in pattern that watches a condition and calls a trigger on its own initiative (see [The Sentinel call-in pattern](#the-sentinel-call-in-pattern)).

The tables are generated from the capability declarations in `vultron/core/behaviors/call_out/capabilities/` each time the site is built.
Each row gives these facts about one capability:

- **Capability**: the name a BT gives to the backend factory.
- **Shape**: the shape base class that the declaration subclasses.
- **Asks**: the first paragraph of the declaration's docstring.
- **Reads**: the input ports that the capability reads.
- **Writes on *yes***: the output ports that the capability writes when it answers *yes* (BT-18-012).

"Verdict only" means the capability writes nothing, and its *yes* or *no* is the whole answer (BT-18-010).
A capability's simulation stand-in, its fuzzer node, sits at the same module path under `vultron/demo/fuzzer/`.

### Report Validation

*See also: [Validation behavior](../behavior_logic/rm_validation_bt.md)*

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("report_management.validate"))
```

### Report Prioritization

*See also: [Prioritization behavior](../behavior_logic/rm_prioritization_bt.md)*

`EvaluateCasePriority` is the natural home for a Stakeholder-Specific Vulnerability Categorization (SSVC) decision.
`OnAccept` and `OnDefer` are the hooks that update your ticketing system when a report is accepted or deferred.

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("report_management.prioritize"))
```

### Case Admission

*See also: [Propose case behavior](../behavior_logic/use-cases/propose-case.md), [Case Initialization](../case_lifecycle/case_initialization.md)*

`EvaluateCaseProposal` is the admission decision a case actor service makes on an inbound `Create(CaseProposal)`, and the only place admission policy lives.
Answering *no* sends `Reject(CaseProposal)`; the default admits.
An unreachable policy service answers *error*, which leaves the proposal in holding rather than declining it.

Build this one if you run a case actor service for others.
The [Propose case](../behavior_logic/use-cases/propose-case.md#where-judgment-enters) page carries the full reasoning: what the policy decides, why the decision sits ahead of every write, and the two ways a refusal gate can be defeated.

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("case_management"))
```

### Embargo Management

*See also: [Embargo behaviors](../behavior_logic/em_bt.md), [Evaluate proposed embargo](../behavior_logic/em_eval_bt.md), [Propose embargo](../behavior_logic/em_propose_bt.md), [Terminate embargo](../behavior_logic/em_terminate_bt.md)*

`CaseOwnerApprovesEmbargoResponse` gates the answer that a participant other than the Case Owner gives to an embargo proposal.
The Case Owner's own answer does not ask it.
A backend can answer it only from the deciding actor's own policy: a decision that only the Case Owner can make is a protocol ask, not a call-out point (BT-18-014).
Whether the active embargo stays acceptable as conditions change (`CurrentEmbargoAcceptable`) is open in [#1943](https://github.com/CERTCC/Vultron/issues/1943).
The embargo's end time is in the case, so a BT reads it there instead of asking `EmbargoTimerExpired` (BT-18-039; see [Still open](#still-open)).

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(
    render_capability_table(
        "embargo.proposal", "embargo.evaluation", "embargo.termination"
    )
)
```

### CVE / Vulnerability ID Assignment

*See also: [ID Assignment behavior](../behavior_logic/id_assignment_bt.md)*

These capabilities are the sub-steps of one ID assignment workflow.
`EvaluateCveEligibility` is a single judgment call that applies the CNA Operational Rules eligibility criteria as one unit.
The publication condition stays a separate protocol check just before it.
`RequestId` asks an outside CNA for an ID when this actor is not the appropriate authority.

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(
    render_capability_table(
        "report_management.assign_vul_id.eligibility",
        "report_management.assign_vul_id.assignment",
    )
)
```

### Fix Development

*See also: [Fix Development behavior](../behavior_logic/fix_dev_bt.md)*

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("report_management.develop_fix"))
```

### Fix and Mitigation Deployment

*See also: [Deployment behavior](../behavior_logic/deployment_bt.md)*

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("report_management.deploy_fix"))
```

### Exploit Management

*See also: [Exploit Acquisition behavior](../behavior_logic/acquire_exploit_bt.md)*

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("report_management.acquire_exploit"))
```

### Publication

*See also: [Publication behavior](../behavior_logic/publication_bt.md), [Reporting behavior](../behavior_logic/reporting_bt.md)*

`ReviewAdvisoryDraft` answers *yes* with `needs_revision` to route the draft to revision, or *no* to block submission entirely.

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(
    render_capability_table(
        "report_management.publication.intents",
        "report_management.publication.advisory",
    )
)
```

### Leaving a Case

*See also: [Closure behavior](../behavior_logic/rm_closure_bt.md)*

An actor closes its part in a case by calling the `leave-case` trigger, which sends `Leave(VulnerabilityCase)` to the CASE_MANAGER.
`leave-case` runs `PreCloseAction` before it sends the Leave, for every caller, so it is where you close your own ticket.
A failure stops the trigger with nothing sent.
`OtherCloseCriteriaMet` is superseded, because the decision to close is the act of calling `leave-case` ([ADR-0145](../../adr/0145-a-case-is-left-through-the-leave-case-trigger-whose-actor-runs-its-pre-close-step-first.md)).

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("report_management.close_report"))
```

### Reporting to Others

*See also: [Reporting behavior](../behavior_logic/reporting_bt.md)*

These capabilities find and notify the other parties a report should reach.
They come from the simulator's report-to-others BT.
To find who else belongs in a case, use a Sentinel that calls `suggest-actor-to-case` or `invite-actor-to-case` ([ADR-0047](../../adr/0047-report-to-others-sentinel-over-inline-bt.md)).

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(
    render_capability_table(
        "report_management.report_to_others.recipients",
        "report_management.report_to_others.injection",
    )
)
```

### Threat Monitoring

*See also: [Monitoring Threats behavior](../behavior_logic/monitor_threats_bt.md), [#1845](https://github.com/CERTCC/Vultron/issues/1845), [#1856](https://github.com/CERTCC/Vultron/issues/1856)*

Each capability here answers a question the BT asks once.
A feed watcher that reports what it sees as it happens is a [Sentinel](#the-sentinel-call-in-pattern) instead.

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("report_management.monitor_threats"))
```

### Messaging

*See also: [Other message behaviors](../behavior_logic/msg_other_bt.md)*

```python exec="true" idprefix=""
from vultron.metadata.docs.capability_catalog import render_capability_table

print(render_capability_table("messaging"))
```

---

## Call-in triggers

These are the actions an external system can invoke on a Vultron actor, each at `POST /actors/{actor_id}/trigger/{behavior}`.
An operator-side Sentinel uses them to act when a monitored condition fires, and any other external system may call them directly.
The [Trigger API Reference](../../reference/trigger-api.md) gives each endpoint's request and response.

### Report lifecycle

- `submit-report` — create and offer a vulnerability report to a recipient
- `ack-report` — acknowledge a received report to its sender
- `validate-report` — mark a received report as valid
- `invalidate-report` — mark a received report as invalid
- `reject-report` — hard-close a report before validation completes; it also sends `Reject(Offer(VulnerabilityReport))`, so it fails once a case holds the report, which by default happens on receipt; from then on you leave the case with `leave-case`

### Case management

- `create-case` — create a local vulnerability case
- `engage-case` — accept a case (transitions to ACCEPTED state)
- `defer-case` — defer a case (transitions to DEFERRED state)
- `add-report-to-case` — link a report to an existing case
- `add-object-to-case` — ask the CASE_MANAGER to add an existing report or note to a case; other object types are refused
- `leave-case` — leave a case: runs your `PreCloseAction`, then sends `Leave(VulnerabilityCase)` to the CASE_MANAGER; the Case Owner's Leave closes the case, so it fails while the case has an active embargo, and you terminate the embargo first

### Embargo

- `propose-embargo` — propose a new embargo
- `accept-embargo` — accept a pending embargo proposal, or the embargo in force by naming the Invite you received for it
- `reject-embargo` — reject a pending embargo proposal, or the embargo in force by naming the Invite you received for it
- `propose-embargo-revision` — propose a revision to an active embargo
- `terminate-embargo` — end the active embargo immediately

### Participants and actors

- `suggest-actor-to-case` — recommend another actor to the Case Owner
- `invite-actor-to-case` — directly invite an actor to a case
- `accept-case-invite` / `reject-case-invite` — respond to a case invitation
- `accept-actor-recommendation` / `reject-actor-recommendation` — approve or decline a suggested actor (Case Owner only)
- `offer-case-participant-role` — offer a CVD role to another actor
- `offer-case-ownership-transfer` / `accept-case-ownership-transfer` / `reject-case-ownership-transfer` / `withdraw-case-ownership-transfer` — transfer case ownership, decline the transfer, or withdraw an open offer
- `add-on-behalf-status` — as CASE_MANAGER or Case Owner, record a vendor's awareness (the *V* event) on behalf of a vendor participant, typically an invitee that has not yet replied, or a deployer's deployment (the *D* event) on behalf of a deployer participant that has accepted, deferred or closed the case, when the evidence is in hand; the target must already be a participant, because a status update never adds an actor to the case (invite the actor first); fix readiness is never recorded on another actor's behalf

### Typical Sentinel patterns

| Sentinel condition | How it acts |
|---|---|
| Embargo end date passes | Calls `terminate-embargo` with the reason `END_TIME_REACHED` |
| Active attack observed in a threat feed | As a case Participant, sends `Add(ParticipantStatus)` recording the attack (the [*A* event](../process_models/cs/cs_model.md#the-attacks-observed-substate-a-a)); no trigger endpoint covers this yet ([#1845](https://github.com/CERTCC/Vultron/issues/1845)) |
| Fix confirmed deployed | As a case Participant, sends `Add(ParticipantStatus)` recording deployment (the [*D* event](../process_models/cs/cs_model.md#the-fix-deployed-substate-d-d)) |
| New party identified by a discovery service | Calls `suggest-actor-to-case` or `invite-actor-to-case` |

---

## Settled and open design questions

You can build the core logic of a capability implementation now.
The questions below determine the wiring details.

### Settled

**What a capability must define** ([#2452](https://github.com/CERTCC/Vultron/issues/2452)).
A named capability declares its blackboard contract as typed input and output ports, on a declaration owned by the core layer (BT-18-012, [ADR-0097](../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md)).
Every capability has its declaration in `vultron/core/behaviors/call_out/capabilities/`, and its simulation stand-in binds to it (BT-18-021).

**How a capability implementation is invoked** ([#2453](https://github.com/CERTCC/Vultron/issues/2453)).
A backend answers synchronously, within the tick that asks, with *yes*, *no* or *error*, and never returns RUNNING (BT-18-011, [ADR-0080](../../adr/0080-protocol-asks-not-suspended-behaviors.md), [ADR-0183](../../adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md)).
It also answers within a time budget that each actor configures (BT-18-015, BT-18-026).
An answer that takes longer is discarded and reported as an internal error that names the node (BT-18-027).
A decision that takes days is not a call-out point: it is a request to another actor, or a Sentinel.

**What a deployment that supplies nothing gets.**
Every call-out point is built through a backend factory, and the default backend is a deterministic one, so a deployment that plugs in nothing still runs (BT-18-004, BT-23-001, [ADR-0025](../../adr/0025-call-out-point-abstraction-layer.md)).
The default is usually the permissive answer, on the reasoning that a stub should not silently hold up progress.
One class of gate inverts that.
Where a permissive default would let a party other than the Case Owner force the adoption of a case state or the teardown of an embargo, the default is the conservative answer instead (BT-23-012, [ADR-0076](../../adr/0076-security-significant-gates-default-require-case-owner-approval.md)).
So when a page says a call-out point "defaults to accept", that describes the stub, not a protocol requirement to accept.

**What the shape classes are called in code** ([#2454](https://github.com/CERTCC/Vultron/issues/2454)).
The shape base classes are `EvaluatorCapability`, `RetrieverCapability`, `ComposerCapability`, and `ActuatorCapability`, in `vultron/core/behaviors/call_out/capability.py` ([ADR-0097](../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md)).
Each named capability is declared once in core, as a subclass of one of them that declares its blackboard contract as typed ports, and its fuzzer node subclasses that declaration (BT-18-012, BT-18-021).
The older names, such as `EvaluatorCallOutPoint`, still import from `vultron/demo/fuzzer/call_out_point.py` and name the same classes.

### Still open

**Should a Sentinel end embargoes on time? ([#1893](https://github.com/CERTCC/Vultron/issues/1893))**
This is no longer a choice of shape for `EmbargoTimerExpired`.
If a BT asks "has the end date passed?" and gets only yes or no, it asks a Retriever.
A synchronous query from the BT is always a Retriever, never a Sentinel (BT-18-006).
The end time is in the case's embargo register, so a BT reads it there instead of asking (BT-18-039).
The CASE_MANAGER ends the embargo the next time it handles the case after the end time (EMB-13-003).
What stays open is whether something should end an embargo at its end time when nothing else happens in the case.
That is a Sentinel (BT-18-013).
No BT asks it: it watches the clock, and calls `terminate-embargo` with the reason `END_TIME_REACHED` on its own initiative.
Who runs it, and how it authenticates to the trigger, are among the Sentinel design questions in [#2450](https://github.com/CERTCC/Vultron/issues/2450).

---

## Choosing what to build

1. **Find the objection you are answering.**
   Start from [the table above](#vultron-doesnt-do-x-your-system-does), or browse the [capability hierarchy](#capability-hierarchy) for a domain that matches your organization's tooling.
2. **Identify the direction.**
   If Vultron asks and you answer, you are building one of the four shapes.
   If you watch something and act when it happens, you are building a Sentinel.
3. **Check the GitHub issues.**
   Several capabilities already have open idea issues under [epic #1147](https://github.com/CERTCC/Vultron/issues/1147).
   If one fits, comment on it.
   If yours is not listed, file a new issue with the `idea` label.
4. **Design the contract.**
   Decide what context your capability needs from Vultron and what structured answer it returns.
5. **Wire it in and test it.**
   Replace the fuzzer node with your backend, following [Wiring a Capability into the Reference Implementation](../../howto/wire_capability.md), and run it against the existing BT structure.

{% include-markdown "../../start/_paths/connect-your-tracker/topics__capability_model__index.md" %}

{% include-markdown "../../start/_paths/coordinate-cases/topics__capability_model__index.md" %}

{% include-markdown "../../start/_paths/how-vultron-works/topics__capability_model__index.md" %}
