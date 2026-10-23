---
stakeholder_type: [project-contributor]
---

# Fix development and deployment fuzzer nodes

These stub nodes belong to the simulator's fix development and fix deployment sub-trees.
Each entry maps a simulator stub to the call-out point that replaces it in `vultron/core/behaviors/report/`.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## Fix development

These nodes belong to the `DevelopFix` fallback tree (`vultron/bt/report_management/_behaviors/develop_fix.py`), which models the vendor's internal process of creating a patch or fix for the vulnerability.

### `CreateFix`

- **Node name**: `CreateFix`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/develop_fix.py`
- **Parent tree**: `DevelopFix`
- **Semantic function**: Action — initiate or advance the internal engineering process to create a patch or mitigation for the vulnerability
- **Input dependency**: Human engineer prompt, bug tracker integration, or CI/CD pipeline trigger; reports progress from the engineering team
- **Notes**: Succeeds almost always in simulation; in production this node would integrate with the vendor's bug/patch tracking system
- **Automation potential**: **Low** — engineering work is human-initiated; automation is limited to triggering a bug-tracker ticket or sending a development task notification.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.develop_fix.CreateFix`
- **Call-out point shape**: Composer
- **Factory-fn placement**: `vultron.core.behaviors.report.develop_fix_tree.create_develop_fix_tree` — Composer action node in the `DevelopFix` Sequence; the primary work node

---

## Fix deployment

These nodes belong to the `Deployment` fallback tree (`vultron/bt/report_management/_behaviors/deploy_fix.py`), which models the process of deploying a developed fix or mitigation to affected systems.

### `NoNewDeploymentInfo`

- **Node name**: `NoNewDeploymentInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether any new deployment-related information has arrived that warrants re-evaluating the deployment workflow
- **Input dependency**: Report/case change detection; metadata timestamp or event subscription on deployment status field
- **Notes**: New deployment info is uncommon; most ticks pass through without update
- **Automation potential**: **High** — metadata timestamp or deployment-event subscription check; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.NoNewDeploymentInfo`
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream `NewDeploymentInfoSentinel` (see the next entry).
  The external seam is at that upstream writer, not at this behavior tree (BT) condition check.
- **Factory-fn placement**: `CheckNoNewDeploymentInfoNode` in `vultron.core.behaviors.report.nodes.deploy_fix` — ProtocolInternal condition check in the `_ShouldStayInRmDeferred` arm of the `DeployFixBT` Fallback built by `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree`, and reused by `create_deploy_mitigation_tree`.
  It reads the blackboard key `new_deployment_info` (`NEW_DEPLOYMENT_INFO_KEY`) and defaults to SUCCESS when the key is absent.
  Not a factory param: there is no injection seam at this node.

### `NewDeploymentInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewDeploymentInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors deployment-relevant data sources (e.g., patch management system, CI/CD pipeline, asset inventory) for new deployment-related events and writes a change-detection flag that `NoNewDeploymentInfo` consumes.
- **Input dependency**: Patch management system event stream, CI/CD pipeline notifications, or asset-inventory change feed; metadata timestamp comparison or event subscription on deployment-relevant case fields.
- **Notes**: This is the real seam implied by `NoNewDeploymentInfo`.
  The writer registers with an external event source and writes a flag to the BT blackboard or local DataLayer; `NoNewDeploymentInfo` reads that flag each tick.
- **Automation potential**: **High** — event subscription on the patch management system or CI/CD pipeline; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewDeploymentInfoSentinel`
- **Call-out point shape**: Sentinel — pending reclassification: Sentinel is no longer a call-out shape (ADR-0097, BT-18-013), and #3424 tracks reclassifying this entry.
- **Factory-fn placement**: Not placed inside the BT tree; writes the `new_deployment_info` blackboard key read by `CheckNoNewDeploymentInfoNode`

### `PrioritizeDeployment`

- **Node name**: `PrioritizeDeployment`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — assess and set the priority for deploying the fix across affected systems
- **Input dependency**: Human analyst or automated vulnerability prioritization system (e.g., a Common Vulnerability Scoring System (CVSS) environmental score, an Exploit Prediction Scoring System (EPSS) score, asset criticality)
- **Notes**: Succeeds almost always in simulation; in production may involve structured prioritization criteria
- **Automation potential**: **Medium** — CVSS environmental scores, EPSS, and asset criticality data are automatable inputs; final prioritization decision may require human approval, especially for production systems.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.PrioritizeDeployment`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `prioritize_deployment_factory` in the shared `DeploymentMonitoringBundle` — Evaluator in the `_DeployFixIfReady` arm of `create_deploy_fix_tree` (before `CheckCSFixNotYetDeployed` and `DeployFix`) and in the `_DeployMitigationIfAvailable` arm of `create_deploy_mitigation_tree`

### `MitigationDeployed`

