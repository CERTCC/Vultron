---
title: Notes Frontmatter Design
status: active
description: >
  Design decisions for YAML frontmatter schema in notes/*.md files; schema,
  loader, migration checklist, and pre-commit hook.
related_specs:
  - specs/notes-frontmatter.md
relevant_packages:
  - pydantic
  - python-frontmatter
---

# Notes Frontmatter Design

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Required vs optional fields | `title` + `status` required; all others optional | Lowers migration barrier; minimal required set enables validation |
| Status vocabulary | `active \| draft \| superseded \| archived` | Mirrors ADR lifecycle; four states cover all practical cases |
| `superseded_by` | Optional string, required when `status: superseded` | Makes replacement explicit; avoids orphaned superseded notes |
| Relationship fields | Three separate lists: `related_specs`, `related_notes`, `relevant_packages` | Explicit, queryable; absent is ok; present-and-populated only |
| Empty-list rule | Present-and-populated or absent; present-and-empty is invalid | Mirrors `OptionalNonEmptyString` pattern already in codebase |
| `description` field | Optional non-empty string | Seeds future README auto-generation from the registry |
| Module location | `vultron/metadata/notes/` subpackage | Parallel to planned `vultron/metadata/specs/`; shared `base.py` |
| Loader isolation | `vultron/metadata/` MUST NOT import application code | Keeps tooling layer standalone; no circular imports |
| Validation enforcement | pytest (all files) + pre-commit (changed files) | Belt-and-suspenders: CI catches everything; pre-commit is fast |
| Migration scope | All existing `notes/*.md` at once | Enables hard enforcement from day one |
| `notes/README.md` | Excluded from frontmatter requirements | Index file, not a design note; loader skips it |
| `title` field | Explicit in frontmatter | Self-contained for tooling; no need to parse markdown body |
| Query/dump tool | Deferred (future task) | Requires both notes and specs loaders; out of scope here |
| Maintenance guidance | Update AGENTS.md + spec; pre-commit for structural checks | Agents need an explicit rule; structure is machine-checked |

---

## Schema Design

### `NoteStatus` StrEnum

```python
from enum import StrEnum

class NoteStatus(StrEnum):
    ACTIVE     = "active"
    DRAFT      = "draft"
    SUPERSEDED = "superseded"
    ARCHIVED   = "archived"
```

### `NotesFrontmatter` Pydantic Model

```python
from __future__ import annotations

from pydantic import BaseModel, model_validator
from vultron.metadata.base import NonEmptyStr, NonEmptyStrList

class NotesFrontmatter(BaseModel):
    title: NonEmptyStr
    status: NoteStatus
    superseded_by: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    related_specs: NonEmptyStrList | None = None
    related_notes: NonEmptyStrList | None = None
    relevant_packages: NonEmptyStrList | None = None

    @model_validator(mode="after")
    def superseded_by_required_when_superseded(self) -> NotesFrontmatter:
        if self.status == NoteStatus.SUPERSEDED and not self.superseded_by:
            raise ValueError(
                "'superseded_by' is required when status is 'superseded'"
            )
        return self
```

### Shared type aliases in `vultron/metadata/base.py`

```python
from typing import Annotated
from pydantic import StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
NonEmptyStrList = Annotated[list[NonEmptyStr], ...]  # non-empty list
```

For the "non-empty list when present" rule, use a field validator or
`Annotated` with `minlength=1` at the list level:

```python
from pydantic import field_validator

@field_validator("related_specs", "related_notes", "relevant_packages",
                  mode="before")
@classmethod
def non_empty_list_if_present(cls, v):
    if v is not None and len(v) == 0:
        raise ValueError("list field must be non-empty if present")
    return v
```

---

## Sample Frontmatter Block

A well-formed frontmatter block at the top of a notes file looks like:

```yaml
---
title: Behavior Tree Integration Design Notes
status: active
description: >
  BT design decisions, py_trees patterns, simulation-to-prototype
  translation strategy, and anti-patterns to avoid.
related_specs:
  - specs/behavior-tree-integration.md
  - specs/behavior-tree-node-design.md
related_notes:
  - notes/bt-reusability.md
  - notes/bt-composability.md
relevant_packages:
  - py_trees
---
```

A minimal valid block:

```yaml
---
title: Docker Build Notes
status: active
---
```

A superseded file:

```yaml
---
title: Old Architecture Notes
status: superseded
superseded_by: notes/architecture-ports-and-adapters.md
---
```

---

## Loader Design

### Module: `vultron/metadata/notes/loader.py`

```python
from pathlib import Path
import yaml
from vultron.metadata.notes.schema import NotesFrontmatter

SKIP_FILES = {"README.md"}

def _find_repo_root(start: Path = Path.cwd()) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("Could not locate repository root (pyproject.toml)")

def _extract_frontmatter(text: str) -> dict | None:
    """Return parsed YAML from a --- ... --- block, or None if absent."""
    if not text.startswith("---"):
        return None
    end = text.index("\n---", 3)
    return yaml.safe_load(text[3:end])

def load_notes_registry(
    repo_root: Path | None = None,
) -> dict[str, NotesFrontmatter]:
    root = repo_root or _find_repo_root()
    notes_dir = root / "notes"
    registry: dict[str, NotesFrontmatter] = {}
    for path in sorted(notes_dir.glob("*.md")):
        if path.name in SKIP_FILES:
            continue
        raw = _extract_frontmatter(path.read_text())
        if raw is None:
            raise ValueError(f"{path}: missing YAML frontmatter")
        key = str(path.relative_to(root))
        registry[key] = NotesFrontmatter.model_validate(raw)
    return registry
```

### Package layout

```text
vultron/metadata/
    __init__.py
    base.py              # shared NonEmptyStr, NonEmptyStrList
    notes/
        __init__.py
        schema.py        # NoteStatus, NotesFrontmatter
        loader.py        # load_notes_registry()
    specs/               # future — IDEA-26042402
        __init__.py
        schema.py
        loader.py
```

---

## Pytest Validation Test

```python
# test/metadata/test_notes_frontmatter.py
import pytest
from vultron.metadata.notes.loader import load_notes_registry

def test_all_notes_files_have_valid_frontmatter():
    """Every notes/*.md (except README.md) must parse cleanly."""
    registry = load_notes_registry()
    assert len(registry) > 0, "Notes registry must not be empty"
    # If load_notes_registry() raises, the test fails with the validation error.
```

Mirror source layout: `test/metadata/` parallels `vultron/metadata/`.

---

## Pre-Commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: validate-notes-frontmatter
      name: Validate notes frontmatter
      entry: python -c "
        from vultron.metadata.notes.loader import load_notes_registry;
        load_notes_registry()
      "
      language: python
      files: ^notes/.*\.md$
      exclude: ^notes/README\.md$
      pass_filenames: false
```

This re-validates the full registry on any notes change, ensuring no file
is accidentally broken by a related edit.

---

## Migration Checklist for Existing Files

For each `notes/*.md` file (except `README.md`), add a frontmatter block with:

1. `title`: copy from the `# H1` heading
2. `status`: choose from `active | draft | superseded | archived` based on
   the file's current relevance
3. `description`: paste or paraphrase the first paragraph or "Load when" line
4. `related_specs`: list any `specs/*.md` files explicitly cross-referenced
5. `related_notes`: list any other `notes/*.md` files cross-referenced
6. `relevant_packages`: list any Python packages central to the topic

Most files warrant `status: active`. Files that have been explicitly replaced
should use `status: superseded` with `superseded_by` pointing to the replacement.

---

## Layer and Import Rules

- `vultron/metadata/` is a **standalone tooling layer**.
- It MUST NOT import from `vultron/core/`, `vultron/wire/`, or
  `vultron/adapters/`.
- It MAY be imported by test files and CLI tools.
- It uses only `pydantic`, `pyyaml` (already in `pyproject.toml`), and
  the standard library.

---

## Future: Registry and Query Tool (Deferred)

When IDEA-26042402 (YAML specs) is also implemented, a unified
`vultron/metadata/registry.py` can combine both loaders and expose:

```python
def relevant_context(topic: str) -> dict:
    """Return notes and specs whose frontmatter relates to `topic`."""
    ...
```

Matching strategy options (to be decided in that task):

- Keyword substring match on `title` + `description`
- File-path inclusion in `related_notes` / `related_specs` cross-references
- Tag/keyword list field added to frontmatter at that time

The `notes/README.md` can also be generated from the registry at that point,
replacing manual summaries with content derived from the `description` fields.
