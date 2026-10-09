---
name: pr-execute
description: >
  Execution phase of the PR review pipeline. Reads .claude/pr-{number}-triage.json,
  applies all FAIL/IMPROVE fixes inline, remediates CI failures, syncs the branch
  with its base and resolves merge conflicts, files GitHub issues for out-of-scope
  findings, resolves review thread comments, and writes
  .claude/pr-{number}-execute.json. Use after /pr-triage, or as the second step
  of /pr-ship.
---

# Skill: PR Execute

## Purpose

Execute consumes the closed finding list from `pr-triage` and processes it in
one batch pass. No new discovery happens here. The finding set is fixed at the
start; execute either resolves each item or records why it was skipped.

Execute's exit criterion is **CI green**: it does not hand off to pr-verify until
the branch is conflict-free against its base, the local gate passes, and all CI
checks have completed successfully (or the 4-iteration cap is reached).

After a PR's first push, CI is the full-suite authority (ADR-0126). Execute
therefore merges the base only when the PR conflicts or the base touched the
PR's files (PAD-18-004), and gates each push with the linters plus the
targeted test set for the branch diff, not the full suite (PAD-18-002).

**One exception to "no new discovery"**: the CI loop (Phase 5) re-reads CI state
and merge state from live sources rather than trusting triage's snapshots. CI
failures and conflicts are moving targets — execute's own fixes can create them,
and other PRs can land on the base branch mid-run.

## Quick Start

```bash
# Execute against the current branch's open PR
/pr-execute

# Execute against a specific PR number
/pr-execute 1234
```

## Prerequisites

`.claude/pr-{number}-triage.json` must exist. If absent, stop immediately:

```text
❌ No triage artifact found for PR #N.
Run /pr-triage first (or /pr-ship to run the full pipeline).
```

## Workflow

### Phase 1 — Load Triage Artifact

1. Detect PR number (current branch or explicit argument).
2. Read `.claude/pr-{number}-triage.json`.
3. Validate `schema_version == "1.0"`. If mismatch, stop and report.
4. Extract `pr_metadata.domains` and invoke `deepen-context` with those hints
   to load the same domain context that triage used.
5. Note `pr_metadata.needs_integration_tests`. It is informational: Phase 5's
   gate does not read it, because `targeted-tests` escalates to the full suite
   on the same integration-bearing paths (PAD-18-003).
6. Note `pr_metadata.base_ref` — Phase 5 syncs against this branch, not
   necessarily `main`.

### Phase 2 — Apply fix-now Fixes

For each finding where `decision_outcome` is `fix-now` and `severity` is `FAIL`
or `IMPROVE`:

> Note: findings with `severity: NEW-ISSUE` are handled exclusively in Phase 3,
> regardless of their `decision_outcome`. Do not process them here. Phase 9
> docs-currency findings are handled in Phase 3b.

1. Apply the fix (edit files as needed).
2. Do not commit yet — batch all fixes, then commit once at the end of this phase.
3. After all fixes are applied: `uv run ruff format` then commit:

   ```text
   fix(pr-execute): address <N> findings from triage

   <bullet per finding: phase-name — short description>
   ```

4. Record `commit_ref` (short SHA) for each finding addressed in this commit.

**Do not push yet.** All pushes happen inside the CI loop (Phase 5) so that
every push includes any merge the base called for and passes the local gate
first.

### Phase 3 — Handle NEW-ISSUE Findings

For each finding with `severity: NEW-ISSUE`. **Filing a record is not the same
as deferring the work** — the default is to fix now and let the PR close the
issue. See `.claude/skills/shared/completeness-doctrine.md` § "Filing Is Not
Deferring" and "The Two Gates".

**`fix-now-file`** (an "also" excursion you fix now):

1. File a GitHub issue via `manage-github-issue` capturing the finding, with
   `--opened-as excursion`.
2. Add the issue to Project #24: `bash .agents/skills/shared/add-to-project.sh <N>`.
3. **Fix it in this PR** (fold into the Phase 2 batch). Add `- Closes #N` to the
   PR body and a one-line "why" in the Changes section (see `pr-body-guide.md`).
4. Record `outcome: fixed` with the `issue_number`.

**`defer-ask`** (Gate 1 — second-order work genuinely too big to finish now):

1. File a GitHub issue via `manage-github-issue` with `--opened-as deferred`
   and add it to Project #24.
