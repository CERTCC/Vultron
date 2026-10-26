---
stakeholder_type: [project-contributor]
---

# Fix development and deployment fuzzer nodes

These stub nodes belong to the simulator's fix development and fix deployment sub-trees.
Each entry maps a simulator stub to the call-out point that replaces it in `vultron/core/behaviors/report/`.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## Fix development

These nodes belong to the `DevelopFix` fallback tree (`vultron/bt/report_management/_behaviors/develop_fix.py`).
This tree models the internal process in which the vendor creates a patch or fix for the vulnerability.

### `CreateFix`

- **Node name**: `CreateFix`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/develop_fix.py`
- **Parent tree**: `DevelopFix`
- **Semantic function**: Action — start or advance the internal engineering process that creates a patch or mitigation for the vulnerability
- **Input dependency**: Human engineer prompt, bug tracker integration, or CI/CD pipeline trigger.
  The input reports progress from the engineering team
- **Notes**: Succeeds almost always in simulation.
  In production, this node connects to the bug/patch tracking system of the vendor
- **Automation potential**: **Low** — a human starts the engineering work.
  Automation can only open a bug-tracker ticket or send a development task notification.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.develop_fix.CreateFix`
- **Call-out point shape**: Composer
- **Factory-fn placement**: `vultron.core.behaviors.report.develop_fix_tree.create_develop_fix_tree` — Composer action node in the `DevelopFix` Sequence.
  It is the primary work node

---

## Fix deployment

These nodes belong to the `Deployment` fallback tree (`vultron/bt/report_management/_behaviors/deploy_fix.py`).
This tree models how a participant deploys a developed fix or mitigation to affected systems.

### `NoNewDeploymentInfo`

- **Node name**: `NoNewDeploymentInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether new deployment-related information has arrived.
  New information can make it necessary to evaluate the deployment workflow again
- **Input dependency**: Report/case change detection.
  A metadata timestamp or an event subscription on the deployment status field
- **Notes**: New deployment information is uncommon.
  Most ticks pass through without an update
- **Automation potential**: **High** — metadata timestamp or deployment-event subscription check.
  Full automation is possible.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.NoNewDeploymentInfo`
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream `NewDeploymentInfoSentinel` (see the next entry).
  The external seam is at that upstream writer, not at this behavior tree (BT) condition check.
- **Factory-fn placement**: `CheckNoNewDeploymentInfoNode` in `vultron.core.behaviors.report.nodes.deploy_fix` — ProtocolInternal condition check in the `_ShouldStayInRmDeferred` arm of the `DeployFixBT` Fallback.
  `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree` builds this Fallback, and `create_deploy_mitigation_tree` uses it again.
  It reads the blackboard key `new_deployment_info` (`NEW_DEPLOYMENT_INFO_KEY`) and defaults to SUCCESS when the key is absent.
  Not a factory param: there is no injection seam at this node.

### `NewDeploymentInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewDeploymentInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors deployment-relevant data sources for new deployment-related events.
  Examples are a patch management system, a CI/CD pipeline, or an asset inventory.
  The node writes a change-detection flag that `NoNewDeploymentInfo` reads.
- **Input dependency**: Patch management system event stream, CI/CD pipeline notifications, or asset-inventory change feed.
  A metadata timestamp comparison or an event subscription on deployment-relevant case fields.
- **Notes**: This is the real seam implied by `NoNewDeploymentInfo`.
  The writer registers with an external event source and writes a flag to the BT blackboard or local DataLayer.
  `NoNewDeploymentInfo` reads that flag each tick.
- **Automation potential**: **High** — event subscription on the patch management system or CI/CD pipeline.
  Full automation is possible.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewDeploymentInfoSentinel`
- **Call-out point shape**: Sentinel — pending reclassification.
  Sentinel is no longer a call-out shape (ADR-0097, BT-18-013), and #3424 tracks the reclassification of this entry.
- **Factory-fn placement**: Not placed in the BT tree.
  It writes the `new_deployment_info` blackboard key that `CheckNoNewDeploymentInfoNode` reads

### `PrioritizeDeployment`

- **Node name**: `PrioritizeDeployment`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — assess and set the priority for deploying the fix across affected systems
- **Input dependency**: Human analyst or automated vulnerability prioritization system.
  Inputs include a Common Vulnerability Scoring System (CVSS) environmental score, an Exploit Prediction Scoring System (EPSS) score, and asset criticality
- **Notes**: Succeeds almost always in simulation.
  In production, the node can use structured prioritization criteria
- **Automation potential**: **Medium** — CVSS environmental scores, EPSS, and asset criticality data are automatable inputs.
  The final prioritization decision can need human approval, especially for production systems.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.PrioritizeDeployment`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `prioritize_deployment_factory` in the shared `DeploymentMonitoringBundle` — Evaluator in two arms: the `_DeployFixIfReady` arm of `create_deploy_fix_tree` (before `CheckCSFixNotYetDeployed` and `DeployFix`), and the `_DeployMitigationIfAvailable` arm of `create_deploy_mitigation_tree`

### `MitigationDeployed`

- **Node name**: `MitigationDeployed`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether a mitigation has already been deployed to affected systems
- **Input dependency**: Query to asset/patch management system, deployment pipeline status, or case metadata flag
- **Notes**: Fails most of the time in simulation because the simulation models mitigation deployment as the active goal
- **Automation potential**: **High** — query to the patch management system or a case-state flag.
  Full automation is possible.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MitigationDeployed`
- **Call-out point shape**: Retriever — synchronous on-demand query to an asset/patch management system or a case-state flag.
  The node returns SUCCESS if a mitigation is deployed, and FAILURE otherwise.
  A boolean is the simplest structured fact (ADR-0024).
- **Factory-fn placement**: `vultron.core.behaviors.report.deploy_mitigation_tree.create_deploy_mitigation_tree` (`mitigation_deployed_factory` in `DeployMitigationCallOutBundle`) — short-circuit first arm of the `DeployMitigationBT` Fallback

### `MitigationAvailable`

- **Node name**: `MitigationAvailable`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether a mitigation (workaround or partial fix) is available for deployment now
- **Input dependency**: Patch/advisory feed, internal mitigation catalog, or case status field
- **Notes**: After the fix development cycle advances, a mitigation is available more often than not
- **Automation potential**: **High** — patch or advisory feed query.
  Full automation is possible after the feed integration is in place.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MitigationAvailable`
