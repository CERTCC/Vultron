"""Received ``Reject(Invite(EmbargoEvent))`` (ER, EJ)."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    reject_invite_to_embargo_tree,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    ALREADY_DECLINED_PREFIX,
)
from vultron.core.models.events.embargo import (
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
    unaddressed_copy_refusal,
)
from vultron.core.use_cases.received._bt_verdict import (
    not_case_manager_refusal,
    verdict_from_bt,
)
from vultron.core.use_cases.received._pending_refusal import (
    close_refused_embargo_proposal,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class RejectInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectInviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: RejectInviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port
        # The owner's Reject of a revision after disclosure terminates the
        # embargo, and the CASE_MANAGER tells the participants (EMB-04-002).
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        # Door check before any tree or write: an unaddressed copy is
        # refused (HP-01-005, ADR-0118).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id,
                request,
                label="Reject(Invite(EmbargoEvent))",
            )
        ) is not None:
            return refusal
        rejecting_actor_id = request.actor_id
        invite_id = request.invite_id

        logger.info(
            "'%s' rejected embargo '%s'", rejecting_actor_id, invite_id
        )
        close_refused_embargo_proposal(self._dl, request)  # EP-09-008
        case_id, embargo_id = request.case_id, request.embargo_id

        if not case_id:
            logger.warning(
                "reject_invite_to_embargo_on_case: cannot resolve case_id"
            )
            return HandlerResult.refused(
                "Reject(Invite(EmbargoEvent)) does not name a case"
            )
        if not embargo_id:
            # Which terms are refused decides the consent effect (MSM-07-004);
            # a Reject that names none is malformed, like an Accept that does.
            logger.warning(
                "reject_invite_to_embargo_on_case: cannot resolve embargo_id"
            )
            return HandlerResult.refused(
                "Reject(Invite(EmbargoEvent)) does not name an embargo"
            )

        tree = reject_invite_to_embargo_tree(
            case_id=case_id,
            rejecting_actor_id=rejecting_actor_id,
            invite_id=invite_id or "",
            embargo_id=embargo_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            # The commit fans the entry out to every participant replica
            # (EP-09-007, RSH-08-004); without the port nothing replays it.
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=receiving_actor_id,
            activity=request,
        )

        verdict = verdict_from_bt(
            tree, result, label="RejectInviteToEmbargoBT"
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            # Only the CASE_MANAGER records an answer; a replica learns it
            # from the ledger broadcast (BT-17-001, HP-01-005).
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if (
            verdict.disposition is HandlerDisposition.REFUSED
            and ALREADY_DECLINED_PREFIX in (verdict.reason or "")
        ):
            # The node named this Reject a repeat of one already recorded
            # (#2255).  Keyed on the node's verdict, not on the store: a
            # DECLINED actor's Reject of an *unknown* embargo is still a
            # refusal (HP-01-003).
            verdict = HandlerResult.skipped(
                f"'{rejecting_actor_id}' already declined on case '{case_id}'"
            )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (invite '%s', case '%s')",
                verdict.reason,
                invite_id,
                case_id,
            )
        return verdict
