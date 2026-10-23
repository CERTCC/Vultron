---
title: 'VOCAB-REG-1.2: Migrate vocabulary classes and update callers'
type: implementation
timestamp: '2026-04-17T00:00:00+00:00'
source: VOCAB-REG-1.2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6687
legacy_heading: "2026-04-10 \u2014 VOCAB-REG-1.2: Migrate vocabulary classes\
  \ and update callers"
date_source: git-blame
legacy_heading_dates:
- '2026-04-10'
---

## VOCAB-REG-1.2: Migrate vocabulary classes and update callers

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6687`
**Canonical date**: 2026-04-17 (git blame)
**Legacy heading**

```text
2026-04-10 — VOCAB-REG-1.2: Migrate vocabulary classes and update callers
```

**Legacy heading dates**: 2026-04-10

- **Outcome**: SUCCESS
- **Summary**: Completed the vocabulary registry migration by removing all
  `@activitystreams_*` decorator call sites (74 sites across 16 files), adding
  `pkgutil`/`importlib` dynamic discovery to four `__init__.py` files,
  explicitly registering `as_Actor`, updating all `find_in_vocabulary()` callers
  to handle `KeyError`, and adding a subclass-identity preservation fix to the
  registry decorators (returning `TypeVar`-based generic signature instead of
  `type[BaseModel]`). Test suite updated with new registry and completeness
  tests plus a regression test for BUG-26040902.
- **Artifacts**:
  - 16 vocab class files: removed `@activitystreams_object` /
    `@activitystreams_activity` / `@activitystreams_link` call sites
  - `vultron/wire/as2/vocab/objects/__init__.py`,
    `vultron/wire/as2/vocab/activities/__init__.py`,
    `vultron/wire/as2/vocab/base/objects/__init__.py`,
    `vultron/wire/as2/vocab/base/objects/activities/__init__.py` — added
    dynamic module discovery
  - `vultron/wire/as2/vocab/base/registry.py` — explicit `as_Actor`
    registration, `TypeVar` return type preservation
  - `vultron/wire/as2/parser.py` — activity-type guard (`issubclass` check)
  - `test/wire/as2/vocab/base/test_registry.py` — new unit tests
  - `test/wire/as2/vocab/base/test_registry_completeness.py` — new completeness
    tests
  - `test/core/behaviors/case/test_bug_26040902_regression.py` — regression
    test for BUG-26040902
