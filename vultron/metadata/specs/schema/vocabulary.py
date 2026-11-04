"""Controlled vocabularies for the spec schema: priorities, statuses, relation
types, kinds, scopes, tags and lint codes.
"""

from __future__ import annotations

from enum import StrEnum


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
                         ``http``; MS-12-018).
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
    MS-12-018). They may also mark a ``protocol`` rule that narrows that
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
#: Every ``foundation`` spec carries at least one (MS-12-018).
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
    NO_PROJECT_PROCESS_STORY = "no_project_process_story"
