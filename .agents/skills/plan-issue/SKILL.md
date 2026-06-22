---
name: plan-issue
description: >
  Convert a single open GitHub Idea or Concern issue into a concrete
  implementation plan. Deepens context from the issue first, then runs a
  grill-me interview to understand scope, creates implementation issues,
  optionally updates specs/notes, archives the source issue, and closes it.
  Auto-detects Idea vs Concern from the GitHub issue type. Replaces the
  former ingest-idea and ingest-concern skills. Use when the user references
  an Idea or Concern issue number, or says "plan this idea/concern".
---

# Skill: Plan Issue

Convert an open GitHub `type:Idea` or `type:Concern` issue into an
implementation plan: interview → explore → create impl issues →
optionally update docs → archive + close the source issue.

## Constants

See `.agents/skills/shared/README.md` for project IDs and issue type IDs.

---

## Workflow

### Phase 0 — Select the Issue

If the user provided a GitHub issue number, skip to Phase 1.

Otherwise, query open Idea and Concern issues and present them as a
combined multiple-choice list via `ask_user`:

```bash
gh issue list --repo CERTCC/Vultron --state open --limit 200 \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Idea" or .issueType.name == "Concern")
        | "#\(.number) [\(.issueType.name)]: \(.title)"'
```

Include a **"Create a new Idea"** option at the end. Wait for the user's
selection before continuing.

#### Creating a new Idea (if selected)

Ask the user to describe the idea (`ask_user`, freeform). Synthesize a
short title, then create the issue via the `manage-github-issue` helper:

```bash
ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "${TITLE}" \
  --body "${BODY}" \
  --issue-type-id "IT_kwDOAjf0s84B_EoA")
```

### Phase 1 — Read and Validate

```bash
ISSUE_JSON=$(gh issue view "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --json number,title,body,labels,state,issueType)
ISSUE_STATE=$(echo "${ISSUE_JSON}" | jq -r '.state')
ISSUE_TYPE=$(echo "${ISSUE_JSON}"  | jq -r '.issueType.name // ""')

if [ "${ISSUE_STATE}" != "OPEN" ]; then
  echo "❌ #${ISSUE_NUMBER} is not open (state=${ISSUE_STATE}). Stopping." >&2
  exit 1
fi
if [ "${ISSUE_TYPE}" != "Idea" ] && [ "${ISSUE_TYPE}" != "Concern" ]; then
  echo "❌ #${ISSUE_NUMBER} is type '${ISSUE_TYPE}', expected Idea or Concern." >&2
  exit 1
fi
```

For both issue types, also query the parent epic (if any):

```bash
EPIC_NUMBER=$(gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: '"${ISSUE_NUMBER}"') { parent { number } }
  }
}' --jq '.data.repository.issue.parent.number // ""')
```

Use the title and body from `ISSUE_JSON` as source material throughout.

### Phase 2 — Orient (invoke `orient-agent`)

Invoke the `orient-agent` skill to load required baseline context.

### Phase 3 — Deepen Context (invoke `deepen-context`)

Invoke the `deepen-context` skill, using focus hints derived from the issue
title and body (e.g., "wire layer", "BT integration", "embargo lifecycle").
This ensures the grill-me interview in Phase 4 starts from an informed
baseline rather than blank-slate baseline context.

### Phase 4 — Grill-Me Interview (invoke `grill-me`)

Invoke the `grill-me` skill. Resolve every decision branch one at a time
via `ask_user`, providing a recommendation for each. Cover:

**Both types (shared base):**

1. **Scope** — What is in scope? What is explicitly out of scope?
2. **Acceptance criteria** — How do we verify this is fully addressed?
   Drive one GitHub issue per distinct AC cluster.
