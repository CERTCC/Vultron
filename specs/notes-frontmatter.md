# Notes Frontmatter Specification

## Overview

This specification defines requirements for YAML frontmatter in `notes/*.md`
files: the required schema, a Pydantic-based loader in `vultron/metadata/`,
validation enforcement, and migration requirements.

**Source**: IDEA-26042403  
**Note**: The `vultron/metadata/specs/` subpackage (for IDEA-26042402) is a
parallel but separate concern; this spec covers the notes side only. A shared
`vultron/metadata/base.py` holds common vocabulary.

---

## Frontmatter Schema (MUST)

- `NF-01-001` Every `notes/*.md` file (except `notes/README.md`) MUST contain
  a YAML frontmatter block delimited by `---` at the top of the file.
- `NF-01-002` The frontmatter MUST include a `title` field whose value is a
  non-empty string matching the file's `# H1` heading.
- `NF-01-003` The frontmatter MUST include a `status` field whose value is one
  of: `active`, `draft`, `superseded`, `archived`.
  - `active`: the note is current and relevant to ongoing work.
  - `draft`: the note is in progress and not yet authoritative.
  - `superseded`: the note has been replaced by another file.
  - `archived`: the note is complete or obsolete; candidate for
    `archived_notes/`.
- `NF-01-004` When `status` is `superseded`, a `superseded_by` field MUST be
  present and MUST contain a non-empty string identifying the replacement
  file path (e.g., `notes/new-topic.md` or `specs/new-spec.yaml`).
- `NF-01-005` The optional `description` field, when present, MUST be a
  non-empty string summarising the file's purpose for tooling and agents.
- `NF-01-006` The optional `related_specs` field, when present, MUST be a
  non-empty list of non-empty strings naming related specification files
  (e.g., `["specs/behavior-tree-integration.yaml"]`).
- `NF-01-007` The optional `related_notes` field, when present, MUST be a
  non-empty list of non-empty strings naming related notes files.
- `NF-01-008` The optional `relevant_packages` field, when present, MUST be a
  non-empty list of non-empty strings naming packages relevant to the note's
  topic. Each entry is either:
  - An external PyPI package name (e.g., `py_trees`, `pydantic`), or
  - An internal Vultron subpackage path using forward slashes
    (e.g., `vultron/core/behaviors`, `vultron/wire/as2`).
  Both forms MAY appear in the same list.

## Pydantic Schema Module (MUST)

- `NF-02-001` The `vultron/metadata/notes/` subpackage MUST define a Pydantic
  model (`NotesFrontmatter`) that validates the frontmatter schema described
  in NF-01.
- `NF-02-002` `NotesFrontmatter` MUST use a `StrEnum` for the `status` field
  vocabulary (`NoteStatus`).
- `NF-02-003` Shared base vocabulary (e.g., common `StrEnum` base classes or
  type aliases) MUST live in `vultron/metadata/base.py` and be importable by
  both `metadata/notes/` and the future `metadata/specs/` subpackage.
- `NF-02-004` The `vultron/metadata/` package MUST NOT import from
  `vultron/core/`, `vultron/wire/`, or `vultron/adapters/`; it is a
  standalone tooling layer with no dependency on application code.

## Loader (MUST)

- `NF-03-001` The `vultron/metadata/notes/` subpackage MUST provide a loader
  that discovers and parses all `notes/*.md` files relative to the repository
  root.
- `NF-03-002` The loader MUST skip `notes/README.md`.
- `NF-03-003` The loader MUST parse each file's YAML frontmatter block and
  validate it against `NotesFrontmatter`, raising a `ValueError` (or
  equivalent) on schema violations.
- `NF-03-004` The loader MUST return a registry mapping file path to validated
  `NotesFrontmatter` instance.
- `NF-03-005` The loader SHOULD resolve the repository root by searching
  upward from the current working directory for a `pyproject.toml` file, so
  it works correctly regardless of where it is called from.

## Validation Enforcement (MUST)

- `NF-04-001` A pytest test MUST load all `notes/*.md` files via the loader
  and assert that every file parses without validation errors.
- `NF-04-002` A pre-commit hook MUST validate the frontmatter of any changed
  `notes/*.md` file before the commit is accepted.
  - The hook SHOULD run the same loader logic used in the pytest test.

## Migration (MUST)

- `NF-05-001` All existing `notes/*.md` files (except `notes/README.md`) MUST
  have compliant YAML frontmatter added as part of the initial implementation
  of this spec.
- `NF-05-002` The `status` field added during migration MUST accurately
  reflect the current state of each file's content.

## Maintenance (SHOULD)

- `NF-06-001` When modifying any `notes/*.md` file, the author SHOULD review
  and update its frontmatter — in particular `status`, `related_specs`, and
  `related_notes` — to reflect any changes in scope or relationships.
- `NF-06-002` `AGENTS.md` MUST document the frontmatter maintenance rule so
  that AI coding agents apply it consistently.

## Future: Registry and Query Tool (MAY)

- `NF-07-001` A query/dump tool MAY be built (in a later task) that accepts a
  topic keyword and returns all notes (and eventually specs) whose frontmatter
  indicates relevance to that topic.
  - This tool depends on both `vultron/metadata/notes/` and the planned
    `vultron/metadata/specs/` loader (IDEA-26042402).
- `NF-07-002` The `notes/README.md` index MAY be generated from the notes
  registry in a later task, replacing the manually-maintained summaries with
  content derived from `description` frontmatter fields.
