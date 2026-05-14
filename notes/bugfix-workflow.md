---
title: Bugfix Workflow — Implementation Notes
status: active
description: >
  Design decisions and implementation patterns for the test-first bugfix
  workflow.
related_specs:
  - specs/bugfix-workflow.yaml
---

# Bugfix Workflow — Implementation Notes

Design decisions, implementation patterns, and examples for the bugfix skill
requirements in `specs/bugfix-workflow.yaml`.

---

## Decision Table

| Question | Decision | Rationale |
|----------|----------|-----------|
| Should deeper root-cause analysis be a new phase or woven into Phase 2? | New Phase 2b — a distinct gate | Keeps Phase 2 focused on basic alignment; Phase 2b is a conditional follow-up that fires only when scope hasn't already been addressed. |
| When should Phase 2b fire? | Only if Phase 2 has not already surfaced broader scope | Avoids redundant questions when the user has already indicated the issue is larger. |
| What should Phase 2b questions reference? | Specific code paths and invariants found by the agent | Open-ended questions invite unhelpful "I don't know" answers; grounded questions drive useful answers. |
| When Phase 2b surfaces multiple issues, what happens to them? | Each filed as a new Bug-type GitHub issue via `manage-github-issue` | Keeps current run focused; new bugs surface for future runs without being lost. |
| Where should fixed bugs be archived? | `plan/history/` via `uv run append-history implementation` | Bug fixes are implementation history; the GitHub issue is closed automatically by the PR "Fixes #N". |
| Should fixed bugs leave a tombstone anywhere? | No — GitHub closes the issue on PR merge; history is captured via `append-history` | GitHub Issues are the source of truth; closed issues are their own record. |
| What if a bug was discovered in a prior session but never filed? | File it as a Bug-type GitHub issue via `manage-github-issue` | GitHub Issues are durable and discoverable; local files are ephemeral. |

---

## Phase 2b — Pattern

After the four standard Phase 2 questions, check whether scope has already
been broadened. If not, ask one targeted question:

```text
"My working theory for the root cause is [specific code path / invariant /
data flow]. Does this look like an isolated defect, or might it be a symptom
of a deeper issue in [module / design pattern]?"
```

If the user says "deeper issue":

```text
"I can see at least [N] related concerns:
  1. [issue A]
  2. [issue B]
Which should this fix address? I'll file the others as new bugs."
```

If the user says "just the surface fix":

> Proceed directly to Phase 3.

---

## Escalation — Pattern

When filing newly discovered bugs during analysis, use the `manage-github-issue`
helper script:

```bash
.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<short bug title>" \
  --body "## Symptoms

<one sentence>

## Root cause (hypothesis)

<what was observed during analysis of #N>

## Components involved

- \`path/to/module.py\`" \
  --issue-type-id "IT_kwDOAjf0s84AcFLq"
```

Reference newly filed issues in the PR description:

```text
Fixes #<N>.
Also filed: #<NNN> (related issue discovered during analysis).
```

---

## Bug Archive Format

Append bug fix summaries to `plan/history/` using `uv run append-history
implementation`. Use the same section format as build-skill completions:

```markdown
## #<N> — <title> (FIXED YYYY-MM-DD)

**Symptoms**: <one sentence describing observed vs expected behaviour>

**Root cause**: <concise technical explanation>

**Fix**: <what was changed and why>

**Components changed**:
- `path/to/file.py`
- `test/path/to/test_file.py`

**Lessons learned** (optional): <any insights for future work>
```

---

## Skill Integration Notes

### Bug lifecycle (GitHub Issues)

```text
Bug filed (GitHub Bug-type issue)
              ↓
    Agent claims issue + creates branch bug/<N>-<slug>
              ↓
    Agent confirms + scopes fix (Phase 2 + 2b)
              ↓
    Fix implemented, tests pass
              ↓
    Summary appended via uv run append-history implementation
              ↓
    PR opened with "Fixes #N" → merges → issue closed automatically
```

### Relationship to grill-me

Phase 2b is not a full grill-me session; it is one targeted question that
escalates into a brief structured exchange only if the user confirms a deeper
issue. Reserve full grill-me for architectural decisions, not individual bugs.

### Layer and import rules

These requirements govern agent skill `SKILL.md` files and `plan/` documents
only — they have no impact on `vultron/` source code layers.
