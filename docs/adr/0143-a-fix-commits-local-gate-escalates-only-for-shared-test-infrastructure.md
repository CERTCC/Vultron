---
status: proposed
date: 2026-10-16
created: 2026-10-16
updated: 2026-10-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0126; ADR-0138; specs/parallel-development.yaml PAD-18;
  agent session transcripts 2026-10-07 to 2026-10-16
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0126-ci-is-the-full-suite-authority-after-the-first-push.md
---

# A Fix Commit's Local Gate Escalates Only for Shared Test Infrastructure

## Context and Problem Statement

ADR-0126 made CI the full-suite authority after a Pull Request's first push and gated each later fix commit with a targeted test set.
It kept one exception: the gate escalated to the full local suite when the branch diff touched an integration-bearing layer (`vultron/core/behaviors/`, `vultron/core/use_cases/`, `vultron/adapters/`, `vultron/demo/`, the extractor, `integration_tests/`).
Those layers are where most code changes land, so the exception became the rule: 23 of the 40 Pull Requests merged before 2026-10-16 touched one of them, and for each of those every fix commit, however small, ran the full suite locally.

The cost was measured from agent session transcripts covering 2026-10-07 to 2026-10-16.
A local `pytest -m ""` run on a 2-CPU slot took a median of about nine minutes and up to twenty under load, while CI ran the same command on the push in six to nine.
`pr-execute` recorded about two full local runs per code Pull Request on top of the one before the first push.
Sixty runs passed the ten-minute limit on a foreground tool call, were moved to the background, and were then polled with `sleep`, which is where most of the agents' measured waiting went and where crashed runs went unnoticed.

Of the 47 full local runs in that window, 12 were red.
Nearly every red run failed in `test/architecture/` or `test/metadata/`: ratchets, generated-file sync checks and size limits, which read the tree rather than import a changed symbol.
None found a failure that CI's run on the next push would not have found sooner.

The question this record settles: after the first push, which changes justify a full local run, and what must the targeted set always include?

## Decision Drivers

- A local run after the first push is worth its cost only when it catches something before CI would (ADR-0126). A full local run that is slower than CI's never does.
- The 2-CPU slot cap made the full suite slower than the tool-call limit, so a full run also broke the agent's ability to see its own exit code.
- The tests that actually failed locally are cheap to always run: `test/architecture/` and `test/metadata/` together take about three minutes on a 2-CPU slot.
- Never merge on red stays non-negotiable. Anything the targeted set misses still fails CI, which runs the full suite on every push.

## Considered Options

- **Keep the integration-bearing escalation and make the suite faster** — larger slots only.
- **Escalate only for shared test infrastructure, and always select `test/architecture/` and `test/metadata/`** — gate an integration-bearing change by its importers like any other change.
- **Never run tests locally after the first push** — linters only, CI for everything else.

## Decision Outcome

Chosen option: **escalate only for shared test infrastructure, and always select `test/architecture/` and `test/metadata/`**, because it removes the full local run that repeated CI's on most fix commits while keeping, locally, the cheap directories where nearly every red local run failed.

The fix-commit gate escalates to the full suite only for files whose effect no import index can bound: `conftest.py`, test fixtures, factories, helpers and data files outside the always-selected directories, `pyproject.toml`, `uv.lock`, and `vultron/__init__.py` (PAD-18-003).
A change to any other path, an integration-bearing layer included, is gated by its importers and mirror tests with the integration marker enabled, plus `test/architecture/` and `test/metadata/` (PAD-18-002).
A fix for a CI failure in a test outside a targeted set adds that test to the gate instead of running the full suite.

Separately, worktree slots may burst to more CPUs than their fair share when the host is idle, so the full run that does remain, before the first push, finishes inside the tool-call limit (`start-dev.sh`).

### Consequences

- Good, because a fix commit on a code Pull Request costs minutes instead of a full local suite run, and the full run it used to make is the one CI makes anyway, sooner.
- Good, because the tests that caught real failures locally still run on every gate.
- Bad, because a fix that breaks an integration test that does not import the changed module is caught by CI, one round trip later, instead of locally. That counts against `pr-execute`'s iteration cap.

The "Bad" item is the deliberate trade.
A future reader who sees a red CI run that a full local run would have caught should check whether it was a one-off before restoring the escalation: restoring it puts a full local run back on most fix commits.

## Validation

PAD-18-002 and PAD-18-003 in `specs/parallel-development.yaml` carry the requirements, and `test/metadata/test_targeted_tests.py` covers the escalation rule and the always-selected directories.
PAD-18-007's velocity report checks the decision against data: the failed CI runs per Pull Request should not rise materially while local suite runs and open-to-merge time fall.

## Pros and Cons of the Options

### Keep the integration-bearing escalation and make the suite faster

- Good, because local integration coverage on fix commits is unchanged.
- Bad, because a faster full run is still a repeat of CI's, and the number of repeats, not their length, is what multiplies (ADR-0126).
- Neutral, because larger slots are worth having anyway; this record adopts them alongside the chosen option.

### Escalate only for shared test infrastructure, and always select `test/architecture/` and `test/metadata/`

- Good, because it removes the full local run from most fix commits while keeping the cheap directories where local failures were found.
- Bad, because it accepts the CI round trip described under Consequences.

### Never run tests locally after the first push

- Good, because it is the fastest local loop.
- Bad, because a broken fix then always costs a CI round trip, and the targeted set catches most of them in a few minutes.

## More Information

ADR-0126 chose the targeted gate and carried the integration-bearing escalation forward from `pr-execute`'s `needs_integration_tests` rule; this record removes that escalation and leaves the rest of ADR-0126 in force.
ADR-0138 had already removed it from the gate after a conflict merge.

Generated spec requirements: `specs/parallel-development.yaml` PAD-18-002 and PAD-18-003.
