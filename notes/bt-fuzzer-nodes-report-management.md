---
title: "BT Fuzzer Nodes: Report Management"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for Report Management workflows in
  the Vultron BT simulation, covering validation, prioritization, ID assignment,
  fix development and deployment, exploit/threat tracking, publication,
  reporting to other parties, and report closure.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/report_management
---

# BT Fuzzer Nodes: Report Management

These are the stub nodes for report management BT sub-trees:
`ValidateReportBt`, `PrioritizeReportBt`, `AssignVulIdBt`, `DevelopFixBt`,
`DeployFixBt`, `MonitorThreatsBt`, `AcquireExploitBt`, `PublicationBt`,
`ReportToOthersBt`, `CloseReportBt`, and `OtherWorkBt` (all sourced from
`vultron/bt/report_management/fuzzer/`). See `notes/bt-fuzzer-nodes.md`
for background on what fuzzer nodes are and the full catalog index.

**Fuzzer base types quick reference:**

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.NoNewValidationInfo`
- **Call-out point shape**: Sentinel — binary change-detection condition; monitors the case record for new validation-relevant events via a metadata timestamp or event subscription; returns SUCCESS/FAILURE with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EvaluateReportCredibility`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EvaluateReportValidity`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EnoughValidationInfo`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.GatherValidationInfo`
- **Call-out point shape**: Retriever

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.NoNewPrioritizationInfo`
- **Call-out point shape**: Sentinel — binary change-detection condition; monitors the case record for new prioritization-relevant events via a metadata timestamp or event subscription; returns SUCCESS/FAILURE with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.EnoughPrioritizationInfo`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.GatherPrioritizationInfo`
- **Call-out point shape**: Retriever

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.OnDefer`
- **Call-out point shape**: Composer — integration hook that generates outbound notifications, schedules follow-up tasks, and writes case-status updates when a report is deferred; the produced artifacts are the emitted stakeholder notifications and workflow records.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.OnAccept`
- **Call-out point shape**: Composer — integration hook that generates outbound notifications, initializes the case workflow, and writes case-status updates when a report is accepted; the produced artifacts are the emitted stakeholder notifications and workflow-initialization records.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IdAssigned`
- **Call-out point shape**: Sentinel — binary status check against case metadata or an external vulnerability registry; returns SUCCESS if an identifier has already been assigned to this vulnerability, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.InScope`
- **Call-out point shape**: Sentinel — binary policy check against CNA scope rules or a product/component registry; returns SUCCESS if the vulnerability falls within the applicable ID namespace, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IsIDAssignmentAuthority`
- **Call-out point shape**: Sentinel — binary organizational capability check against static participant metadata; returns SUCCESS if this participant holds ID-assignment authority, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IdAssignable`
- **Call-out point shape**: Sentinel — binary CNA-scope check against CNA rules and product-to-CNA mappings; returns SUCCESS if this participant has assignment authority for this specific vulnerability, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.RequestId`
- **Call-out point shape**: Retriever — queries an external ID assignment authority (e.g., CVE Services API) with a reservation/assignment request and writes the resulting assigned ID to the case record; SUCCESS = ID retrieved and recorded.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.AssignId`
- **Call-out point shape**: Composer — generates a new vulnerability identifier from this participant's own ID pool via the ID management system or CVE Services reserve/assign endpoint; the produced artifact is the newly assigned ID recorded in the case.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.develop_fix.CreateFix`
- **Call-out point shape**: Composer

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.NoNewDeploymentInfo`
- **Call-out point shape**: Sentinel — binary change-detection condition; monitors the case/deployment record for new deployment-relevant events via a metadata timestamp or event subscription; returns SUCCESS/FAILURE with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.PrioritizeDeployment`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MitigationDeployed`
- **Call-out point shape**: Sentinel — binary status query against an asset/patch management system or case-state flag; returns SUCCESS if a mitigation has been deployed, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MitigationAvailable`
- **Call-out point shape**: Sentinel — binary availability query against a patch/advisory feed or internal mitigation catalog; returns SUCCESS if a mitigation is currently available, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.DeployMitigation`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MonitoringRequirement`
- **Call-out point shape**: Sentinel — binary policy-rule evaluation against case context (severity, asset class, environment); returns SUCCESS if organizational policy requires post-deployment monitoring for this case, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MonitorDeployment`
- **Call-out point shape**: Sentinel

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.DeployFix`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.acquire_exploit.HaveExploit`
- **Call-out point shape**: Sentinel — binary query against an internal exploit repository or threat-intelligence platform; returns SUCCESS if a working exploit is already available for this vulnerability, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.acquire_exploit.ExploitPrioritySet`
- **Call-out point shape**: Sentinel — binary case-metadata flag check; returns SUCCESS if a priority decision for exploit acquisition has already been recorded for this case, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.acquire_exploit.EvaluateExploitPriority`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.acquire_exploit.ExploitDeferred`
- **Call-out point shape**: Sentinel — binary case-metadata flag check against the outcome written by EvaluateExploitPriority; returns SUCCESS if the decision was to defer exploit acquisition, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.acquire_exploit.ExploitDesired`
- **Call-out point shape**: Sentinel — binary case-metadata flag check against the outcome written by EvaluateExploitPriority; returns SUCCESS if the decision was to acquire an exploit, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.acquire_exploit.FindExploit`
- **Call-out point shape**: Retriever

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.acquire_exploit.DevelopExploit`
- **Call-out point shape**: Composer

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.acquire_exploit.PurchaseExploit`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorAttacks`
- **Call-out point shape**: Sentinel

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorExploits`
- **Call-out point shape**: Sentinel

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorPublicReports`
- **Call-out point shape**: Sentinel

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
- **Automation potential**: **TerminalPlaceholder** — terminal success placeholder; no real decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.NoThreatsFound`
- **Call-out point shape**: ProtocolInternal — terminal success placeholder; AlwaysSucceed fallback leaf that prevents MonitorThreats from failing when no active threats are detected in this monitoring cycle; no external input, output, or monitoring seam.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.AllPublished`
- **Call-out point shape**: Sentinel — binary publication-status check against a case-record flag; returns SUCCESS if all intended publication artifacts have been published, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PublicationIntentsSet`
- **Call-out point shape**: Sentinel — binary case-metadata flag check; returns SUCCESS if publication intentions have already been established for this case, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrioritizePublicationIntents`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.Publish`
- **Call-out point shape**: Composer — submits a prepared publication artifact to an external advisory platform (NVD, CVE.org, CMS, package repository, or equivalent); the produced artifact is the externally visible published entry at the target platform.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishExploit`
- **Call-out point shape**: Sentinel — binary publication-intent flag check against the record set by PrioritizePublicationIntents; returns SUCCESS if the exploit is not intended for publication, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ExploitReady`
- **Call-out point shape**: Sentinel — binary artifact-staging status check against the publishing pipeline; returns SUCCESS if the exploit artifact is staged and ready for publication, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareExploit`
- **Call-out point shape**: Composer

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeExploit`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishFix`
- **Call-out point shape**: Sentinel — binary publication-intent flag check against the record set by PrioritizePublicationIntents; returns SUCCESS if the fix is not intended for publication, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareFix`
- **Call-out point shape**: Composer

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeFix`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishReport`
- **Call-out point shape**: Sentinel — binary publication-intent flag check against the record set by PrioritizePublicationIntents; returns SUCCESS if the vulnerability report is not intended for publication, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareReport`
- **Call-out point shape**: Composer

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeReport`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.HaveReportToOthersCapability`
- **Call-out point shape**: Sentinel — binary role/capability configuration check against participant metadata and organizational policy; returns SUCCESS if this participant has the capability and mandate to notify other parties, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.AllPartiesKnown`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.IdentifyVendors`
- **Call-out point shape**: Retriever

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.IdentifyCoordinators`
- **Call-out point shape**: Retriever

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.IdentifyOthers`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.NotificationsComplete`
- **Call-out point shape**: Sentinel — binary status check against notification tracking metadata; returns SUCCESS if all identified parties have been successfully notified, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.ChooseRecipient`
- **Call-out point shape**: Retriever — reads the next recipient entry from the identified-parties queue according to the priority ordering and writes the selected recipient details to the blackboard for downstream nodes (FindContact, SetRcptQrmR, etc.); SUCCESS = next recipient selected and written.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.RemoveRecipient`
- **Call-out point shape**: Composer — writes a queue-removal record to the notification queue in the case management system, dequeuing the current recipient after successful notification or after the per-recipient effort limit is exceeded; the produced artifact is the updated queue state.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.RecipientEffortExceeded`
- **Call-out point shape**: Sentinel — binary effort-threshold check against the per-recipient attempt counter and a configurable policy threshold; returns SUCCESS if the notification-attempt budget for this recipient has been exhausted, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.TotalEffortLimitMet`
- **Call-out point shape**: Sentinel — binary aggregate effort-limit check against the total notification-effort counter and a configurable policy ceiling; returns SUCCESS if the global notification budget has been exhausted, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.PolicyCompatible`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.FindContact`
- **Call-out point shape**: Retriever

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.RcptNotInQrmS`
- **Call-out point shape**: Sentinel — binary RM-state check against the recipient's participant record in the case; returns SUCCESS if the recipient's RM state is still START (not yet notified), FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.SetRcptQrmR`
- **Call-out point shape**: Composer — writes a recipient RM-state transition (START → RECEIVED) to the case management system, recording that the recipient has been successfully notified; the produced artifact is the updated participant state record.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.MoreVendors`
- **Call-out point shape**: Sentinel — binary queue-status check against the vendor notification queue; returns SUCCESS if additional vendors are pending notification, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.MoreCoordinators`
- **Call-out point shape**: Sentinel — binary queue-status check against the coordinator notification queue; returns SUCCESS if additional coordinators are pending notification, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.MoreOthers`
- **Call-out point shape**: Sentinel — binary queue-status check against the other-parties notification queue; returns SUCCESS if additional other parties are pending notification, FAILURE otherwise, with no output keys.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectParticipant`
- **Call-out point shape**: Composer — writes a new participant record to the case management system, registering the notified party as an active case participant; the produced artifact is the participant entry in the case data store.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectVendor`
- **Call-out point shape**: Composer — inherits InjectParticipant; writes a vendor-role participant record to the case management system; the produced artifact is the vendor participant entry in the case data store.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectCoordinator`
- **Call-out point shape**: Composer — inherits InjectParticipant; writes a coordinator-role participant record to the case management system; the produced artifact is the coordinator participant entry in the case data store.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectOther`
- **Call-out point shape**: Composer — inherits InjectParticipant; writes an other-party participant record to the case management system; the produced artifact is the other-party participant entry in the case data store.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.close_report.OtherCloseCriteriaMet`
- **Call-out point shape**: Evaluator

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.close_report.PreCloseAction`
- **Call-out point shape**: Composer — triggers pre-close integration hooks including QA pipeline checks, final stakeholder notifications, and case archiving; the produced artifacts are the archive record, final notifications, and any required sign-off records.

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
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.other_work.OtherWork`
- **Call-out point shape**: Evaluator

---
