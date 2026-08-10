---
title: "Global pytest thread-timeout aborts look like passing runs and fake nondeterminism"
type: learning
timestamp: "2026-08-08"
source: ISSUE-2086
signal: tooling-issue
---

`pyproject.toml` sets `timeout = 5` with `timeout_method = "thread"`. The thread
method cannot cancel a single test — it kills the **entire pytest process**. The
run then emits no `N passed / N failed` summary line and simply stops wherever it
was.

If a triage script counts `FAILED` lines to score a run, an aborted run scores
**zero failures** — indistinguishable from a clean pass. When the abort happens
before the suspect test is even reached, the test appears to have passed.

This produced a false conclusion on #2086. Three identical
`pytest -m "" test/demo/` runs gave `[2, 0, 2]` bootstrap failures, which was
read as proof the failures were "genuinely nondeterministic" and that
`-p no:randomly` did not stabilize them. Re-running with a driver that also
recorded the `+++ Timeout +++` marker and the presence of a summary line
reproduced `[2, 0, 2]` — and showed the middle run had `timeout=True` with no
summary. It never ran `test_pcr_bootstrap.py`.

At every granularity that runs both modules to completion, the failure was
deterministic (`[2, 2, 2]`), and the cause was ordinary cross-module config
leakage. Chasing phantom nondeterminism (dict iteration order, UUID collisions,
BackgroundTasks races) cost real time.

**How to measure a suspected flake reliably**:

- Require a summary line. Its absence means the run is void, not green.
- Grep for `+++ Timeout +++` and treat any hit as void.
- Don't infer pass/fail from exit code alone — an abort and a real failure both
  give non-zero.
- Drive repeated invocations from a Python `subprocess` list, not a shell
  variable holding a file list; word-splitting differences between `bash` and
  `zsh` silently turned an earlier bisect into exit-4 no-ops.

**Related**: `20260803-pytest-full-suite-timeout.md` recorded the same 5s
thread-timeout firing under load. The recurring cost suggests either raising
`timeout` for the integration/demo suites or switching to
`timeout_method = "signal"` so a slow test fails alone instead of voiding the
session.
