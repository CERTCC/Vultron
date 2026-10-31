---
title: >-
  DEMOMA-14-007 and DEMOMA-13-006 require the rccv Vendor to reach CS.VFD,
  which CSB-15-002 forbids a participant without the DEPLOYER role from
  reporting
type: learning
timestamp: 2026-10-31T08:52:34Z
source: ISSUE-5535
signal: spec-contradiction
---

## Trigger

You are reading a scenario group that obliges a Vendor to "advance through the
full fix lifecycle" or to reach a `VFD` case state, and the scenario's code
stops at `VFd` with a comment citing CSB-15-002.

## The question `learn` must settle

Three requirements oblige a `d → D` transition the protocol refuses:

- **DEMOMA-14-007** (MUST): "Vendor MUST advance through the full fix
  lifecycle: CS.VFd (fix ready) and CS.VFD (fix deployed)."
- **DEMOMA-13-006** (MUST): the RCCV-extension scenario "MUST advance to
  VFDPxa CS".
- **DEMOMA-13-011** (MUST): the invariant test file "MUST assert … CS
  transitions VFd and VFD observed in `add_participant_status_to_participant`
  entries for the Vendor actor".

**CSB-15-002** (MUST) says a participant must hold `CVDRole.DEPLOYER` to
report its own `d → D` transition, and one without it "has no deployer (d)
path, and MUST NOT report or record that transition". Both `rccv` scenarios
invite their Vendor with `CVDRole.VENDOR` alone, so the three DEMOMA
requirements cannot be met without breaking CSB-15-002.

Either the two groups should say `VFd`/`VFdPxa` — matching what the scenarios
do, and what `rcvcv` says for its VENDOR-only `V1` — or the scenarios should
invite their Vendor as `VENDOR + DEPLOYER`, which `rcvcv` does for `V2` and
which would change both recordings and both invariant lists. Which way it goes
is the question: the first is a wording correction, the second changes what the
scenarios demonstrate.

## Evidence

Found while composing the two scenarios in #5535 (PR #5595). The code is
already on CSB-15-002's side and says so: both fix-lifecycle steps are
labelled "vendor stops at VFd (CSB-15-002)", and neither invariant test
asserts a `D` transition — `test_rccv_extension_invariants.py` only repeats
the DEMOMA-13-011 claim in its module docstring. So the divergence has been
latent since the scenarios were written, and the invariant harness does not
catch it.

`rvcv-extension` and `rvcv-handoff` carry the same wording — DEMOMA-10-006 and
DEMOMA-11-006 both oblige "VFDPxa CS", and their Vendor2 is invited as
`CVDRole.VENDOR` alone too — so settle all five requirements together.

## How to apply

Do not resolve it inside a composition PR: DEMOMA-17-002 forbids a
consolidation from changing what a scenario passes or fails on, and either
resolution does one or the other. It needs its own change with its own issue.
That record is on open issue
[#5351](https://github.com/CERTCC/Vultron/issues/5351), the register for demo
requirements that contradict other requirements, which already carries
DEMOMA-15-002's rationale naming the same stop. `learn` settles which of the
two resolutions to take; #5351 tracks the work either one implies.
