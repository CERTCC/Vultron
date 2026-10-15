"""Tests for the occasions declared on ``SEMANTIC_REGISTRY`` entries (ADR-0128).

Covers construction-time validation of ``Occasion``, its two distinguisher
shapes and ``SemanticEntry`` (MSM-08-001, MSM-08-002), and the registry-wide
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
from pydantic import ValidationError

from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import PxaDimension
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
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
    semantics: MessageSemantics = MessageSemantics.CREATE_NOTE,
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
@pytest.mark.parametrize("example", ["", "vocab_examples.create_note", "1st"])
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
        (ParticipantStatus, "vf_state", CS_vf.VF),
        (ParticipantStatus, "d_state", CS_d.D),
        (ParticipantStatus, "rm_state", RM.ACCEPTED),
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


@pytest.mark.parametrize(
    ("object_type", "field_name", "spelling"),
    [
        (CaseStatus, "pxa", "pxaState"),
        (CaseStatus, "em", "emState"),
        (ParticipantStatus, "vf_state", "vfState"),
    ],
)
def test_wire_spelling_names_a_field_by_its_as2_spelling(
    object_type: type, field_name: str, spelling: str
):
    assert wire_spelling(object_type, field_name) == spelling


@pytest.mark.spec("MSM-08-002")
def test_field_value_rejects_a_value_of_another_enum():
    with pytest.raises(ValueError, match="not a member of CS_vf"):
        FieldValue(
            object_type=ParticipantStatus, field="vf_state", value=CS_d.D
        )


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
