"""Tests for the occasions declared on ``SEMANTIC_REGISTRY`` entries (ADR-0128).

Covers construction-time validation of ``Occasion``, its three distinguisher
shapes and ``SemanticEntry`` (MSM-08-001, MSM-08-002, MSM-08-011), and the
registry-wide
facts every declared occasion must satisfy: each entry outside the dispatcher
fallbacks has at least one, anchors are unique, how-to links resolve, and each
occasion's example dispatches to its own entry carrying its distinguishing
field value (MSM-08-003).
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    SenderEntitlementKind,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import PxaDimension
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.metadata.markdown_tables import iter_tables
from vultron.semantic_registry import (
    SEMANTIC_REGISTRY,
    find_matching_semantics,
)
from vultron.semantic_registry._entry import (
    DISPATCHER_FALLBACKS,
    SemanticEntry,
)
from vultron.semantic_registry._occasion import (
    FieldValue,
    MessagePage,
    Occasion,
    ProtocolShorthand,
    SenderStanding,
    StateContext,
    wire_spelling,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.examples import vocab_examples

_DOCS = Path(__file__).parents[1] / "docs"


def _occasion(**overrides: Any) -> Occasion:
    fields: dict[str, Any] = {
        "when": "a stub situation arises",
        "anchor": "stub-situation",
        "addressee": AddresseeSide.CASE_MANAGER,
        "heading": "Stub situation",
        "description": "Stands in for a real occasion.",
        "example": "stub_example",
    }
    fields.update(overrides)
    return Occasion(**fields)


class _StubEvent(VultronEvent):
    """Minimal event class for construction tests."""


class _StubUseCase:
    """Minimal use case class for construction tests."""


def _entry(
    semantics: MessageSemantics = MessageSemantics.ADD_NOTE_TO_CASE,
    **overrides: Any,
) -> SemanticEntry:
    fields: dict[str, Any] = {
        "semantics": semantics,
        "pattern": None,
        "event_class": _StubEvent,
        "use_case_class": _StubUseCase,
        "phrase": "{actor} did a thing",
        "occasions": (_occasion(),),
        "page": MessagePage.GENERAL,
    }
    fields.update(overrides)
    return SemanticEntry(**fields)


# ---------------------------------------------------------------------------
# Occasion construction (MSM-08-001, MSM-08-005).
# ---------------------------------------------------------------------------


def test_occasion_is_frozen():
    occasion = _occasion()
    with pytest.raises(ValidationError, match="frozen"):
        occasion.when = "something else"  # type: ignore[misc]


@pytest.mark.spec("MSM-08-001")
@pytest.mark.parametrize("field_name", ["when", "description"])
def test_occasion_rejects_empty_required_prose(field_name: str):
    with pytest.raises(ValueError, match=field_name):
        _occasion(**{field_name: "  "})


@pytest.mark.parametrize("field_name", ["howto", "notes"])
def test_occasion_rejects_present_but_empty_optional_prose(field_name: str):
    """``howto`` is a ``HowToGuide``, so an empty string is no guide at all."""
    with pytest.raises(ValueError, match=field_name):
        _occasion(**{field_name: ""})


@pytest.mark.spec("MSM-08-001")
@pytest.mark.parametrize(
    "anchor", ["", "Fix-Ready", "fix_ready", "fix ready", "-fix", "fix-"]
)
def test_occasion_rejects_malformed_anchor(anchor: str):
    with pytest.raises(ValueError, match="anchor"):
        _occasion(anchor=anchor)


@pytest.mark.spec("MSM-08-001")
@pytest.mark.parametrize(
    "example", ["", "vocab_examples.add_note_to_case", "1st"]
)
def test_occasion_rejects_example_that_is_not_a_function_name(example: str):
    with pytest.raises(ValueError, match="example"):
        _occasion(example=example)


@pytest.mark.spec("MSM-08-005")
def test_occasion_rejects_usual_sender_that_is_not_a_cvd_role():
    with pytest.raises(ValidationError, match="usual_senders"):
        _occasion(usual_senders=("vendor",))


@pytest.mark.spec("MSM-08-005")
def test_occasion_accepts_cvd_role_usual_senders():
    occasion = _occasion(usual_senders=(CVDRole.VENDOR, CVDRole.DEPLOYER))
    assert occasion.usual_senders == (CVDRole.VENDOR, CVDRole.DEPLOYER)


@pytest.mark.spec("MSM-08-008")
def test_occasion_without_shorthand_needs_a_heading():
    with pytest.raises(ValidationError, match="heading"):
        _occasion(heading=None)


@pytest.mark.spec("MSM-08-008")
def test_occasion_with_a_shorthand_may_omit_the_heading():
    occasion = _occasion(heading=None, shorthand=ProtocolShorthand.CF)
    assert occasion.heading is None


def test_occasion_rejects_empty_heading():
    with pytest.raises(ValidationError, match="heading"):
        _occasion(heading="")


def _formal_message_names() -> dict[str, str]:
    """Read ``{code: name}`` from the formal message set's type tables."""
    text = (_DOCS / "reference/formal_protocol/messages.md").read_text(
        encoding="utf-8"
    )
    names: dict[str, str] = {}
    for table in iter_tables(text):
        if table.columns[:2] != ("Message Type", "Name"):
            continue
        for row in table.rows:
            names[row[0].strip("$")] = row[1]
    return names


