---
source: ISSUE-985
timestamp: '2026-06-16T14:41:27.675456+00:00'
title: replace httpx with httpx2 for starlette 1.3.1 compatibility
type: implementation
---

## Issue #985 — Test collection fails: starlette 1.3.1 requires httpx2 but tests use httpx

**Symptoms**: Starlette 1.3.1 (merged via PR #983) emits a
`StarletteDeprecationWarning` when `httpx` is used with
`starlette.testclient`. Because `filterwarnings = ["error"]` is set in
`pyproject.toml`, the warning was promoted to a hard error at collection
time, blocking three test packages:
`test/adapters/driven/test_delivery_inbox_url.py`,
`test/adapters/driving/fastapi/`, and `test/demo/`.

**Root cause**: `httpx` has become a supply-chain risk and is no longer
maintained; `httpx2` is its maintained successor and a drop-in replacement.

**Fix**: Replaced `httpx` with `httpx2` across all production and test code:

- `pyproject.toml`: `httpx>=0.28.1` → `httpx2`
- All `import httpx` → `import httpx2 as httpx` in `vultron/` and `test/`
- All `patch("httpx.X", ...)` → `patch("httpx2.X", ...)` in test files
- All `logging.getLogger("httpx")` → `logging.getLogger("httpx2")` in
  demo and adapter files

**Outcome**: 3584 tests pass (0 new), all linters clean, previously
failing packages collect and pass.

PR: [#987](https://github.com/CERTCC/Vultron/pull/987)
