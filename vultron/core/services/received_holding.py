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

Holding, and leaving it
-----------------------

Every wait holds a ``HELD`` record (ADR-0154): a delivery deferred before the
doors, and one the handling tree held after intake recorded it (a buffered
``Announce(CaseLedgerEntry)`` waiting for its gap, SYNC-14-001).  Neither has
been archived, so releasing it for its replay deletes it and hands its body
to the replay, which routes it as a delivery of its own: its doors find no
record, and its intake records it again (IO-03-009).  Discarding a wait that
ends without routing the message (an eviction, an expired queue) deletes it
too: the message is dropped, body and all, as SYNC-14-013 and CBT-03-003
decide.

A message the receiver already answered is never held again: an archived
message was applied, and a receipt stub gave its body up (CLP-10-018), so
:func:`hold_for_replay` writes nothing for either and the seen-before door
answers the delivery instead.
"""

import logging
from collections.abc import Sequence

from vultron.core.models.received_activity_record import (
    HOLDING_STAGES,
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.verified_proof import VerifiedProof
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
    verified_proofs: Sequence[VerifiedProof] = (),
) -> bool:
    """Hold *activity_id*'s body until its replay; return whether this wrote.

    A record created here keeps *verified_proofs*, the proofs the inbox
    verified on that body, in its first save (SIG-03-004); a record that is
    already there keeps the ones it has.

    The **body** of a record already owing a replay is left as it is, so a
    redelivery of a held activity is not held again (IE-10-001) and the body
    first held is the body replayed.  A record intake recorded, ``HELD`` or
    ``HANDLED``, becomes ``HELD`` and takes the replay flag with the body it
    already holds.  With no record,
    one ``HELD`` record is created.

    A record that is already at its outcome is not held: an ``ARCHIVED``
    message was applied, and a receipt stub holds no body to replay
    (CLP-10-018).  Neither is written, so the stub keeps the first refusal's
    reason (CLP-10-077), and ``False`` is returned.

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
                verified_proofs=list(verified_proofs),
            )
        )
        return True
    if existing.stage not in HOLDING_STAGES:
        logger.info(
            "Received activity %s is already %s, so it is not held for a"
            " replay; its seen-before door answers it (ADR-0154).",
            activity_id,
            existing.stage,
        )
        return False
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
                # A message that waits is HELD, whichever run held it
                # (ADR-0154): HANDLED never owes a replay.
                "stage": ReceivedStage.HELD,
                "replay_owed": True,
                "awaiting_case_id": awaiting_case_id,
                "replay_rows_json": replay_rows_json,
            }
        )
    )
    return True


def hold_unjudged_for_replay(dl: CasePersistence, activity_id: str) -> None:
    """Hold an activity intake recorded but the receiver has not judged yet.

    The CASE_MANAGER holds an activity that arrives past a gap in its
    sender's ``senderSequence`` before it judges it (SYNC-21-010), so the
    delivery has not been received into its records yet: the record goes
    back to ``HELD``, owing the replay that judges it as a delivery of its
    own (IO-03-009, ADR-0154).  When that replay releases it, intake
    records it afresh, so the replay is judged as a first delivery, its
    refusal notice included (CLP-02-005).

    Raises:
        VultronWiringError: Nothing is recorded for *activity_id* (intake
            runs before any precondition guard, CLP-10-017), or it already
            owes a replay
            for another wait, which would make one record two waits.
    """
    record = held_received_record(dl, activity_id)
    if record is None:
        raise VultronWiringError(
            f"received activity '{activity_id}' is not recorded, so there is"
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
            verified_proofs=record.verified_proofs,
        )
    )


def release_from_holding(
    dl: CasePersistence, activity_id: str
) -> ReceivedActivityRecord | None:
    """Take *activity_id* out of holding; return the record as it was held.

    The caller has the body it needs from the returned record, so a caller
    that queues the activity again holds it again from that copy
    (:func:`hold_for_replay`).

    The record was never archived -- a message owed a replay has not reached
    its outcome (ADR-0154) -- so it is deleted: it existed only for this
    replay, which routes the body as a delivery of its own (IO-03-009).
    ``None`` when no replay is owed.
    """
    record = held_for_replay(dl, activity_id)
    if record is None:
        return None
    dl.delete(record.type_, record.id_)
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
    expired (CBT-03-003).  The message is dropped, so its record in holding
    (``HELD`` or ``HANDLED``) goes entirely.  A record already at its
    outcome (an archive, a receipt stub) is not a wait and is left as it is.
    """
    record = held_received_record(dl, activity_id)
    if record is None or record.stage not in HOLDING_STAGES:
        return
    dl.delete(record.type_, record.id_)


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


def records_left_in_holding(
    dl: CasePersistence,
) -> list[ReceivedActivityRecord]:
    """Every record a run left in holding with no verdict, oldest first.

    A record in holding that owes no replay is one intake wrote whose run
    did not reach its outcome: it raised, or the process stopped mid-run
    (CLP-10-074).  Read at startup, when no run is in progress, each is the
    message a crash left to be run again (ADR-0154).  A record waiting for a
    replay is not one of them: its wait ends it.
    """
    left = [
        obj
        for obj in dl.list_objects(ReceivedActivityRecord.__name__)
        if isinstance(obj, ReceivedActivityRecord)
        and obj.stage in HOLDING_STAGES
        and not obj.replay_owed
    ]
    return sorted(left, key=lambda r: (r.received_at, r.activity_id))


__all__ = [
    "discard_holding",
    "held_for_replay",
    "hold_for_replay",
    "hold_unjudged_for_replay",
    "owes_replay",
    "records_awaiting_case",
    "records_left_in_holding",
    "release_from_holding",
    "stop_awaiting_case",
]
