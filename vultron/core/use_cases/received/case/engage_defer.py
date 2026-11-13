"""Use cases for vulnerability case activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.case.received_run import run_received_tree
from vultron.core.behaviors.report.prioritize_tree import (
    create_defer_case_tree,
    create_engage_case_tree,
)
from vultron.core.models.events.case import (
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


class EngageCaseReceivedUseCase:
    # The sender declares its own RM state to the CASE_MANAGER; only a
    # participant of the case may (HP-01-006, RSH-06-006, PCR-08-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
        SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: EngageCaseReceivedEvent,
        trigger_activity: TriggerActivityPort | None = None,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: EngageCaseReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request

        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("engage_case: missing case_id on request")
            return HandlerResult.refused("Engage activity has no case id")

        # The Join names the case (ADR-0165): the tree's path stage refuses
        # one this store does not hold (AKM-03-006).

        # A receipt, not a transition: the tree decides whether the declared
        # move happened, and a restatement is reported SKIPPED.  An
        # ``RM → ACCEPTED`` line here would assert a move the handler may go
        # on to say it did not make (SL-04-007, #5006).  The move itself is
        # logged once, by the status writer.
        logger.info(
            "Actor '%s' declares RM.ACCEPTED on case '%s' (Join received)",
            actor_id,
            case_id,
        )

        tree = create_engage_case_tree(
            case_id=case_id,
            actor_id=actor_id,
            sender_rule=self.sender_entitlement,
        )
        # A restated Join has no move to record, and so no change to
        # announce: the tree skips the CASE_MANAGER's effects whole, and its
        # repeat guard says the run changed nothing, so the runner reports
        # SKIPPED, not APPLIED (ID-05-003, #5006).  Only the CASE_MANAGER
        # records the move: the path stage refuses any other receiver
        # (HP-01-005).
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="EngageCaseBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            case_id=case_id,
        )


class DeferCaseReceivedUseCase:
    # The sender declares its own RM state to the CASE_MANAGER; only a
    # participant of the case may (HP-01-006, RSH-06-006, PCR-08-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
        SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: DeferCaseReceivedEvent,
        trigger_activity: TriggerActivityPort | None = None,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: DeferCaseReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request

        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("defer_case: missing case_id on request")
            return HandlerResult.refused("Defer activity has no case id")

        # The Ignore names the case, as the Join does (AKM-03-006).  A
        # receipt, not a transition, for the reason given on the engage line
        # above (SL-04-007).
        logger.info(
            "Actor '%s' declares RM.DEFERRED on case '%s' (Ignore received)",
            actor_id,
            case_id,
        )

        tree = create_defer_case_tree(
            case_id=case_id,
            actor_id=actor_id,
            sender_rule=self.sender_entitlement,
        )
        # Only the CASE_MANAGER records the move: the path stage refuses any
        # other receiver (HP-01-005).
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="DeferCaseBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            case_id=case_id,
        )
