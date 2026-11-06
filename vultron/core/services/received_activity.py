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

"""Read an activity as this actor holds it (CLP-10-017, DL-06-006, ADR-0149).

A received activity is held only under a key the receiver derives (DL-06-006),
and only as the body that arrived: one ``ReceivedActivityRecord``, whichever
stage it is in -- recorded by intake, archived once applied or skipped, or
held for a replay the inbox still owes (ADR-0154).  Core reads its facts by
loading that body through the ``ReceivedActivityLoader`` port, which parses
and extracts it as the inbox did and returns a read-only view.  That is the
one sanctioned way core reads a received activity's facts (DL-06-001,
DL-06-002).  An activity the actor sent is held under its own id.

:func:`holds_activity` answers only whether the actor holds an activity, from
the records' presence, and parses nothing.

These readers are importable from any core layer, BT nodes included
(BTND-04-003), and are re-exported by ``vultron.core.use_cases._helpers``.
"""

import json
from typing import Any

from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.received_activity_view import ReceivedActivityView
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.received_activity_loader import ReceivedActivityLoader
from vultron.errors import VultronNotFoundError, VultronWiringError


def held_received_record(
    dl: CasePersistence, activity_id: str
) -> ReceivedActivityRecord | None:
    """The receiver-keyed record holding the received *activity_id*, if any.

    One read of one row, whatever stage it is in: intake's record, the archive
    and a body held for a replay are the same record now (ADR-0154).  Never a row under
    the id the sender chose (DL-06-006).  Nothing is parsed.
    """
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    return record if isinstance(record, ReceivedActivityRecord) else None


def holds_received_activity(dl: CasePersistence, activity_id: str) -> bool:
    """Whether this actor holds the received activity *activity_id*.

    Read from the receiver's keys only (:func:`held_received_record`).
    """
    return held_received_record(dl, activity_id) is not None


def sealed_body_of(record: ReceivedActivityRecord) -> str:
    """The sealed received body *record* holds, as the parser sealed it.

    The one guard for every caller that already has a record and needs the
    body off it, so a receipt stub is refused in one place rather than at
    each of them (CS-22-001).

    Raises:
        VultronWiringError: *record* is a receipt stub, which gave the body
            up when the message was refused (CLP-10-018).  Every caller holds
            a record it archived or put in holding, so a stub there is a
            miswiring, not a sender's doing (ARCH-15-001).
    """
    if record.received_body is None:
        raise VultronWiringError(
            f"received activity '{record.activity_id}' is held only as a"
            f" receipt stub ({record.stage}), which keeps no body"
            " (CLP-10-018)"
        )
    return record.received_body


def held_received_body(
    dl: CasePersistence, activity_id: str
) -> dict[str, Any]:
    """The sealed body this receiver holds for *activity_id*, decoded.

    For a node in the run that hands the received activity to the reply seam
    unread, to be embedded as it arrived (DL-06-004, ADR-0149): the refusal
    notice.  Readers in the run read the holding record, whichever
    body-bearing stage it is in -- recorded by intake, or still held for a
    replay -- because the message is the same message either way
    (ADR-0154).

    Raises:
        VultronWiringError: When this receiver holds nothing for
            *activity_id*, or holds only a receipt stub, which gave the body
            up when the message was refused (CLP-10-018).  Either is a
            miswiring: these callers run inside the run, before the outcome
            stage, on a record intake holds (CLP-10-017).
    """
    record = held_received_record(dl, activity_id)
    if record is None:
        raise VultronWiringError(
            f"activity '{activity_id}' is not held by this receiver, so"
            " there is no received body to embed (CLP-10-017)"
        )
    body: dict[str, Any] = json.loads(sealed_body_of(record))
    return body


def holds_activity(dl: CasePersistence, activity_id: str) -> bool:
    """Whether this actor holds the activity *activity_id*, received or sent.

    A received activity under the receiver's keys
    (:func:`holds_received_activity`), else a record under the activity's own
    id, where an activity this actor sent is held.  Nothing is parsed.
    """
    return (
        holds_received_activity(dl, activity_id)
        or dl.read(activity_id) is not None
    )


def read_received_activity(
    loader: ReceivedActivityLoader,
    activity_id: str,
    resource_type: str = "Activity",
) -> ReceivedActivityView:
    """Return the read-only view of the received activity *activity_id*.

    One ``ReceivedActivityRecord`` under the receiver's own key holds the
    body, whichever stage it is in (ADR-0154): recorded by intake once the
    activity reached its use case (CLP-10-017) and archived once applied, or
    held for a replay while the inbox defers it until its case is known
    (IO-03-009).  A stub Invite is never in that last stage: it precedes its
    case by design, so the invitee processes it on arrival and intake records
    it (PCR-06-005).
    Nothing is read under the sender's id (DL-06-006).

    Either way the view is parsed from the held body on this call, so it is
    what the delivery saw, and it cannot be changed (ADR-0149).

    Args:
        loader: The port that loads the receiver's held bodies.
        activity_id: The sender's id for the activity.
        resource_type: Label for the error when nothing is held.

    Raises:
        VultronNotFoundError: When this actor holds no such activity.
    """
    received = loader.load_received_activity(activity_id)
    if received is None:
        raise VultronNotFoundError(resource_type, activity_id)
    return received


def read_held_activity(
    loader: ReceivedActivityLoader,
    dl: CasePersistence,
    activity_id: str,
    resource_type: str = "Activity",
) -> ReceivedActivityView | PersistableModel:
    """Return the activity *activity_id* as this actor holds it, either way.

    Some reads concern an activity this actor either received or sent, such
    as the actor's own ownership-transfer proposal.  A received activity is
    loaded as :func:`read_received_activity` loads it.  Anything else is read
    from *dl* under its own id: an activity this actor sent, the one record
    of an activity type a receiver keeps under the activity's id
    (DL-06-006).

    Args:
        loader: The port that loads the receiver's held bodies.
        dl: This actor's DataLayer.
        activity_id: The activity's id, as its author chose it.
        resource_type: Label for the error when nothing is held.

    Raises:
        VultronNotFoundError: When this actor holds no such activity.
    """
    received = loader.load_received_activity(activity_id)
    if received is not None:
        return received
    held = dl.read(activity_id)
    if held is None:
        raise VultronNotFoundError(resource_type, activity_id)
    return held


__all__ = [
    "held_received_body",
    "held_received_record",
    "holds_activity",
    "holds_received_activity",
    "read_held_activity",
    "read_received_activity",
    "sealed_body_of",
]
