"""Use cases for Accept/Reject of the canonical role-delegation format (ADR-0039).

Handles ``Accept(Offer(CaseParticipantRole, ...))`` and
``Reject(Offer(CaseParticipantRole, ...))``, which the target of a role offer
addresses to the case's CASE_MANAGER (CM-33-004).  The CASE_MANAGER acts on
an answer only from the target of an open role Offer it recorded (CM-33-005),
commits it and broadcasts ``Announce(CaseLedgerEntry)``, and on an Accept
grants the role on its own replica (CM-33-006, CM-02-016).
See SE-08-003, ADR-0039.
"""

from typing import TYPE_CHECKING, ClassVar

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
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received._bt_verdict import (
    role_offer_answer_verdict,
)
from vultron.core.use_cases.received._offer_reply import (
    run_offer_reply_tree,
)
from vultron.enums.roles import CVDRole
from vultron.primitives import normalise_actor_id

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

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
    every replica grants what it names (CM-02-016).  The target is
    normalised, since the CASE_MANAGER's grant looks it up in the case's
    participant index, as every replica does (OID-01-006).
    """
    offer = getattr(request.activity, "object_", None)
    role = getattr(getattr(offer, "object_", None), "role", None)
    target_id = _as_id(getattr(offer, "target", None))
    if target_id is not None:
        target_id = normalise_actor_id(target_id)
    return (role if isinstance(role, CVDRole) else None), target_id


def _case_named(request: _RoleOfferAnswer) -> str | None:
    """The case the answer names in its own ``context``."""
    return _as_id(getattr(request.activity, "context", None))


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
        return run_offer_reply_tree(
            dl=self._dl,
            request=request,
            tree=tree,
            label=label,
            case_id=case_id,
            subject="role offer",
            refine=role_offer_answer_verdict,
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
        return run_offer_reply_tree(
            dl=self._dl,
            request=request,
            tree=tree,
            label=label,
            case_id=case_id,
            subject="role offer",
            refine=role_offer_answer_verdict,
            applied_note="rejected",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
        )
