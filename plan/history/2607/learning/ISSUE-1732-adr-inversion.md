---
title: "ADR-0025 amendment created a core→demo import inversion (blocks #1732)"
type: learning
timestamp: "2026-07-29T00:00:00Z"
source: ISSUE-1732-adr-inversion
signal: design-question
---

While scoping #1732 (in-process fuzz simulation scenario), found that ADR-0025's
2026-07-23 "Bundle Selection Mechanism" amendment contradicts one of ADR-0025's
own decision drivers: "keep simulation artifacts (`vultron/demo/fuzzer/`) out of
`vultron/core/behaviors/` (BT-16-001)".

The amendment placed the call-out **bundle dataclasses** and the
`<DOMAIN>_DETERMINISTIC` **singletons** in `vultron/demo/fuzzer/bundles/`, then
had ~11 core tree builders import them as no-arg defaults (~26
`from vultron.demo...` imports under `vultron/core/behaviors/`). Core depends on
demo. No architecture ratchet guarded it — `test/architecture/` had
core-no-wire and core-no-adapter but no core-no-demo test.

Issue #1732 needs STOCHASTIC bundles injected through the trigger→use-case→BT
cascade (the `Svc*UseCase` classes call tree builders with no `call_out` arg, so
the whole cascade is DETERMINISTIC and there is no injection seam reaching it).
Building the scenario as specified would deepen the inversion.

Decision (maintainer adh): fix the layering first, as its own PR, before
building #1732. Corrected design — bundle dataclasses, `<DOMAIN>_DETERMINISTIC`
singletons, `CallOutBackendFactory` Protocol, and constant `AlwaysSucceed`/
`AlwaysFail` nodes move into a new `vultron/core/behaviors/call_out/` package;
only the probabilistic `WeightedBehavior` nodes and `<DOMAIN>_STOCHASTIC` bundles
stay in demo. Add `test_core_no_demo_imports.py` ratchet. Rewrite the ADR-0025
amendment to record the correction.

Tracked as #1793, wired to block #1732. The seam-injection mechanism for #1732
(threading `call_out` explicitly through `TriggerService` → `Svc*UseCase` →
`_build_tree`) is chosen but implemented after #1793 lands.

**Promoted**: 2026-07-31 — fixed in code via PR #1793 (ADR-0025 correction); architecture boundary now enforced by `test/architecture/test_core_no_demo_imports.py`. No additional durable doc update needed.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1900>0>0>0>0>.
