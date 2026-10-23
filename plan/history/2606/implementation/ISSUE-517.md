---
source: ISSUE-517
timestamp: '2026-06-02T13:41:45.543479+00:00'
title: 'Issue #517 migrate demo HTTP calls from requests to httpx'
type: implementation
---

## Summary

Replaced demo-layer HTTP usage from requests to httpx for runtime code and aligned demo health-check tests with the new transport calls.

## Changes

- Switched `vultron/demo/utils.py` DataLayerClient and server availability helpers from requests APIs to httpx APIs.
- Updated `vultron/demo/helpers/verification.py` to catch `httpx.HTTPStatusError`.
- Updated demo logging config references from `requests` logger to `httpx` logger in exchange/scenario demo scripts.
- Migrated `test/demo/test_health_check_retry.py` mocks and exception types from requests to httpx.

## Validation

- Ran black and flake8 successfully.
- Ran mypy and pyright successfully.
- Ran full pytest including integration tests successfully (`2722 passed, 12 skipped, 3 xfailed`).

## Links

- Issue: <https://github.com/CERTCC/Vultron/issues/517>
- PR: <https://github.com/CERTCC/Vultron/pull/661>
