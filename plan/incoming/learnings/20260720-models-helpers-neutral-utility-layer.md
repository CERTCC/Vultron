---
title: core/models/_helpers.py is the correct home for layer-neutral utility functions
type: learning
timestamp: '2026-07-20T00:00:00+00:00'
source: ISSUE-1428
---

## Observation

`_as_id` and `_report_phase_status_id` were placed in `use_cases/_helpers.py` — likely because use cases needed them first. Both helpers have zero dependencies above primitive types (`str`, `Any`, `uuid`). This caused 15+ `behaviors/` files to import from `use_cases/`, violating BT-IDM-02.

## Learning

When a utility function has no dependencies above `models/` (no ports, no state machines, no use-case logic), its canonical home is `vultron/core/models/_helpers.py`. That module sits at the bottom of the hexagonal stack and is safely importable by **all** layers (behaviors/, use_cases/, services/, adapters/).

Misplacing a layer-neutral helper in a higher layer creates silent transitive violations everywhere the helper is used. The right fix is to move the helper down the stack, not to create a sidecar module at the same level.

## Pattern to apply

Before placing a new utility in `use_cases/_helpers.py` or any layer-specific helpers module, ask: does this function depend on anything above `models/`? If no, put it in `core/models/_helpers.py`.
