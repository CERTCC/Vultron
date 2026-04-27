---
title: Spec Registry Design
status: active
related_specs:
  - specs/spec-registry.yaml
  - specs/notes-frontmatter.yaml
related_notes:
  - notes/append-only-file-handling.md
relevant_packages:
  - vultron/metadata/specs
---

# Spec Registry Design

Implementation guidance for converting `specs/*.md` to structured YAML files
governed by Pydantic models (`vultron/metadata/specs/`). Mirrors the existing
`vultron/metadata/notes/` pattern.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Migration strategy | Full replacement: `.md` → `.yaml`; `.md` deleted | Dual-format doubles maintenance; incremental leaves mixed world for agents |
| YAML file naming | 1-to-1 kebab-case (same as current `.md` names) | Minimal disruption; easy cross-reference by topic |
| Module location | `vultron/metadata/specs/` | Mirrors `vultron/metadata/notes/`; `metadata/` is the home for structured tooling |
| Spec model variants | `StatementSpec` + `BehavioralSpec` discriminated union | Zero migration cost; behavioral fields optional; richer future expressiveness |
| Versioning | File-level semver string only | Individual spec versioning via git history; per-spec `since` adds overhead |
| Pytest marker behavior | Advisory warning (non-blocking) | Linter is the hard gate; test runs shouldn't break on spec refactors |
| Pre-commit hook | Yes, on `specs/*.yaml` changes | Consistent with `validate-notes-frontmatter` pattern |
| Context generation | Both markdown renderer + JSON exporter | Agents prefer markdown; programmatic consumers prefer JSON |
| Rationale length | Soft linter warning (> 500 chars) | Model-level hard cap would reject valid edge cases |
| `testable: false` check | Advisory warning, suppressible via `lint_suppress` | Needed signal without reducing SNR for known intentional cases |
| Tag vocabulary | Controlled `StrEnum` (linted) | Prevents tag drift; free-form strings accumulate noise over time |
| Session scope | Spec + notes + stub modules; all impl tasks as single PR group | The whole feature is one coherent deliverable |

---

## `SpecTag` Initial Vocabulary

Derived from the topic areas covered by existing `specs/*.md` files:

| Tag | Coverage |
|---|---|
| `authentication` | Auth and authorization requirements |
| `behavior-tree` | BT integration, node design, composability |
| `ci-cd` | CI/CD pipeline and GitHub Actions |
| `code-style` | Formatting, naming, import conventions |
| `configuration` | App config, env vars, `AppConfig` |
| `demo` | Demo scripts and scenario coverage |
| `documentation` | Docs structure, Diátaxis, project docs |
| `error-handling` | Exception hierarchy, error responses |
| `federation` | Multi-actor, cross-server delivery |
| `idempotency` | Duplicate detection, idempotent processing |
| `logging` | Structured logging, log levels, audit |
| `messaging` | ActivityStreams, wire format, AS2 mapping |
| `observability` | Health checks, monitoring |
| `performance` | Throughput, latency, rate limiting |
| `persistence` | DataLayer, SQLite, TinyDB |
| `protocol` | CVD protocol conformance, RM/EM/CS |
| `security` | SHA pinning, secrets, encryption |
| `state-machine` | RM/EM/CS/VFD state enums and transitions |
| `testing` | Test coverage, pytest, test organization |
| `tooling` | Developer tooling, pre-commit, linters |
| `wire-format` | AS2 vocabulary, serialization, rehydration |

---

## Module Structure

```text
vultron/metadata/specs/
├── __init__.py        # re-exports load_registry, SpecRegistry
├── schema.py          # all Pydantic models and StrEnums
├── registry.py        # SpecRegistry + load_registry()
├── lint.py            # lint() function + CLI entry point
└── render.py          # markdown renderer + JSON exporter
```

---

## Pydantic Schema Patterns

### StrEnums

```python
from enum import StrEnum

class RFC2119Priority(StrEnum):
    MUST       = "MUST"
    MUST_NOT   = "MUST_NOT"
    SHOULD     = "SHOULD"
    SHOULD_NOT = "SHOULD_NOT"
    MAY        = "MAY"

class SpecKind(StrEnum):
    GENERAL        = "general"
    IMPLEMENTATION = "implementation"

class Scope(StrEnum):
    PROTOTYPE  = "prototype"
    PRODUCTION = "production"

class RelationType(StrEnum):
    IMPLEMENTS  = "implements"
    SUPERSEDES  = "supersedes"
    EXTENDS     = "extends"
    DEPENDS_ON  = "depends_on"
    CONFLICTS   = "conflicts"
    REFINES     = "refines"
    DERIVES_FROM = "derives_from"
    VERIFIES    = "verifies"
    PART_OF     = "part_of"
    CONSTRAINS  = "constrains"

class LintWarningCode(StrEnum):
    TESTABLE_WITHOUT_STEPS = "testable_without_steps"
    RATIONALE_TOO_LONG     = "rationale_too_long"
    MISSING_TAGS           = "missing_tags"

class SpecTag(StrEnum):
    AUTHENTICATION = "authentication"
    BEHAVIOR_TREE  = "behavior-tree"
    CI_CD          = "ci-cd"
    CODE_STYLE     = "code-style"
    CONFIGURATION  = "configuration"
    DEMO           = "demo"
    DOCUMENTATION  = "documentation"
    ERROR_HANDLING = "error-handling"
    FEDERATION     = "federation"
    IDEMPOTENCY    = "idempotency"
    LOGGING        = "logging"
    MESSAGING      = "messaging"
    OBSERVABILITY  = "observability"
    PERFORMANCE    = "performance"
    PERSISTENCE    = "persistence"
    PROTOCOL       = "protocol"
    SECURITY       = "security"
    STATE_MACHINE  = "state-machine"
    TESTING        = "testing"
    TOOLING        = "tooling"
    WIRE_FORMAT    = "wire-format"
```

