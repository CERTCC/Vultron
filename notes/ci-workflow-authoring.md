---
title: CI and GitHub Actions Workflow Authoring Pitfalls
status: active
kind: guidance
description: >
  Pitfalls when writing or reading GitHub Actions workflows and the YAML that
  drives them: PyYAML's bare `on:` key, why a split test job derives its last
  part from the other parts' claims, matrix booleans coerced to strings,
  `actionlint` and block-scalar indentation, single-quoted apostrophes, the
  mandatory `notify-failure` wiring and its one-job-per-label rule, the
  `timeout-minutes` every job needs and the reusable-workflow exemption, why an
  automated find-or-file lookup must not go through the search index, why a
  `GITHUB_TOKEN`-raised event never triggers another workflow, why a script
  must use the spellings macOS's bash 3.2 understands, why a bot-filed issue
  gets a theme but no Epic parent, why an artifact name needs the run attempt,
  why a GitHub write is retried and a label swap is split, how to read a red CI
  job correctly, and why a new pull-request step must be mirrored locally or
  excluded with a reason.
related_notes:
  - notes/testing-pitfalls.md
  - notes/demo-ci-invariants.md
  - notes/demo-ci-scenario-coverage.md
  - notes/demo-ci-diagnostics.md
  - notes/git-workflow-pitfalls.md
  - notes/lint-tooling.md
related_specs:
  - specs/ci-security.yaml
  - specs/demo-ci.yaml
  - specs/parallel-development.yaml
  - specs/testability.yaml
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

## A New Pull-Request Step Is Mirrored Locally or Excluded With a Reason

`prepush-ci-mirror` runs every step a `pull_request` run executes, before each
push. A step added to a pull-request workflow, or to a local composite action
one calls, fails `test/ci/test_prepush_ci_mirror_parity.py` until it has an
entry in `vultron/metadata/planning/ci_mirror/_registry.py`. Add a
`MirrorCheck`, which runs the step's own `run:` script when it needs no GitHub
expression. Or add an `EXCLUSIONS` entry saying why it cannot run locally.
Without that entry the mirror would silently fall behind CI, the gap it closes
(PAD-18-022, ADR-0173).

## Push-to-`main` and Scheduled Workflows MUST Wire `notify-failure`

Any workflow that triggers on `push: branches: [main]` or on `schedule:` MUST end
with the `.github/actions/notify-failure` composite action, or failures on `main`
and unattended runs go unseen. It needs two steps: one on failure (file or update
a `ci:main-failure` issue, CISEC-05-001) and one on success (close it,
CISEC-05-002).

Only one job per workflow runs that pair. The close step closes every open issue
carrying the label, so a passing job closes the issue a sibling job just filed.
When several jobs can run in the same run, the pair moves to a final `notify` job
that `needs:` all of them and keys on `needs.*.result`, as `python-app.yml` does
(CISEC-05-012, CISEC-05-013).

The job that runs the pair MUST hold `issues: write` (CISEC-02-002), or the
action's issue calls fail with 403. Grant it on the aggregate `notify` job and
keep the root at `contents: read`, as `python-app.yml` does; a single-job
workflow may grant it at the root instead.

## Every Job Needs `timeout-minutes`, Except a Reusable-Workflow Call

Every job in every workflow MUST declare `timeout-minutes`, set well above its
observed run time (TB-14-006). An uncapped job that hangs holds a runner for
GitHub's six-hour default and reads as `cancelled`, not failed; a scheduled or
issue-triggered job hangs unseen. A step-level cap does not cover the job's
other steps, so a capped step still needs a job cap.

A job that calls a reusable workflow (`uses: ./.github/workflows/...`) cannot
carry `timeout-minutes`; GitHub rejects the key there. Cap the called
workflow's jobs instead. `test/metadata/test_gate_ceiling.py` enforces both.

## A Split Test Job Derives Its Last Part From the Others' Claims

The `test` job of `python-app.yml` runs the suite as matrix parts, each over a
slice of `test/`. Give each named part the paths it claims, and make the last
part select `test` while ignoring exactly those paths — never a fourth list of
directories (TB-11-002). Parts that each name their own paths drop a new test
directory in silence: no part selects it, every part is green, and nothing ran
it. `test/ci/test_python_app_test_parts.py` compares the ignores with the
claims, so a claim without its ignore (the directory runs twice) and an ignore
without its claim (it never runs) both fail.

Keep the parts inside one matrix job: `build` and `notify` reach all of them
through `needs: test`, while a part promoted to its own job id is one a
`needs:` list can omit (TB-11-003). Set `fail-fast: false`, or the first red
part cancels its siblings and a round reports one failure at a time. Rebalance
the parts from the durations CI reports, not from collected test counts — a
count is a first estimate, and the slowest part sets the round's length.

