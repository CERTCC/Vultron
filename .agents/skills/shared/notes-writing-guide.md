# Notes Writing Guide

How to write, edit, and retire a `notes/*.md` file. Read this before adding to any
note. Requirements: `specs/notes-frontmatter.yaml` NF-01, NF-08, NF-09; archiving:
PD-03-004/005, PD-03-010/011.

## What a note is for

A note exists to inform work that **has not been done yet** (NF-08-001). It is a
working document with an end, not a history of the project:

- When the work it informs lands, the note is archived via `append-history note`, or
  its still-useful content moves out: reference material to `docs/`, lasting rules
  into a `guidance` note.
- The story of how something was found, tried, and fixed belongs in git, the PR, and
  `plan/history/`, never in `notes/`.

## Pick exactly one `kind`

Every note declares `kind:` in its frontmatter, and a file has exactly one
(NF-08-002/003).

| `kind` | It is… | Test | Lifetime |
|---|---|---|---|
| `guidance` | A rule for changing the project without repeating a known mistake, or a procedure for a recurring task | If every open issue closed tomorrow, would it still be true **and** still change how someone works? | Lasting; trimmed, not retired |
| `plan` | A design or decision for work the code does not do yet, too big or cross-cutting for one issue body | Does it describe something the code does not do yet? | Ends when the work lands |
| `generated` | A file a tool writes | Does a command regenerate it? | Owned by its generator |

Material that fits none of these does not belong in `notes/`:

- **Reference material** (catalogs, message tables, conceptual overviews) goes to
  `docs/`.
- **Rationale for delivered work** goes to the ADR or spec that made the decision, or
  to the archive.

### `plan` notes carry `tracks:`

```yaml
kind: plan
tracks:
  - "#1156"   # the leaf issue(s) the plan informs
  - "#4492"   # and their parent epic
```

List the leaf issues **and** their parent epic (NF-01-010). The epic keeps the note
alive while follow-up work continues: a Concern closed by being split into Tasks, or
a leaf moved to another epic, does not make every tracked issue closed. When the work
is re-scoped, update `tracks:` in the same change.

`uv run notes-tracks` lists plan notes whose tracked issues are all closed, plus any
that track an unknown number (NF-09). It only flags. A flagged note is an agenda item
for the next sweep, not an automatic archive.

### `generated` notes carry the marker

The body starts with `<!-- GENERATED … -->` naming the command that writes it
(NF-01-011). Never hand-edit one: change its generator.

## Mixed content

- **Never add a plan item to a `guidance` note.** Put it in a `plan` note (create one
  if none fits) or in the issue itself.
- **When a plan delivers**, promote its lasting lessons into the matching `guidance`
  note, or move reference material to `docs/`, then archive the plan note.
- **A file that has become mixed gets split** so each part has one kind.

## Writing a `guidance` item

State **the rule, the reason, and at most one citation** (an issue, ADR, or spec
ID) (NF-08-004). If a defect taught the lesson, the lesson is the rule; one sentence
of "why" is usually enough.

Cut these on sight, whether you are writing new text or editing nearby:

- **Provenance chains**: several `(#N)` / `ISSUE-N` citations for one rule,
  `<!-- Source: -->` comments, "Source: planning session …" headers. Keep one
  citation.
- **Stories**: how the defect hid, how it was found, which attempts failed, and
  "earlier descriptions were wrong; the correct version is…" blocks.
- **History**: PR-by-PR change-history lists, "migration complete" notices, and
  reconstructions of removed features. "X was removed, not deferred (ADR-N)" is
  enough.
- **Copies of the code**: code blocks reproducing live modules, test-snippet sections,
  `file.py:line` tables, and inventories a test already enforces. Point at the module
  or test instead.
- **Stale tense**: "not yet", "future", "planned", or "decided, not yet built" inside a
  `guidance` note means a plan item has leaked in. Move it out.

## Frontmatter maintenance

When you modify a note, update `status`, `kind`, `tracks`, `related_specs`, and
`related_notes` in the same change (NF-06-001). A new spec citation or note link in
the body needs a matching frontmatter entry. Cross-links should be two-way: if note A
lists note B under `related_notes`, B lists A.

The schema is `vultron/metadata/notes/schema.py`. The `validate-notes-frontmatter`
pre-commit hook and `test/metadata/test_notes_frontmatter.py` enforce it.