@pytest.mark.spec("MSM-08-008")
def test_formal_names_match_the_formal_message_set():
    documented = _formal_message_names()
    declared = {s.value: s.formal_name for s in ProtocolShorthand}
    assert declared == documented


@pytest.mark.spec("MSM-08-006")
def test_evolved_occasion_carries_no_shorthand():
    with pytest.raises(ValueError, match="evolved"):
        _occasion(evolved=True, shorthand=ProtocolShorthand.RE)


# ---------------------------------------------------------------------------
# Distinguishers (MSM-08-002).
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-08-002")
@pytest.mark.parametrize(
    ("object_type", "field_name", "value"),
    [
        (ParticipantStatus, "vf", CS_vf.VF),
        (ParticipantStatus, "d", CS_d.D),
        (ParticipantStatus, "rm", RM.ACCEPTED),
        (CaseStatus, "pxa", CS_pxa.PXa),
        (CaseStatus, "em", EM.ACTIVE),
    ],
)
def test_field_value_accepts_a_member_of_the_field_enum(
    object_type: type, field_name: str, value: Any
):
    distinguisher = FieldValue(
        object_type=object_type, field=field_name, value=value
    )
    assert distinguisher.value is value


@pytest.mark.spec("MSM-08-002")
def test_field_value_reads_a_dimension_field_as_its_state():
    """A dimension field travels as its bare state (ARCH-25-005, ADR-0099)."""
    distinguisher = FieldValue(
        object_type=CaseStatus, field="pxa", value=CS_pxa.PXa
    )
    status = CaseStatus(
        context="urn:uuid:case", pxa=PxaDimension(state=CS_pxa.PXa)
    )
    assert distinguisher.read(status) is CS_pxa.PXa


@pytest.mark.spec("MSM-08-002")
def test_field_value_accepts_a_member_of_an_embedded_field_enum():
    """A participant's view of the public state is the ``pxa`` of the case
    status its participant status embeds (#4569)."""
    distinguisher = FieldValue(
        object_type=ParticipantStatus,
        within="case_status",
        field="pxa",
        value=CS_pxa.Pxa,
    )
    assert distinguisher.declaring_type is CaseStatus
    assert distinguisher.path == "case_status.pxa"


@pytest.mark.spec("MSM-08-002")
def test_field_value_reads_a_field_within_an_embedded_model():
    distinguisher = FieldValue(
        object_type=ParticipantStatus,
        within="case_status",
        field="pxa",
        value=CS_pxa.Pxa,
    )
    status = ParticipantStatus(
        context="urn:uuid:participant",
        case_status=CaseStatus(
            context="urn:uuid:case", pxa=PxaDimension(state=CS_pxa.Pxa)
        ),
    )
    assert distinguisher.read(status) is CS_pxa.Pxa


@pytest.mark.spec("MSM-08-002")
def test_field_value_reads_nothing_when_the_model_is_not_embedded():
    distinguisher = FieldValue(
        object_type=ParticipantStatus,
        within="case_status",
        field="pxa",
        value=CS_pxa.Pxa,
    )
    status = ParticipantStatus(context="urn:uuid:participant")
    assert status.case_status is None
    assert distinguisher.read(status) is None


