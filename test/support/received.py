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
(SYNC-18-015).  A test that builds an activity with a wire factory has no
sender store, so :func:`delivered` stamps an activity that states none, as
the sender's adapter would have stamped its tail: in step with the
receiver's ledger when the test passes the receiver's store (``at=``), else
:data:`TEST_SENDER_POSITION`.  A CASE_MANAGER answers a position its ledger
does not hold as a split chain and re-seeds the sender (SYNC-18-012), so a
test that delivers to one passes ``at=``.  An activity whose object states
its own position is left alone, and a test that delivers an unstamped
activity on purpose builds its body itself.

A participant also numbers each case activity it sends the CASE_MANAGER
(``senderSequence``, SYNC-21-001), and the CASE_MANAGER refuses one that
carries no number (SYNC-21-017).  A test that passes the receiver's store
(``at=``) has its activity numbered in step with it: the number the
CASE_MANAGER expects next from the sender, so it is judged on arrival.  One
that names no receiver store, and an event a test builds by hand
(:func:`with_evidence`), is numbered as its sender's adapter would number
it: in the order the test builds them, one up per sender and case
(:func:`test_sender_number`).
"""

import json
from typing import Any, TypeVar, cast

from vultron.adapters.driven.ledger_position_stamp import (
    with_sender_ledger_position,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.adapters.received_archive import (
    load_received_view,
    read_received_as_received,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.base import CoreObject
from vultron.core.models.events import AnyReceivedEvent
from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    VultronEvent,
)
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.received_activity_view import ReceivedActivityView
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.participants.role_predicate import has_role
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import sealed_body_of
from vultron.core.services.received_outcome import (
    archive_applied,
    write_receipt_stub,
)
from vultron.core.services.sender_sequence_order import sender_sequence_order
from vultron.core.sync_helpers import (
    first_case_with_ledger,
    ledger_tail_position,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    object_states_its_own_position,
    sender_sequence_case_ids,
    stamp_ledger_position,
    stamp_sender_sequence,
)
from vultron.wire.as2.parser import parse_activity, parse_received_body
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseStub,
)

#: The ledger position a test's in-process sender states when the test names
#: no receiver store (SYNC-18-001): an empty ledger with no real genesis
#: hash.  A receiver that is not the case's CASE_MANAGER judges nothing by
#: it; a CASE_MANAGER reads it as a split chain (SYNC-18-005), so a test
#: delivering to one stamps in step with it instead (:func:`stamped`).
TEST_SENDER_POSITION = LedgerPosition(
    log_index=EMPTY_LEDGER_LOG_INDEX, entry_hash="0" * 64
)


#: The number each in-process sender of the running test gave each activity,
#: and the last number it used per case, so a hand-built activity is numbered
#: as its sender's adapter numbers it: in the order the test builds them, one
#: up per case, and a rebuild of the same activity keeps its number
#: (SYNC-21-002, SYNC-21-003).  Cleared before each test
#: (``reset_test_sender_numbers``, from ``test/conftest.py``).
_NUMBERED: dict[str, int] = {}
_LAST_USED: dict[tuple[str, str], int] = {}


def reset_test_sender_numbers() -> None:
    """Forget every number a test's in-process senders used."""
    _NUMBERED.clear()
    _LAST_USED.clear()


def test_sender_number(sender_id: str, case_id: str, activity_id: str) -> int:
    """The ``senderSequence`` a test's in-process sender gives *activity_id*.

    One more than the last number it used on *case_id* in this test, and the
    same number again for an activity it already numbered.
    """
    if activity_id in _NUMBERED:
        return _NUMBERED[activity_id]
    key = (sender_id, case_id)
    number = _LAST_USED.get(key, 0) + 1
    _LAST_USED[key] = number
    _NUMBERED[activity_id] = number
    return number


def in_step_position(dl: CasePersistence, case_id: str) -> LedgerPosition:
    """The ``ledgerPosition`` of a sender in step with *dl*'s ledger.

    For a test that builds a received event by hand: the receiver's own tail
    for *case_id*, which a CASE_MANAGER holds, so it reads no split
    (SYNC-18-005) and replays nothing (SYNC-18-007).
    """
    return ledger_tail_position(case_id, dl)


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


