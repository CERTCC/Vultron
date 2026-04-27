# Spec Registry

## Overview

Requirements for converting `specs/*.md` files to YAML governed by Pydantic
models, building a structured registry of all requirements, and providing
linting, pytest integration, and context-generation tooling.

**Source**: `plan/IDEAS.md` IDEA-26042402; `wip_notes/spec_registry_design.md`  
**Note**: Applies to all `specs/*.yaml` files and the `vultron/metadata/specs/`
module. Migration from `.md` to `.yaml` is a one-time lossless conversion.

---

## YAML File Format (MUST)

- `SR-01-001` Each `specs/*.md` file MUST be replaced by a `specs/*.yaml`
  file with the same kebab-case topic name.
  - The `.md` files are deleted; YAML is the sole source of truth.
- `SR-01-002` Each YAML file MUST have a top-level `id` field containing the
  file-level prefix string (e.g., `"HP"`).
- `SR-01-003` Each YAML file MUST have `title`, `description`, and `version`
  fields.
  - `version` MUST be a semver string (e.g., `"1.0.0"`).
- `SR-01-004` Each YAML file MUST contain a `groups` list; each group MUST
  have `id`, `title`, and `specs` fields.
  - Group IDs MUST follow the pattern `PREFIX-NN` (e.g., `HP-01`).
- `SR-01-005` Each individual spec entry MUST have `id`, `priority`,
  `statement`, and `rationale` fields.
  - Spec IDs MUST follow the pattern `PREFIX-NN-NNN` (e.g., `HP-01-001`).
  - `priority` MUST be one of the `RFC2119Priority` StrEnum values.
- `SR-01-006` Spec IDs MUST be globally unique across all loaded YAML files.
- `SR-01-007` Group IDs within a file MUST match the file-level prefix
  (e.g., group `HP-01` must live in file with `id: HP`).

## YAML File Format (SHOULD)

- `SR-01-008` Each spec entry SHOULD include a `testable` boolean field
  (default `true`).
- `SR-01-009` Spec entries SHOULD include a `kind` field from the `SpecKind`
  StrEnum (`general` or `implementation`); default `general`.
- `SR-01-010` Spec entries SHOULD include a `scope` field listing one or more
  `Scope` StrEnum values (`prototype`, `production`); default `[production]`.
- `SR-01-011` Spec entries SHOULD include a `tags` list using values from the
  `SpecTag` StrEnum vocabulary.
- `SR-01-012` Spec entries SHOULD include a `relationships` list when
  cross-spec traceability is needed; each relationship MUST have `rel_type`
  and `spec_id` fields.

---

## Pydantic Schema (MUST)

- `SR-02-001` The `vultron/metadata/specs/` module MUST define Pydantic models
  for all registry structures: `SpecFile`, `SpecGroup`, `StatementSpec`,
  `BehavioralSpec`, `Relationship`.
- `SR-02-002` Fixed vocabularies MUST be implemented as `StrEnum` subclasses:
  `RFC2119Priority`, `RelationType`, `SpecKind`, `Scope`, `SpecTag`.
- `SR-02-003` `RFC2119Priority` MUST include at minimum: `MUST`, `MUST_NOT`,
  `SHOULD`, `SHOULD_NOT`, `MAY`.
- `SR-02-004` `RelationType` MUST include at minimum: `implements`,
  `supersedes`, `extends`, `depends_on`, `conflicts`, `refines`,
  `derives_from`, `verifies`, `part_of`, `constrains`.
- `SR-02-005` `SpecKind` MUST include: `general`, `implementation`.
- `SR-02-006` `Scope` MUST include: `prototype`, `production`.
- `SR-02-007` `SpecTag` MUST be a controlled vocabulary StrEnum; initial
  values are defined in `notes/spec-registry.md`.
  - Tags MUST be lowercase hyphenated strings.
- `SR-02-008` A `SpecIdStr` type alias MUST enforce the ID pattern
  `^[A-Z]{2,8}(-\d{2}(-\d{3})?)?$` via Pydantic `StringConstraints`.
- `SR-02-009` `StatementSpec` MUST have fields: `id` (`SpecIdStr`),
  `priority` (`RFC2119Priority`), `statement` (non-empty str), `rationale`
  (non-empty str), and optional fields: `testable`, `kind`, `scope`, `tags`,
  `relationships`, `lint_suppress`.
- `SR-02-010` `BehavioralSpec` MUST extend `StatementSpec` with optional
  fields: `preconditions`, `steps`, `postconditions`.
  - A spec is treated as `BehavioralSpec` when any behavioral extension field
    is present.
- `SR-02-011` The `lint_suppress` field on a spec MUST accept a list of
  `LintWarningCode` StrEnum values to suppress named linter warnings for
  that spec.
- `SR-02-012` `SpecGroup` MUST have fields: `id` (`SpecIdStr`), `title`,
  `specs` (non-empty list), and optional `description`, `kind`, `scope`.
- `SR-02-013` `SpecFile` MUST have fields: `id` (str), `title`, `description`,
  `version` (semver str), `groups` (non-empty list), and optional `kind`,
  `scope`.
- `SR-02-014` `kind` and `scope` at `SpecFile` and `SpecGroup` level MUST
  serve as defaults; individual specs MAY override them.

## Pydantic Schema (SHOULD)

- `SR-02-015` `Relationship` SHOULD include an optional `note` field for
  free-text annotation of the relationship.
- `SR-02-016` `BehaviorStep` SHOULD include fields: `order` (int), `actor`
  (str), `action` (str), and optional `expected` (str).

---

## Registry Loader (MUST)

