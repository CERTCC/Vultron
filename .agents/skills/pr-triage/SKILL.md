---
name: pr-triage
description: >
  Pure-discovery phase of the PR review pipeline. Runs all 11 inspection
  phases (orient through CI status), produces a machine-readable finding list
  at .claude/pr-{number}-triage.json, and posts a human-readable PR comment.
  Makes NO code changes. Use as the first step of /pr-ship, or standalone
  when you want a full finding inventory before deciding whether to execute
  fixes.
---

# Skill: PR Triage

## Purpose

Triage closes the finding list before any mutation occurs. All 11 inspection
phases run to completion; then and only then is the artifact written and the
comment posted. `pr-execute` reads the artifact — it never re-runs discovery.

## Finding Severity

This skill uses the three-category system from
`.claude/skills/shared/completeness-doctrine.md`.

| Verdict | Meaning | Required action |
|---|---|---|
| **FAIL** | Broken: won't work correctly, spec violated, changed behavior untested | Must be fixed before merge |
| **IMPROVE** | Works but incomplete: missing adjacent test, stale doc, obvious gap in scope | Fix in the same session |
| **NEW-ISSUE** | Distinct problem, out of this PR's family | Cut a GitHub issue; apply decision tree |

### Decision-Tree Outcomes

Each finding is tagged with one of four outcomes. Triage records the outcome
but does NOT act on it — `pr-execute` acts.

| Outcome | Condition | What execute does |
|---|---|---|
| `fix-now` | Trivial fix, any conceptual distance; OR non-trivial but same family (does not meaningfully expand PR scope) | Fix inline, mention in comment |
| `fix-now-expand-scope` | Non-trivial, same family, and the fix meaningfully expands the PR's stated scope | Fix inline, expand PR scope |
| `new-issue-ask` | Non-trivial, distant cousin | File issue, stop and ask user whether to fold in |
| `new-issue-no-ask` | Requires separate design effort | File issue, continue without asking |

**Same family** means: if you had to explain why you fixed both things in this
PR, you could do it in one sentence without using the word "also."

## Quick Start

```bash
# Triage the current branch's open PR
/pr-triage

# Triage a specific PR
/pr-triage 1234
```

## Workflow

### Phase 1 — Orient

1. Invoke `orient-agent` to load baseline context.
2. Identify the target PR:
   - If a PR number was provided, use it.
   - Otherwise detect the PR for the current branch:
     `gh pr view --json number,title,body,headRefName,baseRefName,files`
3. Fetch PR metadata: title, body, linked issues, changed files, CI status.

### Phase 2 — Issue Linkage

1. Extract closing references (`Closes #N`, `Fixes #N`) from the PR body.
2. Fetch each linked issue: `gh issue view N --json title,body,labels`.
3. Assess: does implementation scope match what the issue describes?
   Emit findings for scope creep (PR does more than the issue), scope gaps
   (issue requirements not addressed), and missing issue links.

### Phase 3 — PR Body Format

Check against `.claude/skills/shared/pr-body-guide.md`:

- Closing references at the **top**, one per bullet
- Required sections present (Summary, Changes, Verification for impl PRs)
- Test counts in Verification are real numbers, not placeholders
- Co-authored-by trailer present in all commits

### Phase 4 — Domain Context

1. Identify domains from changed file paths (e.g., `wire/as2/`, `core/behaviors/`,
   `adapters/`, `demo/`).
2. Invoke `deepen-context` with hints matching those domains.
3. Load specs relevant to the changed domains via `load-specs` or
   `PYTHONPATH= uv run spec-dump`.
4. Record the domain list in `pr_metadata.domains` — execute re-uses these hints.

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
2. Consult `notes/specs-vs-adrs.md` (MS-11-001–MS-11-006) to determine if an
   ADR was warranted.
3. Check `docs/adr/index.md` for a relevant existing ADR:
   - PR *should have* an ADR and none referenced → **IMPROVE**
   - Existing ADR contradicted without amendment → **FAIL**
   - New ADR added: verify it follows `docs/adr/_adr-template.md`

### Phase 7 — AGENTS.md Compliance

Check the diff for violations of non-negotiable coding rules. See
[REFERENCE.md](REFERENCE.md) § "AGENTS.md Rule Checklist".

### Phase 8 — Code Review Sub-Agent

Invoke a `code-review` sub-agent (`agent_type: "code-reviewer"`) against the
branch diff to surface bugs, logic errors, and security issues. Wait for the
sub-agent to complete before proceeding — its findings must be merged into the
finding list before the artifact is written.

### Phase 9 — Notes and Docs Currency

1. **Notes currency**: Identify `notes/*.md` files covering any domain touched
   by the PR. If an active note was NOT updated: **IMPROVE** — stale guidance
   is a real cost.
2. **Notes frontmatter**: For any `notes/*.md` modified in the PR, validate
   YAML frontmatter per NF-06-001/NF-06-002:
   - Required fields: `title`, `status`
   - If `status: superseded`, `superseded_by` must be a non-empty scalar
3. **Docs link integrity**: If any `docs/` file was modified, flag need to run
   `uv run mkdocs build --strict`.
4. **Silent contradiction**: If the PR's behavior change conflicts with an
   `active` note without updating it: **FAIL**.

### Phase 10 — Test Coverage

- Are new or changed behaviors covered by tests?
- If any file under `demo/` or `adapters/` was changed: verify the PR body or
  CI confirms the integration test suite ran.
- Flag any public function or use-case `execute()` path with no test.

### Phase 11 — Linter / CI Status

1. Check CI status: `gh pr checks <number>`.
2. Summarize which checks fail if CI is failing.
3. Note if CI has not yet run.

### Phase 12 — Emit Artifact and Post Comment

This is the only phase that produces output. No mutations before this point.

1. Assign a stable `id` slug to each finding: `phase{N}-{kebab-description}-{index}`
   where index is a sequential integer suffix that guarantees uniqueness within
   the run (e.g., `phase5-missing-nonemptystring-0`, `phase5-missing-nonemptystring-1`).
2. Write `.claude/pr-{number}-triage.json` per the schema in [REFERENCE.md](REFERENCE.md).
3. Render a human-readable markdown comment from the finding list (format in
   [REFERENCE.md](REFERENCE.md) § "Triage Comment Format").
4. Post comment: `gh pr review <number> --comment --body "<report>"`
5. Record the returned comment URL in the artifact (`triage_comment_url`), then
   re-write the artifact with the URL filled in.
6. Print artifact path and finding count summary to stdout.

## Artifact Location

`.claude/pr-{number}-triage.json` — never committed; must be gitignored.

## No Code Changes

Triage never edits files, never commits, never creates issues. Any finding
that could be resolved right now is recorded with `decision_outcome: fix-now`
so execute can act on it. Triage just observes.
