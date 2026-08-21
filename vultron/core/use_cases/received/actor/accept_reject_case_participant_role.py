"""Use cases for Accept/Reject of the canonical role-delegation format (ADR-0039).

Handles ``Accept(Offer(CaseParticipantRole, ...))`` and
``Reject(Offer(CaseParticipantRole, ...))`` received by the offering actor
after the target actor (or their CaseActor) responds to a role offer.
See SE-08-003, ADR-0039.
"""

import logging

from vultron.core.models.events.actor import (
    AcceptCaseParticipantRoleReceivedEvent,
    RejectCaseParticipantRoleReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import _idempotent_create

logger = logging.getLogger(__name__)


class AcceptCaseParticipantRoleReceivedUseCase:
    """Handle acceptance of a canonical role-delegation offer (ADR-0039).

    The offering actor receives this Accept from the target actor (or their
    CaseActor representative).  Idempotently persists the activity and logs
    at INFO level.  See SE-08-003, ADR-0039.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptCaseParticipantRoleReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AcceptCaseParticipantRoleReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "AcceptCaseParticipantRole",
            request.activity_id,
        )
        logger.info(
            "AcceptCaseParticipantRoleReceived: actor '%s' accepted role"
            " delegation offer '%s'",
            request.actor_id,
            request.object_id,
        )


class RejectCaseParticipantRoleReceivedUseCase:
    """Handle rejection of a canonical role-delegation offer (ADR-0039).

    The offering actor receives this Reject from the target actor (or their
    CaseActor representative).  Logs at WARNING level.
    See SE-08-003, ADR-0039.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectCaseParticipantRoleReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectCaseParticipantRoleReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.warning(
            "RejectCaseParticipantRoleReceived: actor '%s' rejected role"
            " delegation offer '%s'",
            request.actor_id,
            request.object_id,
        )