@pytest.mark.spec("MSM-08-002")
def test_field_value_rejects_a_value_of_another_embedded_field_enum():
    with pytest.raises(
        ValueError, match=r"ParticipantStatus\.case_status\.pxa"
    ):
        FieldValue(
            object_type=ParticipantStatus,
            within="case_status",
            field="pxa",
            value=CS_vf.VF,
        )


@pytest.mark.spec("MSM-08-002")
@pytest.mark.parametrize(
    ("within", "match"),
    [
        ("fix_state", "no typed field"),
        ("vf", "does not embed exactly one model"),
        ("case_engagement", "does not embed exactly one model"),
    ],
)
def test_field_value_rejects_a_within_that_embeds_no_model(
    within: str, match: str
):
    with pytest.raises(ValueError, match=match):
        FieldValue(
            object_type=ParticipantStatus,
            within=within,
            field="pxa",
            value=CS_pxa.Pxa,
        )


class _StatusOrIri(BaseModel):
    """A carrier whose field holds an embedded model *or* an IRI string."""

    status: CaseStatus | str | None = None


@pytest.mark.spec("MSM-08-002")
def test_field_value_rejects_a_within_that_may_hold_a_non_model():
    """Only ``| None`` may accompany the embedded model: an IRI member
    would leave read() nothing to look the field up on."""
    with pytest.raises(ValueError, match="does not embed exactly one model"):
        FieldValue(
            object_type=_StatusOrIri,
            within="status",
            field="pxa",
            value=CS_pxa.Pxa,
        )


@pytest.mark.spec("MSM-08-002")
def test_field_value_rejects_a_field_the_embedded_model_does_not_declare():
    with pytest.raises(ValueError, match="CaseStatus has no typed field 'vf'"):
        FieldValue(
            object_type=ParticipantStatus,
            within="case_status",
            field="vf",
            value=CS_vf.VF,
        )


@pytest.mark.spec("MSM-08-002")
def test_field_value_rejects_an_embedded_field_no_enum_types():
    with pytest.raises(
        ValueError,
        match=r"ParticipantStatus\.case_status\.context is not typed by an enum",
    ):
        FieldValue(
            object_type=ParticipantStatus,
            within="case_status",
            field="context",
            value=CS_pxa.Pxa,
        )


def test_wire_spelling_names_an_embedded_field_by_its_dotted_path():
    assert (
        wire_spelling(ParticipantStatus, "pxa", "case_status")
        == "caseStatus.pxaState"
    )


@pytest.mark.parametrize(
    ("object_type", "field_name", "spelling"),
    [
        (CaseStatus, "pxa", "pxaState"),
        (CaseStatus, "em", "emState"),
        (ParticipantStatus, "vf", "vfState"),
        (ParticipantStatus, "d", "dState"),
        (ParticipantStatus, "rm", "rmState"),
    ],
)
def test_wire_spelling_names_a_field_by_its_as2_spelling(
    object_type: type, field_name: str, spelling: str
):
    assert wire_spelling(object_type, field_name) == spelling


@pytest.mark.spec("MSM-08-002")
def test_field_value_rejects_a_value_of_another_enum():
    with pytest.raises(ValueError, match="not a member of CS_vf"):
        FieldValue(object_type=ParticipantStatus, field="vf", value=CS_d.D)


@pytest.mark.spec("MSM-08-002")
def test_field_value_rejects_an_unknown_field():
    with pytest.raises(ValueError, match="no typed field"):
        FieldValue(
            object_type=ParticipantStatus, field="fix_state", value=CS_vf.VF
        )


@pytest.mark.spec("MSM-08-002")
def test_field_value_rejects_a_field_not_typed_by_an_enum():
    with pytest.raises(ValueError, match="not typed by an enum"):
        FieldValue(
            object_type=ParticipantStatus,
            field="case_engagement",
            value=CS_vf.VF,
        )


@pytest.mark.spec("MSM-08-002")
def test_state_context_accepts_states_of_its_machine():
    context = StateContext(machine=EM, states=(EM.ACTIVE, EM.REVISE))
    assert context.states == (EM.ACTIVE, EM.REVISE)


@pytest.mark.spec("MSM-08-002")
def test_state_context_rejects_a_state_outside_its_machine():
    with pytest.raises(ValueError, match="not members of EM"):
        StateContext(machine=EM, states=(EM.ACTIVE, RM.ACCEPTED))


