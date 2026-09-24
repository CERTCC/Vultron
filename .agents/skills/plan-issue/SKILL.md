---
name: plan-issue
description: >
  Convert an open GitHub Idea, Concern, or Epic issue — or a bundle of them —
  into a concrete implementation plan. Deepens context from the issue first, then runs a
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

If the user provided a GitHub issue number, skip to Phase 1. **Several numbers
is a bundle**: plan all of them in one PR that closes every member, per
`.agents/skills/shared/bundling.md` § "Executing a bundle". Every member must be
an Idea, Concern, or Epic (name the right skill for any that is not), one
grill-me interview covers the whole bundle, and each member still gets its own
implementation issues and its own disposition in Phase 9.

Otherwise, query open issues of all three types and present as a combined
multiple-choice list via `ask_user`:

```bash
# Ideas and Concerns
gh issue list --repo CERTCC/Vultron --state open --limit 1000 \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Idea" or .issueType.name == "Concern")
        | "#\(.number) [\(.issueType.name)]: \(.title)"'

# Epics with needs-decomposition label only
gh issue list --repo CERTCC/Vultron --state open --limit 1000 \
  --label "needs-decomposition" \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Epic")
        | "#\(.number) [Epic/needs-decomposition]: \(.title)"'
```

Include a **"Create a new Idea"** option at the end. Wait for the user's
selection before continuing.

#### Creating a new Idea (if selected)

Ask the user to describe the idea (`ask_user`, freeform). Synthesize a
short title. Then select a parent epic (query open Epics and ask the user to
confirm — see `new-item` Phase 4 for the pattern) and a milestone (see
`shared/issue-creation-requirements.md`). Then create:

```bash
IDEA_TYPE_ID=$(bash .agents/skills/shared/board-id.sh issue-type Idea)
ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "${TITLE}" \
  --body "${BODY}" \
  --issue-type-id "${IDEA_TYPE_ID}" \
  --parent "${EPIC_NUMBER}" \
  --milestone "${MILESTONE_NUMBER}")
```

### Phase 0b — Sync

Move the worktree HEAD to `origin/main` before loading any context, so all
planning (orient, deepen-context, grill-me) is based on the current state of
specs and notes. Do **not** use `git checkout main` — that branch may be
checked out in another worktree.

```bash
git fetch origin main && git reset --hard origin/main
```

If this fails, stop and investigate before proceeding.

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

### Phase 1b — Claim the Issue and Create Task Branch

Claim the issue now — as soon as it is validated — so others can see work
has started. Derive `<slug>` from the issue title (lowercase, hyphenated).
Delegate to `claim-issue.sh` for idempotency guard, branch creation,
assignee, and claim comment — exactly as `build` and `bugfix` do:

```bash
bash .agents/skills/shared/claim-issue.sh "${ISSUE_NUMBER}" plan "<slug>" \
  ${OTHER_MEMBERS[@]+"${OTHER_MEMBERS[@]}"}
```

### Phase 2 — Orient (invoke `orient-agent`)

Invoke the `orient-agent` skill to load required baseline context.

### Phase 3 — Deepen Context (invoke `deepen-context`)

Invoke the `deepen-context` skill, using focus hints derived from the issue
title and body (e.g., "wire layer", "BT integration", "embargo lifecycle").
This ensures the grill-me interview in Phase 4 starts from an informed
baseline rather than blank-slate context.

### Phase 4 — Grill-Me Interview (invoke `grill-me`)

Invoke the `grill-me` skill. The interview is conversation-driven and
bottom-up — conclusions (scope, ACs, ADR, options, recommendation) emerge
from the discussion rather than being asked as structured questions.

**General pattern (all types):**

1. **Prior-art search (before the synthesis brief):** Load
   `.agents/skills/shared/compose-before-create.md` and search for existing
   helpers, use cases, or base classes that match the domain nouns in the
   issue title and body. This surfaces reuse opportunities before acceptance
   criteria are drafted. Record any findings — they become the `## Prior Art`
   section of the implementation issues created in Phase 8; omit the section
   if nothing is found.

