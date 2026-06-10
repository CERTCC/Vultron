---
source: CONCERN-501
timestamp: '2026-05-19T20:00:08.038567+00:00'
title: Demo HTTP calls use requests which is not declared in project.dependencies
type: learning
---

## #501 Demo HTTP calls use `requests` which is not declared in `project.dependencies`

`vultron/demo/utils.py` and `vultron/demo/helpers/verification.py` import `requests`,
but `requests` is not listed in `project.dependencies` in `pyproject.toml`. The `httpx`
library (`>=0.28.1`) is already a declared runtime dependency and could serve as a
drop-in replacement.

**Category**: Top risk

**Severity**: high

**Evidence**:

- `vultron/demo/utils.py`
- `vultron/demo/helpers/verification.py`
- `vultron/demo/scenario/two_actor_demo.py`
- `pyproject.toml`

**Impact if Ignored**: Fresh non-dev installs may fail at runtime when demos run
outbound HTTP calls, since `requests` is not guaranteed to be installed.

**Suggested Action**: Migrate demo HTTP calls from `requests` to `httpx` (already
a declared runtime dep), or formally add `requests` to `project.dependencies`.

**Resolved**: 2026-05-19 — implementation tracked in #517.
