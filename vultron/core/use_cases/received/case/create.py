"""Use cases for vulnerability case activities."""

import logging
from typing import ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.create_case_received_tree import (
    create_create_case_received_tree,
)
from vultron.core.behaviors.case.nodes.replica_bootstrap import (
    ClassifyBootstrapRouteNode,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    exempt,
)
from vultron.core.models.events.case import CreateCaseReceivedEvent
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    find_node,
    verdict_from_bt,
)

logger = logging.getLogger(__name__)


class CreateCaseReceivedUseCase:
    """Process a bootstrap ``Create(VulnerabilityCase)`` from a remote actor.

    Receiving this message means *someone else* created the case and is
    notifying us.  We do NOT create our own case infrastructure here.

    The trust decision and every write run in
    :func:`~vultron.core.behaviors.case.create_case_received_tree.create_create_case_received_tree`
    (CLP-10-005, CLP-10-007): a sender the receiver expected (a pending
    ``VultronReportCaseLink``, CBT-01-005 / CBT-01-006), a redelivery of a
    bootstrap already accepted, or a CASE_MANAGER bootstrapping a participant
    directly (ADR-0041 AC-5).  ``execute()`` builds the tree, runs it once, and
    reports the outcome.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4070", "no sender check defined for case creation"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CreateCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id

        if request.case is None:
            logger.warning(
                "create_case_received: no case domain object in event for "
                "case '%s'",
                case_id,
            )
            return HandlerResult.refused(
                "Create(VulnerabilityCase) carries no case object"
            )

        if case_id is None:
            logger.warning(
                "create_case_received: case_id missing in event — refusing"
            )
            return HandlerResult.refused(
                "Create(VulnerabilityCase) case object has no id"
            )

        tree = create_create_case_received_tree(
            request.case, case_id, request.actor_id
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = verdict_from_bt(tree, result, label="CreateCaseReceivedBT")
        if verdict.disposition is not HandlerDisposition.APPLIED:
            return verdict
        classify = find_node(tree, ClassifyBootstrapRouteNode)
        route = classify.route if classify is not None else None
        if route is not None and route.name == "redelivery":
            # Redelivery of a bootstrap already accepted (CBT-01-006).
            return HandlerResult.skipped(
                f"bootstrap of case '{case_id}' already accepted"
            )
        if route is not None and not route.replica_stored:
            # The trust anchors and embedded objects are re-applied
            # idempotently; only the replica itself already existed.
            return HandlerResult.skipped(f"case '{case_id}' already seeded")
        return HandlerResult.applied()
