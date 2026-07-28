---
title: "BT Fuzzer Nodes: RM Fix Development and Deployment"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for Fix Development (`DevelopFixBt`)
  and Fix Deployment (`DeployFixBt`) sub-workflows: patch creation,
  deployment, rollout, and new-deployment-info sentinel nodes used in simulation.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-fuzzer-nodes-report-management.md
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/report_management
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