2. **Open with a short brief** — Before asking anything, give a few bullets
   on what the research from Phase 3 reveals: what the issue says, what the
   current codebase/specs show, any prior-art findings from step 1, and 2–3
   plausible directions, each described in a line. End with **one specific
   question** — never "is this accurate?" about the whole block.

3. **Conversation** — Walk through the problem bottom-up. Ask clarifying
   questions as understanding builds. Do not impose a predetermined question
   structure. Scope, ACs, and ADR applicability are conclusions to confirm,
   not questions to ask.

4. **Signal the transition** — When understanding is forming, say so:
   "I think we're almost there — here's what I have so far. Got more?"
   Do not declare done unilaterally.

5. **Confirm conclusions** — After the user closes the conversation, list the
   plan as a short numbered list, one plain-language line per decision: what
   to implement, what docs to update, whether an ADR is warranted. Write every
   item out in full — never refer back by number or bare ID. The user says
   which lines are wrong; this is not a new round of questions.

Every question follows `.agents/skills/shared/asking-the-user.md` (one at a
time, problem before decision, plain language, no bare IDs).

**Type-specific opening and conversation guidance:** see the loaded
companion file.

Do **not** write anything until grill-me is complete.

If the interview surfaces focus areas not covered in Phase 3, invoke
`deepen-context` again with those additional hints before proceeding.

### Phase 5 — Update Docs (conditional)

Only if Phase 4 identified a concrete gap. See the loaded companion file for
which files to update per type.

- **`specs/<topic>.yaml`** — Add or amend requirements. Follow
  `specs/meta-specifications.yaml` conventions (ID scheme `PREFIX-NN-NNN`,
  RFC 2119 keywords). Update `specs/README.md` if adding a new file.
- **`notes/<topic>.md`** — Add design decisions, pitfalls, or implementation
  guidance. Every `notes/*.md` must have valid YAML frontmatter (`title`,
  `status`). Update `notes/README.md` if adding a new file.
- **`AGENTS.md`** — If Phase 4 identified a recurring agent gap (Concern type
  only), route the pitfall per
  [`notes/agents-md-structure.md`](../../../notes/agents-md-structure.md): the
  write-up goes in the nearest `notes/` or per-directory `AGENTS.md`, and root's
  **Common Pitfalls** index gets *at most* an extended table cell. Do **not**
  append to root — it sits at exactly its 400-line budget and
  `test/metadata/test_agents_md_size_ratchet.py` fails CI on line 401.
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

### Phase 7 — Open PR

Always open a PR. If Phase 5 produced doc changes, commit them first:

```bash
# Only if Phase 5 produced file changes:
git add specs/ notes/ docs/adr/ AGENTS.md
git commit -m "docs: plan issue #${ISSUE_NUMBER} — <short title>

- <bullet: what was added or changed>"
```

Then invoke the `create-pr` skill:

```text
type:         docs
title:        docs: plan issue #<N> — <short title>
body:         <composed per pr-body-guide.md docs template>
labels:       specs-notes
issue_number: <N>   (omit for Epics — the Epic must not be closed by the docs PR)
```

`create-pr` performs the rebase on `origin/main`, runs linters, pushes, and
returns the PR URL. Use the returned URL in the `archive-history` call (Phase 9).

> For Ideas and Concerns, include `issue_number` so the PR body contains
> `Closes #N`. For Epics, omit `issue_number` — the Epic must not be closed
> by the docs PR.
>
> For a bundle, pass the first member as `issue_number` and put one
> `- Closes #N` line per **non-Epic** member at the top of the body, in bundle
> order (`bundling.md` § "Executing a bundle"). An Epic member never gets a
> `Closes` line, even inside a bundle.
>
> Even when Phase 5 produced no doc changes the PR must still be opened — the
> history entry (Phase 9) will be committed to this branch and ride along with
> it to main.

### Phase 8 — Create Implementation Issues

Create one Task sub-issue per distinct AC cluster from Phase 4.

Before creating, resolve the milestone to carry forward:

