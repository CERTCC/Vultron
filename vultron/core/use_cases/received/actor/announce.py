"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import ClassVar, cast

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.announce_case_received_tree import (
    create_announce_vulnerability_case_received_tree,
)
from vultron.core.behaviors.case.nodes.announce import (
    AnnounceSenderTrustedNode,
    SeedAnnouncedCaseNode,
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
    get_ledger_gap_buffer,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    find_node,
    guard_refusal,
    incomplete_activity_refusal,
    verdict_from_bt,
)
from vultron.core.use_cases.received.sync import drain_gap_buffer
from vultron.errors import VultronBTInternalError

logger = logging.getLogger(__name__)


class AnnounceVulnerabilityCaseReceivedUseCase:
    """Seed the local DataLayer with a full VulnerabilityCase from the case owner.

    Per MV-10-003, the invitee creates the case if it does not already exist.
    Per MV-10-004, if the case already exists locally, the announcement is
    accepted without overwriting the existing record (idempotent).
    """

    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4522", "no sender check for actor announcement"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceVulnerabilityCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        gap_buffer: LedgerGapBuffer | None = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request = request
        self._sync_port = sync_port
        self._gap_buffer = gap_buffer

    def execute(self) -> HandlerResult:
        request = self._request
        tree = create_announce_vulnerability_case_received_tree(
            case_obj=getattr(request.activity, "object_", None),
            request=request,
        )
        bridge = BTBridge(
            datalayer=self._dl,
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
        )
        # The guards' own reasons are the refusal (PCR-03-004, CLP-10-018).
        if (refusal := incomplete_activity_refusal(tree)) is not None:
            return refusal
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
        seed = find_node(tree, SeedAnnouncedCaseNode)
        if seed is None:
            raise VultronBTInternalError(
                "AnnounceVulnerabilityCaseReceivedBT: applied without seeding"
            )
        case_id = seed.case_id

        # The case (and therefore its deterministic per-case genesis hash) is
        # now seeded locally.  Any Announce(CaseLedgerEntry) that arrived during
        # the pre-genesis window was parked in the actor-local gap buffer rather
        # than dropped (SYNC-15-004, #2186); drain it now so the ledger converges
        # without waiting on the reject → replay round-trip (SYNC-15-005, #2180).
        gap_buffer = self._gap_buffer
        if gap_buffer is None and request.receiving_actor_id:
            gap_buffer = get_ledger_gap_buffer(request.receiving_actor_id)
        if gap_buffer is not None and gap_buffer.depth(case_id) > 0:
            drain_gap_buffer(
                cast(CaseOutboxPersistence, self._dl),
                case_id,
                resolve_receiving_actor_id(
                    self._dl, request.receiving_actor_id
                ),
                gap_buffer,
                self._sync_port,
                self._wire_render_port,
            )
        return HandlerResult.applied()
