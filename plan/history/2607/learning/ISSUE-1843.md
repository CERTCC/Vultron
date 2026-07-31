---
title: "STOCHASTIC call-out bundle for a production-only domain with no simulator fuzzer nodes"
type: learning
timestamp: "2026-07-30T00:00:00Z"
source: ISSUE-1843
signal: design-question
---

## Context

Issue #1843 added `StatusAuthorizationCallOutBundle` for the two-seam
received-side status authorization model (ADR-0046). Every prior
`<DOMAIN>_STOCHASTIC` singleton (validation, embargo, prioritization,
assign_cve_id, …) wires **existing named simulator fuzzer nodes** from
`vultron/demo/fuzzer/` (e.g. `EvaluateReportCredibility`, `WantToProposeEmbargo`).

The status-authorization domain is different: it is a **production-only**
pattern (ADR-0046 / IDEA-1836) with **no named fuzzer node counterpart** — the
two seams (`StatusUpdateGuard`, `SideEffectsGuard`) are new Evaluator call-outs
that never existed in the legacy `vultron/bt/` simulation. So there was no
established probabilistic class to wire, and no spec or `notes/` guidance on
what the STOCHASTIC singleton should contain.

## Decision made

Both seams in `STATUS_AUTHORIZATION_STOCHASTIC` use the generic
`AlmostAlwaysSucceed` (p=0.90) `WeightedBehavior` from
`vultron/demo/fuzzer/base.py`, chosen because:

- It matches the p=0.90 convention already used by the other Evaluator
  call-outs (report credibility/validity subclass `AlmostAlwaysSucceed`).
- p=0.90 → DETERMINISTIC ceiling of `AlwaysSucceed` (BT-23-002), consistent
  with the RSH-01-002 / RSH-02-002 `AlwaysSucceed` defaults.
- It still occasionally exercises the reject/block path during fuzz runs,
  which a mirror-of-DETERMINISTIC (both `AlwaysSucceed`) would not.

The user confirmed this choice when asked.

## Why this matters for future agents

When a future call-out domain is **production-only** (no legacy fuzzer node),
the STOCHASTIC singleton has no fuzzer class to wire. The precedent set here:
back both/all seams with the **generic `WeightedBehavior` subclass whose
`success_rate` equals the p implied by the DETERMINISTIC ceiling** (p≥0.5 →
`AlmostAlwaysSucceed`/similar, floor → `AlmostAlwaysFail`), rather than
mirroring DETERMINISTIC or inventing a bespoke fuzzer node. This keeps the
STOCHASTIC bundle behaviorally meaningful without adding simulation nodes for
a pattern that has no simulation counterpart.

Consider capturing this as a short rule in
`notes/call-out-configuration.md` (§ "Three-Mode Model" or a new
"production-only domains" note) if more such domains appear.

**Promoted**: 2026-07-31 — captured in `notes/call-out-configuration.md` (production-only domains section).
Docs PR: TBD.
