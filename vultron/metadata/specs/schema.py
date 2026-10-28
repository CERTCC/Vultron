"""Pydantic schema for ``specs/*.yaml`` structured requirement files.

Schema requirements: specs/spec-registry.yaml SR-02.

Design principle: YAML is the authoritative data source.  The schema
validates what is present but does **not** silently inject defaults for
absent fields.  ``kind`` is required on every individual spec item;
``scope`` is required at the file level and optional at the group level.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
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

#: A range of requirement IDs: a full start ID, then either a range word and a
#: full end ID (``CM-10-001 through CM-10-005``) or a dash or ``..`` and an end
#: that is a full ID, ``NN-NNN`` or ``NNN`` (``CM-10-001–005``,
#: ``CSB-18-002..004``). A word before a bare number is prose, not a range:
#: ``CM-10-001 to 100 actors`` must not expand a whole group. A plain hyphen is
#: not a range mark either: ``CM-10-001-005`` is too close to an ID typo.
_SPEC_ID_RANGE_RE = re.compile(
    r"\b(?P<prefix>[A-Z]{2,8})-(?P<group>\d{2})-(?P<index>\d{3})\s*(?:"
    r"\b(?:through|thru|to)\s+"
    r"(?P<word_prefix>[A-Z]{2,8})-(?P<word_group>\d{2})-(?P<word_index>\d{3})"
    r"|(?:–|—|\.\.)\s*"
    r"(?:(?:(?P<dash_prefix>[A-Z]{2,8})-)?(?P<dash_group>\d{2})-)?"
    r"(?P<dash_index>\d{3})"
    r")\b"
)

#: A slash list of IDs in one group: ``CLP-14-006/007/008``.
_SPEC_ID_SLASH_RE = re.compile(r"\b([A-Z]{2,8}-\d{2}-)\d{3}((?:/\d{3})+)\b")


def _id_key(spec_id: str) -> tuple[str, int, int] | None:
    parts = spec_id.split("-")
    if len(parts) != 3 or not (parts[1].isdigit() and parts[2].isdigit()):
        return None
    return parts[0], int(parts[1]), int(parts[2])


def cited_spec_ids(text: str, known_ids: Iterable[str]) -> set[str]:
    """Every requirement ID *text* names, with ranges and slash lists expanded.

    A literal ID (:data:`SPEC_ID_CITATION_RE`) is returned whether or not it is
    known. A range yields every ID in *known_ids* with the start's prefix that
    sorts between its ends, inclusive, so it may cross groups but never invents
    an ID; a range whose ends name different prefixes yields only those ends.
    A slash list ``PREFIX-NN-AAA/BBB`` yields ``PREFIX-NN-BBB`` beside its
    literal first ID.

    Args:
        text: Prose to scan, such as a decision record's body.
        known_ids: The requirement IDs a range may expand to.
    """
    found = set(SPEC_ID_CITATION_RE.findall(text))
    keyed = [(key, i) for i in known_ids if (key := _id_key(i)) is not None]
    for match in _SPEC_ID_RANGE_RE.finditer(text):
        prefix = match["prefix"]
        end_prefix = match["word_prefix"] or match["dash_prefix"] or prefix
        if end_prefix != prefix:
            continue
        end_group = (
            match["word_group"] or match["dash_group"] or match["group"]
        )
        end_index = match["word_index"] or match["dash_index"]
        low = (prefix, int(match["group"]), int(match["index"]))
        high = (prefix, int(end_group), int(end_index))
        found.update(i for key, i in keyed if low <= key <= high)
    for match in _SPEC_ID_SLASH_RE.finditer(text):
        stem, tail = match.groups()
        found.update(stem + index for index in tail.split("/")[1:])
    return found


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

#: The issue that owns verifying an unverified MUST-tier requirement
#: (MS-10-006): one GitHub reference in ``#N`` form. Quote it in YAML —
#: ``verification_debt: #12`` is a comment and loads as null.
IssueRefStr = Annotated[
    str,
    StringConstraints(pattern=r"^#[1-9]\d*$"),
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
    ``specs/notes-frontmatter.yaml`` NF-01-004). The linter also tolerates the inline MADR
    form ``superseded by <link>`` by normalising it to ``SUPERSEDED`` before
    the enum check.
    """

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACCEPTED_PROVISIONAL = "accepted-provisional"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class RelationEnd(StrEnum):
    """Which end of a relationship is the more general (upstream) requirement.

    A relationship is recorded on its *source* requirement and names its
    *target* (SR-13-012). Pointing every edge from its downstream end to its
    upstream end is what lets the requirements graph answer "what does a change
    to this requirement affect?" (SR-13-014).
    """

    TARGET = "target"
    SOURCE = "source"
    NEITHER = "neither"


