---
title: 'VOCAB-REG-1.1: Redesign vocabulary registry core mechanics'
type: implementation
timestamp: '2026-04-17T00:00:00+00:00'
source: VOCAB-REG-1.1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6665
legacy_heading: "2026-04-10 \u2014 VOCAB-REG-1.1: Redesign vocabulary registry\
  \ core mechanics"
date_source: git-blame
legacy_heading_dates:
- '2026-04-10'
---

## VOCAB-REG-1.1: Redesign vocabulary registry core mechanics

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6665`
**Canonical date**: 2026-04-17 (git blame)
**Legacy heading**

```text
2026-04-10 — VOCAB-REG-1.1: Redesign vocabulary registry core mechanics
```

**Legacy heading dates**: 2026-04-10

- **Outcome**: SUCCESS
- **Summary**: Replaced the Pydantic `Vocabulary(BaseModel)` singleton with a
  plain `VOCABULARY: dict[str, type[BaseModel]]` module-level dict and switched
  auto-registration from explicit decorator calls to `__init_subclass__` hook in
  `as_Base`. Added `VocabNamespace` enum (`AS`, `VULTRON`). All class files
  updated to remove `@activitystreams_*` decorator imports while leaving the
  decorator definitions in place for the follow-on migration (VOCAB-REG-1.2).
- **Artifacts**:
  - `vultron/wire/as2/vocab/base/enums.py` — new `VocabNamespace` enum
  - `vultron/wire/as2/vocab/base/registry.py` — rewrote flat-dict registry,
    removed decorator definitions, updated `find_in_vocabulary()` to raise
    `KeyError` on miss
  - `vultron/wire/as2/vocab/base/base.py` (`as_Base`) — added
    `_vocab_ns: ClassVar[VocabNamespace]`, added `__init_subclass__`
    auto-registration hook
  - `vultron/wire/as2/vocab/objects/base.py` (`VultronObject`) — overrides
    `_vocab_ns = VocabNamespace.VULTRON`
