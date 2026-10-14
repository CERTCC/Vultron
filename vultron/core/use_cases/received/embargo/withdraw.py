"""Received ``Leave(EmbargoEvent)``: a signatory's withdrawal (MSM-07-010).

A participant whose consent row for the embargo in force is ``AGREED`` ends
its own consent by sending ``Leave(EmbargoEvent)[context=VulnerabilityCase]``
to the CASE_MANAGER (EP-09-013, ADR-0122).  The CASE_MANAGER declines that
row and every open proposal's row the sender had agreed to, commits the
withdrawal and changes no register entry; every replica learns it from the
ledger (EP-09-007).
"""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.withdrawal_tree import (
    withdraw_from_embargo_on_case_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.embargo import (
    WithdrawFromEmbargoOnCaseReceivedEvent,
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

logger = logging.getLogger(__name__)

_LABEL = "Leave(EmbargoEvent)"


class WithdrawFromEmbargoOnCaseReceivedUseCase:
    """The received ``Leave(EmbargoEvent)`` (MSM-07-010).

    Shape checks that write nothing, then the door check (HP-01-005,
    ADR-0118), then the tree.  The sender must be an active participant
    (CM-10-004), which a signatory to the embargo in force is; the tree's
    guard then refuses, with the reason, a Leave of an embargo not in force,
    from a row that is not ``AGREED``, or from the case owner.  Only the
    CASE_MANAGER records the withdrawal, so a receiver whose gate turns it
    away reports a refusal (BT-17-001).
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: WithdrawFromEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._wire_render_port = wire_render_port

    def execute(self) -> HandlerResult:
        request = self._request
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        embargo_id, case_id = request.embargo_id, request.case_id
        if embargo_id is None or case_id is None:
            logger.warning("%s: missing embargo_id or case_id", _LABEL)
            return HandlerResult.refused(
                f"{_LABEL} is missing its embargo id or case id"
            )
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id, request, label=_LABEL
            )
        ) is not None:
            return refusal

        tree = withdraw_from_embargo_on_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            withdrawing_actor_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            # The commit fans the entry out to every participant replica
            # (EP-09-007, RSH-08-004); without the port nothing replays it.
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005).
            actor_id=receiving_actor_id,
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="WithdrawFromEmbargoOnCaseBT"
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            # Only the CASE_MANAGER records a withdrawal; a replica learns it
            # from the ledger broadcast (BT-17-001, HP-01-005).
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is HandlerDisposition.APPLIED:
            logger.info(
                "'%s' withdrew from embargo '%s' on case '%s'",
                request.actor_id,
                embargo_id,
                case_id,
            )
        else:
            logger.warning(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict


__all__ = ["WithdrawFromEmbargoOnCaseReceivedUseCase"]
