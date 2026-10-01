"""Pydantic schema for ``specs/*.yaml`` structured requirement files.

Schema requirements: specs/spec-registry.yaml SR-02.

Design principle: YAML is the authoritative data source.  The schema
validates what is present but does **not** silently inject defaults for
absent fields.  ``kind`` is required on every individual spec item;
``scope`` is required at the file level and optional at the group level.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.metadata.base import NonEmptyStr

#: A fully-qualified requirement ID as it appears in prose — ``PREFIX-NN-NNN``
#: (MS-04-001): 2–8 uppercase letters, two-digit group, three-digit index.
#: ``\b`` on both sides keeps ``ADR-0001``, semantic versions, and a prefix
#: that merely ends in another topic's letters from matching. Shared by the
#: spec linter, bundle-fit, and the citation ratchets so the ID grammar is
#: defined once.
SPEC_ID_CITATION_RE = re.compile(r"\b[A-Z]{2,8}-\d{2}-\d{3}\b")

SpecIdStr = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z]{2,8}(-\d{2}(-\d{3}[a-z]?)?)?$"),
]

# Structured ADR reference (SR-02, MS-11-004): ``ADR-NNNN`` form. Kept separate
# from SpecIdStr — ADR IDs are four-digit and would not match the spec ID
# pattern — so an amended ADR can be traced to its dependent specs via the edges
# graph rather than only free-text rationale prose.
AdrIdStr = Annotated[
    str,
    StringConstraints(pattern=r"^ADR-\d{4}$"),
]

StoryIdStr = Annotated[
    str,
    StringConstraints(pattern=r"^story_\d{4}_\d{3}$"),
]


class RFC2119Tier(StrEnum):
    """The three strengths RFC 2119 defines, each pairing a keyword with its
    negation (MS-02-003).

    ``MUST NOT`` is as binding as ``MUST`` and ``SHOULD NOT`` as ``SHOULD``, so
    a gate that selects requirements by strength names a tier, never a keyword.
    """

    MUST = "MUST"
    SHOULD = "SHOULD"
    MAY = "MAY"


class RFC2119Priority(StrEnum):
    """RFC 2119 priority levels for requirements (SR-02-003).

    :attr:`tier` is the single shared tiering (MS-02-004). Code that selects
    requirements by priority asks it — ``spec.priority.is_must_tier``, or
    ``spec.priority.tier is RFC2119Tier.SHOULD`` — and never compares against
    individual members; a static check in ``test/metadata/specs/`` fails on
    the literal comparison.
    """

    MUST = "MUST"
    MUST_NOT = "MUST_NOT"
    SHOULD = "SHOULD"
    SHOULD_NOT = "SHOULD_NOT"
    MAY = "MAY"

    @property
    def tier(self) -> RFC2119Tier:
        """The tier this keyword belongs to: a negation shares its positive's."""
        return _PRIORITY_TIERS[self]

    @property
    def is_must_tier(self) -> bool:
        """``MUST`` or ``MUST_NOT`` — the absolute tier."""
        return self.tier is RFC2119Tier.MUST


#: The one place a keyword is assigned its tier (MS-02-004). Every member has
#: an entry; ``test_schema.py`` asserts the mapping is total.
_PRIORITY_TIERS: dict[RFC2119Priority, RFC2119Tier] = {
    RFC2119Priority.MUST: RFC2119Tier.MUST,
    RFC2119Priority.MUST_NOT: RFC2119Tier.MUST,
    RFC2119Priority.SHOULD: RFC2119Tier.SHOULD,
    RFC2119Priority.SHOULD_NOT: RFC2119Tier.SHOULD,
    RFC2119Priority.MAY: RFC2119Tier.MAY,
}