3. **ADR determination** — Apply the `notes/specs-vs-adrs.md` decision tree
   (MS-11-001 through MS-11-006). Form a recommendation with reasoning
   (e.g., "This warrants an ADR because alternative X was meaningfully
   evaluated and rejected"). Present the recommendation to the user for
   approval or refinement before proceeding.

**For Idea (additional):**

1. **Spec scope** — What requirements should be captured?
2. **Design decisions** — What alternatives were considered? Which is recommended?
3. **Notes scope** — What implementation guidance should be documented?

**For Concern (additional):**

1. **Root cause** — What is actually broken, risky, or missing?
2. **Impact** — What fails or degrades if left unaddressed?
3. **Options** — 2–3 ways to address this concern.
4. **Recommended approach** — Which option and why.
5. **Spec/notes gaps** — Does this concern reveal missing requirements or
   design decisions? Which file(s) should be added or changed?
6. **AGENTS.md gap** — Is there a recurring implementation pitfall to capture?

Do **not** write anything until grill-me is complete.

If the interview surfaces focus areas not covered in Phase 3 (e.g., a
subsystem or design pattern that only became apparent during grilling),
invoke `deepen-context` again with those additional hints before proceeding.

### Phase 4b — Create Task Branch (if docs changes are expected)

If grill-me established that Phase 5 will produce file writes, create the
branch **before** writing any files so uncommitted changes are never at risk:

```bash
bash .agents/skills/shared/sync-check.sh \
  || { echo "❌ Aborted — sync check failed." >&2; exit 1; }
git switch -c "plan/${ISSUE_NUMBER}-<slug>"
```

If no doc gaps were found (Phase 5 will be skipped), skip this step.

### Phase 5 — Update Docs (conditional)

**For both types** — only if Phase 4 identified a concrete gap (docs changes
are optional; skip this phase if no gap was found).

- **`specs/<topic>.yaml`** — Add or amend requirements. Follow
  `specs/meta-specifications.yaml` conventions (ID scheme `PREFIX-NN-NNN`,
  RFC 2119 keywords). Update `specs/README.md` if adding a new file.
- **`notes/<topic>.md`** — Add design decisions, pitfalls, or implementation
  guidance. Every `notes/*.md` must have valid YAML frontmatter (`title`,
  `status`). Update `notes/README.md` if adding a new file.
- **`AGENTS.md`** — Append a new pitfall entry to the
  **Common Pitfalls** section if Phase 4 identified a recurring agent gap.
- **ADR** — Draft `docs/adr/NNNN-<slug>.md` alongside the spec if the ADR
  determination in Phase 4 recommended one (applies to both Ideas and
  Concerns; see `notes/specs-vs-adrs.md`).

Track created filenames:

```bash
SPEC_FILE=""    # e.g., "actor-discovery.yaml"; empty if no spec created
NOTES_FILE=""   # e.g., "actor-discovery.md"; empty if no notes created
```

### Phase 6 — Lint Markdown (if docs changed)

Invoke the `format-markdown` skill on all new/modified markdown files.
Fix all errors before proceeding.

### Phase 7 — Open Docs-Only PR (if docs changed)

Only if Phase 5 produced file changes:

```bash
git add specs/ notes/ docs/adr/ AGENTS.md
git commit -m "docs: plan issue #${ISSUE_NUMBER} — <short title>

- <bullet: what was added or changed>

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin "plan/${ISSUE_NUMBER}-<slug>"

gh pr create --repo CERTCC/Vultron \
  --title "docs: plan issue #${ISSUE_NUMBER} — <short title>" \
  --body "- Closes #${ISSUE_NUMBER}

## Summary

<1–2 sentences: what was planned and what docs/specs were produced>

## Changes

- <bullet: what was added or changed>" \
  --label "specs-notes"
```

> For both Idea and Concern, `Closes #N` in the PR body closes the issue
> on merge. If no docs PR is opened, close the issue directly in Phase 9
> instead (applies to both types).

### Phase 8 — Create Implementation Issue(s)

Create one GitHub issue per distinct AC cluster from Phase 3.
Use `manage-github-issue` for relationship wiring.

For both types, wire the impl issue as **blocked-by the source issue** and
as **child of the parent epic** (if `EPIC_NUMBER` is non-empty):

```bash
PARENT_ARG=""
[ -n "${EPIC_NUMBER}" ] && PARENT_ARG="--parent ${EPIC_NUMBER}"

IMPL_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<Implementation title from grill-me>" \
  --body "## Summary
<Description>

## Acceptance Criteria
- [ ] AC-1: <from grill-me>

## Reference
Source: #${ISSUE_NUMBER}
$([ -n "${SPEC_FILE}" ] && echo "Spec: \`specs/${SPEC_FILE}\`")
$([ -n "${NOTES_FILE}" ] && echo "Notes: \`notes/${NOTES_FILE}\`")" \
  --label "size:<S|M|L>" \
  ${PARENT_ARG} \
  --blocked-by "${ISSUE_NUMBER}")
```

Repeat for each additional impl issue. Set `size:` by AC count:
1–2 → `size:S`; 3–6 → `size:M`; 7+ → `size:L`.

Add each new issue to Project #24:

```bash
bash .agents/skills/shared/add-to-project.sh "${IMPL_NUMBER}"
```

### Phase 9 — Archive and Close

Invoke the `archive-history` skill (after PR URL is known):

**Idea:**

```text
TYPE    = idea
TITLE   = <short idea title>
SOURCE  = IDEA-<ISSUE_NUMBER>
BODY    = Full original idea text
          + "**Processed**: YYYY-MM-DD — implementation tracked in #<IMPL_NUMBER>."
          + "Docs PR: <PR_URL>." (if docs PR was opened)
          + "Spec: `specs/${SPEC_FILE}`." (if spec was written)
          + "Notes: `notes/${NOTES_FILE}`." (if notes were written)
```

**Concern:**

```text
TYPE    = learning
TITLE   = <short concern title>
SOURCE  = CONCERN-<ISSUE_NUMBER>
BODY    = Full original concern body
          + "**Resolved**: YYYY-MM-DD — implementation tracked in #<N>
            [, #<M> ...]."
          + "Docs PR: <PR_URL>." (if docs PR was opened)
          + "Spec: `specs/${SPEC_FILE}`." (if spec was written)
          + "Notes: `notes/${NOTES_FILE}`." (if notes were written)
```

Then post a resolution comment and close:

```bash
gh issue comment "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --body "✅ Planned.

$([ -n "${PR_URL}" ] && echo "- Docs PR: ${PR_URL}")
$(for n in "${IMPL_NUMBERS[@]}"; do echo "- Implementation issue: #${n}"; done)
$([ -n "${SPEC_FILE}" ] && echo "Spec: \`specs/${SPEC_FILE}\`.")
$([ -n "${NOTES_FILE}" ] && echo "Notes: \`notes/${NOTES_FILE}\`.")"

# Only close directly when no docs PR was opened (applies to both types).
# When a PR exists, Closes #N in the PR body closes the issue on merge.
if [ -z "${PR_URL}" ]; then
  gh issue close "${ISSUE_NUMBER}" --repo CERTCC/Vultron
fi
```

---

## Checklist

- [ ] Issue identified (user-specified or selected from list)
- [ ] Issue body fetched; type auto-detected (Idea or Concern); issue is open
- [ ] `orient-agent` invoked
- [ ] `deepen-context` invoked with focus hints from the issue
- [ ] All grill-me branches resolved
- [ ] `deepen-context` re-invoked if new focus areas emerged during grilling
- [ ] Task branch created (`plan/<N>-<slug>`) — if docs changes expected
- [ ] Docs updated — optional for both types (or consciously skipped with a note)
- [ ] Markdown lint clean (if docs changed)
- [ ] Docs-only PR opened with `specs-notes` label — or skipped (no doc changes)
- [ ] Implementation issue(s) created via `manage-github-issue` + `add-to-project.sh`
- [ ] Impl issues wired blocked-by source issue + child of epic (if any)
- [ ] Issue archived via `archive-history` (after PR URL known)
- [ ] Issue commented with impl issue(s) + optional PR URL; closed appropriately

---

## Conventions

- **Branch name**: `plan/<N>-<slug>` (only created if docs changed)
- **History source**: `IDEA-<N>` for Ideas; `CONCERN-<N>` for Concerns
- **History type**: `idea` for Ideas; `learning` for Concerns
- **Spec file names**: lowercase hyphenated `.yaml` in `specs/`
- **Notes file names**: same base name as spec, `.md` in `notes/`
- **Close behavior**: `Closes #N` in the PR body closes on merge for both
  types. If no docs PR is opened, close directly after archive (applies to
  both types).
- **Project board**: all new issues added with `Schedule=Someday` via
  `shared/add-to-project.sh`

## Relationship to Other Skills

| Skill | Input | Docs output | Closes issue? |
|---|---|---|---|
| `plan-issue` | One Idea or Concern issue | Optional specs+notes for both types | Yes |
| `learn` | plan/incoming/learnings/ + all Concern issues | specs/notes/AGENTS | Yes (batch) |
| `new-item` | Freeform text | None | N/A (creates, not resolves) |
| `process-concerns` | CONCERNS.md file | None | No |