### ID Constraint

```python
from typing import Annotated
from pydantic import StringConstraints

SpecIdStr = Annotated[
    str,
    StringConstraints(pattern=r'^[A-Z]{2,8}(-\d{2}(-\d{3})?)?$')
]
```

### Core Models

```python
from pydantic import BaseModel

class Relationship(BaseModel):
    rel_type: RelationType
    spec_id:  SpecIdStr
    note:     str | None = None

class StatementSpec(BaseModel):
    id:            SpecIdStr
    priority:      RFC2119Priority
    statement:     str
    rationale:     str
    testable:      bool              = True
    kind:          SpecKind          = SpecKind.GENERAL
    scope:         list[Scope]       = [Scope.PRODUCTION]
    tags:          list[SpecTag]     = []
    relationships: list[Relationship] = []
    lint_suppress: list[LintWarningCode] = []

class Precondition(BaseModel):
    description: str

class BehaviorStep(BaseModel):
    order:    int
    actor:    str
    action:   str
    expected: str | None = None

class Postcondition(BaseModel):
    description: str

class BehavioralSpec(StatementSpec):
    preconditions:  list[Precondition]  = []
    steps:          list[BehaviorStep]  = []
    postconditions: list[Postcondition] = []

# A spec resolves to StatementSpec or BehavioralSpec based on behavioral fields
Spec = StatementSpec | BehavioralSpec
```

### Discriminated Union Resolution

Use a model validator on a wrapper to dispatch:

```python
from pydantic import model_validator

class SpecWrapper(BaseModel):
    """Thin wrapper that routes to the correct Spec variant."""

    @model_validator(mode="before")
    @classmethod
    def route_to_variant(cls, data: dict) -> StatementSpec | BehavioralSpec:
        behavioral_keys = {"preconditions", "steps", "postconditions"}
        if any(k in data for k in behavioral_keys):
            return BehavioralSpec.model_validate(data)
        return StatementSpec.model_validate(data)
```

### Group and File Models

```python
class SpecGroup(BaseModel):
    id:          SpecIdStr
    title:       str
    description: str | None    = None
    kind:        SpecKind      = SpecKind.GENERAL
    scope:       list[Scope]   = [Scope.PRODUCTION]
    specs:       list[Spec]

class SpecFile(BaseModel):
    id:          str
    title:       str
    description: str
    version:     str            # semver string
    kind:        SpecKind       = SpecKind.GENERAL
    scope:       list[Scope]    = [Scope.PRODUCTION]
    groups:      list[SpecGroup]
```

---

## Registry Pattern

```python
from pathlib import Path
from pydantic import BaseModel, PrivateAttr
import yaml

class SpecRegistry(BaseModel):
    files: list[SpecFile]

    _index:       dict[SpecIdStr, Spec]      = PrivateAttr(default_factory=dict)
    _group_index: dict[SpecIdStr, SpecGroup] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: object) -> None:
        for file in self.files:
            for group in file.groups:
                self._register_group(group)
                for spec in group.specs:
                    self._register_spec(spec)

    def _register_spec(self, spec: Spec) -> None:
        if spec.id in self._index:
            raise ValueError(f"Duplicate spec ID: {spec.id}")
        self._index[spec.id] = spec

    def get(self, spec_id: SpecIdStr) -> Spec:
        if spec_id not in self._index:
            raise KeyError(f"Unknown spec ID: {spec_id}")
        return self._index[spec_id]

    def validate_cross_references(self) -> list[str]:
        errors = []
        for spec_id, spec in self._index.items():
            for rel in spec.relationships:
                if rel.spec_id not in self._index:
                    errors.append(
                        f"{spec_id}: relationship target '{rel.spec_id}' not found"
                    )
        return errors


def load_registry(spec_dir: Path) -> SpecRegistry:
    files = []
    for yaml_path in sorted(spec_dir.glob("*.yaml")):
        raw = yaml.safe_load(yaml_path.read_text())
        files.append(SpecFile.model_validate(raw))
    return SpecRegistry(files=files)
```

