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
and only as the body that arrived: its ``ReceivedActivityRecord`` once intake
archived it, or, while the inbox defers it until its case is known, the
``DeferredInboxActivity`` that holds it for replay.  Core reads its facts by
loading that body through the ``ReceivedActivityLoader`` port, which parses
and extracts it as the inbox did and returns a read-only view.  That is the
one sanctioned way core reads a received activity's facts (DL-06-001,
DL-06-002).  An activity the actor sent is held under its own id.

:func:`holds_activity` answers only whether the actor holds an activity, from
the records' presence, and parses nothing.

These readers are importable from any core layer, BT nodes included
(BTND-04-003), and are re-exported by ``vultron.core.use_cases._helpers``.
"""

from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.received_activity_view import ReceivedActivityView
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.received_activity_loader import ReceivedActivityLoader
from vultron.errors import VultronNotFoundError


def holds_received_activity(dl: CasePersistence, activity_id: str) -> bool:
    """Whether this actor holds the received activity *activity_id*.

    Read from the receiver's keys only (DL-06-006): intake's archive, or the
    record holding a deferred activity for its replay.  Nothing is parsed.
    """
    return any(
        dl.read(record_id) is not None
        for record_id in (
            ReceivedActivityRecord.build_id(activity_id),
            DeferredInboxActivity.build_id(activity_id),
        )
    )


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

    A received activity that reached its use case is archived by intake as a
    ``ReceivedActivityRecord`` under the receiver's own key (CLP-10-017,
    ADR-0111), so that record is loaded first.

    An activity the inbox deferred until its case is known has not reached
    intake yet.  The inbox holds its body for replay in a
    ``DeferredInboxActivity``, also under a key the receiver derives
    (DL-06-006), and that body is loaded next.  A stub Invite is never in that
    state: it precedes its case by design, so the invitee processes it on
    arrival and intake archives it (PCR-06-005).  Nothing is read under the
    sender's id.

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
    "holds_activity",
    "holds_received_activity",
    "read_held_activity",
    "read_received_activity",
]
