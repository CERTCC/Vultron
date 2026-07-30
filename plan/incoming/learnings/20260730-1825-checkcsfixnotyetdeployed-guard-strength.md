---
title: "AC-3 guard name understated the required VFD precondition"
type: learning
timestamp: 2026-07-30
source: ISSUE-1825
signal: spec-ambiguity
---

Issue #1825 AC-3 said to "Create `CheckCSFixNotYetDeployed` guard node." Read
literally, that name only requires the D bit to be unset (SUCCESS for `vfd`,
`Vfd`, or `VFd`). But the node guards the `_DeployFixIfReady` arm, whose action
node `TransitionCStoFixDeployed` performs the VFD `d→D` transition — which the
state machine (`_vfd_transitions`, `vultron/core/states/cs.py`) permits **only**
from `VFd`. The literal guard would let a deployer in `vfd`/`Vfd` jump straight
to `VFD` under any SUCCESS-returning `DeployFix` backend (e.g. STOCHASTIC),
producing an invalid status snapshot.

Resolution: implemented `CheckCSFixNotYetDeployed` to require exactly `VFd`
(fix-ready AND not-deployed), matching the legacy
`CSinStateVendorAwareFixReadyFixNotDeployed` guard. Caught by pre-PR code
review, not by the AC text.

**Why:** ACs that name a guard by its "not-yet-X" symptom can understate the
real precondition, which is set by the state-machine transition the guarded
action performs.

**How to apply:** when an AC names a CS/RM/EM guard, derive its SUCCESS
condition from the source state(s) of the transition the guarded action
triggers, not from the guard's name. Cross-check against the legacy simulation
tree's equivalent guard.
