---
title: verify_fix_deployed confusing for vendor-only actors after CSB-15-002 enforcement
type: learning
timestamp: 2026-07-28T16:40:00Z
source: ISSUE-1736
signal: concern
---

`verify_fix_deployed` in `vultron/demo/helpers/milestones.py` asserts
`CVDRole.VENDOR` in participant roles, then checks for `vfd_state == VFD`.
After enforcing CSB-15-002 (only DEPLOYER actors advance to VFD), calling
`verify_fix_deployed` with a vendor-only actor will fail at the VENDOR role
check before reaching the VFD state assertion — giving a confusing error
("actor does not hold CVDRole.VENDOR") when the real issue is that the actor
is a vendor-only actor who terminates at VFd, not VFD.

A future concern issue should: rename `verify_fix_deployed` to clarify it
is for DEPLOYER actors, update its docstring to remove the VENDOR role
requirement (DEPLOYER actors need not be VENDOR), and add a
`verify_fix_deployed_for_deployer` that checks for DEPLOYER role instead.
Tracked as a DEFER from ISSUE-1736 review.