---

## Linter Patterns

### Hard Errors vs Advisory Warnings

```python
def lint(spec_dir: Path) -> int:
    """Returns 0 (clean) or 1 (hard errors found)."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        registry = load_registry(spec_dir)
    except (ValidationError, ValueError) as e:
        print(f"[FATAL] Registry load failed:\n{e}")
        return 1

    # Hard errors
    errors.extend(registry.validate_cross_references())
    # ... prefix consistency checks, ID format checks

    # Advisory warnings (respect lint_suppress)
    for spec_id, spec in registry._index.items():
        suppressed = set(spec.lint_suppress)

        if (
            not spec.testable
            and not getattr(spec, "steps", [])
            and LintWarningCode.TESTABLE_WITHOUT_STEPS not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: testable=false but no behavioral steps"
            )

        if (
            len(spec.rationale) > 500
            and LintWarningCode.RATIONALE_TOO_LONG not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: rationale exceeds 500 characters"
            )

    for w in warnings:
        print(w)
    for e in errors:
        print(f"[ERROR] {e}")

    return 0 if not errors else 1
```

### `lint_suppress` Usage Example (in YAML)

```yaml
- id: SR-02-010
  priority: MUST
  statement: "..."
  rationale: "This requirement is verified by human review of the migration output."
  testable: false
  lint_suppress: [testable_without_steps]
```

---

## Pytest Integration Pattern

```python
# conftest.py
from pathlib import Path
import pytest
from vultron.metadata.specs import load_registry

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "spec(id): mark test as verifying a specific spec requirement ID"
    )

def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    registry = load_registry(Path("specs/"))
    for item in items:
        marker = item.get_closest_marker("spec")
        if marker:
            spec_id = marker.args[0]
            try:
                registry.get(spec_id)
            except KeyError:
                item.warn(
                    pytest.PytestWarning(
                        f"Test references unknown spec ID: {spec_id}"
                    )
                )
```

Test usage:

```python
@pytest.mark.spec("SR-01-001")
def test_yaml_replaces_md():
    ...
```

---

## Pre-commit Hook Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: spec-lint
        name: Validate spec registry
        entry: python -m vultron.metadata.specs.lint specs/
        language: python
        types: [yaml]
        files: ^specs/
        pass_filenames: false
```

---

## YAML File Layout Example

```yaml
# specs/handler-protocol.yaml
id: HP
title: "Handler Protocol"
description: "Handler use-case contract and implementation patterns"
version: "1.0.0"
kind: general
scope: [production]

groups:
  - id: HP-01
    title: "Use-Case Structure"
    specs:
      - id: HP-01-001
        priority: MUST
        statement: >
          Handler use-case classes MUST accept (dl: DataLayer,
          request: XxxReceivedEvent) in __init__ and implement
          execute() -> None.
        rationale: >
          Enforces the UseCase Protocol contract; enables uniform
          dispatch and dependency injection.
        testable: true
        tags: [protocol, testing]
        relationships:
          - rel_type: implements
            spec_id: ARCH-03-001
```

---

## Migration Approach

1. For each `specs/TOPIC.md`, parse the requirement bullets manually or with
   a script into the YAML structure.
2. Run `python -m vultron.metadata.specs.lint specs/` — fix all errors.
3. Delete the `.md` source file.
4. Keep `specs/README.md` and `specs/meta-specifications.yaml` as Markdown.

The migration is expected to require human review of each file; a migration
script is a starting point, not a complete solution.

---

## Layer and Import Rules

- `vultron/metadata/specs/` MUST NOT import from `vultron/core/`, `vultron/wire/`,
  or any adapter layer — it is a standalone tooling module.
- `vultron/metadata/specs/` MAY import from `vultron/metadata/base.py` for
  shared type aliases (`NonEmptyStr`, `NonEmptyStrList`).
- External dependencies: `pydantic`, `pyyaml` (already in project); no new
  runtime dependencies required.

---

## Testing Patterns

```python
# test/metadata/specs/test_schema.py
from vultron.metadata.specs.schema import (
    StatementSpec, BehavioralSpec, RFC2119Priority, SpecTag
)

def test_statement_spec_valid():
    spec = StatementSpec(
        id="SR-01-001",
        priority=RFC2119Priority.MUST,
        statement="The system MUST do X.",
        rationale="Because Y.",
    )
    assert spec.testable is True
    assert spec.tags == []

def test_behavioral_spec_detected():
    spec = BehavioralSpec(
        id="SR-01-002",
        priority=RFC2119Priority.MUST,
        statement="...",
        rationale="...",
        steps=[{"order": 1, "actor": "system", "action": "does X"}],
    )
    assert spec.steps[0].order == 1

def test_duplicate_id_raises():
    from vultron.metadata.specs.registry import SpecRegistry, SpecFile, SpecGroup
    # ... build two files with same spec ID, assert ValueError
```
