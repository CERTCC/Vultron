"""Pydantic schema for ``specs/*.yaml`` structured requirement files.

Schema requirements: specs/spec-registry.yaml SR-02.

Design principle: YAML is the authoritative data source.  The schema
validates what is present but does **not** silently inject defaults for
absent fields.  Inheritable fields (``kind``, ``scope``) are required at
the file level and optional at group/spec level; effective values are
resolved by the registry loader, not by Pydantic defaults.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Union

from pydantic import BaseModel, StringConstraints, field_validator

from vultron.metadata.base import NonEmptyStr
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole

SpecIdStr = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z]{2,8}(-\d{2}(-\d{3})?)?$"),
]


class RFC2119Priority(StrEnum):
    """RFC 2119 priority levels for requirements (SR-02-003)."""

    MUST = "MUST"
    MUST_NOT = "MUST_NOT"
    SHOULD = "SHOULD"
    SHOULD_NOT = "SHOULD_NOT"
    MAY = "MAY"


class RelationType(StrEnum):
    """Relationship types between spec requirements (SR-02-004)."""

    IMPLEMENTS = "implements"
    SUPERSEDES = "supersedes"
    EXTENDS = "extends"
    DEPENDS_ON = "depends_on"
    CONFLICTS = "conflicts"
    REFINES = "refines"
    DERIVES_FROM = "derives_from"
    VERIFIES = "verifies"
    PART_OF = "part_of"
    CONSTRAINS = "constrains"
    SATISFIES = "satisfies"


class TriggerType(StrEnum):
    """Enumeration of known behavioral trigger kinds (SR-02-017).

    Enumerating trigger kinds allows a third kind (e.g. ``timer_expired``) to
    be added explicitly rather than via free text, and lets conformance tooling
    classify groups without parsing prose.
    """

    MESSAGE_RECEIVED = "message_received"
    STATE_ENTERED = "state_entered"


class Trigger(BaseModel):
    """A typed trigger that activates a behavioral spec group (SR-02-018).

    ``type`` identifies the category of trigger; ``value`` names the specific
    message (e.g. ``"EP"``) or state (e.g. ``"RM.VALID"``) within that
    category.
    """

    type: TriggerType
    value: str


class SpecKind(StrEnum):
    """Portability tier for a spec requirement (SR-02-005).

    The six tiers form a portability hierarchy.  Use them to filter which
    specs apply to your project:

    - ``general``        — Universal: any project, any language.
                           Examples: idempotency, linter discipline, CI
                           security.
    - ``pattern``        — Architectural / framework approach: language-agnostic
                           and not CVD-specific.
                           Examples: hexagonal architecture, BT composability,
                           event-driven dispatch.
    - ``domain``         — Vultron / CVD protocol: language-agnostic.
                           Examples: embargo lifecycle, case management, AS2
                           semantics, MPCVD state machines.
    - ``language``       — Python ecosystem: any Python project.
                           Examples: pydantic conventions, py_trees API, pytest,
                           FastAPI patterns.
    - ``implementation`` — This specific codebase.
                           Examples: file paths under ``vultron/``, class names
                           in ``vultron/core/``, notes frontmatter schema.
    - ``dev-process``    — This project's development and maintenance process.
                           Examples: skill workflows, history management,
                           spec authoring conventions, parallel agentic dev.

    Portability use cases
    ~~~~~~~~~~~~~~~~~~~~~
    - Implementing Vultron in Python          → general + pattern + domain + language + implementation
    - Implementing Vultron in another language → general + pattern + domain
    - Different domain, Python/BT/hex stack   → general + pattern + language
    - BT / hexagonal wisdom, any language      → general + pattern
    - Universal wisdom only                    → general
    - Contributing to this project            → all six tiers (include dev-process)
    """

    GENERAL = "general"
    PATTERN = "pattern"
    DOMAIN = "domain"
    LANGUAGE = "language"
    IMPLEMENTATION = "implementation"
    DEV_PROCESS = "dev-process"


class Scope(StrEnum):
    """Deployment scope for a spec requirement (SR-02-006)."""

    PROTOTYPE = "prototype"
    PRODUCTION = "production"


class SpecTag(StrEnum):
    """Controlled vocabulary of topic tags (SR-02-007).

    See ``notes/spec-registry.md`` for the full tag inventory and rationale.
    """

    AUTHENTICATION = "authentication"
    BEHAVIOR_TREE = "behavior-tree"
    CI_CD = "ci-cd"
    CODE_STYLE = "code-style"
    CONFIGURATION = "configuration"
    DEMO = "demo"
    DOCUMENTATION = "documentation"
    ERROR_HANDLING = "error-handling"
    FEDERATION = "federation"
    IDEMPOTENCY = "idempotency"
    LOGGING = "logging"
    MESSAGING = "messaging"
    OBSERVABILITY = "observability"
    PERFORMANCE = "performance"
    PERSISTENCE = "persistence"
    PROTOCOL = "protocol"
    SECURITY = "security"
    STATE_MACHINE = "state-machine"
    TESTING = "testing"
    TOOLING = "tooling"
    WIRE_FORMAT = "wire-format"


class LintWarningCode(StrEnum):
    """Named linter warnings that can be suppressed via ``lint_suppress``
    (SR-02-011)."""

    TESTABLE_WITHOUT_STEPS = "testable_without_steps"
    RATIONALE_TOO_LONG = "rationale_too_long"
    MISSING_TAGS = "missing_tags"
    DANGLING_ADR_REF = "dangling_adr_ref"


class Relationship(BaseModel):
    """Cross-spec traceability link (SR-02-015)."""

    rel_type: RelationType
    spec_id: SpecIdStr
    note: str | None = None


def _check_nonempty_list(v: list | None, field_name: str) -> list | None:
    """Shared validator: if present, must be non-empty."""
    if v is not None and len(v) == 0:
        raise ValueError(f"{field_name} must be non-empty if present")
    return v


class StatementSpec(BaseModel):
    """A single normative statement requirement (SR-02-009).

    Inheritable fields (``kind``, ``scope``) default to ``None``, meaning
    "inherit from parent group or file."  The registry loader resolves
    effective values after loading.
    """

    id: SpecIdStr
    priority: RFC2119Priority
    statement: NonEmptyStr
    rationale: NonEmptyStr | None = None
    testable: bool = True
    kind: SpecKind | None = None
    scope: list[Scope] | None = None
    tags: list[SpecTag] | None = None
    relationships: list[Relationship] | None = None
    lint_suppress: list[LintWarningCode] | None = None

    @field_validator("scope", "tags", "relationships", "lint_suppress")
    @classmethod
    def _nonempty_if_present(cls, v: list | None, info: object) -> list | None:
        if v is not None and len(v) == 0:
            field_name = getattr(info, "field_name", "list field")
            raise ValueError(f"{field_name} must be non-empty if present")
        return v


class Precondition(BaseModel):
    """A precondition for a behavioral spec (SR-02-019).

    Typed fields reference the stable protocol state-machine enums directly so
    conformance tooling can evaluate preconditions without parsing prose.
    At least one field must be provided; ``description`` is a prose fallback
    for conditions that don't map cleanly to the typed fields.
    """

    rm_state: list[RM] | None = None
    em_state: list[EM] | None = None
    cs_pattern: str | None = None
    role: list[CVDRole] | None = None
    description: str | None = None


class BehaviorStep(BaseModel):
    """A single step in a behavioral spec sequence (SR-02-016)."""

    order: int
    actor: str
    action: str
    expected: str | None = None


class Postcondition(BaseModel):
    """A postcondition for a behavioral spec."""

    description: str


class BehavioralSpec(StatementSpec):
    """A spec with structured pre/step/post conditions (SR-02-010)."""

    preconditions: list[Precondition] | None = None
    steps: list[BehaviorStep] | None = None
    postconditions: list[Postcondition] | None = None

    @field_validator("preconditions", "steps", "postconditions")
    @classmethod
    def _nonempty_if_present(cls, v: list | None, info: object) -> list | None:
        if v is not None and len(v) == 0:
            field_name = getattr(info, "field_name", "list field")
            raise ValueError(f"{field_name} must be non-empty if present")
        return v


Spec = Union[BehavioralSpec, StatementSpec]


class SpecGroup(BaseModel):
    """A logical grouping of specs within a file (SR-02-012).

    ``kind`` and ``scope`` are optional overrides; when absent, values are
    inherited from the containing :class:`SpecFile`.

    ``trigger`` annotates behavioral groups with the event that activates them,
    enabling conformance tooling to classify groups by trigger kind without
    parsing prose titles.
    """

    id: SpecIdStr
    title: NonEmptyStr
    description: NonEmptyStr | None = None
    kind: SpecKind | None = None
    scope: list[Scope] | None = None
    trigger: Trigger | None = None
    specs: list[Spec]

    @field_validator("scope")
    @classmethod
    def _nonempty_if_present(cls, v: list | None, info: object) -> list | None:
        if v is not None and len(v) == 0:
            field_name = getattr(info, "field_name", "list field")
            raise ValueError(f"{field_name} must be non-empty if present")
        return v

    @field_validator("specs")
    @classmethod
    def _specs_nonempty(cls, v: list) -> list:
        if not v:
            raise ValueError("specs must not be empty")
        return v


class SpecFile(BaseModel):
    """One YAML spec file with its groups and file-level metadata (SR-02-013).

    ``kind`` and ``scope`` are required at the file level and serve as
    defaults for groups and specs that do not override them (SR-02-014).
    """

    id: str
    title: NonEmptyStr
    description: NonEmptyStr
    version: NonEmptyStr
    kind: SpecKind
    scope: list[Scope]
    groups: list[SpecGroup]

    @field_validator("scope")
    @classmethod
    def _scope_nonempty(cls, v: list) -> list:
        if not v:
            raise ValueError("scope must not be empty")
        return v

    @field_validator("groups")
    @classmethod
    def _groups_nonempty(cls, v: list) -> list:
        if not v:
            raise ValueError("groups must not be empty")
        return v
