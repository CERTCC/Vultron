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

"""Read an activity as this actor holds it (CLP-10-017, DL-06-006).

A received activity is held only under a key the receiver derives (DL-06-006):
its ``ReceivedActivityRecord`` once intake archived it, or, while the inbox
defers it until its case is known, the ``DeferredInboxActivity`` that holds it
for replay.  An activity the actor sent is held under its own id.  These
readers are importable from any core layer, BT nodes included (BTND-04-003),
and are re-exported by ``vultron.core.use_cases._helpers``.
"""

from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronNotFoundError


def _archived(
    dl: CasePersistence, activity_id: str
) -> PersistableModel | None:
    """The received activity *activity_id* as this receiver holds it, or ``None``.

    Read by the receiver's keys, never by the id the sender chose
    (CLP-10-017, DL-06-006): intake's archive first, then the record that
    holds a deferred activity for its replay, which carries the same core
    summary of it.
    """
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    if isinstance(record, ReceivedActivityRecord):
        return record.activity
    deferred = dl.read(DeferredInboxActivity.build_id(activity_id))
    if isinstance(deferred, DeferredInboxActivity):
        return deferred.activity
    return None


def read_received_activity(
    dl: CasePersistence, activity_id: str, resource_type: str = "Activity"
) -> PersistableModel:
    """Return the activity *activity_id* as this receiver holds it.

    A received activity that reached its use case is archived by intake as a
    ``ReceivedActivityRecord`` under the receiver's own key (CLP-10-017,
    ADR-0111), so that record is read first.

    An activity the inbox deferred until its case is known has not reached
    intake yet.  The inbox holds it for replay in a ``DeferredInboxActivity``,
    also under a key the receiver derives (DL-06-006), and that record is
    read next.  A stub Invite is never in that state: it precedes its case by
    design, so the invitee processes it on arrival and intake archives it
    (PCR-06-005).  Nothing is read under the sender's id.

    Args:
        dl: The receiver's DataLayer.
        activity_id: The sender's id for the activity.
        resource_type: Label for the error when nothing is held.

    Raises:
        VultronNotFoundError: When this store holds no such activity.
    """
    received = _archived(dl, activity_id)
    if received is None:
        raise VultronNotFoundError(resource_type, activity_id)
    return received


def read_held_activity(
    dl: CasePersistence, activity_id: str, resource_type: str = "Activity"
) -> PersistableModel:
    """Return the activity *activity_id* as this actor holds it, either way.

    Some replies answer an activity this actor either received or sent: an
    embargo ``Reject`` of an Invite that another participant proposed or that
    this actor proposed, a withdrawal of the actor's own ownership-transfer
    Offer.  A received activity is read as :func:`read_received_activity`
    reads it.  Anything else is read under its own id: an activity this
    actor sent, the one record of an activity type a receiver keeps under the
    activity's id (DL-06-006), or a core record kept under that id (the
    ledger-replayed ownership-transfer Offer).

    Args:
        dl: This actor's DataLayer.
        activity_id: The activity's id, as its author chose it.
        resource_type: Label for the error when nothing is held.

    Raises:
        VultronNotFoundError: When this store holds no such activity.
    """
    received = _archived(dl, activity_id)
    if received is not None:
        return received
    held = dl.read(activity_id)
    if held is None:
        raise VultronNotFoundError(resource_type, activity_id)
    return held


__all__ = ["read_held_activity", "read_received_activity"]
