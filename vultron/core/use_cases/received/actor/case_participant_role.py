"""Use case for the canonical role-delegation wire format (ADR-0039).

Handles ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``
introduced by ADR-0039 as the replacement for the deprecated
``Offer(VulnerabilityCase, target=CaseParticipant)`` format.  The Case Owner
sends it to the CASE_MANAGER, which checks it, records it and forwards it to
the target; the target answers the CASE_MANAGER (CM-33).
"""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.offer_case_participant_role_received_tree import (
    create_offer_case_participant_role_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.events.actor import (
    OfferCaseParticipantRoleReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
    unaddressed_copy_refusal,
)
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    role_offer_verdict,
    verdict_from_bt,
)
from vultron.enums.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)

_LABEL = "OfferCaseParticipantRoleReceivedBT"


class OfferCaseParticipantRoleReceivedUseCase:
    """Handle an incoming ``Offer(CaseParticipantRole, ...)`` (ADR-0039, CM-33).

    At the CASE_MANAGER the sender must be the Case Owner (CM-33-002); at any
    other store, the target's, it must be the CASE_MANAGER forwarding it
    (CM-33-004, PCR-03-001).  The CASE_MANAGER refuses an Offer whose role or
    target it may not record (CM-33-003); an admitted Offer is committed and
    forwarded to the target, and nothing is granted until the target's
    Accept is committed (CM-33-001, CM-02-016).  The target answers the
    forward, to the CASE_MANAGER.  A refused Offer leaves no entry and sends
    nothing; a redelivery of an Offer the CASE_MANAGER recorded is
    ``SKIPPED`` (HP-01-003).

    The ``context`` field carries the VulnerabilityCase ID; ``target``
    carries the Actor receiving the role; ``object_`` carries the CVDRole
    being offered.

    See SE-08-003, ADR-0039.
    """

    # Only the Case Owner offers a role; a participant takes the forward from
    # the CASE_MANAGER alone (CM-33-002, CM-33-004, PCR-03-001).  The
    # CASE_MANAGER-originated Offer CM-33-002 permits is omitted.
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: OfferCaseParticipantRoleReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: OfferCaseParticipantRoleReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request
        # Resolve the receiver before any write: it raises when no actor owns
        # this store, and a refusal must not leave the Offer behind.
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        offer_id = request.activity_id

        # The Offer is addressed to the CASE_MANAGER, and its forward to the
        # target (CM-33-001); anyone else holds a misaddressed copy, refuses,
        # and stores nothing (HP-01-005).
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id, request, label="role Offer"
            )
        ) is not None:
            return refusal

        # context carries the VulnerabilityCase; target carries the Actor
        case_id = _as_id(getattr(request.activity, "context", None))
        target_actor_id = _as_id(getattr(request.activity, "target", None))
        # The offered role; a missing one is refused, never defaulted
        # (CM-33-003).
        role_obj = getattr(
            getattr(request.activity, "object_", None), "role", None
        )
        role = role_obj if isinstance(role_obj, CVDRole) else None

        tree = create_offer_case_participant_role_received_tree(
            offer_id=offer_id,
            case_id=case_id,
            role=role,
            target_actor_id=target_actor_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        if case_id is None:
            # Intake archived the Offer; there is no case to act on.
            applied_or_raise(tree, result, label=_LABEL)
            logger.warning(
                "OfferCaseParticipantRoleReceivedUseCase: role Offer '%s'"
                " names no case — refusing",
                offer_id,
            )
            return HandlerResult.refused(
                "Offer(CaseParticipantRole) names no case"
            )
        verdict = role_offer_verdict(
            tree, verdict_from_bt(tree, result, label=_LABEL)
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "OfferCaseParticipantRoleReceivedUseCase: refused offer"
                " '%s' from '%s': %s",
                offer_id,
                request.actor_id,
                verdict.reason,
            )
        return verdict
