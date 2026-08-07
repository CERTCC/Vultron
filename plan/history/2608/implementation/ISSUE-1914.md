---
source: ISSUE-1914
timestamp: '2026-08-07T20:44:48.129340+00:00'
title: 'fix: run integration suite in pre-PR validation'
type: implementation
---

## Issue #1914 — Pre-PR validation silently skips all integration tests

Fixed the blind spot where `build` Phase 6 and `create-pr` Phase 3 both ran
`uv run pytest --tb=short` which silently deselected all integration tests via
`addopts = "-m 'not integration'"` in pyproject.toml.

**Root cause**: validation steps hardcoded a command that relies on `addopts`
to run everything, but `addopts` actively *excludes* integration tests. A
branch breaking only `test/demo/` tests (all auto-marked `integration`) could
open a non-draft PR reporting "tests pass".

**Fix**: Added `uv run pytest -m integration --tb=short 2>&1 | tail -5` after
the unit run in both `build` Phase 6 and `create-pr` Phase 3. Updated
`run-tests/SKILL.md` to document the two-step pre-PR validation requirement.

**Files changed**: `.agents/skills/build/SKILL.md`,
`.agents/skills/create-pr/SKILL.md`, `.agents/skills/run-tests/SKILL.md`

PR: <https://github.com/CERTCC/Vultron/pull/2114>
