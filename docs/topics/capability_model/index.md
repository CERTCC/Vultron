# Capability Model

## Overview

This page is for developers building external services that integrate with Vultron's coordination protocol. You are probably building one of:

- A **REST service** (microservice, serverless function, or similar) that Vultron calls when it needs a decision, data, or action
- A **monitoring process** that watches an external condition and notifies Vultron when something changes

This page explains the conceptual model, the five types of services you can build, and the catalog of known integration points.

---

## Why Vultron needs external services

Vultron automates multi-party coordinated vulnerability disclosure (CVD) — the process by which a vulnerability finder, vendor, coordinator, and others manage a vulnerability from discovery through public disclosure.

Much of that process is mechanical: send a message, record a state, wait for a reply. Vultron handles all of that automatically using [behavior trees (BTs)](../behavior_logic/index.md) — a kind of state machine that runs as protocol activities arrive.

But some steps require judgment that Vultron cannot make by itself:

- Is this vulnerability report credible?
- Should we accept this embargo proposal?
- Has a CVE (Common Vulnerabilities and Exposures) ID already been assigned?
- Is it time to publish the advisory?

These are **call-out points** — places where the BT pauses and waits for an answer from an external service before it can continue.

During development and simulation, call-out points are filled by **fuzzer nodes** — stubs that return a random success or failure based on a probability. In production, you replace a fuzzer node with a real service: a **capability implementation**.

---

## The two integration surfaces

There are two ways an external service interacts with Vultron:

**Call-out** — Vultron calls *you*. The BT reaches a call-out point, packages up a question as a structured payload, sends it to your service, and waits for a structured answer. Your service decides and responds.

**Call-in** — You call *Vultron*. Your service monitors something externally — a timer, a threat feed, a deployment system — and, when a condition is met, sends a trigger to Vultron. Vultron acts on it.

