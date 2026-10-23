---
title: "P347-DEMOORG \u2014 Reorganize demo/ into exchange/ and scenario/\
  \ sub-packages"
type: implementation
timestamp: '2026-04-20T00:00:00+00:00'
source: P347-DEMOORG
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6946
legacy_heading: "P347-DEMOORG \u2014 Reorganize demo/ into exchange/ and scenario/\
  \ sub-packages"
date_source: git-blame
---

## P347-DEMOORG — Reorganize demo/ into exchange/ and scenario/ sub-packages

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6946`
**Canonical date**: 2026-04-20 (git blame)
**Legacy heading**

```text
P347-DEMOORG — Reorganize demo/ into exchange/ and scenario/ sub-packages
```

**Commit**: d4e650e5
**Priority**: 347

Reorganized `vultron/demo/` into two semantically distinct sub-packages:

- **`vultron/demo/exchange/`** (13 scripts): Individual protocol-fragment demos
  using direct inbox injection to demonstrate single-message semantics.
  (`receive_report_demo`, `initialize_case_demo`, `initialize_participant_demo`,
  `invite_actor_demo`, `establish_embargo_demo`, `acknowledge_demo`,
  `status_updates_demo`, `suggest_actor_demo`, `transfer_ownership_demo`,
  `manage_case_demo`, `manage_embargo_demo`, `manage_participants_demo`,
  `trigger_demo`)

- **`vultron/demo/scenario/`** (3 scripts): End-to-end multi-actor workflow demos
  using trigger-based puppeteering.
  (`two_actor_demo`, `three_actor_demo`, `multi_vendor_demo`)

**Changes:**

- Created `exchange/__init__.py` and `scenario/__init__.py` with docstrings
- `git mv` all 16 demo scripts into the appropriate sub-package
- Updated cross-imports in `three_actor_demo.py` and `multi_vendor_demo.py`
- Updated all 16 import paths in `vultron/demo/cli.py`
- Updated all import paths in 18 test files under `test/demo/`
- Updated mkdocstrings references in `docs/reference/code/demo/demos.md`
- Added `exchange/README.md` and `scenario/README.md`
- Restructured `vultron/demo/README.md` to describe the two sub-packages

**Test Result:**

1669 passed, 12 skipped, 182 deselected, 5581 subtests passed
