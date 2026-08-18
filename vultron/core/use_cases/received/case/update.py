"""Use cases for vulnerability case activities."""

import logging

from vultron.core.models.events.case import UpdateCaseReceivedEvent
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
            actor_id=request.receiving_actor_id or actor_id,
            request=request,
        )
        # The tree now contains a CheckIsCaseManagerNode gate, so it MUST run
        # under the *receiving* actor's identity, not the sender's (BT-17-005).
        # Passing request.actor_id would compare the sender against the case's
        # CASE_MANAGER: on the normal path a participant sends the update to the
        # CaseActor, so the gate would never match and the CM-06-001 broadcast
        # would silently never fire.
        executing_actor_id = request.receiving_actor_id or actor_id
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=executing_actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "UpdateCaseBT did not succeed for actor '%s' / case '%s': %s",
                executing_actor_id,
                case_id,
                BTBridge.get_failure_reason(tree),
            )
