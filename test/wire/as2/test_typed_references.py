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

from vultron.core.models.actor import CoreActor
from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import find_matching_semantics
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingPublishedError,
)
from vultron.wire.as2.extractor._builders import proposed_embargo_from
from vultron.wire.as2.extractor._pattern import bare_object_id
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.typed_reference import as_TypedReference
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
)

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
    """No type defines a preview yet, so every typed reference carrying one
    is refused, and the refusal names where it sat."""
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
def test_a_case_reference_is_still_the_case_reference() -> None:
    """The typed case reference keeps its own class (ADR-0165)."""
    reference = {"id": CASE_ID, "type": "VulnerabilityCase"}

    parsed = parse_activity(_body(reference, "Join"))

    assert isinstance(_object_of(parsed), as_VulnerabilityCaseReference)


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
