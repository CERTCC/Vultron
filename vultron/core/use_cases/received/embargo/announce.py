"""Received ``Announce(EmbargoEvent)``."""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_received_tree import (
    announce_embargo_received_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    ApplyAnnouncedEmbargoRevisionNode,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.embargo import (
    AnnounceEmbargoEventToCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    addressee_refusal,
    find_node,
    verdict_from_bt,
)

logger = logging.getLogger(__name__)


class AnnounceEmbargoEventToCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
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
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        # One tree.  Its door guards refuse an unaddressed copy (HP-01-005,
        # ADR-0118) and any sender but the CASE_MANAGER, at every replica,
        # since the announcement is canonical case state (EP-09-003,
        # PCR-03-001, ADR-0115).  A replica whose ledger stream is paused
        # applies a shorter revision from the CASE_MANAGER's notice
        # (CM-31-009, CM-31-010); any other replica only archives it and
        # takes the change from the ledger.
        embargo = request.embargo
        tree = announce_embargo_received_tree(
            case_id=request.case_id,
            embargo_id=request.embargo_id,
            embargo=embargo if isinstance(embargo, EmbargoEvent) else None,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree, actor_id=receiving_actor_id, activity=request
        )
        # A revision this replica cannot hold (another case's embargo, or
        # one it cannot read) is the sender's fault: refused, not raised.
        verdict = verdict_from_bt(
            tree, result, label="AnnounceEmbargoEventToCaseReceivedBT"
        )
        if (refusal := addressee_refusal(tree)) is not None:
            return refusal
        if verdict.disposition is not HandlerDisposition.APPLIED:
            return verdict
        apply_node = find_node(tree, ApplyAnnouncedEmbargoRevisionNode)
        if apply_node is not None and apply_node.applied:
            return verdict
        return self._no_change()

    def _no_change(self) -> HandlerResult:
        logger.info(
            "Received embargo announcement '%s' — no receiver-side state"
            " change required",
            self._request.activity_id,
        )
        return HandlerResult.skipped("no receiver-side state change")