@pytest.mark.spec("MSM-08-002")
def test_state_context_rejects_no_states():
    with pytest.raises(ValidationError, match="states"):
        StateContext(machine=EM, states=())


@pytest.mark.spec("MSM-08-002")
def test_state_context_rejects_a_machine_that_is_not_an_enum():
    with pytest.raises(ValidationError, match="machine"):
        StateContext(machine=str, states=(EM.ACTIVE,))  # type: ignore[arg-type]


@pytest.mark.spec("MSM-08-002")
def test_sender_standing_accepts_an_entitlement_kind():
    standing = SenderStanding(
        kind=SenderEntitlementKind.CASE_OWNER, holds=False
    )
    assert standing.kind is SenderEntitlementKind.CASE_OWNER
    assert standing.holds is False


@pytest.mark.spec("MSM-08-002")
@pytest.mark.parametrize(
    "kind",
    [CVDRole.CASE_OWNER, "CASE_OWNER", SenderEntitlementKind.CASE_OWNER.value],
    ids=["cvd-role", "name", "value"],
)
def test_sender_standing_rejects_a_kind_that_is_not_an_entitlement_kind(
    kind: object,
):
    with pytest.raises(ValidationError, match="kind"):
        SenderStanding(kind=kind, holds=True)  # type: ignore[arg-type]


@pytest.mark.spec("MSM-08-002")
def test_sender_standing_rejects_a_kind_that_requires_no_standing():
    with pytest.raises(ValueError, match="ANY_ACTOR requires no standing"):
        SenderStanding(kind=SenderEntitlementKind.ANY_ACTOR, holds=True)