Most services use the call-out surface. One shape — the **Sentinel** — works exclusively on the call-in side (see [The five shapes](#the-five-shapes) below).

---

## Three-level taxonomy

Every integration point in Vultron fits into a three-level hierarchy:

**Shape** → **Capability** → **Capability implementation**

| Level | What it is | Example |
|---|---|---|
| **Shape** | The abstract type of interaction — what the service receives, what it returns, and how the BT uses the result | Evaluator |
| **Capability** | A specific named integration point with its own input/output contract | `EvaluateCveEligibility` |
| **Capability implementation** | The concrete service you build that fulfills a capability at runtime | A microservice that applies CNA Operational Rules and returns pass/fail |

Think of the shape as a job description, the capability as the open role, and your implementation as the service hired into that role.

Some capabilities are sub-steps of a larger workflow capability. For example, `EvaluateCveEligibility` is a step within the broader `AssignCveId` workflow. Most capabilities are not nested — the hierarchy is shallow for most domains.

!!! note "Design decisions"
    The taxonomy is defined in [ADR-0024](../../adr/0024-coordination-agent-taxonomy.md).
    The factory-injection pattern and three-mode backend model are defined in [ADR-0025](../../adr/0025-call-out-point-abstraction-layer.md).

---

## The five shapes

### Evaluator

**You receive:** A situation — case context, report details, embargo terms, or similar
**You return:** A structured recommendation — typically a decision plus optional reasoning
**The BT uses it to:** Gate what happens next

If you return "needs revision," the BT routes to the revision branch. If you return FAILURE, the pipeline stops. The BT does not care whether the judgment came from a human reviewer, a rules engine, or an LLM (large language model) — what matters is that you return a structured answer it can act on.

Evaluators require human-level judgment. Examples: assessing whether a report is credible, deciding whether an embargo proposal is acceptable, checking whether a vulnerability meets CVE assignment criteria.

### Retriever

**You receive:** A query
**You return:** Structured facts the BT needs to proceed
**The BT uses it to:** Supply inputs for downstream steps

Retrievers are data lookups. Examples: "does a CVE ID already exist for this vulnerability?", "is there a known exploit in public exploit databases?", "what is the current SSVC (Stakeholder-Specific Vulnerability Categorization) score for this case?". Boolean yes/no questions are also Retrievers — not Sentinels.

Most Retrievers have high automation potential: they can be wired directly to an API or database without human involvement.

### Composer

**You receive:** Context — case details, draft content, constraints
**You return:** A content artifact — a document, report body, advisory text, or fix description
**The BT uses it to:** Pass the artifact to the next stage (review, publish, etc.)

The output of a Composer is written into the BT's shared state (the **blackboard**) so later steps can read it. Examples: drafting a security advisory, writing a vulnerability report body, preparing a fix description.

!!! tip "Composer vs. Actuator"
    If your service *generates* a document, it is a Composer. If it *submits* that document to a publication platform, that is an Actuator.

### Actuator

**You receive:** A trigger — a signal that something should happen
**You return:** Confirmation of success or failure — no content artifact
**The BT uses it to:** Confirm that a side effect was executed

Actuators fire side effects in external systems. Examples: posting an embargo acceptance notification to a collaboration platform, submitting an advisory to a publication pipeline, updating a ticket-tracking system when a report is closed.

If your service "does something" in an outside system and confirms it worked, it is an Actuator.

### Sentinel

**Sentinels work differently from the other four shapes.** They have no call-out point — Vultron does not call them. Instead, a Sentinel monitors a condition externally and calls *into* Vultron when that condition is met.

A Sentinel is a long-running process. It watches something — a timer, a threat intelligence feed, a deployment monitor, a public advisory database — and when it detects the trigger condition, it sends one of Vultron's **trigger endpoints** (see [Call-in triggers](#call-in-triggers) below).

Examples:

- An embargo timer that fires `terminate_embargo` when the agreed end date passes
- A threat-feed monitor that signals Vultron when active attacks on the vulnerability are observed
- A deployment monitor that fires when a fix is confirmed deployed across affected systems

Because Sentinels are long-running monitors, building one requires different infrastructure than building a call-out responder.

---

## Capability hierarchy

The following is the current catalog of known integration points, organized by domain. Use this list to identify which capability you are building toward.

Capabilities marked with a shape label are call-out points — Vultron calls you. Capabilities marked (Sentinel) are call-in — you call Vultron.

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

### Embargo Management

*See also: [Embargo behaviors](../behavior_logic/em_bt.md), [Evaluate proposed embargo](../behavior_logic/em_eval_bt.md), [Propose embargo](../behavior_logic/em_propose_bt.md), [Terminate embargo](../behavior_logic/em_terminate_bt.md)*

- **WantToProposeEmbargo** (Evaluator) — should we propose an embargo for this case?
- **SelectEmbargoOfferTerms** (Evaluator) — what embargo terms should we propose?
- **EvaluateEmbargoProposal** (Evaluator) — should we accept an incoming embargo proposal?
- **WillingToCounterEmbargoProposal** (Evaluator) — if we reject, should we make a counter-proposal?
- **CurrentEmbargoAcceptable** (Evaluator) — is the active embargo still acceptable given current conditions? (see [#1943](https://github.com/CERTCC/Vultron/issues/1943))
- **StopProposingEmbargo** (Evaluator) — should we stop trying to negotiate an embargo?
- **ExitEmbargoWhenFixReady** / **ExitEmbargoWhenDeployed** / **ExitEmbargoForOtherReason** (Evaluators) — should the embargo end early?
- **EmbargoTimerExpired** (Retriever or Sentinel — classification open; see [Open questions](#open-questions) and [#1893](https://github.com/CERTCC/Vultron/issues/1893)) — has the embargo end date passed?
- **CaseOwnerApprovesEmbargoResponse** (Evaluator) — security gate: does the case owner approve this action?
- **OnEmbargoAccept** / **OnEmbargoReject** / **OnEmbargoExit** (Actuators) — notification hooks for embargo lifecycle events

### CVE / Vulnerability ID Assignment

*See also: [ID Assignment behavior](../behavior_logic/id_assignment_bt.md)*

This domain has one extra level because the ID assignment workflow has distinct sub-steps.

- **AssignCveId** — the overall ID assignment workflow, containing:
  - **IdAssigned** (Retriever) — does a CVE ID already exist for this vulnerability?
  - **InScope** (Evaluator) — is this vulnerability in scope for ID assignment?
  - **ProductInCNAScope** / **IsMostAppropriateCNA** (Evaluators) — CNA (CVE Numbering Authority) scoping checks
  - **EvaluateCveEligibility** (Evaluator) — does this vulnerability meet the CNA criteria for CVE assignment? This is a single judgment call that consolidates multiple CNA Operational Rules criteria. See [#2518](https://github.com/CERTCC/Vultron/issues/2518).
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

- **ResolveActor** / **IdentifyVendors** / **IdentifyCoordinators** (Retrievers) — look up parties who should be involved in this case
- **AllPartiesKnown** (Evaluator) — have all relevant parties been identified?
- **InjectParticipant** (Actuator) — add a discovered party to the case

### Threat Monitoring

*See also: [Monitoring Threats behavior](../behavior_logic/monitor_threats_bt.md), [#1845](https://github.com/CERTCC/Vultron/issues/1845), [#1856](https://github.com/CERTCC/Vultron/issues/1856)*

- **MonitorAttacks** / **MonitorExploits** / **MonitorPublicReports** (Retrievers) — query threat intelligence for current status of attacks, exploit availability, and public reports

---

## Call-in triggers

These are the actions an external system can invoke on Vultron. Sentinels use these to notify Vultron when a monitored condition fires. Other external systems may also call them directly.

The exact API is not yet finalized (see [Open questions](#open-questions)), but the available trigger actions are:

### Report lifecycle

- `submit_report` — create and offer a vulnerability report to a recipient
- `validate_report` — mark a received report as valid
- `invalidate_report` — mark a received report as invalid
- `reject_report` — close a report before validation completes
- `close_case` — close a case via the report management lifecycle

### Case management

- `create_case` — create a local vulnerability case
- `engage_case` — accept a case (transitions to ACCEPTED state)
- `defer_case` — defer a case (transitions to DEFERRED state)
- `leave_case` — depart from a case
- `add_report_to_case` — link a report to an existing case
- `add_object_to_case` — add any protocol object to a case
- `add_note_to_case` — add a free-text note to a case
- `add_participant_status` — report your current state to the case manager

### Embargo

- `propose_embargo` — propose a new embargo
- `accept_embargo` — accept a pending embargo proposal
- `reject_embargo` — reject a pending embargo proposal
- `propose_embargo_revision` — propose a revision to an active embargo
- `terminate_embargo` — end the active embargo immediately

### Participants and actors

- `suggest_actor_to_case` — recommend another actor to the case owner
- `invite_actor_to_case` — directly invite an actor to a case
- `accept_case_invite` / `reject_case_invite` — respond to a case invitation
- `accept_actor_recommendation` — approve a suggested actor (case owner only)
- `offer_case_participant_role` — offer a CVD role to another actor
- `offer_case_ownership_transfer` / `accept_case_ownership_transfer` — transfer case ownership

### Typical Sentinel patterns

| Sentinel condition | Trigger to call |
|---|---|
| Embargo end date passes | `terminate_embargo` |
| Active attack observed in threat feed | `add_participant_status` (signaling the A event) |
| Fix confirmed deployed | `add_participant_status` (signaling the D event) |
| New party identified by a discovery service | `suggest_actor_to_case` or `invite_actor_to_case` |

---

## Open questions

These questions are actively under discussion. You can build the core logic of your service without waiting for answers, but the wiring details will depend on how they are resolved.

**What must a capability formally define? ([#2452](https://github.com/CERTCC/Vultron/issues/2452))**
There is no finalized specification yet for what a named capability must declare — its input schema, output schema, shape classification, and blackboard contract. The current code uses factory injection (each call-out point has a factory function in a domain bundle). Whether this becomes a formal interface definition, a JSON schema registry, or both is open.

**How are capability implementations invoked? ([#2453](https://github.com/CERTCC/Vultron/issues/2453))**
The invocation model is not yet decided. Synchronous REST + JSON is likely for most shapes. Asynchronous callbacks (webhook, queue) are under consideration for long-running Evaluators and Sentinels. This work is blocked on a broader async delivery design that has not been written yet.

**Code naming ([#2454](https://github.com/CERTCC/Vultron/issues/2454))**
The codebase currently uses class names like `EvaluatorCallOutPoint` that predate the three-level taxonomy. Whether these will be renamed to match the current terminology is open.

**EmbargoTimerExpired: Retriever or Sentinel? ([#1893](https://github.com/CERTCC/Vultron/issues/1893))**
A timer check could be either shape: a Retriever that the BT polls each tick, or a Sentinel that fires `terminate_embargo` at the right moment. The right classification affects what you build.

---

## Choosing what to build

1. **Read the capability hierarchy above.** Find a domain that matches your expertise or your organization's existing tooling.
2. **Identify the shape.** Ask: will Vultron call me (Evaluator, Retriever, Composer, or Actuator), or will I watch something and call Vultron (Sentinel)?
3. **Check the GitHub issues.** Several capabilities already have open idea issues under [epic #1147](https://github.com/CERTCC/Vultron/issues/1147). If one fits, comment on it. If your capability is not listed, file a new issue with the `idea` label.
4. **Design the interface.** Even though the formal calling convention is not finalized, you can design the JSON input/output contract for your capability now. Focus on: what context does Vultron need to give you, and what structured answer do you need to return?
5. **Build and test with the stochastic layer.** The Vultron demo layer uses probabilistic stub nodes for every call-out point. You can replace a stub with a real service and test it against the existing BT structure.