class AdrStatus(StrEnum):
    """Valid ADR ``status:`` frontmatter values (MS-14-001, ADR-0043).

    The status field is the confidence signal coding agents read; a fixed
    vocabulary lets the linter typecheck it the way spec fields are checked
    against their StrEnums. See the decision tree in ``notes/specs-vs-adrs.md``
    for how to choose a value.

    A retired ADR uses ``SUPERSEDED`` with a separate ``superseded_by:``
    frontmatter field (the project convention, see
    ``notes/notes-frontmatter.md``). The linter also tolerates the inline MADR
    form ``superseded by <link>`` by normalising it to ``SUPERSEDED`` before
    the enum check.
    """

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACCEPTED_PROVISIONAL = "accepted-provisional"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


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
    SCENARIO_START = "scenario_start"


class Trigger(BaseModel):
    """A typed trigger that activates a behavioral spec group (SR-02-018).

    ``type`` identifies the category of trigger; ``value`` names the specific
    message (e.g. ``"EP"``) or state (e.g. ``"RM.VALID"``) within that
    category. For ``scenario_start`` triggers, ``value`` names the scenario
    (e.g. ``"fv"``, ``"fvv"``).
    """

    model_config = ConfigDict(extra="forbid")

    type: TriggerType
    value: str


class SpecKind(StrEnum):
    """Portability tier for a spec requirement (SR-02-005).

    The four tiers form a portability hierarchy.  Use them to filter which
    specs apply to your project:

    - ``protocol``     — Required for Vultron compliance — any implementation
                         in any language must satisfy this.  Covers wire
                         behaviour, state machine invariants, behavioural
                         contracts, message semantics, and protocol rules.
    - ``architecture`` — Implementation-independent structural guidance —
                         transferable across languages and frameworks, but not
                         required for Vultron compliance per se.  Covers
                         hexagonal boundaries, event-driven dispatch,
                         port/adapter patterns, fail-fast principles.
    - ``project``      — Specific to this codebase — Python paths, BT nodes,
                         py_trees, pydantic, factory names, module
                         organisation, endpoint conventions.
    - ``process``      — How we run this project — CI config, GitHub workflow,
                         agent conventions, docs standards, spec authoring
                         rules.

    Portability use cases
    ~~~~~~~~~~~~~~~~~~~~~
    - Implement Vultron in any language          → ``protocol``
    - Understand the reference architecture      → ``protocol`` + ``architecture``
    - Contribute to this Python codebase         → ``protocol`` + ``architecture`` + ``project``
    - Contribute to this project (incl. process) → all four tiers
    """

    PROTOCOL = "protocol"
    ARCHITECTURE = "architecture"
    PROJECT = "project"
    PROCESS = "process"


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
    BEHAVIORAL = "behavioral"


class LintWarningCode(StrEnum):
    """Named linter warnings that can be suppressed via ``lint_suppress``
    (SR-02-011)."""

    TESTABLE_WITHOUT_STEPS = "testable_without_steps"
    RATIONALE_TOO_LONG = "rationale_too_long"
    MISSING_TAGS = "missing_tags"
    DANGLING_ADR_REF = "dangling_adr_ref"
    PHANTOM_PATH_REF = "phantom_path_ref"
    PHANTOM_SYMBOL_REF = "phantom_symbol_ref"
    MUST_WITHOUT_VERIFICATION = "must_without_verification"
    MISSING_STORY_REFERENCE = "missing_story_reference"
    PROTOCOL_KIND_WITH_CODE_REFERENCE = "protocol_kind_with_code_reference"


