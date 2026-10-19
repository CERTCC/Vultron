"""Received ``Reject(Invite(EmbargoEvent))``: the sender's own consent.

The case owner's rejection of a proposal for the case is
``Reject(EmbargoEvent, target=Case)`` (:mod:`.owner_decision`, ADR-0122).
"""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    reject_invite_to_embargo_tree,
)
from vultron.core.models.events.embargo import (
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    door_guards_admitted,
    embargo_answer_repeat_verdict,
    not_case_manager_refusal,
    verdict_from_bt,
)
from vultron.core.use_cases.received._pending_refusal import (
    close_refused_embargo_proposal,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


class RejectInviteToEmbargoOnCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.INVITEE
    )

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
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        rejecting_actor_id = request.actor_id
        invite_id = request.invite_id

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

        if not invite_id:
            # The invitee is read from the recorded Invite (EP-09-010); a
            # Reject that names none has no invitee to be.
            logger.warning(
                "reject_invite_to_embargo_on_case: cannot resolve invite_id"
            )
            return HandlerResult.refused(
                "Reject(Invite(EmbargoEvent)) is missing its Invite id"
            )

        # One tree: its door guards refuse a closed case, an unaddressed copy
        # (HP-01-005, ADR-0118) and a sender that is not the recorded Invite's
        # invitee (EP-09-010, HP-01-006, ADR-0115) before anything is written.
        tree = reject_invite_to_embargo_tree(
            case_id=case_id,
            rejecting_actor_id=rejecting_actor_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            sender_rule=self.sender_entitlement,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            # The commit fans the entry out to every participant replica
            # (EP-09-007, RSH-08-004); without the port nothing replays it.
            sync_port=self._sync_port,
            # The Reject's own entry carries the rejecter's row (ADR-0122);
            # any other row the rejection changes is the CASE_MANAGER's own
            # Update(EmbargoConsent) entry, built through it (ADR-0124).
            trigger_activity=self._trigger_activity,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=receiving_actor_id,
            activity=request,
        )

        if door_guards_admitted(tree):
            # The door guards admitted the Reject, so the sender has standing,
            # and a CASE_MANAGER's Reject closes the proposer's pending ask,
            # whatever the tree then decided about the consent (EP-09-008).
            logger.info(
                "'%s' rejected embargo '%s'", rejecting_actor_id, invite_id
            )
            close_refused_embargo_proposal(self._dl, request)

        # A repeat of a Reject already recorded is refused by the tree's
        # repeat guard before the commit, and reported SKIPPED (CM-13-005,
        # HP-01-003).
        verdict = embargo_answer_repeat_verdict(
            tree,
            verdict_from_bt(tree, result, label="RejectInviteToEmbargoBT"),
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            # Only the CASE_MANAGER records an answer; a replica learns it
            # from the ledger broadcast (BT-17-001, HP-01-005).
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (invite '%s', case '%s')",
                verdict.reason,
                invite_id,
                case_id,
            )
        return verdict
