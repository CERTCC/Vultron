"""Received ``Announce(EmbargoEvent)``."""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.case.received_run import (
    ReceivedOutcome,
    find_node,
    run_received_tree,
)
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
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


def _unless_revision_applied(outcome: ReceivedOutcome) -> HandlerResult | None:
    """``SKIPPED`` for a run that succeeded without applying the revision.

    Only a replica whose ledger stream is paused applies the notice's
    revision (CM-31-009, CM-31-010); any other only archives it.
    """
    if not outcome.succeeded:
        return None
    apply_node = find_node(outcome.tree, ApplyAnnouncedEmbargoRevisionNode)
    if apply_node is not None and apply_node.applied:
        return None
    logger.info(
        "%s: received embargo announcement — no receiver-side state change"
        " required",
        outcome.label,
    )
    return HandlerResult.skipped("no receiver-side state change")


class AnnounceEmbargoEventToCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.CASE_MANAGER
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceEmbargoEventToCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AnnounceEmbargoEventToCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
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
        # A revision this replica cannot hold (another case's embargo, or
        # one it cannot read) is the sender's fault: refused, not raised.
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="AnnounceEmbargoEventToCaseReceivedBT",
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
            reader=_unless_revision_applied,
        )