- **Node name**: `MitigationDeployed`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether a mitigation has already been deployed to affected systems
- **Input dependency**: Query to asset/patch management system, deployment pipeline status, or case metadata flag
- **Notes**: Fails most of the time in simulation since mitigation deployment is modeled as the active goal
- **Automation potential**: **High** — query to patch management system or case-state flag; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MitigationDeployed`
- **Call-out point shape**: Retriever — synchronous on-demand query to an asset/patch management system or case-state flag; returns SUCCESS if a mitigation has been deployed, FAILURE otherwise.
  A boolean is the simplest structured fact (ADR-0024).
- **Factory-fn placement**: `vultron.core.behaviors.report.deploy_mitigation_tree.create_deploy_mitigation_tree` (`mitigation_deployed_factory` in `DeployMitigationCallOutBundle`) — short-circuit first arm of the `DeployMitigationBT` Fallback

### `MitigationAvailable`

- **Node name**: `MitigationAvailable`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether a mitigation (workaround or partial fix) is currently available for deployment
- **Input dependency**: Patch/advisory feed, internal mitigation catalog, or case status field
- **Notes**: Mitigations are available more often than not once the fix development cycle has progressed
- **Automation potential**: **High** — patch or advisory feed query; fully automatable once the feed integration is in place.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MitigationAvailable`
- **Call-out point shape**: Retriever — synchronous on-demand query to a patch/advisory feed or internal mitigation catalog; returns SUCCESS if a mitigation is currently available, FAILURE otherwise.
  A boolean is the simplest structured fact (ADR-0024).
- **Factory-fn placement**: `vultron.core.behaviors.report.deploy_mitigation_tree.create_deploy_mitigation_tree` (`mitigation_available_factory` in `DeployMitigationCallOutBundle`) — availability gate in the `_DeployMitigationIfAvailable` arm

### `DeployMitigation`

- **Node name**: `DeployMitigation`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — apply the available mitigation to affected systems (e.g., configuration change, web application firewall (WAF) rule, temporary patch)
- **Input dependency**: Human operator prompt or automated deployment pipeline; patch management or configuration management system integration
- **Notes**: Succeeds most of the time in simulation; production implementation would integrate with patch/config management tooling
- **Automation potential**: **Medium** — automated deployment is feasible for some environments (configuration management, cloud); human approval is typically required for production system changes.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.DeployMitigation`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.deploy_mitigation_tree.create_deploy_mitigation_tree` (`deploy_mitigation_factory` in `DeployMitigationCallOutBundle`) — final Evaluator in the `_DeployMitigationIfAvailable` arm

### `MonitoringRequirement`

- **Node name**: `MonitoringRequirement`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Condition — check whether organizational policy requires active monitoring of the fix deployment
- **Input dependency**: Policy engine or static organizational configuration; determines if post-deployment monitoring is mandatory
- **Notes**: A policy decision; could be a static rule or context-dependent evaluation
- **Automation potential**: **High** — policy rule evaluation against case context (severity, asset class, environment); fully automatable as a policy engine check.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MonitoringRequirement`
- **Call-out point shape**: Evaluator — evaluates whether organizational policy requires post-deployment monitoring for this case by applying policy rules against case context (severity, asset class, environment); a policy judgment call, not a binary condition monitor.
- **Factory-fn placement**: `monitoring_requirement_factory` in the shared `DeploymentMonitoringBundle` — Evaluator guard in the `_MonitorDeploymentIfDesired` arm of both `create_deploy_fix_tree` and `create_deploy_mitigation_tree`; SUCCESS proceeds to `MonitorDeployment`

### `MonitorDeployment`

- **Node name**: `MonitorDeployment`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — initiate or perform ongoing monitoring of the fix deployment to verify completeness and effectiveness
- **Input dependency**: Integration with asset management, patch verification tools, or security monitoring platforms
- **Notes**: Always succeeds in simulation; in production monitors deployment coverage metrics
- **Automation potential**: **High** — integration with deployment verification tools, patch compliance dashboards, or asset management platforms; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.MonitorDeployment`
- **Call-out point shape**: Actuator — initiates external deployment-monitoring as a side-effect; invokes patch-compliance dashboard, deployment-verification application programming interface (API), or asset-management platform to start ongoing coverage tracking.
  There is no content artifact placed on the blackboard; the side effect in the external monitoring system is the seam.
  This is a fire-and-confirm action node, not a continuous monitor running outside the BT — the BT tick reaches this node once per `MonitoringRequirement` pass and asks the external system to begin tracking.
- **Factory-fn placement**: `monitor_deployment_factory` in the shared `DeploymentMonitoringBundle` — Actuator in the `_MonitorDeploymentIfDesired` arm of both deployment trees, after `MonitoringRequirement` succeeds

### `DeployFix`

- **Node name**: `DeployFix`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/deploy_fix.py`
- **Parent tree**: `Deployment`
- **Semantic function**: Action — deploy the completed fix to all affected systems (full patch deployment, as opposed to a temporary mitigation)
- **Input dependency**: Human operator action or automated release pipeline; patch management system or software update infrastructure
- **Notes**: Modeled as rare per-tick because full fix deployment is a significant, infrequent milestone; over many ticks it eventually succeeds
- **Automation potential**: **Medium** — release pipeline and patch distribution can be automated (CI/CD, package repositories); human approval gate is commonly required for production releases.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.deploy_fix.DeployFix`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree` (`deploy_fix_factory` in `DeployFixCallOutBundle`) — Evaluator in the `_DeployFixIfReady` arm, after `PrioritizeDeployment` succeeds

---

## Fix and mitigation trees

`create_deploy_tree()` in `vultron/core/behaviors/report/deploy_tree.py` composes a `DeployOrMitigateBT` Fallback: the fix arm (`create_deploy_fix_tree`) is preferred and the mitigation arm (`create_deploy_mitigation_tree`) is the fallback (BT-20-005).
The fix tree records the case state (CS) `d → D` transition and emits a `CD` message; the mitigation tree does neither, because mitigation has no CS state bit and no protocol message.
That is why `MitigationDeployed` and `MitigationAvailable` are Retriever call-outs rather than CS-state condition nodes.
The two trees share the `DeploymentMonitoringBundle` seams (`PrioritizeDeployment`, `MonitoringRequirement`, `MonitorDeployment`).
