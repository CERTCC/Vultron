# Vultron BT Fuzzer Nodes: External Dependency Touchpoints

## Background and Purpose

This document catalogs all **fuzzer nodes** in the Vultron Behavior Tree (BT)
simulation. Fuzzer nodes are stub implementations created with the
`vultron.bt.base.factory.fuzzer` factory function. Each one wraps a
probabilistic base type from `vultron.bt.base.fuzzer` (e.g.,
`AlwaysSucceed`, `UsuallyFail`, `ProbablySucceed`) to stand in for
real-world logic that has not yet been implemented.

### What Fuzzer Nodes Represent

Every fuzzer node is a **named external dependency touchpoint** — a location
in the protocol simulation where one of the following is required to
determine the outcome:

- **External data source**: e.g., threat intelligence feeds, exploit
  databases, vulnerability registries, contact directories
- **State of the world**: e.g., whether a fix has been deployed, whether a
  threat has materialized, whether a timer has elapsed
- **Human judgment**: e.g., analyst decisions on report validity, embargo
  terms, publication priorities, effort thresholds
- **Decision-support input from another agent**: e.g., automated scoring
  systems (CVSS, SSVC), policy engines, orchestration services

### Why This Document Exists

The fuzzer nodes define the interface boundary between the Vultron protocol
engine and the external systems and humans it must interact with. This
document is a structured inventory of those interfaces so that:

1. Requirements can be written for mechanisms to acquire these inputs.
2. Future integration work can be scoped and prioritized.
3. Researchers and implementers can understand where human or automated
   decision support is needed in each workflow.

### How to Read This Document

Entries are organized by **topic area** (corresponding to BT sub-trees).
Each fuzzer node has its own section with the following fields:

- **Node name**: The Python identifier used in the BT
- **btz type**: The probabilistic base type from `vultron.bt.base.fuzzer`
  and its approximate success probability in the simulation
- **Source file**: Path relative to `vultron/bt/`
- **Parent tree**: The named BT sub-tree this node participates in
- **Semantic function**: What this node represents in the CVD process
- **Input dependency**: The kind of real-world input needed to replace it
- **Notes**: Any implementation guidance from the source code comments
- **Automation potential**: An assessment of how automatable the real-world
  input is, categorized as follows:
  - High — fully automatable via API calls, metadata queries, or policy-rule
    evaluation
  - Medium — partially automatable with data feeds or policy templates, but  
    human oversight or judgment still needed for edge cases
  - Low — inherently human-driven; automation limited to notifications or  
    task triggers
  - N/A — terminal placeholder nodes with no real decision logic

### Fuzzer Base Types (Quick Reference)

| btz type | Success probability |
|---|---|
| `AlwaysSucceed` | 1.00 |
| `AlmostCertainlySucceed` | 0.93 |
| `AlmostAlwaysSucceed` | 0.90 |
| `UsuallySucceed` | 0.75 |
| `OftenSucceed` / `LikelySucceed` | 0.70 |
| `ProbablySucceed` | 0.67 |
| `UniformSucceedFail` / `RandomSucceedFail` | 0.50 |
| `SuccessOrRunning` | 0.50 (never fails; returns SUCCESS or RUNNING) |
| `ProbablyFail` | 0.33 |
| `OftenFail` | 0.30 |
| `UsuallyFail` | 0.25 |
| `AlmostAlwaysFail` / `RarelySucceed` | 0.10 |
| `AlmostCertainlyFail` | 0.07 |
| `OneInTwenty` | 0.05 |
| `OneInOneHundred` | 0.01 |
| `OneInTwoHundred` | 0.005 |
| `AlwaysFail` | 0.00 |

---

## Table of Contents

