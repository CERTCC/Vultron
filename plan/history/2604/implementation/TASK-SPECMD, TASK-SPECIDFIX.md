---
title: TASK-SPECMD + TASK-SPECIDFIX
type: implementation
timestamp: '2026-04-28T20:44:00+00:00'

source: TASK-SPECMD, TASK-SPECIDFIX
---

## TASK-SPECMD + TASK-SPECIDFIX — Spec YAML conversion and ID prefix fixes

Converted the two remaining Markdown spec files to YAML format and fixed
157 spec ID prefix violations across 8 spec files. Added a new lint
check that enforces the spec-ID-within-group prefix rule going forward.

**TASK-SPECMD** (SPECMD.1, SPECMD.2, SPECMD.3):

- `specs/datalayer.md` → `specs/datalayer.yaml` (DL prefix, 3 groups, 8 specs: DL-01 Auto-Rehydration, DL-02 Type-Safe Write, DL-03 Port Isolation)
- `specs/meta-specifications.md` → `specs/meta-specifications.yaml` (MS prefix, 10 groups, 29 specs)
- Deleted both `.md` source files
- Added `test/metadata/test_specs_format.py` to enforce no `.md` files in `specs/` except README.md

**TASK-SPECIDFIX** (SPECIDFIX.1, SPECIDFIX.2):

- Strategy: kept all spec IDs stable (too many external references in AGENTS.md, notes/, tests); renamed/merged groups instead
- Fixed all 157 violations by group operations:
  - `architecture.yaml`: extracted ARCH-09-001 into new ARCH-09 group
  - `ci-security.yaml`: merged CISEC-03 into CISEC-01; renamed CISEC-04→03, CISEC-05→04
  - `code-style.yaml`: 11 group ops (merge CS-02 into CS-01, extract CS-04, rename CS-12 through CS-17)
  - `handler-protocol.yaml`: merged HP-08 into HP-07; renamed HP-09→08, HP-10→09
  - `project-documentation.yaml`: renamed PD-04→03, PD-06→04, PD-07→05, PD-08→06
  - `spec-registry.yaml`: merged 8 MUST/SHOULD pairs into single groups (SR-01 through SR-08)
  - `sync-log-replication.yaml`: merged SYNC-04 into SYNC-03; renamed SYNC-05 through SYNC-10
  - `triggerable-behaviors.yaml`: merged TRIG-03 through TRIG-07 into TRIG-02; renamed TRIG-08 through TRIG-15
- Fixed SR-08-004: removed incorrect reference to meta-specifications.md
- Added `_check_spec_id_prefix_consistency()` to `vultron/metadata/specs/lint.py`
- Added tests to `test/metadata/specs/test_lint.py` (SPECIDFIX.1)

All 1944 tests pass. `spec-lint specs/` exits 0 with new check active.
Commit: e6af9cb4
