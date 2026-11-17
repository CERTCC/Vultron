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

"""What an object slot may hold, and when a whole object must carry its time.

ADR-0198: a slot holds a whole object, a typed reference (exactly ``id`` and
``type``, optionally a ``preview``), or a URI.  A typed reference routes by its
type but is never read as the object (MV-10-011), a ``preview`` is refused for a
type that defines none (MV-10-012), and a received whole object other than an
actor profile or a collection carries ``published`` (CLP-15-011).

Each test feeds raw JSON through ``parse_activity``, the real inbound edge.  The
tests still waiting on an implementation Task are strict xfails; each reason
names its Task, so the known-gaps page links it.
"""

import logging
from typing import Any

import pytest
from pydantic import ValidationError

from test.support.objects import authored_at, make
from test.support.received import TEST_SENDER_POSITION
from vultron.core.models.actor import CoreActor
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import MessageSemantics
from vultron.core.models.participant_status import ParticipantStatus
from vultron.semantic_registry import extract_event, find_matching_semantics
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingPublishedError,
)
from vultron.wire.as2.extractor._builders import proposed_embargo_from
from vultron.wire.as2.extractor._pattern import bare_object_id
from vultron.wire.as2.factories import rm_engage_case_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.typed_reference import (
    as_TypedReference,
    is_case_reference,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

ACTOR = "https://example.org/actors/alice"
CASE_ID = "https://example.org/cases/c1"
PUBLISHED = "2026-01-02T03:04:05+00:00"

REQUIRED_PUBLISHED_TASK = "#6456"

#: Types whose ``{id, type}`` form was once accepted as a hollow whole object
#: (#5265); each is now read as a typed reference.
REFERENCED_TYPES = ["Note", "Event", "CaseParticipant", "VulnerabilityReport"]


def _body(
    obj: dict[str, Any], activity_type: str = "Remove", **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": activity_type,
        "id": "https://example.org/activities/1",
        "actor": ACTOR,
        "published": PUBLISHED,
        "object": obj,
    }
    body.update(extra)
    return body


@pytest.mark.spec("MV-10-011")
@pytest.mark.parametrize("type_", REFERENCED_TYPES)
def test_a_typed_reference_is_not_read_as_the_object(type_: str) -> None:
    """An ``{id, type}`` object names the object; it never becomes one."""
    whole_class = find_in_vocabulary(type_)
    assert whole_class is not None
    reference = {"id": f"https://example.org/objects/{type_}", "type": type_}

    parsed = parse_activity(_body(reference, target=CASE_ID))

    assert isinstance(parsed, as_TransitiveActivity)
    assert not isinstance(parsed.object_, whole_class)


@pytest.mark.spec("MV-10-012")
def test_a_typed_reference_with_an_undefined_preview_is_refused() -> None:
    """No preview is defined for a note, so a note reference carrying one fails."""
    reference = {
        "id": "https://example.org/notes/1",
        "type": "Note",
        # A URI preview: the note class reads ``preview`` as a string, so this
        # is the form that parses today rather than failing for another reason.
        "preview": "https://example.org/notes/1/preview",
    }

    # The match keeps this from passing on another refusal: the reference has
    # no ``published``, so CLP-15-011 alone would refuse it as a whole note.
    with pytest.raises(VultronParseError, match="MV-10-012"):
        parse_activity(_body(reference, target=CASE_ID))


@pytest.mark.xfail(
    strict=True,
    reason=f"CLP-15-011: a received whole object without published is carried."
    f" Tracked by {REQUIRED_PUBLISHED_TASK}.",
)
@pytest.mark.spec("CLP-15-011")
def test_a_whole_object_without_published_is_refused() -> None:
    """A whole note with no ``published`` is malformed, not untimed."""
    note = {
        "id": "https://example.org/notes/1",
        "type": "Note",
        "content": "the vendor confirmed the fix",
        "attributedTo": ACTOR,
    }

    with pytest.raises(VultronParseMissingPublishedError, match="CLP-15-011"):
        parse_activity(_body(note, "Create"))


@pytest.mark.xfail(
    strict=True,
    reason=f"CLP-15-011: a nested whole object without published is carried."
    f" Tracked by {REQUIRED_PUBLISHED_TASK}.",
)
@pytest.mark.spec("CLP-15-011")
def test_a_nested_whole_object_without_published_is_refused() -> None:
    """The rule reaches a whole object at any depth, not only the top slot."""
    note = {
        "id": "https://example.org/notes/1",
        "type": "Note",
        "content": "the vendor confirmed the fix",
        "attributedTo": ACTOR,
    }
    create = {
        "id": "https://example.org/activities/2",
        "type": "Create",
        "actor": ACTOR,
        "published": PUBLISHED,
        "object": note,
    }

    with pytest.raises(VultronParseMissingPublishedError, match="CLP-15-011"):
        parse_activity(_body(create, "Announce"))


@pytest.mark.spec("CLP-15-011")
@pytest.mark.parametrize(
    "exempt",
    [
        {
            "id": "https://example.org/actors/bob",
            "type": "Person",
            "name": "Bob",
            "inbox": "https://example.org/actors/bob/inbox",
            "outbox": "https://example.org/actors/bob/outbox",
        },
        {
            "id": "https://example.org/collections/1",
            "type": "Collection",
            "totalItems": 0,
            "items": [],
        },
    ],
    ids=["actor-profile", "collection"],
)
def test_an_actor_profile_or_collection_without_published_is_accepted(
    exempt: dict[str, Any],
) -> None:
    """An actor profile and a collection are exempt from CLP-15-011."""
    parsed = parse_activity(_body(exempt, "Create"))

    assert isinstance(parsed, as_TransitiveActivity)
    assert parsed.object_ is not None
    assert getattr(parsed.object_, "published", None) is None


def _object_of(activity: object) -> object:
    """The ``object`` an activity carries, as the parser read it."""
    return getattr(activity, "object_", None)


def _as_typed_reference(value: object) -> as_TypedReference:
    assert isinstance(value, as_TypedReference)
    return value


@pytest.mark.spec("MV-10-011")
@pytest.mark.parametrize("type_", REFERENCED_TYPES)
def test_a_typed_reference_claims_only_its_id_and_type(type_: str) -> None:
    """No field default of the named class runs for a reference: it carries
    exactly the ``id`` and ``type`` it arrived with (#5265)."""
    reference = {"id": f"https://example.org/objects/{type_}", "type": type_}

    parsed = parse_activity(_body(reference, target=CASE_ID))

    parsed_reference = _as_typed_reference(_object_of(parsed))
    dumped = parsed_reference.model_dump(by_alias=True, exclude_none=True)
    dumped.pop("@context", None)
    assert dumped == reference


@pytest.mark.spec("MV-10-011")
def test_a_typed_reference_is_read_as_one_at_any_depth() -> None:
    """A reference nested in an inline activity is read the same way."""
    reference = {
        "id": "https://example.org/participants/p1",
        "type": "CaseParticipant",
    }
    invite = {
        "id": "https://example.org/activities/2",
        "type": "Remove",
        "actor": ACTOR,
        "published": PUBLISHED,
        "object": reference,
        "target": CASE_ID,
    }

    parsed = parse_activity(_body(invite, "Undo"))

    inner = _object_of(parsed)
    assert isinstance(inner, as_TransitiveActivity)
    assert _as_typed_reference(_object_of(inner)).id_ == reference["id"]


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("MV-04-003")
def test_an_object_with_one_more_key_is_a_whole_object_not_a_reference() -> (
    None
):
    """The shape decides: a key beyond ``id`` and ``type`` makes the object a
    whole object, which its class judges (ADR-0198)."""
    note = {
        "id": "https://example.org/notes/1",
        "type": "Note",
        "content": "the vendor confirmed the fix",
    }

    parsed = parse_activity(_body(note, "Create"))

    assert isinstance(_object_of(parsed), find_in_vocabulary("Note"))
    assert not isinstance(_object_of(parsed), as_TypedReference)


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("SE-01-002")
@pytest.mark.parametrize(
    ("activity_type", "type_", "extra", "semantics"),
    [
        (
            "Remove",
            "CaseParticipant",
            {"target": CASE_ID},
            MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
        ),
        (
            "Add",
            "CaseParticipant",
            {"target": CASE_ID},
            MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE,
        ),
        (
            "Announce",
            "EmbargoEvent",
            {"context": CASE_ID},
            MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE,
        ),
        (
            "Add",
            "Note",
            {"target": CASE_ID},
            MessageSemantics.ADD_NOTE_TO_CASE,
        ),
        (
            "Offer",
            "VulnerabilityReport",
            {},
            MessageSemantics.SUBMIT_REPORT,
        ),
    ],
    ids=[
        "Remove(CaseParticipant)",
        "Add(CaseParticipant)",
        "Announce(EmbargoEvent)",
        "Add(Note)",
        "Offer(VulnerabilityReport)",
    ],
)
def test_a_typed_reference_routes_by_its_type(
    activity_type: str,
    type_: str,
    extra: dict[str, Any],
    semantics: MessageSemantics,
) -> None:
    """An activity naming its object by typed reference matches the semantics
    of one carrying the whole object of that type."""
    reference = {"id": f"https://example.org/objects/{type_}", "type": type_}

    parsed = parse_activity(_body(reference, activity_type, **extra))

    assert find_matching_semantics(parsed) is semantics


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("VAM-01-009")
def test_a_reference_no_pattern_matches_names_the_object_to_fetch() -> None:
    """A reference to an activity cannot satisfy a nested pattern by type
    alone, so the activity is unresolvable and names the reference's id."""
    reference = {
        "id": "https://example.org/activities/invite-1",
        "type": "Invite",
    }

    parsed = parse_activity(_body(reference, "Accept"))

    assert (
        find_matching_semantics(parsed)
        is MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    )
    assert bare_object_id(parsed) == reference["id"]


@pytest.mark.spec("AKM-03-006")
@pytest.mark.parametrize("outer", ["Undo", "Reject", "Announce"])
def test_an_unmatched_act_ending_in_a_case_reference_names_nothing_to_fetch(
    outer: str,
) -> None:
    """A case is read from the receiver's store, never fetched (ADR-0165).

    An act no pattern matches whose ``object`` chain ends in a case
    reference stays unknown: it names no object for the inbox to fetch.
    """
    join = {
        "type": "Join",
        "id": "https://example.org/activities/join-1",
        "actor": ACTOR,
        "published": PUBLISHED,
        "object": {"id": CASE_ID, "type": "VulnerabilityCase"},
    }

    parsed = parse_activity(_body(join, outer))

    assert find_matching_semantics(parsed) is MessageSemantics.UNKNOWN
    assert bare_object_id(parsed) is None


@pytest.mark.spec("MV-10-012")
@pytest.mark.parametrize(
    ("type_", "slot"),
    [
        ("CaseParticipant", "object"),
        ("EmbargoEvent", "object"),
        ("VulnerabilityCase", "object"),
        ("Person", "object"),
        ("Note", "target"),
    ],
)
def test_a_preview_is_refused_for_every_type_naming_its_position(
    type_: str, slot: str
) -> None:
    """No type but the case defines a preview, and a case's preview is an
    inline stub, so each of these references is refused, and the refusal
    names where it sat."""
    reference = {
        "id": f"https://example.org/objects/{type_}",
        "type": type_,
        "preview": "https://example.org/previews/1",
    }
    other = (
        {"object": "https://example.org/notes/1"} if slot == "target" else {}
    )
    body = _body(reference, "Add", target=CASE_ID, **other)
    if slot == "target":
        body["target"] = reference

    with pytest.raises(VultronParseError, match="MV-10-012") as raised:
        parse_activity(body)

    assert repr(slot) in str(raised.value)


@pytest.mark.spec("MV-10-012")
def test_a_nested_preview_is_refused_at_its_position() -> None:
    reference = {
        "id": "https://example.org/participants/p1",
        "type": "CaseParticipant",
        "preview": {"type": "Note", "content": "a participant"},
    }
    inner = {
        "id": "https://example.org/activities/2",
        "type": "Remove",
        "actor": ACTOR,
        "published": PUBLISHED,
        "object": reference,
        "target": CASE_ID,
    }

    with pytest.raises(VultronParseError, match="MV-10-012") as raised:
        parse_activity(_body(inner, "Undo"))

    assert "'object.object'" in str(raised.value)


@pytest.mark.spec("AKM-05-017")
@pytest.mark.spec("MV-10-011")
def test_an_actor_reference_is_still_read_as_the_actor() -> None:
    """The actor reference keeps its form: the actor's class, naming only
    the actor's id (AKM-05-017 to AKM-05-019, ADR-0159)."""
    reference = {"id": "https://example.org/actors/bob", "type": "Person"}

    parsed = parse_activity(_body(reference, "Offer", target=CASE_ID))

    actor = _object_of(parsed)
    assert isinstance(actor, CoreActor)
    assert actor.id_ == reference["id"]
    assert not isinstance(actor, as_TypedReference)


@pytest.mark.spec("MV-10-011")
def test_a_case_reference_is_a_typed_reference() -> None:
    """The case reference is the generic typed reference (ADR-0165, ADR-0198).

    No class of its own is registered under ``VulnerabilityCase``: the shape,
    not the registry, tells it from a case (VM-01-017).
    """
    reference = {"id": CASE_ID, "type": "VulnerabilityCase"}

    parsed = parse_activity(_body(reference, "Join"))

    named = _as_typed_reference(_object_of(parsed))
    assert named.type_ == "VulnerabilityCase"
    assert named.id_ == CASE_ID
    assert find_in_vocabulary("VulnerabilityCase") is VulnerabilityCase


@pytest.mark.spec("AKM-03-004")
def test_an_act_naming_its_case_refuses_a_reference_to_another_type() -> None:
    """The object of an act on a case is the case, never another reference.

    The case reference is the generic typed reference, so the slot checks
    the type it names (ADR-0165).
    """
    join = rm_engage_case_activity(CASE_ID, actor=ACTOR, at=authored_at())
    assert is_case_reference(join.object_)
    note = {"id": "https://example.org/notes/n1", "type": "Note"}
    body = join.model_dump(by_alias=True, mode="json") | {"object": note}

    with pytest.raises(ValidationError, match="names no case"):
        type(join).model_validate(body)


@pytest.mark.spec("AKM-03-004")
@pytest.mark.spec("MV-10-012")
def test_a_case_reference_carrying_a_preview_is_no_case_reference() -> None:
    """A case reference is exactly a case's ``id`` and ``type`` (ADR-0165).

    One that also carries the case's preview is a previewed reference
    (ADR-0205): an act on a case may not name the case by it, and the
    receiver's case-reference exceptions do not apply to it.
    """
    previewed = as_TypedReference.model_validate(
        {
            "id": CASE_ID,
            "type": "VulnerabilityCase",
            "preview": {
                "type": "CasePreview",
                "id": f"{CASE_ID}/stub",
                "summary": "A remote code execution vulnerability.",
            },
        }
    )

    assert not is_case_reference(previewed)
    assert is_case_reference(
        as_TypedReference(type_="VulnerabilityCase", id_=CASE_ID)
    )


@pytest.mark.spec("MV-10-011")
def test_a_reference_in_a_slot_needing_the_whole_object_says_so() -> None:
    """A slot that admits only a whole object refuses a reference, and the
    refusal names the slot and why."""
    proposal = {
        "id": "https://example.org/proposals/1",
        "type": "CaseProposal",
        "published": PUBLISHED,
        "attributedTo": ACTOR,
        "inReplyTo": {"id": "https://example.org/offers/1", "type": "Offer"},
    }

    with pytest.raises(VultronParseError, match="MV-10-011") as raised:
        parse_activity(_body(proposal, "Create"))

    assert "'object.inReplyTo'" in str(raised.value)


@pytest.mark.spec("MV-10-011")
def test_a_reference_in_a_slot_taking_only_a_uri_says_to_send_its_id() -> None:
    """A slot that admits only a URI refuses a reference, and the refusal
    says to send the reference's id, not the whole object."""
    embargo = {
        "id": "https://example.org/embargoes/2",
        "type": "EmbargoEvent",
        "startTime": PUBLISHED,
        "endTime": "2027-03-01T00:00:00Z",
        "published": PUBLISHED,
        "context": {"id": "https://example.org/notes/1", "type": "Note"},
    }

    with pytest.raises(VultronParseError, match="MV-10-011") as raised:
        parse_activity(_body(embargo, "Invite", target=CASE_ID))

    message = str(raised.value)
    assert "'object.context'" in message
    assert "takes only a URI" in message
    assert "needs the whole object" not in message


@pytest.mark.spec("MV-10-011")
def test_a_typed_reference_target_reaches_core_as_a_reference() -> None:
    """A reference in ``target`` never reaches core as the wire reference,
    in the event or in the activity snapshot core reads (MV-10-011)."""
    status = make(
        ParticipantStatus,
        context=CASE_ID,
        attributed_to=ACTOR,
    )
    participant_id = "https://example.org/participants/p1"
    activity = parse_activity(
        _body(
            status.model_dump(mode="json", by_alias=True, exclude_none=True),
            "Add",
            target={"id": participant_id, "type": "CaseParticipant"},
            context=CASE_ID,
            ledgerPosition=TEST_SENDER_POSITION.model_dump(by_alias=True),
        )
    )

    event = extract_event(activity)

    assert (
        event.semantic_type
        == MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    )
    snapshot_target = getattr(event.activity, "target", None)
    assert isinstance(snapshot_target, CoreObject)
    assert not isinstance(snapshot_target, as_TypedReference)
    assert snapshot_target.id_ == participant_id


@pytest.mark.spec("EP-04-004")
@pytest.mark.spec("MV-10-011")
def test_a_proposed_embargo_by_reference_is_no_proposal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A reference claims no terms, so it is read as a bare id would be:
    logged, and no proposal."""
    carrier = parse_activity(
        _body(
            {
                "id": "https://example.org/reports/1",
                "type": "VulnerabilityReport",
            },
            "Offer",
            proposedEmbargo={
                "id": "https://example.org/embargoes/1",
                "type": "EmbargoEvent",
            },
        )
    )

    with caplog.at_level(logging.WARNING):
        found = proposed_embargo_from(carrier, activity_id="a-1")

    assert found is None
    assert any("by reference" in r.getMessage() for r in caplog.records)
