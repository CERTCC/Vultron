---
source: issue-528
timestamp: '2026-05-15T16:07:29.174764+00:00'
title: 'Add pytest-timeout guardrail: 30s default per-test ceiling'
type: implementation
---

## Issue #528 — Add pytest-timeout guardrail: 30s default per-test ceiling

Added `pytest-timeout` (v2.4.0) as a dev dependency and configured a
30-second default per-test timeout with thread-based interruption. Changed
files: `pyproject.toml`, `uv.lock`, `test/AGENTS.md`. Unit suite (2368 tests)
passed with no unexpected trips. PR: <https://github.com/CERTCC/Vultron/pull/529>