- **Call-out point shape**: Retriever — synchronous on-demand query to a patch/advisory feed or an internal mitigation catalog.
  The node returns SUCCESS if a mitigation is available now, and FAILURE otherwise.
  A boolean is the simplest structured fact (ADR-0024).
- **Factory-fn placement**: `vultron.core.behaviors.report.deploy_mitigation_tree.create_deploy_mitigation_tree` (`mitigation_available_factory` in `DeployMitigationCallOutBundle`) — availability gate in the `_DeployMitigationIfAvailable` arm

### `DeployMitigation`

- **Node name**: `DeployMitigation`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — apply the available mitigation to affected systems.
  Examples are a configuration change, a web application firewall (WAF) rule, or a temporary patch
- **Input dependency**: Human operator prompt or automated deployment pipeline.
  Patch management or configuration management system integration
- **Notes**: Succeeds most of the time in simulation.
  A production implementation connects to patch/config management tools
- **Automation potential**: **Medium** — automated deployment is possible in some environments, such as configuration management or cloud.
  Production system changes usually need human approval.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.DeployMitigation`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.deploy_mitigation_tree.create_deploy_mitigation_tree` (`deploy_mitigation_factory` in `DeployMitigationCallOutBundle`) — final Evaluator in the `_DeployMitigationIfAvailable` arm

### `MonitoringRequirement`

- **Node name**: `MonitoringRequirement`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether organizational policy requires active monitoring of the fix deployment
- **Input dependency**: Policy engine or static organizational configuration.
  The input tells whether post-deployment monitoring is mandatory
- **Notes**: A policy decision.
  It can be a static rule or a context-dependent evaluation
- **Automation potential**: **High** — policy rule evaluation against case context (severity, asset class, environment).
  A policy engine check can fully automate it.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MonitoringRequirement`
- **Call-out point shape**: Evaluator — applies policy rules against case context (severity, asset class, environment).
  The result tells whether organizational policy requires post-deployment monitoring for this case.
  The node is a policy judgment call, not a binary condition monitor.
- **Factory-fn placement**: `monitoring_requirement_factory` in the shared `DeploymentMonitoringBundle` — Evaluator guard in the `_MonitorDeploymentIfDesired` arm of both `create_deploy_fix_tree` and `create_deploy_mitigation_tree`.
  On SUCCESS, the tree continues to `MonitorDeployment`

### `MonitorDeployment`

- **Node name**: `MonitorDeployment`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — start or do ongoing monitoring of the fix deployment.
  The monitoring makes sure that the deployment is complete and effective
- **Input dependency**: Integration with asset management, patch verification tools, or security monitoring platforms
- **Notes**: Always succeeds in simulation.
  In production, the node monitors deployment coverage metrics
- **Automation potential**: **High** — integration with deployment verification tools, patch compliance dashboards, or asset management platforms.
  Full automation is possible.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MonitorDeployment`
- **Call-out point shape**: Actuator — starts external deployment monitoring as a side effect.
  It calls a patch-compliance dashboard, a deployment-verification application programming interface (API), or an asset-management platform to start ongoing coverage tracking.
  The seam is the side effect in the external monitoring system, not a content artifact on the blackboard.
  This node is a fire-and-confirm action node, not a continuous monitor that runs outside the BT.
  The BT tick reaches this node once per `MonitoringRequirement` pass and asks the external system to start tracking.
- **Factory-fn placement**: `monitor_deployment_factory` in the shared `DeploymentMonitoringBundle` — Actuator in the `_MonitorDeploymentIfDesired` arm of both deployment trees, after `MonitoringRequirement` succeeds

### `DeployFix`

- **Node name**: `DeployFix`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — deploy the completed fix to all affected systems.
  This action is a full patch deployment, not a temporary mitigation
- **Input dependency**: Human operator action or automated release pipeline.
  Patch management system or software update infrastructure
- **Notes**: The simulation makes success rare on each tick because full fix deployment is a significant, infrequent milestone.
  Over many ticks, the node eventually succeeds
- **Automation potential**: **Medium** — CI/CD and package repositories can automate the release pipeline and patch distribution.
  Production releases usually need a human approval gate.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.DeployFix`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree` (`deploy_fix_factory` in `DeployFixCallOutBundle`) — Evaluator in the `_DeployFixIfReady` arm, after `PrioritizeDeployment` succeeds

---

## Fix and mitigation trees

`create_deploy_tree()` in `vultron/core/behaviors/report/deploy_tree.py` composes a `DeployOrMitigateBT` Fallback (BT-20-005).
The tree prefers the fix arm (`create_deploy_fix_tree`), and the mitigation arm (`create_deploy_mitigation_tree`) is the fallback.
The fix tree records the case state (CS) `d → D` transition and emits a `CD` message.
The mitigation tree does neither, because mitigation has no CS state bit and no protocol message.

That is why `MitigationDeployed` and `MitigationAvailable` are Retriever call-outs rather than CS-state condition nodes.
The two trees share the `DeploymentMonitoringBundle` seams (`PrioritizeDeployment`, `MonitoringRequirement`, `MonitorDeployment`).
