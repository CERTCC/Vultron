---
name: ingest-idea
description: >
  Process a raw design idea from plan/IDEAS.md into formal specs and
  implementation notes, then archive the idea, open a docs-only PR, and
  create a GitHub Issue for implementation. Runs a structured interview
  (grill-me), writes specs/<topic>.yaml and notes/<topic>.md, archives the
  idea via `uv run append-history idea`, opens a docs-only PR with the
  specs-notes label, and creates a GitHub Issue tagged group:unscheduled.
  Use when the user says "ingest idea", references an IDEA ID, or wants to
  convert a plan/IDEAS.md entry into spec and notes files.
---

# Skill: Ingest Idea

Convert a raw idea from `plan/IDEAS.md` into durable specs and notes, then
archive it and open a docs-only PR. This is the full end-to-end workflow:
interview → write → archive → PR → issue.

## Workflow

### 1. Identify the target idea

If the user specified an IDEA ID (e.g., `IDEA-26041002`), skip to step 2.

Otherwise, read `plan/IDEAS.md` and extract every line that starts with
`## IDEA-` to build a list of ID + summary pairs. Present them to the user
as a multiple-choice list using `ask_user` with a `choices` array where each
entry is the full `IDEA-XXXXXXXX Short title` string. Wait for the user's
selection before continuing.

### 2. Read the idea

Locate the target IDEA ID in `plan/IDEAS.md`. Extract the full text of that
section (from its `## IDEA-*` heading to the next `## IDEA-*` heading).

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
`--title` and `--source` flags:

```bash
cat <<'ENDOFENTRY' | uv run append-history idea \
    --title "<short idea title>" \
    --source "IDEA-<ID>"

## IDEA-<ID> <short title>

<full original idea text here>

**Processed**: YYYY-MM-DD — design decisions captured in
`specs/<topic>.yaml` (ID-01 through ID-NN) and `notes/<topic>.md`.
ENDOFENTRY
```

Remove the idea section (heading + body) from `plan/IDEAS.md`.

### 10. Open a docs-only PR

Create a branch, commit all spec/notes/README/IDEAS.md changes, and open a
PR carrying the `specs-notes` label:

```bash
git switch -c ingest/<IDEA-ID>-<slug>
git add specs/<topic>.yaml notes/<topic>.md specs/README.md plan/IDEAS.md
git commit -m "specs: ingest IDEA-<ID> — <short title>

- Add specs/<topic>.yaml (ID-01 through ID-NN)
- Add notes/<topic>.md with implementation guidance
- Archive IDEA-<ID> via append-history idea

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin ingest/<IDEA-ID>-<slug>

gh pr create --repo CERTCC/Vultron \
  --title "specs: ingest IDEA-<ID> — <short title>" \
  --body "Docs-only PR: adds spec and notes for IDEA-<ID>.

No .py files changed." \
  --label "specs-notes"
```

This PR carries the `specs-notes` label for reviewer awareness. This ensures
spec and notes files are on `main` and
referenceable from GitHub Issues before any implementation work begins.

### 11. Create a GitHub Issue for implementation

After opening the docs-only PR, create a GitHub Issue to track implementation:

```bash
gh issue create --repo CERTCC/Vultron \
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
  --label "group:unscheduled,size:<S|M|L>"
```

Set the `size:` label based on AC checkbox count:
1–2 ACs → `size:S`; 3–6 ACs → `size:M`; 7+ ACs → `size:L`.

The Issue sits in `group:unscheduled` until a human runs `review-priorities`
to slot it into `plan/PRIORITIES.md`.

## Checklist

- [ ] Target IDEA ID confirmed (specified by user or selected via `ask_user`)
- [ ] Idea text read from `plan/IDEAS.md`
- [ ] Codebase explored before grilling
- [ ] All design decision branches resolved via grill-me
- [ ] `specs/<topic>.yaml` created with correct ID scheme
- [ ] `notes/<topic>.md` created with decision table + examples
- [ ] `specs/README.md` updated (both tables)
- [ ] Markdown lint clean
- [ ] Idea archived via `uv run append-history idea`
- [ ] `plan/IDEAS.md` — idea section removed
- [ ] Docs-only PR opened with `specs-notes` label
- [ ] GitHub Issue created with `group:unscheduled` and `size:` labels

## Conventions

- **Spec file names**: use the topic name, lowercase hyphenated with `.yaml`
  extension (e.g., `configuration.yaml`, `actor-discovery.yaml`)
- **ID prefix**: derive from the topic abbreviation (e.g., `CFG`, `AD`)
- **Notes file name**: same as spec file name with `.md` extension, in `notes/`
  instead of `specs/` (e.g., `configuration.md`, `actor-discovery.md`)
- **History archiving**: use `uv run append-history idea` to archive processed
  ideas — do not append directly to any `plan/history/*.md` file

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
