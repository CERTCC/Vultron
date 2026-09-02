---
name: pr-review
description: >
  DEPRECATED — use /pr-ship (full pipeline) or /pr-triage (discovery only)
  instead. Kept as canonical prose reference for the 11 inspection phases;
  do not invoke directly for new work.
---

# Skill: PR Review

> **Deprecated.** This skill has been superseded by the `pr-triage` →
> `pr-execute` → `pr-verify` pipeline, invoked via `/pr-ship`. The phase
> descriptions below remain the authoritative reference for what `pr-triage`
> inspects. Do not invoke `/pr-review` for new work.

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

Use this decision tree for anything you find beyond the original issue. FILE
(does this warrant a record?) and DEFER (fix now, or leave for later?) are
**separate** decisions; the default is fix-now. See
`.agents/skills/shared/completeness-doctrine.md`.

1. **Not an "also" excursion** — you can explain fixing it and the original thing in one sentence without the word "also" → fix it now, no issue. The diff is the record.
2. **An "also" excursion** → fix it now **and** file an issue this PR closes (`- Closes #N`), with a one-line "why". Filing does not mean deferring.
3. **Genuinely too big to finish now** → defer only through Gate 1: file, present a *measured remainder* (what you did, what concretely remains) in plain language, and get explicit approval. On silence, fix it now. Only *second-order* findings (revealed while fixing an excursion) are eligible.
4. **Inverts a premise** the issue or its backing specs/ADRs rested on → Gate 2: explain the overturned premise in plain language, ask if/what to file, and do not act on it unreviewed. On silence, halt the PR.

**The "also" test**: if explaining why you fixed both things needs the word "also," it is a genuine excursion (file it). If not, it is simply doing the task (no file). Siblings, cousins, aunts/uncles of the original problem share the same parent concept; a fix that needs "also" has drifted far enough to warrant its own record.

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
3. Load specs relevant to the changed domains via `load-specs` or `PYTHONPATH= uv run spec-dump`.

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