class Relationship(BaseModel):
    """Cross-spec traceability link (SR-02-015)."""

    model_config = ConfigDict(extra="forbid")

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

    ``kind`` is required on every spec item.  ``scope`` is optional and
    inherits from the containing file when absent.
    """

    model_config = ConfigDict(extra="forbid")

    id: SpecIdStr
    priority: RFC2119Priority
    kind: SpecKind
    statement: NonEmptyStr
    rationale: NonEmptyStr | None = None
    testable: bool = True
    deprecated: bool = False
    superseded_by: SpecIdStr | None = None
    verification: NonEmptyStr | None = None
    note: NonEmptyStr | None = None
    tracking_issue: str | None = None
    trigger: Trigger | None = None
    scope: list[Scope] | None = None
    tags: list[SpecTag] | None = None
    references: list[str] | None = None
    exceptions: list[NonEmptyStr] | None = None
    relationships: list[Relationship] | None = None
    adr: list[AdrIdStr] | None = None
    lint_suppress: list[LintWarningCode] | None = None
    stories: list[StoryIdStr] | None = None

    @field_validator(
        "scope",
        "tags",
        "references",
        "exceptions",
        "relationships",
        "adr",
        "lint_suppress",
        "stories",
    )
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
    ``description`` is required and provides a human-readable prose summary of
    the full precondition, synthesised from all typed fields present.  Typed
    fields that don't map to ``rm_state``, ``em_state``, ``cs_pattern``, or
    ``role`` MUST be described here as a prose fallback.
    """

    model_config = ConfigDict(extra="forbid")

    rm_state: list[RM] | None = None
    em_state: list[EM] | None = None
    role: list[CVDRole] | None = None
    cs_pattern: str | None = None
    description: NonEmptyStr


class BehaviorStep(BaseModel):
    """A single step in a behavioral spec sequence (SR-02-016)."""

    model_config = ConfigDict(extra="forbid")

    order: int
    actor: str
    action: str
    expected: str | None = None


class Postcondition(BaseModel):
    """A postcondition for a behavioral spec."""

    model_config = ConfigDict(extra="forbid")

    description: NonEmptyStr


class BehavioralSpec(StatementSpec):
    """A spec with structured pre/step/post conditions (SR-02-010)."""

    model_config = ConfigDict(extra="forbid")

    preconditions: list[Precondition] | None = None
    steps: list[BehaviorStep] | None = None
    postconditions: list[Postcondition] | None = None

    @field_validator("preconditions", "steps", "postconditions")
    @classmethod
    def _behavioral_nonempty_if_present(
        cls, v: list | None, info: object
    ) -> list | None:
        if v is not None and len(v) == 0:
            field_name = getattr(info, "field_name", "list field")
            raise ValueError(f"{field_name} must be non-empty if present")
        return v


Spec = BehavioralSpec | StatementSpec


class SpecGroup(BaseModel):
    """A logical grouping of specs within a file (SR-02-012).

    ``scope`` is an optional override; when absent, the value is inherited
    from the containing :class:`SpecFile`.

    ``trigger`` annotates behavioral groups with the event that activates them,
    enabling conformance tooling to classify groups by trigger kind without
    parsing prose titles.
    """

    model_config = ConfigDict(extra="forbid")

    id: SpecIdStr
    title: NonEmptyStr
    description: NonEmptyStr | None = None
    rationale: NonEmptyStr | None = None
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

    ``scope`` is required at the file level and serves as the default for
    groups and specs that do not override it (SR-02-014).  ``kind`` is now
    required on each individual spec item rather than at the file level.

    There is deliberately no ``version`` field (SR-01-003): the release tag
    pins spec content and requirement IDs are the citation address.
    ``extra="forbid"`` makes a file that declares one fail to load.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: NonEmptyStr
    description: NonEmptyStr
    scope: list[Scope]
    tags: list[SpecTag] | None = None
    relationships: list[Relationship] | None = None
    groups: list[SpecGroup]

    @field_validator("scope")
    @classmethod
    def _scope_nonempty(cls, v: list) -> list:
        if not v:
            raise ValueError("scope must not be empty")
        return v

    @field_validator("tags", "relationships")
    @classmethod
    def _tags_nonempty_if_present(cls, v: list | None) -> list | None:
        if v is not None and len(v) == 0:
            raise ValueError("list field must be non-empty if present")
        return v

    @field_validator("groups")
    @classmethod
    def _groups_nonempty(cls, v: list) -> list:
        if not v:
            raise ValueError("groups must not be empty")
        return v
