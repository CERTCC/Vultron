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

"""Hand core an activity, or seed a store with one, as if it had been received.

A received activity carries, as its received evidence, the body its sender
delivered (VM-08-002), and a received entry records that body verbatim
(CLP-07-011, ADR-0107).  :func:`received_event` gives a test's in-process
activity that evidence before extracting its event, so the code under test
sees what the inbox would hand it.

A received activity that reaches its use case is stored by intake, as a
``ReceivedActivityRecord`` under the receiver's key (CLP-10-017, ADR-0111).
A test that needs the receiver to *hold* a dispatched activity — an invitee
about to answer its Invite, for instance — seeds that record, so the code
under test reads it the way production does.
"""

import json
from typing import Any, TypeVar

from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.driving.fastapi.inbox_staging import (
    InlineObjectStaging,
)
from vultron.core.models.base import CoreObject
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.events import AnyReceivedEvent
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.semantic_registry import extract_event
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity


def delivered_body(activity: as_Activity) -> dict[str, Any]:
    """The JSON body a sender delivers for *activity*.

    Dumped as ``outbox_delivery`` dumps it.  ``serialize_as_any`` matters:
    without it a field typed as a parent class dumps only the parent's fields,
    so an inline ``CaseProposal`` loses the ``object``/``target`` a receiver
    requires and the body no longer parses.
    """
    return activity.model_dump(
        mode="json", by_alias=True, exclude_none=True, serialize_as_any=True
    )


def delivered(activity: as_Activity) -> as_Activity:
    """*activity* as its receiver's parser hands it on.

    A copy sealed with the body its sender delivers for it (VM-08-002), so the
    caller's object is left as it was.  An activity that already carries
    evidence (one ``parse_activity`` returned) is returned unchanged.
    """
    if activity.received_evidence_json is not None:
        return activity
    copy = activity.model_copy()
    copy.seal_received_evidence(
        json.dumps(delivered_body(activity), ensure_ascii=False)
    )
    return copy


def evidence_for(activity: CoreObject) -> str:
    """The received evidence a sender's delivery of core *activity* would carry.

    For a test that builds its event from a core ``VultronActivity`` rather
    than a wire activity: the body is the activity's AS2 rendering, so the
    received entry records what a sender would have sent.
    """
    return json.dumps(
        As2WireRenderAdapter().render(activity), ensure_ascii=False
    )


_Event = TypeVar("_Event", bound=VultronEvent)


def with_evidence(event: _Event) -> _Event:
    """*event*, carrying the evidence a delivery of its activity would carry.

    For a test that builds a received event from core objects: the inbox's
    events carry their received body (VM-08-002), which a received entry
    records verbatim (ADR-0107).
    """
    if event.activity is None:
        raise ValueError(f"{event!r} has no activity to give evidence for")
    return event.model_copy(
        update={"received_evidence": evidence_for(event.activity)}
    )


def received_event(activity: as_Activity, **update: Any) -> AnyReceivedEvent:
    """The event the inbox dispatches for *activity*, as delivered.

    *update* overrides event fields, as a test that sets
    ``receiving_actor_id`` needs.
    """
    event = extract_event(delivered(activity))
    return event.model_copy(update=update) if update else event


def archive_received(dl: Any, activity: Any) -> ReceivedActivityRecord:
    """Store *activity* in *dl* as intake archives a received activity.

    *activity* may be a wire activity, as a factory builds it: it is extracted
    to the event intake receives and the event's activity is archived, exactly
    the object intake stores.
    """
    received = extract_event(activity).activity
    if received is None:
        raise ValueError(f"{activity!r} extracts to an event with no activity")
    record = ReceivedActivityRecord.for_activity(received)
    dl.create(record)
    return record


def hold_deferred(dl: Any, activity: Any) -> DeferredInboxActivity:
    """Hold *activity* in *dl* as the inbox holds one it defers.

    An activity waiting on its case has not reached intake, so it has no
    ``ReceivedActivityRecord``; the inbox holds it whole in a
    ``DeferredInboxActivity`` under the receiver's key (DL-06-006,
    IO-03-004).  *activity* is delivered as a sender would send it: its body
    is parsed, staged and held through the inbox's own staging, beside the
    core summary its event carries.
    """
    body = activity.model_dump(mode="json", by_alias=True, exclude_none=True)
    parsed = parse_activity(body)
    staging = InlineObjectStaging(dl)
    staging.rehydrate_parsed(parsed)
    staging.hold_for_replay(parsed.id_, extract_event(parsed).activity)
    held = staging.held(parsed.id_)
    if held is None:
        raise AssertionError(f"{parsed.id_!r} was not held for replay")
    return held


def received_of_type(dl: CasePersistence, activity_type: str) -> list[Any]:
    """Every *activity_type* activity *dl* holds as received, as archived.

    A receiver keeps a received activity only in its ``ReceivedActivityRecord``
    (DL-06-006), so a per-type table scan never finds one.
    """
    return [
        record.activity
        for record in dl.list_objects(ReceivedActivityRecord.__name__)
        if isinstance(record, ReceivedActivityRecord)
        and record.activity.type_ == activity_type
    ]


def received_record(
    dl: CasePersistence, activity_id: str
) -> ReceivedActivityRecord | None:
    """The ``ReceivedActivityRecord`` *dl* holds for *activity_id*, if any.

    Looked up by the receiver's key, as production reads it
    (``ReceivedActivityRecord.build_id``).
    """
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    return record if isinstance(record, ReceivedActivityRecord) else None


def assert_held_only_as_received(
    dl: CasePersistence, activity_id: str
) -> None:
    """Assert *dl* holds *activity_id* as a received archive and nothing else.

    A receiver keeps a received activity only under a key it derives, never
    as a record readable by the id its sender chose (DL-06-006).
    """
    assert dl.read(activity_id) is None, (
        f"{activity_id!r} is held under the id its sender chose (DL-06-006)"
    )
    assert received_record(dl, activity_id) is not None, (
        f"{activity_id!r} has no ReceivedActivityRecord"
    )
