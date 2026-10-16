"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.announce_case_received_tree import (
    create_announce_vulnerability_case_received_tree,
)
from vultron.core.behaviors.case.nodes.announce import (
    AnnounceSenderTrustedNode,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    exempt,
)
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.ledger_gap_buffer import (
    LedgerGapBuffer,
    resolve_ledger_gap_buffer,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.inbox_hand_back import InboxHandBackPort
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    guard_refusal,
    verdict_from_bt,
)

logger = logging.getLogger(__name__)


class AnnounceVulnerabilityCaseReceivedUseCase:
    """Seed the local DataLayer with a full VulnerabilityCase from the case owner.

    Per MV-10-003, the invitee creates the case if it does not already exist.
    Per MV-10-004, if the case already exists locally, the announcement is
    accepted without overwriting the existing record (idempotent).

    Seeding the case anchors its genesis hash, so an
    ``Announce(CaseLedgerEntry)`` parked in the gap buffer during the
    pre-genesis window (SYNC-15-004) may now extend the chain.  The tree
    hands that entry back to this actor's inbox through the injected
    :class:`~vultron.core.ports.inbox_hand_back.InboxHandBackPort` as a
    delivery of its own (SYNC-15-005, SYNC-14-009); it never runs the entry's
    tree here.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4785", "no sender check for actor announcement"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceVulnerabilityCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        gap_buffer: LedgerGapBuffer | None = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        inbox_hand_back: InboxHandBackPort | None = None,
    ) -> None:
        self._dl = dl
        self._inbox_hand_back = inbox_hand_back
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._request = request
        self._sync_port = sync_port
        self._gap_buffer = gap_buffer

    def execute(self) -> HandlerResult:
        request = self._request
        case_obj = getattr(request.activity, "object_", None)
        tree = create_announce_vulnerability_case_received_tree(
            case_obj=case_obj, request=request
        )
        gap_buffer = resolve_ledger_gap_buffer(
            self._gap_buffer, request.receiving_actor_id
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
            gap_buffer=gap_buffer,
            inbox_hand_back=self._inbox_hand_back,
        )
        # The guards' own reasons are the refusal (PCR-03-004, CLP-10-018).
        if (
            refusal := guard_refusal(tree, AnnounceSenderTrustedNode)
        ) is not None:
            return refusal
        verdict = verdict_from_bt(
            tree, result, label="AnnounceVulnerabilityCaseReceivedBT"
        )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (activity '%s')", verdict.reason, request.activity_id
            )
            return verdict
        return HandlerResult.applied()
