---
title: "create_deploy_fix_tree omits legacy non-vendor public-aware deploy gate"
type: learning
timestamp: "2026-07-30T00:00:00Z"
source: ISSUE-1825-c
signal: design-question
---

The legacy `Deployment` tree gated deployment ability via
`_DecideAbilityToDeploy` = `RoleIsVendor OR CSinStateNotDeployedButPublicAware`
(`vultron/bt/report_management/_behaviors/deploy_fix.py`): a non-vendor deployer
could only deploy a fix after the case was public. Issue #1825 AC-1 enumerates
the `_DeployFixIfReady` guard set as `CheckDeployerRoleNode` +
`CheckRMStateAccepted` + `CheckCSFixNotYetDeployed` + call-outs — with no
public-aware check. The new `create_deploy_fix_tree` therefore gates only on the
deployer role and drops the public-aware precondition for non-vendor deployers.

Decision: honoured AC-1 as written (best-judgment call, unattended); did not
re-introduce the legacy gate, to avoid unscoped protocol-behavior expansion.

**Why:** this is a protocol-behavior difference from the legacy simulation, not
a bug in this PR — but it is a latent gap: a non-vendor deployer can now deploy
before public awareness.

**How to apply:** if MPCVD correctness requires the public-aware precondition
for non-vendor deployers, file a follow-up issue to add a
`CSinStateNotDeployedButPublicAware`-equivalent guard to the deploy arm (or
confirm in the spec that vendor-role gating alone is sufficient). See
[[20260730-1825-checkcsfixnotyetdeployed-guard-strength]].

**Promoted**: 2026-07-31 — captured in `notes/do-work-behaviors.md` (deploy-fix public-aware precondition section).
Docs PR: TBD.
