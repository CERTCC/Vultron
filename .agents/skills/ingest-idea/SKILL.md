---
name: ingest-idea
description: >
  Process a raw design idea from plan/IDEAS.md into formal specs and
  implementation notes, then archive the idea and commit. Runs a structured
  interview (grill-me), writes specs/<topic>.md and notes/<topic>.md, archives
  the idea via `uv run append-history idea`, updates specs/README.md, lints,
  and commits. Use when the user says "ingest idea", references an IDEA ID, or
  wants to convert a plan/IDEAS.md entry into spec and notes files.
---

# Skill: Ingest Idea

Convert a raw idea from `plan/IDEAS.md` into durable specs and notes, then
archive it. This is the full end-to-end workflow: interview → write → archive
→ commit.

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

Create or modify `specs/<topic>.md` following `specs/meta-specifications.yaml`
conventions:

- Use a `FILE_PREFIX-SECTION_#-###` ID scheme (e.g., `CFG-01-001`)
- Group requirements by category with RFC 2119 keywords on every line
- Include an `## Overview` with source reference and scope note
- Sections: one `---` divider after the header; categories as `##` headings

### 6. Write the notes file

Create or modify `notes/<topic>.md` with implementation guidance:

- Decision table (question → decision → rationale)
- Key design patterns and code examples
- Call-site migration guide if replacing existing patterns
- Testing pattern examples
- Layer / import rules relevant to the change

### 7. Update specs/README.md

Add the new spec to both:

- The **Load Contextually** table (topic → file)
- The **Specification Structure** section (bullet with ID range)

### 8. Archive the idea

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
`specs/<topic>.md` (ID-01 through ID-NN) and `notes/<topic>.md`.
ENDOFENTRY
```

Remove the idea section (heading + body) from `plan/IDEAS.md`.

### 9. Lint markdown

Invoke the `format-markdown` skill on all new/modified markdown files. Fix
any errors before proceeding.

### 10. Commit

Invoke the `commit` skill:

```bash
git add specs/<topic>.md notes/<topic>.md \
        plan/IDEAS.md \
        specs/README.md
git commit -m "ingest IDEA-<ID>: <short title>

- Add specs/<topic>.md (ID-01 through ID-NN)
- Add notes/<topic>.md with implementation guidance
- Archive IDEA-<ID> via append-history idea

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Checklist

- [ ] Target IDEA ID confirmed (specified by user or selected via `ask_user`)
- [ ] Idea text read from `plan/IDEAS.md`
- [ ] Codebase explored before grilling
- [ ] All design decision branches resolved via grill-me
- [ ] `specs/<topic>.md` created with correct ID scheme
- [ ] `notes/<topic>.md` created with decision table + examples
- [ ] `specs/README.md` updated (both tables)
- [ ] `plan/IDEAS.md` — idea section removed
- [ ] Idea archived via `uv run append-history idea`
- [ ] Markdown lint clean
- [ ] Git commit done

## Conventions

- **Spec file names**: use the topic name, lowercase hyphenated
  (e.g., `configuration.md`, `actor-discovery.md`)
- **ID prefix**: derive from the topic abbreviation (e.g., `CFG`, `AD`)
- **Notes file name**: same as spec file name, in `notes/` instead of `specs/`
- **History archiving**: use `uv run append-history idea` to archive processed
  ideas — do not append directly to any `plan/history/*.md` file
