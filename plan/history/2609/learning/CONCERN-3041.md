---
source: CONCERN-3041
timestamp: '2026-09-24T00:10:10.520643+00:00'
title: Demo integration marker and timeout tier
type: learning
---

**Resolved**: 2026-09-24 — premise disproved, recharacterized; implementation
tracked in #3603, #3604, #3605.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3608>.

Notes: `notes/testing-pitfalls.md`.

## What the investigation found

The concern's stated problem does not exist. `test/demo/conftest.py` applies
`pytest.mark.integration` to every item collected from `test/demo/` via a
`pytest_collection_modifyitems` hook, so a per-module `pytestmark` declaration
(AC-1) would be a no-op duplicating the hook. A `trylast` probe measured 1274
demo tests at `integration=True, timeout=60`, plus two explicit per-test
overrides (180 s, 10 s), and **zero** at the 30 s unit ceiling.

The dates show the premise was already false when the concern was filed: the
directory hook landed 2026-04-13 (`f95ecfd2e`) and the 60 s integration tier
2026-08-12 (`527200bb4`); the concern was filed 2026-09-02.

The sweep that produced "59 of 63 modules" counted **declarations** in module
source, which is not what pytest ends up with. This measurement error is itself
the durable lesson, recorded in `notes/testing-pitfalls.md`.

## The real defect underneath

The symptom the concern was reaching for is genuine but sits one level down:
`timeout_method = "thread"` kills the whole pytest process, so a trip yields no
summary line and every later test goes unrun. It entered in `85bf2743a` (#528)
with no stated rationale, and six separate investigations (ISSUE-1925,
ISSUE-1988, ISSUE-2086, ISSUE-2237, #2762, #3576) then re-diagnosed the same
missing-signal symptom and tuned ceilings around it. Raising a ceiling lowers
the frequency of signal loss, never its severity.

Measured with a throwaway probe outside the repo: under `thread` the process is
killed with no summary; under `signal` the run reports
`2 failed, 2 passed in 2.02s` with both failures named. A full-suite run on
`cdb35d428` under `--timeout-method=signal` returned exit 0.

Named-but-unretired risk: SIGALRM raising while a test holds the module-level
`py_trees` blackboard `RLock` is a deadlock mode `thread` does not have, and the
green happy-path run does not exercise it. That evaluation is #3603.

## Decision recorded

Spec amendment plus notes, no ADR (user decision). Stale timeout MUSTs found in
the test-behavior spec — TB-12-006 (`timeout = 5`), TB-12-005 (MUST redesign
"rather than raising the timeout", which forbids what #2270 did), TB-12-003 (BT
tests < 5 s), TB-13-004 (full suite < 90 s; actual ~9 min) — are retired
under #3605.

---

## Original concern body

`pyproject.toml` sets a 30 s unit-tier `timeout` with `timeout_method = "thread"`.
`test/conftest.py` widens that to `INTEGRATION_TIMEOUT_SECONDS = 60` **only** for
tests carrying `@pytest.mark.integration`.

A sweep of `test/demo/` finds that **59 of 63 test modules carry no
`integration` marker**, despite driving the full HTTP stack in-process. They are
therefore running under a ceiling meant for unit tests.

Because `timeout_method = "thread"` cannot cancel a single test, a timeout kills
the entire pytest process. One unmarked demo test crossing 30 s destroys the
result signal for the whole session — no summary line, no other results.

Observed during ISSUE-2762: `uv run pytest -m ""` aborted at ~69 % with a
`+++ Timeout +++` dump naming `test/demo/test_invite_actor_demo.py::test_demo`,
hung in `setup_initialized_case` → `post_to_inbox_and_wait`. Alone: 2 passed in
9.19 s. Whole demo tier: 1240 passed, exit 0. Unit tier: 8017 passed, exit 0.

Acceptance criteria as filed: AC-1 every `test/demo/` module carries a
module-level `pytestmark`; AC-2 a guard prevents a new unmarked module from
inheriting the unit ceiling; AC-3 `uv run pytest -m ""` completes with a summary
line rather than a process-level abort.

Provenance: recovered from
`plan/incoming/learnings/20260901-2762-unmarked-demo-test-timeout-tier.md`
during the 2026-09-02 learnings-queue audit.
