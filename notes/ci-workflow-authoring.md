---
title: CI and GitHub Actions Workflow Authoring Pitfalls
status: active
description: >
  Pitfalls when writing or reading GitHub Actions workflows and the YAML that
  drives them: PyYAML's bare `on:` key, matrix booleans coerced to strings,
  `actionlint` and block-scalar indentation, single-quoted apostrophes, the
  mandatory `notify-failure` wiring, and how to read a red CI job correctly.
related_notes:
  - notes/demo-ci-invariants.md
  - notes/demo-ci-scenario-coverage.md
  - notes/demo-ci-diagnostics.md
  - notes/git-workflow-pitfalls.md
related_specs:
  - specs/ci-security.yaml
  - specs/demo-ci.yaml
---

# CI and GitHub Actions Workflow Authoring Pitfalls

Migrated out of the root `AGENTS.md` pitfalls list. Root keeps one-line
pointers; the full write-ups live here.

## A Red CI Job Is Not Evidence That Its Assertions Ran

A job that dies in an earlier step (artifact download, dependency setup,
container build) never reaches pytest, so its red status says nothing about what
the tests assert. Open the log and identify the failing *step* before concluding
a test is wrong, unsatisfiable, or "can never pass". A permanently-red
`<scenario> Invariant Harness` job was misread this way in CONCERN-2243: it
failed at `actions/download-artifact` on every run, so the assertion blamed for
the failure had never once executed. Note the inverse trap too — an all-skipped
pytest run exits 0 and reports **green** while checking nothing.

See [notes/demo-ci-invariants.md](demo-ci-invariants.md) § "Reading a Red
Invariant Harness Job".

Source: CONCERN-2243

## New Push-to-`main` or Scheduled Workflows MUST Wire the `notify-failure` Composite Action

Any workflow that triggers on `push: branches: [main]` or on `schedule:` MUST
include `.github/actions/notify-failure` as a final step (CISEC-05-001). Without
it, failures on `main` or unattended scheduled runs go undetected until someone
manually audits the Actions tab. Two separate steps are required: one on failure
(file/update a `ci:main-failure` issue, CISEC-05-001) and one on success (close
the issue for recovery visibility, CISEC-05-002).

Source: CONCERN-2132

## PyYAML Parses Bare `on:` Mapping Key as Python `True`

PyYAML (YAML 1.1) resolves the bare token `on` as boolean `True` when it appears
as a mapping key. A GitHub Actions workflow file starting with `on:` is loaded by
`yaml.safe_load()` as `{True: {...}, 'name': '...', 'jobs': {...}}` — NOT
`{'on': {...}}`. Any test or tool that reads workflow YAML and queries the
trigger block must use `wf_data.get(True, wf_data.get("on", {}))`. If you use
only `wf_data.get("on", {})` the result is always `{}` and any
`pytest.mark.parametrize` fixture over it silently produces zero cases — all
parametrized tests SKIP instead of FAIL.

Source: ISSUE-2184

## GHA Matrix Boolean Fields Fail Differently at Job-Level vs. Step-Level `if:`

Two distinct failure modes when a boolean field from the matrix (e.g.
`full_suite_only: false`) is referenced in a GitHub Actions `if:` expression:

1. **Job-level `if:`**: the `matrix` context does not exist yet — GitHub
   evaluates job-level `if:` conditions *before* expanding the matrix. The
   workflow is rejected with a startup failure: zero jobs scheduled, no logs, no
   per-job status, and the run name is reported as the file path. The failure
   reads as noise, not a regression (DEMOCI-06-004, ISSUE-2118).
2. **Step-level `if:`**: the `matrix` context IS available, but GitHub coerces
   JSON boolean `false` to the string `"false"`. The comparison
   `matrix.full_suite_only == false` then always evaluates to `false` because a
   string never equals a boolean, silently defeating the intended filter
   (CONCERN-2327).

Fix for both: resolve the boolean filter *before* matrix expansion using a
dedicated `scenarios` job that calls `jq 'select(.full_suite_only == false)'` on
the JSON source and exposes a filtered matrix as a job output. Both downstream
jobs expand `fromJSON()` of that output — the boolean comparison lives in `jq`,
which understands JSON natively. See DEMOCI-06-004, DEMOCI-06-007, DEMOCI-06-008
and [notes/demo-ci-scenario-coverage.md](demo-ci-scenario-coverage.md).

Sources: CONCERN-2327, ISSUE-2118

## GH Actions `python3 -c` Multi-Line Block Fails `actionlint`

When embedding multi-line Python in a `run: |` block via `python3 -c "..."`, all
Python lines must stay within the block's indentation level. A line at a lower
indentation than the block's first content line terminates the YAML block scalar
early; `actionlint` then fails with `could not find expected ':'`. Fix: collapse
to a semicolon-separated one-liner, or write to a file in a prior step.

Source: ISSUE-2312

## YAML Single-Quoted String: Double Apostrophes or Use `>-`

Inside a single-quoted YAML value, apostrophes must be escaped as `''` (two
single quotes). A bare `'s` (possessive) or contraction terminates the string
early; the parser fails with an opaque "did not find expected key" error
pointing at the column of the apostrophe, not at a syntax-level message.
Alternatively, convert the field to a `>-` block scalar and use apostrophes
freely.

Source: ISSUE-2393
