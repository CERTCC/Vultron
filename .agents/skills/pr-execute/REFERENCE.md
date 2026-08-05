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

Proceed to Phase 5.

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
4. If pre-existing is proven: create/update a Bug issue with evidence via
   `manage-github-issue`; wire structured blockers; post a handoff comment.
5. If evidence is incomplete: treat as PR-owned and continue debugging.

### Integration Tests Fail ❌

**Default assumption**: current PR changes caused the failure until disproven.

**Action**:

1. Display failure output (first 50 lines + last 20 for context).
2. Perform targeted causality checks against the PR diff.
3. Allow "unrelated/pre-existing" only with clean-base + causality evidence.
4. If pre-existing is proven: create/update a Bug issue with evidence; wire
   blockers via `manage-github-issue`; add a handoff comment.
5. Stop only after recording blocked/unblocked status with linked evidence.

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
   record as `outcome: filed`.
3. If issue number found: `gh issue view <N> --json state`
   - `open` → fine, no action needed.
   - `closed` → the fix landed without removing the marker; file a new tracking
     issue, update the reason string, record as `outcome: filed`.

The rule: **every `xfail` must point to a live open issue**. An xfail with a
dead or missing reference is treated as unmanaged debt and triggers a
`new-issue-no-ask` finding.

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
- 2+ consecutive test failures after fix attempts
- Test output suggests missing context (env vars, setup, infrastructure)
- Error suggests architectural issue (breaking change to core logic)

Report the state with linked Bug issue evidence, structured blockers, and
explicit blocked/unblocked status.

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

The comment raises something outside the PR's scope or requiring design work.

**Reply template**:
> "This would require {brief explanation}. Filed as #{issue_number} for
> separate treatment. Can we discuss whether this should block merge?"

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
  "final_ci_status": "passing",
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
      "finding_id": "phase9-distant-refactor-0",
      "outcome": "deferred-ask",
      "commit_ref": null,
      "issue_number": 999,
      "skip_reason": "Non-trivial, distant cousin — filed as #999, awaiting user decision on fold-in.",
      "comment_resolution": null
    }
  ],
  "execute_comment_url": "https://github.com/CERTCC/Vultron/pull/1234#issuecomment-..."
}
```

### Outcome Values

| Value | Meaning |
|---|---|
| `fixed` | Applied inline; commit_ref recorded |
| `filed` | GitHub issue created; issue_number recorded |
| `deferred-ask` | Issue filed; user asked whether to fold in; awaiting decision |
| `skipped` | Could not address; skip_reason explains why |

**Integrity check**: `len(results)` must equal `len(triage.findings)`. Every
finding must have an outcome. `pr-verify` checks this count and warns if they
diverge (indicating execute was interrupted before completion).

---

## Execute Comment Format

```markdown
## PR Execute: #<number> — <title>

**Fixes applied**: <N> commits
**Issues filed**: <M>
**Deferred (awaiting your input)**: <K>
**Tests run**: unit only / unit + integration
**CI status after push**: ✅ passing / ❌ failing / ⏳ pending

---

### Fixed

| Finding | Commit |
|---|---|
| phase5-missing-nonemptystring-0: Field must use OptionalNonEmptyString | `abc1234` |
| phase8-unused-import-0: Remove unused import | `abc1234` |

### Filed as Issues

| Finding | Issue |
|---|---|
| phase9-distant-refactor-0: Refactor dispatcher | #999 |

### Deferred — Awaiting Your Input

| Finding | Issue | Question |
|---|---|---|
| phase8-extract-helper-0: Extract helper function | #1000 | Fold into this PR or leave for #1000? |

### Skipped

| Finding | Reason |
|---|---|
| phase11-preexisting-test-fail-0 | Pre-existing failure; filed as Bug #1001 with evidence |

---

*Execute artifact: `.claude/pr-<number>-execute.json`*
*Next step: run `/pr-verify` or wait for CI, then `/pr-ship` will continue automatically.*
```
