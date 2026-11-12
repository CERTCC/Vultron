#!/usr/bin/env python

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

"""The actor ids a case record is keyed on carry one spelling (#5919).

``CaseParticipant.attributed_to`` and ``VulnerabilityCase.attributed_to`` are
``NormalisedActorId``: a value with a trailing slash is refused where it is
built (ARCH-10-001), and a received record is normalised at its parse, the
point where its ids are extracted (OID-01-006).  So the roster index key that
``add_participant`` builds from the record is the record's own spelling, and
a canonical-id lookup finds both.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from test.support.objects import authored_at, make
from vultron.core.models._helpers import INBOUND_CONTEXT_KEY
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import add_participant_to_case_activity
from vultron.wire.as2.parser import parse_activity

CASE_ID = "https://example.org/cases/c1"
OWNER_ID = "https://example.org/actors/owner"
VENDOR_ID = "https://example.org/actors/vendor"
PARTICIPANT_ID = f"{CASE_ID}/participants/vendor"


def _inbound(cls: type[Any], data: dict[str, Any]) -> Any:
    return cls.model_validate(data, context={INBOUND_CONTEXT_KEY: True})


def _participant_dump(attributed_to: str) -> dict[str, Any]:
    participant = make(
        CaseParticipant,
        id_=PARTICIPANT_ID,
        attributed_to=VENDOR_ID,
        context=CASE_ID,
    )
    dumped = participant.model_dump(by_alias=True, mode="json")
    dumped["attributedTo"] = attributed_to
    return dumped


@pytest.mark.spec("OID-01-006", "ARCH-10-001")
def test_a_participant_refuses_a_slash_spelled_actor_at_construction() -> None:
    with pytest.raises(ValidationError, match="trailing slash"):
        make(
            CaseParticipant,
            id_=PARTICIPANT_ID,
            attributed_to=f"{VENDOR_ID}/",
            context=CASE_ID,
        )


@pytest.mark.spec("OID-01-006", "ARCH-10-001")
def test_a_case_refuses_a_slash_spelled_owner_at_construction() -> None:
    with pytest.raises(ValidationError, match="trailing slash"):
        make(VulnerabilityCase, id_=CASE_ID, attributed_to=f"{OWNER_ID}/")


@pytest.mark.spec("OID-01-006")
def test_a_received_participants_derived_name_and_status_are_canonical() -> (
    None
):
    """The name and first status a received record derives from its actor
    take the spelling the record's ``attributed_to`` holds, not the raw one:
    the model before-validators that seed them run before the field's own
    inbound normaliser (#5919)."""
    data = _participant_dump(f"{VENDOR_ID}/")
    for key in ("name", "participantStatuses"):
        data.pop(key, None)

    participant = _inbound(CaseParticipant, data)

    assert participant.attributed_to == VENDOR_ID
    assert participant.name == VENDOR_ID
    assert [s.attributed_to for s in participant.participant_statuses] == [
        VENDOR_ID
    ]


@pytest.mark.spec("OID-01-006")
def test_a_received_participant_is_normalised_where_it_is_parsed() -> None:
    participant = _inbound(CaseParticipant, _participant_dump(f"{VENDOR_ID}/"))

    assert participant.attributed_to == VENDOR_ID


@pytest.mark.spec("OID-01-006")
def test_a_received_case_is_normalised_where_it_is_parsed() -> None:
    case = make(VulnerabilityCase, id_=CASE_ID, attributed_to=OWNER_ID)
    dumped = case.model_dump(by_alias=True, mode="json")
    dumped["attributedTo"] = f"{OWNER_ID}/"

    assert _inbound(VulnerabilityCase, dumped).attributed_to == OWNER_ID


@pytest.mark.spec("OID-01-006", "ARCH-10-001")
def test_a_stored_row_with_the_other_spelling_is_refused_not_rewritten() -> (
    None
):
    """Only a received record is normalised; any other read refuses it.

    No stored record is converted: a store holding the slash spelling is
    refused on load and is reset or reseeded (AC-3 of #5919).
    """
    with pytest.raises(ValidationError, match="trailing slash"):
        CaseParticipant.model_validate(_participant_dump(f"{VENDOR_ID}/"))


@pytest.mark.spec("OID-01-006")
def test_the_roster_key_is_the_received_records_own_spelling() -> None:
    """``add_participant`` keys the index on the canonical id (AC-2)."""
    participant = _inbound(CaseParticipant, _participant_dump(f"{VENDOR_ID}/"))
    case = make(VulnerabilityCase, id_=CASE_ID, attributed_to=OWNER_ID)

    case.add_participant(participant)

    assert case.actor_participant_index == {VENDOR_ID: PARTICIPANT_ID}
    assert participant.attributed_to in case.actor_participant_index


@pytest.mark.spec("OID-01-006", "OID-01-007")
def test_an_add_participant_activity_yields_the_canonical_actor() -> None:
    """A peer's ``Add(CaseParticipant)`` reaches core with one spelling.

    The whole edge: the body is parsed as received, then the extractor
    builds the participant the use case adds to the roster.
    """
    participant = make(
        CaseParticipant,
        id_=PARTICIPANT_ID,
        attributed_to=VENDOR_ID,
        context=CASE_ID,
    )
    activity = add_participant_to_case_activity(
        participant,
        target=CASE_ID,
        actor=OWNER_ID,
        to=[VENDOR_ID],
        at=authored_at(),
    )
    body = activity.model_dump(by_alias=True, mode="json", exclude_none=True)
    body["object"]["attributedTo"] = f"{VENDOR_ID}/"
    body["ledgerPosition"] = {"logIndex": -1, "entryHash": "0" * 64}

    event = extract_event(parse_activity(body))

    assert isinstance(event.object_, CaseParticipant)
    assert event.object_.attributed_to == VENDOR_ID
