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
partway through (observed at 6% and again at 79%) with a faulthandler traceback,
no `short test summary info`, and no pass/fail counts.

This fires on load, not on defect. It was triggered twice during this session
simply by running `uv run pyright` concurrently with `uv run pytest` in the
devcontainer; the two aborts named unrelated tests
(`test/architecture/test_activity_factory_imports.py`, which AST-parses every
`.py` file, and a `starlette.testclient` HTTP test). Run alone, the full suite
passes with zero failures.

Two costs: the output looks like a hard failure of whatever test happened to be
running, which invites debugging the wrong thing; and there is no signal
distinguishing "too slow" from "hung". Do not run other heavy tooling
concurrently with the suite in this container, and read an abrupt end-of-log
faulthandler dump as contention until proven otherwise.

Possible systemic fixes: raise the default `timeout`, mark the handful of
genuinely slow tests with `@pytest.mark.timeout(N)` and lower the global value,
or switch to `timeout_method = "signal"` so a single test fails instead of the
process dying.
