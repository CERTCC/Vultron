---
name: plan-issue
description: >
  Convert a single open GitHub Idea, Concern, or Epic issue into a concrete
  implementation plan. Deepens context from the issue first, then runs a
  grill-me interview to understand scope, creates implementation issues,
  optionally updates specs/notes, and closes or annotates the source issue
  appropriately. Auto-detects type from the GitHub issue type. Use when the
  user references an Idea, Concern, or Epic issue number, or says "plan this
  idea/concern/epic".
---

# Skill: Plan Issue

Convert an open GitHub `type:Idea`, `type:Concern`, or `type:Epic` issue into
an implementation plan: interview → explore → create impl issues →
optionally update docs → archive/close (Ideas and Concerns) or annotate
(Epics).

Type-specific interview questions, docs output, and completion steps are in
the companion files alongside this one:

- `idea.md` — Idea-specific interview and archive/close steps
- `concern.md` — Concern-specific interview and archive/close steps
- `epic.md` — Epic validation (Phase A) and decomposition (Phase B) steps

Load only the file matching the detected issue type.

## Constants

See `.agents/skills/shared/README.md` for project IDs and issue type IDs.

---

## Workflow

### Phase 0 — Select the Issue

If the user provided a GitHub issue number, skip to Phase 1.

Otherwise, query open issues of all three types and present as a combined
multiple-choice list via `ask_user`:

```bash
# Ideas and Concerns
gh issue list --repo CERTCC/Vultron --state open --limit 200 \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Idea" or .issueType.name == "Concern")
        | "#\(.number) [\(.issueType.name)]: \(.title)"'

# Epics with needs-decomposition label only
gh issue list --repo CERTCC/Vultron --state open --limit 200 \
  --label "needs-decomposition" \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Epic")
        | "#\(.number) [Epic/needs-decomposition]: \(.title)"'
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
if [ "${ISSUE_TYPE}" != "Idea" ] && \
   [ "${ISSUE_TYPE}" != "Concern" ] && \
   [ "${ISSUE_TYPE}" != "Epic" ]; then
  echo "❌ #${ISSUE_NUMBER} is type '${ISSUE_TYPE}', expected Idea, Concern, or Epic." >&2
  exit 1
fi
```

**Load the type-specific companion file** matching `${ISSUE_TYPE}`:
`idea.md`, `concern.md`, or `epic.md`. All type-specific steps below
reference that file.

For all types, also query the parent epic (if any):

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
baseline rather than blank-slate context.

### Phase 4 — Grill-Me Interview (invoke `grill-me`)

Invoke the `grill-me` skill. Resolve every decision branch one at a time
via `ask_user`, providing a recommendation for each.

**Shared base questions (all types):**

1. **Scope** — What is in scope? What is explicitly out of scope?
2. **Acceptance criteria** — How do we verify this is fully addressed?
   Drive one GitHub issue per distinct AC cluster.
3. **ADR determination** — Apply the `notes/specs-vs-adrs.md` decision tree
   (MS-11-001 through MS-11-006). Form a recommendation with reasoning.
   Present for approval before proceeding.

**Type-specific questions:** see the loaded companion file.

Do **not** write anything until grill-me is complete.

If the interview surfaces focus areas not covered in Phase 3, invoke
`deepen-context` again with those additional hints before proceeding.

### Phase 4b — Create Task Branch (if docs changes are expected)

If grill-me established that Phase 5 will produce file writes, create the
branch **before** writing any files:

```bash
bash .agents/skills/shared/sync-check.sh \
  || { echo "❌ Aborted — sync check failed." >&2; exit 1; }
git switch -c "plan/${ISSUE_NUMBER}-<slug>"
```

If no doc gaps were found (Phase 5 will be skipped), skip this step.

### Phase 5 — Update Docs (conditional)

Only if Phase 4 identified a concrete gap. See the loaded companion file for
which files to update per type.

- **`specs/<topic>.yaml`** — Add or amend requirements. Follow
  `specs/meta-specifications.yaml` conventions (ID scheme `PREFIX-NN-NNN`,
  RFC 2119 keywords). Update `specs/README.md` if adding a new file.