2. Post the deferral-ask (see "No User Prompts (Except Two)" below): describe
   the remainder in plain language with a **measured remainder** (what you did,
   what concretely remains, the ratio) — not an attempt count.
3. **On explicit approval**: record `outcome: deferred-ask` with `issue_number`
   and leave the work for the filed issue.
4. **On silence or no approval**: DEFER is unavailable. Fix it now (fold into
   the Phase 2 batch), `- Closes #N`, and record `outcome: fixed`. If it cannot
   be finished, hold the PR: record `outcome: halted`, mark the PR draft/blocked
   with the unfinished item stated, and stop. Never leave the work on the filed
   issue and let the PR proceed. Silence is never consent to defer.

Only *second-order* findings are eligible for `defer-ask`. A first-order
finding is never deferred — fix it.

**`inversion-halt`** (Gate 2 — the work inverts an issue/spec/ADR premise):

1. Do **not** file autonomously and do **not** act on the new premise.
2. Post the inversion-ask (see below): explain the overturned premise in plain
   language and ask if/what to file.
3. **On response**: act as directed (file and/or fix per the human's call).
4. **On silence**: record `outcome: halted`, mark the PR draft/blocked, and
   stop. An inversion is a circuit breaker.

**Pre-existing findings are not exempt (BW-07-009).** A finding in a file this
PR did not touch still gets a `type:Bug` or `type:Concern` issue here, before
the session ends. There is no advisory tier: posting it only as an
`[ADVISORY]` PR comment, or describing it in a `plan/incoming/learnings/`
file, does not count as tracking it — neither can be assigned, scheduled, or
closed. Nor does citing the PR that surfaced it: a merged PR number is not a
tracking reference. In the 2026-09-02 audit, nearly every finding parked this way
was eventually re-found and filed by a later session — the deferral bought
nothing but the rediscovery cost, and four findings fell through entirely.

### Phase 3b — Refresh the `Docs:` Line

Execute's fix commits can change behavior that `docs/` describes, which makes
the PR body's `Docs:` line stale (PD-03-007, PD-03-008). After Phases 2–3 and
before the CI loop:

1. Diff the fix commits this run made, and answer `check-docs-sync` Q1 and
   Q2 against that diff: which `docs/` pages describe what those commits
   changed. If triage flagged the `Docs:` line as missing or placeholder,
   answer them against the whole PR diff (`git diff origin/<base_ref>...HEAD`)
   instead — the author never recorded a determination. Phase 9
   docs-currency findings from triage already name their pages; this phase
   owns them, and Phase 2 skips them.
2. For each affected page, apply the update the way `check-docs-sync` Step 3
   does (`lint-docs` gate, then `build-docs`), and commit it as
   `docs: sync docs/ for PR #<number>`.
3. Rewrite the PR body's `Docs:` line so it lists every page the PR now
   updates, in the forms of `.agents/skills/shared/pr-body-guide.md`
   § "Implementation PR rules", then `gh pr edit <number> --body-file <file>`.
   When the fix commits touch no described behavior, leave the line as written
   unless triage flagged it.
4. Record the result in the artifact's `docs_refresh` block (see
   [REFERENCE.md](REFERENCE.md) § "Execute Artifact Schema").
5. Add a `results` entry for every Phase 9 docs-currency finding this phase
   owns, so `results` still covers every triage finding. A page update gets
   `outcome: fixed` with the docs commit as `commit_ref`. A fix that only
   rewrote the `Docs:` line (for example a placeholder replaced by
   `Docs: no docs impact — …`) has no commit: record `commit_ref: null` and
   `fix_kind: "pr-body"`, and `pr-verify` checks it against the live body.

Phase 5's CI-fix commits land after this phase. Before Phase 6 writes the
artifact, repeat steps 1–3 for any CI-fix commit, add it to
`docs_refresh.fix_commits_checked`, and append any further docs commit to
`docs_refresh.docs_commit_refs`.

### Phase 4 — Resolve Review Thread Comments

For each unresolved review comment on the PR (fetched via
`gh api repos/CERTCC/Vultron/pulls/<number>/comments`):

Match each comment to the finding(s) it corresponds to. Then per
[REFERENCE.md](REFERENCE.md) § "Comment Resolution":

