---
title: "Do-Work Behaviors: Scope Boundaries"
status: active
kind: guidance
description: >
  Which 'do work' behaviors Vultron models, which are external processes it
  only records, and the one known protocol difference in the deploy-fix tree.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/case-management.yaml
  - specs/triggerable-behaviors.yaml
related_notes:
  - notes/triggerable-behaviors.md
relevant_packages:
  - vultron/core/behaviors/report
  - vultron/demo/fuzzer
---

# Do-Work Behaviors: Scope Boundaries

The "do work" branches of the reference trees (`docs/topics/behavior_logic/`)
mix protocol actions with external, human-driven work. Vultron records the
outcomes of external work as state transitions and notes; it does not automate
it.

---

## Vulnerability Discovery Is Out of Scope

Vultron does not model discovery. Its starting point is a finder or reporter
submitting a `VulnerabilityReport` to an inbox; `vuldisco_bt.md` is
explanatory only and needs no implementation.

---

## External Processes Are Call-Out Points, Not Automation

Exploit acquisition, threat monitoring, fix development, and fix deployment
are external processes. Model each as a call-out point (ADR-0025) whose
default backend is a stub, so a real integration can be injected without
restructuring the tree; never try to perform the work inside the BT. Threat
detection in particular arrives from outside: the monitoring nodes are
Retriever call-out points, and real signals come in through a Sentinel on the
call-in surface (#1143).

Documentation pages for these behaviors SHOULD carry an admonition stating
that the process is notional and not automated inside Vultron, so readers do
not expect the protocol to perform it.

---

## Each Sub-Behavior Owns Its Preconditions

`do_work_bt.md` draws the sub-behaviors (assign ID, develop fix, deploy fix,
publish, …) as one parallel node, as if all run at once. In the implementation
each sub-behavior's own tree states its preconditions as guard nodes (for
example, `create_assign_cve_id_tree` checks the CNA role first); do not rely
on the parallel parent to sequence them.

---

## Deploy-Fix Does Not Gate Non-Vendors on Public Awareness

The simulator let a non-vendor deployer deploy only after the case became
public (`RoleIsVendor OR CSinStateNotDeployedButPublicAware`).
`create_deploy_fix_tree` checks only the deployer role, RM `ACCEPTED`, and
fix-not-yet-deployed, so a non-vendor can deploy before public awareness.
Restoring the simulator behavior needs a spec entry first, then a guard on
the deploy arm (#1825).
