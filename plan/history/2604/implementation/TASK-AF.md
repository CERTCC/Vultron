---
title: "TASK-AF.1: Create factories/errors.py"
type: implementation
date: 2026-04-30
source: TASK-AF
---

## TASK-AF.1 — Create `factories/errors.py` with `VultronActivityConstructionError`

Created `vultron/wire/as2/factories/` package with `errors.py` defining
`VultronActivityConstructionError(VultronError)` and `__init__.py`
re-exporting it. Added `test/wire/as2/factories/test_errors.py` with four
tests covering inheritance, re-export identity, chained cause, and
catchability as VultronError. Subsequent AF steps (AF.2–AF.13) will add
domain factory modules, migrate call sites, and enforce the import boundary.
Specs satisfied: AF-04-002, AF-02-004 (partial — only errors module present).
