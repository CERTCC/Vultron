"""Use cases for vulnerability case activities."""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.models.events.case import (
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import CasePersistence

from ._helpers import _store_embedded_participants

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class EngageCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: EngageCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: EngageCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.prioritize_tree import (
            create_engage_case_tree,
        )

        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("engage_case: missing case_id on request")
            return

        # Persist any inline participant objects carried in the case snapshot
        # so BT nodes (CheckParticipantExists, AppendParticipantStatusNode) can
        # locate them by UUID.  Mirrors the Create (#564) and Announce (#566)
        # paths (CBT-05-005, fixes #573).
        case_obj = request.case
        if is_case_model(case_obj):
            _store_embedded_participants(case_obj, self._dl, case_id)

        logger.info(
            "Actor '%s' engages case '%s' (RM → ACCEPTED)",
            actor_id,
            case_id,
        )

        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        tree = create_engage_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        if result.status != Status.SUCCESS:
            logger.warning(
                "EngageCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                BTBridge.get_failure_reason(tree),
            )


class DeferCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: DeferCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: DeferCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.prioritize_tree import (
            create_defer_case_tree,
        )

        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("defer_case: missing case_id on request")
            return

        logger.info(
            "Actor '%s' defers case '%s' (RM → DEFERRED)",
            actor_id,
            case_id,
        )

        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        tree = create_defer_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        if result.status != Status.SUCCESS:
            logger.warning(
                "DeferCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                BTBridge.get_failure_reason(tree),
            )
