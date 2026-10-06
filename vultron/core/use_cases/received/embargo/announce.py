"""Received ``Announce(EmbargoEvent)``."""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.models.events.embargo import (
    AnnounceEmbargoEventToCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
    SenderMayAssertEmbargoNode,
)
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
    unaddressed_copy_refusal,
)
from vultron.core.use_cases.received._sender_preflight import sender_refusal

logger = logging.getLogger(__name__)


class AnnounceEmbargoEventToCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.CASE_MANAGER
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceEmbargoEventToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AnnounceEmbargoEventToCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        # Door check before any tree or write: an unaddressed copy is
        # refused (HP-01-005, ADR-0118).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id, request, label="Announce(EmbargoEvent)"
            )
        ) is not None:
            return refusal
        # The announcement is canonical case state, so only the CASE_MANAGER
        # makes it, at every replica (EP-09-003, PCR-03-001, ADR-0115).  No
        # tree runs here, so the guard runs ahead of the handler's effects.
        if (
            refusal := sender_refusal(
                self._dl,
                receiving_actor_id,
                SenderMayAssertEmbargoNode(
                    case_id=request.case_id,
                    sender_actor_id=request.actor_id,
                ),
                label="Announce(EmbargoEvent)",
                sync_port=self._sync_port,
            )
        ) is not None:
            return refusal
        logger.info(
            "Received embargo announcement '%s' — no receiver-side state"
            " change required",
            request.activity_id,
        )
        return HandlerResult.skipped("no receiver-side state change")
