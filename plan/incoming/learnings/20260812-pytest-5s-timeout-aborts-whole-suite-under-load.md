---
title: "pytest timeout=5 with timeout_method=thread aborts the entire suite under CPU contention, with no failure summary"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2235
signal: tooling-issue
---

`pyproject.toml` sets `timeout = 5` and `timeout_method = "thread"`. The thread
method cannot cancel a single test, so when any test exceeds 5 seconds
pytest-timeout dumps every thread's stack and **kills the process**. The run ends
partway through (observed at 6%, 38% and 71% on three separate runs) with a
faulthandler traceback, no `short test summary info`, and no pass/fail counts.

The margin is thin, which is why it fires so readily. `--durations=10` on a
quiet run puts the slowest tests at **3.84s, 3.01s and 2.96s** against the 5s
cap — `test/metadata/specs/test_real_specs.py::test_real_specs_lint_no_hard_errors`
and its neighbours, plus `test/architecture/test_activity_factory_imports.py`
at 2.91s. Any of those needs only ~30% CPU contention to cross the line and take
the whole run down with it.

This fires on load, not on defect. It was triggered three times during this
session by ordinary background work in the devcontainer — `uv run pyright`
running concurrently, and the graphify post-checkout rebuild that
`freshen-branch.sh` kicks off three times as it switches branches. Each abort
named a different, unrelated test
(`test/architecture/test_activity_factory_imports.py`, a `starlette.testclient`
HTTP test, a SQLite `cursor.execute`). Run with the machine quiet, or with
`--timeout=60`, the same suite passes with zero failures and zero timeouts.

Two costs: the output looks like a hard failure of whatever test happened to be
running, which invites debugging the wrong thing; and there is no signal
distinguishing "too slow" from "hung". Do not run other heavy tooling
concurrently with the suite in this container, and read an abrupt end-of-log
faulthandler dump as contention until proven otherwise.

Possible systemic fixes: raise the default `timeout`, mark the handful of
genuinely slow tests with `@pytest.mark.timeout(N)` and lower the global value,
or switch to `timeout_method = "signal"` so a single test fails instead of the
process dying.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: killed pytest run; docs/reference/codebase/TESTING.md.
Docs PR: TBD.
