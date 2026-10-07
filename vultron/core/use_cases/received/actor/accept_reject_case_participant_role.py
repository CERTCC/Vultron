"""Use cases for Accept/Reject of the canonical role-delegation format (ADR-0039).

Handles ``Accept(Offer(CaseParticipantRole, ...))`` and
``Reject(Offer(CaseParticipantRole, ...))`` received by the offering actor
after the target actor (or their CaseActor) responds to a role offer.
See SE-08-003, ADR-0039.
"""

import logging
from typing import ClassVar

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    exempt,
)
from vultron.core.models.events.actor import (
    AcceptCaseParticipantRoleReceivedEvent,
    RejectCaseParticipantRoleReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    intake_verdict,
)
from vultron.core.use_cases.received._store_only import run_store_only

logger = logging.getLogger(__name__)


class AcceptCaseParticipantRoleReceivedUseCase:
    """Handle acceptance of a canonical role-delegation offer (ADR-0039).

    The offering actor receives this Accept from the target actor (or their
    CaseActor representative).  Idempotently persists the activity and logs
    at INFO level.  See SE-08-003, ADR-0039.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4070", "no sender check for accept case participant role"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptCaseParticipantRoleReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AcceptCaseParticipantRoleReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        tree, result = run_store_only(
            self._dl,
            request,
            name="AcceptCaseParticipantRoleReceivedBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
        stored = intake_verdict(
            tree, result, label="AcceptCaseParticipantRoleReceivedBT"
        )
        logger.info(
            "AcceptCaseParticipantRoleReceived: actor '%s' accepted role"
            " delegation offer '%s'",
            request.actor_id,
            request.object_id,
        )
        return stored


class RejectCaseParticipantRoleReceivedUseCase:
    """Handle rejection of a canonical role-delegation offer (ADR-0039).

    The offering actor receives this Reject from the target actor (or their
    CaseActor representative).  Logs at WARNING level.
    See SE-08-003, ADR-0039.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4070", "no sender check for reject case participant role"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectCaseParticipantRoleReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: RejectCaseParticipantRoleReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        tree, result = run_store_only(
            self._dl,
            request,
            name="RejectCaseParticipantRoleReceivedBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
        applied_or_raise(
            tree, result, label="RejectCaseParticipantRoleReceivedBT"
        )
        logger.warning(
            "RejectCaseParticipantRoleReceived: actor '%s' rejected role"
            " delegation offer '%s'",
            request.actor_id,
            request.object_id,
        )
        return HandlerResult.skipped(
            "role delegation offer declined; nothing to undo"
        )
