---
title: CI and GitHub Actions Workflow Authoring Pitfalls
status: active
kind: guidance
description: >
  Pitfalls when writing or reading GitHub Actions workflows and the YAML that
  drives them: PyYAML's bare `on:` key, matrix booleans coerced to strings,
  `actionlint` and block-scalar indentation, single-quoted apostrophes, the
  mandatory `notify-failure` wiring and its one-job-per-label rule, why a `GITHUB_TOKEN`-raised event never
  triggers another workflow, and how to read a red CI job correctly.
related_notes:
  - notes/demo-ci-invariants.md
  - notes/demo-ci-scenario-coverage.md
  - notes/demo-ci-diagnostics.md
  - notes/git-workflow-pitfalls.md
  - notes/lint-tooling.md
related_specs:
  - specs/ci-security.yaml
  - specs/demo-ci.yaml
---

# CI and GitHub Actions Workflow Authoring Pitfalls

## A Red CI Job Is Not Evidence That Its Assertions Ran

A job that dies in an earlier step (artifact download, dependency setup,
container build) never reaches pytest, so its red status says nothing about what
the tests assert. Open the log and find the failing *step* before concluding a
test is wrong or "can never pass" (CONCERN-2243). The inverse trap: an
all-skipped pytest run exits 0 and reports **green** while checking nothing.
See [notes/demo-ci-invariants.md](demo-ci-invariants.md) for reading a red
Invariant Harness job.

## Push-to-`main` and Scheduled Workflows MUST Wire `notify-failure`

Any workflow that triggers on `push: branches: [main]` or on `schedule:` MUST end
with the `.github/actions/notify-failure` composite action, or failures on `main`
and unattended runs go unseen. It needs two steps: one on failure (file or update
a `ci:main-failure` issue, CISEC-05-001) and one on success (close it,
CISEC-05-002).

Only one job per workflow runs that pair. The close step closes every open issue
carrying the label, so a passing job closes the issue a sibling job just filed.
A workflow with several jobs adds a final `notify` job that `needs:` all of them
and keys on `needs.*.result`, as `python-app.yml` does (CISEC-05-003, #4229).

The workflow MUST grant `issues: write` (CISEC-02-002). A root-level
`permissions: contents: read` block MUST become a map that also lists
`issues: write`, or the action's issue calls fail with 403.

## Events Raised With `GITHUB_TOKEN` Never Trigger Other Workflows

GitHub does not dispatch events a workflow raises with its own `GITHUB_TOKEN`
(filing an issue, adding a label, pushing a commit) to other workflows, to
prevent recursion. So a bot-filed issue cannot be typed by labelling it and
waiting for `label-to-issue-type.yml`, and `gh issue create` cannot set a type.
A workflow that needs a typed issue resolves the type's node ID by name through
the `issueTypes` GraphQL field and applies it with `updateIssue` itself, failing
the step if the type does not exist (CISEC-05-007); `notify-failure` does this.

## PyYAML Parses a Bare `on:` Key as `True`

PyYAML (YAML 1.1) loads a workflow's bare `on:` key as the boolean `True`, so
`wf_data.get("on", {})` is always `{}`, and a `parametrize` over it yields zero
cases: the tests SKIP instead of FAIL. Read triggers through
`test/ci/_workflows.py::triggers()`, which checks both keys (ISSUE-2184).

## Matrix Booleans Fail Differently in Job-Level and Step-Level `if:`

- **Job-level `if:`** is evaluated before the matrix expands, so `matrix` does
  not exist. The workflow fails at startup with zero jobs and no logs, which
  reads as noise rather than a regression (DEMOCI-06-004).
- **Step-level `if:`** sees `matrix`, but GitHub coerces JSON `false` to the
  string `"false"`, so `matrix.full_suite_only == false` is always false and the
  filter silently does nothing (CONCERN-2327).

Fix for both: filter before matrix expansion. The `scenarios` job in
`demo-integration.yml` runs `jq 'select(.full_suite_only == false)'` over
`.github/demo-scenarios.json` and exposes the result as a job output that the
downstream jobs expand with `fromJSON()` (DEMOCI-06-007, DEMOCI-06-008).

## Multi-Line `python3 -c` in a `run: |` Block Fails `actionlint`

A Python line indented less than the block's first content line ends the YAML
block scalar early, and `actionlint` fails with `could not find expected ':'`.
Collapse the script to a semicolon-separated one-liner, or write it to a file in
a prior step (ISSUE-2312).

## Apostrophes in a Single-Quoted YAML String

Inside a single-quoted YAML value an apostrophe must be doubled (`''`). A bare
`'s` ends the string, and the parser reports an opaque "did not find expected
key" at the apostrophe's column. Double it, or use a `>-` block scalar
(ISSUE-2393).
