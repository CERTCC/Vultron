---
name: ingest-idea
description: >
  Process a raw design idea from a GitHub Idea-type issue into formal specs
  and implementation notes, then close the idea issue, open a docs-only PR,
  and create a GitHub implementation Issue as a sub-issue of the idea issue.
  Runs a structured interview (grill-me), writes specs/<topic>.yaml and
  notes/<topic>.md, archives the idea via `uv run append-history idea`, opens
  a docs-only PR with the specs-notes label, and creates a GitHub Issue tagged
  group:unscheduled. Use when the user says "ingest idea", references a GitHub
  Idea issue number, or wants to convert an idea into spec and notes files.
---

# Skill: Ingest Idea

Convert a GitHub Idea-type issue into durable specs and notes, then close the
idea issue and open a docs-only PR. This is the full end-to-end workflow:
interview → write → archive → PR → implementation issue.

## Workflow

### 1. Identify the target idea

If the user specified a GitHub issue number (e.g., `#42` or just `42`),
skip to step 2.

Otherwise, query GitHub for open Idea-type issues and present them to the
user as a multiple-choice list using `ask_user`. Include a **"Create a new
idea"** option at the end.

```bash
gh issue list --repo CERTCC/Vultron \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Idea") | "#\(.number): \(.title)"'
```

Build a `choices` array from the results (e.g. `["#42: Actor discovery",
"#51: Config refactor", "Create a new idea"]`). Wait for the user's
selection before continuing.

#### 1a. Creating a new idea (if selected)

Ask the user to describe the idea in freeform text (using `ask_user`).
Synthesize a short, descriptive title from the description, then create
a GitHub Idea-type issue:

```bash
IDEA_BODY="<freeform description from user>"
IDEA_TITLE="<synthesized title>"
REPO_NODE_ID="R_kgDOIn77fA"
IDEA_TYPE_ID="IT_kwDOAjf0s84B_EoA"

TITLE_JSON=$(printf '%s' "${IDEA_TITLE}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
BODY_JSON=$(printf '%s' "${IDEA_BODY}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

IDEA_NUMBER=$(gh api graphql -f query="
mutation {
  createIssue(input: {
    repositoryId: \"${REPO_NODE_ID}\"
    title: ${TITLE_JSON}
    body: ${BODY_JSON}
    issueTypeId: \"${IDEA_TYPE_ID}\"
  }) {
    issue { number }
  }
}" --jq '.data.createIssue.issue.number')
echo "Created idea issue #${IDEA_NUMBER}"
```

Continue with step 2 using `IDEA_NUMBER`.

### 2. Read the idea

Fetch the idea from GitHub:

```bash
gh issue view "${IDEA_NUMBER}" --repo CERTCC/Vultron --json number,title,body
```

Use the issue title and body as the idea content for all subsequent steps.

### 3. Explore the codebase

Invoke the `study-project-docs` skill. It loads all specs, reads plan/,
docs/adr/, notes/, and AGENTS.md, and scans vultron/ and test/.

Answer questions from exploration rather than asking the user where possible.

### 4. Interview with grill-me

Invoke the `grill-me` skill. Follow its instructions to walk every design
decision branch one at a time using `ask_user`, providing a recommendation
for each question. Reach shared understanding before writing anything.

### 5. Write the spec file

Create or modify `specs/<topic>.yaml` following `specs/meta-specifications.yaml`
conventions:

- Use a `FILE_PREFIX-SECTION_#-###` ID scheme (e.g., `CFG-01-001`)
- Define requirements as YAML structures with RFC 2119 keywords
- Include an overview section with source reference and scope note
- Organize by category with clear section headings

### 6. Write the notes file

Create or modify `notes/<topic>.md` with implementation guidance:

- Decision table (question → decision → rationale)
- Key design patterns and code examples
- Call-site migration guide if replacing existing patterns
- Testing pattern examples
- Layer / import rules relevant to the change

### 7. Update specs/README.md

Add the new spec to both:

- The **Load Contextually** table (topic → file with .yaml extension)
- The **Specification Structure** section (bullet with ID range)

### 8. Lint markdown

Invoke the `format-markdown` skill on all new/modified markdown files. Fix
any errors before proceeding.

### 9. Archive the idea

Build the entry body — the full original idea text with a `**Processed**`
line at the end — and pipe it to `uv run append-history idea` with
`--title` and `--source` flags. Use `IDEA-<number>` (the GitHub issue
number) as the source identifier:

```bash
cat <<'ENDOFENTRY' | uv run append-history idea \
    --title "<short idea title>" \
    --source "IDEA-<IDEA_NUMBER>"

## #<IDEA_NUMBER> <short title>

<full idea title and body here>

**Processed**: YYYY-MM-DD — design decisions captured in
`specs/<topic>.yaml` (ID-01 through ID-NN) and `notes/<topic>.md`.
ENDOFENTRY
```

Then close the idea issue with a comment linking to the docs-only PR and
the implementation issue. (Create the PR first in step 10, then add the
comment after step 11 once both numbers are known.)

```bash
gh issue comment "${IDEA_NUMBER}" --repo CERTCC/Vultron \
  --body "✅ Ingested.

- Docs PR: <PR_URL>
- Implementation issue: #<IMPL_ISSUE_NUMBER>

Design decisions captured in \`specs/<topic>.yaml\` and \`notes/<topic>.md\`."

gh issue close "${IDEA_NUMBER}" --repo CERTCC/Vultron
```

### 10. Open a docs-only PR

Create a branch, commit all spec/notes/README changes, and open a PR
carrying the `specs-notes` label. Reference the originating idea issue in
the PR body so GitHub auto-links them:

```bash
git switch -c ingest/idea-<IDEA_NUMBER>-<slug>
git add specs/<topic>.yaml notes/<topic>.md specs/README.md
git commit -m "specs: ingest idea #<IDEA_NUMBER> — <short title>

- Add specs/<topic>.yaml (ID-01 through ID-NN)
- Add notes/<topic>.md with implementation guidance
- Archive idea #<IDEA_NUMBER> via append-history idea

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin ingest/idea-<IDEA_NUMBER>-<slug>

gh pr create --repo CERTCC/Vultron \
  --title "specs: ingest idea #<IDEA_NUMBER> — <short title>" \
  --body "Docs-only PR: adds spec and notes for idea #<IDEA_NUMBER>.

Ref #<IDEA_NUMBER>

No .py files changed." \
  --label "specs-notes"
```

This PR carries the `specs-notes` label for reviewer awareness. This ensures
spec and notes files are on `main` and
referenceable from GitHub Issues before any implementation work begins.

### 11. Create a GitHub Issue for implementation

After opening the docs-only PR, create a GitHub Issue to track implementation
using the `manage-github-issue` skill. Wire the idea issue as the **parent**
of the new implementation issue — the idea is the origin, and the
implementation is its child. If the issue has known blockers at creation time,
wire them as structured relationships too.

```bash
IMPL_ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<Implementation title from spec>" \
  --body "## Summary

<Description from spec — one paragraph>

## Acceptance Criteria

- [ ] AC-1: <from spec>
- [ ] AC-2: <from spec>
...

## Reference

Spec: \`specs/<topic>.yaml\` (ID-01 through ID-NN)
Notes: \`notes/<topic>.md\`" \
  --label "group:unscheduled,size:<S|M|L>" \
  --parent "${IDEA_NUMBER}")
  # Add --blocked-by N if this issue has known blockers at creation time
echo "Created implementation issue #${IMPL_ISSUE_NUMBER}"
```

Set the `size:` label based on AC checkbox count:
1–2 ACs → `size:S`; 3–6 ACs → `size:M`; 7+ ACs → `size:L`.

The implementation Issue sits in `group:unscheduled` until a human runs
`review-priorities` to slot it into `plan/PRIORITIES.md`.

After creating the implementation issue, post the closing comment on the
idea issue and close it (see end of step 9):

```bash
gh issue comment "${IDEA_NUMBER}" --repo CERTCC/Vultron \
  --body "✅ Ingested.

- Docs PR: <PR_URL>
- Implementation issue: #${IMPL_ISSUE_NUMBER}

Design decisions captured in \`specs/<topic>.yaml\` and \`notes/<topic>.md\`."

gh issue close "${IDEA_NUMBER}" --repo CERTCC/Vultron
```

## Checklist

- [ ] Target idea issue confirmed (specified by user, selected from list, or
  created inline)
- [ ] Idea content fetched from GitHub issue
- [ ] Codebase explored before grilling
- [ ] All design decision branches resolved via grill-me
- [ ] `specs/<topic>.yaml` created with correct ID scheme
- [ ] `notes/<topic>.md` created with decision table + examples
- [ ] `specs/README.md` updated (both tables)
- [ ] Markdown lint clean
- [ ] Idea archived via `uv run append-history idea --source "IDEA-<number>"`
- [ ] Docs-only PR opened with `specs-notes` label and `Ref #<idea_number>`
  in body
- [ ] Implementation GitHub Issue created via `manage-github-issue` with
  `group:unscheduled` and `size:` labels; idea issue wired as parent;
  other blockers wired as structured relationships
- [ ] Idea issue commented with links to PR and implementation issue, then
  closed

## Conventions

- **Spec file names**: use the topic name, lowercase hyphenated with `.yaml`
  extension (e.g., `configuration.yaml`, `actor-discovery.yaml`)
- **ID prefix**: derive from the topic abbreviation (e.g., `CFG`, `AD`)
- **Notes file name**: same as spec file name with `.md` extension, in `notes/`
  instead of `specs/` (e.g., `configuration.md`, `actor-discovery.md`)
- **History source ID**: use `IDEA-<github_issue_number>` (e.g., `IDEA-42`)
  as the `--source` argument to `uv run append-history idea`
- **History archiving**: use `uv run append-history idea` to archive processed
  ideas — do not append directly to any `plan/history/*.md` file

## Creating a New Idea Issue

To submit a new idea outside of the inline creation flow, create a GitHub
Idea-type issue directly:

```bash
REPO_NODE_ID="R_kgDOIn77fA"
IDEA_TYPE_ID="IT_kwDOAjf0s84B_EoA"

TITLE_JSON=$(printf '%s' "<short idea title>" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
BODY_JSON=$(printf '%s' "<freeform description>" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

gh api graphql -f query="
mutation {
  createIssue(input: {
    repositoryId: \"${REPO_NODE_ID}\"
    title: ${TITLE_JSON}
    body: ${BODY_JSON}
    issueTypeId: \"${IDEA_TYPE_ID}\"
  }) {
    issue { number url }
  }
}"
```

The issue will appear as an Idea type in GitHub and will be picked up by
`ingest-idea` the next time it runs.

## Label Naming Rules (PAD-02-007)

All new Issues created by this skill use `group:unscheduled` by default — no
priority number or slug is needed at creation time. However, if you are
assigning a specific `group:` label for any reason:

- **Never include a priority number** in the label name.
  Use `group:architecture-hardening`, **not** `group:473-architecture-hardening`.
- **Derive the slug** from the priority group title in kebab-case.
- **Check for label existence** before assigning. Create it if missing:

  ```bash
  gh label create "group:<slug>" \
    --repo CERTCC/Vultron \
    --description "<Priority group title (no number)>" \
    --color "#1d76db"
  ```