class RelationType(StrEnum):
    """Relationship types between spec requirements (SR-02-004).

    The docstring's member list below is generated from
    :data:`RELATION_DEFINITIONS`, which a test checks against SR-13-001
    through SR-13-011 and SR-13-017, the one statement of what each type means.
    """

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
    USES_DEFINITION = "uses_definition"

    @property
    def definition(self) -> str:
        """What a relationship of this type asserts (SR-13-001..011, SR-13-017)."""
        return RELATION_DEFINITIONS[self][0]

    @property
    def upstream_end(self) -> RelationEnd:
        """The end that is the more general (upstream) requirement."""
        return RELATION_DEFINITIONS[self][1]


#: The meaning of each relationship type and which end is upstream. The text
#: is SR-13-001 through SR-13-011 and SR-13-017 verbatim; ``test_schema.py``
#: asserts the two agree and that every member has an entry.
RELATION_DEFINITIONS: dict[RelationType, tuple[str, RelationEnd]] = {
    RelationType.IMPLEMENTS: (
        "An `implements` relationship recorded on A naming B MUST mean that A "
        "states the concrete mechanism by which B is met; B is the more "
        "general requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.SUPERSEDES: (
        "A `supersedes` relationship recorded on A naming B MUST mean that A "
        "replaces B, wholly or in a case A names, so that where A applies B "
        "no longer binds; B is the earlier, upstream requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.EXTENDS: (
        "An `extends` relationship recorded on A naming B MUST mean that A adds "
        "obligations to B without narrowing or changing what B already "
        "requires; B is the more general requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.DEPENDS_ON: (
        "A `depends_on` relationship recorded on A naming B MUST mean that A "
        "cannot be met unless B is also met; B is the upstream requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.CONFLICTS: (
        "A `conflicts` relationship recorded on A naming B MUST mean that A and "
        "B cannot both be met as written; neither end is upstream.",
        RelationEnd.NEITHER,
    ),
    RelationType.REFINES: (
        "A `refines` relationship recorded on A naming B MUST mean that A "
        "restates B for a narrower case or with more precision, so that "
        "meeting A in that case meets B; B is the more general requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.DERIVES_FROM: (
        "A `derives_from` relationship recorded on A naming B MUST mean that A "
        "states a consequence that follows from B without being a narrower "
        "case of B; B is the upstream requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.VERIFIES: (
        "A `verifies` relationship recorded on A naming B MUST mean that A "
        "states a check that confirms B is met; B is the upstream "
        "requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.PART_OF: (
        "A `part_of` relationship recorded on A naming B MUST mean that A is "
        "one component of B, which is met only when all of its parts are met; "
        "B is the more general requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.CONSTRAINS: (
        "A `constrains` relationship recorded on A naming B MUST mean that A "
        "bounds how B may be met without B being a narrower case of A; A is "
        "the more general requirement.",
        RelationEnd.SOURCE,
    ),
    RelationType.SATISFIES: (
        "A `satisfies` relationship recorded on A naming B MUST mean that "
        "meeting A is sufficient to meet B; B is the upstream requirement.",
        RelationEnd.TARGET,
    ),
    RelationType.USES_DEFINITION: (
        "A `uses_definition` relationship recorded on A naming B MUST mean "
        "that A uses a term or notion that B defines, so that a change to "
        "what B defines changes what A requires; B is the upstream "
        "requirement.",
        RelationEnd.TARGET,
    ),
}

