---
source: NOTE-coordination-agents-3421
timestamp: '2026-11-11T16:34:19.407331+00:00'
title: 'Archive coordination-agents section: core-owned typed-port contracts (#3421)'
type: note
---

## notes/coordination-agents.md — "Core-Owned Typed-Port Contracts (#3421)"

Archived when #3421 delivered the core capability declarations; replaced by
"Capability Declarations Are the Roster".

## Core-Owned Typed-Port Contracts (#3421)

Target state set by ADR-0097 and BT-18-012; today the mixins are still in
`vultron/demo/fuzzer/call_out_point.py`, and each fuzzer node declares a
`CallOutContract` (ADR-0183) rather than typed ports.

- Each named capability gets a **core-owned declaration** carrying py_trees typed
  ports (`INPUT_PORTS` / `OUTPUT_PORTS`, ADR-0044). The shape base class cannot
  hold a per-capability contract, because many capabilities share a shape.
- The probabilistic fuzzer stand-in stays in `vultron/demo/fuzzer/` (BT-16-001)
  and binds to that declaration instead of restating it.
- The docstring is description, not authority: BT-18-001 still requires it, but a
  test reads the ports, and a disagreeing docstring is a doc bug.
- The shape bases move to `vultron/core/behaviors/call_out/` as
  `EvaluatorCapability`, `RetrieverCapability`, `ComposerCapability`,
  `ActuatorCapability`; the fuzzer layer re-exports the old `*CallOutPoint` names
  and new code uses the capability names.

Why a contract declared outside core fails: `notes/call-out-configuration.md` §
"A data-producing capability's default must write its outputs".

