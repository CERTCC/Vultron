---
title: Receive-side boundary needs dual isinstance OR type_ check for wire objects
type: learning
timestamp: "2026-07-20T00:00:00+00:00"
source: ISSUE-1504
---

Core received-side use cases process incoming wire-layer activities before the
objects are stored in the DataLayer. At this boundary, `case_obj` is a wire-layer
`as_VulnerabilityCase`, not a core `VulnerabilityCase` — so `isinstance(case_obj,
VulnerabilityCase)` returns False.

The fix without importing wire types in core: use a dual check:

```python
if (
    not isinstance(case_obj, VulnerabilityCase)
    and getattr(case_obj, "type_", None) != "VulnerabilityCase"
):
    # reject — neither core type nor wire type claiming to be a VulnerabilityCase
    return
```

This pattern:

- Accepts core `VulnerabilityCase` objects (from dl.read())
- Accepts wire `as_VulnerabilityCase` objects (from incoming activities)
- Rejects anything else
- Does NOT import from `vultron/wire/` — preserves ARCH-01-001

Applies to `vultron/core/use_cases/received/actor/announce.py` and any future
received-side use case that processes wire objects at the entry point.

**Promoted**: 2026-07-22 — captured in `vultron/core/AGENTS.md`.
Docs PR: TBD (fill in after PR is opened).
