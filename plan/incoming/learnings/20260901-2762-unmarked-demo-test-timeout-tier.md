---
title: test_invite_actor_demo.py has no integration marker, so it runs at the 30s unit ceiling
type: learning
timestamp: 2026-09-01
source: ISSUE-2762
signal: tooling-issue
---

`uv run pytest -m ""` aborted at ~69% with a `+++ Timeout +++` dump and no
summary line. The stack named
`test/demo/test_invite_actor_demo.py::test_demo`, hung in
`setup_initialized_case` → `post_to_inbox_and_wait` on the first report-offer
POST.

It is not a flaky test and not a regression:

- Alone: 2 passed in 9.19s.
- Whole demo tier (`pytest -m "" test/demo/`): 1240 passed, exit 0.
- The unit tier (`pytest`): 8017 passed, exit 0.

The cause is the ceiling, not the test. `test/conftest.py` gives
`@pytest.mark.integration` tests `INTEGRATION_TIMEOUT_SECONDS = 60`; everything
else inherits `timeout = 30` from `pyproject.toml`.
`test_invite_actor_demo.py` carries no `integration` marker despite driving the
full HTTP stack in-process, so under combined unit+demo load its ~9s of honest
work crossed 30s. Because `timeout_method = "thread"` kills the whole pytest
process, one trip destroyed the signal for the entire session.

This is the exact error mode `notes/flaky-tests.md` warns about: "before adding
a row here, ask whether the test is nondeterministic or whether the *ceiling* is
wrong." Not catalogued as flaky for that reason.

Worth checking whether other demo test modules are missing the marker too — a
sweep of `test/demo/` for modules with no `pytestmark = pytest.mark.integration`
would size the problem. Fixing it is a test-infrastructure change, out of scope
for a bug fix on the embargo path.
