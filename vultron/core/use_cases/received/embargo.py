"""Use cases for embargo management activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    AddEmbargoEventToCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.use_cases._helpers import (
    _as_id,
    _idempotent_create,
    add_activity_to_outbox,
)
from vultron.core.models.protocols import (
    PersistableModel,
    is_case_model,
)
from vultron.core.states.cs import (
    CS_pxa,
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _pxa_embargo_ineligible(dl: CasePersistence, case_id: str) -> bool:
    """Return True when P/X/A is set on the case (EMB-01-002, EMB-02-002).

    Reads the case from the DataLayer; returns False (eligible) when the case
    cannot be resolved so normal processing can continue.
    """
    case = dl.read(case_id)
    if not is_case_model(case):
        return False
    try:
        pxa_state = CS_pxa(case.current_status.pxa_state)
    except ValueError:
        return False
    return (
        is_pxa_public_aware(pxa_state)
        or is_pxa_exploit_public(pxa_state)
        or is_pxa_attacks_observed(pxa_state)
    )


def _resolve_case_for_embargo_acceptance(
    dl: CasePersistence, request: AcceptInviteToEmbargoOnCaseReceivedEvent
) -> PersistableModel | None:
    if request.case_id:
        return dl.read(request.case_id)

    if request.invite_id is None:
        logger.error(
            "accept_invite_to_embargo_on_case: missing invite_id on request"
        )
        return None

    invite = dl.read(request.invite_id)
    if invite is None:
        logger.error(
            "accept_invite_to_embargo_on_case: invite '%s' not found",
            request.invite_id,
        )
        return None

    context_id = _as_id(getattr(invite, "context", None))
    if context_id is None:
        logger.error(
            "accept_invite_to_embargo_on_case: cannot determine case from "
            "invite '%s'",
            request.invite_id,
        )
        return None
    return dl.read(context_id)


class CreateEmbargoEventReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateEmbargoEventReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateEmbargoEventReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.embargo_id,
            request.embargo,
            "EmbargoEvent",
            request.activity_id,
        )


class AddEmbargoEventToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddEmbargoEventToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AddEmbargoEventToCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.embargo.announce_teardown_tree import (
            add_embargo_to_case_tree,
        )

        request = self._request
        embargo_id = request.embargo_id
        case_id = request.case_id
        if embargo_id is None or case_id is None:
            logger.warning(
                "add_embargo_event_to_case: missing embargo_id or case_id"
            )
            return

        tree = add_embargo_to_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
            sync_port=self._sync_port,
        )

        if result.status != Status.SUCCESS:
            logger.debug(
                "add_embargo_event_to_case: BT did not fully succeed for"
                " embargo '%s' on case '%s' (msg: '%s')",
                embargo_id,
                case_id,
                result.feedback_message,
            )


class RemoveEmbargoEventFromCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RemoveEmbargoEventFromCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: RemoveEmbargoEventFromCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.embargo.announce_teardown_tree import (
            remove_embargo_from_case_tree,
        )

        request = self._request
        embargo_id = request.embargo_id
        case_id = request.case_id
        if embargo_id is None or case_id is None:
            logger.warning(
                "remove_embargo_from_case: missing embargo_id or case_id"
            )
            return

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "remove_embargo_from_case: missing receiving_actor_id"
                " — skipping"
            )
            return

        # The tree embeds the guarded commit as its final step (ADR-0021,
        # CLP-10-002, CLP-10-003).  Running it with actor_id=receiving_actor_id
        # means CheckIsCaseManagerNode naturally fires only when the receiving
        # actor holds the CASE_MANAGER role — no identity comparison in Python.
        tree = remove_embargo_from_case_tree(
            case_id=case_id, embargo_id=embargo_id
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )

        if result.status != Status.SUCCESS:
            logger.debug(
                "remove_embargo_from_case: BT did not succeed for"
                " embargo '%s' on case '%s' (msg: '%s')",
                embargo_id,
                case_id,
                result.feedback_message,
            )


class AnnounceEmbargoEventToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceEmbargoEventToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AnnounceEmbargoEventToCaseReceivedEvent = request

    def execute(self) -> None:
        logger.info(
            "Received embargo announcement '%s' — no receiver-side state"
            " change required",
            self._request.activity_id,
        )


class InviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: InviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.embargo.announce_teardown_tree import (
            invite_to_embargo_on_case_tree,
        )

        request = self._request
        invitee_id = request.receiving_actor_id or ""
        case_id = request.context_id or ""
        invite_id = request.activity_id

        if not invite_id:
            logger.warning("invite_to_embargo_on_case: missing activity_id")
            return

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "invite_to_embargo_on_case: missing receiving_actor_id"
                " — skipping"
            )
            return

        # EMB-01-002: MUST NOT process EP when P/X/A is set; MUST emit ER.
        if case_id and _pxa_embargo_ineligible(self._dl, case_id):
            logger.info(
                "invite_to_embargo_on_case: P/X/A set on case '%s'"
                " — rejecting EP '%s' (EMB-01-002)",
                case_id,
                invite_id,
            )
            if self._trigger_activity is not None:
                _idempotent_create(
                    self._dl,
                    request.activity_type,
                    invite_id,
                    request.activity,
                    "InviteToEmbargoOnCase",
                    invite_id,
                )
                reject_id, _ = self._trigger_activity.reject_embargo(
                    proposal_id=invite_id,
                    case_id=case_id,
                    actor=receiving_actor_id,
                    to=[request.actor_id],
                )
                add_activity_to_outbox(receiving_actor_id, reject_id, self._dl)
            else:
                logger.warning(
                    "invite_to_embargo_on_case: trigger_activity unavailable"
                    " — ER not emitted for EP '%s' on case '%s'",
                    invite_id,
                    case_id,
                )
            return

        # Single BT execution under receiving_actor_id (ADR-0022 / CLP-10-005).
        # invitee_id is threaded into the tree as a node constructor arg so
        # OptionalLookupParticipantNode looks up the correct participant even
        # when receiving_actor_id != invitee_id (e.g. CaseActor processing
        # the invite).  The embedded guarded-commit branch fires naturally
        # when the receiving actor holds CVDRole.CASE_MANAGER.
        tree = invite_to_embargo_on_case_tree(
            case_id=case_id,
            invitee_id=invitee_id,
            invite_id=invite_id,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )

        if result.status != Status.SUCCESS:
            logger.debug(
                "invite_to_embargo_on_case: BT did not fully succeed for"
                " invite '%s' (msg: '%s')",
                invite_id,
                result.feedback_message,
            )


class AcceptInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.embargo.announce_teardown_tree import (
            accept_invite_to_embargo_tree,
        )

        request = self._request
        embargo_id = request.embargo_id
        if embargo_id is None:
            logger.error(
                "accept_invite_to_embargo_on_case: missing embargo_id on request"
            )
            return

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "accept_invite_to_embargo_on_case: missing receiving_actor_id"
                " — skipping"
            )
            return

        _case = _resolve_case_for_embargo_acceptance(self._dl, request)
        if not is_case_model(_case):
            logger.error("accept_invite_to_embargo_on_case: case not found")
            return

        case_id = _case.id_
        accepting_actor_id = request.actor_id
        invite_id = request.invite_id or ""

        # EMB-02-002: MUST NOT process EA to transition EM to Active when P/X/A
        # is set; MUST emit ER instead.
        if _pxa_embargo_ineligible(self._dl, case_id):
            logger.info(
                "accept_invite_to_embargo_on_case: P/X/A set on case '%s'"
                " — rejecting EA (EMB-02-002)",
                case_id,
            )
            if self._trigger_activity is not None and invite_id:
                reject_id, _ = self._trigger_activity.reject_embargo(
                    proposal_id=invite_id,
                    case_id=case_id,
                    actor=receiving_actor_id,
                    to=[request.actor_id],
                )
                add_activity_to_outbox(receiving_actor_id, reject_id, self._dl)
            else:
                logger.warning(
                    "accept_invite_to_embargo_on_case: trigger_activity"
                    " unavailable or missing invite_id — ER not emitted"
                    " for EA on case '%s'",
                    case_id,
                )
            return

        # Single BT execution under receiving_actor_id (ADR-0022 / CLP-10-005).
        # accepting_actor_id is threaded into the tree as a node constructor arg
        # so RecordParticipantAcceptanceNode records acceptance for the correct
        # actor even when receiving_actor_id != accepting_actor_id (e.g. the
        # CaseActor processing an Accept sent by the invitee).  The embedded
        # guarded-commit branch fires naturally when the receiving actor holds
        # CVDRole.CASE_MANAGER.
        tree = accept_invite_to_embargo_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=accepting_actor_id,
            invite_id=invite_id,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )

        if result.status != Status.SUCCESS:
            logger.debug(
                "accept_invite_to_embargo_on_case: BT did not fully succeed for"
                " embargo '%s' on case '%s' (msg: '%s')",
                embargo_id,
                case_id,
                result.feedback_message,
            )


class RejectInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectInviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: RejectInviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> None:
        from py_trees.common import Status

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.embargo.announce_teardown_tree import (
            reject_invite_to_embargo_tree,
        )

        request = self._request
        rejecting_actor_id = request.actor_id
        invite_id = request.invite_id

        logger.info(
            "Actor '%s' rejected embargo proposal '%s'",
            rejecting_actor_id,
            invite_id,
        )

        # Extract case and embargo IDs from the stored invite activity.
        case_id: str | None = None
        embargo_id: str | None = None
        if invite_id:
            invite = self._dl.read(invite_id)
            if invite is not None:
                case_id = _as_id(getattr(invite, "context", None))
                embargo_id = _as_id(getattr(invite, "object_", None))

        if not case_id:
            logger.warning(
                "reject_invite_to_embargo_on_case: cannot resolve case_id"
            )
            return

        tree = reject_invite_to_embargo_tree(
            case_id=case_id,
            rejecting_actor_id=rejecting_actor_id,
            invite_id=invite_id or "",
            embargo_id=embargo_id,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )

        if result.status != Status.SUCCESS:
            logger.debug(
                "reject_invite_to_embargo_on_case: BT did not fully succeed for"
                " invite '%s' on case '%s' (msg: '%s')",
                invite_id,
                case_id,
                result.feedback_message,
            )