- ✅ Fully addressed → resolve with commit reference
- ⚠️ Partially addressed → reply explaining why; leave for reviewer to close
- ❌ Cannot address → reply explaining why; reference any filed issue

Do not mark a comment resolved unless the code actually addresses it.

### Phase 5 — CI Loop

This phase owns syncing, testing, pushing, and CI wait. It loops until CI is
green or the cap is reached. **Maximum 4 iterations.** One iteration = one
Sync (when needed) → Test → Push → Wait cycle.

#### Step 1 — Apply CI fixes

*Iteration 1*: apply any CI-failure findings from the triage artifact (triage
Phase 11). Fix lint/type/format failures directly. For test failures, apply Test
Failure Rules from [REFERENCE.md](REFERENCE.md).

*Subsequent iterations*: apply fixes for failures found in the previous
iteration's CI wait result. Fetch logs first:

```bash
gh run list --branch <head_ref> --limit 1
gh run view <run-id> --log-failed
```

**Repeated-failure rule**: if the same CI failure appears in two consecutive
iterations:

1. Apply Test Failure Rules from [REFERENCE.md](REFERENCE.md) to determine
   whether it is pre-existing.
2. Before filing or deferring: assess whether a fix is straightforward and
   context is in hand. If yes, fix it now — a pre-existing failure you can
   resolve is still a failure worth resolving.
3. Only file a bug issue (`--opened-as separate-defect`) and record `outcome: skipped` if the fix is genuinely
   non-trivial or requires design work outside this PR's scope. `skipped` does
   not clear the check: the CI stays red, `final_ci_status` is `"failing"`, and
   `pr-verify` returns `GAPS-FOUND`. "Pre-existing" never makes a red check
   mergeable (`completeness-doctrine.md` § "Never Merge on Red").
4. **Rerun exception.** A failed check may be re-run once only if it is already
   tracked by an open `flaky-test` issue with a reproduction (see
   [REFERENCE.md](REFERENCE.md) § "Flaky Test Dedup"); cite that issue in
   `skip_reason`. A rerun that passes with no such issue is not evidence —
   file the issue with the reproduction (`--opened-as separate-defect`) and
   leave the PR held.
5. **Never bypass a pre-commit hook** (`--no-verify`, `SKIP=`),
   including the spec-lint hook. Fix what the hook reports and re-stage. The
   sole exception is the devcontainer `actionlint` hang
   (`notes/devcontainer-tooling.md`).

Commit CI fixes separately from Phase 2 fixes:

```text
fix(ci): resolve CI failures — <summary>
```

Record `commit_ref` for each CI finding addressed.

#### Step 2 — Sync with base, only when needed

Merge the base into the branch **only** when GitHub reports the PR
`CONFLICTING` or the base changed files this PR also changes (PAD-18-004).
Being behind the base is not by itself a reason to merge: CI tests the PR
merged into its base on every push. Run both checks first:

```bash
git fetch origin <base_ref>
bash .agents/skills/shared/merge-state.sh <number>; ms=$?; echo "merge-state exit: $ms"
PYTHONPATH= uv run targeted-tests --base origin/<base_ref> --overlap; ov=$?; echo "overlap exit: $ov"
```

`targeted-tests --overlap` lists the paths the base changed since the merge
base that this branch also changes, counting uncommitted work. It does not
fetch, so the `git fetch` must come first.

Treat a `merge_state_status` of `DIRTY` in `merge-state.sh`'s JSON as
`CONFLICTING`, whatever its exit code. Then take the first row that matches:

| `merge-state.sh` | `--overlap` | Action |
|---|---|---|
| any | `2` | Setup error (unknown base ref) — stop and report |
| `1` (`CONFLICTING`) | `0` or `1` | Merge — record `merge_reason: "conflicting"` |
| `0` or `2` | `1` (paths listed) | Merge — record `merge_reason: "overlap"` and the listed paths |
| `0` or `2` | `0` (none) | **Do not merge.** Go to Step 3 |

`merge_state.merge_required` is `true` if any iteration merged, and `false` only
when every iteration reached the last row.

`merge-state.sh` exit `2` (`UNKNOWN`, or a `gh pr view` failure) does not
force a merge: a conflict needs a file both sides changed, so the overlap check
already sees it whatever GitHub answered. The live mergeability gate is
`pr-verify`'s, not this step's.