def stamped(
    activity: as_Activity, *, at: CasePersistence | None = None
) -> as_Activity:
    """*activity* stating its sender's position, if it states none.

    With *at*, the receiver's store, the sender is in step with the
    receiver: the stamp is the tail of the case the activity names in that
    store, as ``with_sender_ledger_position`` reads it from a sender's own
    store (SYNC-18-001).  The CASE_MANAGER answers a position it does not
    hold as a split chain, re-seeding the sender (SYNC-18-012), so a test
    that delivers to a CASE_MANAGER passes its store.  Without *at*, or when
    *at* holds no ledger for any case the activity names, the stamp is
    :data:`TEST_SENDER_POSITION`.  An activity whose object states its own
    position (a ledger entry's or a case copy's ``Announce``) is returned
    unchanged, as is one already stamped.

    An activity this stamps with a position is also numbered, when it is one
    its sender numbers (SYNC-21-001): with *at*, in step with the receiver
    when the receiver is the case's CASE_MANAGER
    (:func:`in_step_sender_sequence`), and otherwise as the test's
    in-process sender numbers it (:func:`test_sender_number`).  An activity
    a test built already stating a position (a full-case Invite reply states
    the replier's, CM-11-034) is numbered too when *at* is given and it
    carries no number: its sender's adapter numbers whatever position it
    states (SYNC-21-001).  Without *at* it is left as it is, as a sealed body
    carries the number its sender gave it, or none.
    """
    if object_states_its_own_position(activity):
        return activity
    if activity.ledger_position is not None:
        if at is None or activity.sender_sequence is not None:
            return activity
        number = in_step_sender_sequence(at, activity)
        if number is None:
            return activity
        return stamp_sender_sequence(activity, number)
    positioned = _positioned(activity, at=at)
    if positioned.sender_sequence is not None:
        return positioned
    number = (
        in_step_sender_sequence(at, positioned)
        if at is not None
        else _numbered_by_its_sender(positioned)
    )
    if number is None:
        return positioned
    return stamp_sender_sequence(positioned, number)


def _numbered_by_its_sender(activity: as_Activity) -> int | None:
    """The number a test's in-process sender gives *activity*, if it takes one.

    For a test that names no receiver store: the activity is numbered as its
    sender would number it (:func:`test_sender_number`).  ``None`` for an
    activity that takes no number (SYNC-21-001).
    """
    case_ids = list(sender_sequence_case_ids(activity))
    sender = _as_id(activity.actor)
    if not case_ids or sender is None or not activity.id_:
        return None
    return test_sender_number(sender, case_ids[0], activity.id_)


def _positioned(
    activity: as_Activity, *, at: CasePersistence | None
) -> as_Activity:
    """*activity* stating its sender's ledger position (:func:`stamped`)."""
    if activity.ledger_position is not None or object_states_its_own_position(
        activity
    ):
        return activity
    if at is not None:
        in_step = with_sender_ledger_position(at, activity)
        if in_step.ledger_position is not None:
            return in_step
    return stamp_ledger_position(activity, TEST_SENDER_POSITION)


def in_step_sender_sequence(
    dl: CasePersistence, activity: as_Activity
) -> int | None:
    """The ``senderSequence`` of a sender in step with the CASE_MANAGER *dl*.

    For a test whose sender keeps no store: the number the CASE_MANAGER
    expects next from the activity's sender, so the activity is judged on
    arrival (SYNC-21-008).  ``None`` when the activity takes no number
    (:func:`~vultron.wire.as2.factories.sender_sequence_case_ids`), names no
    case *dl* holds a ledger for, or *dl* is not that case's CASE_MANAGER,
    or the sender is.
    """
    case_id = first_case_with_ledger(
        list(sender_sequence_case_ids(activity)), dl
    )
    sender = _as_id(activity.actor)
    receiver = getattr(dl, "actor_id", None)
    if case_id is None or sender is None or receiver is None:
        return None
    if not has_role(receiver, case_id, CVDRole.CASE_MANAGER, dl):
        return None
    if has_role(sender, case_id, CVDRole.CASE_MANAGER, dl):
        return None
    return sender_sequence_order(dl, case_id, sender).next_expected


