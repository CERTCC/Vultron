---
source: ISSUE-1793
timestamp: '2026-07-29T15:16:31.328404+00:00'
title: Fix ADR-0025 core→demo call-out inversion; move DETERMINISTIC seam into core
type: implementation
---

## Issue #1793 — Fix ADR-0025 core→demo import inversion

PR: <https://github.com/CERTCC/Vultron/pull/1795>

ADR-0025's 2026-07-23 amendment placed the call-out bundle dataclasses and
`<DOMAIN>_DETERMINISTIC` singletons in `vultron/demo/fuzzer/bundles/` and had
~11 core tree builders import them as defaults — a core→demo dependency
inversion violating ADR-0025's own BT-16-001 driver. Discovered while scoping
issue #1732 (in-process fuzz scenario).

**Outcome:** Introduced `vultron/core/behaviors/call_out/` (Protocol,
deterministic `AlwaysSucceed`/`AlwaysFail` nodes, 9 bundle dataclasses +
`<DOMAIN>_DETERMINISTIC` singletons). Core builders now default to the core
DETERMINISTIC bundle with zero `vultron.demo` imports. Demo bundles keep only
`<DOMAIN>_STOCHASTIC` and re-export core symbols for back-compat.
`call_out_point.py` became a re-export shim. `publish_artifact_tree.py`'s
anomalous STOCHASTIC no-arg default was corrected to DETERMINISTIC. Added
`test/architecture/test_core_no_demo_imports.py` ratchet. Rewrote the ADR-0025
amendment, specs BT-23-003/005, and `notes/call-out-configuration.md`.

Deterministic ceiling/floor defaults and STOCHASTIC wiring verified identical
to pre-refactor across all 9 domains (no behavior change). Full suite: 6577
passed, 3 pre-existing xfail. Unblocks #1732.
