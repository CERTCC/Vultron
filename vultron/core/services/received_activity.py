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

A received activity is held only under a key the receiver derives, its
``ReceivedActivityRecord``; an activity the actor sent is held under its own
id.  These readers are importable from any core layer, BT nodes included
(BTND-04-003), and are re-exported by ``vultron.core.use_cases._helpers``.
"""

from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronNotFoundError


def read_received_activity(
    dl: CasePersistence, activity_id: str, resource_type: str = "Activity"
) -> PersistableModel:
    """Return the activity *activity_id* as this receiver holds it.

    A received activity that reached its use case is archived by intake as a
    ``ReceivedActivityRecord`` under the receiver's own key (CLP-10-017,
    ADR-0111), so that record is read first.

    An activity the inbox deferred until its case is known has not reached
    intake yet.  An Invite to a case is usually in that state: the invitee
    holds no case until its Accept brings the bootstrap Announce (MV-10-003).
    The inbox holds such an activity under the sender's id for replay, and
    that copy is then the only one the receiver has, so it is read next.

    Args:
        dl: The receiver's DataLayer.
        activity_id: The sender's id for the activity.
        resource_type: Label for the error when nothing is held.

    Raises:
        VultronNotFoundError: When this store holds no such activity.
    """
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    if isinstance(record, ReceivedActivityRecord):
        return record.activity
    deferred = dl.read(activity_id)
    if deferred is None:
        raise VultronNotFoundError(resource_type, activity_id)
    return deferred


def read_held_activity(
    dl: CasePersistence, activity_id: str, resource_type: str = "Activity"
) -> PersistableModel:
    """Return the activity *activity_id* as this actor holds it, either way.

    Some replies answer an activity this actor either received or sent: an
    embargo ``Reject`` of an Invite that another participant proposed or that
    this actor proposed, a withdrawal of the actor's own ownership-transfer
    Offer.  A received activity is read through :func:`read_received_activity`.
    An activity this actor sent is held under its own id, the one record of
    an activity type a receiver keeps under the activity's id (DL-06-006).

    Args:
        dl: This actor's DataLayer.
        activity_id: The activity's id, as its author chose it.
        resource_type: Label for the error when nothing is held.

    Raises:
        VultronNotFoundError: When this store holds no such activity.
    """
    try:
        return read_received_activity(dl, activity_id, resource_type)
    except VultronNotFoundError:
        own = dl.read(activity_id)
        if own is None:
            raise
        return own


__all__ = ["read_held_activity", "read_received_activity"]