- `SR-03-001` The `vultron/metadata/specs/` module MUST provide a
  `load_registry(spec_dir)` function that loads all `*.yaml` files from the
  given directory into a `SpecRegistry`.
- `SR-03-002` `SpecRegistry` MUST maintain an index of all specs by ID and
  enforce global uniqueness, raising `ValueError` on duplicate IDs.
- `SR-03-003` `SpecRegistry` MUST provide a `get(spec_id)` method returning
  the `Spec` for a given ID, raising `KeyError` on unknown IDs.
- `SR-03-004` `SpecRegistry` MUST provide a `validate_cross_references()`
  method returning a list of error strings for any dangling relationship
  targets.
- `SR-03-005` The loader MUST work regardless of the caller's working
  directory by accepting an explicit `spec_dir` path.

## Registry Loader (SHOULD)

- `SR-03-006` `SpecRegistry` SHOULD maintain a group index in addition to the
  spec index.
- `SR-03-007` The loader SHOULD provide a `_find_repo_root()` helper
  (mirroring the notes loader) for callers that do not supply an explicit
  path.

---

## Linter (MUST)

- `SR-04-001` The `vultron/metadata/specs/lint.py` module MUST provide a
  `lint(spec_dir)` function that returns exit code `0` (clean) or `1`
  (errors found).
- `SR-04-002` The linter MUST report as hard errors: duplicate spec IDs,
  dangling relationship targets, group-ID/file-prefix mismatches, and
  invalid YAML structure.
- `SR-04-003` The linter MUST be invokable as a CLI command:
  `python -m vultron.metadata.specs.lint specs/`.
- `SR-04-004` The linter MUST respect `lint_suppress` fields on individual
  specs when checking advisory warnings.

## Linter (SHOULD)

- `SR-04-005` The linter SHOULD emit advisory warnings (non-blocking) for:
  specs with `testable: false` and no behavioral steps (suppressible via
  `lint_suppress: [testable_without_steps]`), rationale text exceeding 500
  characters, and specs with no tags.
- `SR-04-006` The linter SHOULD check that tag values in spec entries are
  members of the `SpecTag` StrEnum vocabulary.
- `SR-04-007` The linter SHOULD check that `scope` at the spec level is not
  broader than the containing group or file scope.

---

## Pytest Integration (MUST)

- `SR-05-001` The project MUST register a `spec` pytest marker in
  `conftest.py`: `@pytest.mark.spec("SR-01-001")`.
- `SR-05-002` `pytest_collection_modifyitems` MUST validate each `spec`
  marker value against the loaded `SpecRegistry` and emit a
  `PytestWarning` (non-blocking) for any unknown spec ID.

## Pytest Integration (SHOULD)

- `SR-05-003` The pytest integration SHOULD load the registry once per
  session (not per test) to avoid I/O overhead.
- `SR-05-004` Tests SHOULD use `@pytest.mark.spec` to assert which
  requirement they verify, enabling coverage reporting by spec ID.

---

## Pre-commit Hook (MUST)

- `SR-06-001` A `spec-lint` pre-commit hook MUST be defined that fires on any
  staged change to a `specs/*.yaml` file.
- `SR-06-002` The hook MUST run `python -m vultron.metadata.specs.lint specs/`
  and block the commit on exit code `1`.
- `SR-06-003` The hook MUST be configured with `pass_filenames: false` so the
  full registry is always validated, not just the changed file.

---

## Context Generation Tool (MUST)

- `SR-07-001` The `vultron/metadata/specs/` module MUST provide a context
  generation tool that accepts a `SpecRegistry` and produces output for
  agent consumption.
- `SR-07-002` The tool MUST support a **markdown renderer** that regenerates
  a `.md` view of a spec file from its YAML source.
- `SR-07-003` The tool MUST support a **JSON exporter** that serializes
  the full registry or individual spec files to JSON.

## Context Generation Tool (SHOULD)

- `SR-07-004` The markdown renderer SHOULD produce output compatible with the
  existing `meta-specifications.md` style guide.
- `SR-07-005` The JSON exporter SHOULD support filtering by `kind`, `scope`,
  `tags`, or `priority` to allow agents to request only relevant subsets.

---

## Migration (MUST)

- `SR-08-001` All existing `specs/*.md` files MUST be migrated to
  `specs/*.yaml` using a lossless conversion that preserves all requirement
  text, IDs, and relationships.
- `SR-08-002` The migration MUST produce YAML files that pass the spec linter
  with zero errors.
- `SR-08-003` After migration, the `specs/*.md` files MUST be deleted; the
  YAML files are the sole source of truth.
- `SR-08-004` `specs/README.md` and `specs/meta-specifications.yaml` MUST be
  retained as Markdown (they are documentation, not requirement files).
- `SR-08-005` All in-project skills, prompts, and agent instructions that
  reference `specs/*.md` files by path or extension MUST be updated to use
  `specs/*.yaml` paths or the context-generation tool output before the
  migration is considered complete.
  - Files to audit include `.github/skills/*/SKILL.md`, `prompts/`,
    `AGENTS.md`, and any Copilot instruction files that cite `specs/`
    paths by extension.
- `SR-08-006` The original `specs/*.md` requirement files MUST NOT be deleted
  until the YAML files have passed the spec linter with zero errors and all
  agent/skill references have been updated to YAML paths.
  - The `.md` files serve as the safety net during migration; deleting
    them before YAML is validated risks an unrecoverable state.

## Migration (SHOULD)

- `SR-08-007` A migration script SHOULD be provided to convert a single
  `specs/*.md` file to the YAML format as a starting point; manual review
  and cleanup is expected.
