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

from typing import Any

from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.semantic_registry import extract_event


def archive_received(dl: Any, activity: Any) -> ReceivedActivityRecord:
    """Store *activity* in *dl* as intake archives a received activity.

    *activity* may be a wire activity, as a factory builds it: it is extracted
    to the event intake receives and the event's activity is archived, exactly
    the object intake stores.
    """
    record = ReceivedActivityRecord.for_activity(
        extract_event(activity).activity
    )
    dl.create(record)
    return record
