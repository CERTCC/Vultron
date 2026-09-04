# PR Execute — Reference

Detailed criteria consumed during execution. Referenced from SKILL.md.

---

## Integration Test Detection

`pr_metadata.needs_integration_tests` is set by `pr-triage`. Execute reads
this flag — it does not re-detect. The detection logic (for reference) is:

Run **full suite (unit + integration)** if PR modifies any of:

- `demo/` — any demo script or orchestration file
- `integration_tests/` — any integration test file
- `adapters/` — driving or driven adapters
- `vultron/core/behaviors/` — behavior tree logic
- `vultron/core/use_cases/` — use-case implementations
- `vultron/wire/as2/extractor.py` — semantic extraction

---

## Test Failure Rules

### All Tests Pass ✅

Proceed to Phase 6.

### Unit Tests Fail ❌

**Default assumption**: current PR changes caused the failure until disproven.

**Action**:

1. Display failure output.
2. Fix branch-owned issues directly; re-run relevant tests.
3. Classify as pre-existing **only after**:
   - Clean-base proof: checkout main (or equivalent), run same test, confirm
     it fails there too.
   - At least one causality check: confirm no line in the PR diff plausibly
     causes the failure.
4. If pre-existing is proven: assess whether a fix is straightforward and
   context is in hand. If yes, fix it now — a pre-existing failure you can
   resolve is still a failure worth resolving. Only proceed to step 5 if the
   fix is genuinely non-trivial or requires design work outside this PR's scope.
5. If deferral is warranted: create/update a Bug issue with evidence via
   `manage-github-issue`; wire structured blockers; post a handoff comment.
6. If evidence is incomplete: treat as PR-owned and continue debugging.

### Integration Tests Fail ❌

**Default assumption**: current PR changes caused the failure until disproven.

**Action**:

1. Display failure output (first 50 lines + last 20 for context).
2. Perform targeted causality checks against the PR diff.
3. Allow "unrelated/pre-existing" only with clean-base + causality evidence.
4. If pre-existing is proven: assess whether a fix is straightforward and
   context is in hand. If yes, fix it now. Only proceed to step 5 if the fix
   is genuinely non-trivial or requires design work outside this PR's scope.
5. If deferral is warranted: create/update a Bug issue with evidence; wire
   blockers via `manage-github-issue`; add a handoff comment.
6. Stop only after recording blocked/unblocked status with linked evidence.

Integration tests can fail due to: missing environment setup, timing issues
in demo orchestration, architectural breaking changes, or infrastructure
problems (docker, network). All require evidence-based triage — not just
"looks unrelated."

### Flaky Test Dedup (pre-existing failures)

When a test failure is confirmed pre-existing, use this fractal search before
creating a new issue — cheapest check first:

**Level 1 — Local catalog** (`notes/flaky-tests.md`):

- For unit tests: exact match on pytest node ID (e.g.
  `test/bt/test_vultrabot.py::MyTestCase::test_main`).
- For CI/demo jobs: exact match on job name (e.g. `fvcv-extension`).
- If match found: `gh issue view <N> --json state,title`
  - `open` → post a comment on the issue:

    ```text
    Blocked PR #<N> on <date>. Step: <failure description>. Evidence: <log excerpt>.
    ```

    Use that issue number in `skip_reason`. **Do not create a new issue.**
  - `closed` → evict the stale catalog entry; fall through to Level 2.

**Level 2 — Exact GitHub search**:

```bash
gh issue list --label flaky-test --state open --search '"<node_id_or_job_name>"'
```

If one match: post comment as above; use that issue.

**Level 3 — File-path GitHub search** (unit tests only):

Strip `::Class::method`, search on the file path alone. If exactly one match:
use it. If multiple: proceed to Level 4.

**Level 4 — Agent judgment**:

Read top 3 search results. If one is clearly the same failure: use it.
**When in doubt: create a new issue** rather than incorrectly merging two
distinct failures.

**Creating a new flaky-test issue**:

- Labels: `bug` + `flaky-test`
- Title: `Flaky: <job_name or test_node_id>`
- Body must include:
  - The exact node ID or job name (for future exact-phrase search)
  - A `## Blocked PRs` section with the first occurrence entry
  - Clean-base proof and causality check summary as evidence
