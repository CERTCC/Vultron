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

"""Move a received message into and out of holding (ADR-0154, IO-03-009).

One :class:`~vultron.core.models.received_activity_record.ReceivedActivityRecord`
holds a received message, and these are the only sanctioned writes to its
holding fields.  Every caller that holds a body for a replay, releases it, or
discards it goes through here, so the "a held body owes a replay" invariant
is kept in one place instead of at each of the waits (a case, a ledger
gap, an object fetch, a retry, and at the CASE_MANAGER a gap in a sender's
numbers).

The reads live in ``received_activity.py``, which stays read-only.

Two stages, one record
----------------------

A record the receiver has not archived is ``HELD`` and is deleted when its
replay releases it: nothing else would ever read it.  A record intake already
archived stays archived and only loses its :attr:`replay_owed` flag, because
the archive outlives the replay -- a buffered ``Announce(CaseLedgerEntry)``
is archived *and* awaiting its gap, and releasing it must not take the
archive with it (SYNC-14-009, CLP-10-018).
"""

import logging

from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import (
    held_received_record,
    sealed_body_of,
)
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


def owes_replay(dl: CasePersistence, activity_id: str) -> bool:
    """Whether a replay is still owed from the body held for *activity_id*."""
    record = held_received_record(dl, activity_id)
    return record is not None and record.replay_owed


def held_for_replay(
    dl: CasePersistence, activity_id: str
) -> ReceivedActivityRecord | None:
    """The record owing a replay for *activity_id*, if one does."""
    record = held_received_record(dl, activity_id)
    return record if record is not None and record.replay_owed else None


def hold_for_replay(
    dl: CasePersistence,
    activity_id: str,
    received_body: str,
    *,
    replay_rows_json: str = "[]",
    awaiting_case_id: str | None = None,
) -> bool:
    """Hold *activity_id*'s body until its replay; return whether this wrote.

    The **body** of a record already owing a replay is left as it is, so a
    redelivery of a held activity is not held again (IE-10-001) and the body
    first held is the body replayed.  A record intake archived takes the
    replay flag without losing its archive.  With neither, one ``HELD``
    record is created.

    A receipt stub, all an earlier refusal left (CLP-10-018), holds no body
    to replay, so a delivery that brings the body again replaces the stub
    with a ``HELD`` record for it, keeping the stub's time of receipt.  This
    is the same overwrite intake makes over a stub, and it lasts only while
    the doors follow intake: once the seen-before door runs first, a resend
    of a refused message is answered from its stub and never reaches a hold
    (#5045's third part).  The overwrite writes a whole new record rather
    than copying the stub, so the record's stage/body invariant is checked
    at construction.

    *awaiting_case_id* is recorded even on a record that already owed a
    replay, because the wait and the body are different facts: a body held
    for one wait (a retry, a fetch) and then deferred on its case must still
    become findable by that case, or nothing replays it and the message is
    lost silently.  Naming a case never drops one already named for a
    different case; that would be two waits on one record, which this
    refuses.

    Returns whether this call newly held a body.  A call that only recorded
    the case on an existing hold returns ``False``.

    Hold before you queue: the record is the receiver's only copy of the
    activity (DL-06-006), so an id queued with nothing held behind it is a
    lost message.

    Raises:
        VultronWiringError: *awaiting_case_id* names a case other than the
            one this record already waits on.
    """
    existing = held_received_record(dl, activity_id)
    if existing is None:
        dl.create(
            ReceivedActivityRecord(
                activity_id=activity_id,
                received_body=received_body,
                stage=ReceivedStage.HELD,
                replay_owed=True,
                awaiting_case_id=awaiting_case_id,
                replay_rows_json=replay_rows_json,
            )
        )
        return True
    if existing.is_receipt_stub:
        dl.save(
            ReceivedActivityRecord(
                activity_id=activity_id,
                received_body=received_body,
                stage=ReceivedStage.HELD,
                replay_owed=True,
                awaiting_case_id=awaiting_case_id,
                replay_rows_json=replay_rows_json,
                received_at=existing.received_at,
            )
        )
        logger.info(
            "Received activity %s was a receipt stub; its body is held again"
            " for a replay (CLP-10-018, IO-03-009).",
            activity_id,
        )
        return True
    if existing.replay_owed:
        logger.debug(
            "Received activity %s already owes a replay; keeping the held"
            " copy.",
            activity_id,
        )
        if awaiting_case_id is not None and (
            existing.awaiting_case_id != awaiting_case_id
        ):
            if existing.awaiting_case_id is not None:
                raise VultronWiringError(
                    f"received activity '{activity_id}' already waits on case"
                    f" '{existing.awaiting_case_id}', so it cannot also wait"
                    f" on '{awaiting_case_id}' (IO-03-009)"
                )
            dl.save(
                existing.model_copy(
                    update={"awaiting_case_id": awaiting_case_id}
                )
            )
        return False
    dl.save(
        existing.model_copy(
            update={
                "replay_owed": True,
                "awaiting_case_id": awaiting_case_id,
                "replay_rows_json": replay_rows_json,
            }
        )
    )
    return True


