---
title: "WIRE-TRANS-03 \u2014 Concrete wire object/domain conversions"
type: implementation
date: '2026-04-15'
source: WIRE-TRANS-03
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6306
legacy_heading: "WIRE-TRANS-03 \u2014 Concrete wire object/domain conversions"
date_source: git-blame
---

## WIRE-TRANS-03 — Concrete wire object/domain conversions

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6306`
**Canonical date**: 2026-04-15 (git blame)
**Legacy heading**

```text
WIRE-TRANS-03 — Concrete wire object/domain conversions
```

**Date**: 2026-04-15

**Task**: Implement `from_core()` on concrete wire object types and add
`to_core()` where the reverse mapping is well-defined.

**What was done**:

- Added shared helpers to `vultron/wire/as2/vocab/objects/base.py` for
  reference-ID normalization and reverse field-map application.
- Implemented concrete `from_core()` / `to_core()` methods on:
  - `VulnerabilityReport`
  - `CaseStatus`
  - `ParticipantStatus`
  - `CaseParticipant`
  - `VulnerabilityCase`
  - `CaseLogEntry`
  - `CaseActor`
- `VulnerabilityCase.from_core()` now materializes string-only `case_activity`
  entries as minimal `as_Activity` objects for wire validation, while
  `to_core()` collapses them back to ID strings.
- Reverse translation of nested wire objects now routes through each nested
  object's own `to_core()` implementation so enum-valued state fields survive
  the round-trip cleanly.
- Added focused regression coverage in
  `test/wire/as2/vocab/test_wire_domain_translation.py`.

**Validation**:

- `uv run black vultron/ test/`
- `uv run flake8 vultron/ test/`
- `uv run mypy`
- `uv run pyright`
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1425 passed, 12 skipped, 182 deselected, 5581 subtests passed in 23.29s`
