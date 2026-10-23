---
source: ISSUE-1055
timestamp: '2026-06-18T20:17:45.638404+00:00'
title: example VulnerabilityCase genesis_hash fix
type: implementation
---

## Issue #1055 — fix: example VulnerabilityCase objects lack genesis_hash — violates CLP-08-003

**Symptoms**: Both the module-level `_CASE` object and the `case(random_id=True)`
path in `vultron/wire/as2/vocab/examples/_base.py` constructed `VulnerabilityCase`
without `attributed_to`, leaving `genesis_hash=""` in violation of CLP-08-003.

**Root cause**: Example objects predated PR #1048 (the genesis hash feature). The
model's empty-string default is intentional for rehydration, so no construction-time
error was raised.

**Fix**: Added `attributed_to=_VENDOR.id_` to both constructions so the
`_compute_genesis_hash_if_missing` model validator fires and produces a non-empty
hash. Also expanded the `genesis_hash` field descriptions in both `core/models/case.py`
and `wire/as2/vocab/objects/vulnerability_case.py` to document that the empty-string
default is intentional for rehydration paths (addressing acceptance criterion 3).

**Verification**: 2 new tests added (`test_case_has_genesis_hash`,
`test_case_random_id_has_genesis_hash`); 3486 passed, 2 xfailed in 53 s.
Black, flake8, mypy, pyright clean.

PR: [#1059](https://github.com/CERTCC/Vultron/pull/1059)
