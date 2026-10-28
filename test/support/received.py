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
``ReceivedActivityRecord`` of the body that arrived, under the receiver's key
(CLP-10-017, ADR-0111, ADR-0149).
A test that needs the receiver to *hold* a dispatched activity — an invitee
about to answer its Invite, for instance — seeds that record, so the code
under test reads it the way production does.

A sender's adapter stamps each case activity with its ledger tail
(SYNC-18-001), and the parse edge refuses a case activity without one
(SYNC-18-003).  A test that builds an activity with a wire factory has no
sender store, so :func:`delivered` stamps :data:`TEST_SENDER_POSITION` on an
activity that states none, as the sender's adapter would have stamped its
tail.  An activity whose object states its own position is left alone, and a
test that delivers an unstamped activity on purpose builds its body itself.
"""

import json
from typing import Any, TypeVar, cast

from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.adapters.received_archive import (
    load_received_view,
    read_received_as_received,
)
from vultron.core.models.base import CoreObject
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.events import AnyReceivedEvent
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.received_activity_view import ReceivedActivityView
from vultron.core.ports.case_persistence import CasePersistence
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    object_states_its_own_position,
    stamp_ledger_position,
)
from vultron.wire.as2.parser import parse_activity, parse_received_body
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseStub,
)

#: The ledger position a test's in-process sender states (SYNC-18-001): an
#: empty ledger.  The receiver records a stamp and judges no act by it, so
#: any well-formed position stands in for the sender's tail.
TEST_SENDER_POSITION = LedgerPosition(
    log_index=EMPTY_LEDGER_LOG_INDEX, entry_hash="0" * 64
)


def peer_position(
    last_accepted_hash: str, log_index: int = 0
) -> LedgerPosition | None:
    """The ``ledgerPosition`` of a peer whose last accepted entry is the hash.

    For a ``Reject(CaseLedgerEntry)`` a test builds (SYNC-03-002,
    SYNC-18-001).  ``None`` for an empty hash: a peer that holds no case
    states no position.
    """
    if not last_accepted_hash:
        return None
    return LedgerPosition(log_index=log_index, entry_hash=last_accepted_hash)


def stamped(activity: as_Activity) -> as_Activity:
    """*activity* stating :data:`TEST_SENDER_POSITION`, if it states none.

    An activity whose object states its own position (a ledger entry's or a
    case copy's ``Announce``) is returned unchanged, as is one already
    stamped (SYNC-18-001).
    """
    if activity.ledger_position is not None or object_states_its_own_position(
        activity
    ):
        return activity
    return stamp_ledger_position(activity, TEST_SENDER_POSITION)


def delivered_body(activity: as_Activity) -> dict[str, Any]:
    """The JSON body a sender delivers for *activity*.

    Stamped as its sender's adapter stamps it (:func:`stamped`), and dumped
    as ``outbox_delivery`` dumps it.  ``serialize_as_any`` matters:
    without it a field typed as a parent class dumps only the parent's fields,
    so an inline ``CaseProposal`` loses the ``object``/``target`` a receiver
    requires and the body no longer parses.
    """
    return stamped(activity).model_dump(
        mode="json", by_alias=True, exclude_none=True, serialize_as_any=True
    )


def delivered(activity: as_Activity, *, as_sent: bool = False) -> as_Activity:
    """*activity* as its receiver's parser hands it on.

    A copy sealed with the body its sender delivers for it (VM-08-002), so the
    caller's object is left as it was.  An activity that already carries
    evidence (one ``parse_activity`` returned) is returned unchanged when it
    states a ledger position, or *as_sent* is set; otherwise its body is
    parsed again with :data:`TEST_SENDER_POSITION` added, as a sender's
    adapter would have stamped it (SYNC-18-001).
    """
    evidence = activity.received_evidence
    if evidence is not None:
        if as_sent or stamped(activity) is activity:
            return activity
        return parse_activity(
            {
                **evidence,
                "ledgerPosition": TEST_SENDER_POSITION.model_dump(
                    by_alias=True
                ),
            }
        )
    copy = stamped(activity).model_copy()
    copy.seal_received_evidence(
        json.dumps(delivered_body(activity), ensure_ascii=False)
    )
    return copy


def evidence_for(activity: CoreObject) -> str:
    """The received evidence a sender's delivery of core *activity* would carry.

    For a test that builds its event from a core ``VultronActivity`` rather
    than a wire activity: the body is the activity's AS2 rendering, so the
    received entry records what a sender would have sent, stamped with
    :data:`TEST_SENDER_POSITION` when it states no position.
    """
    if getattr(
        activity, "ledger_position", "absent"
    ) is None and not object_states_its_own_position(
        cast(as_Activity, activity)
    ):
        activity = activity.model_copy(
            update={"ledger_position": TEST_SENDER_POSITION}
        )
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
        update={"received_evidence": evidence_for(_as_delivered(event))}
    )


def _as_delivered(event: VultronEvent) -> CoreObject:
    """*event*'s activity with the objects a sender would have inlined.

    A test that builds an event by hand often names the activity's object
    and target on the event alone.  The body a sender delivers carries them
    on the activity, so a reader that loads the archived body finds them
    there too.
    """
    assert event.activity is not None
    update = {
        field: getattr(event, field)
        for field in ("object_", "target")
        if getattr(event.activity, field, None) is None
        and getattr(event, field, None) is not None
    }
    return (
        event.activity.model_copy(update=update) if update else event.activity
    )


def extract_stamped(activity: as_Activity, **kwargs: Any) -> AnyReceivedEvent:
    """``extract_event`` of *activity* as its sender stamps it (:func:`stamped`).

    For a test that extracts a factory-built activity directly, without the
    received evidence :func:`received_event` gives it.
    """
    return extract_event(stamped(activity), **kwargs)


def received_event(
    activity: as_Activity, *, as_sent: bool = False, **update: Any
) -> AnyReceivedEvent:
    """The event the inbox dispatches for *activity*, as delivered.

    *update* overrides event fields, as a test that sets
    ``receiving_actor_id`` needs.  *as_sent* hands over a parsed activity
    exactly as it arrived, unstamped (:func:`delivered`).
    """
    event = extract_event(delivered(activity, as_sent=as_sent))
    return event.model_copy(update=update) if update else event


def case_stub(case_id: str) -> as_VulnerabilityCaseStub:
    """The case stub a deliverable stub Invite for *case_id* carries.

    A receiver refuses a stub with no ``summary`` at parse (MV-10-001), and
    every received body is parsed again when it is loaded (ADR-0149), so a
    test that delivers a stub Invite gives its stub one.
    """
    return as_VulnerabilityCaseStub(case_id=case_id, summary="A case to join")


def body_of(activity: Any) -> str:
    """The received evidence a sender's delivery of *activity* would carry.

    A wire activity is dumped as a sender delivers it and sealed by the parser
    (VM-08-002); a core activity is rendered as its AS2 form
    (:func:`evidence_for`).
    """
    if isinstance(activity, as_Activity):
        evidence = parse_activity(
            delivered_body(activity)
        ).received_evidence_json
        assert evidence is not None
        return evidence
    return evidence_for(activity)


def archive_received(dl: Any, activity: Any) -> ReceivedActivityRecord:
    """Store *activity* in *dl* as intake archives a received activity.

    Intake archives the body that arrived (CLP-10-017, ADR-0149), so the
    record holds the body a sender's delivery of *activity* carries.
    """
    record = ReceivedActivityRecord(
        activity_id=activity.id_, received_body=body_of(activity)
    )
    dl.create(record)
    return record


def archive_delivered(
    dl: Any, body: str | dict[str, Any]
) -> ReceivedActivityRecord:
    """Archive in *dl* the activity a sender delivered as *body*.

    For a test that holds the outbound body a peer sealed: it is parsed as
    the receiver's inbox parses it, and the sealed evidence is archived.
    """
    parsed = parse_activity(
        json.loads(body) if isinstance(body, str) else body
    )
    evidence = parsed.received_evidence_json
    assert evidence is not None
    record = ReceivedActivityRecord(
        activity_id=parsed.id_, received_body=evidence
    )
    dl.create(record)
    return record


def hold_deferred(dl: Any, activity: Any) -> DeferredInboxActivity:
    """Hold *activity* in *dl* as the inbox holds one it defers.

    An activity waiting on its case has not reached intake, so it has no
    ``ReceivedActivityRecord``; the inbox holds it whole in a
    ``DeferredInboxActivity`` under the receiver's key (DL-06-006,
    IO-03-004).  *activity* is delivered as a sender would send it: its body
    is parsed, staged and held through the inbox's own staging.
    """
    parsed = parse_activity(delivered_body(activity))
    staging = InlineObjectStaging(dl)
    staging.rehydrate_parsed(parsed)
    staging.hold_for_replay(parsed.id_)
    held = staging.held(parsed.id_)
    if held is None:
        raise AssertionError(f"{parsed.id_!r} was not held for replay")
    return held


def received_view(dl: Any, activity_id: str) -> ReceivedActivityView:
    """Core's read-only view of the received *activity_id* in *dl*.

    Loaded as production loads it (ADR-0149); fails when nothing is held.
    """
    view = load_received_view(dl, activity_id)
    assert view is not None, f"{activity_id!r} is not held as received"
    return view


def received_activity(dl: Any, activity_id: str) -> Any:
    """The received *activity_id* in *dl*, parsed from its archived body."""
    return read_received_as_received(dl, activity_id)


def received_of_type(dl: CasePersistence, activity_type: str) -> list[Any]:
    """Every *activity_type* activity *dl* holds as received, as received.

    A receiver keeps a received activity only in its ``ReceivedActivityRecord``
    (DL-06-006), so a per-type table scan never finds one.  Each is parsed
    from the body the record holds.
    """
    parsed = (
        parse_received_body(record.received_body)
        for record in dl.list_objects(ReceivedActivityRecord.__name__)
        if isinstance(record, ReceivedActivityRecord)
    )
    return [activity for activity in parsed if activity.type_ == activity_type]


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
