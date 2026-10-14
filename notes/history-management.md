---
title: "History Management: Writing and Reading plan/history/"
status: active
kind: guidance
description: >
  Rules for agents writing to and reading the project history: write only
  through append-history, which entries become GitHub comments, why the monthly
  README is never committed, when to read plan/history/ at all, and how stale
  notes sections are archived.
related_specs:
  - specs/history-management.yaml
  - specs/project-documentation.yaml
related_notes:
  - notes/agentic-workflow.md
---

# History Management: Writing and Reading plan/history/

The requirements are `specs/history-management.yaml` (HM-01 through HM-08); the
tool is `vultron/metadata/history/`.

---

## Write Only Through `append-history`

Never write a file under `plan/history/` by hand. Run
`uv run append-history <type> --title <title> --source <id>` with the body on
stdin or `--file <path>`; the tool builds the frontmatter, stamps the UTC time
and picks the `YYMM` directory (HM-07-004). Entries are write-once (HM-01-005).

An `implementation` or `idea` entry whose `--source` is `ISSUE-<n>` is posted
as a comment on issue *n* instead of written to a file, and the tool prints the
comment URL. `archive-history` then skips its git steps (HM-08).

The monthly `plan/history/YYMM/README.md` is a gitignored local cache that the
tool rebuilds on every append, so parallel branches never conflict on it. Do
not stage it; view the index with `uv run show-history [--month YYMM | --all]`.

---

## Read `plan/history/` Only When You Need It

Orientation reads `plan/*.md` and never `plan/history/`, so the archive costs no
context in an ordinary session. Read it only to investigate a regression from a
recent task, to extract lessons (`learn`), or to audit what shipped in a window.
Get the index from `show-history`, then open only the entries you need.

---

## Superseded Notes Sections Are Archived via `append-history note`

Stale sections (or whole files) go to `plan/history/YYMM/note/` with source ID
`NOTES-<file-stem>--<section-slug>`. The body states the reason and the
superseding pointer, then `---`, then the removed text verbatim (PD-03-005).
When every section of a file is archived, delete the file and its
`notes/README.md` entry (PD-03-004).
