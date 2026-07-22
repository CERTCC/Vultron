---
title: "BT Fuzzer Nodes: Report Management"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for Report Management workflows in
  the Vultron BT simulation, covering validation, prioritization, ID assignment,
  fix development and deployment, exploit/threat tracking, publication,
  reporting to other parties, and report closure. Includes provisional
  production-collapse designs for four simulator subtree groups (issue #1200).
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-fuzzer-nodes.md
  - notes/coordination-agents.md
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
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream
  `NewValidationInfoSentinel` agent (see stub entry below). The external agent seam is at the
  Sentinel (event subscription or polling hook), not at this BT condition check. In production this
  node reads from the BT blackboard or case metadata written by the upstream Sentinel.
  (Category 2 per issue #1199 triage — consumes a flag written by an upstream Sentinel.)
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  ProtocolInternal condition check at the top of `ValidationOrShortcut` Selector;
  currently stubbed as `CheckRMStateValid` but the change-detection variant
  belongs here when the full retry loop is implemented (Phase 2)

### `NewValidationInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewValidationInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors the case record for new
  validation-relevant events (e.g., reporter follow-up, credibility update,
  new threat intelligence) and writes a change-detection flag that
  `NoNewValidationInfo` consumes.
- **Input dependency**: Case management system event stream; metadata
  timestamp comparison or event subscription on validation-relevant case
  fields.
- **Notes**: This is the real call-out point implied by `NoNewValidationInfo`.
  The upstream Sentinel registers with an external event source and writes
  a flag to the BT blackboard / local DataLayer; `NoNewValidationInfo` then
  reads that flag each BT tick. Implementation tracked in FUZZ-08f.
- **Automation potential**: **High** — event subscription on the case record
  or metadata timestamp comparison; fully automatable.
- **New-arch cross-ref**: *(to be implemented — see FUZZ-08f)*
- **Call-out point shape**: Sentinel — registers with a case-event source;
  fires a change-detection signal into the BT blackboard when new
  validation-relevant information arrives; no output keys beyond the flag.
- **Factory-fn placement**: FUZZ-08f (planned) — upstream agent seam, not
  placed inside the BT tree; writes a change-detection flag to the blackboard
  key read by `NoNewValidationInfo` at the top of the
  `ValidationOrShortcut` Selector in
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree`

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
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  Evaluator condition guard in `ValidationFlow` Sequence (second child, before
  `EvaluateReportValidity`); currently a stub `EvaluateReportCredibility` node
  that always returns SUCCESS

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
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  Evaluator condition guard in `ValidationFlow` Sequence (third child, before
  `ValidationActions`); currently a stub `EvaluateReportValidity` node that
  always returns SUCCESS

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
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  Evaluator condition guard in `ValidationFlow` Sequence (Phase 2); gate
  before the info-gathering loop that `GatherValidationInfo` populates

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
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  Retriever action node in the info-gathering Sequence (Phase 2), triggered
  when `EnoughValidationInfo` returns FAILURE

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
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream
  `NewPrioritizationInfoSentinel` agent (see stub entry below). The external agent seam is at the
  Sentinel (event subscription or polling hook), not at this BT condition check.
  (Category 2 per issue #1199 triage — consumes a flag written by an upstream Sentinel.)
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  ProtocolInternal condition check at the top of `PrioritizeBT` Selector; the retry
  skip-if-no-new-info check belongs here when the full re-prioritization
  loop is implemented (Phase 2)

### `NewPrioritizationInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewPrioritizationInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors the case record for new
  prioritization-relevant events (e.g., updated SSVC scoring data, new
  threat intelligence, CVSS score update) and writes a change-detection
  flag that `NoNewPrioritizationInfo` consumes.
- **Input dependency**: Case management system event stream; metadata
  timestamp comparison or event subscription on prioritization-relevant
  case fields (e.g., SSVC decision points, CVSS scores).
- **Notes**: This is the real call-out point implied by
  `NoNewPrioritizationInfo`. The upstream Sentinel registers with an
  external event source and writes a flag to the BT blackboard / local
  DataLayer; `NoNewPrioritizationInfo` reads that flag each BT tick.
  Implementation tracked in FUZZ-08f.
- **Automation potential**: **High** — event subscription on the case record
  or metadata timestamp comparison; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewPrioritizationInfoSentinel`
- **Call-out point shape**: Sentinel — registers with a case-event source;
  fires a change-detection signal into the BT blackboard when new
  prioritization-relevant information arrives; no output keys beyond the flag.
- **Factory-fn placement**: FUZZ-08f (planned) — upstream agent seam, not
  placed inside the BT tree; writes a change-detection flag to the blackboard
  key read by `NoNewPrioritizationInfo` at the top of the
  `PrioritizeBT` Selector in
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree`

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
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  Evaluator condition guard in the `PrioritizeBT` Sequence (Phase 2); gate
  before the info-gathering loop that `GatherPrioritizationInfo` populates

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
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  Retriever action node in the info-gathering Sequence (Phase 2), triggered
  when `EnoughPrioritizationInfo` returns FAILURE

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
- **Call-out point shape**: Actuator — fires integration hooks on report deferral; invokes notification APIs, task-scheduling services, and case-management state writes. There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  Actuator effect node appended to `DeferCaseTriggerBT` Sequence (in
  `create_defer_case_tree`), after `TransitionParticipantRMtoDeferred` and
  the sender-side subtree

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
- **Call-out point shape**: Actuator — fires integration hooks on report acceptance; invokes notification APIs, workflow-initialization services, and case-management state writes. There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  Actuator effect node appended to `EngageCaseTriggerBT` Sequence (in
  `create_engage_case_tree`), after `TransitionParticipantRMtoAccepted` and
  the sender-side subtree

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
- **Call-out point shape**: Retriever — synchronous on-demand query to case metadata or an external vulnerability registry (e.g., CVE database); returns SUCCESS if an identifier has already been assigned to this vulnerability, FAILURE otherwise. A boolean is the simplest structured fact (ADR-0024); the on-demand query pattern makes this a Retriever, not a Sentinel (see BT-18-006).
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  early-exit Retriever guard at the top of `AssignVulID` Fallback Selector;
  returns SUCCESS if an ID is already assigned, short-circuiting assignment work

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
- **Call-out point shape**: Evaluator — evaluates whether the vulnerability falls within the applicable ID namespace by comparing vulnerability attributes against CNA scope rules or a product/component registry; returns a policy judgment (in-scope or out-of-scope), not a binary monitor.
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.assign_vul_id_tree.create_assign_vul_id_tree`
  (`in_scope_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  Evaluator condition guard early in `AssignVulID` Sequence, before the
  authority-check nodes

### `IsIDAssignmentAuthority`

- **Node name**: `IsIDAssignmentAuthority`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether this participant is
  itself an ID assignment authority (e.g., a CVE CNA) able to assign
  IDs directly
- **Input dependency**: Organizational metadata / role configuration;
  fully automatable as a static capability check.  Driven by
  `CVDRole.CVE_NUMBERING_AUTHORITY` on the participant's `case_roles`
  list — if the participant holds this role, the check succeeds.
- **Notes**: In production this is a static configuration check, not a
  runtime decision.  Multiple participants in the same case may
  independently hold `CVDRole.CVE_NUMBERING_AUTHORITY` (e.g., a vendor
  CNA and a coordinator CNA); each evaluates this node independently in
  their own BT context.
- **Automation potential**: **High** — static organizational configuration; can be fully automated as a capability metadata lookup.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IsIDAssignmentAuthority`
- **Call-out point shape**: ProtocolInternal — reads a deployment-time configuration constant (`CVDRole.CVE_NUMBERING_AUTHORITY` on this participant's `case_roles`); the value is set at participant registration, not queried from an external system at runtime. There is no agent seam here: the check resolves entirely within the protocol's own DataLayer.
  (Category 2 per issue #1199 triage — reads a flag written by the protocol's own deployment-time setup.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  ProtocolInternal condition check in `AssignVulID` Sequence; evaluates
  participant role metadata before `IdAssignable` and `AssignId`

### `IdAssignable`

- **Node name**: `IdAssignable`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether this participant has
  authority to assign an ID to this specific vulnerability (e.g., is the
  authoritative CNA for the affected product)
- **Input dependency**: CNA rules lookup, product-to-CNA mapping, or
  human analyst determination.  Requires that the participant holds
  `CVDRole.CVE_NUMBERING_AUTHORITY` (necessary precondition, evaluated
  by `IsIDAssignmentAuthority`); this node then evaluates the CNA's
  scope rules against the specific vulnerability's affected product/
  component to determine whether assignment authority applies here.
- **Notes**: A participant may be an ID authority generally (holds
  `CVDRole.CVE_NUMBERING_AUTHORITY`) but not the authoritative CNA for
  this specific product.  The two checks are separate and sequential:
  `IsIDAssignmentAuthority` first, `IdAssignable` second.
- **Automation potential**: **High** — CNA-scope and product-to-CNA mapping checks are automatable via the CVE Services API or a local policy registry.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IdAssignable`
- **Call-out point shape**: Evaluator — evaluates whether this CNA
  (`CVDRole.CVE_NUMBERING_AUTHORITY` participant) has assignment
  authority for this specific vulnerability by matching vulnerability
  attributes against CNA scope rules and product-to-CNA mappings;
  a scope-matching evaluation, not a binary condition monitor.
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.assign_vul_id_tree.create_assign_vul_id_tree`
  (`id_assignable_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  Evaluator condition guard in the assign-direct path Sequence, after
  `IsIDAssignmentAuthority` succeeds

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  Retriever action node in the request-external-id Sequence, used when
  `IsIDAssignmentAuthority` fails (non-CNA path)

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  Composer action node in the direct-assign Sequence, used when
  `IdAssignable` succeeds (CNA-direct path)

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_develop_fix_tree` (issue #1247) —
  Composer action node in the `DevelopFix` Sequence; the primary work node

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
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream
  `NewDeploymentInfoSentinel` agent (see stub entry below). The external agent seam is at the
  Sentinel (event subscription or polling hook), not at this BT condition check.
  (Category 2 per issue #1199 triage — consumes a flag written by an upstream Sentinel.)
- **Factory-fn placement**: FUTURE (not wired in Phase 1 stub):
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248) —
  ProtocolInternal condition check at the top of `Deployment` Fallback Selector.
  Note: Phase 1 stub exists as of PR #1357 in
  `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree`
  but this ProtocolInternal node is not among the 4 factory params exposed.

### `NewDeploymentInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewDeploymentInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors deployment-relevant data sources
  (e.g., patch management system, CI/CD pipeline, asset inventory) for new
  deployment-related events and writes a change-detection flag that
  `NoNewDeploymentInfo` consumes.
- **Input dependency**: Patch management system event stream, CI/CD pipeline
  notifications, or asset-inventory change feed; metadata timestamp
  comparison or event subscription on deployment-relevant case fields.
- **Notes**: This is the real call-out point implied by
  `NoNewDeploymentInfo`. The upstream Sentinel registers with an external
  event source and writes a flag to the BT blackboard / local DataLayer;
  `NoNewDeploymentInfo` reads that flag each BT tick.
  Implementation tracked in FUZZ-08f.
- **Automation potential**: **High** — event subscription on the patch
  management system or CI/CD pipeline; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewDeploymentInfoSentinel`
- **Call-out point shape**: Sentinel — registers with a deployment-event
  source; fires a change-detection signal into the BT blackboard when new
  deployment-relevant information arrives; no output keys beyond the flag.
- **Factory-fn placement**: FUZZ-08f (planned) — upstream agent seam, not
  placed inside the BT tree; writes a change-detection flag to the blackboard
  key read by `NoNewDeploymentInfo` at the top of the `Deployment` Fallback
  Selector in
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248)

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
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree`
  (`prioritize_deployment_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248) —
  Evaluator action node in the `Deployment` Sequence, setting deployment
  priority before the mitigation/fix-deploy paths

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
- **Call-out point shape**: Retriever — synchronous on-demand query to an asset/patch management system or case-state flag; returns SUCCESS if a mitigation has been deployed, FAILURE otherwise. A boolean is the simplest structured fact (ADR-0024); the on-demand query pattern makes this a Retriever, not a Sentinel.
- **Factory-fn placement**: FUTURE (not wired in Phase 1 stub):
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248) —
  early-exit Retriever guard in `Deployment` Selector; short-circuits when
  mitigation is already deployed.
  Note: Phase 1 stub exists as of PR #1357 but this Retriever is not
  among the 4 factory params exposed.

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
- **Call-out point shape**: Retriever — synchronous on-demand query to a patch/advisory feed or internal mitigation catalog; returns SUCCESS if a mitigation is currently available, FAILURE otherwise. A boolean is the simplest structured fact (ADR-0024); the on-demand query pattern makes this a Retriever, not a Sentinel.
- **Factory-fn placement**: FUTURE (not wired in Phase 1 stub):
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248) —
  Retriever condition guard in the mitigation-deploy Sequence, before
  `DeployMitigation`; queries availability before attempting deployment.
  Note: Phase 1 stub exists as of PR #1357 but this Retriever is not
  among the 4 factory params exposed.

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
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree`
  (`deploy_mitigation_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248) —
  Evaluator action node in the mitigation-deploy Sequence, after
  `MitigationAvailable` succeeds

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
- **Call-out point shape**: Evaluator — evaluates whether organizational policy requires post-deployment monitoring for this case by applying policy rules against case context (severity, asset class, environment); a policy judgment call, not a binary condition monitor.
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree`
  (`monitoring_requirement_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248) —
  Evaluator condition guard in the monitoring-initiation Sequence; SUCCESS
  proceeds to `MonitorDeployment`

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
- **Call-out point shape**: Actuator — initiates external deployment-monitoring as a side-effect;
  invokes patch-compliance dashboard, deployment-verification API, or asset-management platform
  to start ongoing coverage tracking. There is no content artifact placed on the blackboard;
  the side effect in the external monitoring system is the seam. This is a fire-and-confirm
  action node, not a continuous monitor running outside the BT — the BT tick reaches this node
  once per `MonitoringRequirement` pass and asks the external system to begin tracking.
- **Factory-fn placement**: FUTURE (not wired in Phase 1 stub):
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248) —
  Actuator action node in the monitoring-initiation Sequence, after
  `MonitoringRequirement` succeeds; fires the external monitoring registration
  call and confirms activation.
  Note: Phase 1 stub exists as of PR #1357 but this Actuator is not
  among the 4 factory params exposed.

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
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree`
  (`deploy_fix_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_deploy_fix_tree` (issue #1248) —
  Evaluator action node in the full-fix-deploy Sequence; the primary patch
  deployment step (distinct from mitigation deployment)

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
- **Call-out point shape**: Retriever — synchronous on-demand query to an internal exploit repository or threat-intelligence platform; returns SUCCESS if a working exploit is already available for this vulnerability, FAILURE otherwise. A boolean is the simplest structured fact (ADR-0024); the on-demand query pattern makes this a Retriever, not a Sentinel.
- **Factory-fn placement**: Implemented (PR #1566) —
  `vultron.core.behaviors.report.acquire_exploit_strategy_tree.create_acquire_exploit_strategy_tree`
  (`have_exploit_factory` param) — early-exit Retriever guard at the head of the
  `AcquireExploitStrategyBT` Selector (Production Collapse 1, ADR-0027)

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
- **Call-out point shape**: ProtocolInternal — reads a flag written by `EvaluateExploitPriority`
  during the same BT execution cycle; the flag lives on the BT blackboard (per-actor in-process).
  No external agent seam — the flag never crosses an actor boundary.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: Eliminated (Production Collapse 1, PR #1566) —
  collapsed into the `EvaluateExploitStrategy` Evaluator's output record;
  no longer a separate BT leaf or factory parameter.

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
- **Factory-fn placement**: Superseded by Production Collapse 1 (PR #1566) —
  Phase 1 stub in `create_acquire_exploit_tree` (`evaluate_exploit_priority_factory`)
  is replaced by `EvaluateExploitStrategy` in
  `create_acquire_exploit_strategy_tree` (`evaluate_exploit_strategy_factory`).
  The priority decision is now encoded in `ExploitStrategyDecision.acquire`.

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
- **Call-out point shape**: ProtocolInternal — reads a flag written by `EvaluateExploitPriority`
  during the same BT execution cycle; the flag lives on the BT blackboard (per-actor in-process).
  No external agent seam — the flag never crosses an actor boundary.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: Eliminated (Production Collapse 1, PR #1566) —
  collapsed into the `EvaluateExploitStrategy` Evaluator's output record;
  no longer a separate BT leaf or factory parameter.

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
- **Call-out point shape**: ProtocolInternal — reads a flag written by `EvaluateExploitPriority`
  during the same BT execution cycle; the flag lives on the BT blackboard (per-actor in-process).
  No external agent seam — the flag never crosses an actor boundary.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: Eliminated (Production Collapse 1, PR #1566) —
  collapsed into the `EvaluateExploitStrategy` Evaluator's output record;
  no longer a separate BT leaf or factory parameter.

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_acquire_exploit_strategy_tree`
  (issue #1249) — first Retriever child in the acquisition Fallback;
  searched before `DevelopExploit` and `PurchaseExploit`

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_acquire_exploit_strategy_tree`
  (issue #1249) — second Composer child in the acquisition Fallback;
  tried after `FindExploit` fails, before `PurchaseExploit`

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
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.acquire_exploit_tree.create_acquire_exploit_tree`
  (`purchase_exploit_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_acquire_exploit_strategy_tree`
  (issue #1249) — third (last-resort) Evaluator child in the acquisition
  Fallback; tried only after `FindExploit` and `DevelopExploit` both fail

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
- **Call-out point shape**: Retriever — synchronous per-tick query to threat-intelligence feeds or SIEM/IDS telemetry; returns SUCCESS if active attacks are detected, FAILURE otherwise. The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_monitor_threats_tree`
  (issue #1250) — first Retriever child in the `MonitorThreats` Fallback;
  queries SIEM/IDS feeds for evidence of active in-the-wild attacks

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
- **Call-out point shape**: Retriever — synchronous per-tick query to exploit database feeds or threat-intelligence platforms; returns SUCCESS if a newly published exploit is found, FAILURE otherwise. The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_monitor_threats_tree`
  (issue #1250) — second Retriever child in the `MonitorThreats` Fallback;
  queries exploit-database feeds and CVE enrichment APIs for newly
  published exploit code

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
- **Call-out point shape**: Retriever — synchronous per-tick query to OSINT feeds, news/RSS sources, or social-media tracking APIs; returns SUCCESS if public disclosure evidence is found, FAILURE otherwise. The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_monitor_threats_tree`
  (issue #1250) — third Retriever child in the `MonitorThreats` Fallback;
  queries OSINT/news feeds for public disclosure of the vulnerability

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
- **Factory-fn placement**: N/A — ProtocolInternal terminal success leaf;
  `create_monitor_threats_tree` (issue #1250) will provide this node
  internally as a hardcoded AlwaysSucceed fallback, not a call-out point

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
- **Call-out point shape**: ProtocolInternal — reads a publication-completion flag maintained in the
  local DataLayer / BT blackboard by the protocol's own BT execution (written by `Publish` nodes).
  No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: FUTURE (not part of the Production Collapse 2 lean
  shape, issue #1310) — a top-level early-exit ProtocolInternal condition check
  that short-circuits the whole subtree once all artifacts are published. The
  lean `create_publication_tree` omits this idempotency guard for now; if added,
  it would wrap the `PublicationBT` Sequence in a `Selector(AllPublished, …)`.
  Tracked with the broader publication workflow in issue #1251.

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
- **Call-out point shape**: ProtocolInternal — reads a flag written by `PrioritizePublicationIntents`
  during the same BT execution cycle; the flag lives on the local DataLayer / BT blackboard.
  No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the flag check disappears in production; the BT reads the
  `PublicationIntentDecision` record directly via `ShouldPublishX` gate nodes.
  No longer a separate BT leaf or factory parameter.

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
- **Factory-fn placement**: Implemented (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`prioritize_publication_intents_factory` param) — the surviving Evaluator;
  runs first and writes a structured `PublicationIntentDecision` record that
  gates the three per-artifact arms. See Production Collapse 2 below.

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
- **Call-out point shape**: Actuator — submits an already-prepared artifact to an external advisory platform (NVD, CVE.org, CMS, package repository, or equivalent) via an API call; the side effect is the externally visible published entry at the target platform. There is no new content artifact placed on the blackboard; the preceding Prepare* nodes produce the content.
- **Factory-fn placement**: Wired (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`publish_factory` param, applied once per arm) — terminal Actuator node at
  the end of each per-artifact `Do…` Sequence (`PrepareExploit → PublishExploit`,
  `PrepareFix → PublishFix`, `PrepareReport → PublishReport`).
  See Production Collapse 4 below — this single leaf still expands into a
  draft-review-submit pipeline (ADR-0030 / BT-20-004), tracked separately.

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
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishExploit`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the exploit is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam. Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  replaced by the positively-named `ShouldPublishExploit` gate node
  (reads `PublicationIntentDecision.publish_exploit`) plus the exploit arm's
  `Inverter(ShouldPublishExploit)` skip branch, which provides the graceful
  no-op this leaf used to. Not a call-out point.

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
- **Call-out point shape**: ProtocolInternal — reads a staging-readiness flag written by
  `PrepareExploit` during the same BT execution cycle; the flag lives on the local DataLayer /
  BT blackboard. No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the lean per-artifact arm is `ShouldPublishExploit → PrepareExploit →
  Publish` with no separate staging-readiness early-exit. Not a call-out point.

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
- **Factory-fn placement**: Implemented (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`prepare_exploit_factory` param) — Composer node in the exploit arm's
  `Do…` Sequence, between `ShouldPublishExploit` and `Publish`

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
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the single `PrioritizePublicationIntents` Evaluator now carries all
  publish/withhold intent in its `PublicationIntentDecision` record; per-arm
  reprioritization is not a separate call-out point in the lean shape.

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
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishFix`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the fix is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam. Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  replaced by the positively-named `ShouldPublishFix` gate node
  (reads `PublicationIntentDecision.publish_fix`) plus the fix arm's
  `Inverter(ShouldPublishFix)` skip branch, which provides the graceful
  no-op this leaf used to. Not a call-out point.

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
- **Factory-fn placement**: Implemented (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`prepare_fix_factory` param) — Composer node in the fix arm's `Do…`
  Sequence, between `ShouldPublishFix` and `Publish`

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
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the single `PrioritizePublicationIntents` Evaluator now carries all
  publish/withhold intent in its `PublicationIntentDecision` record; per-arm
  reprioritization is not a separate call-out point in the lean shape.

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
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishReport`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the vulnerability report is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam. Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  replaced by the positively-named `ShouldPublishReport` gate node
  (reads `PublicationIntentDecision.publish_report`) plus the report arm's
  `Inverter(ShouldPublishReport)` skip branch, which provides the graceful
  no-op this leaf used to. Not a call-out point.

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
- **Factory-fn placement**: Implemented (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`prepare_report_factory` param) — Composer node in the report arm's `Do…`
  Sequence, between `ShouldPublishReport` and `Publish`

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
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the single `PrioritizePublicationIntents` Evaluator now carries all
  publish/withhold intent in its `PublicationIntentDecision` record; per-arm
  reprioritization is not a separate call-out point in the lean shape.

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
- **Call-out point shape**: TBD — role/eligibility check: "does this participant have the capability and mandate to notify other parties?" In the evolving architecture this may devolve to a `CVDRole.CASE_MANAGER` membership check (internal BT condition check, not a call-out point), or remain an Evaluator if notification-obligation reasoning beyond role membership is required. Revisit after the invite-participant-to-case protocol is finalized (see #1199, #1200).
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — top-level guard at the root of `MaybeReportToOthers`;
  exact shape (Evaluator vs. internal condition check) depends on
  invite-participant-to-case protocol design (#1199, #1200)

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
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`
  (`all_parties_known_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator Sentinel after `HaveReportToOthersCapability`;
  exits the outer party-identification loop once all parties are known

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Retriever node in the party-identification Sequence;
  populates the vendor portion of the identified-parties queue using
  CPE/product database lookups, SBOM analysis, and NVD product data

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Retriever node in the party-identification Sequence;
  populates the coordinator portion of the identified-parties queue using
  FIRST member directory and national CSIRT registry lookups

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator node in the party-identification Sequence;
  catch-all for non-vendor, non-coordinator stakeholders requiring
  case-specific human expert assessment

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
- **Call-out point shape**: ProtocolInternal — reads notification-completion flags maintained in the
  local DataLayer / BT blackboard by the protocol's own `SetRcptQrmR` Actuator nodes (per-actor
  in-process). No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal condition check at the top of the per-recipient
  notification loop; exits the loop once the full notification queue
  is drained

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Retriever node at the top of the per-recipient loop
  body; pops the next candidate from the queue and writes it to the
  blackboard

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
- **Call-out point shape**: Actuator — writes a queue-removal state change to the case management system, dequeuing the current recipient; the side effect in the external system is the seam, not a content artifact placed on the blackboard.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Actuator node appended at the end of the per-recipient
  notification Sequence (after `SetRcptQrmR`); removes the processed
  recipient from the pending queue

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
- **Call-out point shape**: Evaluator — evaluates whether the notification-attempt budget for this recipient has been exhausted by comparing the per-recipient attempt counter against a configurable policy threshold; a process-gate judgment about whether continued effort is warranted.
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`
  (`recipient_effort_exceeded_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator guard in the per-recipient effort-limit
  Sequence; triggers `RemoveRecipient` when the per-recipient attempt
  budget is exhausted

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
- **Call-out point shape**: Evaluator — evaluates whether the global notification budget has been exhausted by comparing the total effort counter against a configurable policy ceiling; a process-gate judgment about whether any further notification attempts are warranted across all recipients.
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`
  (`total_effort_limit_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator guard checked at the outer loop level;
  terminates all further notification attempts when the global effort
  ceiling is reached

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
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`
  (`policy_compatible_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator precondition guard before `FindContact` and
  `RcptNotInQrmS`; gates notification on policy compatibility check
  against the recipient's published CVD/embargo policy

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Retriever node after `PolicyCompatible`; resolves contact
  details for the current recipient and writes them to the blackboard
  for downstream use by `SetRcptQrmR` and outbound message nodes

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
- **Call-out point shape**: ProtocolInternal — reads a per-recipient RM-state flag maintained in the
  local DataLayer / BT blackboard; the flag is written by `SetRcptQrmR` (protocol-internal Actuator)
  after each notification. No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal idempotency check after `FindContact`; skips
  re-notification if the recipient's RM state is already past START

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
- **Call-out point shape**: Actuator — writes a recipient RM-state transition (START → RECEIVED) to the case management system; the side-effect state write is the seam, not a content artifact placed on the blackboard.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Actuator node after `RcptNotInQrmS` in the notification
  Sequence; records the state transition confirming the recipient was
  notified, before `RemoveRecipient` dequeues them

### `MoreVendors`

- **Node name**: `MoreVendors`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — return SUCCESS iff the
  `identified_vendors` blackboard list is non-empty; falls back to
  probabilistic behaviour (`UsuallyFail`, p=0.25) when the key is absent
  or the list is empty.  Drives exhaustion-based loop iteration.
- **Blackboard contract**: Input keys: `identified_vendors: list`
  (READ; key may be absent). Output keys: none.
  Implemented via `setup()`/`update()` overrides that call
  `attach_blackboard_client()` with `Access.READ`.
- **Input dependency**: Query to the `identified_vendors` blackboard key;
  written by `IdentifyVendors` upstream.
- **Notes**: Returns SUCCESS deterministically when `identified_vendors`
  is non-empty; falls back to `UsuallyFail` (25%) when absent or empty.
- **Automation potential**: **High** — queue-emptiness check; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.MoreVendors`
- **Call-out point shape**: ProtocolInternal — checks the local `identified_vendors`
  blackboard list (BT blackboard, per-actor in-process); this is a BT for-loop
  iteration guard, not an external query. No external agent seam — the list is
  local and actor-scoped.
  (Category 3 per issue #1199 triage — reads from the protocol's own BT blackboard.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal iteration guard at the head of the vendor sub-loop;
  drives the vendor-notification iteration until the vendor queue is empty

### `MoreCoordinators`

- **Node name**: `MoreCoordinators`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — return SUCCESS iff the
  `identified_coordinators` blackboard list is non-empty; falls back to
  probabilistic behaviour (`AlmostAlwaysFail`, p=0.10) when the key is
  absent or the list is empty.  Mirrors `MoreVendors` for the coordinator
  sub-list.
- **Blackboard contract**: Input keys: `identified_coordinators: list`
  (READ; key may be absent). Output keys: none.
  Implemented via `setup()`/`update()` overrides that call
  `attach_blackboard_client()` with `Access.READ`.
- **Input dependency**: Query to the `identified_coordinators` blackboard
  key; written by `IdentifyCoordinators` upstream.
- **Notes**: Returns SUCCESS deterministically when
  `identified_coordinators` is non-empty; falls back to `AlmostAlwaysFail`
  (10%) when absent or empty.
- **Automation potential**: **High** — queue-emptiness check; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.MoreCoordinators`
- **Call-out point shape**: ProtocolInternal — checks the local `identified_coordinators`
  blackboard list (BT blackboard, per-actor in-process); this is a BT for-loop iteration guard,
  not an external query. No external agent seam — the list is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads from the protocol's own BT blackboard.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal iteration guard at the head of the coordinator sub-loop;
  drives coordinator-notification iteration until the coordinator queue is
  empty

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
- **Call-out point shape**: ProtocolInternal — checks the local `bb.case.potential_participants`
  other-parties sub-list (BT blackboard, per-actor in-process); this is a BT for-loop iteration guard,
  not an external query. No external agent seam — the list is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads from the protocol's own BT blackboard.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal iteration guard at the head of the other-parties sub-loop;
  drives other-party notification iteration until the other-parties queue
  is empty

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
  role-specific inject nodes below. In production, these simulator leaf nodes
  would be replaced by subtrees that invoke the InviteParticipantToCase
  protocol; the call-out point lives at the boundary with that protocol, not
  at this leaf.
- **Automation potential**: **High** — case management system write; fully automatable once participant details are known.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectParticipant`
- **Call-out point shape**: Actuator — writes a new participant record to the case management system; the side-effect state write is the seam. Production replacement: InviteParticipantToCase protocol subtree (not yet implemented).
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — base Actuator node; production replacement is the
  `suggest-actor-to-case` trigger (see Production Collapse 3 below);
  the call-out point seam lives here at the case-management write boundary

### `InjectVendor`

- **Node name**: `InjectVendor`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — pop the first entry from the
  `identified_vendors` blackboard list and append it to
  `potential_participants`.  When the list is absent or empty, succeeds
  as a no-op.  Specialization of `InjectParticipant` via `source_key =
  "identified_vendors"`.
- **Blackboard contract**: Input keys: `identified_vendors: list`
  (READ/WRITE; key may be absent). Output keys: `potential_participants:
  list` (WRITE; key may be absent).
  Implemented through the shared `InjectParticipant.setup()`/`update()`
  logic keyed by `source_key`; uses `attach_blackboard_client()` with
  `Access.WRITE`.
- **Input dependency**: Reads `identified_vendors` written by
  `IdentifyVendors`; writes to `potential_participants`.
- **Notes**: Specialization of `InjectParticipant` for vendor role. See
  `InjectParticipant` for production-replacement note.
- **Automation potential**: **High** — case management system write for vendor role; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectVendor`
- **Call-out point shape**: Actuator — pops from `identified_vendors` and appends to
  `potential_participants`; the side-effect state write is the seam. Production
  replacement: InviteParticipantToCase protocol subtree.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Actuator node in the vendor sub-loop, after `MoreVendors`
  succeeds and the notification Sequence completes; replaced by
  `suggest-actor-to-case` with `CVDRole.VENDOR` (see Production Collapse 3)

### `InjectCoordinator`

- **Node name**: `InjectCoordinator`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — pop the first entry from the
  `identified_coordinators` blackboard list and append it to
  `potential_participants`.  When the list is absent or empty, succeeds
  as a no-op.  Specialization of `InjectParticipant` via `source_key =
  "identified_coordinators"`.
- **Blackboard contract**: Input keys: `identified_coordinators: list`
  (READ/WRITE; key may be absent). Output keys: `potential_participants:
  list` (WRITE; key may be absent).
  Implemented through the shared `InjectParticipant.setup()`/`update()`
  logic keyed by `source_key`; uses `attach_blackboard_client()` with
  `Access.WRITE`.
- **Input dependency**: Reads `identified_coordinators` written by
  `IdentifyCoordinators`; writes to `potential_participants`.
- **Notes**: Specialization of `InjectParticipant` for coordinator role. See
  `InjectParticipant` for production-replacement note.
- **Automation potential**: **High** — case management system write for coordinator role; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectCoordinator`
- **Call-out point shape**: Actuator — pops from `identified_coordinators` and appends to
  `potential_participants`; the side-effect state write is the seam. Production
  replacement: InviteParticipantToCase protocol subtree.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Actuator node in the coordinator sub-loop, after
  `MoreCoordinators` succeeds and the notification Sequence completes;
  replaced by `suggest-actor-to-case` with `CVDRole.COORDINATOR`
  (see Production Collapse 3)

### `InjectOther`

- **Node name**: `InjectOther`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — add any other identified party as a
  participant in the coordinated disclosure case
- **Input dependency**: Case management system write; stakeholder contact
  and acceptance of participation
- **Notes**: Specialization of `InjectParticipant` for other-party role. See
  `InjectParticipant` for production-replacement note.
- **Automation potential**: **High** — case management system write for other-party role; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectOther`
- **Call-out point shape**: Actuator — inherits InjectParticipant; writes an other-party participant record to the case management system; the side-effect state write is the seam. Production replacement: InviteParticipantToCase protocol subtree.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Actuator node in the other-parties sub-loop, after
  `MoreOthers` succeeds and the notification Sequence completes;
  replaced by `suggest-actor-to-case` with `CVDRole.OTHER`
  (see Production Collapse 3)

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
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.close_report_tree.create_close_report_tree`
  (`other_close_criteria_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_close_report_tree`
  (issue #1253) — Evaluator precondition guard in the `RMCloseBt` Sequence;
  evaluated before `PreCloseAction`; blocks closure until site-specific
  criteria are satisfied

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
- **Call-out point shape**: Actuator — fires integration hooks before case closure; invokes QA pipeline checks, final notification APIs, and case-archiving services. There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_close_report_tree`
  (issue #1253) — Actuator effect node after `OtherCloseCriteriaMet`;
  last node before the RM → CLOSED state transition fires

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_do_work_tree`
  (issue #1255) — primary Evaluator leaf of `RMDoWorkBt`; the main
  extensibility seam for organization-specific in-flight case work
  not covered by more specific sub-trees

---

## Production Collapse Designs

The sections below document how groups of simulator fuzzer nodes are expected
to **collapse** in the production BT architecture. Each group of simulator
leaves maps to a smaller set of production call-out points. These designs are
**provisional** — they represent the best understanding at planning time
(issue #1200) and are subject to revision when the corresponding
implementation issues are worked.

Cross-references: each affected simulator-node entry above has a
"see Production Collapse" note pointing here. The implementation issues listed
in each section are what to work when it is time to build the production
subtrees.

---

### Production Collapse 1: Exploit-strategy subtree → EvaluateExploitStrategy

**Simulator nodes involved**: `HaveExploit`, `ExploitPrioritySet`,
`EvaluateExploitPriority`, `ExploitDeferred`, `ExploitDesired`
(see Exploit Acquisition section above)

**Implemented by**: issue #1309 (PR #1566)

#### Production shape

The five-node simulator sequence is replaced by two independently-swappable
call-out points (ADR-0027 Option 2):

1. **`HaveExploit`** (Retriever) — early-exit guard; queries whether a working
   exploit already exists. Survives as a separate seam for independent swapability.
2. **`EvaluateExploitStrategy`** (Evaluator) — receives case context and returns
   a structured `ExploitStrategyDecision` record.

The three ProtocolInternal nodes (`ExploitPrioritySet`, `ExploitDeferred`,
`ExploitDesired`) are eliminated as separate BT leaves — their decisions become
internal reads on the Evaluator's output record.

**Output schema** (Pydantic BaseModel, implemented in
`vultron.core.behaviors.report.acquire_exploit_strategy_tree`):

```python
class ExploitStrategyDecision(BaseModel):
    have_exploit: bool = False  # whether a working exploit is already available
    acquire: bool = False       # decision: pursue exploit acquisition
    rationale: str = ""         # reasoning for the decision
```

**Factory function**:
`vultron.core.behaviors.report.acquire_exploit_strategy_tree.create_acquire_exploit_strategy_tree`

**Spec requirements**: BT-20-001 (see `specs/behavior-tree-integration.yaml`)

---

### Production Collapse 2: Publication-intent subtree → Evaluator + per-artifact arms

**Simulator nodes involved**: `PublicationIntentsSet`, `PrioritizePublicationIntents`,
`NoPublishExploit`, `ExploitReady`, `PrepareExploit`, `ReprioritizeExploit`,
`NoPublishFix`, `PrepareFix`, `ReprioritizeFix`, `NoPublishReport`,
`PrepareReport`, `ReprioritizeReport`
(see Publication section above)

**Implemented by**: issue #1310

#### Production shape

The `PublicationIntentsSet` flag check and `NoPublish*` bypass leaves are
**ProtocolInternal structural artifacts** of the simulator representation —
they do not survive as call-out points. In production:

1. **`PrioritizePublicationIntents`** (already an Evaluator) returns a
   structured `PublicationIntentDecision` record: `{publish_exploit: bool,
   publish_fix: bool, publish_report: bool, rationale: str}`. The
   `PublicationIntentsSet` flag check disappears — the BT queries the intent
   record directly via `ShouldPublishX` gate nodes.

2. For each intended artifact: one **Composer** subtree
   (`PrepareExploit` / `PrepareFix` / `PrepareReport`) drafts and stages the
   artifact.

3. For each prepared artifact: one **Actuator** (`Publish`) submits to the
   external advisory platform.

The `NoPublish*` bypass leaves and `ReprioritizeX` Evaluators disappear — the
intent record from step 1 drives which arms execute. The removed `NoPublishX`
leaves are replaced by positively-named `ShouldPublishX` gate nodes
(BTND-08-001) that read the intent record; each arm's `Inverter(ShouldPublishX)`
skip branch provides the graceful no-op that `NoPublishX` used to.

**BT structure** (lean: three named arms — exploit arm, fix arm, report arm):

```text
PublicationBT (Sequence)
├── PrioritizePublicationIntents (Evaluator)       — writes PublicationIntentDecision
├── ExploitPublicationArm (Selector)
│   ├── Sequence(ShouldPublishExploit, PrepareExploit, Publish)
│   └── Inverter(ShouldPublishExploit)             — SUCCESS no-op if not intended
├── FixPublicationArm (Selector)                   — same shape, publish_fix gate
└── ReportPublicationArm (Selector)                — same shape, publish_report gate
```

The per-arm `Publish` Actuator is kept as a single leaf here; expanding it into
a draft-review-submit pipeline is Production Collapse 4 (ADR-0030 / BT-20-004).

**Factory function**:
`vultron.core.behaviors.report.publication_tree.create_publication_tree`

**Output schema**: `PublicationIntentDecision(publish_exploit, publish_fix,
publish_report, rationale)` (Pydantic BaseModel) in
`vultron/core/behaviors/report/publication_tree.py`

**Spec requirements**: BT-20-002 (see
`specs/behavior-tree-integration.yaml`) and ADR-0028

---

### Production Collapse 3: Notification loop → InviteParticipantToCase protocol

**Simulator nodes involved**: `HaveReportToOthersCapability`, `AllPartiesKnown`,
`IdentifyVendors`, `IdentifyCoordinators`, `IdentifyOthers`,
`NotificationsComplete`, `ChooseRecipient`, `RemoveRecipient`,
`RecipientEffortExceeded`, `TotalEffortLimitMet`, `PolicyCompatible`,
`FindContact`, `RcptNotInQrmS`, `SetRcptQrmR`, `MoreVendors`,
`MoreCoordinators`, `MoreOthers`, `InjectParticipant`, `InjectVendor`,
`InjectCoordinator`, `InjectOther`
(see Reporting to Other Parties section above)

**Tracked by**: implementation issue for collapse candidate 3 (blocked by #1200 and #1298 suggest-actor redesign)

#### Production shape

The **outer loop structure survives** — `MaybeReportToOthers` remains a BT
subtree that asks "should we notify additional parties?" and iterates through
identified parties. What changes is **what happens at the end of each
iteration**: instead of `InjectParticipant` (a direct case-management write),
the BT calls the `suggest-actor-to-case` trigger, which initiates the full
`RecommendActor → Invite → Accept → Record` cascade automatically.

**Nodes that survive** (as call-out points or ProtocolInternal guards):

- `HaveReportToOthersCapability` — TBD shape; likely resolves to a
  `CVDRole.CASE_MANAGER` membership check (ProtocolInternal) once the
  invite-participant-to-case protocol is finalized
- `AllPartiesKnown` — Evaluator (unchanged)
- `IdentifyVendors`, `IdentifyCoordinators`, `IdentifyOthers` — Retrievers
  (unchanged)
- `NotificationsComplete` — ProtocolInternal (unchanged)
- `ChooseRecipient`, `FindContact` — Retrievers (unchanged; feed context into
  the suggest-actor call)
- `RecipientEffortExceeded`, `TotalEffortLimitMet` — Evaluators (unchanged)
- `PolicyCompatible` — Evaluator (unchanged)
- `RcptNotInQrmS` — ProtocolInternal idempotency check (unchanged)
- `MoreVendors`, `MoreCoordinators`, `MoreOthers` — ProtocolInternal
  iteration guards (unchanged; three typed sub-loops survive)

**Nodes that collapse**:

- `SetRcptQrmR` — the RM-state write is now handled by the `AcceptInviteToCase`
  cascade; no standalone Actuator needed at this layer
- `InjectParticipant`, `InjectVendor`, `InjectCoordinator`, `InjectOther` —
  replaced by a call to the `suggest-actor-to-case` trigger endpoint (or
  equivalently, emitting an `Offer(Actor)` to the CaseActor). The full
  `RecommendActor → Invite → Accept → Record` cascade follows automatically.

**Key design note**: `suggest-actor-to-case` currently assumes
`CVDRole.VENDOR` for the invited party. Collapse candidate 3 implementation
**MUST** extend `suggest-actor-to-case` to accept an explicit role parameter
(VENDOR / COORDINATOR / OTHER), since the three typed sub-loops each map to
a different CVD role.

**Target factory function**:
`vultron.core.behaviors.report.create_report_to_others_tree` (issue #1252)

**Spec requirements**: BT-20-003 (provisional — see
`specs/behavior-tree-integration.yaml`)

---

### Production Collapse 4: Publish leaf → draft-review-submit pipeline

**Simulator nodes involved**: `Publish`
(see Publication section above; also see Production Collapse 2 for the
per-artifact preparation context)

**Tracked by**: implementation issue for collapse candidate 4 (blocked by #1200 and collapse candidate 2 impl issue)

#### Production shape

The single `Publish` simulator leaf expands into a **multi-step pipeline**
with its own call-out points. This acknowledges that advisory publication in
production involves drafting, review/approval, and submission — not a single
atomic action.

**Core pipeline** (lean: Composer → Evaluator → Actuator):

```text
PublishArtifactBT (Sequence)
├── DraftAdvisoryArtifact (Composer)    — draft CSAF/CVE JSON/advisory from case data
├── ReviewAdvisoryDraft (Evaluator)     — review/approve the draft (human or automated QA)
├── [optional] ReviseAdvisoryDraft (Composer) — revise based on review feedback
└── SubmitAdvisoryArtifact (Actuator)   — submit finalized artifact to advisory platform
```

**Open design question**: Should the review phase include a
"broadcast draft to case participants for comment" step before the Evaluator
runs? This would involve emitting an outbound Activity (a protocol-visible
action) and optionally waiting for participant responses — resembling the
`Accept/Reject` question pattern used elsewhere in the protocol. This is
captured here as an open question; the implementation issue should design
the review-phase protocol before wiring the BT.

**Impact on existing `Publish` Actuator nodes**: Each per-artifact arm in
Production Collapse 2 (`ExploitReady → Publish`, `PrepareFix → Publish`,
`PrepareReport → Publish`) has its own `Publish` Actuator. In production,
those Actuators are each replaced by this full `PublishArtifactBT` subtree.

**Target factory function**:
`vultron.core.behaviors.report.create_publish_artifact_tree` (new; called
from within `create_publication_tree`)

**Spec requirements**: BT-20-004 (provisional — see
`specs/behavior-tree-integration.yaml`)

---

## Sentinel Stubs Must Be Synced When the Upstream Issue Closes

(ISSUE-1177, 2026-07-14)

A catalog entry with `New-arch cross-ref: *(to be implemented — see FUZZ-08x)*`
where the referenced issue is now **closed** is a gap — the stub was never
promoted.

When FUZZ-08f (Sentinel shape, issue #1175) closed, three catalog entries
here carried `*(to be implemented — see FUZZ-08f)*`:

- `NewValidationInfoSentinel` — was implemented; cross-ref updated.
- `NewPrioritizationInfoSentinel` — left unimplemented.
- `NewDeploymentInfoSentinel` — left unimplemented.

Only the first was added; the other two remained as unimplemented stubs with
no matching class in `call_out_point.py`.

**Pattern to apply** during domain-sweep audits (FUZZ-08h style):

1. Grep catalog entries for `*(to be implemented — see FUZZ-08x)*`.
2. Check if the referenced issue is closed.
3. If closed but the class is absent from `call_out_point.py`, it is a gap —
   add the class and update the catalog cross-ref line.

The domain-sweep audit is the right checkpoint for this; catching it there
prevents gaps from persisting across multiple closed issues.

---
