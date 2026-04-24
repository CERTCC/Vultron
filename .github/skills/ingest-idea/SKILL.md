---
name: ingest-idea
description: >
  Process a raw design idea from plan/IDEAS.md into formal specs and
  implementation notes, then archive the idea and commit. Runs a structured
  interview (grill-me), writes specs/<topic>.md and notes/<topic>.md, moves
  the idea to plan/IDEA-HISTORY.md, updates specs/README.md, lints, and
  commits. Use when the user says "ingest idea", references an IDEA ID, or
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

Before interviewing, understand the current state. Search for:

- Existing code that touches the idea's domain (modules, env vars, patterns)
- Existing specs or notes that overlap with or constrain the idea
- Any already-implemented partial solutions

Answer questions from exploration rather than asking the user where possible.

### 4. Interview with grill-me

Invoke the `grill-me` skill. Follow its instructions to walk every design
decision branch one at a time, providing a recommendation for each question.
Reach shared understanding before writing anything.

### 5. Write the spec file

Create or modify `specs/<topic>.md` following `specs/meta-specifications.md` 
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

Append the full original idea text to `plan/IDEA-HISTORY.md` (create the file
if it does not exist) with a `**Processed**:` line at the end:

```markdown
**Processed**: YYYY-MM-DD — design decisions captured in
`specs/<topic>.md` (ID-01 through ID-NN) and `notes/<topic>.md`.
```

Remove the idea section (heading + body) from `plan/IDEAS.md`.

### 9. Lint markdown

Run `./mdlint.sh` on all new/modified markdown files. Fix any errors before
proceeding.

### 10. Commit

Stage and commit all new and modified files:

```bash
git add specs/<topic>.md notes/<topic>.md \
        plan/IDEAS.md plan/IDEA-HISTORY.md \
        specs/README.md
git commit -m "ingest IDEA-<ID>: <short title>

- Add specs/<topic>.md (ID-01 through ID-NN)
- Add notes/<topic>.md with implementation guidance
- Archive IDEA-<ID> to plan/IDEA-HISTORY.md

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
- [ ] `plan/IDEA-HISTORY.md` updated with full original text + Processed note
- [ ] Idea removed from `plan/IDEAS.md`
- [ ] Markdown lint clean
- [ ] Git commit done

## Conventions

- **Spec file names**: use the topic name, lowercase hyphenated
  (e.g., `configuration.md`, `actor-discovery.md`)
- **ID prefix**: derive from the topic abbreviation (e.g., `CFG`, `AD`)
- **Notes file name**: same as spec file name, in `notes/` instead of `specs/`
- **IDEA-HISTORY.md**: append-only; new entries go at the **end**