```bash
MILESTONE_NUMBER=$(gh issue view "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --json milestone --jq '.milestone.number // ""')
# If the source issue has no milestone, query open milestones and ask the user
# to pick one (see shared/issue-creation-requirements.md for defaults).
```

For Ideas and Concerns, wire the impl issue as **blocked-by the source
issue** and as **child of the parent epic**. `manage_github_issue.sh` requires
`--parent` on create, so if `EPIC_NUMBER` is empty, resolve it **before** the
create call: invoke **`calve-epics`** (Mode 1) to find the epic the impl issue
matches, and if it finds none, follow "A parent epic is mandatory" below
(#3591).

```bash
TASK_TYPE_ID=$(bash .agents/skills/shared/board-id.sh issue-type Task)

# Body template. Include the "## Prior Art" heading and its bullets only
# when Phase 4 found relevant helpers, use cases, or base classes; delete
# both entirely when the prior-art search returned no results (AC-3 in
# #2646). Instructions stay in these comments, never inside --body, or
# they are posted verbatim (#2770). Pass --parent unconditionally: a
# conditional ${VAR:+--parent "${VAR}"} is one word under zsh (#2771).
IMPL_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<Implementation title from grill-me>" \
  --body "## Summary
<Description>

Governing specs: <spec/group IDs, e.g. CS-02-003, EM-04> ← or \"none — <reason>\"

## Acceptance Criteria
- [ ] AC-1: <from grill-me>

## Prior Art
- <existing helper / use case / base class and its location>

## Reference
Source: #${ISSUE_NUMBER}
$([ -n "${PR_URL}" ] && echo "Docs PR: ${PR_URL}")
$([ -n "${SPEC_FILE}" ] && echo "Spec: \`specs/${SPEC_FILE}\`")
$([ -n "${NOTES_FILE}" ] && echo "Notes: \`notes/${NOTES_FILE}\`")" \
  --issue-type-id "${TASK_TYPE_ID}" \
  --label "size:<S|M|L>" \
  --parent "${EPIC_NUMBER}" \
  --milestone "${MILESTONE_NUMBER}" \
  --blocked-by "${ISSUE_NUMBER}")
```

**`Governing specs:` is required in every impl issue body.** List the spec
IDs (or group IDs) the work must satisfy: draw them from the Spec manifest
`deepen-context` emitted in Phase 3 (floor + selected entries that apply to
this AC cluster) plus any requirements added in Phase 5. Leave it empty only
as an explicit `none — <reason>`. `build` and `bugfix` pass this line to
`deepen-context` as the spec floor, so a missing line means the implementer
loads no task-specific specs by default. See
`.agents/skills/shared/issue-creation-requirements.md` § "Governing specs".

For Epics, see the `epic.md` companion file — Tasks are wired as sub-issues
of the Epic itself, not blocked-by it.

Repeat for each additional impl issue. Set `size:` from the AC count with
`PYTHONPATH= uv run pr-size --acs <N> --quiet` — an **estimate**, per
`.agents/skills/shared/sizing.md`. Never `size:XL`: an issue that large is a
decomposition signal, and the band is measurement-only (PAD-05-012).

Add each new issue to Project #24:

```bash
bash .agents/skills/shared/add-to-project.sh "${IMPL_NUMBER}"
```

**The impl issue is already on the epic forest.** Because its parent epic is
resolved before the create call, it is a sub-issue of that epic and inherits
the epic's Schedule tier — leave it there.

**A parent epic is mandatory.** If `calve-epics` Mode 1 finds no match, do
**not** create the issue at root. Instead use `AskUserQuestion` to present the
full list of open epics and require the user to select the best fit. If the
user determines a new epic is warranted, run `calve-epics` Mode 2 to propose
and confirm it before closing this skill. An impl issue without a parent epic
is invisible to prioritisation and blocks future sprint planning — never ship
one orphaned.

### Phase 8b — Add Implementation Issue References to Docs PR (Ideas and Concerns only)

After all impl issues are created, edit the PR body to add a forward-tracing
section. This ensures the docs PR links forward to the work it spawned.

Collect all impl issue numbers created in Phase 8 into `IMPL_NUMBERS` (array).
Then compose an edit to the PR body:

```bash
IMPL_LIST=""
for n in "${IMPL_NUMBERS[@]}"; do
  IMPL_LIST="${IMPL_LIST}
- #${n}"
done

# Append to existing PR body (or patch inline if section already present)
CURRENT_BODY=$(gh pr view "${PR_URL}" --repo CERTCC/Vultron --json body --jq '.body')
NEW_BODY="${CURRENT_BODY}

## Implementation Issues
${IMPL_LIST}"

gh pr edit "${PR_URL}" --repo CERTCC/Vultron --body "${NEW_BODY}"
```

Skip this step for Epics — the Epic docs PR does not close the source issue
and the impl issues are wired differently.

### Phase 9 — Archive, Close, or Annotate

See the loaded companion file for the type-specific completion step:

- **Idea**: invoke `archive-history`, post resolution comment, close issue
- **Concern**: invoke `archive-history`, post resolution comment, close issue
- **Epic**: remove `needs-decomposition` label, post summary comment, leave open

---

## Checklist

- [ ] Issue identified (user-specified or selected from list)
- [ ] Worktree reset to `origin/main` (Phase 0b — planning baseline)
- [ ] Issue body fetched; type auto-detected (Idea, Concern, or Epic); issue is open
- [ ] Type-specific companion file loaded (`idea.md`, `concern.md`, or `epic.md`)
- [ ] Issue claimed via `claim-issue.sh` (`plan/<N>-<slug>`) — always (Phase 1b)
- [ ] `orient-agent` invoked
- [ ] `deepen-context` invoked with focus hints from the issue
- [ ] Grill-me conversation complete — conclusions confirmed as proposals (scope, ACs, ADR, options)
- [ ] `deepen-context` re-invoked if new focus areas emerged during grilling
- [ ] Docs updated — optional for all types (or consciously skipped with a note)
- [ ] Markdown lint clean (if docs changed)
- [ ] PR opened with `specs-notes` label — always
- [ ] Implementation issue(s) created via `manage-github-issue` + `add-to-project.sh` (with type, parent epic, and milestone set)
- [ ] Every impl issue body has a `Governing specs:` line (IDs, or `none — <reason>`)
- [ ] Impl issues wired per type (blocked-by for Ideas/Concerns; sub-issue for Epics)
- [ ] Impl issues reference docs PR URL in their body (Ideas/Concerns only — Phase 8)
- [ ] Docs PR body updated with Implementation Issues section (Ideas/Concerns only — Phase 8b)
- [ ] Completion step executed per type (archive+close for Ideas/Concerns; annotate for Epics)

---

## Conventions

- **Branch name**: `plan/<N>-<slug>` (always created via `claim-issue.sh` in Phase 1b)
- **History source**: `IDEA-<N>` for Ideas; `CONCERN-<N>` for Concerns (not used for Epics)
- **History type**: `idea` for Ideas; `learning` for Concerns (not used for Epics)
- **Spec file names**: lowercase hyphenated `.yaml` in `specs/`
- **Notes file names**: same base name as spec, `.md` in `notes/`
- **Close behavior**: `Closes #N` in the PR body closes on merge for Ideas
  and Concerns. Epics are never closed by this skill.
- **Project board**: new issues are added via `shared/add-to-project.sh`, then
  routed onto the epic forest via `calve-epics` (Mode 1) — inheriting the parent
  epic's Schedule tier. Only true orphans (no matching epic) stay at
  `Schedule=Someday` as calving candidates.

## Relationship to Other Skills

| Skill | Input | Docs output | Closes issue? |
|---|---|---|---|
| `plan-issue` (Idea) | One Idea issue | Optional specs+notes | Yes |
| `plan-issue` (Concern) | One Concern issue | Optional specs+notes | Yes |
| `plan-issue` (Epic) | One Epic issue | Optional specs+notes | No — annotates only |
| `learn` | plan/incoming/learnings/ + all Concern issues | specs/notes/AGENTS | Yes (batch) |
| `new-item` | Freeform text | None | N/A (creates, not resolves) |
| `process-concerns` | CONCERNS.md file | None | No |
