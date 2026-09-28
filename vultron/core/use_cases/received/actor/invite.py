"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.accept_invite_tree import (
    create_accept_invite_actor_to_case_tree,
)
from vultron.core.behaviors.case.nodes.invite_participant import (
    CheckInviteeNotAlreadyParticipantNode,
)
from vultron.core.behaviors.case.invite_actor_to_case_received_tree import (
    create_invite_actor_to_case_received_tree,
    create_reject_invite_actor_to_case_received_tree,
)
from vultron.core.behaviors.narrative_log import log_invite_received
from vultron.core.models.events.actor import (
    AcceptInviteActorToCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
)
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import (
    _find_case_actor_id,
    _idempotent_create,
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    node_failed,
    not_case_manager,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _record_invite_trust_anchor(
    dl: "CaseOutboxPersistence", case_id: str, case_actor_id: str
) -> None:
    """Write a VultronPendingCaseInbox trust anchor for the inviting CASE_MANAGER.

    Called by the invitee path of InviteActorToCaseReceivedUseCase so that
    AnnounceVulnerabilityCaseReceivedUseCase can admit a subsequent Announce
    from the same actor even before the local case replica exists
    (PCR-03-004 path b, AC-2).

    First-invite-wins: if a record already exists with a case_actor_id, it is
    kept unchanged.  A record with case_actor_id=None (created by the pre-
    bootstrap queue for an earlier ledger entry) is updated with the sender.
    """
    pending_id = VultronPendingCaseInbox.build_id(case_id)
    existing = dl.read(pending_id)
    if not isinstance(existing, VultronPendingCaseInbox):
        dl.save(
            VultronPendingCaseInbox(
                case_id=case_id,
                case_actor_id=case_actor_id,
            )
        )
        logger.debug(
            "InviteActorToCase: trust anchor recorded for case '%s'",
            case_id,
        )
    elif existing.case_actor_id is None:
        dl.save(existing.model_copy(update={"case_actor_id": case_actor_id}))
        logger.debug(
            "InviteActorToCase: trust anchor added to existing pending"
            " record for case '%s'",
            case_id,
        )


class InviteActorToCaseReceivedUseCase:
    """Handle an incoming Invite(Actor, Case) activity.

    Two delivery paths use this use case (CLP-10-001, ADR-0021):

    1. **Invitee inbox** — ``receiving_actor_id`` is absent (``None``).
       The invited actor stores the Invite idempotently and logs the case-stub
       ID per MV-10-004.  No ledger commit occurs; that is reserved for the
       CaseActor.

    2. **CaseActor inbox** (self-delivered ``cc:`` copy) — ``receiving_actor_id``
       is set by the inbox adapter to the CaseActor's URI.  The BT runs via
       BTBridge; ``GuardedCommitCaseLedgerEntryBT`` inside
       ``InviteActorToCaseReceivedBT`` commits the canonical
       ``CaseLedgerEntry`` only when the receiving actor holds
       ``CVDRole.CASE_MANAGER`` (CLP-10-006).  ``StoreActivityNode`` in the
       BT's effect nodes handles idempotent storage for this path.

    Note: when the trigger could not resolve the authority's address
    (``_find_case_actor_id`` returned ``None``), the outbound Invite is sent
    without a ``cc:`` field and no self-delivery occurs, so no ledger entry is
    committed.  Under ADR-0088 that ``None`` means only "no resolvable address"
    — a case with no CASE_MANAGER on its roster and no recorded
    ``ReportCaseLink``.  It is *not* the older ADR-0021 reading, in which a
    separate CaseActor entity could be absent while the role was held: there is
    no such entity, and an ordinary participant enacting ``CVDRole.CASE_MANAGER``
    is the authority and does resolve here (ARCH-24-004, CM-02-011).

    The ``sync_port`` kwarg is injected when ``INVITE_ACTOR_TO_CASE`` is in
    ``_SYNC_PORT_SEMANTICS`` so ``CommitCaseLedgerEntryNode`` can fan out
    via ``sync_port`` (SYNC-02-002).
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteActorToCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: InviteActorToCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        receiving_actor_id = request.receiving_actor_id

        if receiving_actor_id is None:
            # Invitee path: this branch is deliberately NOT converted to
            # resolve_receiving_actor_id() because the receiving actor is the
            # *invitee* — an actor who does not yet own the case store.  Routing
            # work into the store owner would silently create state in the wrong
            # actor's database.  The stub-creation and log below are safe because
            # they use self._dl directly (the caller's store), not an actor-scoped
            # DataLayer.  (See issue #2446 AC-2.)
            # Invitee path: store idempotently and log the case-stub reference.
            stored = _idempotent_create(
                self._dl,
                request.activity_type,
                request.activity_id,
                request.activity,
                "InviteActorToCase",
                request.activity_id,
            )
            # MV-10-004: do NOT create a case from the stub target.  Full case
            # details arrive later in an AnnounceVulnerabilityCase (MV-10-003).
            case_stub_id = request.target_id
            if case_stub_id:
                # SL-04-001/SL-04-006: the invitee's receipt of the invite is a
                # protocol milestone and must read in human terms at INFO.
                log_invite_received(
                    logger,
                    request.object_id or "<unknown>",
                    case_stub_id,
                    request.actor_id or "<unknown>",
                )
                logger.debug(
                    "InviteActorToCase: received invite with case stub '%s'."
                    " Awaiting AnnounceVulnerabilityCase before creating case.",
                    case_stub_id,
                )
                # Record the invite sender as the expected CASE_MANAGER for
                # this case so AnnounceVulnerabilityCaseReceivedUseCase can
                # admit a subsequent Announce before the case replica exists
                # (PCR-03-004 trust anchor, AC-2).
                if request.actor_id:
                    _record_invite_trust_anchor(
                        self._dl, case_stub_id, request.actor_id
                    )
            return stored

        # CaseActor self-delivery path (CLP-10-001): the BT handles idempotent
        # storage via StoreActivityNode and commits the canonical CaseLedgerEntry
        # via GuardedCommitCaseLedgerEntryBT (CLP-10-006).
        case_id = request.target_id or ""
        tree = create_invite_actor_to_case_received_tree(
            invite_id=request.activity_id,
            invite_obj=request.activity,
            case_id=case_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )
        verdict = verdict_from_bt(
            tree, result, label="InviteActorToCaseReceivedBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "InviteActorToCaseReceivedUseCase: invite '%s' refused: %s",
                request.activity_id,
                verdict.reason,
            )
        return verdict


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
        sync_port: SyncActivityPort,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteActorToCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        invitee_id = request.invitee_id
        if case_id is None or invitee_id is None:
            logger.warning(
                "accept_invite_actor_to_case: missing case_id or invitee_id"
            )
            return HandlerResult.refused(
                "Accept(Invite) is missing its case id or invitee id"
            )

        # Resolve the CaseActor ID to use as the BT actor.
        # receiving_actor_id is set by the inbox adapter to the CaseActor's ID.
        # Fall back to _find_case_actor_id when dispatched outside the inbox
        # path (e.g. CLI, tests that do not set receiving_actor_id).
        actor_id = request.receiving_actor_id or _find_case_actor_id(
            self._dl, case_id
        )
        if actor_id is None:
            # Not a failure: no dedicated CaseActor is a legitimate topology
            # (ADR-0021), and the store we hold is the receiving actor's own.
            actor_id = resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            )
            logger.debug(
                "accept_invite_actor_to_case: no CaseActor for case '%s' —"
                " running as the store's own actor '%s'",
                case_id,
                actor_id,
            )

        tree = create_accept_invite_actor_to_case_tree(
            case_id=case_id,
            invitee_id=invitee_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        ).execute_with_setup(
            tree=tree,
            actor_id=actor_id,
            activity=request,
            sync_port=self._sync_port,
        )

        # The idempotency guard fails both for a fully joined invitee (a
        # duplicate, CLP-13-001) and for a case this actor does not hold.
        if node_failed(tree, CheckInviteeNotAlreadyParticipantNode):
            if self._dl.read(case_id) is None:
                verdict = HandlerResult.refused(f"unknown case '{case_id}'")
            else:
                return HandlerResult.skipped(
                    f"'{invitee_id}' already joined case '{case_id}'"
                )
        else:
            verdict = verdict_from_bt(
                tree, result, label="AcceptInviteActorToCaseBT"
            )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "accept_invite_actor_to_case: refused invitee '%s' case"
                " '%s': %s",
                invitee_id,
                case_id,
                verdict.reason,
            )
        return verdict


class RejectInviteActorToCaseReceivedUseCase:
    """CaseActor processes ``Reject(Invite(actor, case))`` from an invitee.

    Commits a canonical ``CaseLedgerEntry`` for the received rejection
    (``("Reject", "Invite")`` in ``_CANONICAL_PAYLOAD_SIGNATURES``) via BTBridge.
    The CaseActor records that the invitee declined the invitation.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectInviteActorToCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: RejectInviteActorToCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            request.actor_id,
            request.invite_id,
        )
        case_id = request.case_id or ""
        if not case_id:
            logger.warning(
                "RejectInviteActorToCase: missing case_id for invite '%s'"
                " — refusing",
                request.invite_id,
            )
            return HandlerResult.refused(
                "Reject(Invite) is missing its case id"
            )

        # The store we hold *is* the receiving actor's, so this resolves
        # without scanning for an actor object (ADR-0073).
        actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_reject_invite_actor_to_case_received_tree(
            case_id=case_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        ).execute_with_setup(
            tree=tree,
            actor_id=actor_id,
            activity=request,
            sync_port=self._sync_port,
        )
        verdict = verdict_from_bt(
            tree, result, label="RejectInviteActorToCaseReceivedBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "RejectInviteActorToCaseReceivedUseCase: invite '%s' refused:"
                " %s",
                request.invite_id,
                verdict.reason,
            )
            return verdict
        if not_case_manager(tree):
            # The gate also reads a case we do not hold as "not the manager".
            if self._dl.read(case_id) is None:
                return HandlerResult.refused(f"unknown case '{case_id}'")
            # Recording the decline is the CASE_MANAGER's job alone.
            return HandlerResult.skipped(
                f"not the CASE_MANAGER of case '{case_id}'"
            )
        return verdict
