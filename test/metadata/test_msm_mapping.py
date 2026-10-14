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

from typing import Any, ClassVar

import pytest

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
    SenderExemption,
    SenderRule,
    any_of,
    exempt,
)
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.enums.roles import CVDRole
from vultron.metadata.msm._mapping import (
    NOT_YET_CHECKED,
    ROW_SPECS,
    SENT_BY_WORDING,
    MappingStatus,
    answered_request,
    mapping_status,
    sent_by,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY, lookup_entry
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    MessagePage,
    Occasion,
    ProtocolShorthand,
)
from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
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
        "heading": f"Stub situation {index}",
        "description": "Stands in for a real occasion.",
        "example": f"stub_example_{index}",
    }
    fields.update(overrides)
    return Occasion(**fields)


def _entry(
    *occasions: Occasion,
    semantics: MessageSemantics = MessageSemantics.CREATE_NOTE,
    entitlement: SenderEntitlement | None = _CASE_OWNER_RULE,
    pattern: ActivityPattern | None = None,
) -> SemanticEntry:
    return SemanticEntry(
        semantics=semantics,
        pattern=pattern,
        event_class=_StubEvent,
        use_case_class=_use_case(entitlement),
        phrase="{actor} did a thing",
        occasions=occasions or (_occasion(),),
        page=MessagePage.GENERAL,
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
        (MessageSemantics.CREATE_NOTE, MappingStatus.EXPANSION),
        (MessageSemantics.CREATE_EMBARGO_EVENT, MappingStatus.NONE),
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


@pytest.mark.spec("MSM-08-005")
@pytest.mark.parametrize(
    ("kind", "wording"),
    [
        (SenderEntitlementKind.CASE_MANAGER, "the case manager"),
        (SenderEntitlementKind.CASE_OWNER, "the case owner"),
        (SenderEntitlementKind.ACTIVE_PARTICIPANT, "an active participant"),
        (SenderEntitlementKind.INVITEE, "the invitee"),
        (SenderEntitlementKind.ANY_ACTOR, "any actor"),
    ],
)
def test_sent_by_words_each_kind(kind: SenderEntitlementKind, wording: str):
    entry = _entry(entitlement=SenderRule.in_case(kind))
    assert sent_by(entry, entry.occasions[0]) == wording


@pytest.mark.spec("MSM-08-005")
def test_every_kind_has_a_wording():
    """A new kind without a wording would make ``sent_by`` raise KeyError."""
    worded = set(SENT_BY_WORDING) | {SenderEntitlementKind.NAMED_ACTOR}
    assert worded == set(SenderEntitlementKind)


@pytest.mark.spec("MSM-08-005")
def test_sent_by_states_an_exemption_as_not_yet_checked():
    entry = _entry(entitlement=exempt("#0000", "stub"))
    assert sent_by(entry, entry.occasions[0]) == "not yet checked"


@pytest.mark.spec("MSM-08-005")
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
        == "the addressee of the vulnerability case"
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


@pytest.mark.spec("MSM-08-005")
def test_sent_by_words_the_case_manager_side_of_a_two_sided_rule():
    entry = _entry(
        entitlement=SenderRule(
            at_case_manager=any_of(SenderEntitlementKind.ACTIVE_PARTICIPANT),
            at_participant=any_of(SenderEntitlementKind.CASE_MANAGER),
        )
    )
    assert sent_by(entry, entry.occasions[0]) == "an active participant"


@pytest.mark.spec("MSM-08-005")
def test_sent_by_words_the_outside_case_side_of_a_pre_case_rule():
    entry = _entry(
        entitlement=SenderRule.before_case(SenderEntitlementKind.ANY_ACTOR)
    )
    assert sent_by(entry, entry.occasions[0]) == "any actor"


def test_sent_by_refuses_an_undeclared_entitlement():
    entry = _entry(entitlement=None)
    with pytest.raises(ValueError, match="declares no sender_entitlement"):
        sent_by(entry, entry.occasions[0])


def _expected_sent_by(entry: SemanticEntry, occasion: Occasion) -> str:
    """Recompute "Sent by" from the declaration, independently of the code.

    Reads the declaration rather than pinning per-entry strings, so a use case
    that trades an exemption for a real rule changes the value without
    breaking this test.  The addressee wording reuses ``answered_request``,
    which the synthetic-entry tests above pin to literal strings.
    """
    declared = getattr(entry.use_case_class, "sender_entitlement", None)
    if isinstance(declared, SenderExemption):
        base = NOT_YET_CHECKED
    else:
        assert isinstance(declared, SenderRule)
        side = (
            declared.at_case_manager
            or declared.outside_case
            or declared.at_participant
        )
        words = [
            f"the addressee of the {answered_request(entry)}"
            if kind is SenderEntitlementKind.NAMED_ACTOR
            else SENT_BY_WORDING[kind]
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


@pytest.mark.spec("MSM-08-005")
@pytest.mark.parametrize(
    ("entry", "occasion"),
    [(e, o) for e in SEMANTIC_REGISTRY for o in e.occasions],
    ids=lambda value: getattr(value, "anchor", ""),
)
def test_registry_sent_by_follows_the_declared_entitlement(
    entry: SemanticEntry, occasion: Occasion
):
    assert sent_by(entry, occasion) == _expected_sent_by(entry, occasion)
    for role in occasion.usual_senders:
        assert isinstance(role, CVDRole)
