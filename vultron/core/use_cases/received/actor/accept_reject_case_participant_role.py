"""Use cases for Accept/Reject of the canonical role-delegation format (ADR-0039).

Handles ``Accept(Offer(CaseParticipantRole, ...))`` and
``Reject(Offer(CaseParticipantRole, ...))``, which the target of a role offer
addresses to the case's CASE_MANAGER (CM-33-004).  The CASE_MANAGER acts on
an answer only from the target of an open role Offer it recorded (CM-33-005),
commits it and broadcasts ``Announce(CaseLedgerEntry)``, and on an Accept
grants the role on its own replica (CM-33-006, CM-02-016).
See SE-08-003, ADR-0039.
"""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.role_offer_answer_tree import (
    create_accept_case_participant_role_tree,
    create_reject_case_participant_role_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.events.actor import (
    AcceptCaseParticipantRoleReceivedEvent,
    RejectCaseParticipantRoleReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    role_offer_answer_verdict,
    verdict_from_bt,
)
from vultron.core.use_cases.received._intake_only import run_intake_only
from vultron.enums.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)

_RoleOfferAnswer = (
    AcceptCaseParticipantRoleReceivedEvent
    | RejectCaseParticipantRoleReceivedEvent
)


def _carried_role_and_target(
    request: _RoleOfferAnswer,
) -> tuple[CVDRole | None, str | None]:
    """The role and target the Offer the answer carries names.

    Read only to check them against the recorded Offer, never to find it
    (CM-33-005): the entry the CASE_MANAGER commits carries this copy, and
    every replica grants what it names (CM-02-016).
    """
    offer = getattr(request.activity, "object_", None)
    role = getattr(getattr(offer, "object_", None), "role", None)
    target_id = _as_id(getattr(offer, "target", None))
    return (role if isinstance(role, CVDRole) else None), target_id


def _case_named(request: _RoleOfferAnswer) -> str | None:
    """The case the answer names in its own ``context``."""
    return _as_id(getattr(request.activity, "context", None))


def _names_no_case(
    *,
    dl: CaseOutboxPersistence,
    request: _RoleOfferAnswer,
    label: str,
    verb: str,
    sync_port: SyncActivityPort | None,
    wire_render_port: "WireRenderPort | None",
) -> HandlerResult:
    """Archive an answer that names no case, and refuse it (CLP-10-018)."""
    tree, result = run_intake_only(
        dl,
        request,
        name=label,
        sync_port=sync_port,
        wire_render_port=wire_render_port,
    )
    applied_or_raise(tree, result, label=label)
    logger.warning(
        "%s: %s(role Offer) '%s' from '%s' names no case — refusing",
        label,
        verb,
        request.activity_id,
        request.actor_id,
    )
    return HandlerResult.refused(f"{verb}(role Offer) names no case")


def _run_role_offer_answer(
    *,
    dl: CaseOutboxPersistence,
    request: _RoleOfferAnswer,
    tree: py_trees.behaviour.Behaviour,
    label: str,
    applied_note: str,
    sync_port: SyncActivityPort | None,
    wire_render_port: "WireRenderPort | None",
    trigger_activity: "TriggerActivityPort | None",
) -> HandlerResult:
    """Run the received tree of an answer to a role Offer; read its verdict.

    Shared by the Accept and the Reject.  A redelivery of the answer that
    closed the Offer is ``SKIPPED`` (HP-01-003); a refusal is logged at
    WARNING with the sender and the case, and an applied answer at INFO with
    *applied_note*.
    """
    receiving_actor_id = resolve_receiving_actor_id(
        dl, request.receiving_actor_id
    )
    result = BTBridge(
        datalayer=dl,
        trigger_activity=trigger_activity,
        wire_render_port=wire_render_port,
        sync_port=sync_port,
    ).execute_with_setup(
        tree=tree, actor_id=receiving_actor_id, activity=request
    )
    verdict = role_offer_answer_verdict(
        tree, verdict_from_bt(tree, result, label=label)
    )
    if verdict.disposition is HandlerDisposition.REFUSED:
        logger.warning(
            "%s refused '%s' from '%s': %s",
            label,
            request.activity_id,
            request.actor_id,
            verdict.reason,
        )
    elif verdict.disposition is HandlerDisposition.APPLIED:
        logger.info(
            "%s: actor '%s' %s role offer '%s' (CM-33-006)",
            label,
            request.actor_id,
            applied_note,
            request.object_id,
        )
    return verdict


class AcceptCaseParticipantRoleReceivedUseCase:
    """The CASE_MANAGER records the target's acceptance of a role Offer.

    The sender must be the target of an open role Offer the CASE_MANAGER
    recorded for the case; an answer naming the CASE_MANAGER's forward is
    resolved to that Offer through the forward's ``inReplyTo`` (CM-33-005).
    Anyone else, or an answer to an Offer already answered, is ``REFUSED``
    with no entry and no role change; a redelivery of the Accept that closed
    the Offer is ``SKIPPED`` (HP-01-003).  An admitted Accept is committed as
    ``accept_case_participant_role`` and announced to the participants, and
    the CASE_MANAGER grants the role on its own replica (CM-33-006,
    CM-02-016).  See SE-08-003, ADR-0039.
    """

    # The target of the recorded role Offer is the addressee of the request
    # (ADR-0129).  The answer goes to the CASE_MANAGER only (CM-33-004), so
    # no sender is admitted at any other store: a participant learns the
    # answer from the CASE_MANAGER's entry, never from the answer itself
    # (CM-02-016).
    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_case_manager=any_of(SenderEntitlementKind.NAMED_ACTOR)
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptCaseParticipantRoleReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AcceptCaseParticipantRoleReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        label = "AcceptCaseParticipantRoleReceivedBT"
        case_id = _case_named(request)
        if case_id is None:
            return _names_no_case(
                dl=self._dl,
                request=request,
                label=label,
                verb="Accept",
                sync_port=self._sync_port,
                wire_render_port=self._wire_render_port,
            )
        role, target_id = _carried_role_and_target(request)
        tree = create_accept_case_participant_role_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            answer_id=request.activity_id,
            carried_role=role,
            carried_target_id=target_id,
            sender_rule=self.sender_entitlement,
        )
        return _run_role_offer_answer(
            dl=self._dl,
            request=request,
            tree=tree,
            label=label,
            applied_note="accepted",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
        )


class RejectCaseParticipantRoleReceivedUseCase:
    """The CASE_MANAGER records the target's refusal of a role Offer.

    The Accept's sender rule and open-Offer check (CM-33-005).  An admitted
    Reject is committed as ``reject_case_participant_role`` and announced to
    the participants (CM-33-006, CLP-02-012); that entry closes the Offer,
    and no role changes.  See SE-08-003, ADR-0039.
    """

    # The Accept's rule (CM-33-005).
    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_case_manager=any_of(SenderEntitlementKind.NAMED_ACTOR)
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectCaseParticipantRoleReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: RejectCaseParticipantRoleReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        label = "RejectCaseParticipantRoleReceivedBT"
        case_id = _case_named(request)
        if case_id is None:
            return _names_no_case(
                dl=self._dl,
                request=request,
                label=label,
                verb="Reject",
                sync_port=self._sync_port,
                wire_render_port=self._wire_render_port,
            )
        role, target_id = _carried_role_and_target(request)
        tree = create_reject_case_participant_role_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            answer_id=request.activity_id,
            carried_role=role,
            carried_target_id=target_id,
            sender_rule=self.sender_entitlement,
        )
        return _run_role_offer_answer(
            dl=self._dl,
            request=request,
            tree=tree,
            label=label,
            applied_note="rejected",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
        )