A `mergeStateStatus` of `BEHIND` is not a merge trigger either. GitHub reports
it only when a ruleset requires up-to-date branches, which ADR-0126 found this
repository does not set; record triage's `BEHIND` finding as `outcome: skipped`
with that reason, and let `pr-verify` block on it (PAD-18-005) until a human
decides.

When a merge is called for:

```bash
bash .agents/skills/shared/sync-with-main.sh <base_ref>
```

| Exit | Meaning | Action |
|---|---|---|
| `0` | Already current, or merged cleanly | Continue to Step 3 |
| `1` | Conflicts left in the worktree | Resolve them (see below) |
| `2` | Unexpected error (dirty tree, merge in progress) | Stop and report; do not force anything |

Resolve each conflicted path per [REFERENCE.md](REFERENCE.md) § "Conflict
Resolution Rules". Read both sides before editing. Never resolve by
wholesale `--ours`/`--theirs` on a file you have not read.

```bash
uv run ruff format
git add <resolved files>
git commit --no-edit
```

Verify no markers survived:

```bash
git grep -nE '^(<<<<<<<|>>>>>>>) ' -- . && echo "MARKERS PRESENT — do not push" || echo "clean"
```

**If a conflict cannot be resolved safely** (PAD-11-003 to PAD-11-005), do not
guess and do not push:

1. `bash .agents/skills/shared/sync-with-main.sh --abort`
2. Post a PR comment naming each conflicted path and why its resolution is
   unclear: `gh pr comment <number> --body-file <file>`.
3. `gh pr edit <number> --add-label needs-rebase` — the label name predates
   merge-based syncing; it means "a human must resolve this conflict".
4. Record the merge-state finding as `outcome: skipped` with the conflicted
   paths, set `merge_state.conflict_free: false`, and stop the run after
   Phase 6.

#### Step 3 — Run the local gate

The gate is the linters plus the **targeted test set** for the branch diff
(PAD-18-002), never a bare full-suite run by default. Derive the set from the
branch as it stands now, after any Step 2 merge, so a merge's overlapping and
conflicted files are covered by the same derivation:

```bash
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pyright
git fetch origin <base_ref>
PYTHONPATH= uv run targeted-tests --base origin/<base_ref> > /tmp/targeted-tests.txt; rc=$?; cat /tmp/targeted-tests.txt; echo "exit: $rc"; (exit $rc)
```

Read the first line of `/tmp/targeted-tests.txt`:

- **A test path** — the gate is the targeted set. Paths printed on stderr as
  `no test maps to` are left to CI; that is expected, not an error.
- **`full`** — the branch diff touches shared test infrastructure or an
  integration-bearing path (PAD-18-003); each following line names the path
  and reason. The gate is the full suite with every marker enabled.

Run the command `targeted-tests --pytest` prints for whichever mode it chose.
It carries `-m ""` so integration-marked tests among the selected files are
not deselected by the `addopts` default:

```bash
gate=$(PYTHONPATH= uv run targeted-tests --base origin/<base_ref> --pytest); rc=$?
[ "$rc" -eq 0 ] && { eval "$gate" > /tmp/pytest-gate.log 2>&1; rc=$?; tail -20 /tmp/pytest-gate.log; }; echo "exit: $rc"; (exit $rc)
```

**Escalate yourself when the CI failure being fixed is outside the set.**
`targeted-tests` cannot see CI (PAD-18-003). If the iteration's input includes
a CI test failure whose test file is not one of the paths in
`/tmp/targeted-tests.txt` (and is not under a listed directory), the set
missed something: run the full suite instead.

```bash
uv run pytest -m "" -n auto --tb=short > /tmp/pytest-gate.log 2>&1; rc=$?; tail -20 /tmp/pytest-gate.log; echo "exit: $rc"; (exit $rc)
```

Read the `exit:` line, not just the tail — see `run-tests/SKILL.md` § Constraints.
A piped form would report 0 for a killed run and this step would push it.

**If the tail output is insufficient**, grep or read `/tmp/pytest-gate.log`
— **do not re-run the test suite for more output**.

**Count every gate run** for the execute summary's `Suite runs:` line
(PAD-18-006): a run of the full suite (either escalation) adds one to
`suite_runs.full`; a targeted run adds one to `suite_runs.targeted`. Single-test
re-runs while debugging a failure are not gate runs and are not counted.

