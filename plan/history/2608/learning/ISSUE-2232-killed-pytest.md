---
title: Tooling — a pytest run killed by the 5s per-test timeout is indistinguishable from a passing run under the mandated command
type: learning
timestamp: 2026-08-12T00:00:00Z
source: ISSUE-2232-killed-pytest
signal: tooling-issue
---

`pyproject.toml` sets `timeout = 5` with `timeout_method = "thread"`
(pytest-timeout). When a test exceeds that budget the plugin dumps a stack
trace and **kills the process** — the run stops partway, having executed maybe
12% of the suite.

The ONE RUN RULE mandates `uv run pytest --tb=short 2>&1 | tail -5`. That
command cannot show this happening, for two compounding reasons:

1. The pipeline's exit status is `tail`'s, not pytest's, so a killed run still
   reports `0`.
2. The faulthandler stack dump is long and lands at the end of the combined
   stream, so `tail -5` shows dump frames where the
   `N passed, M skipped in Xs` summary line would normally be.

The result is a validation cycle that produced no summary line and exited `0`.
Both of my first two unit-suite runs on this branch were killed this way; I
only noticed because the last visible progress marker read `[ 10%]`. Redirecting
to a file and checking pytest's own exit code showed `UNIT_EXIT=1` and the kill
inside `test/metadata/specs/test_real_specs.py::test_real_specs_lint_no_hard_errors`.

The test itself is fine in isolation — 3.05s against the 5s budget, 61% of it —
which is exactly the problem: it is close enough to the ceiling that ambient
load decides the outcome, and the whole suite dies with it. A third run passed
cleanly (6592 passed in 115s), confirming a load-sensitive flake rather than a
branch-owned failure.

**Suggestions:**

- Have the run-tests skill capture full output and assert on pytest's own exit
  code, e.g. `uv run pytest --tb=short > /tmp/unit.log 2>&1; echo $?` followed
  by a grep for the summary line — so an absent summary is loud rather than
  silent. `tail -5` on a pipe is not a safe success signal.
- Either raise the global `timeout` or mark the spec-lint tests with a larger
  per-test budget. A single slow test taking the entire suite down is a
  disproportionate failure mode, and 61%-of-budget is not headroom.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: killed pytest run reports exit 0 under tail -5.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