- **`notes/<topic>.md`** — Add design decisions, pitfalls, or implementation
  guidance. Every `notes/*.md` must have valid YAML frontmatter (`title`,
  `status`). Update `notes/README.md` if adding a new file.
- **`AGENTS.md`** — Append a new pitfall entry to the **Common Pitfalls**
  section if Phase 4 identified a recurring agent gap (Concern type only).
- **ADR** — Draft `docs/adr/NNNN-<slug>.md` if the ADR determination
  recommended one.

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

> For Ideas and Concerns, `Closes #N` in the PR body closes the issue on
> merge. For Epics, omit `Closes #N` — the Epic must not be closed by the
> docs PR.

### Phase 8 — Create Implementation Issues

Create one Task sub-issue per distinct AC cluster from Phase 4.

For Ideas and Concerns, wire the impl issue as **blocked-by the source
issue** and as **child of the parent epic** (if `EPIC_NUMBER` is non-empty):

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

For Epics, see the `epic.md` companion file — Tasks are wired as sub-issues
of the Epic itself, not blocked-by it.

Repeat for each additional impl issue. Set `size:` by AC count:
1–2 → `size:S`; 3–6 → `size:M`; 7+ → `size:L`.

Add each new issue to Project #24:

```bash
bash .agents/skills/shared/add-to-project.sh "${IMPL_NUMBER}"
```

### Phase 9 — Archive, Close, or Annotate

See the loaded companion file for the type-specific completion step:

- **Idea**: invoke `archive-history`, post resolution comment, close issue
- **Concern**: invoke `archive-history`, post resolution comment, close issue
- **Epic**: remove `needs-decomposition` label, post summary comment, leave open

---

## Checklist

- [ ] Issue identified (user-specified or selected from list)
- [ ] Issue body fetched; type auto-detected (Idea, Concern, or Epic); issue is open
- [ ] Type-specific companion file loaded (`idea.md`, `concern.md`, or `epic.md`)
- [ ] `orient-agent` invoked
- [ ] `deepen-context` invoked with focus hints from the issue
- [ ] All grill-me branches resolved (shared + type-specific)
- [ ] `deepen-context` re-invoked if new focus areas emerged during grilling
- [ ] Task branch created (`plan/<N>-<slug>`) — if docs changes expected
- [ ] Docs updated — optional for all types (or consciously skipped with a note)
- [ ] Markdown lint clean (if docs changed)
- [ ] Docs-only PR opened with `specs-notes` label — or skipped (no doc changes)
- [ ] Implementation issue(s) created via `manage-github-issue` + `add-to-project.sh`
- [ ] Impl issues wired per type (blocked-by for Ideas/Concerns; sub-issue for Epics)
- [ ] Completion step executed per type (archive+close for Ideas/Concerns; annotate for Epics)

---

## Conventions

- **Branch name**: `plan/<N>-<slug>` (only created if docs changed)
- **History source**: `IDEA-<N>` for Ideas; `CONCERN-<N>` for Concerns (not used for Epics)
- **History type**: `idea` for Ideas; `learning` for Concerns (not used for Epics)
- **Spec file names**: lowercase hyphenated `.yaml` in `specs/`
- **Notes file names**: same base name as spec, `.md` in `notes/`
- **Close behavior**: `Closes #N` in the PR body closes on merge for Ideas
  and Concerns. Epics are never closed by this skill.
- **Project board**: all new issues added with `Schedule=Someday` via
  `shared/add-to-project.sh`

## Relationship to Other Skills

| Skill | Input | Docs output | Closes issue? |
|---|---|---|---|
| `plan-issue` (Idea) | One Idea issue | Optional specs+notes | Yes |
| `plan-issue` (Concern) | One Concern issue | Optional specs+notes | Yes |
| `plan-issue` (Epic) | One Epic issue | Optional specs+notes | No — annotates only |
| `learn` | plan/incoming/learnings/ + all Concern issues | specs/notes/AGENTS | Yes (batch) |
| `new-item` | Freeform text | None | N/A (creates, not resolves) |
| `process-concerns` | CONCERNS.md file | None | No |
