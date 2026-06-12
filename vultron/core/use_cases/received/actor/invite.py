"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.accept_invite_tree import (
    create_accept_invite_actor_to_case_tree,
)
from vultron.core.models.events.actor import (
    AcceptInviteActorToCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
)
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.use_cases._helpers import (
    _find_case_actor_id,
    _idempotent_create,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class InviteActorToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: InviteActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: InviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "InviteActorToCase",
            request.activity_id,
        )
        # MV-10-004: do NOT create a case from the stub target.  The stub
        # carries only {id, type} for identification; the full case details
        # arrive later in an AnnounceVulnerabilityCase activity (MV-10-003).
        case_stub_id = request.target_id
        if case_stub_id:
            logger.info(
                "InviteActorToCase: received invite with case stub '%s'."
                " Awaiting AnnounceVulnerabilityCase before creating case.",
                case_stub_id,
            )


class AcceptInviteActorToCaseReceivedUseCase:
    """CaseActor processes ``Accept(Invite(actor, case))`` from the invitee.

    Delegates all protocol-significant work to
    ``AcceptInviteActorToCaseBT`` via BTBridge.  The BT runs as the
    CaseActor (not the invitee), recording the invitee's participation in
    the CaseActor's own DataLayer without identity spoofing (PCR-08-010).

    BT-06-001, BT-15-001: all RM transitions, participant creation, case
    events, and outbox work live in leaf nodes of the BT.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteActorToCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteActorToCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        case_id = request.case_id
        invitee_id = request.invitee_id
        if case_id is None or invitee_id is None:
            logger.warning(
                "accept_invite_actor_to_case: missing case_id or invitee_id"
            )
            return

        # Resolve the CaseActor ID to use as the BT actor.
        # receiving_actor_id is set by the inbox adapter to the CaseActor's ID.
        # Fall back to _find_case_actor_id when dispatched outside the inbox
        # path (e.g. CLI, tests that do not set receiving_actor_id).
        actor_id = request.receiving_actor_id or _find_case_actor_id(
            self._dl, case_id
        )
        if actor_id is None:
            logger.warning(
                "accept_invite_actor_to_case: no CaseActor ID for case '%s'"
                " — BT will run without a named actor context",
                case_id,
            )
            actor_id = "unknown"

        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        ).execute_with_setup(
            tree=create_accept_invite_actor_to_case_tree(
                case_id=case_id,
                invitee_id=invitee_id,
            ),
            actor_id=actor_id,
            activity=request,
        )

        if result.status == Status.FAILURE:
            logger.debug(
                "accept_invite_actor_to_case: BT returned FAILURE for"
                " invitee '%s' case '%s': %s",
                invitee_id,
                case_id,
                result.feedback_message,
            )


class RejectInviteActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RejectInviteActorToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectInviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            request.actor_id,
            request.invite_id,
        )
