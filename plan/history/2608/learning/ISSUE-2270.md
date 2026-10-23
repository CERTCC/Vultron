---
title: A timeout tuned for one test tier masquerades as flakiness in another
timestamp: 2026-08-12T00:00:00Z
source: ISSUE-2270
type: learning
signal: tooling-issue
---

# A timeout tuned for one test tier masquerades as flakiness in another

*Areas: testing, pytest, timeouts, flaky-test triage.*

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

Fixed by #2270: a two-tier ceiling — 60s for `integration`-marked tests via
`test/conftest.py::apply_integration_timeout`, and the unit default raised from
5s to 30s in `pyproject.toml`.

## This was diagnosed four times before it was fixed

The same root cause was written up in three earlier learning files, each time as
a workaround rather than a fix:

| File | Source | What it concluded |
|---|---|---|
| `20260803-pytest-full-suite-timeout.md` | ISSUE-1925 | full suite "never finishes"; worked around with scoped runs |
| `20260805-per-test-timeout-marginal-under-load.md` | ISSUE-1988 | AST ratchets at ~3.4s sit near the 5s ceiling; mitigated one ratchet with a prefilter |
| `20260808-pytest-thread-timeout-fakes-nondeterminism.md` | ISSUE-2086 | thread-method aborts fake nondeterminism; cost real time chasing phantoms |

Three sessions correctly identified that `timeout = 5` plus
`timeout_method = "thread"` was the problem, and all three treated the ceiling as
fixed background. The unit tier was raised to 20s in this session only because
those three files were read together and the pattern became visible.

Note the second file's finding is why widening only the integration tier would
have been an incomplete fix: the *unit* suite has AST-walking ratchets at ~3.4s,
so the 5s ceiling had a load-dependent margin there too.

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
- **A recurring workaround is a signal to read the earlier write-ups, not to add
  another.** Three learning files independently named this root cause and each
  worked around it. Before writing a learning file about tooling friction, grep
  `plan/incoming/learnings/` for the same symptom — if it is already there, the
  finding is not the symptom, it is that nobody fixed the cause.

Related: [[20260812-cs-hypercube-premise-was-wrong]]

**Promoted**: 2026-08-17 — captured in docs/reference/codebase/TESTING.md (integration timeout tier — prior session update).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
