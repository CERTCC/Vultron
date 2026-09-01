"""Per-semantic inbound domain event type for ProcessingFault activities.

Covers the receiver-side Create(ProcessingFault) notification flow
defined in ADR-0080, ASK-07-001.
"""

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

from typing import Literal

from vultron.core.models.events.base import MessageSemantics, VultronEvent


class CreateProcessingFaultReceivedEvent(VultronEvent):
    """Sender received a Create(ProcessingFault) NACK from a receiver.

    Indicates the receiver could not process the sender's status assertion
    (ADR-0080, ASK-07-001).  ``object_`` contains a minimal ``VultronObject``
    wrapping the ``as_ProcessingFault``; the ``in_reply_to`` field on that
    object points to the failed activity URI (ASK-07-004).
    """

    semantic_type: Literal[MessageSemantics.CREATE_PROCESSING_FAULT] = (
        MessageSemantics.CREATE_PROCESSING_FAULT
    )

    @property
    def fault_id(self) -> str | None:
        return self.object_id
