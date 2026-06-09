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
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.core.models.protocols import (
    PersistableModel,
    is_case_model,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort

logger = logging.getLogger(__name__)


def _commit_embargo_log_cascade(
    case_id: str | None,
    object_id: str | None,
    event_type: str,
    dl: CaseOutboxPersistence,
    receiving_actor_id: str | None,
    sync_port: "SyncActivityPort | None",
) -> None:
    """Commit a CaseLogEntry and fan it out to all case participants.

    Shared helper for all embargo received-side handlers that need to fire
    the ``commit_log_entry → fan_out`` cascade after accepting an embargo
    operation (PCR-08-003, PCR-08-004).

    Silently skips when *case_id* or *object_id* is ``None``, or when no
    CaseActor can be resolved.
    """
    from vultron.core.use_cases.received.actor import _find_case_actor_id
    from vultron.core.use_cases.triggers.sync import commit_log_entry_trigger

    if case_id is None or object_id is None:
        logger.warning(
            "embargo cascade: missing case_id or object_id"
            " — skipping log entry cascade (PCR-08-003)"
        )
        return

    # Resolve the CaseActor ID.  Only use receiving_actor_id if it
    # resolves to a Service (CaseActor) whose context matches case_id.
    # Some handlers (e.g. InviteToEmbargoOnCaseReceivedUseCase) set
    # receiving_actor_id to the invitee's actor ID; using that would
    # attribute the log entry to the wrong actor and exclude the wrong
    # recipient from fan-out.
    actor_id: str | None = None
    if receiving_actor_id is not None:
        obj = dl.read(receiving_actor_id)
        if (
            obj is not None
            and getattr(obj, "type_", None) == "Service"
            and str(getattr(obj, "context", None)) == case_id
        ):
            actor_id = receiving_actor_id
    if actor_id is None:
        actor_id = _find_case_actor_id(dl, case_id)
    if actor_id is None:
        logger.warning(
            "embargo cascade: cannot resolve CaseActor for case '%s'"
            " — skipping log entry cascade (PCR-08-003)",
            case_id,
        )
        return

    commit_log_entry_trigger(
        case_id=case_id,
        object_id=object_id,
        event_type=event_type,
        actor_id=actor_id,
        dl=dl,
        sync_port=sync_port,
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

        tree = add_embargo_to_case_tree(case_id=case_id, embargo_id=embargo_id)
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
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

        tree = remove_embargo_from_case_tree(
            case_id=case_id, embargo_id=embargo_id
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )

        if result.status != Status.SUCCESS:
            logger.debug(
                "remove_embargo_from_case: BT did not fully succeed for"
                " embargo '%s' on case '%s' (msg: '%s') — embargo may have"
                " been in proposed_embargoes only",
                embargo_id,
                case_id,
                result.feedback_message,
            )

        # Always commit a log entry regardless of BT result.  FAILURE means
        # the embargo was already cleared or only in proposed_embargoes —
        # both are non-error outcomes that still require fan-out (PCR-08-003).
        _commit_embargo_log_cascade(
            case_id=case_id,
            object_id=embargo_id,
            event_type="remove_embargo_event_from_case",
            dl=self._dl,
            receiving_actor_id=request.receiving_actor_id,
            sync_port=self._sync_port,
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
    ) -> None:
        self._dl = dl
        self._request: InviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port

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

        tree = invite_to_embargo_on_case_tree(
            case_id=case_id, invitee_id=invitee_id, invite_id=invite_id
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=invitee_id,
            activity=request,
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
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port

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

        _case = _resolve_case_for_embargo_acceptance(self._dl, request)
        if not is_case_model(_case):
            logger.error("accept_invite_to_embargo_on_case: case not found")
            return

        case_id = _case.id_
        accepting_actor_id = request.actor_id
        invite_id = request.invite_id or ""

        tree = accept_invite_to_embargo_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=accepting_actor_id,
            invite_id=invite_id,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
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
