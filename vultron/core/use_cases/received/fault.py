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
from typing import ClassVar

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    exempt,
)
from vultron.core.models.events.fault import CreateProcessingFaultReceivedEvent
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases.received._bt_verdict import applied_or_raise
from vultron.core.use_cases.received._intake_only import run_intake_only

logger = logging.getLogger(__name__)


class CreateProcessingFaultReceivedUseCase:
    """Log a received Create(ProcessingFault) NACK.

    Full ask-register correlation (AC-8) is deferred to issue #2883.

    No sender check gates anything yet: the handler archives the fault, as
    every received tree does before its guards (CLP-10-018), logs it and
    reports ``SKIPPED``, committing, writing and sending nothing.  The
    CASE_MANAGER's re-seed on a case-diverged fault (SYNC-16-003) is the first
    effect a fault will have, and its sender rule lands with it in #4799.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4799",
        "a fault changes nothing until the case-diverged re-seed (SYNC-16-003)"
        " acts on it; that issue declares the sender rule",
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateProcessingFaultReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        # The received baseline supplies the trigger port to every use case;
        # this one runs no tree that builds an activity, so it is unused.
        del trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request = request

    def execute(self) -> HandlerResult:
        request = self._request
        tree, result = run_intake_only(
            self._dl,
            request,
            name="CreateProcessingFaultReceivedBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
        verdict = applied_or_raise(
            tree, result, label="CreateProcessingFaultReceivedBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            return verdict  # the case is fully closed (CM-23-013)
        logger.warning(
            "ProcessingFault received from '%s' for activity '%s'"
            " (fault object: %s)",
            request.actor_id,
            request.activity_id,
            request.fault_id,
        )
        return HandlerResult.skipped(
            "ask-register correlation not implemented (#2883)"
        )
