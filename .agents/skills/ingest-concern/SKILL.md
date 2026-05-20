---
name: ingest-concern
description: >
  Process a single open GitHub Concern-type issue into a concrete action plan:
  runs a grill-me interview to understand root cause, options, and fix scope,
  then creates one or more GitHub implementation issues and optionally updates
  specs/ or notes/ when the concern reveals missing documentation. Archives the
  concern via `uv run append-history learning`, comments resolution links on
  the concern issue, and closes it. Opens a docs-only PR (specs-notes label)
  only when specs/notes/AGENTS.md files are changed. Use when the user says
  "ingest concern", references an open Concern-type GitHub issue number, or
  wants to convert a tracked concern into an implementation plan with tickets.
---

# Skill: Ingest Concern

Convert a single open GitHub `type:Concern` issue into a concrete action plan.
Interview → explore → create impl issues → optionally update docs → archive +
close the concern.

## Constants

```text
REPO           = CERTCC/Vultron
REPO_NODE_ID   = R_kgDOIn77fA
CONCERN_TYPE   = IT_kwDOAjf0s84B_2VT
```

---

## Workflow

### Phase 0 — Select the Concern

If the user provided a GitHub issue number (e.g., `#42` or just `42`),
skip to Phase 1.

Otherwise, query open Concern-type issues and present them as a
multiple-choice list via `ask_user`:

```bash
gh issue list \
  --repo CERTCC/Vultron \
  --state open \
  --limit 200 \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Concern") | "#\(.number): \(.title)"'
```

Build a `choices` array from the results and wait for the user's selection.

### Phase 1 — Read the Concern

Fetch the full issue:

```bash
gh issue view "${CONCERN_NUMBER}" \
  --repo CERTCC/Vultron \
  --json number,title,body,labels
```

Use the title and body as source material for all subsequent steps.

### Phase 2 — Study Context

Invoke the `study-project-docs` skill. It loads all specs, reads `plan/`,
`docs/adr/`, `notes/`, `AGENTS.md`, and `docs/reference/codebase/`.

Explore the codebase files referenced in the concern's **Evidence** section.
Answer questions from exploration rather than asking the user where possible.

### Phase 3 — Grill-Me Exploration

Invoke the `grill-me` skill. Resolve every decision branch one at a time via
`ask_user`, providing a recommendation for each. Cover:

1. **Root cause** — What is actually broken, risky, or missing? Is the concern
   accurately scoped?
2. **Impact** — If left unaddressed, what fails or degrades?
3. **Options** — What are 2–3 ways to address this concern?
4. **Recommended approach** — Which option do we go with, and why?
5. **Acceptance criteria** — How do we verify the concern is fully resolved?
   (Drive one GitHub issue per distinct AC cluster.)
6. **Spec / notes gaps** — Does this concern reveal a missing requirement in
   `specs/` or a missing design decision in `notes/`? If so, which file and
   what should be added or changed?
7. **AGENTS.md gap** — Is there a recurring implementation pitfall that agents
   need to know about? If so, what's the canonical pitfall text?

Do **not** write anything until grill-me is complete.

### Phase 4 — Update Specs / Notes (optional)

Only proceed if Phase 3 established a concrete spec or notes gap.

- **`specs/<topic>.yaml`** — Add or amend requirements that the concern
  reveals are missing. Follow `specs/meta-specifications.yaml` conventions
  (ID scheme `PREFIX-NN-NNN`, RFC 2119 keywords, YAML structure).
  Update `specs/README.md` if a new file is added.
- **`notes/<topic>.md`** — Add a design decision or pitfall entry derived
  from the concern. Every `notes/*.md` must have valid YAML frontmatter
  (`title`, `status`). Update `notes/README.md` if a new file is added.
- **`AGENTS.md`** — Append a new pitfall entry in the
  **Common Pitfalls (Lessons Learned)** section if Phase 3 identified a
  recurring agent guidance gap.

Skip this phase entirely if grill-me did not surface a documentation gap.

### Phase 5 — Create Implementation Issues

Create one GitHub issue per distinct cluster of acceptance criteria identified
in Phase 3. Use the `manage-github-issue` skill for each issue so structured
relationships are wired correctly.

Wire the concern issue as the **parent** of each implementation issue. If the
implementation issues have a natural sequence, wire the later ones as
`--blocked-by` the earlier ones.

```bash
IMPL_ISSUE_NUMBER=$(
  .agents/skills/manage-github-issue/manage_github_issue.sh \
    --title "<Implementation title from grill-me>" \
    --body "## Summary

<One paragraph describing what needs to be done, derived from grill-me.>

## Acceptance Criteria

- [ ] AC-1: <from grill-me>
- [ ] AC-2: <from grill-me>

## Reference

Concern: #${CONCERN_NUMBER}
$([ -n "${SPEC_FILE}" ] && echo "Spec: \`specs/${SPEC_FILE}\`")
$([ -n "${NOTES_FILE}" ] && echo "Notes: \`notes/${NOTES_FILE}\`")" \
    --label "group:unscheduled,size:<S|M|L>" \
    --parent "${CONCERN_NUMBER}"
    # Add --blocked-by N for sequenced issues
)
echo "Created impl issue #${IMPL_ISSUE_NUMBER}"
```

