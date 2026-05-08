---
source: ISSUE-469-CI
timestamp: '2026-05-08T17:28:58.040043+00:00'
title: CI runs all tests; local default omits integration
type: learning
---

## Learning: CI Runs All Tests; Local Default Omits Integration

When demo files or scenario assertions are modified, local `uv run pytest` runs
only `pytest -m 'not integration'` (via `pyproject.toml addopts`), while CI
runs `uv run pytest -m "" --tb=short` (all tests including integration). This
means integration-marked failures — especially hardcoded count assertions in
`vultron/demo/scenario/` — are invisible locally and only surface in CI.

**Root cause of the #473 CI failure**: `verify_vendor_case_state()` had a
hardcoded `!= 2` participant-count check. After #469 added a third participant
(case-actor), this was not caught locally because the test is marked
`@pytest.mark.integration` and skipped by default.

**Fix applied**: Updated `AGENTS.md` commit workflow to require `pytest -m ""`
when any demo or scenario file is touched. Added "CI Runs All Tests; Default
Local Run Omits Integration" to AGENTS.md Common Pitfalls.

**Long-term**: Replace hardcoded count assertions with presence-based checks
(commented on Issue #463).