- Add to Project #24: `bash .agents/skills/shared/add-to-project.sh <N>`
- Add entry to `notes/flaky-tests.md`

### xfail Ratchet

After running the test suite, scan `XFAIL` lines in pytest output. For each:

1. Extract `#<N>` from the `reason` string (regex `#(\d+)`).
2. If no issue number found: this is an unmanaged xfail — file a new `bug` +
   `flaky-test` issue, update the `reason` string in the PR to reference it,
   record as `outcome: fixed` with the new `issue_number` (the xfail now points to
a live issue — the finding is resolved).
3. If issue number found: `gh issue view <N> --json state`
   - `open` → fine, no action needed.
   - `closed` → the fix landed without removing the marker; file a new tracking
     issue, update the reason string, record as `outcome: fixed` with the new `issue_number` (the xfail now points to
a live issue — the finding is resolved).

The rule: **every `xfail` must point to a live open issue**. An xfail with a
dead or missing reference is treated as unmanaged debt and triggers a
NEW-ISSUE finding — file a fresh tracking issue for it.

> **xfail-tracking issues vs flaky-test issues**: these are distinct categories.
> An xfail-tracking issue documents a known architectural violation or pre-existing
> test failure that cannot yet be fixed (e.g. ARCH-12 cleanup debt). A flaky-test
> issue tracks a test that *sometimes* fails due to timing/ordering/probabilistic
> behavior. xfail-tracking issues should use the `bug` label (not `flaky-test`),
> so they do not pollute the `--label flaky-test` GitHub search in Level 2 of the
> dedup procedure above.

### When to Stop and Report

Stop and surface to the user if:

- Integration test failure with unclear root cause after causality checks
- CI loop reaches 4 iterations with the same failure persisting (see Phase 5 eject condition in SKILL.md)
- Test output suggests missing context (env vars, setup, infrastructure)
- Error suggests architectural issue (breaking change to core logic)
- A merge conflict whose correct resolution is genuinely unclear (see
  § "Conflict Resolution Rules") — abort the merge, do not guess
- `merge-state.sh` still reports `CONFLICTING` after a resolution was pushed
- `git push` is rejected as non-fast-forward after a merge, implying someone
  rewrote the remote branch

Report the state with linked Bug issue evidence, structured blockers, and
explicit blocked/unblocked status.

---

## Conflict Resolution Rules

### Why sync runs late

The branch is synced in Phase 5 (CI loop, Step 2) — after all fixes, before the
test suite. Three reasons:

1. **Execute's own fixes can create conflicts.** A fix touching the same lines a
   base-branch commit touched is only conflicting once both exist.
2. **The base branch moves during the run.** Triage's merge state is stale by the
   time execute finishes; another PR can land mid-pipeline.
3. **Tests must run on the merged tree.** A clean merge can still be a *semantic*
   conflict — both sides apply, the result is broken. Only running the suite
   post-merge catches that.

### Merge, do not rewrite

Once a branch is pushed and a PR is open, use `sync-with-main.sh` (merge commit),
not `freshen-branch.sh` (cherry-pick rewrite). Rewriting a pushed branch requires
a force-push, which orphans reviewers' line comments and breaks any `commit_ref`
already recorded in the triage/execute artifacts. `freshen-branch.sh` belongs to
`create-pr`, before the first push.

### Resolving each path

| Situation | Resolution |
|---|---|
| Base changed a line the PR does not care about | Take base (`--theirs` in merge terms), then re-verify the PR's intent still holds |
| PR intentionally changed what base also changed | Combine by hand — keep the PR's semantic and base's refactor |
| Both added entries to a list/registry/index | Keep **both** entries; this is the most common false conflict |
| Generated or lock file (`uv.lock`, `board-ids.json`) | Take base, then regenerate from the merged sources |
| `CHANGELOG`/history/append-only file | Keep both blocks in chronological order — see `archived_notes/append-only-file-handling.md` |
| Conflict is in a file the PR never meant to touch | Take base wholesale, then confirm with `git diff <base_ref>...HEAD` that the file is absent from the PR diff |

Rules that do not bend:

- **Read both sides before resolving.** `git log --merge -p -- <path>` shows the
  competing commits. Blind `--ours`/`--theirs` on an unread file silently reverts
  someone's work.
- **Never resolve by deleting the base's changes** to make the PR's diff apply.
  That is a silent revert; it is worse than the conflict.
- **Verify no markers remain** before pushing:
  `git grep -nE '^(<<<<<<<|=======|>>>>>>>)'` must be empty.
- **Re-run the full suite after resolving**, even if it passed pre-merge.
- **Never resolve a conflict you do not understand.** Abort
  (`sync-with-main.sh --abort`), record the merge-state finding as `skipped` with
  the conflicted paths and why, and stop. An honest stop beats a wrong merge.

### Commit message

`git commit --no-edit` keeps git's generated `Merge branch 'main' into <branch>`
message, which is what tooling expects. If the resolution required judgment,
amend a body describing it:

```text
Merge branch 'main' into task/1234-slug

Resolved conflicts in:
- vultron/core/models/case/case.py — kept both new fields
- uv.lock — regenerated after taking main's version
```

---

## Comment Resolution

For each unresolved review comment, the resolution strategy is:

### ✅ Fully Addressed

The code change directly addresses what was asked.

**Resolution message template**:
> "Addressed in commit `{commit_ref}`: {one-sentence description of what changed}."

### ⚠️ Partially Addressed

The immediate issue is fixed but something related cannot be addressed now.

**Reply template**:
> "Addressed the immediate issue in commit `{commit_ref}`. The broader concern
> around {topic} is tracked in #{issue_number}. Leaving this thread open for
> the reviewer to close if the immediate fix is sufficient."

### ❌ Cannot Address / Needs Discussion

The comment raises something genuinely too big to finish now. "Separate
treatment" is a deferral — it must clear Gate 1 (measured remainder + explicit
approval), not be asserted by the act of filing. If you can just fix it, fix it.

**Reply template**:
> "This would require {brief explanation}. I did {what}, and {measured
> remainder} concretely remains. Filed as #{issue_number}. Can we discuss
> whether to fold it in here or leave it for #{issue_number}?"

### Do NOT Resolve If

- The code change doesn't actually address the comment
- The comment asks for something that requires reviewer decision
- The comment suggests a breaking change needing discussion
- The comment is about future work that's been deferred

Leave unresolved and reply — let the reviewer close it when satisfied.

### Architecture/Design Comments

If the comment asks "why X instead of Y":

- If decision is in an ADR or design note: resolve with reference.
- If it deserves discussion: reply, do not mark resolved.

---

## Execute Artifact Schema

File: `.claude/pr-{number}-execute.json`

```json
{
  "schema_version": "1.0",
  "pr_number": 1234,
  "timestamp": "2026-01-01T00:00:00Z",
  "integration_tests_run": true,
  "final_ci_status": "passing",  // "passing" | "failing" | "timeout"
  "merge_state": {
    "base_ref": "main",
    "synced": true,
    "sync_commit_ref": "def5678",
    "conflicts_resolved": ["vultron/core/models/case/case.py", "uv.lock"],
    "mergeable_after_sync": "MERGEABLE",
    "merge_state_status_after_sync": "CLEAN",
    "undrafted": false
  },
  "results": [
    {
      "finding_id": "phase5-missing-nonemptystring-0",
      "outcome": "fixed",
      "commit_ref": "abc1234",
      "issue_number": null,
      "skip_reason": null,
      "comment_resolution": "Addressed in commit abc1234: changed field to OptionalNonEmptyString."
    },
    {
      "finding_id": "phase8-unused-import-0",
      "outcome": "fixed",
      "commit_ref": "abc1234",
      "issue_number": null,
      "skip_reason": null,
      "comment_resolution": null
    },
    {
      "finding_id": "phase9-retry-logic-0",
      "outcome": "fixed",
      "commit_ref": "abc1234",
      "issue_number": 999,
      "skip_reason": null,
      "comment_resolution": "'also' excursion — filed #999 and fixed it in this PR; PR closes #999."
    }
  ],
  "execute_comment_url": "https://github.com/CERTCC/Vultron/pull/1234#issuecomment-..."
}
```

