---
title: "Lint cleanup \u2014 mypy and pyright baseline burn-down"
type: implementation
timestamp: '2026-03-26T00:00:00+00:00'
source: LEGACY-2026-03-26-lint-cleanup-mypy-and-pyright-baseline-burn-down
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 239
legacy_heading: "Lint cleanup \u2014 mypy and pyright baseline burn-down (COMPLETE\
  \ 2026-03-26)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-26'
---

## Lint cleanup — mypy and pyright baseline burn-down

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:239`
**Canonical date**: 2026-03-26 (git blame)
**Legacy heading**

```text
Lint cleanup — mypy and pyright baseline burn-down (COMPLETE 2026-03-26)
```

**Legacy heading dates**: 2026-03-26

- Reduced `mypy` from 440 errors in 69 files to 0 without broad ignore
  rules; fixes focused first on shared protocols, DataLayer typing,
  AS2/domain model boundaries, and extractor/rehydration surfaces.
- Reduced `pyright` from 838 initial errors to 0 after the repository became
  more analyzable; the cleanup included preserving subclass identity in
  ActivityStreams registry decorators, tightening BT base typing, and
  updating stale `id=` / `object=` constructor call sites to
  `as_id=` / `as_object=`.
- Cleaned test infrastructure and fixtures so static analysis matches real
  runtime objects, especially around inbox/outbox handlers, persisted object
  round-trips, and BT mock state.
- Final validation completed with:
  - `uv run black vultron/ test/`
  - `uv run flake8 vultron/ test/`
  - `uv run mypy`
  - `uv run pyright`
  - `uv run pytest --tb=short 2>&1 | tail -5`
- Final result: `1025 passed, 1 warning, 5581 subtests passed in 35.29s`
  package; split into 8 submodules (`_base`, `actor`, `case`, `embargo`, `note`,
  `participant`, `report`, `status`); compatibility shim provided.
- **TECHDEBT-6**: Shim `vultron/scripts/vocab_examples.py` removed (commit 29005e4);
  all callers updated to import directly from `vultron.as_vocab.examples`.
