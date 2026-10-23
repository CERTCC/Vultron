---
source: CONCERN-649
timestamp: '2026-06-02T20:53:03.516842+00:00'
title: Demo HTTP helpers use requests, which is not a declared runtime dependency
type: learning
---

## Summary

`vultron/demo/utils.py` and `vultron/demo/helpers/verification.py` import
`requests`, but `requests` is not listed in `pyproject.toml`
`[project.dependencies]`. `httpx` (>=0.28.1) is already a declared runtime
dep. Fresh non-dev installs may fail when demo or verification helpers make
HTTP calls.

## Category

- [x] Top risk

## Severity

high

## Evidence

- `vultron/demo/utils.py` — `import requests`
- `vultron/demo/helpers/verification.py` — `import requests`
- `pyproject.toml` — `httpx>=0.28.1` is listed; `requests` is absent from
  runtime deps

## Impact if Ignored

Users who install Vultron without dev dependencies will encounter
`ModuleNotFoundError: No module named 'requests'` when running the demo
or verification helpers, with no clear guidance on how to resolve the issue.

## Suggested Action

Migrate demo HTTP helpers from `requests` to `httpx`. Tracked in GitHub
issue #517 (child of bug #501). No timeline is currently set.

**Resolved**: 2026-06-02 — migration completed in #517 (closed). No
`requests` imports remain; `httpx` is the declared runtime dep. No
spec, notes, or AGENTS.md changes required.
