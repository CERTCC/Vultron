---
source: ISSUE-1428
timestamp: '2026-07-20T00:00:00+00:00'
title: move _as_id and _report_phase_status_id to core/models/_helpers
type: implementation
---

## Issue #1428 — BT import-direction violation: behaviors/ imported from use_cases/

`_as_id` and `_report_phase_status_id` were defined in `vultron/core/use_cases/_helpers.py` but had zero dependencies on the use_cases layer (only `str`, `Any`, `uuid`). This caused 15+ `behaviors/` files to violate BT-IDM-02 (behaviors/ MUST NOT import from use_cases/).

Fix: moved both helpers to `vultron/core/models/_helpers.py` — the bottom of the dependency stack, safely importable by all layers. Updated all 15 behaviors/ callers, 4 non-behaviors callers (services/, adapters/, use_cases/), and 16 test files to the new import path. Removed the now-unused `import uuid` from use_cases/_helpers.py; added `from vultron.core.models._helpers import _as_id` there for internal callers. Reduced `KNOWN_VIOLATIONS` in the architecture ratchet from 29 to 15. Added regression tests in `test/core/models/test_helpers.py`.

All 5083 tests pass, linters clean.

PR: <https://github.com/CERTCC/Vultron/pull/1524>
