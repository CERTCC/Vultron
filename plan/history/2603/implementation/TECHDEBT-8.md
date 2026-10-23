---
title: "TECHDEBT-8 \u2014 Pyright gradual static type checking (2026-03-10)"
type: implementation
timestamp: '2026-03-10T00:00:00+00:00'
source: TECHDEBT-8
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 882
legacy_heading: "TECHDEBT-8 \u2014 Pyright gradual static type checking (2026-03-10)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-10'
---

## TECHDEBT-8 — Pyright gradual static type checking (2026-03-10)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:882`
**Canonical date**: 2026-03-10 (git blame)
**Legacy heading**

```text
TECHDEBT-8 — Pyright gradual static type checking (2026-03-10)
```

**Legacy heading dates**: 2026-03-10

**Task**: Configure pyright for gradual static type checking (IMPLTS-07-002).

**Implementation**:

- Added `pyright` to `[dependency-groups].dev` in `pyproject.toml`.
- Created `pyrightconfig.json` at the repo root with `typeCheckingMode: "basic"`,
  targeting `vultron/` and `test/`, Python 3.12, `reportMissingImports: true`,
  `reportMissingTypeStubs: false`.
- Added `pyright` target to `Makefile` (`uv run pyright`).

**Baseline error count (2026-03-10, pyright 1.1.408, basic mode)**:

```text
811 errors, 7 warnings, 0 informations
```

These errors are pre-existing technical debt and are NOT blocking. They will
be resolved incrementally as part of ongoing development. New and modified
code should be made clean under pyright basic mode before merging.

**Key error categories observed**:

- `reportInvalidTypeArguments`: `Optional[str]` spelled as `str | None` used
  as type argument (Pydantic `Annotated` patterns) — widespread across
  `wire/as2/vocab/objects/`.
- `reportAttributeAccessIssue` / `reportOptionalMemberAccess`: Union types
  narrowed incorrectly in property implementations.
- `reportGeneralTypeIssues`: Field override without default value.
