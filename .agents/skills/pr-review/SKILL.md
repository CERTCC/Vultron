---
name: pr-review
description: >
  Comprehensive pull request review for the Vultron project. Verifies that
  a PR addresses its originating GitHub issue(s), conforms to Vultron specs
  and notes, follows AGENTS.md coding rules and naming conventions, has
  adequate test coverage, and passes linting requirements. Produces a
  structured PASS/FAIL/IMPROVE/DEFER report, attempts fixes for FAIL and
  IMPROVE findings, and posts results as a GitHub PR review comment. Use
  when the user asks to review a PR, validate a PR before merge, or audit
  a PR against project standards.
---

# Skill: PR Review

## Finding Severity

This skill uses the three-category system from
`.claude/skills/shared/completeness-doctrine.md` (loaded by `orient-agent`).
There is no WARN category — every finding is resolved here or explicitly gated.

| Verdict | Meaning | Required action |
|---|---|---|
| **FAIL** | Broken: won't work correctly, spec violated, changed behavior untested | Fix before the PR merges |
| **IMPROVE** | Works but incomplete: missing adjacent test, stale doc, extractable helper, obvious gap in scope | Fix in this session; document in a follow-up commit and PR comment |
| **NEW-ISSUE** | Distinct problem, out of this PR's family | Cut a GitHub issue; decide below whether to fold it in or leave it |

For FAIL and IMPROVE findings: attempt the fix in the same session, commit the
changes, and note them in a PR comment. Do not just flag and stop.

### Deciding what belongs in this PR

The scope boundary is **the problem the issue describes and its close relatives**
— not just the files already in the diff.

Use this decision tree for anything you find beyond the original issue:

1. **Trivial fix, any conceptual distance** → fix it now, mention it in the PR comment. Don't cut an issue.
2. **Non-trivial, same family** → fix it now. Expand the PR scope. Cut a GitHub issue if useful for tracking, but close it in this same PR.
3. **Non-trivial, distant cousin** → cut a GitHub issue, then ask the user: "I found X — should I fold it into this PR or leave it for the new issue?" Give a recommendation based on effort ratio (if fixing now is cheaper than reloading context later, lean toward fixing now).
4. **Requires separate design effort** (you recognize the problem but don't have the solution, or solving it requires deep investigation of a different domain) → cut a GitHub issue, keep this PR focused, do not ask.

**Same family** means: if you had to explain why you fixed both things in this PR, you could do it in one sentence without using the word "also." Siblings, cousins, aunts/uncles of the original problem — things that share the same parent concept. Distant cousins share an ancestor if you trace far enough, but the connection requires too many hops to justify expanding this PR.

**Never** create a NEW-ISSUE finding and leave it unaddressed in the report without following the decision tree above.

## Quick Start

```bash
# Review the current branch's open PR
/pr-review

# Review a specific PR
/pr-review 1234
```

## Workflow

### Phase 1 — Orient

1. Invoke `orient-agent` to load baseline context.
2. Identify the target PR:
   - If a PR number was provided, use it.
   - Otherwise, detect the PR for the current branch:
     `gh pr view --json number,title,body,headRefName,baseRefName,files`
3. Fetch PR metadata: title, body, linked issues, changed files, CI status.

### Phase 2 — Issue Linkage

1. Extract closing references (`Closes #N`, `Fixes #N`) from the PR body.
2. Fetch each linked issue with `gh issue view N --json title,body,labels`.
3. Verify: does the implementation scope match what the issue describes?
   Flag scope creep (PR does more than the issue), scope gaps (issue
   requirements not addressed), and missing issue links.

### Phase 3 — PR Body Format

Check against `.agents/skills/shared/pr-body-guide.md`:

- Closing references at the **top**, one per bullet
- Required sections present (Summary, Changes, Verification for impl PRs)
- Test counts in Verification are real numbers, not placeholders
- Co-authored-by trailer present in all commits

### Phase 4 — Domain Context

1. Identify domains from changed file paths (e.g., `wire/as2/`, `core/behaviors/`,
   `adapters/`, `demo/`).
2. Invoke `deepen-context` with hints matching those domains.
3. Load specs relevant to the changed domains via `load-specs` or `uv run spec-dump`.

### Phase 5 — Spec and Notes Conformance

With specs loaded, check changed code against requirements. See
[REFERENCE.md](REFERENCE.md) § "Spec Conformance Criteria" for the per-domain
checklist. Pay particular attention to:

- AGENTS.md Common Pitfalls relevant to the changed code areas
- Any spec IDs mentioned in the PR body or issue — confirm they are satisfied

### Phase 6 — ADR Check

1. Scan changed files for architectural signals: new layers, new protocols,
   changes to public APIs, persistence schema changes, new adapters, new BT
   integration patterns.
2. For each signal, consult `notes/specs-vs-adrs.md` (MS-11-001–MS-11-006)
   to determine if an ADR was warranted.
3. Check `docs/adr/index.md` for a relevant existing ADR:
   - If the PR *should have* an ADR and none is referenced: **IMPROVE** — draft
     the ADR stub or add it to the PR before merging.
   - If an existing ADR is contradicted by the change without amendment: **FAIL**.
   - If a new ADR was added: verify it follows `docs/adr/_adr-template.md`.

### Phase 7 — AGENTS.md Compliance

Check the diff for violations of non-negotiable coding rules. See
[REFERENCE.md](REFERENCE.md) § "AGENTS.md Rule Checklist".

### Phase 8 — Code Review

Invoke a `code-review` sub-agent (task tool, `agent_type: "code-review"`)
against the branch diff to surface bugs, logic errors, and security issues.

### Phase 9 — Notes and Docs Currency

1. **Notes currency**: Identify `notes/*.md` files that cover any domain
   touched by the PR (cross-reference domain hints from Phase 4). If an
   active note exists for a changed domain and was NOT updated: **IMPROVE** —
   update the note before merging; stale guidance is a real cost.
2. **Notes frontmatter**: For any `notes/*.md` file modified in the PR,
   validate YAML frontmatter per NF-06-001/NF-06-002:
   - Required fields: `title`, `status`
   - If `status: superseded`, `superseded_by` must be a non-empty scalar
   - If status is `superseded`, file should have been moved to `archived_notes/`
3. **Docs link integrity**: If any `docs/` file was modified, flag the need
   to run `uv run mkdocs build --strict` (or confirm CI did so).
4. **Silent contradiction**: If the PR's behavior change conflicts with an
   `active` note's guidance without updating that note: **FAIL**.

### Phase 10 — Test Coverage

- Are new or changed behaviors covered by tests?
- If any file under `demo/` or `adapters/` was changed: verify the PR body
  or CI confirms the integration test suite ran.
- Flag any public function or use-case `execute()` path with no test.

### Phase 11 — Linter / CI Status

1. Check CI status: `gh pr checks <number>`.
2. If CI is failing, summarize which checks fail.
3. If CI is not yet run, note that lint/type verification is pending.

### Phase 12 — Fix, Report, and Post

1. For all **FAIL** and **IMPROVE** findings that are within reach: attempt the
   fix now, before generating the report. Commit the changes. The PR history
   must show that the review finding was addressed, not just noted.

2. For **NEW-ISSUE** findings: apply the decision tree from the Finding Severity
   section above. Cut any needed GitHub issues first, then ask the user before
   folding distant-cousin work into this PR. Do not create issues and then treat
   user acknowledgment as a formality — the question is genuine.

3. Produce a structured report grouped by phase, with **PASS / FAIL / IMPROVE /
   NEW-ISSUE** for each area. See [REFERENCE.md](REFERENCE.md) § "Report Format".
   For any finding that was fixed in step 1, mark it as `FIXED` in the report
   with the commit reference.

4. Ask the user whether to post the report as a GitHub PR review comment:
   - If yes: `gh pr review <number> --comment --body "<report>"`
   - If yes + approve: `gh pr review <number> --approve --body "<report>"`
   - If yes + request changes: `gh pr review <number> --request-changes --body "<report>"`

---

See [REFERENCE.md](REFERENCE.md) for detailed criteria, per-domain checklists,
and the report format template.
