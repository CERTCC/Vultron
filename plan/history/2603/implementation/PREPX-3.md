---
title: "PREPX-3 \u2014 Remove `DispatchEvent` and `InboundPayload` deprecated\
  \ aliases (2026-03-18)"
type: implementation
timestamp: '2026-03-18T00:00:00+00:00'
source: PREPX-3
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1940
legacy_heading: "PREPX-3 \u2014 Remove `DispatchEvent` and `InboundPayload`\
  \ deprecated aliases (2026-03-18)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-18'
---

## PREPX-3 — Remove `DispatchEvent` and `InboundPayload` deprecated aliases (2026-03-18)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1940`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
PREPX-3 — Remove `DispatchEvent` and `InboundPayload` deprecated aliases (2026-03-18)
```

**Legacy heading dates**: 2026-03-18

**Task**: Remove the `DispatchEvent` backward-compat wrapper from
`vultron/types.py` and the `InboundPayload` alias from
`vultron/core/models/events/__init__.py`. Neither was referenced outside its
definition file after PREPX-2 removed the handler shim layer.

**What was done**:

- Deleted `DispatchEvent` class and `DispatchActivity = DispatchEvent` alias
  from `vultron/types.py`. Removed the now-unused `BaseModel` and
  `MessageSemantics` imports. `BehaviorHandler` Protocol retained.
- Removed `InboundPayload = VultronEvent` alias and its `__all__` entry from
  `vultron/core/models/events/__init__.py`. Updated module docstring.
- Updated `specs/handler-protocol.yaml`: HP-01-001 now reflects the use-case
  class interface; HP-02-001 implementation note updated; verification
  criteria updated.
- Updated `specs/dispatch-routing.yaml`: Overview and DR-01-002 reflect
  `VultronEvent` + `DataLayer`; DR-02 verification uses `USE_CASE_MAP`;
  Related section updated to canonical paths.
- Updated `specs/code-style.yaml`: docstring example uses a use-case class.
- Updated `AGENTS.md`: quickstart example, Use-Case Protocol section,
  Registry Pattern section, Decorator Usage section, Quick Reference
  "Adding a New Message Type", Handler Testing checklist, Key Files Map
  (removed deleted shim entries), and Test Data Quality anti-pattern.

### Test results

981 passed, 5581 subtests, 5 warnings.
