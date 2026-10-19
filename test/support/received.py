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

"""Seed a store with an activity as if it had been received.

A received activity that reaches its use case is stored by intake, as a
``ReceivedActivityRecord`` under the receiver's key (CLP-10-017, ADR-0111).
A test that needs the receiver to *hold* a dispatched activity — an invitee
about to answer its Invite, for instance — seeds that record, so the code
under test reads it the way production does.
"""

from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity


def archive_received(
    dl: CasePersistence, activity: as_Activity
) -> ReceivedActivityRecord:
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