Two consequences land outside the workflow. A merge gate that looks for the
test result by name must match the **prefix** and require every declared part
(`verify-ci-gate.sh`): an exact name finds nothing, and a prefix with no count
reads one green part as a whole suite. And no test may assert over the whole
collection, because each part is its own session —
[testing-pitfalls](testing-pitfalls.md) § "A Test MUST Not Assert Over the
Whole Collection".

## A Find-or-File Lookup Must Not Use the Search Index

A step that files an issue only when none is open must find the open one through
the list-issues REST endpoint (`gh api "repos/$REPO/issues?labels=a,b"`), never
`gh issue list --label` or `gh search`. Both run a search query, and the search
index lags: it once returned nothing while a tracker was open, and a second one
was filed (#5105). Read the result through a command substitution, not
`mapfile < <(...)`, so an API error fails the step under `set -e` instead of
reading as "none open" (CISEC-05-011).

## Events Raised With `GITHUB_TOKEN` Never Trigger Other Workflows

GitHub does not dispatch events a workflow raises with its own `GITHUB_TOKEN`
(filing an issue, adding a label, pushing a commit) to other workflows, to
prevent recursion. So a bot-filed issue cannot be typed by labelling it and
waiting for `label-to-issue-type.yml`, and `gh issue create` cannot set a type.
A workflow that needs a typed issue calls
`.github/scripts/ensure-issue-type.sh <repo> <issue> <type>` on both its create
and update arms. The script resolves the type by name, applies it with
`updateIssue`, leaves a typed issue alone, and fails the step when the type does
not exist (CISEC-05-017 to CISEC-05-019). `notify-failure` and
`demo-recordings.yml` use it; never copy its body into a workflow.

## A Script Runs On The Host's bash, Which May Be 3.2

A `.github/scripts/*.sh` or `.agents/skills/**/*.sh` runs with the first `bash`
on `PATH`, and macOS still ships bash 3.2, so a bash 4 builtin exits 127 on a
contributor's host while the Linux runners stay green — the gate is then red
for a reason the diff cannot cause, which is how a real failure gets read past
([testing-pitfalls](testing-pitfalls.md) § "A Harness That Fails For The
Environment Hides Real Failures", #5698). Write the 3.2 spelling:

| Instead of | Write |
|---|---|
| `mapfile -t a < <(cmd)` | `out=$(cmd)`, then one `IFS= read -r` per field |
| `declare -A m` on numeric keys | `declare -a m` — an indexed array is sparse |
| `declare -A m` on text keys | parallel arrays, or a `case` lookup |
| `"${a[@]}"` on a maybe-empty array | `${a[@]+"${a[@]}"}` (`set -u`, pre-4.4) |
| `${v^^}` | `tr '[:lower:]' '[:upper:]'` |
| `[[ -v name ]]` | `[ -n "${name+set}" ]` |

The command-substitution form is also the one `set -e` can see: a process
substitution swallows the failure of the command inside it (§ "A Find-or-File
Lookup Must Not Use the Search Index", CISEC-05-011).
`test/ci/test_shell_script_portability.py` scans every tracked `*.sh`; it
cannot see the empty-array case, which is a question about the script's logic
rather than a construct.

## A Bot-Filed Issue Gets a Theme From the Filer, and No Parent

A workflow that files an issue MUST give it one `theme:` label and a
`Theme: <label> — <outcome>` line, and MUST NOT give it a parent (PAD-02-026,
PAD-02-027). Call `.github/scripts/ensure-issue-triage.sh` on both arms, after
`ensure-issue-type.sh`; it never overrides a theme a person set (PAD-02-029).
Reason: a workflow cannot calve an Epic, and a fixed Epic number (a literal or a
repository variable) breaks the step whenever that Epic closes, is rethemed or
split, or reaches GitHub's 100-sub-issue cap. The issue starts untriaged
(PAD-01-007), and `theme-fit` lists it for routing without counting it as a
finding (#5450).

## An Artifact a Later Job Downloads Needs the Run Attempt in Its Name

A re-run attempt uploads its artifact beside the earlier attempt's, under the same
name, and a download by that name can return the stale one: a re-run Invariant
Harness judged the first attempt's case log and failed a demo that had passed
(#4577). Put `${{ github.run_attempt }}` in the name, and have the consumer pick
the highest attempt not later than its own, since a consumer re-run alone keeps
its producer's earlier attempt (DEMOCI-04-008, DEMOCI-04-009).

## Retry a GitHub Write, and Never Swap Labels in One Call

GitHub sometimes answers a call with a server error that a retry clears. Wrap
each repeatable call in `retry` from `.github/scripts/retry.sh`, which is bounded.
Split a label swap into an add, then the removals: one `gh pr edit --add-label X
--remove-label Y` once removed Y, failed before adding X, and left the PR with no
size label (#4524).

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
