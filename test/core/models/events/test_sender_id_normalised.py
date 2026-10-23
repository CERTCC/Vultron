"""A received event refuses a sender id that is not normalised (OID-01-007).

The wire extractor strips a trailing slash from the sender id before it builds
the event, so core compares it with stored ids exactly.  A path that skips the
extractor (a trigger, a fixture) must fail where it builds the event instead of
storing the other spelling (ARCH-10-001).
"""

import pytest
from pydantic import ValidationError

from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.events.note import AddNoteToCaseReceivedEvent
from vultron.primitives import normalise_actor_id, same_actor_id

SENDER = "https://example.org/actors/vendor"
ACTIVITY_ID = "https://example.org/activities/a1"


@pytest.mark.spec("OID-01-007")
@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize(
    "event_class", [VultronEvent, AddNoteToCaseReceivedEvent]
)
def test_received_event_refuses_slash_spelled_sender_id(event_class):
    with pytest.raises(ValidationError, match="trailing slash"):
        event_class(
            semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
            activity_id=ACTIVITY_ID,
            actor_id=SENDER + "/",
        )


@pytest.mark.spec("OID-01-007")
def test_received_event_accepts_normalised_sender_id():
    event = VultronEvent(
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        activity_id=ACTIVITY_ID,
        actor_id=SENDER,
    )
    assert event.actor_id == SENDER


@pytest.mark.spec("OID-01-007")
def test_received_event_refuses_slash_spelled_sender_id_on_assignment():
    event = VultronEvent(
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        activity_id=ACTIVITY_ID,
        actor_id=SENDER,
    )
    with pytest.raises(ValidationError, match="trailing slash"):
        event.actor_id = SENDER + "/"


@pytest.mark.spec("OID-01-007")
def test_received_event_still_refuses_blank_sender_id():
    with pytest.raises(ValidationError):
        VultronEvent(
            semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
            activity_id=ACTIVITY_ID,
            actor_id="   ",
        )


@pytest.mark.spec("OID-01-007")
@pytest.mark.spec("ARCH-22-001")
def test_addressing_re_exports_the_primitive_normaliser():
    """``core/predicates/addressing`` re-exports the one definition."""
    from vultron.core.predicates import addressing

    assert addressing.normalise_actor_id is normalise_actor_id
    assert addressing.same_actor_id is same_actor_id
