"""Use case for received Create(ProcessingFault) NACK messages.

A sender receives this when their status assertion was refused by a receiver
(ADR-0080, ASK-07-001).  Ask-register integration (AC-8) is deferred to
issue #2883 (outstanding-request register).
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

import logging

from vultron.core.models.events.fault import CreateProcessingFaultReceivedEvent
from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


class CreateProcessingFaultReceivedUseCase:
    """Log a received Create(ProcessingFault) NACK.

    Full ask-register correlation (AC-8) is deferred to issue #2883.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateProcessingFaultReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        request = self._request
        logger.warning(
            "ProcessingFault received from '%s' for activity '%s'"
            " (fault object: %s)",
            request.actor_id,
            request.activity_id,
            request.fault_id,
        )