### Outcome Values

| Value | Meaning |
|---|---|
| `fixed` | Applied inline; commit_ref recorded. `issue_number` is `null` for a plain `fix-now`, or set for a `fix-now-file` excursion the PR closes |
| `deferred-ask` | Gate 1: issue filed, a measured remainder presented, and the user **explicitly approved** deferral. Silence does not produce this outcome — silence produces `fixed` |
| `halted` | Gate 2: an inversion the user did not resolve; PR set to draft/blocked; pipeline stopped |
| `skipped` | Could not address (e.g., unresolved conflict, pre-existing failure filed with evidence); skip_reason explains why |

There is no standalone `filed` outcome — filing a record is not an endpoint.
A filed finding is either `fixed` (the PR closes it) or `deferred-ask`
(explicitly approved). See `.claude/skills/shared/completeness-doctrine.md`
§ "Filing Is Not Deferring".

**Integrity check**: `len(results)` must equal `len(triage.findings)`. Every
finding must have an outcome. `pr-verify` checks this count and warns if they
diverge (indicating execute was interrupted before completion).

### `merge_state` Fields

| Field | Meaning |
|---|---|
| `base_ref` | Branch synced against — copied from `pr_metadata.base_ref`, not assumed to be `main` |
| `synced` | `true` if the branch contains the base tip after Phase 4 |
| `sync_commit_ref` | Merge commit SHA, or `null` if the branch was already current |
| `conflicts_resolved` | Paths that had conflict markers; `[]` for a clean merge |
| `mergeable_after_sync` | `merge-state.sh` result from Phase 4 step 6 |
| `merge_state_status_after_sync` | `mergeStateStatus` from the same call |
| `undrafted` | `true` if execute ran `gh pr ready` and dropped `needs-rebase` |

`merge_state` is **required**. `pr-verify` treats a missing or `synced: false`
block as a hard gate failure — an execute run that never checked mergeability
cannot produce a READY-TO-MERGE verdict.

---

## Execute Comment Format

```markdown
## PR Execute: #<number> — <title>

**Fixes applied**: <N> commits
**Excursions filed and fixed**: <M> (PR closes them)
**Deferred (you approved)**: <K>
**Halted (inversion, awaiting you)**: <H>
**Tests run**: unit only / unit + integration
**CI status**: ✅ passing / ❌ failing / ⏳ timed out
**Base sync**: ✅ merged `<base_ref>` @ `def5678` — <N> conflicts resolved / ✅ already current / ❌ conflicts unresolved

---

### Conflicts Resolved

| Path | Resolution |
|---|---|
| `vultron/core/models/case/case.py` | Kept both new fields |
| `uv.lock` | Took `main`, regenerated |

_Omit this section entirely when the merge was clean._

---

### Fixed

| Finding | Commit | Closes |
|---|---|---|
| phase5-missing-nonemptystring-0: Field must use OptionalNonEmptyString | `abc1234` | — |
| phase8-unused-import-0: Remove unused import | `abc1234` | — |
| phase9-retry-logic-0: "also" excursion — rewrote retry logic | `abc1234` | #999 |

_The `Closes` column shows `fix-now-file` excursions the PR closes; `—` means a
plain `fix-now` recorded by the diff alone._

### Deferred — You Approved

| Finding | Issue | Measured remainder |
|---|---|---|
| phase9-migrate-callsites-0: Migrate remaining call sites | #1000 | 3 of 47 done; 44 remain, each a distinct signature change |

_Only appears when you **explicitly approved** deferral. Silence produces a fix,
not a deferral._

### Halted — Inversion, Awaiting You

| Finding | Overturned premise |
|---|---|
| phase6-embargo-premise-0 | Issue assumed embargo state is single-owner; the fix requires multi-owner, which contradicts ADR-0012 |

_PR is set to draft/blocked until you resolve the inversion._

### Skipped

| Finding | Reason |
|---|---|
| phase11-preexisting-test-fail-0 | Pre-existing failure; filed as Bug #1001 with evidence |

---

*Execute artifact: `.claude/pr-<number>-execute.json`*
*Next step: run `/pr-verify`, or `/pr-ship` will continue automatically.*
```
