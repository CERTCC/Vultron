---
title: Fuzzer stub nodes may be spec'd and bundle-wired but not yet implemented
type: learning
timestamp: 2026-08-03T00:00:00Z
source: ISSUE-1891
signal: concern
---

During ISSUE-1891, `EmbargoExitPolicyGuard` and `EmbargoExitOverride` were found to be fully
designed (spec entries in `notes/bt-fuzzer-nodes-embargo.md`, bundle fields with correct
deterministic defaults in `EmbargoCallOutBundle`) but had zero implementation in
`vultron/demo/fuzzer/embargo.py`. The bundle fields silently fell back to `AlwaysSucceed`/`AlwaysFail`
stubs rather than raising an error, so the gap was invisible until a factory injection test was written.

**Risk**: Other call-out bundle domains (report management, CVD participant, etc.) may have the same
pattern — fields defined in the core bundle dataclass and wired into a DETERMINISTIC singleton, but no
corresponding fuzzer class in the demo layer and no stochastic factory in the demo bundle. A simulation
run using EMBARGO_STOCHASTIC-style bundles for those domains would silently use deterministic stubs
instead of exercising the probabilistic path.

**Suggested follow-up**: Audit all `CallOutBundle` dataclasses for fields whose stochastic bundle
factory is absent or points to a non-existent class. Create a Concern issue to track the gap.

**Promoted**: 2026-08-17 — captured in GitHub #2328 (Concern: CallOutBundle fuzzer stubs not stochastically implemented).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