If tests fail: fix branch-owned failures per [REFERENCE.md](REFERENCE.md)
§ "Test Failure Rules", commit, then **re-run Step 2's two checks**. Return to
the merge only if they now call for one; otherwise re-run this step's gate
directly. Do not push failing code.

After tests pass, run the xfail ratchet per [REFERENCE.md](REFERENCE.md)
§ "xfail Ratchet".

#### Step 4 — Push

```bash
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)
if [[ "$upstream" == */"<head_ref>" ]]; then
  git push
else
  git push -u origin "HEAD:<head_ref>"
fi
```

A branch already tracking the PR head (including a fork remote from
`gh pr checkout`) keeps its bare push. One with no upstream, or tracking
`<base_ref>` because it was created from it, is pushed to the PR head by name
and gets that as its upstream — never to a branch named after the local
checkout, which would leave the PR head unmoved (#3893).

If git demands a force-push, stop — something rewrote history and that needs
a human.

#### Step 5 — Wait for CI

```bash
bash .agents/skills/shared/wait-for-ci.sh <number>
```

| Exit | Meaning | Action |
|---|---|---|
| `0` | All checks passed | CI is green — proceed to "On CI green" below |
| `1` | One or more checks failed | Start next iteration with the failures as input |
| `2` | Timed out (10 min) | Record `final_ci_status: "timeout"`; exit loop |

**On CI green**:

1. Run `merge-state.sh <number>`. If it now reports `CONFLICTING`, return to
   Step 2 — a push can race a base-branch merge. A base that merely moved
   ahead is not a reason to return; only `CONFLICTING` is.

2. If the PR is a draft with a `needs-rebase` label, undraft it:

   ```bash
   gh pr ready <number>

   gh pr edit <number> --remove-label needs-rebase
   ```

3. Record `final_ci_status: "passing"`. Populate the `merge_state` block from
   this `merge-state.sh` call and the Step 2 decision.
4. Exit the loop.

**On iteration 4 failure (eject)**:

Record `final_ci_status: "failing"`. List the unresolved CI failures. Run
`merge-state.sh <number>` and populate the `merge_state` block. Exit the loop.

### Phase 6 — Emit Artifact and Post Comment

1. Build the execute artifact in memory throughout Phases 2–5; write it only now.
   Write `.claude/pr-{number}-execute.json` per the schema in [REFERENCE.md](REFERENCE.md).
2. Render the execute summary comment (format in [REFERENCE.md](REFERENCE.md)
   § "Execute Comment Format"). It carries the `Suite runs: <N> full, <M>
   targeted` line, derived per [REFERENCE.md](REFERENCE.md) § "`suite_runs`
   Fields and the Suite runs count" — the full count starts at one for `create-pr`'s first-push run.
3. Post comment: `gh pr review <number> --comment --body "<summary>"`
4. Record `execute_comment_url` in the artifact; re-write the file with the URL.
5. Print artifact path and outcome summary to stdout.

## No User Prompts (Except Two)

Execute runs to completion without user prompts, with two exceptions — the two
gates from `.claude/skills/shared/completeness-doctrine.md`. Note the default is
always fix-now; a gate is the exception, not the reflex.

**Gate 1 — `defer-ask`**: after filing the issue, post the deferral-ask and ask:

> "This is genuinely too big to finish in this PR. Here's what I did and what
> concretely remains: <measured remainder — the ratio, in plain language>.
> Filed as #N. May I defer the remainder to that issue?
> (If no response, I'll fix it now rather than defer.)"

Wait for a response. **On silence: fix it now** — fold the work in, `- Closes #N`,
record `outcome: fixed`. If it cannot be finished, hold the PR (`outcome: halted`,
draft/blocked). Silence is never approval to defer, and an unsupervised run has
no DEFER. Do not present an attempt count in place of a measured remainder.

**Gate 2 — `inversion-halt`**: do not file or act autonomously. Post the
inversion-ask:

> "This work overturns an assumption the issue/spec/ADR rested on:
> <the premise, in plain language>. That may invalidate other issues or docs
> that shared it. Is this a real inversion, and if so what should I file?"

Wait for a response. **On silence: halt** — record `outcome: halted`, set the PR
to draft/blocked, and stop. Do not proceed on the new premise unreviewed.

## Artifact Location

`.claude/pr-{number}-execute.json` — never committed; must be gitignored.
