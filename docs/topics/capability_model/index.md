---
description: >
  The answer to "Vultron doesn't do X": every decision the protocol leaves to
  your organization is a call-out point where your own system plugs in.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 300
---

# Capability Model

Vultron does not decide whether a report is credible, how urgent a case is, or when an advisory is ready to publish.
Each of those decisions is a **call-out point**: a place where the protocol stops and asks a system you run.
This page answers the objection "Vultron doesn't do X" by naming, for each X, the call-out point where your system does it.
It then describes the four shapes a call-out point can take, the Sentinel call-in pattern, and the full catalog of known call-out points.

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
| develop or deploy fixes | [CreateFix](#fix-development), [DeployFix](#fix-deployment) | Composer, Evaluator |
| know whether an exploit exists | [HaveExploit, FindExploit](#exploit-management) | Retriever |
| write or publish advisories | [DraftAdvisoryArtifact, ReviewAdvisoryDraft, SubmitAdvisoryArtifact](#publication) | Composer, Evaluator, Actuator |
| know who else belongs in the case | [IdentifyVendors, ResolveActorDetails, InjectParticipant](#participant-and-actor-discovery) | Retriever, Actuator |
| watch threat feeds | [MonitorAttacks, MonitorExploits, MonitorPublicReports](#threat-monitoring), or a [Sentinel](#the-sentinel-call-in-pattern) that reports what it sees | Retriever |
| update your ticketing system | [OnAccept, OnDefer](#report-prioritization) and [PreCloseAction](#close-report) | Actuator |

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

!!! note "A call-out point is answerable now; asking another actor is not"

    A call-out point asks a service *you* run, so it is answered while the BT is still running (BT-18-011).
    Some questions cannot be answered that way, because they need a **decision from another actor in the case**.
    An example is whether the case owner permits a change to the case's agreed state.
    No service can answer that on the owner's behalf, and the answer may take days.
    There the actor does not wait: it sends a request and finishes, and the reply starts new work when it arrives.
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
For example, the proposed `EvaluateCveEligibility` is a step within the broader `AssignCveId` workflow.
Most capabilities are not nested.

!!! note "Design decisions"
    The taxonomy is defined in [ADR-0024](../../adr/0024-coordination-agent-taxonomy.md), and [ADR-0097](../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md) reduces it to four shapes.
    The factory-injection pattern is defined in [ADR-0025](../../adr/0025-call-out-point-abstraction-layer.md).

---

## The four shapes

There are exactly four capability shapes (BT-18-013).
The normative contracts are in [Annex G of the protocol specification](../../reference/vultron-spec/index.md#annex-g-capability-shapes-i); this section explains how each one behaves.

### Evaluator

**You receive:** a situation, such as case context, report details, or embargo terms.
**You return:** a structured recommendation, typically a decision plus optional reasoning.
**The BT uses it to:** gate what happens next.

If you return "needs revision," the BT routes to the revision branch.
If you return FAILURE, the pipeline stops.
FAILURE is the only way to stop it: an Evaluator that returns SUCCESS with a "rejected" value in its output does not block the next step (BT-18-007).
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

**You receive:** a trigger, a signal that something should happen.
**You return:** confirmation of success or failure, with no content artifact.
**The BT uses it to:** confirm that a side effect was executed.

Actuators fire side effects in external systems.
Examples are posting an embargo acceptance to a collaboration platform, submitting an advisory to a publication pipeline, and updating a ticket when a report is closed.

---

## The Sentinel call-in pattern

A **Sentinel** is not a capability shape (BT-18-013, [ADR-0097](../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md)).
It watches a condition over time and, when the condition is met, acts on its own initiative.
The protocol never asks it anything, so it has no call-out point, no blackboard contract, and no backend factory.

The discriminator is *who initiates*, not where the information comes from.
A capability is asked and answers within the tick that asks.
A Sentinel decides for itself that the moment has come.

A Sentinel takes one of two forms:

- a case **Participant**, typically holding the Observer role, that learns case state through ordinary ledger replication and acts by sending ordinary protocol messages, visible to every participant;
- operator-side machinery with no case identity, which drives one actor through its [call-in triggers](#call-in-triggers) and is invisible to the case.

Examples are an embargo timer that calls `terminate-embargo` when the agreed end date passes, a threat-feed monitor that reports active attacks, and a deployment monitor that reports a fix as deployed.
A Sentinel is a long-running monitor, so building one needs different infrastructure from building a call-out responder: a way to observe, a decision rule, and something to call.

---

## Capability hierarchy

The following is the current catalog of known integration points, organized by domain.
Use this list to identify which capability you are building toward.

Entries marked with a shape are call-out points: Vultron asks, and your capability answers.
Entries marked (Sentinel) are not capabilities: they are call-in patterns that watch a condition and call a trigger on their own initiative (see [The Sentinel call-in pattern](#the-sentinel-call-in-pattern)).

### Report Validation

*See also: [Validation behavior](../behavior_logic/rm_validation_bt.md)*

- **EvaluateReportCredibility** (Evaluator) — is this report from a credible source?
- **EvaluateReportValidity** (Evaluator) — does this report describe a real, in-scope vulnerability?
- **GatherValidationInfo** (Retriever) — collect background information needed to evaluate a report
- **NewValidationInfoSentinel** (Sentinel) — fires when new validation-relevant information becomes available

### Report Prioritization

*See also: [Prioritization behavior](../behavior_logic/rm_prioritization_bt.md)*

- **EvaluateCasePriority** (Evaluator) — assign a priority score to a case; the natural home for an SSVC integration
- **EnoughPrioritizationInfo** (Evaluator) — is there sufficient information to make a prioritization decision?
- **GatherPrioritizationInfo** (Retriever) — collect data needed for prioritization
- **NewPrioritizationInfoSentinel** (Sentinel) — fires when new prioritization-relevant information arrives
- **OnAccept** / **OnDefer** (Actuators) — notification hooks when a report is accepted or deferred

### Case Admission

*See also: [Propose case behavior](../behavior_logic/use-cases/propose-case.md), [Case Initialization](../case_lifecycle/case_initialization.md)*

- **EvaluateCaseProposal** (Evaluator) — should this service open and manage a case for this proposal?

This is the admission decision a case actor service makes on an inbound `Create(as_CaseProposal)`, and the only place admission policy lives.
Returning FAILURE sends `Reject(as_CaseProposal)`; the default admits.

Build this one if you run a case actor service for others.
The [Propose case](../behavior_logic/use-cases/propose-case.md#where-judgment-enters) page carries the full reasoning — what the policy decides, why the decision sits ahead of every write, and the two ways a refusal gate can be defeated.

### Embargo Management

*See also: [Embargo behaviors](../behavior_logic/em_bt.md), [Evaluate proposed embargo](../behavior_logic/em_eval_bt.md), [Propose embargo](../behavior_logic/em_propose_bt.md), [Terminate embargo](../behavior_logic/em_terminate_bt.md)*

- **WantToProposeEmbargo** (Evaluator) — should we propose an embargo for this case?
- **SelectEmbargoOfferTerms** (Evaluator) — what embargo terms should we propose?
- **EvaluateEmbargoProposal** (Evaluator) — should we accept an incoming embargo proposal?
- **WillingToCounterEmbargoProposal** (Evaluator) — if we reject, should we make a counter-proposal?
- **CurrentEmbargoAcceptable** (Evaluator) — is the active embargo still acceptable given current conditions? (see [#1943](https://github.com/CERTCC/Vultron/issues/1943))
- **StopProposingEmbargo** (Evaluator) — should we stop trying to negotiate an embargo?
- **ExitEmbargoWhenFixReady** / **ExitEmbargoWhenDeployed** / **ExitEmbargoForOtherReason** (Evaluators) — should the embargo end early?
- **EmbargoTimerExpired** (Retriever; whether a Sentinel should replace this call-out point is open — see [Still open](#still-open) and [#1893](https://github.com/CERTCC/Vultron/issues/1893)) — has the embargo end date passed?
- **CaseOwnerApprovesEmbargoResponse** (Evaluator) — security gate: does the case owner approve this action?
- **OnEmbargoAccept** / **OnEmbargoReject** / **OnEmbargoExit** (Actuators) — notification hooks for embargo lifecycle events

### CVE / Vulnerability ID Assignment

*See also: [ID Assignment behavior](../behavior_logic/id_assignment_bt.md)*

This domain has one extra level because the ID assignment workflow has distinct sub-steps.

- **AssignCveId** — the overall ID assignment workflow, containing:
  - **IdAssigned** (Retriever) — does a CVE ID already exist for this vulnerability?
  - **InScope** (Evaluator) — is this vulnerability in scope for ID assignment?
  - **ProductInCNAScope** / **IsMostAppropriateCNA** (Evaluators) — CNA scoping checks
  - **EvaluateCveEligibility** (Evaluator, proposed) — does this vulnerability meet the CNA criteria for CVE assignment?
    This is a single judgment call that consolidates multiple CNA Operational Rules criteria.
    See [#2518](https://github.com/CERTCC/Vultron/issues/2518).
  - **AssignId** (Composer) — generate and record the CVE ID
  - **RequestId** (Retriever) — request an ID from an external CNA if we are not the appropriate authority

### Fix Development

*See also: [Fix Development behavior](../behavior_logic/fix_dev_bt.md)*

- **CreateFix** (Composer) — produce a fix artifact

### Fix Deployment

*See also: [Deployment behavior](../behavior_logic/deployment_bt.md)*

- **DeployFix** / **PrioritizeDeployment** / **MonitoringRequirement** (Evaluators) — deployment decisions and monitoring judgment calls
- **NewDeploymentInfoSentinel** (Sentinel) — fires when deployment status changes

### Mitigation Deployment

*See also: [Deployment behavior](../behavior_logic/deployment_bt.md)*

- **MitigationAvailable** / **MitigationDeployed** (Retrievers) — check whether a mitigation exists and is deployed
- **DeployMitigation** (Evaluator) — should we deploy a mitigation now?

### Exploit Management

*See also: [Exploit Acquisition behavior](../behavior_logic/acquire_exploit_bt.md)*

- **HaveExploit** / **FindExploit** (Retrievers) — check for known exploits
- **EvaluateExploitPriority** / **EvaluateExploitStrategy** / **PurchaseExploit** (Evaluators) — exploit handling decisions
- **PrepareExploit** / **DevelopExploit** (Composers) — produce an exploit artifact

### Publication

*See also: [Publication behavior](../behavior_logic/publication_bt.md), [Reporting behavior](../behavior_logic/reporting_bt.md)*

- **PrioritizePublicationIntents** (Evaluator) — order and prioritize publication targets
- **PrepareReport** / **PrepareFix** / **DraftAdvisoryArtifact** / **ReviseAdvisoryDraft** (Composers) — produce publication artifacts
- **ReviewAdvisoryDraft** (Evaluator) — review an advisory draft; return `needs_revision` to route to revision, or FAILURE to block submission entirely
- **Publish** / **SubmitAdvisoryArtifact** (Actuators) — submit the advisory to a publication platform

### Close Report

*See also: [Closure behavior](../behavior_logic/rm_closure_bt.md)*

- **OtherCloseCriteriaMet** (Evaluator) — are there additional conditions that should trigger closing this report?
- **PreCloseAction** (Actuator) — perform any pre-closure integration actions

### Participant and Actor Discovery

*See also: [#1142](https://github.com/CERTCC/Vultron/issues/1142)*

- **ResolveActorDetails** / **IdentifyVendors** / **IdentifyCoordinators** (Retrievers) — look up parties who should be involved in this case
- **AllPartiesKnown** (Evaluator) — have all relevant parties been identified?
- **InjectParticipant** (Actuator) — add a discovered party to the case

### Threat Monitoring

*See also: [Monitoring Threats behavior](../behavior_logic/monitor_threats_bt.md), [#1845](https://github.com/CERTCC/Vultron/issues/1845), [#1856](https://github.com/CERTCC/Vultron/issues/1856)*

- **MonitorAttacks** / **MonitorExploits** / **MonitorPublicReports** (Retrievers) — query threat intelligence for current status of attacks, exploit availability, and public reports

---

## Call-in triggers

These are the actions an external system can invoke on a Vultron actor, each at `POST /actors/{actor_id}/trigger/{behavior}`.
An operator-side Sentinel uses them to act when a monitored condition fires, and any other external system may call them directly.
The [Trigger API Reference](../../reference/trigger-api.md) gives each endpoint's request and response.

### Report lifecycle

- `submit-report` — create and offer a vulnerability report to a recipient
- `validate-report` — mark a received report as valid
- `invalidate-report` — mark a received report as invalid
- `reject-report` — hard-close a report before validation completes
- `close-report` — close a report through the report management lifecycle

### Case management

- `create-case` — create a local vulnerability case
- `engage-case` — accept a case (transitions to ACCEPTED state)
- `defer-case` — defer a case (transitions to DEFERRED state)
- `add-report-to-case` — link a report to an existing case
- `add-object-to-case` — add any protocol object to a case

### Embargo

- `propose-embargo` — propose a new embargo
- `accept-embargo` — accept a pending embargo proposal
- `reject-embargo` — reject a pending embargo proposal
- `propose-embargo-revision` — propose a revision to an active embargo
- `terminate-embargo` — end the active embargo immediately

### Participants and actors

- `suggest-actor-to-case` — recommend another actor to the case owner
- `invite-actor-to-case` — directly invite an actor to a case
- `accept-case-invite` / `reject-case-invite` — respond to a case invitation
- `accept-actor-recommendation` — approve a suggested actor (case owner only)
- `offer-case-participant-role` — offer a CVD role to another actor
- `offer-case-ownership-transfer` / `accept-case-ownership-transfer` — transfer case ownership

### Typical Sentinel patterns

| Sentinel condition | How it acts |
|---|---|
| Embargo end date passes | Calls `terminate-embargo` |
| Active attack observed in a threat feed | As a case Participant, sends `Add(ParticipantStatus)` recording the attack (the [*A* event](../process_models/cs/cs_model.md#the-attacks-observed-substate-a-a)); no trigger endpoint covers this yet ([#1845](https://github.com/CERTCC/Vultron/issues/1845)) |
| Fix confirmed deployed | As a case Participant, sends `Add(ParticipantStatus)` recording deployment (the [*D* event](../process_models/cs/cs_model.md#the-fix-deployed-substate-d-d)) |
| New party identified by a discovery service | Calls `suggest-actor-to-case` or `invite-actor-to-case` |

---

## Settled and open design questions

You can build the core logic of a capability implementation now.
The questions below determine the wiring details.

### Settled

**What a capability must define.**
A named capability declares its blackboard contract as typed input and output ports, on a declaration owned by the core layer (BT-18-012, [ADR-0097](../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md)).
Moving the existing declarations into the core layer is in progress under [#3421](https://github.com/CERTCC/Vultron/issues/3421).

**How a capability implementation is invoked.**
A backend answers synchronously, within the tick that asks, and never returns RUNNING (BT-18-011, [ADR-0080](../../adr/0080-protocol-asks-not-suspended-behaviors.md)).
A decision that takes days is not a call-out point: it is a request to another actor, or a Sentinel.

**What a deployment that supplies nothing gets.**
Every call-out point is built through a backend factory, and the default backend is a deterministic one, so a deployment that plugs in nothing still runs (BT-18-004, BT-23-001, [ADR-0025](../../adr/0025-call-out-point-abstraction-layer.md)).
The default is usually the permissive answer, on the reasoning that a stub should not silently hold up progress.
One class of gate inverts that.
Where a permissive default would let a party other than the case owner force the adoption of a case state or the teardown of an embargo, the default is the conservative answer instead (BT-23-012, [ADR-0076](../../adr/0076-security-significant-gates-default-require-case-owner-approval.md)).
So when a page says a call-out point "defaults to accept", that describes the stub, not a protocol requirement to accept.

**What the shape classes are called in code.**
The shape base classes are being renamed to `EvaluatorCapability`, `RetrieverCapability`, `ComposerCapability`, and `ActuatorCapability` ([ADR-0097](../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md), [#3421](https://github.com/CERTCC/Vultron/issues/3421)).
Until that lands, the code uses names such as `EvaluatorCallOutPoint`.
The fuzzer's leftover Sentinel call-out classes are being removed under [#3424](https://github.com/CERTCC/Vultron/issues/3424).

### Still open

**EmbargoTimerExpired: Retriever or Sentinel? ([#1893](https://github.com/CERTCC/Vultron/issues/1893))**
A timer check could be a Retriever the BT asks each tick, or the call-out point could give way to a Sentinel that calls `terminate-embargo` at the right moment.
The answer changes what you build.

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
