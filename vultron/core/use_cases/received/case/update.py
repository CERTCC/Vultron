"""Use cases for vulnerability case activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.update_tree import (
    create_update_case_received_tree,
)
from vultron.core.models.events.case import UpdateCaseReceivedEvent
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import verdict_from_bt

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class UpdateCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: UpdateCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: UpdateCaseReceivedEvent = request
        # The CM-06-001 broadcast is emitted through this port so the adapter
        # persists and seals it (VM-08-003); the inbox pipeline injects it.
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        if case_id is None:
            logger.warning("update_case: missing case_id on request")
            return HandlerResult.refused(
                "Update(VulnerabilityCase) has no case id"
            )

        # The tree contains a CheckIsCaseManagerNode gate, so it MUST run
        # under the *receiving* actor's identity, not the sender's (BT-17-005).
        # Passing request.actor_id would compare the sender against the case's
        # CASE_MANAGER: on the normal path a participant sends the update to the
        # CaseActor, so the gate would never match and the CM-06-001 broadcast
        # would silently never fire.  Absent receiving_actor_id the answer is
        # the store's owner, never the sender (BT-17-006, #2667).
        executing_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        tree = create_update_case_received_tree(
            case_id=case_id,
            actor_id=executing_actor_id,
            request=request,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=executing_actor_id,
            activity=request,
        )
        # A non-manager applies the update and skips only the broadcast, so the
        # tree still succeeds: that is APPLIED, not a skip (CM-06-001).
        verdict = verdict_from_bt(tree, result, label="UpdateCaseBT")
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "UpdateCaseBT refused for actor '%s' / case '%s': %s",
                executing_actor_id,
                case_id,
                verdict.reason,
            )
        return verdict
