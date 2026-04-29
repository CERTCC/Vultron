---
title: "VCR-019a \u2014 Move case_states/ into vultron/core/ (2026-03-19)"
type: implementation
date: '2026-03-18'
source: VCR-019a
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2103
legacy_heading: "VCR-019a \u2014 Move case_states/ into vultron/core/ (2026-03-19)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-19'
---

## VCR-019a — Move case_states/ into vultron/core/ (2026-03-19)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2103`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
VCR-019a — Move case_states/ into vultron/core/ (2026-03-19)
```

**Legacy heading dates**: 2026-03-19

### What was done

Relocated `vultron/case_states/` into `vultron/core/` with no compatibility shims.

**New packages created:**

- `vultron/core/states/` — CS enum and related state machine definitions
  (`CS`, `CS_vfd`, `CS_pxa`, `VendorAwareness`, `FixReadiness`, `FixDeployment`,
  `PublicAwareness`, `ExploitPublication`, `AttackObservation`, `CompoundState`,
  `VfdState`, `PxaState`, `State`, helper functions `state_string_to_enums`,
  `state_string_to_enum2`, `all_states`). `cs.py` is the implementation module;
  `__init__.py` re-exports all public symbols.

- `vultron/core/scoring/` — Assessment/scoring enums moved from
  `vultron/case_states/enums/`: `EmbargoViability`, SSVC-2, CVSS-3.1, VEP,
  `Actions`, zero-day types, and utilities (`unique_enum_list`, `enum2title`,
  `enum_item_in_list`).

- `vultron/core/case_states/` — Remainder of `case_states/`: `validations.py`,
  `type_hints.py`, `hypercube.py`, `make_doc.py`, and `patterns/` subpackage.

**Errors merged:**

- `CvdStateModelError` hierarchy from `vultron/case_states/errors.py` appended
  directly to `vultron/errors.py`; all classes now inherit from `VultronError`.

**Callers updated:** 12 files in `vultron/`, 21 files in `test/`.

**Test directory renamed:** `test/case_states/` → `test/core/case_states/`.

**Deleted:** `vultron/case_states/` entirely.

### Test results

981 passed, 5581 subtests (unchanged from baseline).
