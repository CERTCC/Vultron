---
source: NOTES-bt-fuzzer-rm-fix--production-collapse-mitigation-deployment-subtree
timestamp: '2026-10-12T19:39:00.271952+00:00'
title: 'Production Collapse: Mitigation Deployment Subtree'
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered: create_deploy_mitigation_tree and create_deploy_tree exist; their module docstrings carry the tree shape and bundles
**Superseded by:** BT-20-005; vultron/core/behaviors/report/deploy_mitigation_tree.py, deploy_tree.py; docs/developer/reference/bt-fuzzer/rm-fix.md § Fix and mitigation trees

---

## Production Collapse: Mitigation Deployment Subtree → `create_deploy_mitigation_tree`

**Simulator nodes involved**: `MitigationDeployed`, `MitigationAvailable`,
`DeployMitigation` (all in
`vultron/demo/fuzzer/report_management/deploy_fix.py`)

**Planning issue**: #1826 (peer Idea to #1248)

**Spec**: `specs/behavior-tree-integration.yaml` BT-20-005

### Structural difference from `create_deploy_fix_tree`

The fix deployment tree persists a CS state transition (`VFD` d→D) and emits
a `CD` protocol message (`EmitCDActivity`). The mitigation tree does **not**:
mitigation deployment is tracked externally (CMDB, case record, or asset
inventory) and the 29-message Vultron protocol has no dedicated
mitigation-deployed message type. The short-circuit guard (`MitigationDeployed`)
and the availability gate (`MitigationAvailable`) are therefore call-out
Retrievers, not `DataLayerCondition` nodes reading a CS state bit.

A follow-on Idea under epic #1935 (Protocol authority & lifecycle semantics)
tracks the open question of whether a dedicated mitigation-deployed message
type should be added to the protocol.

### Production tree shape

```text
DeployMitigationBT (Fallback)
├─ <MitigationDeployed>                    # Retriever call-out — short-circuit
├─ _ShouldStayInRmDeferred (Sequence)
│  ├─ RMinStateDeferred                    # reused from deploy_fix nodes
│  └─ CheckNoNewDeploymentInfoNode         # reused from deploy_fix nodes
├─ _DeployMitigationIfAvailable (Sequence)
│  ├─ CheckDeployerRoleNode                # reused from vfd_role_guards
│  ├─ CheckRMStateAccepted                 # reused from develop_fix nodes
│  ├─ <MitigationAvailable>               # Retriever call-out — availability gate
│  ├─ <PrioritizeDeployment>              # Evaluator call-out (shared seam)
│  └─ <DeployMitigation>                  # Evaluator call-out
└─ _MonitorDeploymentIfDesired (Sequence)
   ├─ <MonitoringRequirement>             # Evaluator call-out (shared seam)
   └─ <MonitorDeployment>                # Actuator call-out (shared seam)
```

No `TransitionCS` or `EmitActivity` nodes — mitigation has no CS state bit
and no protocol message counterpart.

### Bundle structure

`DeploymentMonitoringBundle` (shared base,
`vultron/core/behaviors/call_out/bundles/deploy_monitoring.py`):

- `prioritize_deployment_factory` — Evaluator (p=0.90 → AlwaysSucceed)
- `monitoring_requirement_factory` — Evaluator (p=0.70 → AlwaysSucceed)
- `monitor_deployment_factory` — Actuator (p=1.00 → AlwaysSucceed)

`DeployFixCallOutBundle(DeploymentMonitoringBundle)` — adds:

- `deploy_fix_factory` — Evaluator (p=0.10 → AlwaysFail)

`DeployMitigationCallOutBundle(DeploymentMonitoringBundle)` — adds:

- `mitigation_deployed_factory` — Retriever (p=0.25 → AlwaysFail)
- `mitigation_available_factory` — Retriever (p=0.70 → AlwaysSucceed)
- `deploy_mitigation_factory` — Evaluator (p=0.75 → AlwaysSucceed)

### Combinator tree

`create_deploy_tree()` in `vultron/core/behaviors/report/deploy_tree.py`
composes the overarching deployment decision:

```text
DeployOrMitigateBT (Fallback)
├─ create_deploy_fix_tree(...)      # fix arm — preferred
└─ create_deploy_mitigation_tree(...)  # mitigation arm — fallback
```
