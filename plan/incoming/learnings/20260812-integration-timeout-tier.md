---
title: A timeout tuned for one test tier masquerades as flakiness in another
date: 2026-08-12
source: ISSUE-2237
type: learning
tags: [testing, pytest, timeout, flaky-tests, triage]
---

# A timeout tuned for one test tier masquerades as flakiness in another

## What happened

While validating #2237, `uv run pytest -m integration` exited 1 with two
`+++ Timeout +++` dumps and **no summary line**. Which test tripped it moved
with the `pytest-randomly` seed, and `-p no:randomly` made the suite pass — the
classic signature of a flaky test.

It was not flaky. `timeout = 5` in `pyproject.toml` is sized for the unit suite,
but several integration tests do 3.5-4.3s of honest work. Because
`timeout_method = "thread"` kills the *whole pytest process* rather than the one
slow test, a single spurious trip aborted the session. At the suite level the
failure was **reliably red** (2/2 on clean `origin/main` 65fe33f1b); only the
location was nondeterministic.

Fixed by #2270: `test/conftest.py::apply_integration_timeout` gives
`integration`-marked tests a 60s tier while the unit suite keeps 5s.

## Why it matters

A red integration run carried **no information about the branch**. That is worse
than a failing test — it trains everyone to re-run rather than read, and it lets
a genuinely broken branch be waved off as "the usual timeout".

The near-miss: the ready-made move was to add two rows to
`notes/flaky-tests.md` and proceed. That would have permanently catalogued a
config defect as noise, which is exactly the error #2249 was filed to correct in
the opposite direction.

## How to apply

- Before cataloguing a test as flaky, ask whether the test is nondeterministic
  or whether the **ceiling** is wrong. Distinguish *suite reliably red* from
  *test intermittently red*; if only the failure's location varies, suspect a
  global resource limit, not the tests.
- `-p no:randomly` flipping a suite green is not evidence of flakiness. It is
  evidence of order- or timing-sensitivity, which a too-tight global timeout
  produces.
- Check for a summary line before concluding anything. A session aborted by
  `timeout_method = "thread"` looks identical to a clean pass if you only count
  `FAILED` lines. `notes/flaky-tests.md` already recorded this trap; it caught a
  second victim anyway, so check for the `+++ Timeout +++` marker explicitly.
- Timeouts are diagnostics, not correctness invariants. When a tier fires on
  honest work rather than catching hangs, change the tier — do not contort the
  tests or paper over it with scattered `@pytest.mark.timeout(N)`.
- When widening a timeout, prefer widening the ceiling over switching
  `timeout_method` off `thread`. The signal method cannot interrupt code blocked
  in a C extension, so it converts a noisy abort into an invisible hang.

Related: [[20260812-cs-hypercube-premise-was-wrong]]
