"""Use cases for vulnerability case activities."""

import logging

from vultron.core.behaviors.case.update_support import broadcast_case_update
from vultron.core.models.events.case import UpdateCaseReceivedEvent
from vultron.core.models.protocols import CaseModel
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


class UpdateCaseReceivedUseCase:
    def __init__(
        self, dl: CaseOutboxPersistence, request: UpdateCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: UpdateCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("update_case: missing case_id on request")
            return

        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.update_tree import (
            create_update_case_received_tree,
        )

        tree = create_update_case_received_tree(
            case_id=case_id,
            actor_id=actor_id,
            request=request,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "UpdateCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                BTBridge.get_failure_reason(tree),
            )

    def _broadcast_case_update(
        self,
        case_id: str,
        case: CaseModel,
        excluded_actor_ids: set[str] = set(),
    ) -> None:
        """Broadcast an Announce activity for the updated case to participants.

        Implements CM-06-001/CM-06-002: after a case update, the CaseActor MUST
        send an ActivityStreams Announce to each active case participant's inbox.
        Per CM-10-004, participants who have not accepted the active embargo are
        excluded from the broadcast.
        """
        broadcast_case_update(self._dl, case_id, case, excluded_actor_ids)