RelationType.__doc__ = (RelationType.__doc__ or "") + "".join(
    f"\n    ``{member.value}``: {member.definition}\n"
    for member in RelationType
)


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
    (e.g. ``"rv"``, ``"rvv"``).
    """

    model_config = ConfigDict(extra="forbid")

    type: TriggerType
    value: str


class SpecKind(StrEnum):
    """Portability tier for a spec requirement (SR-02-005, ADR-0134).

    Who must obey a rule decides its kind; naming a codebase construct never
    does (MS-12-002). A spec that mixes kinds is split before it is classified
    (MS-12-010). The five tiers:

    - ``protocol``     — The Vultron layer: Vultron's message forms on the
                         wire (including where ActivityStreams allows several
                         forms and Vultron requires one), which messages are
                         sent and when, what a receiver does given its state
                         (including on duplicate delivery), and the state
                         machines underlying those behaviors. State-machine
                         states such as ``RM.CLOSED`` are protocol constructs.
                         The CASE_MANAGER role and case-ledger sync are
                         ``protocol`` for now.
    - ``foundation``   — Rules Vultron inherits from the standards beneath it:
                         ActivityStreams 2.0, ActivityPub, HTTP. Addressing and
                         delivery, HTTP status codes, and rules that only
                         restate ActivityStreams (every ID is an IRI). A tag
                         records the standard (``as2``, ``activitypub``,
                         ``http``; MS-12-009).
    - ``architecture`` — Recommended structure that carries over to other
                         languages but is not required for compliance.
                         Behavior trees, and keeping protocol behavior inside
                         the behavior tree, are here.
    - ``project``      — This codebase only: deployment choices (the
                         CASE_MANAGER as an actor separate from the case
                         owner), performance and operating limits, how a
                         receiver records what it receives, core internals.
    - ``process``      — How we run this project — CI config, GitHub workflow,
                         agent conventions, docs standards, spec authoring
                         rules.

    Portability use cases
    ~~~~~~~~~~~~~~~~~~~~~
    - Implement Vultron in any language          → ``protocol`` + ``foundation``
    - Understand the reference architecture      → the above + ``architecture``
    - Contribute to this Python codebase         → the above + ``project``
    - Contribute to this project (incl. process) → all five tiers
    """

    PROTOCOL = "protocol"
    FOUNDATION = "foundation"
    ARCHITECTURE = "architecture"
    PROJECT = "project"
    PROCESS = "process"


class Scope(StrEnum):
    """Deployment scope for a spec requirement (SR-02-006)."""

    PROTOTYPE = "prototype"
    PRODUCTION = "production"


class SpecTag(StrEnum):
    """Controlled vocabulary of topic tags (SR-02-007).

    Three tags name the standard a ``foundation`` rule is inherited from —
    ``as2``, ``activitypub`` and ``http`` (:data:`FOUNDATION_STANDARD_TAGS`,
    MS-12-009). They may also mark a ``protocol`` rule that narrows that
    standard.
    """

    ACTIVITYPUB = "activitypub"
    AS2 = "as2"
    AUTHENTICATION = "authentication"
    BEHAVIOR_TREE = "behavior-tree"
    CI_CD = "ci-cd"
    CODE_STYLE = "code-style"
    CONFIGURATION = "configuration"
    DEMO = "demo"
    DOCUMENTATION = "documentation"
    ERROR_HANDLING = "error-handling"
    FEDERATION = "federation"
    HTTP = "http"
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


#: The kinds every Vultron implementation must obey: the kinds an implementer
#: reads (ADR-0134). The marker-coverage guard (SR-05-004, SR-05-005) and the
#: code-reference detector (MS-12-006) cover both; the story gate (SR-11-003)
#: names its own population.
IMPLEMENTER_KINDS: frozenset[SpecKind] = frozenset(
    {SpecKind.PROTOCOL, SpecKind.FOUNDATION}
)


#: The tags that name the standard a ``foundation`` rule is inherited from.
#: Every ``foundation`` spec carries at least one (MS-12-009).
FOUNDATION_STANDARD_TAGS: frozenset[SpecTag] = frozenset(
    {SpecTag.AS2, SpecTag.ACTIVITYPUB, SpecTag.HTTP}
)


class LintWarningCode(StrEnum):
    """Named linter warnings that can be suppressed via ``lint_suppress``
    (SR-02-011)."""

    TESTABLE_WITHOUT_STEPS = "testable_without_steps"
    RATIONALE_TOO_LONG = "rationale_too_long"
    MISSING_TAGS = "missing_tags"
    DANGLING_ADR_REF = "dangling_adr_ref"
    PHANTOM_PATH_REF = "phantom_path_ref"
    PHANTOM_SYMBOL_REF = "phantom_symbol_ref"
    MISSING_STORY_REFERENCE = "missing_story_reference"
    PROTOCOL_KIND_WITH_CODE_REFERENCE = "protocol_kind_with_code_reference"
    COMPOUND_STATEMENT = "compound_statement"


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