| Section | Line | Topic |
|---------|------|-------|
| [Vulnerability Discovery](#vulnerability-discovery) | ~85 | Discovery priority, vulnerability finding, `NoVulFound` |
| [Embargo Management](#embargo-management) | ~140 | Embargo exit triggers, proposal/counter logic, acceptance/rejection |
| [Report Validation](#report-validation) | ~351 | Validation info gathering, credibility/validity evaluation |
| [Report Prioritization](#report-prioritization) | ~433 | Prioritization info gathering, engage/defer decisions |
| [Vulnerability ID Assignment](#vulnerability-id-assignment) | ~511 | In-scope checks, ID assignment |
| [Fix Development](#fix-development) | ~606 | Fix readiness, patch preparation |
| [Fix Deployment](#fix-deployment) | ~629 | Deployment status checks, deployer discovery |
| [Exploit Acquisition](#exploit-acquisition) | ~751 | Exploit publication gates, exploit readiness/preparation |
| [Threat Monitoring](#threat-monitoring) | ~873 | Threat presence and materialization checks |
| [Publication](#publication) | ~945 | Publication readiness for exploit, fix, and report |
| [Reporting to Other Parties](#reporting-to-other-parties) | ~1146 | Recipient selection, contact finding, effort limits |
| [Report Closure](#report-closure) | ~1449 | Closure criteria and pre-close actions |
| [Other Work (Do Work)](#other-work-do-work) | ~1489 | Generic work dispatch |
| [Inbound Message Handling](#inbound-message-handling) | ~1514 | Error message follow-up |
| [Related](#related) | ~1548 | Cross-references |

---

## Vulnerability Discovery

These nodes belong to the `DiscoverVulnerabilityBt` fallback tree
(`vultron/bt/vul_discovery/behaviors.py`), which is one of the four top-level
branches of `CvdProtocolRoot`. The tree models the process by which a
participant with the FINDER role searches for and discovers a new vulnerability.

Note that the `DiscoverVulnerabilityBt` is only needed for the simulation,
and would not be part of a real Vultron implementation. The actual Vultron
system would start with creating and submitting vulnerability reports, which
is essentially the "output" of the discovery process.

### `HaveDiscoveryPriority`

- **Node name**: `HaveDiscoveryPriority`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `FindVulnerabilities` (within `DiscoverVulnerabilityBt`)
- **Semantic function**: Condition check — has the participant decided to
  prioritize vulnerability discovery as a current goal?
- **Input dependency**: Organizational priority setting; could be driven by
  human tasking, scheduled policy, or an automated work-queue query
- **Notes**: Always succeeds in simulation to keep the discovery loop active
- **Automation potential**: **High** — static role/capability configuration check; can be fully automated as a lookup against the participant's role metadata or organizational task queue.

### `DiscoverVulnerability`

- **Node name**: `DiscoverVulnerability`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `FindVulnerabilities` (within `DiscoverVulnerabilityBt`)
- **Semantic function**: Action — execute a vulnerability discovery activity,
  such as fuzzing, code audit, pentesting, or research
- **Input dependency**: Results from a vulnerability research tool, a
  researcher's findings, or an automated scanning system
- **Notes**: Succeeds often enough to drive simulation throughput while still
  modeling that discovery is not guaranteed on every cycle
- **Automation potential**: **Low** — inherently a human or tool-driven research activity (fuzzing, code audit, pentesting); results must be fed in from an external research pipeline.

### `NoVulFound`

- **Node name**: `NoVulFound`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `DiscoverVulnerabilityBt`
- **Semantic function**: Fallback leaf — acknowledge that no vulnerability
  was discovered in this tick; keep the overall BT from failing
- **Input dependency**: None (terminal success placeholder); no external
  input needed once we confirm discovery came up empty
- **Notes**: Ensures the discovery branch always succeeds so the top-level
  sequence can continue to other work
- **Automation potential**: **N/A** — terminal success placeholder; no real decision logic required.

---

## Embargo Management

These nodes belong to `EmbargoManagementBt` and its sub-trees
(`TerminateEmbargoBt`, `_ConsiderTerminatingActiveEmbargo`,
`_ProposeEmbargoBt`, `_ChooseEmProposedResponse`, etc.) in
`vultron/bt/embargo_management/behaviors.py`. They model the negotiation,
evaluation, and lifecycle management of coordinated disclosure embargoes.

### `ExitEmbargoWhenDeployed`

- **Node name**: `ExitEmbargoWhenDeployed`
- **btz type**: `ProbablyFail` (p=0.33)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_MaybeExitWhenDeployed` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition/action — decide whether a deployed fix is
  sufficient reason to exit an active embargo
- **Input dependency**: Human or policy judgment; deployment event plus
  site policy on post-deployment embargo continuation
- **Notes**: Modeled as unlikely because deployment alone is usually
  insufficient (e.g., partial rollout, emergency deployment)
- **Automation potential**: **Medium** — deployment status check is automatable via patch-management or case-state APIs; the *decision* to exit still requires policy-rule evaluation or human confirmation.

### `ExitEmbargoWhenFixReady`

- **Node name**: `ExitEmbargoWhenFixReady`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_MaybeExitWhenFixReady` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition/action — decide whether a ready (but not
  yet deployed) fix is sufficient reason to exit the embargo
- **Input dependency**: Human or policy judgment; fix-readiness status plus
  organizational policy
- **Notes**: Less common than deployment-triggered exit; vendor may want to
  coordinate simultaneous deployment across affected population first
- **Automation potential**: **Medium** — fix-readiness flag is queryable automatically; the exit decision depends on configurable organizational policy that may require human override.

### `ExitEmbargoForOtherReason`

- **Node name**: `ExitEmbargoForOtherReason`
- **btz type**: `OneInTwoHundred` (p=0.005)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_OtherReasonToExitEmbargo` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition — catch-all for exiting an embargo for
  reasons other than fix readiness, deployment, timer expiry, public
  awareness, known exploits, or observed attacks
- **Input dependency**: Human judgment; rare edge-case policy decision
- **Notes**: Intentionally very rare in simulation; represents extraordinary
  circumstances
- **Automation potential**: **Low** — rare edge case representing extraordinary circumstances; fundamentally requires human judgment that cannot be anticipated by a general policy rule.

### `EmbargoTimerExpired`

- **Node name**: `EmbargoTimerExpired`
- **btz type**: `OneInOneHundred` (p=0.01)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_SufficientCauseToTerminateActiveEmbargo` (within
  `TerminateEmbargoBt`)
- **Semantic function**: Condition — check whether the embargo's agreed-upon
  deadline has passed
- **Input dependency**: System clock compared to the embargo expiry
  timestamp recorded in the case; fully automatable
- **Notes**: Rare in simulation (most ticks occur well before expiry); in
  production this is a simple timestamp comparison
- **Automation potential**: **High** — simple system-clock comparison against the recorded embargo expiry timestamp; fully automatable with no human involvement.

### `OnEmbargoExit`

- **Node name**: `OnEmbargoExit`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderTerminatingActiveEmbargo`
- **Semantic function**: Action — execute any site-specific tasks required
  when leaving an active embargo (notifications, logging, downstream
  triggers)
- **Input dependency**: Site-specific integration hook; may invoke
  notification APIs, case management system updates, etc.
- **Notes**: Always succeeds in simulation; production implementation
  must ensure idempotent execution
- **Automation potential**: **High** — integration hook (notifications, state updates, downstream triggers); can be fully automated via API calls to notification and case-management systems.

### `StopProposingEmbargo`

- **Node name**: `StopProposingEmbargo`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderAbandoningProposedEmbargo` (within
  `_ProposeEmbargoBt`)
- **Semantic function**: Condition — human or policy decision to give up on
  negotiating an embargo (e.g., too many counter-proposals, time pressure)
- **Input dependency**: Human judgment or policy-driven escalation trigger
- **Notes**: Modeled as uncommon; parties are usually willing to keep
  negotiating
- **Automation potential**: **Low** — fundamentally a negotiation-fatigue judgment; depends on relationship context and subjective assessment of negotiation prospects; requires human decision.

### `SelectEmbargoOfferTerms`

- **Node name**: `SelectEmbargoOfferTerms`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ProposeNewEmbargo` and `_ProposeEmbargoRevision`
  (within `_ProposeEmbargoBt`)
- **Semantic function**: Action — choose the specific terms (duration,
  conditions) to include in an embargo proposal or counter-proposal
- **Input dependency**: Human decision or policy-driven term selection;
  could be automated from organizational policy templates
- **Notes**: Always succeeds in simulation; in production may involve
  negotiation-support tooling or policy lookup
- **Automation potential**: **Medium** — standard terms (duration, conditions) can be drawn from organizational policy templates automatically; atypical situations may need human review.

### `WantToProposeEmbargo`

- **Node name**: `WantToProposeEmbargo`
- **btz type**: `RandomSucceedFail` / `UniformSucceedFail` (p=0.50)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderProposingEmbargo` (within `_EmNone`)
- **Semantic function**: Condition — does the participant currently wish to
  initiate an embargo negotiation?
- **Input dependency**: Human or automated policy decision; depends on case
  context, role, and organizational policy
- **Notes**: Default recommendation is to propose an embargo; fuzzer
  exercises both paths equally
- **Automation potential**: **Medium** — default policy (always propose) can be automated; exceptions (e.g., already-public vulnerability, no vendor identified) could be rule-encoded, but edge cases may need human override.

### `WillingToCounterEmbargoProposal`

- **Node name**: `WillingToCounterEmbargoProposal`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_AvoidCounterProposal` (within `_EmProposed`)
- **Semantic function**: Condition — is the participant willing to respond
  to an incoming embargo proposal with a counter-proposal rather than
  accepting or rejecting it outright?
- **Input dependency**: Human judgment or policy; generally discouraged in
  favor of accepting and then proposing a revision
- **Notes**: Intentionally low probability; the recommended behavior is to
  accept the current proposal and negotiate revisions separately
- **Automation potential**: **Low** — nuanced negotiation judgment about whether countering is strategically preferable to accepting and revising; best left to human discretion.

### `ReasonToProposeEmbargoWhenDeployed`

- **Node name**: `ReasonToProposeEmbargoWhenDeployed`
- **btz type**: `AlmostCertainlyFail` (p=0.07)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_AvoidNewEmbargoesInCsDeployedUnlessReason`
- **Semantic function**: Condition — is there an unusual reason to start a
  new embargo negotiation even though the fix has already been deployed?
- **Input dependency**: Human judgment; exceptional circumstance requiring
  explicit decision
- **Notes**: Very rare by design; post-deployment embargo proposals are
  exceptional
- **Automation potential**: **Low** — highly exceptional circumstance; no general rule can anticipate valid reasons, so human judgment is required.

### `EvaluateEmbargoProposal`

- **Node name**: `EvaluateEmbargoProposal`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_EvaluateAndAcceptProposedEmbargo` (within
  `_ChooseEmProposedResponse`)
- **Semantic function**: Condition/action — assess an incoming embargo
  proposal and decide whether to accept it
- **Input dependency**: Human analyst review, or an automated policy
  compatibility check comparing proposed terms against organizational policy
- **Notes**: Modeled as usually succeeding (acceptance is the common
  outcome); in production may involve structured negotiation support
- **Automation potential**: **Medium** — basic compatibility check (is proposed duration within policy bounds?) is automatable; final accept/reject for out-of-range proposals typically needs human review.

### `OnEmbargoAccept`

- **Node name**: `OnEmbargoAccept`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_EvaluateAndAcceptProposedEmbargo`
- **Semantic function**: Action — execute site-specific tasks triggered when
  an embargo proposal is accepted (e.g., notify stakeholders, record
  agreement, start embargo timer)
- **Input dependency**: Integration hook; may invoke notification APIs,
  calendar/timer services, case management system updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — notification dispatch, timer initialization, and state-update actions are all integration-automatable via APIs.

### `OnEmbargoReject`

- **Node name**: `OnEmbargoReject`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_RejectProposedEmbargo` (within `_ChooseEmProposedResponse`)
- **Semantic function**: Action — execute site-specific tasks triggered when
  an embargo proposal is rejected (e.g., notify stakeholders, log rejection
  rationale)
- **Input dependency**: Integration hook; notification APIs and case
  management updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — notification dispatch and logging actions are fully automatable via APIs.

### `CurrentEmbargoAcceptable`

- **Node name**: `CurrentEmbargoAcceptable`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ChooseEmActiveResponse` (within `_EmActive`)
- **Semantic function**: Condition — is the participant satisfied with the
  current active embargo terms, or do they wish to propose a revision?
- **Input dependency**: Human judgment or automated policy check comparing
  current embargo terms against organizational preferences
- **Notes**: Modeled as usually acceptable; revision proposals are
  relatively uncommon
- **Automation potential**: **Medium** — automated comparison of current terms against policy preferences is feasible; edge cases and dynamic negotiation contexts may still require human judgment.

---

## Report Validation

These nodes belong to `RMValidateBt`
(`vultron/bt/report_management/_behaviors/validate_report.py`), the sub-tree
responsible for assessing whether an incoming vulnerability report is
credible and valid for the receiving organization.

### `NoNewValidationInfo`

- **Node name**: `NoNewValidationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — check whether any new information has
  arrived that should trigger re-evaluation of the report's validity
- **Input dependency**: Report change detection; could be a metadata
  timestamp check, event subscription, or manual flag
- **Notes**: Succeeds (no new info) more often than not, avoiding redundant
  re-evaluation loops
- **Automation potential**: **High** — event subscription on the case record or metadata timestamp comparison; fully automatable.

### `EvaluateReportCredibility`

- **Node name**: `EvaluateReportCredibility`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — assess whether the report's source and
  content are credible (i.e., likely to describe a real vulnerability)
- **Input dependency**: Human analyst judgment; structured credibility
  criteria (e.g., SSVC Exploitation, reporter reputation, technical
  plausibility); potentially automatable with ML-based triage tools
- **Notes**: SSVC documentation provides structured criteria for this
  evaluation
- **Automation potential**: **Medium** — SSVC exploitation status, reporter reputation scoring, and technical plausibility checks can be partially automated; final credibility determination typically requires human analyst review.

### `EvaluateReportValidity`

- **Node name**: `EvaluateReportValidity`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — assess whether the report is valid for
  this organization's scope (credible AND meeting org-specific acceptance
  criteria)
- **Input dependency**: Human analyst judgment or policy-driven scope check;
  context-specific to the receiving organization's CVD charter
- **Notes**: A report can be credible but out of scope; validity is
  contextual and role-dependent
- **Automation potential**: **Medium** — scope checks against well-defined CNA/charter rules are automatable; organizational-context validity judgment often requires human review.

### `EnoughValidationInfo`

- **Node name**: `EnoughValidationInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — determine whether sufficient information
  is available to reach a validation decision
- **Input dependency**: Human decision or automated completeness check
  against required report fields or evidence criteria
- **Notes**: Sufficient information is the normal case; absence triggers
  info-gathering
- **Automation potential**: **Medium** — completeness check against required fields or evidence criteria can be automated; the sufficiency threshold for final decision often involves human judgment.

### `GatherValidationInfo`

- **Node name**: `GatherValidationInfo`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Action — request or collect additional information
  needed to validate the report (e.g., reproduction steps, affected
  versions, proof-of-concept)
- **Input dependency**: Human analyst outreach to reporter, or automated
  intake forms / follow-up workflows
- **Notes**: Succeeds most of the time in simulation to keep the workflow
  progressing
- **Automation potential**: **Low–Medium** — structured intake form follow-ups and automated case-update requests are partially automatable; direct reporter outreach typically requires human involvement.

---

## Report Prioritization

These nodes belong to `RMPrioritizeBt`
(`vultron/bt/report_management/_behaviors/prioritize_report.py`), which
models the process of deciding whether to accept (engage with) or defer
(set aside) a validated vulnerability report.

### `NoNewPrioritizationInfo`

- **Node name**: `NoNewPrioritizationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — check whether new information has
  arrived that should trigger re-prioritization of the report
- **Input dependency**: Report change detection; metadata timestamp or
  event subscription
- **Notes**: Succeeds more often than not to avoid redundant re-evaluation
- **Automation potential**: **High** — metadata timestamp or case-update event check; fully automatable.

### `EnoughPrioritizationInfo`

- **Node name**: `EnoughPrioritizationInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — determine whether there is enough
  context to make an accept/defer decision
- **Input dependency**: Human analyst assessment or automated completeness
  check (e.g., SSVC decision point availability)
- **Notes**: Insufficient info triggers a gathering phase
- **Automation potential**: **Medium** — availability of SSVC decision-point data (e.g., CVSS score, exploitation status) is automatable; the sufficiency judgment for a final accept/defer decision usually involves human analyst review.

### `GatherPrioritizationInfo`

- **Node name**: `GatherPrioritizationInfo`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — collect additional context needed to
  support a prioritization decision (e.g., severity scores, asset
  inventory, threat landscape data)
- **Input dependency**: Human analyst research, CVSS/SSVC scoring tools,
  asset management systems, threat intelligence feeds
- **Notes**: Succeeds almost always in simulation to keep the workflow
  progressing
- **Automation potential**: **Medium** — fetching CVSS scores, EPSS scores, NVD data, and asset inventory is fully automatable via APIs; analyst interpretation and gap-filling still requires human involvement.

### `OnDefer`

- **Node name**: `OnDefer`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — execute site-specific tasks when a report
  is deferred (e.g., notify stakeholders, schedule a follow-up, update
  case status)
- **Input dependency**: Integration hook; notification APIs, task scheduling
  services, case management system updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — stakeholder notifications, follow-up scheduling, and state updates are all automatable via integration APIs.

### `OnAccept`

- **Node name**: `OnAccept`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — execute site-specific tasks when a report
  is accepted (e.g., notify stakeholders, initialize case workflow, assign
  to a team)
- **Input dependency**: Integration hook; notification APIs, workflow
  initialization, case management system updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — stakeholder notifications, workflow initialization, and state updates are all automatable via integration APIs.

---

## Vulnerability ID Assignment

These nodes belong to the `AssignVulID` fallback tree
(`vultron/bt/report_management/_behaviors/assign_vul_id.py`), which models
the process of assigning a public vulnerability identifier (e.g., a CVE ID)
to a validated report.

### `IdAssigned`

- **Node name**: `IdAssigned`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether the vulnerability has
  already been assigned an identifier (e.g., CVE ID)
- **Input dependency**: Query to internal case metadata or an external
  vulnerability registry (e.g., CVE database lookup)
- **Notes**: Fails most of the time in simulation because ID assignment is
  the main workflow; in production this is a simple metadata check
- **Automation potential**: **High** — simple query against case metadata or a vulnerability registry; fully automatable.

### `InScope`

- **Node name**: `InScope`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether the vulnerability is
  within the scope of the relevant ID namespace (e.g., CVE CNA rules)
- **Input dependency**: Human analyst review against CNA scope rules, or
  automated scope-checking against a product/component registry
- **Notes**: Scope rules vary by ID space; a broad ID space may skip
  this check
- **Automation potential**: **High** — scope rules for well-defined ID spaces (e.g., CVE CNA rules) can be encoded as a policy check and automated; may require human review for ambiguous cases.

### `IsIDAssignmentAuthority`

- **Node name**: `IsIDAssignmentAuthority`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether this participant is
  itself an ID assignment authority (e.g., a CVE CNA) able to assign
  IDs directly
- **Input dependency**: Organizational metadata / role configuration;
  fully automatable as a static capability check
- **Notes**: In production this is a static configuration check, not a
  runtime decision
- **Automation potential**: **High** — static organizational configuration; can be fully automated as a capability metadata lookup.

### `IdAssignable`

- **Node name**: `IdAssignable`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether this participant has
  authority to assign an ID to this specific vulnerability (e.g., is the
  authoritative CNA for the affected product)
- **Input dependency**: CNA rules lookup, product-to-CNA mapping, or
  human analyst determination
- **Notes**: A participant may be an ID authority generally but not the
  authoritative CNA for this specific product
- **Automation potential**: **High** — CNA-scope and product-to-CNA mapping checks are automatable via the CVE Services API or a local policy registry.

### `RequestId`

- **Node name**: `RequestId`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Action — submit a request for an ID to the
  appropriate assignment authority (e.g., submit a CVE ID request to the
  relevant CNA)
- **Input dependency**: API call to a CVE services endpoint (e.g.,
  CVE.org API), or human analyst manual submission
- **Notes**: Could be fully automated via the CVE Services API
- **Automation potential**: **High** — can be fully automated as an API call to the CVE Services endpoint or equivalent ID-request interface.

### `AssignId`

- **Node name**: `AssignId`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Action — assign an ID from the participant's own
  ID pool (when the participant is an assignment authority)
- **Input dependency**: Internal ID pool management system or CVE Services
  API (reserve/assign endpoint)
- **Notes**: Always succeeds in simulation; in production may involve
  API calls or database writes
- **Automation potential**: **High** — can be fully automated as an API call (reserve/assign) to the ID assignment authority or an internal ID pool management system.

---

## Fix Development

These nodes belong to the `DevelopFix` fallback tree
(`vultron/bt/report_management/_behaviors/develop_fix.py`), which models
the vendor's internal process of creating a patch or fix for the
vulnerability.

### `CreateFix`

- **Node name**: `CreateFix`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/develop_fix.py`
- **Parent tree**: `DevelopFix`
- **Semantic function**: Action — initiate or advance the internal
  engineering process to create a patch or mitigation for the vulnerability
- **Input dependency**: Human engineer prompt, bug tracker integration,
  or CI/CD pipeline trigger; reports progress from the engineering team
- **Notes**: Succeeds almost always in simulation; in production this
  node would integrate with the vendor's bug/patch tracking system
- **Automation potential**: **Low** — engineering work is human-initiated; automation is limited to triggering a bug-tracker ticket or sending a development task notification.

---

## Fix Deployment

These nodes belong to the `Deployment` fallback tree
(`vultron/bt/report_management/_behaviors/deploy_fix.py`), which models
the process of deploying a developed fix or mitigation to affected systems.

### `NoNewDeploymentInfo`

- **Node name**: `NoNewDeploymentInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether any new deployment-related
  information has arrived that warrants re-evaluating the deployment
  workflow
- **Input dependency**: Report/case change detection; metadata timestamp
  or event subscription on deployment status field
- **Notes**: New deployment info is uncommon; most ticks pass through
  without update
- **Automation potential**: **High** — metadata timestamp or deployment-event subscription check; fully automatable.

### `PrioritizeDeployment`

- **Node name**: `PrioritizeDeployment`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — assess and set the priority for deploying
  the fix across affected systems
- **Input dependency**: Human analyst or automated vulnerability
  prioritization system (e.g., CVSS environmental score, EPSS, asset
  criticality)
- **Notes**: Succeeds almost always in simulation; in production may
  involve structured prioritization criteria
- **Automation potential**: **Medium** — CVSS environmental scores, EPSS, and asset criticality data are automatable inputs; final prioritization decision may require human approval, especially for production systems.

### `MitigationDeployed`

- **Node name**: `MitigationDeployed`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether a mitigation has already
  been deployed to affected systems
- **Input dependency**: Query to asset/patch management system, deployment
  pipeline status, or case metadata flag
- **Notes**: Fails most of the time in simulation since mitigation
  deployment is modeled as the active goal
- **Automation potential**: **High** — query to patch management system or case-state flag; fully automatable.

### `MitigationAvailable`

- **Node name**: `MitigationAvailable`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether a mitigation (workaround
  or partial fix) is currently available for deployment
- **Input dependency**: Patch/advisory feed, internal mitigation catalog,
  or case status field
- **Notes**: Mitigations are available more often than not once the fix
  development cycle has progressed
- **Automation potential**: **High** — patch or advisory feed query; fully automatable once the feed integration is in place.

### `DeployMitigation`

- **Node name**: `DeployMitigation`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — apply the available mitigation to affected
  systems (e.g., configuration change, WAF rule, temporary patch)
- **Input dependency**: Human operator prompt or automated deployment
  pipeline; patch management or configuration management system integration
- **Notes**: Succeeds most of the time in simulation; production
  implementation would integrate with patch/config management tooling
- **Automation potential**: **Medium** — automated deployment is feasible for some environments (configuration management, cloud); human approval is typically required for production system changes.

### `MonitoringRequirement`

- **Node name**: `MonitoringRequirement`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether organizational policy
  requires active monitoring of the fix deployment
- **Input dependency**: Policy engine or static organizational configuration;
  determines if post-deployment monitoring is mandatory
- **Notes**: A policy decision; could be a static rule or context-dependent
  evaluation
- **Automation potential**: **High** — policy rule evaluation against case context (severity, asset class, environment); fully automatable as a policy engine check.

### `MonitorDeployment`

- **Node name**: `MonitorDeployment`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — initiate or perform ongoing monitoring of
  the fix deployment to verify completeness and effectiveness
- **Input dependency**: Integration with asset management, patch
  verification tools, or security monitoring platforms
- **Notes**: Always succeeds in simulation; in production monitors
  deployment coverage metrics
- **Automation potential**: **High** — integration with deployment verification tools, patch compliance dashboards, or asset management platforms; fully automatable.

### `DeployFix`

- **Node name**: `DeployFix`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — deploy the completed fix to all affected
  systems (full patch deployment, as opposed to a temporary mitigation)
- **Input dependency**: Human operator action or automated release pipeline;
  patch management system or software update infrastructure
- **Notes**: Modeled as rare per-tick because full fix deployment is a
  significant, infrequent milestone; over many ticks it eventually succeeds
- **Automation potential**: **Medium** — release pipeline and patch distribution can be automated (CI/CD, package repositories); human approval gate is commonly required for production releases.

---

## Exploit Acquisition

These nodes belong to the `AcquireExploit` fallback tree
(`vultron/bt/report_management/_behaviors/acquire_exploit.py`), which models
a participant's process for obtaining a working exploit for the
vulnerability, typically to support impact assessment or testing.

### `HaveExploit`

- **Node name**: `HaveExploit`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/acquire_exploit.py`
- **Parent tree**: `AcquireExploit`
- **Semantic function**: Condition — check whether the organization already
  possesses a working exploit for this vulnerability
- **Input dependency**: Internal exploit repository or threat intelligence
  platform query
- **Notes**: Fails most of the time since acquiring the exploit is the
  modeled goal
- **Automation potential**: **High** — query against an internal exploit repository or threat-intelligence platform; fully automatable.

### `ExploitPrioritySet`

- **Node name**: `ExploitPrioritySet`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/acquire_exploit.py`
- **Parent tree**: `AcquireExploit`
- **Semantic function**: Condition — check whether a priority decision for
  exploit acquisition has already been recorded for this case
- **Input dependency**: Case metadata / process state check; automatable
  as a flag query
- **Notes**: Succeeds almost always because priority-setting is a
  prerequisite step that runs early
- **Automation potential**: **High** — metadata flag check on the case record; fully automatable.

### `EvaluateExploitPriority`

- **Node name**: `EvaluateExploitPriority`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/acquire_exploit.py`
- **Parent tree**: `AcquireExploit`
- **Semantic function**: Action — assess and record the organization's
  priority for acquiring an exploit for this vulnerability
- **Input dependency**: Human analyst decision, potentially supported by
  SSVC/CVSS scoring data and organizational policy
- **Notes**: Always succeeds in simulation; in production drives the
  `ExploitDesired` and `ExploitDeferred` outcomes
- **Automation potential**: **Medium** — SSVC/CVSS scoring inputs are automatable; the final exploit-acquisition priority decision often requires human analyst judgment given organizational and legal context.

### `ExploitDeferred`

- **Node name**: `ExploitDeferred`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/acquire_exploit.py`
- **Parent tree**: `AcquireExploit`
- **Semantic function**: Condition — check whether the priority evaluation
  resulted in a decision to defer exploit acquisition
- **Input dependency**: Result of `EvaluateExploitPriority`; case metadata
  flag or priority queue status
- **Notes**: Succeeds (deferred) more often than not, reflecting that
  exploit acquisition is not always the highest priority
- **Automation potential**: **High** — read the outcome of the priority evaluation from case metadata; fully automatable.

### `ExploitDesired`

- **Node name**: `ExploitDesired`
- **btz type**: `OftenFail` (p=0.30)
- **Source file**: `report_management/fuzzer/acquire_exploit.py`
- **Parent tree**: `AcquireExploit`
- **Semantic function**: Condition — check whether the priority evaluation
  resulted in a positive decision to acquire an exploit
- **Input dependency**: Result of `EvaluateExploitPriority`; case metadata
  flag or priority queue status
- **Notes**: Complements `ExploitDeferred`; fails more often than it succeeds
- **Automation potential**: **High** — read the outcome of the priority evaluation from case metadata; fully automatable.

### `FindExploit`

- **Node name**: `FindExploit`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/acquire_exploit.py`
- **Parent tree**: `AcquireExploit`
- **Semantic function**: Action — search for an existing exploit in external
  sources (exploit databases, threat intelligence feeds, dark web
  repositories)
- **Input dependency**: Automated search against exploit databases (e.g.,
  ExploitDB, Metasploit modules, NVD, threat intel platforms), or human
  researcher search
- **Notes**: Succeeds rarely because public exploits for specific
  vulnerabilities are uncommon at intake time
- **Automation potential**: **High** — automated search of exploit databases (ExploitDB, Metasploit module index, NVD exploit references, threat-intel APIs) is fully feasible.

### `DevelopExploit`

- **Node name**: `DevelopExploit`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/acquire_exploit.py`
- **Parent tree**: `AcquireExploit`
- **Semantic function**: Action — develop a proof-of-concept or working
  exploit internally to confirm exploitability
- **Input dependency**: Human security researcher task; bug bounty or
  internal red team assignment
- **Notes**: Succeeds often in simulation to model that internal
  development is more reliably achievable than finding an external exploit
- **Automation potential**: **Low** — security research requiring human expertise; cannot be meaningfully automated in the general case.

### `PurchaseExploit`

- **Node name**: `PurchaseExploit`
- **btz type**: `RarelySucceed` / `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/acquire_exploit.py`
- **Parent tree**: `AcquireExploit`
- **Semantic function**: Action — procure a working exploit from a commercial
  or grey-market source
- **Input dependency**: Human procurement decision; commercial exploit
  brokerage or bug bounty marketplace interaction
- **Notes**: Modeled as rare; purchasing exploits is uncommon and involves
  legal/policy considerations
- **Automation potential**: **Low** — procurement and legal authorization require human decision-making; cannot be automated.

---

## Threat Monitoring

These nodes belong to the `MonitorThreats` fallback tree
(`vultron/bt/report_management/_behaviors/monitor_threats.py`), which models
continuous scanning for evidence that the vulnerability is being actively
exploited in the wild. Threat detection can trigger embargo termination via
`TerminateEmbargoBt`.

### `MonitorAttacks`

- **Node name**: `MonitorAttacks`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan threat intelligence feeds
  and security telemetry for evidence of active attacks exploiting this
  vulnerability
- **Input dependency**: Threat intelligence platform integration (e.g.,
  ISAC feeds, IDS/IPS alerts, SIEM queries), CTI API, or human analyst
  review of threat reports
- **Notes**: Succeeds rarely to reflect the low base rate of detected
  in-the-wild attacks during active coordination
- **Automation potential**: **High** — SIEM queries, IDS/IPS alert feeds, and threat-intelligence platform APIs can fully automate in-the-wild attack detection.

### `MonitorExploits`

- **Node name**: `MonitorExploits`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan exploit databases and
  vulnerability intelligence sources for newly published exploits targeting
  this vulnerability
- **Input dependency**: Exploit database feeds (ExploitDB, Metasploit,
  GitHub), threat intelligence platforms, CVE/NVD exploit availability
  fields, or human analyst monitoring
- **Notes**: Rarely succeeds; public exploits typically appear after
  disclosure, not during the coordination phase
- **Automation potential**: **High** — exploit database feeds, CVE enrichment APIs, and threat-intel platforms can fully automate exploit publication monitoring.

### `MonitorPublicReports`

- **Node name**: `MonitorPublicReports`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan public sources (news,
  social media, security blogs, full-disclosure lists) for reports of
  this vulnerability being publicly known
- **Input dependency**: Open-source intelligence (OSINT) tools, RSS/news
  feed monitoring, social media tracking, or human analyst media review
- **Notes**: Somewhat more likely to trigger than attack/exploit detection
  because public discussion of vulnerabilities is more common than
  confirmed attacks
- **Automation potential**: **High** — RSS/news feed monitoring, OSINT tools, and social-media tracking APIs can automate public disclosure detection with high coverage.

### `NoThreatsFound`

- **Node name**: `NoThreatsFound`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Fallback leaf — confirm that no threats were
  detected in this monitoring cycle; keep the monitoring branch from
  failing when all monitoring nodes return failure
- **Input dependency**: None; terminal success placeholder
- **Notes**: Ensures `MonitorThreats` always succeeds so the broader
  workflow continues uninterrupted
- **Automation potential**: **N/A** — terminal success placeholder; no real decision logic required.

---

## Publication

These nodes belong to the `Publication` fallback tree
(`vultron/bt/report_management/_behaviors/publication.py`), which models
the process of deciding what vulnerability-related artifacts to publish,
preparing them, and executing publication.

### `AllPublished`

- **Node name**: `AllPublished`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether all intended publication
  artifacts (report, fix, exploit) have been published
- **Input dependency**: Case/publication status metadata query; automatable
  against a publication tracking field
- **Notes**: Fails most of the time in simulation because publication
  is an active goal being worked toward
- **Automation potential**: **High** — publication status flag on the case record; fully automatable as a metadata check.

### `PublicationIntentsSet`

- **Node name**: `PublicationIntentsSet`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether publication intentions
  (what to publish, when, and in what format) have been established for
  this case
- **Input dependency**: Case metadata check; publication plan document or
  structured publication intent flags
- **Notes**: Fails most of the time in simulation because setting intents
  is an early workflow step being modeled
- **Automation potential**: **High** — publication intent flags on the case record; fully automatable as a metadata check.

### `PrioritizePublicationIntents`

- **Node name**: `PrioritizePublicationIntents`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — establish and record publication
  intentions: what artifacts to publish, their priority order, timing, and
  format
- **Input dependency**: Human analyst decision, publication policy, or
  automated policy engine; may depend on case context (embargo status,
  fix availability, threat level)
- **Notes**: Always succeeds in simulation; in production this involves
  structured editorial/policy decisions
- **Automation potential**: **Medium** — standard policy-driven publication priorities (e.g., always publish report and fix) can be automated; editorial or legal exceptions require human judgment.

### `Publish`

- **Node name**: `Publish`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — execute the publication of a prepared
  artifact to the intended audience (advisory, patch, bulletin, etc.)
- **Input dependency**: Publication platform API (CMS, advisory database,
  package repository, NVD/CVE submission); could be fully automated
- **Notes**: Succeeds almost always in simulation; in production may involve
  API calls to advisory publishing platforms
- **Automation potential**: **High** — advisory platform APIs (NVD, CVE.org, CMS, package repository) enable fully automated artifact publication.

### `NoPublishExploit`

- **Node name**: `NoPublishExploit`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for
  the exploit artifact; `SUCCESS` means "do not publish exploit"
- **Input dependency**: Publication intent record set by
  `PrioritizePublicationIntents`; case policy
- **Notes**: Succeeds (no exploit publication) in most cases, reflecting
  that exploit publication is not always required or desired
- **Automation potential**: **High** — read the exploit publication intent flag from the case record; fully automatable.

### `ExploitReady`

- **Node name**: `ExploitReady`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether the exploit artifact is
  ready for publication (prepared, reviewed, and staged)
- **Input dependency**: Artifact status metadata; staging system check
- **Notes**: Ready more often than not once preparation has started
- **Automation potential**: **High** — artifact staging-status check in the publishing pipeline; fully automatable.

### `PrepareExploit`

- **Node name**: `PrepareExploit`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, document, and stage the exploit
  artifact for publication (write-up, code packaging, filing in publishing
  system)
- **Input dependency**: Human security researcher; content authoring and
  artifact staging workflow
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low** — write-up and proof-of-concept packaging require human security researcher expertise; not automatable in the general case.

### `ReprioritizeExploit`

- **Node name**: `ReprioritizeExploit`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the exploit artifact
  in the publication queue (e.g., in response to a changing threat
  landscape or embargo state change)
- **Input dependency**: Human analyst or automated policy trigger; priority
  queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — embargo state changes and threat-level updates can trigger automated reprioritization rules; human override may be needed for unusual cases.

### `NoPublishFix`

- **Node name**: `NoPublishFix`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for
  the fix artifact; `SUCCESS` means "do not publish fix"
- **Input dependency**: Publication intent record; case policy
- **Notes**: Fails most of the time because fix publication is the standard
  expected outcome of CVD
- **Automation potential**: **High** — read the fix publication intent flag from the case record; fully automatable.

### `PrepareFix`

- **Node name**: `PrepareFix`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, document, and stage the fix
  artifact for publication (patch notes, release artifacts, advisory text)
- **Input dependency**: Engineering team output; patch release pipeline
  and content authoring workflow
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low–Medium** — CI/CD pipeline can automate patch build and packaging; advisory text and release notes typically require human authoring and review.

### `ReprioritizeFix`

- **Node name**: `ReprioritizeFix`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the fix artifact
  in the publication queue
- **Input dependency**: Human analyst or automated policy trigger; priority
  queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — embargo state changes and threat-level updates can trigger automated reprioritization rules; human override may be needed.

### `NoPublishReport`

- **Node name**: `NoPublishReport`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for
  the vulnerability report artifact; `SUCCESS` means "do not publish
  report"
- **Input dependency**: Publication intent record; case policy
- **Notes**: Fails most of the time because report publication is standard
  CVD outcome
- **Automation potential**: **High** — read the report publication intent flag from the case record; fully automatable.

### `PrepareReport`

- **Node name**: `PrepareReport`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, review, and stage the vulnerability
  advisory or report artifact for publication
- **Input dependency**: Human analyst; content authoring, review, and
  approval workflow; advisory publishing pipeline
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low** — advisory writing requires human expertise and editorial judgment; review and approval workflow also typically involves human stakeholders.

### `ReprioritizeReport`

- **Node name**: `ReprioritizeReport`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the report artifact
  in the publication queue
- **Input dependency**: Human analyst or automated policy trigger; priority
  queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — policy-triggered reprioritization (e.g., on embargo exit or threat escalation) is automatable; complex editorial decisions require human oversight.

---

## Reporting to Other Parties

These nodes belong to the `MaybeReportToOthers` sequence tree
(`vultron/bt/report_management/_behaviors/report_to_others.py`), which
models the process of identifying and notifying additional stakeholders
(vendors, coordinators, and other parties) who should be involved in the
coordinated disclosure.

### `HaveReportToOthersCapability`

- **Node name**: `HaveReportToOthersCapability`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether this participant has
  the capability and mandate to notify other parties
- **Input dependency**: Role/capability configuration; static metadata
  check on the participant's CVD role and organizational policy
- **Notes**: In production this is typically a static capability check,
  not a dynamic decision
- **Automation potential**: **High** — static capability and role configuration check; fully automatable as a metadata lookup.

### `AllPartiesKnown`

- **Node name**: `AllPartiesKnown`
- **btz type**: `UniformSucceedFail` (p=0.50)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether all relevant parties
  that should receive notification have been identified
- **Input dependency**: Human analyst assessment; completion check on the
  party identification workflow
- **Notes**: Modeled as a coin flip in simulation because identification
  completeness is inherently uncertain
- **Automation potential**: **Low** — inherently requires human expert judgment about stakeholder completeness in a specific vulnerability context; hard to automate reliably.

### `IdentifyVendors`

- **Node name**: `IdentifyVendors`
- **btz type**: `SuccessOrRunning` (p=0.50; never fails)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — identify the software vendors responsible
  for the affected product(s) so they can be notified
- **Input dependency**: Human analyst research; product/vendor databases
  (CPE, NVD product data, SBOM, asset inventory), supply chain data, or
  OSINT
- **Notes**: Uses `SuccessOrRunning` to model that vendor identification
  may be an ongoing (multi-tick) process; never hard-fails
- **Automation potential**: **Medium** — CPE/product database lookups, SBOM analysis, and NVD product data queries are automatable for known products; novel, multi-vendor, or open-source supply-chain cases benefit from human review.

### `IdentifyCoordinators`

- **Node name**: `IdentifyCoordinators`
- **btz type**: `SuccessOrRunning` (p=0.50; never fails)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — identify any coordinator organizations
  (e.g., CERT/CC, national CSIRTs) that should be involved in the
  disclosure
- **Input dependency**: Human analyst judgment; coordinator registry or
  directory (e.g., FIRST member directory, national CSIRT listings),
  or organizational policy on when to involve coordinators
- **Notes**: Uses `SuccessOrRunning` to model an ongoing identification
  process; never hard-fails
- **Automation potential**: **Medium** — FIRST member directory and national CSIRT registry lookups are automatable; routing policy (when to involve a coordinator) may require human judgment.

### `IdentifyOthers`

- **Node name**: `IdentifyOthers`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — identify any other parties (beyond vendors
  and coordinators) that should be notified
- **Input dependency**: Human analyst judgment; case-specific stakeholder
  analysis
- **Notes**: Always succeeds in simulation (stub placeholder)
- **Automation potential**: **Low** — by definition a catch-all for non-vendor, non-coordinator parties; requires human expert assessment of the specific disclosure context.

### `NotificationsComplete`

- **Node name**: `NotificationsComplete`
- **btz type**: `UniformSucceedFail` (p=0.50)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether all identified parties
  have been successfully notified
- **Input dependency**: Notification tracking metadata; outbound message
  status records for each identified recipient
- **Notes**: Modeled as a coin flip; in production this is a status check
  against a notification queue
- **Automation potential**: **High** — notification status tracking against the identified-parties queue; fully automatable.

### `ChooseRecipient`

- **Node name**: `ChooseRecipient`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — select the next recipient from the
  identified-parties list for notification
- **Input dependency**: Automated queue selection; priority ordering of
  the identified parties list
- **Notes**: Could be fully automated; always succeeds in simulation
- **Automation potential**: **High** — deterministic queue selection from the identified-parties list; fully automatable.

### `RemoveRecipient`

- **Node name**: `RemoveRecipient`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — remove a recipient from the pending
  notification queue (after successful notification or after effort
  limits are exceeded)
- **Input dependency**: Notification queue management; could be automated
- **Notes**: Always succeeds in simulation
- **Automation potential**: **High** — queue management operation; fully automatable.

### `RecipientEffortExceeded`

- **Node name**: `RecipientEffortExceeded`
- **btz type**: `AlmostCertainlyFail` (p=0.07)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether the effort spent trying
  to notify a specific recipient has exceeded an organizational threshold
  (e.g., 3 contact attempts, 1 hour of effort)
- **Input dependency**: Effort tracking metadata per recipient; configurable
  policy threshold; may require human analyst judgment
- **Notes**: Rarely triggers in simulation; in production enforces
  reasonable limits on notification attempts
- **Automation potential**: **High** — effort counter check against a configurable policy threshold; fully automatable once the threshold policy is defined.

### `TotalEffortLimitMet`

- **Node name**: `TotalEffortLimitMet`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether the total effort across
  all notification attempts has exceeded an organizational ceiling
- **Input dependency**: Aggregate effort tracking; configurable policy
  threshold; may require human analyst review
- **Notes**: Rarely triggers in simulation; provides a global stop
  condition to prevent unbounded notification effort
- **Automation potential**: **High** — aggregate effort counter check against a configurable policy ceiling; fully automatable.

### `PolicyCompatible`

- **Node name**: `PolicyCompatible`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether the potential recipient's
  disclosure/embargo policy is compatible with the case's current embargo
  expectations before notifying them
- **Input dependency**: Policy comparison between recipient's published
  CVD policy and the case embargo terms; could be automated via a
  policy registry, or require human analyst judgment
- **Notes**: In production may involve structured policy comparison tooling
- **Automation potential**: **Medium** — comparison between the recipient's published CVD policy and the case embargo terms is automatable for machine-readable policies (e.g., OpenVEX, structured security.txt); human review needed for ambiguous or informal policies.

### `FindContact`

- **Node name**: `FindContact`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — look up contact information for the
  chosen recipient (security email, bug bounty platform, disclosure portal)
- **Input dependency**: Contact directory lookup (e.g., security.txt,
  vendor security contacts, FIRST member database, PSIRT directory);
  could be automated for well-known organizations
- **Notes**: Succeeds most of the time; may fail for lesser-known vendors
  with no published security contact
- **Automation potential**: **High** — security.txt lookup, PSIRT directory queries, FIRST member database, and NVD contact data are all automatable for well-known organizations; obscure vendors may require manual research.

### `RcptNotInQrmS`

- **Node name**: `RcptNotInQrmS`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — verify that the recipient has not
  already been notified (i.e., their RM state is still START / not yet
  RECEIVED)
- **Input dependency**: Case state lookup; RM state record for the
  recipient participant; automatable
- **Notes**: Succeeds almost always; guards against duplicate notifications
- **Automation potential**: **High** — RM state query against the case participant record; fully automatable.

### `SetRcptQrmR`

- **Node name**: `SetRcptQrmR`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — record that the recipient has been
  notified by transitioning their RM state from START to RECEIVED
- **Input dependency**: State write to case management system; automatable
  state transition
- **Notes**: Always succeeds in simulation; in production performs
  a state update
- **Automation potential**: **High** — RM state write on the case participant record; fully automatable.

### `MoreVendors`

- **Node name**: `MoreVendors`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether there are more vendor
  parties in the identified-but-not-yet-notified queue
- **Input dependency**: Query to the vendor notification queue; automatable
  against the identified-parties list
- **Notes**: Fails most of the time in simulation because the vendor list
  is usually short
- **Automation potential**: **High** — query against the vendor notification queue; fully automatable.

### `MoreCoordinators`

- **Node name**: `MoreCoordinators`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether there are more coordinator
  parties pending notification
- **Input dependency**: Query to the coordinator notification queue;
  automatable
- **Notes**: Fails almost always because the coordinator list is typically
  short (often zero or one)
- **Automation potential**: **High** — query against the coordinator notification queue; fully automatable.

### `MoreOthers`

- **Node name**: `MoreOthers`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether there are more "other"
  parties pending notification
- **Input dependency**: Query to the other-parties notification queue;
  automatable
- **Notes**: Fails almost always; catch-all category is usually empty
- **Automation potential**: **High** — query against the other-parties notification queue; fully automatable.

### `InjectParticipant`

- **Node name**: `InjectParticipant`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — add a new participant to the case (generic
  form; specialized by `InjectVendor`, `InjectCoordinator`, `InjectOther`)
- **Input dependency**: Case management system write; triggered after a
  recipient is successfully notified and agrees to participate
- **Notes**: Always succeeds in simulation; base class for the three
  role-specific inject nodes below
- **Automation potential**: **High** — case management system write; fully automatable once participant details are known.

### `InjectVendor`

- **Node name**: `InjectVendor`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — add an identified vendor as a participant
  in the coordinated disclosure case
- **Input dependency**: Case management system write; vendor contact and
  acceptance of participation
- **Notes**: Specialization of `InjectParticipant` for vendor role
- **Automation potential**: **High** — case management system write for vendor role; fully automatable.

### `InjectCoordinator`

- **Node name**: `InjectCoordinator`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — add an identified coordinator as a
  participant in the coordinated disclosure case
- **Input dependency**: Case management system write; coordinator contact
  and acceptance of participation
- **Notes**: Specialization of `InjectParticipant` for coordinator role
- **Automation potential**: **High** — case management system write for coordinator role; fully automatable.

### `InjectOther`

- **Node name**: `InjectOther`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — add any other identified party as a
  participant in the coordinated disclosure case
- **Input dependency**: Case management system write; stakeholder contact
  and acceptance of participation
- **Notes**: Specialization of `InjectParticipant` for other-party role
- **Automation potential**: **High** — case management system write for other-party role; fully automatable.

---

## Report Closure

These nodes belong to `RMCloseBt`
(`vultron/bt/report_management/_behaviors/close_report.py`), which models
the process of closing a vulnerability report once the CVD workflow is
complete (or otherwise concluded).

### `OtherCloseCriteriaMet`

- **Node name**: `OtherCloseCriteriaMet`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/close_report.py`
- **Parent tree**: `RMCloseBt`
- **Semantic function**: Condition — check whether site-specific or
  case-specific closure criteria (beyond the standard CVD completion
  conditions) have been met
- **Input dependency**: Human analyst decision or policy-driven checklist;
  context-specific to organizational CVD policy
- **Notes**: Fails most of the time in simulation because non-standard
  closure criteria are uncommon; may represent editorial board sign-off,
  legal review completion, etc.
- **Automation potential**: **Low** — site-specific; closure criteria vary widely by organization and case context; typically requires human policy evaluation or explicit sign-off.

### `PreCloseAction`

- **Node name**: `PreCloseAction`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/close_report.py`
- **Parent tree**: `RMCloseBt`
- **Semantic function**: Action — execute any site-specific tasks that must
  be completed before a report can be closed (e.g., quality assurance
  review, final stakeholder notification, archiving)
- **Input dependency**: Integration hook; QA pipeline, archiving system,
  or final notification API
- **Notes**: Always succeeds in simulation; production may involve
  multi-step pre-close workflows
- **Automation potential**: **Medium** — archiving and standard notification steps can be automated; QA review and final approvals typically require human involvement.

---

## Other Work (Do Work)

These nodes belong to `RMDoWorkBt`
(`vultron/bt/report_management/_behaviors/do_work.py`), the general
"do work" fallback tree that represents miscellaneous active work on an
accepted vulnerability report outside of the more specific sub-trees.

### `OtherWork`

- **Node name**: `OtherWork`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/other_work.py`
- **Parent tree**: `RMDoWorkBt`
- **Semantic function**: Action — placeholder for any additional work
  activities not covered by the more specific BT sub-trees (e.g.,
  internal documentation, stakeholder meetings, legal review, additional
  analysis)
- **Input dependency**: Site-specific work queue; human analyst tasks or
  automated workflow steps not yet modeled in the BT
- **Notes**: Always succeeds; this is an extensibility point for
  organizations to plug in their own workflow steps
- **Automation potential**: **Low** — intentional extensibility stub for unmodeled work; automation potential is entirely site-specific and cannot be assessed generically.

---

## Inbound Message Handling

These nodes are used within `ReceiveMessagesBt`
(`vultron/bt/messaging/inbound/behaviors.py`) across the RM, EM, CS, and
general message-handling sub-trees. They handle error conditions arising
from unexpected or malformed inbound protocol messages.

### `FollowUpOnErrorMessage`

- **Node name**: `FollowUpOnErrorMessage`
- **btz type**: `UniformSucceedFail` (p=0.50) as a child inside a
  `fallback_node`
- **Source file**: `messaging/inbound/_behaviors/fuzzer.py`
- **Parent tree**: Used in RM, EM, CS, and general message handlers within
  `ReceiveMessagesBt`
- **Semantic function**: Action — when an unexpected or error message type
  is received, attempt to send a follow-up inquiry (GI message) to the
  sender to request clarification
- **Input dependency**: Protocol error-handling policy; may require human
  analyst involvement for unusual error conditions; automated GI message
  dispatch for standard cases
- **Notes**: Implemented as a fallback node containing a 50/50 random
  success and `EmitGI`; models the uncertainty of whether a follow-up
  inquiry will be sent; in production this should be a deterministic
  policy-driven action
- **Automation potential**: **High** — deterministic policy-driven GI message dispatch in response to error conditions; can be fully automated once the follow-up policy is defined.

---

*This document was generated by studying the `vultron/bt` behavior tree*
*simulation code. Last updated: 2026-03-04.*

---

## Related

- `notes/bt-integration.md` — canonical subtree map; each fuzzer
  node listed here is an integration point where a real behavior subtree
  will replace the stub. The canonical-bt-reference maps these points to
  their use-case BT targets.
- `specs/behavior-tree-integration.md` BT-06-001 — all protocol-significant
  behaviors must be BT nodes or subtrees; fuzzer stubs are placeholders
  until the real subtree is implemented
- `notes/bt-integration.md` — BT design decisions and composability model