def hold_unjudged_for_replay(dl: CasePersistence, activity_id: str) -> None:
    """Hold an activity intake archived but the receiver has not judged yet.

    The CASE_MANAGER holds an activity that arrives past a gap in its
    sender's ``senderSequence`` before it judges it (SYNC-21-010), so the
    delivery has not been received into its records yet: the record goes
    back to ``HELD``, owing the replay that judges it as a delivery of its
    own (IO-03-009, ADR-0154).  When that replay releases it, intake
    archives it afresh, so the replay is judged as a first delivery, its
    refusal notice included (CLP-02-005).

    Raises:
        VultronWiringError: Nothing is archived for *activity_id* (intake
            runs before any guard, CLP-10-017), or it already owes a replay
            for another wait, which would make one record two waits.
    """
    record = held_received_record(dl, activity_id)
    if record is None:
        raise VultronWiringError(
            f"received activity '{activity_id}' is not archived, so there is"
            " no received body to hold for its replay (CLP-10-017,"
            " SYNC-21-010)"
        )
    if record.replay_owed:
        raise VultronWiringError(
            f"received activity '{activity_id}' already owes a replay, so it"
            " cannot also wait on its sender's number (IO-03-009)"
        )
    dl.save(
        ReceivedActivityRecord(
            activity_id=record.activity_id,
            # A receipt stub keeps no body, so there is none to hold.
            received_body=sealed_body_of(record),
            stage=ReceivedStage.HELD,
            replay_owed=True,
            received_at=record.received_at,
            replay_rows_json=record.replay_rows_json,
        )
    )


def release_from_holding(
    dl: CasePersistence, activity_id: str
) -> ReceivedActivityRecord | None:
    """Take *activity_id* out of holding; return the record as it was held.

    The caller has the body it needs from the returned record, so a caller
    that queues the activity again holds it again from that copy
    (:func:`hold_for_replay`).

    A record the receiver never archived is deleted: it existed only for this
    replay.  An archived one keeps its archive and only stops owing a replay
    (CLP-10-018).  ``None`` when nothing is held.
    """
    record = held_received_record(dl, activity_id)
    if record is None:
        return None
    if record.stage is ReceivedStage.HELD:
        dl.delete(record.type_, record.id_)
        return record
    dl.save(
        record.model_copy(
            update={"replay_owed": False, "awaiting_case_id": None}
        )
    )
    return record


def stop_awaiting_case(dl: CasePersistence, activity_id: str) -> None:
    """Note that *activity_id* no longer waits on a case, only on its replay.

    For the moment the case arrives and the activity goes onto the live inbox
    queue: the body stays held until the drain replays it, but it is no
    longer waiting on the case, so a second bootstrap for the same case does
    not queue it twice.
    """
    record = held_received_record(dl, activity_id)
    if record is None or record.awaiting_case_id is None:
        return
    dl.save(record.model_copy(update={"awaiting_case_id": None}))


def discard_holding(dl: CasePersistence, activity_id: str) -> None:
    """Drop what is held for *activity_id* without replaying it.

    For a wait that ends without routing the message: a bounded holding area
    evicting its farthest-ahead entry (SYNC-14-013), or a queue whose window
    expired (CBT-03-003).  An archived record keeps its archive
    (CLP-10-018); one never archived goes entirely.
    """
    record = held_received_record(dl, activity_id)
    if record is None:
        return
    if record.stage is ReceivedStage.HELD:
        dl.delete(record.type_, record.id_)
        return
    dl.save(
        record.model_copy(
            update={"replay_owed": False, "awaiting_case_id": None}
        )
    )


def records_awaiting_case(
    dl: CasePersistence, case_id: str
) -> list[ReceivedActivityRecord]:
    """Every record waiting on *case_id*, in the order they arrived.

    The replay order is the arrival order (:attr:`received_at`), which is
    what the retired ``VultronPendingCaseInbox.activity_ids`` list gave by
    being appended to.
    """
    waiting = [
        obj
        for obj in dl.list_objects(ReceivedActivityRecord.__name__)
        if isinstance(obj, ReceivedActivityRecord)
        and obj.replay_owed
        and obj.awaiting_case_id == case_id
    ]
    return sorted(waiting, key=lambda r: (r.received_at, r.activity_id))


__all__ = [
    "discard_holding",
    "held_for_replay",
    "hold_for_replay",
    "hold_unjudged_for_replay",
    "owes_replay",
    "records_awaiting_case",
    "release_from_holding",
    "stop_awaiting_case",
]
