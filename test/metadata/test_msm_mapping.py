"""Tests for the MSM facts derived from occasions (MSM-08-005, MSM-08-006).

The mapping status and the "Sent by" value are computed, never declared: a
declared status is a second copy of what the shorthands already say, and the
two disagreed for ``EP`` (MSM-08-006 rationale).
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

import dataclasses
import re
from pathlib import Path
from typing import Any, ClassVar

import pytest

from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    SenderEntitlement,
    SenderEntitlementKind,
    SenderExemption,
    SenderRule,
    any_of,
    exempt,
    no_sender_check,
)
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.enums.roles import CVDRole
from vultron.metadata.msm._mapping import (
    NO_SENDER_CHECK,
    NOT_YET_CHECKED,
    ROW_SPECS,
    MappingStatus,
    answered_request,
    mapping_status,
    send_to,
    sent_by,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY, lookup_entry
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    MessagePage,
    Occasion,
    ProtocolShorthand,
)
from vultron.wire.as2.enums import (
    as_ObjectType,
    as_TransitiveActivityType as TAtype,
)
from vultron.wire.as2.extractor import ActivityPattern


class _StubEvent(VultronEvent):
    """Minimal event class for derivation tests."""


def _use_case(entitlement: SenderEntitlement | None) -> type:
    """A use-case class declaring *entitlement* (or nothing, when ``None``)."""

    class _UseCase:
        if entitlement is not None:
            sender_entitlement: ClassVar[SenderEntitlement] = entitlement

    return _UseCase


_CASE_OWNER_RULE = SenderRule.in_case(SenderEntitlementKind.CASE_OWNER)


def _occasion(index: int = 0, **overrides: Any) -> Occasion:
    fields: dict[str, Any] = {
        "when": f"stub situation {index} arises",
        "anchor": f"stub-{index}",
        "addressee": AddresseeSide.CASE_MANAGER,
        "heading": f"Stub situation {index}",
        "description": "Stands in for a real occasion.",
        "example": f"stub_example_{index}",
    }
    fields.update(overrides)
    return Occasion(**fields)


def _entry(
    *occasions: Occasion,
    semantics: MessageSemantics = MessageSemantics.ADD_NOTE_TO_CASE,
    entitlement: SenderEntitlement | None = _CASE_OWNER_RULE,
    pattern: ActivityPattern | None = None,
    answers: tuple[VOtype | ActivityPattern, ...] = (),
) -> SemanticEntry:
    return SemanticEntry(
        semantics=semantics,
        pattern=pattern,
        event_class=_StubEvent,
        use_case_class=_use_case(entitlement),
        phrase="{actor} did a thing",
        occasions=occasions or (_occasion(),),
        page=MessagePage.GENERAL,
        answers=answers,
    )


# ---------------------------------------------------------------------------
# Mapping status (MSM-08-006).
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-08-006")
def test_one_shorthand_on_one_entry_is_direct():
    entry = _entry(_occasion(shorthand=ProtocolShorthand.RS))
    assert mapping_status(entry, [entry]) is MappingStatus.DIRECT


@pytest.mark.spec("MSM-08-006")
def test_several_distinct_shorthands_on_one_entry_is_a_collapse():
    entry = _entry(
        _occasion(0, shorthand=ProtocolShorthand.CV),
        _occasion(1, shorthand=ProtocolShorthand.CF),
    )
    assert mapping_status(entry, [entry]) is MappingStatus.COLLAPSE


@pytest.mark.spec("MSM-08-006")
def test_one_shorthand_across_several_entries_is_an_expansion():
    first = _entry(_occasion(0, shorthand=ProtocolShorthand.GI))
    second = _entry(
        _occasion(1, shorthand=ProtocolShorthand.GI),
        semantics=MessageSemantics.ADD_NOTE_TO_CASE,
    )
    registry = [first, second]
    assert mapping_status(first, registry) is MappingStatus.EXPANSION
    assert mapping_status(second, registry) is MappingStatus.EXPANSION


@pytest.mark.spec("MSM-08-006")
def test_no_shorthand_is_none():
    entry = _entry(_occasion())
    assert mapping_status(entry, [entry]) is MappingStatus.NONE


@pytest.mark.spec("MSM-08-006")
def test_a_declared_evolved_mechanism_is_evolved():
    entry = _entry(_occasion(evolved=True))
    assert mapping_status(entry, [entry]) is MappingStatus.EVOLVED


@pytest.mark.spec("MSM-08-006")
def test_occasions_sharing_one_shorthand_on_one_entry_are_direct():
    """Two situations conveyed by one shorthand do not make a collapse."""
    entry = _entry(
        _occasion(0, shorthand=ProtocolShorthand.RA),
        _occasion(1, shorthand=ProtocolShorthand.RA),
    )
    assert mapping_status(entry, [entry]) is MappingStatus.DIRECT


@pytest.mark.spec("MSM-08-006")
@pytest.mark.parametrize(
    ("semantics", "expected"),
    [
        (MessageSemantics.SUBMIT_REPORT, MappingStatus.DIRECT),
        (MessageSemantics.INVITE_TO_EMBARGO_ON_CASE, MappingStatus.COLLAPSE),
        (MessageSemantics.ADD_CASE_STATUS_TO_CASE, MappingStatus.COLLAPSE),
        (
            MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
            MappingStatus.COLLAPSE,
        ),
        (MessageSemantics.ADD_NOTE_TO_CASE, MappingStatus.EXPANSION),
        (MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE, MappingStatus.NONE),
        (MessageSemantics.CREATE_PROCESSING_FAULT, MappingStatus.EVOLVED),
        (MessageSemantics.REJECT_CASE_LEDGER_ENTRY, MappingStatus.EVOLVED),
    ],
)
def test_registry_statuses_derive_as_documented(
    semantics: MessageSemantics, expected: MappingStatus
):
    entry = lookup_entry(semantics)
    assert mapping_status(entry, SEMANTIC_REGISTRY) is expected


@pytest.mark.spec("MSM-02-001")
def test_ep_is_carried_only_by_the_embargo_invite():
    carriers = [row.semantics for row in ROW_SPECS if "EP" in row.shorthands]
    assert carriers == [MessageSemantics.INVITE_TO_EMBARGO_ON_CASE]


# ---------------------------------------------------------------------------
# "Sent by" (MSM-08-005).
# ---------------------------------------------------------------------------


_GLOSSARY = Path(__file__).parents[2] / "docs" / "reference" / "glossary.md"


def _glossary_terms() -> set[str]:
    """The bold terms that open a row of a glossary table."""
    text = _GLOSSARY.read_text(encoding="utf-8")
    return set(re.findall(r"^\| \*\*(.+?)\*\* \|", text, flags=re.M))


@pytest.mark.spec("MSM-08-010")
@pytest.mark.parametrize("kind", list(SenderEntitlementKind), ids=str)
def test_every_kind_declares_wording_and_a_glossary_term(
    kind: SenderEntitlementKind,
):
    assert kind.sent_by.strip()
    assert kind.term in _glossary_terms()


@pytest.mark.spec("MSM-08-009")
@pytest.mark.parametrize("side", list(AddresseeSide), ids=str)
def test_every_addressee_side_declares_wording_and_a_glossary_term(
    side: AddresseeSide,
):
    assert side.send_to.strip()
    assert side.term in _glossary_terms()


@pytest.mark.spec("MSM-08-010")
def test_only_positions_name_the_object_they_are_held_over():
    """A role is worded alone; a position names its request or object."""
    named = {k for k in SenderEntitlementKind if "{object}" in k.sent_by}
    assert named == {
        SenderEntitlementKind.NAMED_ACTOR,
        SenderEntitlementKind.AUTHOR,
    }


@pytest.mark.spec("MSM-08-005")
@pytest.mark.spec("MSM-08-010")
@pytest.mark.parametrize(
    ("kind", "wording"),
    [
        (SenderEntitlementKind.CASE_MANAGER, "the case manager"),
        (SenderEntitlementKind.CASE_OWNER, "the case owner"),
        (SenderEntitlementKind.ACTIVE_PARTICIPANT, "an active participant"),
        (SenderEntitlementKind.PARTICIPANT, "a participant"),
        (
            SenderEntitlementKind.LEDGER_PEER,
            "an active participant, including one that has left the case",
        ),
        (SenderEntitlementKind.INVITEE, "the invitee"),
        (SenderEntitlementKind.ANY_ACTOR, "any actor"),
    ],
)
def test_sent_by_words_each_kind(kind: SenderEntitlementKind, wording: str):
    entry = _entry(entitlement=SenderRule.in_case(kind))
    assert sent_by(entry, entry.occasions[0]) == wording


@pytest.mark.spec("MSM-08-005")
def test_sent_by_states_an_exemption_as_not_yet_checked():
    entry = _entry(entitlement=exempt("#0000", "stub"))
    assert sent_by(entry, entry.occasions[0]) == "not yet checked"


def test_an_exemption_naming_no_issue_must_say_why():
    with pytest.raises(ValueError, match="HP-01-007"):
        no_sender_check("  ")


@pytest.mark.spec("MSM-08-010")
def test_sent_by_names_each_request_the_pattern_does_not_nest():
    """A bootstrap ``Create(VulnerabilityCase)`` answers either request that
    asked for the case: a case proposal or a report offer."""
    pattern = ActivityPattern(
        activity_=TAtype.CREATE, object_=VOtype.VULNERABILITY_CASE
    )
    entry = _entry(
        entitlement=SenderRule.in_case(SenderEntitlementKind.NAMED_ACTOR),
        pattern=pattern,
        answers=(
            VOtype.CASE_PROPOSAL,
            ActivityPattern(
                activity_=TAtype.OFFER, object_=VOtype.VULNERABILITY_REPORT
            ),
        ),
    )
    assert sent_by(entry, entry.occasions[0]) == (
        "the addressee of the case proposal or vulnerability report offer"
    )


@pytest.mark.spec("MSM-08-010")
def test_sent_by_words_the_addressee_from_the_answered_request():
    pattern = ActivityPattern(
        activity_=TAtype.ACCEPT, object_=VOtype.CASE_PROPOSAL
    )
    entry = _entry(
        entitlement=SenderRule.in_case(SenderEntitlementKind.NAMED_ACTOR),
        pattern=pattern,
    )
    assert (
        sent_by(entry, entry.occasions[0])
        == "the addressee of the case proposal"
    )


@pytest.mark.spec("MSM-08-005")
@pytest.mark.spec("MSM-08-010")
def test_sent_by_words_the_author_from_the_changed_object():
    pattern = ActivityPattern(
        activity_=TAtype.REMOVE, object_=as_ObjectType.NOTE
    )
    entry = _entry(
        entitlement=SenderRule.in_case(
            SenderEntitlementKind.AUTHOR, SenderEntitlementKind.CASE_OWNER
        ),
        pattern=pattern,
    )
    assert (
        sent_by(entry, entry.occasions[0])
        == "the case owner or the note's author"
    )


@pytest.mark.spec("MSM-08-010")
def test_sent_by_reads_the_inner_object_of_a_nested_request():
    inner = ActivityPattern(
        activity_=TAtype.OFFER, object_=VOtype.VULNERABILITY_CASE
    )
    pattern = ActivityPattern(activity_=TAtype.ACCEPT, object_=inner)
    entry = _entry(
        entitlement=SenderRule.in_case(SenderEntitlementKind.NAMED_ACTOR),
        pattern=pattern,
    )
    assert (
        sent_by(entry, entry.occasions[0])
        == "the addressee of the vulnerability case offer"
    )


@pytest.mark.spec("MSM-08-005")
def test_sent_by_adds_the_usual_senders():
    occasion = _occasion(usual_senders=(CVDRole.VENDOR, CVDRole.CASE_OWNER))
    entry = _entry(
        occasion,
        entitlement=SenderRule.in_case(
            SenderEntitlementKind.ACTIVE_PARTICIPANT
        ),
    )
    assert (
        sent_by(entry, occasion)
        == "an active participant (usually: vendor, case owner)"
    )


@pytest.mark.spec("MSM-08-005")
def test_sent_by_joins_an_any_of_side_with_or():
    entry = _entry(
        entitlement=SenderRule.in_case(
            SenderEntitlementKind.CASE_OWNER,
            SenderEntitlementKind.CASE_MANAGER,
        )
    )
    assert (
        sent_by(entry, entry.occasions[0])
        == "the case manager or the case owner"
    )


_TWO_SIDED = SenderRule(
    at_case_manager=any_of(SenderEntitlementKind.ACTIVE_PARTICIPANT),
    at_participant=any_of(SenderEntitlementKind.CASE_MANAGER),
)


@pytest.mark.spec("MSM-08-005")
@pytest.mark.spec("MSM-08-009")
@pytest.mark.parametrize(
    ("addressee", "wording"),
    [
        (AddresseeSide.CASE_MANAGER, "an active participant"),
        (AddresseeSide.PARTICIPANT, "the case manager"),
    ],
)
def test_sent_by_words_the_side_of_the_occasions_addressee(
    addressee: AddresseeSide, wording: str
):
    """Two occasions of one two-sided rule get two senders (ADR-0129)."""
    occasion = _occasion(addressee=addressee)
    entry = _entry(occasion, entitlement=_TWO_SIDED)
    assert sent_by(entry, occasion) == wording


@pytest.mark.spec("MSM-08-005")
def test_sent_by_words_the_outside_case_side_of_a_pre_case_rule():
    occasion = _occasion(addressee=AddresseeSide.OUTSIDE_CASE)
    entry = _entry(
        occasion,
        entitlement=SenderRule.before_case(SenderEntitlementKind.ANY_ACTOR),
    )
    assert sent_by(entry, occasion) == "any actor"


@pytest.mark.spec("MSM-08-009")
@pytest.mark.parametrize(
    ("rule", "addressee"),
    [
        (_TWO_SIDED, AddresseeSide.OUTSIDE_CASE),
        (
            SenderRule.before_case(SenderEntitlementKind.ANY_ACTOR),
            AddresseeSide.CASE_MANAGER,
        ),
        (
            SenderRule.before_case(SenderEntitlementKind.ANY_ACTOR),
            AddresseeSide.PARTICIPANT,
        ),
    ],
)
def test_an_occasion_sent_to_a_side_its_rule_lacks_fails(
    rule: SenderRule, addressee: AddresseeSide
):
    with pytest.raises(ValueError, match="MSM-08-009"):
        _entry(_occasion(addressee=addressee), entitlement=rule)


@pytest.mark.spec("MSM-08-009")
@pytest.mark.parametrize("addressee", list(AddresseeSide), ids=str)
def test_an_exempt_occasion_may_name_any_addressee(addressee: AddresseeSide):
    """An exemption has no sides yet, so it constrains no addressee."""
    occasion = _occasion(addressee=addressee)
    entry = _entry(occasion, entitlement=exempt("#0000", "stub"))
    assert sent_by(entry, occasion) == NOT_YET_CHECKED


@pytest.mark.spec("MSM-08-010")
def test_a_permanent_exemption_reads_no_sender_check_not_not_yet_checked():
    """Nothing is pending for a use case no sender check applies to."""
    occasion = _occasion(addressee=AddresseeSide.CASE_MANAGER)
    entry = _entry(occasion, entitlement=no_sender_check("nothing to gate"))
    assert sent_by(entry, occasion) == NO_SENDER_CHECK


#: The "Send to" wording of each addressee, pinned as literals.
_SEND_TO: dict[AddresseeSide, str] = {
    AddresseeSide.CASE_MANAGER: "the case manager",
    AddresseeSide.PARTICIPANT: "a participant",
    AddresseeSide.OUTSIDE_CASE: "an actor outside any case",
}


@pytest.mark.spec("MSM-08-009")
@pytest.mark.parametrize("addressee", list(AddresseeSide), ids=str)
def test_send_to_words_the_addressee(addressee: AddresseeSide):
    assert send_to(_occasion(addressee=addressee)) == _SEND_TO[addressee]


def test_sent_by_refuses_an_undeclared_entitlement():
    entry = _entry(entitlement=None)
    with pytest.raises(ValueError, match="declares no sender_entitlement"):
        sent_by(entry, entry.occasions[0])


def test_sent_by_refuses_a_declaration_that_is_not_a_rule():
    """A bare kind, the pre-HP-01-008 shape, is not a declaration."""
    entry = _entry()

    class _BareKind:
        sender_entitlement = SenderEntitlementKind.CASE_OWNER

    entry = dataclasses.replace(entry, use_case_class=_BareKind)
    with pytest.raises(ValueError, match="declares no sender_entitlement"):
        sent_by(entry, entry.occasions[0])


#: The side of a sender rule each addressee reads, restated here so the
#: registry test below does not reuse ``SenderRule.side``.
_SIDE_FIELD: dict[AddresseeSide, str] = {
    AddresseeSide.CASE_MANAGER: "at_case_manager",
    AddresseeSide.PARTICIPANT: "at_participant",
    AddresseeSide.OUTSIDE_CASE: "outside_case",
}


def _expected_sent_by(entry: SemanticEntry, occasion: Occasion) -> str:
    """Recompute "Sent by" from the declaration, independently of the code.

    Reads the declaration rather than pinning per-entry strings, so a use case
    that trades an exemption for a real rule changes the value without
    breaking this test.  The object a position names reuses
    ``answered_request``, which the synthetic-entry tests above pin to
    literal strings.
    """
    declared = getattr(entry.use_case_class, "sender_entitlement", None)
    if isinstance(declared, SenderExemption):
        base = NOT_YET_CHECKED
    else:
        assert isinstance(declared, SenderRule)
        side = getattr(declared, _SIDE_FIELD[occasion.addressee])
        assert side, f"{occasion.anchor}: no side for its addressee"
        words = [
            kind.sent_by.replace("{object}", answered_request(entry))
            for kind in SenderEntitlementKind
            if kind in side
        ]
        base = " or ".join(words)
    if not occasion.usual_senders:
        return base
    roles = ", ".join(
        r.value.replace("_", " ") for r in occasion.usual_senders
    )
    return f"{base} (usually: {roles})"


_REGISTRY_OCCASIONS = [(e, o) for e in SEMANTIC_REGISTRY for o in e.occasions]


@pytest.mark.spec("MSM-08-005")
@pytest.mark.spec("MSM-08-009")
@pytest.mark.parametrize(
    ("entry", "occasion"),
    _REGISTRY_OCCASIONS,
    ids=lambda value: getattr(value, "anchor", ""),
)
def test_registry_sent_by_follows_the_side_of_the_addressee(
    entry: SemanticEntry, occasion: Occasion
):
    assert sent_by(entry, occasion) == _expected_sent_by(entry, occasion)
    assert send_to(occasion) == _SEND_TO[occasion.addressee]
    for role in occasion.usual_senders:
        assert isinstance(role, CVDRole)


@pytest.mark.spec("MSM-08-005")
@pytest.mark.spec("MSM-08-009")
@pytest.mark.parametrize(
    ("anchor", "addressee", "wording"),
    [
        (
            "embargo-proposal",
            AddresseeSide.CASE_MANAGER,
            "the case manager or an active participant",
        ),
        (
            "relay-embargo-proposal",
            AddresseeSide.PARTICIPANT,
            "the case manager",
        ),
        (
            "embargo-termination",
            AddresseeSide.CASE_MANAGER,
            "the case manager or the case owner",
        ),
        (
            "embargo-termination-notice",
            AddresseeSide.PARTICIPANT,
            "the case manager",
        ),
        (
            "remove-note-from-case",
            AddresseeSide.CASE_MANAGER,
            "the case owner or the note's author",
        ),
        (
            "report-acknowledgment",
            AddresseeSide.OUTSIDE_CASE,
            "the addressee of the vulnerability report offer"
            " (usually: vendor, coordinator)",
        ),
    ],
)
def test_one_wire_activity_carries_an_occasion_per_side(
    anchor: str, addressee: AddresseeSide, wording: str
):
    """The two-sided embargo rules give each occasion its own sender."""
    entry, occasion = next(
        (e, o) for e, o in _REGISTRY_OCCASIONS if o.anchor == anchor
    )
    assert occasion.addressee is addressee
    assert sent_by(entry, occasion) == wording