@pytest.mark.spec("MSM-08-002")
def test_sender_standing_rejects_a_holds_that_is_not_a_bool():
    with pytest.raises(ValidationError, match="holds"):
        SenderStanding(
            kind=SenderEntitlementKind.CASE_OWNER,
            holds=1,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# SemanticEntry construction (MSM-08-001, MSM-06-002).
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-08-001")
def test_entry_without_occasion_fails_at_construction():
    with pytest.raises(ValueError, match="declares no occasion"):
        _entry(occasions=())


@pytest.mark.spec("MSM-06-002")
def test_entry_without_page_fails_at_construction():
    with pytest.raises(ValueError, match="names no message page"):
        _entry(page=None)


def test_entry_occasions_must_be_a_tuple():
    with pytest.raises(TypeError, match="tuple"):
        _entry(occasions=[_occasion()])


def test_entry_page_must_be_a_message_page():
    with pytest.raises(TypeError, match="MessagePage"):
        _entry(page="general")


@pytest.mark.spec("MSM-08-001")
@pytest.mark.parametrize("semantics", sorted(DISPATCHER_FALLBACKS))
def test_dispatcher_fallback_needs_no_occasion(semantics: MessageSemantics):
    entry = _entry(semantics, occasions=(), page=None)
    assert entry.occasions == ()


@pytest.mark.spec("MSM-06-002")
@pytest.mark.parametrize(
    "overrides",
    [
        {"page": None},
        {"occasions": ()},
    ],
    ids=["occasion", "page"],
)
def test_dispatcher_fallback_declares_neither_occasion_nor_page(
    overrides: dict[str, Any],
):
    with pytest.raises(ValueError, match="dispatcher fallback"):
        _entry(MessageSemantics.UNKNOWN, **overrides)


# ---------------------------------------------------------------------------
# Same-addressee siblings (MSM-08-011).
# ---------------------------------------------------------------------------


def _siblings(
    first: object, second: object, **second_overrides: Any
) -> tuple[Occasion, Occasion]:
    """Two occasions on one addressee, with the given distinguishers."""
    return (
        _occasion(anchor="first-situation", distinguisher=first),
        _occasion(
            anchor="second-situation", distinguisher=second, **second_overrides
        ),
    )


def _owner(holds: bool) -> SenderStanding:
    return SenderStanding(kind=SenderEntitlementKind.CASE_OWNER, holds=holds)


def _register(*states: EmbargoRegisterStatus) -> StateContext:
    return StateContext(machine=EmbargoRegisterStatus, states=states)


def _vf(value: CS_vf) -> FieldValue:
    return FieldValue(object_type=ParticipantStatus, field="vf", value=value)


@pytest.mark.spec("MSM-08-011")
@pytest.mark.parametrize(
    ("first", "second", "undistinguished"),
    [
        (None, _owner(True), "'first-situation'"),
        (_owner(True), None, "'second-situation'"),
        (None, None, "'first-situation'"),
    ],
    ids=["first", "second", "both"],
)
def test_entry_refuses_a_same_addressee_occasion_without_a_distinguisher(
    first: object, second: object, undistinguished: str
):
    with pytest.raises(
        ValueError,
        match=f"occasion {undistinguished} shares the addressee CASE_MANAGER"
        " with another and declares no distinguisher",
    ):
        _entry(occasions=_siblings(first, second))


@pytest.mark.spec("MSM-08-011")
def test_entry_reports_every_undistinguished_sibling():
    with pytest.raises(ValueError) as caught:
        _entry(occasions=_siblings(None, None))
    assert "'first-situation'" in str(caught.value)
    assert "'second-situation'" in str(caught.value)
    assert "MSM-08-011" in str(caught.value)


@pytest.mark.spec("MSM-08-011")
@pytest.mark.parametrize(
    ("first", "second"),
    [
        (_owner(True), _owner(True)),
        (_register(EmbargoRegisterStatus.ACTIVE),) * 2,
        (_vf(CS_vf.VF), _vf(CS_vf.VF)),
        (
            StateContext(machine=EM, states=(EM.NONE, EM.PROPOSED)),
            StateContext(machine=EM, states=(EM.PROPOSED,)),
        ),
    ],
    ids=[
        "equal-standings",
        "equal-contexts",
        "equal-field-values",
        "contexts-sharing-a-state",
    ],
)
def test_entry_refuses_same_addressee_siblings_whose_distinguishers_overlap(
    first: object, second: object
):
    with pytest.raises(
        ValueError,
        match="'first-situation' and 'second-situation' share the addressee"
        " CASE_MANAGER and their distinguishers overlap",
    ):
        _entry(occasions=_siblings(first, second))


@pytest.mark.spec("MSM-08-011")
@pytest.mark.parametrize(
    ("first", "second"),
    [
        (_owner(True), _owner(False)),
        (
            _register(EmbargoRegisterStatus.ACTIVE),
            _register(EmbargoRegisterStatus.TERMINATED),
        ),
        (_vf(CS_vf.Vf), _vf(CS_vf.VF)),
        # Different fields, machines or kinds are not compared: one
        # activity may carry both values by design.
        (
            _vf(CS_vf.VF),
            FieldValue(object_type=ParticipantStatus, field="d", value=CS_d.D),
        ),
        (
            StateContext(machine=EM, states=(EM.ACTIVE,)),
            _register(EmbargoRegisterStatus.ACTIVE),
        ),
        (
            _owner(True),
            SenderStanding(
                kind=SenderEntitlementKind.CASE_MANAGER, holds=True
            ),
        ),
        (_owner(True), _register(EmbargoRegisterStatus.ACTIVE)),
    ],
    ids=[
        "standings-held-and-not",
        "disjoint-contexts",
        "different-values",
        "different-fields",
        "different-machines",
        "different-kinds",
        "different-distinguisher-kinds",
    ],
)
def test_entry_accepts_same_addressee_siblings_that_differ(
    first: object, second: object
):
    entry = _entry(occasions=_siblings(first, second))
    assert len(entry.occasions) == 2


@pytest.mark.spec("MSM-08-011")
def test_entry_does_not_compare_occasions_with_different_addressees():
    entry = _entry(
        occasions=_siblings(None, None, addressee=AddresseeSide.PARTICIPANT)
    )
    assert len(entry.occasions) == 2


@pytest.mark.spec("MSM-08-011")
def test_registry_same_addressee_siblings_are_distinguished():
    """The four occasions #4821 found undistinguished now declare one."""
    declared = {
        o.anchor: o.distinguisher
        for e in SEMANTIC_REGISTRY
        for o in e.occasions
    }
    assert declared["request-invite-actor-to-case"] == _owner(True)
    assert declared["suggest-actor-to-case"] == _owner(False)
    assert declared["announce-embargo"] == _register(
        EmbargoRegisterStatus.ACTIVE
    )
    assert declared["announce-embargo-termination"] == _register(
        EmbargoRegisterStatus.TERMINATED
    )


# ---------------------------------------------------------------------------
# The declared registry.
# ---------------------------------------------------------------------------

_OCCASIONS: list[tuple[SemanticEntry, Occasion]] = [
    (entry, occasion)
    for entry in SEMANTIC_REGISTRY
    for occasion in entry.occasions
]


def _occasion_id(item: tuple[SemanticEntry, Occasion]) -> str:
    return item[1].anchor


@pytest.mark.spec("MSM-08-001")
def test_every_non_fallback_entry_declares_an_occasion():
    missing = [
        e.semantics.name
        for e in SEMANTIC_REGISTRY
        if e.semantics not in DISPATCHER_FALLBACKS and not e.occasions
    ]
    assert missing == []


@pytest.mark.spec("MSM-08-001")
def test_occasions_were_collected():
    """A parametrized gate over no occasions would pass vacuously."""
    non_fallback = [
        e for e in SEMANTIC_REGISTRY if e.semantics not in DISPATCHER_FALLBACKS
    ]
    assert len(_OCCASIONS) >= len(non_fallback) > 40


@pytest.mark.spec("MSM-08-004")
def test_occasion_anchors_are_unique_across_the_registry():
    """The uniqueness half of MSM-08-004.

    That each anchor resolves to one section on its page, and that each
    section is referenced by a table row, is tested over the pages in
    ``test/metadata/test_msm_occasions.py``.
    """
    counts = Counter(occasion.anchor for _, occasion in _OCCASIONS)
    assert [a for a, n in counts.items() if n > 1] == []


@pytest.mark.spec("MSM-08-003")
@pytest.mark.parametrize("item", _OCCASIONS, ids=_occasion_id)
def test_occasion_example_dispatches_to_its_own_entry(
    item: tuple[SemanticEntry, Occasion],
):
    """Each example routes to its occasion's entry, and carries its value.

    A state context is the receiver's state, not payload, so only a
    field-value distinguisher is checked in the example.
    """
    entry, occasion = item
    build = getattr(vocab_examples, occasion.example, None)
    assert callable(build), (
        f"{occasion.anchor}: vocab_examples has no function"
        f" {occasion.example!r}"
    )
    activity = build()
    assert isinstance(activity, as_Activity)
    assert find_matching_semantics(activity) is entry.semantics
    matching = [
        other.semantics
        for other in SEMANTIC_REGISTRY
        if other.semantics not in DISPATCHER_FALLBACKS
        and other.pattern is not None
        and other.pattern.match(activity)
    ]
    assert matching == [entry.semantics], (
        f"{occasion.example}() matches {matching}, not only"
        f" {entry.semantics.name} (MSM-08-003)"
    )
    distinguisher = occasion.distinguisher
    if isinstance(distinguisher, FieldValue):
        carrier = getattr(activity, "object_", None)
        assert isinstance(carrier, distinguisher.object_type)
        assert distinguisher.read(carrier) == distinguisher.value


@pytest.mark.spec("MSM-08-003")
def test_collapsed_occasions_do_not_share_an_example():
    """An entry's occasions each render their own example (MSM-08-003)."""
    shared = [
        e.semantics.name
        for e in SEMANTIC_REGISTRY
        if len({o.example for o in e.occasions}) != len(e.occasions)
    ]
    assert shared == []


@pytest.mark.parametrize(
    "item",
    [item for item in _OCCASIONS if item[1].howto is not None],
    ids=_occasion_id,
)
def test_occasion_howto_link_resolves(item: tuple[SemanticEntry, Occasion]):
    howto = item[1].howto
    assert howto is not None
    assert (_DOCS / howto).is_file(), f"docs/{howto} does not exist"


@pytest.mark.spec("MSM-08-001")
def test_notify_published_form_is_a_declared_occasion():
    """The demo's notify-published report (CSB-15-003) has its own row: an
    ``Add(ParticipantStatus)`` whose embedded case status is at ``Pxa``
    (#4569)."""
    entry = next(
        e
        for e in SEMANTIC_REGISTRY
        if e.semantics
        is MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    )
    declared = {
        (o.shorthand, o.distinguisher.within, o.distinguisher.value)
        for o in entry.occasions
        if isinstance(o.distinguisher, FieldValue)
    }
    assert (ProtocolShorthand.CP, "case_status", CS_pxa.Pxa) in declared