def delivered_body(
    activity: as_Activity, *, at: CasePersistence | None = None
) -> dict[str, Any]:
    """The JSON body a sender delivers for *activity*.

    Stamped as its sender's adapter stamps it (:func:`stamped`), and dumped
    as ``outbox_delivery`` dumps it.  ``serialize_as_any`` matters:
    without it a field typed as a parent class dumps only the parent's fields,
    so an inline ``CaseProposal`` loses the ``object``/``target`` a receiver
    requires and the body no longer parses.
    """
    return stamped(activity, at=at).model_dump(
        mode="json", by_alias=True, exclude_none=True, serialize_as_any=True
    )


def delivered(
    activity: as_Activity,
    *,
    as_sent: bool = False,
    at: CasePersistence | None = None,
) -> as_Activity:
    """*activity* as its receiver's parser hands it on.

    A copy sealed with the body its sender delivers for it (VM-08-002), so the
    caller's object is left as it was.  An activity that already carries
    evidence (one ``parse_activity`` returned) is returned unchanged when it
    states a ledger position, or *as_sent* is set; otherwise its body is
    parsed again with the position :func:`stamped` gives it, as a sender's
    adapter would have stamped it (SYNC-18-001).  *at* is the receiver's
    store (:func:`stamped`).
    """
    evidence = activity.received_evidence
    if evidence is not None:
        stamp = stamped(activity, at=at)
        if as_sent or stamp is activity:
            return activity
        assert stamp.ledger_position is not None
        stamps: dict[str, Any] = {
            "ledgerPosition": stamp.ledger_position.model_dump(by_alias=True)
        }
        # A body that states a number keeps it, even one the parse set
        # aside as malformed (SYNC-21-017).
        if (
            stamp.sender_sequence is not None
            and "senderSequence" not in evidence
        ):
            stamps["senderSequence"] = stamp.sender_sequence
        return parse_activity({**evidence, **stamps})
    copy = stamped(activity, at=at).model_copy()
    copy.seal_received_evidence(
        json.dumps(delivered_body(activity, at=at), ensure_ascii=False)
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
    event = _numbered_event(event)
    return event.model_copy(
        update={"received_evidence": evidence_for(_as_delivered(event))}
    )


def _numbered_event(event: _Event) -> _Event:
    """*event* whose activity carries the number its sender would give it.

    A case activity that states its sender's ledger position is numbered by
    its sender (SYNC-21-001), so a hand-built one is numbered as the test's
    in-process sender numbers it (:func:`test_sender_number`), unless it
    carries a number already.
    """
    activity = event.activity
    if (
        not isinstance(event, LedgerPositionedEvent)
        or activity is None
        or getattr(activity, "sender_sequence", None) is not None
    ):
        return event
    case_id = getattr(event, "case_id", None) or _as_id(
        getattr(activity, "context", None)
    )
    if not case_id:
        return event
    number = test_sender_number(event.actor_id, case_id, event.activity_id)
    return event.model_copy(
        update={
            "activity": activity.model_copy(update={"sender_sequence": number})
        }
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


def extract_stamped(
    activity: as_Activity,
    *,
    at: CasePersistence | None = None,
    **kwargs: Any,
) -> AnyReceivedEvent:
    """``extract_event`` of *activity* as its sender stamps it (:func:`stamped`).

    For a test that extracts a factory-built activity directly, without the
    received evidence :func:`received_event` gives it.  *at* is the
    receiver's store (:func:`stamped`).
    """
    return extract_event(stamped(activity, at=at), **kwargs)


def received_event(
    activity: as_Activity,
    *,
    as_sent: bool = False,
    at: CasePersistence | None = None,
    **update: Any,
) -> AnyReceivedEvent:
    """The event the inbox dispatches for *activity*, as delivered.

    *update* overrides event fields, as a test that sets
    ``receiving_actor_id`` needs.  *as_sent* hands over a parsed activity
    exactly as it arrived, unstamped, and *at* is the receiver's store, so
    the sender is stamped in step with it (:func:`delivered`).
    """
    event = extract_event(delivered(activity, as_sent=as_sent, at=at))
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
    """Store *activity* in *dl* as the archive of an applied message.

    The outcome stage archives the body an applied or skipped message
    arrived with (CLP-10-073, ADR-0149), so the record holds the body a
    sender's delivery of *activity* carries.  A resend of it is skipped at
    the seen-before door (ADR-0154).
    """
    record = ReceivedActivityRecord(
        activity_id=activity.id_, received_body=body_of(activity)
    )
    dl.create(record)
    return record


def settle_as_the_inbox(dl: Any, event: Any, result: Any) -> None:
    """Record *result*'s outcome on *event*'s record, as the inbox does.

    For a test that runs a use case directly, without the inbox's outcome
    stage around it, and then delivers the activity again: the outcome stage
    archives an applied or skipped message and leaves a receipt stub for a
    refused one (CLP-10-073, CLP-10-018), and the seen-before door answers
    the resend from that record (ADR-0154).  A deferred message is left in
    holding.  Mirrors ``SettleReceivedOutcome``.
    """
    disposition = result.disposition
    if disposition in (HandlerDisposition.APPLIED, HandlerDisposition.SKIPPED):
        archive_applied(dl, event.activity_id)
    elif disposition is HandlerDisposition.REFUSED:
        write_receipt_stub(
            dl,
            event.activity_id,
            sender_id=event.actor_id,
            reason=result.reason or "refused",
            received_body=event.received_evidence,
        )


def intake_received(dl: Any, activity: Any) -> ReceivedActivityRecord:
    """Store *activity* in *dl* as intake records it, before its outcome.

    Intake writes the body that arrived as a ``HELD`` record owing no
    replay (CLP-10-017); the outcome stage then archives it or reduces it
    to a receipt stub (CLP-10-073).
    """
    record = ReceivedActivityRecord(
        activity_id=activity.id_,
        received_body=body_of(activity),
        stage=ReceivedStage.HELD,
        replay_owed=False,
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


def hold_deferred(
    dl: Any, activity: Any, *, awaiting_case_id: str | None = None
) -> ReceivedActivityRecord:
    """Hold *activity* in *dl* as the inbox holds one it defers.

    An activity waiting on its case has not reached intake, so its one
    ``ReceivedActivityRecord`` is in the ``HELD`` stage and owes a replay,
    under the receiver's key (DL-06-006, IO-03-009, ADR-0154).  *activity* is
    delivered as a sender would send it: its body is parsed, staged and held
    through the inbox's own staging.  *awaiting_case_id* names the case it
    waits on, when the test needs the wait to be findable by case.
    """
    parsed = parse_activity(delivered_body(activity))
    staging = InlineObjectStaging(dl)
    staging.rehydrate_parsed(parsed)
    staging.hold_for_replay(parsed.id_, awaiting_case_id=awaiting_case_id)
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


def received_activities(dl: CasePersistence) -> list[Any]:
    """Every activity *dl* holds as received, whatever its type.

    A receiver keeps a received activity only in its ``ReceivedActivityRecord``
    (DL-06-006), so a per-type table scan never finds one.  Each is parsed
    from the body the record holds.

    Use this when the question is about the whole delivered set — "did anything
    arrive naming *this* actor as its sender" — rather than about one type.
    """
    return [
        parse_received_body(sealed_body_of(record))
        for record in dl.list_objects(ReceivedActivityRecord.__name__)
        if isinstance(record, ReceivedActivityRecord)
        and _received_into_records(record)
    ]


def _received_into_records(record: ReceivedActivityRecord) -> bool:
    """Whether *record* holds a message its doors admitted.

    One record holds a message at every stage (ADR-0154), so the table also
    holds a body the inbox is still holding for a replay, which has not been
    received into this actor's records yet, and a receipt stub, which holds
    no message.  An archive counts, and so does a record intake wrote that a
    test read before any outcome stage ran (a use case run directly).
    """
    if record.stage is ReceivedStage.ARCHIVED:
        return True
    return record.stage is ReceivedStage.HELD and not record.replay_owed


def received_of_type(dl: CasePersistence, activity_type: str) -> list[Any]:
    """Every *activity_type* activity *dl* holds as received, as received."""
    return [
        activity
        for activity in received_activities(dl)
        if activity.type_ == activity_type
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
    """Assert *dl* holds *activity_id* as received and nothing else.

    A receiver keeps a received activity only under a key it derives, never
    as a record readable by the id its sender chose (DL-06-006).  It is
    archived, or recorded by intake and not yet at its outcome when the use
    case ran with no inbox around it (CLP-10-017).
    """
    assert dl.read(activity_id) is None, (
        f"{activity_id!r} is held under the id its sender chose (DL-06-006)"
    )
    record = received_record(dl, activity_id)
    assert record is not None, f"{activity_id!r} has no ReceivedActivityRecord"
    assert _received_into_records(record), (
        f"{activity_id!r} is held but not received: {record.stage}"
    )
