"""Pydantic schema for ``specs/*.yaml`` structured requirement files.

Schema requirements: specs/spec-registry.md SR-02.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Union

from pydantic import BaseModel, StringConstraints

from vultron.metadata.base import NonEmptyStr

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


class SpecKind(StrEnum):
    """Whether a spec is implementation-agnostic or language/framework-specific
    (SR-02-005)."""

    GENERAL = "general"
    IMPLEMENTATION = "implementation"


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


class Relationship(BaseModel):
    """Cross-spec traceability link (SR-02-015)."""

    rel_type: RelationType
    spec_id: SpecIdStr
    note: str | None = None


class StatementSpec(BaseModel):
    """A single normative statement requirement (SR-02-009)."""

    id: SpecIdStr
    priority: RFC2119Priority
    statement: NonEmptyStr
    rationale: NonEmptyStr
    testable: bool = True
    kind: SpecKind = SpecKind.GENERAL
    scope: list[Scope] = [Scope.PRODUCTION]
    tags: list[SpecTag] = []
    relationships: list[Relationship] = []
    lint_suppress: list[LintWarningCode] = []


class Precondition(BaseModel):
    """A precondition for a behavioral spec."""

    description: str


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

    preconditions: list[Precondition] = []
    steps: list[BehaviorStep] = []
    postconditions: list[Postcondition] = []


Spec = Union[BehavioralSpec, StatementSpec]


class SpecGroup(BaseModel):
    """A logical grouping of specs within a file (SR-02-012)."""

    id: SpecIdStr
    title: NonEmptyStr
    description: str | None = None
    kind: SpecKind = SpecKind.GENERAL
    scope: list[Scope] = [Scope.PRODUCTION]
    specs: list[Spec]


class SpecFile(BaseModel):
    """One YAML spec file with its groups and file-level metadata (SR-02-013).

    ``kind`` and ``scope`` serve as defaults; individual specs may override
    them (SR-02-014).
    """

    id: str
    title: NonEmptyStr
    description: NonEmptyStr
    version: NonEmptyStr
    kind: SpecKind = SpecKind.GENERAL
    scope: list[Scope] = [Scope.PRODUCTION]
    groups: list[SpecGroup]
