---
title: pytest killed by SIGKILL (exit 137) when run multiple times in same session
type: learning
timestamp: 2026-09-01
source: ISSUE-2458
signal: tooling-issue
---

During ISSUE-2458 build session, running `uv run pytest --tb=short` three times
in sequence resulted in the third run being killed with exit code 137 (SIGKILL).
The first two runs completed normally (7915 passed in ~119s each). The SIGKILL
occurred at ~27% completion on the third run.

Likely cause: container memory exhaustion from repeated full-suite runs in the
same session. The `pytest-timeout` thread method kills the *whole process* rather
than just the offending test, which can also produce exit 137.

Mitigations already documented:

- Always redirect to a file and check pytest's own exit code (`echo $?`)
- The absence of a summary line from `tail -5` is the signal that the run was killed
- Known pre-existing: `notes/flaky-tests.md` documents this class of issue

No new action needed beyond awareness: run pytest once before freshen, confirm
the suite passes, and trust that result for docstring-only changes.
