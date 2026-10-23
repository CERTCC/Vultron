---
source: CONCERN-504
timestamp: '2026-06-10T16:58:55.574720+00:00'
title: Module size and organization — large files in all layers
type: learning
---

## Summary

Five production source files exceeding 500 lines and mixing multiple
responsibilities were identified. Three are also high-churn, increasing
merge-conflict risk.

## Category

- [x] Top risk
- [x] Technical debt

## Severity

medium

## Evidence (at time of filing)

- `vultron/demo/scenario/two_actor_demo.py` (2050 lines)
- `vultron/core/behaviors/case/nodes.py` (1502 lines)
- `vultron/adapters/driven/datalayer_sqlite.py` (1042 lines)
- `vultron/wire/as2/extractor.py` (821 lines)
- `vultron/semantic_registry.py` (783 lines)

## Progress since filing

- `case/nodes.py` → split into `nodes/` subpackage (#514, closed)
- `semantic_registry.py` → split into package (#702)
- `triggers/embargo.py` → split (#516, closed)
- `two_actor_demo.py` reduced from 2050 → 989 lines

## Remaining large files (at planning date 2026-06-10)

- `adapters/driven/datalayer_sqlite.py` — 1296 lines (grew)
- `core/behaviors/status/nodes.py` — 1281 lines (new)
- `demo/scenario/two_actor_demo.py` — 989 lines (integration complexity; skipped)
- `core/behaviors/embargo/nodes.py` — 920 lines (new)
- `wire/as2/extractor.py` — 826 lines (unchanged)
- `core/use_cases/received/case.py` — 819 lines (new)
- `core/behaviors/case/nodes/participant.py` — 816 lines (emerged from split)
- `core/use_cases/received/actor.py` — 803 lines (new)

## Impact if Ignored

Large, multi-responsibility files accumulate technical debt, slow review
cycles, and make targeted test coverage difficult. High-churn large files
are especially prone to merge conflicts.

**Resolved**: 2026-06-10 — implementation tracked in issues 876, 877, 878, 879, 880, and 881.
Docs PR: <https://github.com/CERTCC/Vultron/pull/875>.
Spec: `specs/code-style.yaml` (CS-18-001 through CS-18-004).
