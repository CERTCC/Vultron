"""Pydantic models for a spec file, its groups and its requirement items."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.metadata.base import NonEmptyStr
from vultron.metadata.specs.schema.ids import (
    AdrIdStr,
    IssueRefStr,
    SpecIdStr,
    StoryIdStr,
)
from vultron.metadata.specs.schema.vocabulary import (
    LintWarningCode,
    RelationType,
    RFC2119Priority,
    Scope,
    SpecKind,
    SpecTag,
    TriggerType,
)


class Trigger(BaseModel):
    """A typed trigger that activates a behavioral spec group (SR-02-018).

    ``type`` identifies the category of trigger; ``value`` names the specific
    message (e.g. ``"EP"``) or state (e.g. ``"RM.VALID"``) within that
    category. For ``scenario_start`` triggers, ``value`` names the scenario
    (e.g. ``"rv"``, ``"rvv"``).
    """

    model_config = ConfigDict(extra="forbid")

    type: TriggerType
    value: str


class Relationship(BaseModel):
    """Cross-spec traceability link (SR-02-015)."""

    model_config = ConfigDict(extra="forbid")

    rel_type: RelationType
    spec_id: SpecIdStr
    note: str | None = None


#: Keys a requirement once used to stay in place after it was superseded.
#: The schema declares neither: a superseded requirement is removed and
#: archived instead (MS-04-005, MS-09-001).
_RETIRED_LIFECYCLE_KEYS: tuple[str, ...] = ("deprecated", "superseded_by")


def _refuse_lifecycle_keys(item: object) -> None:
    """Refuse ``deprecated:``/``superseded_by:`` with the retirement path.

    ``extra="forbid"`` (SR-02-022) would already reject either key, but only
    as an unnamed extra input, once per branch of the ``Spec`` union. This
    names the rule and the command that replaces the key, so spec-lint's
    refusal stays actionable (MS-09-001, MS-09-007). Input that is not a
    mapping is left for the model's own type error.
    """
    if not isinstance(item, dict):
        return
    found = [k for k in _RETIRED_LIFECYCLE_KEYS if k in item]
    if found:
        spec_id = item.get("id", "<unknown>")
        keys = ", ".join(f"'{k}:'" for k in found)
        raise ValueError(
            f"Spec '{spec_id}' carries {keys}; a superseded requirement is "
            f"removed, not marked in place. Archive it with "
            f"`uv run spec-retire {spec_id}` instead (MS-09-001)"
        )


def _check_nonempty_list(v: list | None, field_name: str) -> list | None:
    """Shared validator: if present, must be non-empty."""
    if v is not None and len(v) == 0:
        raise ValueError(f"{field_name} must be non-empty if present")
    return v


class StatementSpec(BaseModel):
    """A single normative statement requirement (SR-02-009).

    ``kind`` and ``rationale`` are required on every spec item (MS-10-012).
    ``scope`` is optional and inherits from the containing file when absent.
    """

    model_config = ConfigDict(extra="forbid")

    id: SpecIdStr
    priority: RFC2119Priority
    kind: SpecKind
    statement: NonEmptyStr
    rationale: NonEmptyStr
    testable: bool = True
    verification: NonEmptyStr | None = None
    #: Set only on a MUST-tier item with no ``verification:`` (MS-10-006).
    #: Distinct from ``tracking_issue``, which tracks planned implementation.
    verification_debt: IssueRefStr | None = None
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
    """A precondition for a behavioral spec (SR-02-019, SR-02-028).

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

    @field_validator("specs", mode="before")
    @classmethod
    def _refuse_lifecycle_keys_once(cls, v: object) -> object:
        """Check raw items before the ``Spec`` union splits them (MS-09-001).

        Run here rather than on ``StatementSpec``: both union branches would
        each raise the refusal, printing it twice for one key.
        """
        if isinstance(v, list):
            for item in v:
                _refuse_lifecycle_keys(item)
        return v

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
    required on each individual spec item rather than at the file level
    (SR-02-027).

    There is deliberately no ``version`` field (SR-01-003, SR-02-025): the
    release tag pins spec content and requirement IDs are the citation address.
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