Set `size:` based on AC count: 1–2 → `size:S`; 3–6 → `size:M`; 7+ → `size:L`.

### Phase 6 — Lint Markdown (if docs changed)

If Phase 4 modified any files, invoke the `format-markdown` skill on all
new/modified markdown files. Fix all errors before proceeding.

### Phase 7 — Open a Docs-Only PR (if docs changed)

Only if Phase 4 produced file changes:

```bash
FRESHEN="$HOME/.copilot/skills/manage-worktree/scripts/manage_worktree.sh"
[ -f "$FRESHEN" ] && bash "$FRESHEN" freshen
git switch -c ingest/concern-${CONCERN_NUMBER}-<slug>
git add specs/ notes/ AGENTS.md
git commit -m "docs: ingest concern #${CONCERN_NUMBER} — <short title>

- <bullet: what spec/notes/AGENTS.md was added or changed>
- Concern originated in #${CONCERN_NUMBER}

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin ingest/concern-${CONCERN_NUMBER}-<slug>

gh pr create --repo CERTCC/Vultron \
  --title "docs: ingest concern #${CONCERN_NUMBER} — <short title>" \
  --body "Docs-only PR: addresses concern #${CONCERN_NUMBER} at the spec/notes
level. Implementation tracked in #${IMPL_ISSUE_NUMBER}.

Ref #${CONCERN_NUMBER}

No .py files changed." \
  --label "specs-notes"
```

### Phase 8 — Archive and Close the Concern

Archive the concern via `uv run append-history learning`:

```bash
cat <<'EOF' | uv run append-history learning \
    --title "<short concern title>" \
    --source "CONCERN-${CONCERN_NUMBER}"

## #${CONCERN_NUMBER} <concern title>

<full original concern body here>

**Resolved**: YYYY-MM-DD — implementation tracked in #${IMPL_ISSUE_NUMBER}.
$([ -n "${PR_URL}" ] && echo "Docs PR: ${PR_URL}.")
EOF
```

Then post a resolution comment and close the concern:

```bash
gh issue comment "${CONCERN_NUMBER}" --repo CERTCC/Vultron \
  --body "✅ Ingested.

$([ -n "${PR_URL}" ] && echo "- Docs PR: ${PR_URL}")
$(for n in ${IMPL_ISSUE_NUMBERS}; do echo "- Implementation issue: #${n}"; done)

Root cause and fix plan captured via grill-me session.
$([ -n "${SPEC_FILE}" ] && echo "Spec: \`specs/${SPEC_FILE}\`.")
$([ -n "${NOTES_FILE}" ] && echo "Notes: \`notes/${NOTES_FILE}\`.")"

gh issue close "${CONCERN_NUMBER}" --repo CERTCC/Vultron
```

---

## Checklist

- [ ] Concern issue identified (user-specified or selected from list)
- [ ] Concern body fetched from GitHub
- [ ] `study-project-docs` invoked; evidence files explored
- [ ] All grill-me branches resolved (root cause, options, ACs, doc gaps)
- [ ] `specs/` and/or `notes/` updated — or consciously skipped
- [ ] `AGENTS.md` updated — or consciously skipped
- [ ] Markdown lint clean (if docs changed)
- [ ] One or more implementation issues created via `manage-github-issue`
  with `group:unscheduled` + `size:` labels; concern wired as parent
- [ ] Docs-only PR opened with `specs-notes` label — or skipped (no doc
  changes)
- [ ] Concern archived via `uv run append-history learning
  --source "CONCERN-<N>"`
- [ ] Concern issue commented with impl issue(s) + optional PR URL, then
  closed

---

## Conventions

- **Branch name**: `ingest/concern-<N>-<slug>` (only created if docs changed)
- **History source ID**: `CONCERN-<github_issue_number>`
  (e.g., `CONCERN-42`)
- **`append-history` command**: `uv run append-history learning`
  (same category as `learn` — resolved concerns are learning outcomes)
- **Spec file names**: lowercase hyphenated `.yaml` in `specs/`
- **Notes file names**: same base name as spec, `.md` in `notes/`
- **Label rules** (PAD-02-007): `group:unscheduled` by default; if a
  specific `group:` label is needed, derive slug from priority title in
  kebab-case — no priority numbers in label names. Create the label if
  missing:

  ```bash
  gh label create "group:<slug>" \
    --repo CERTCC/Vultron \
    --description "<Priority group title>" \
    --color "#1d76db"
  ```

## Relationship to Other Skills

| Skill | Input | Docs output | Closes issue? |
|---|---|---|---|
| `ingest-concern` | One Concern issue | Optional specs/notes/AGENTS | Yes |
| `learn` | BUILD_LEARNINGS + all Concern issues | specs/notes/AGENTS | Yes (batch) |
| `new-concern` | Freeform text | None | N/A (creates, not resolves) |
| `process-concerns` | CONCERNS.md file | None | No |
| `ingest-idea` | One Idea issue | Required specs + notes | Yes |
