"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.announce_case_received_tree import (
    create_announce_vulnerability_case_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.inbox_replay import InboxReplayPort
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    stale_case_copy_verdict,
    verdict_from_bt,
)

logger = logging.getLogger(__name__)


class AnnounceVulnerabilityCaseReceivedUseCase:
    """Seed, or update, the local replica from a full VulnerabilityCase copy.

    Per MV-10-003 and PCR-02-003, the invitee creates the case if it does not
    already exist.  Per PCR-02-004, a copy of a case the replica already
    holds is an authoritative update, judged by the ledger position the copy
    names (SYNC-16-005, SYNC-16-006): a copy the replica is already past is
    ``SKIPPED``; one naming a different entry at an index the replica holds
    is ``REFUSED`` and logged at ERROR; any other copy replaces the case,
    position included.  The case is unchanged in both of the first two.  A
    repeat of the same Announce is judged the same way (SYNC-16-006).  After a
    replacement whose position is ahead of the chain the replica asks for
    the missing entries and stores each one the copy reflects as a no-op
    (SYNC-16-007).

    Only the case's CASE_MANAGER sends it, and every receiver, a participant
    replica, takes it from the CASE_MANAGER alone (PCR-03-001): the one its
    bootstrap recorded on a completed ``ReportCaseLink`` (CBT-02-003), else
    the one its replica names, else the trust anchor its stub Invite
    recorded (PCR-03-004).  With none of them, the Announce is refused.

    Seeding the case anchors its genesis hash, so an
    ``Announce(CaseLedgerEntry)`` held during the pre-genesis window
    (SYNC-15-004) may now extend the chain.  The tree replays that
    ``Announce``, as it was received, through this actor's inbox via the
    injected :class:`~vultron.core.ports.inbox_replay.InboxReplayPort`, as a
    delivery of its own (SYNC-15-005, SYNC-14-009); it never runs the entry's
    tree here.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.CASE_MANAGER
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceVulnerabilityCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        inbox_replay: InboxReplayPort | None = None,
    ) -> None:
        self._dl = dl
        self._inbox_replay = inbox_replay
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._request = request
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request
        case_obj = getattr(request.activity, "object_", None)
        tree = create_announce_vulnerability_case_received_tree(
            case_obj=case_obj,
            request=request,
            sender_rule=self.sender_entitlement,
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
            inbox_replay=self._inbox_replay,
        )
        verdict = stale_case_copy_verdict(
            tree,
            verdict_from_bt(
                tree, result, label="AnnounceVulnerabilityCaseReceivedBT"
            ),
        )
        if verdict.disposition is HandlerDisposition.SKIPPED:
            # The guard logged the stale copy (SYNC-16-006, CLP-04-008).
            return verdict
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (activity '%s')", verdict.reason, request.activity_id
            )
            return verdict
        return HandlerResult.applied()
