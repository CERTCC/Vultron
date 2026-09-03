"""Use cases for embargo management activities."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase

from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    AddEmbargoEventToCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.models._helpers import _as_id
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
    _idempotent_create,
    add_activity_to_outbox,
)
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.states.cs import (
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC_Trigger

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _pxa_embargo_ineligible(dl: CasePersistence, case_id: str) -> bool:
    """Return True when P/X/A is set on the case (EMB-01-002, EMB-02-002).

    Reads the case from the DataLayer; returns False (eligible) when the case
    cannot be resolved so normal processing can continue.
    """
    case = dl.read_case(case_id)
    if case is None:
        return False
    pxa_state = case.current_status.pxa.state
    return (
        is_pxa_public_aware(pxa_state)
        or is_pxa_exploit_public(pxa_state)
        or is_pxa_attacks_observed(pxa_state)
    )


def resolve_invitee_id(
    request: InviteToEmbargoOnCaseReceivedEvent,
    receiving_actor_id: str,
    invite_id: str,
) -> str:
    """Resolve whose participant record an embargo invitation applies to.

    The invitee is a *message subject*: it comes from the activity's ``to:``
    field, never from ``resolve_receiving_actor_id()`` (ADR-0022).  Resolution
    is by **addressee membership**, not by position, mirroring
    ``_is_primary_submit_report_recipient`` in ``received/report.py``:

    1. ``receiving_actor_id`` is among the recipients — the ordinary case.
       Preferring it is what makes a multi-recipient ``Invite`` correct in
       *every* recipient's replica rather than only the first one's, and it is
       canonical by construction, since ``inbox_handler`` normalises
       ``receiving_actor_id`` against ``activity.to`` (HP-09-001).
    2. Exactly one recipient, and it is not this store's actor — the CaseActor
       relaying on a participant's behalf, CLI dispatch, or log replay.
    3. Several recipients, none of them this store's actor — ambiguous.  Warn
       and degrade rather than guessing positionally.
    4. No recipient at all — an OX-08-001 violation upstream.  Warn and
       degrade.

    Cases 3 and 4 fall back to ``receiving_actor_id`` rather than dropping the
    invitation, because the guarded-commit branch lives inside the same single
    tree (ADR-0022): skipping the writes would also discard the canonical
    ledger commit this message is entitled to.  The WARNING is what the old
    ``invitee_id = receiving_actor_id`` fallback lacked.
    """
    recipients = request.to_recipients

    if receiving_actor_id in recipients:
        return receiving_actor_id

    if len(recipients) == 1:
        return recipients[0]

    if recipients:
        logger.warning(
            "invite_to_embargo_on_case: invite '%s' names %d recipients"
            " and none of them is receiving actor '%s' — cannot tell which"
            " participant this replica should apply the invitation to;"
            " treating the receiving actor as the subject",
            invite_id,
            len(recipients),
            receiving_actor_id,
        )
        return receiving_actor_id

    logger.warning(
        "invite_to_embargo_on_case: invite '%s' carries no 'to:' recipient"
        " (OX-08-001) — treating receiving actor '%s' as the invitation's"
        " subject",
        invite_id,
        receiving_actor_id,
    )
    return receiving_actor_id


def _resolve_case_for_embargo_acceptance(
    dl: CasePersistence, request: AcceptInviteToEmbargoOnCaseReceivedEvent
) -> "VulnerabilityCase | None":
    if request.case_id:
        return dl.read_case(request.case_id)

    logger.error(
        "accept_invite_to_embargo_on_case: missing case_id on request"
        " (invite '%s')",
        request.invite_id,
    )
    return None


def _record_embargo_proposal_index(
    dl: CasePersistence,
    case_id: str,
    embargo_id: str,
    proposal_id: str,
) -> None:
    """Record embargo_id → proposal_id in case core state (ADR-0035 DL-06)."""
    case = dl.read_case(case_id)
    if case is None:
        return
    if case.pending_embargo_proposal_index.get(embargo_id) == proposal_id:
        return
    case.pending_embargo_proposal_index[embargo_id] = proposal_id
    dl.save(case)


def _store_invite_deadline(
    dl: CasePersistence,
    case_id: str,
    actor_id: str,
    rsvp_deadline: datetime,
) -> None:
    """Store RSVP deadline on the participant record for lazy lapse detection."""
    case = dl.read_case(case_id)
    if case is None:
        return
    participant_id = case.actor_participant_index.get(actor_id)
    if not participant_id:
        return
    participant = dl.read(participant_id)
    if not isinstance(participant, CaseParticipant):
        return
    if participant.invite_rsvp_deadline == rsvp_deadline:
        return
    participant.invite_rsvp_deadline = rsvp_deadline
    dl.save(participant)


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
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
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

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

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
        case_id = request.context_id or ""
        invite_id = request.activity_id

        if not invite_id:
            logger.warning("invite_to_embargo_on_case: missing activity_id")
            return

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
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

        # The invitee is a subject the message names, not the actor whose
        # replica this is (ADR-0022).  Resolving it from `to:` is what keeps
        # the two apart: an EP dispatched into any store other than the
        # addressee's — CLI, replay, or a CaseActor relaying on a
        # participant's behalf — would otherwise write this participant's PEC
        # transition and RSVP deadline (CM-28-001, CM-28-003) onto the wrong
        # record.  Resolved after the P/X/A guard so the warnings it may emit
        # describe an invitation this use case is actually going to apply.
        invitee_id = resolve_invitee_id(request, receiving_actor_id, invite_id)

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

        # Record embargo_id → invite_id in core state so accept/reject
        # trigger use cases can correlate without re-reading the Invite wire
        # activity (ADR-0035 DL-06).
        embargo_id = request.object_id
        if case_id and embargo_id and invite_id:
            _record_embargo_proposal_index(
                self._dl, case_id, embargo_id, invite_id
            )

        # Store RSVP deadline on the invitee's participant record so
        # detect_and_apply_lapse() can check it without reading the stored
        # invite activity (CM-28, EP-07-001).
        if case_id and request.rsvp_deadline:
            _store_invite_deadline(
                self._dl, case_id, invitee_id, request.rsvp_deadline
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

    def _commit_lapse_ledger_entry(
        self,
        *,
        case_id: str,
        invite_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        receiving_actor_id: str,
        has_pec_change: bool,
    ) -> None:
        # CM-28-009: only commit when a PEC transition was actually applied to
        # keep the entry idempotent — a repeated late-Accept does not double-log.
        if not has_pec_change:
            return
        from vultron.core.behaviors.bridge import BTBridge

        tree = create_commit_log_entry_tree(
            case_id=case_id,
            object_id=invite_id or case_id,
            event_type="invite_to_embargo_on_case_lapsed",
            payload_snapshot={
                "type": "Lapse",
                "actor": accepting_actor_id,
                "context": case_id,
                # CLP-07-011: a snapshot without ``published`` is not the
                # verbatim AS2 activity, and the CLP-14 commit-boundary guard
                # rejects it (ISSUE-2824).  This is a CaseActor-synthesised
                # lapse event (CM-28-009), so its clock is the event time.
                "published": datetime.now(tz=timezone.utc).isoformat(),
                "object": {
                    "type": "Invite",
                    "id": invite_id or case_id,
                    "object": {"type": "EmbargoEvent", "id": embargo_id},
                },
            },
        )
        BTBridge(datalayer=self._dl).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            sync_port=self._sync_port,
        )

    def _handle_emb17_routing(
        self,
        *,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        receiving_actor_id: str,
        service: "EmbargoLifecycle",
    ) -> None:
        """EMB-17: late-Accept compatibility routing after a lapse is detected."""
        _fresh_case = self._dl.read_case(case_id)
        em_state = (
            _fresh_case.current_status.em.state
            if _fresh_case is not None
            else EM.NONE
        )
        active_embargo_id = (
            _as_id(_fresh_case.active_embargo)
            if _fresh_case is not None
            else None
        )

        if em_state == EM.ACTIVE and active_embargo_id == embargo_id:
            # AC-2 of #2213: current embargo still matches — honor.
            service.record_participant_consent(
                case_id=case_id,
                actor_id=accepting_actor_id,
                pec_trigger=PEC_Trigger.INVITE,
                embargo_id=embargo_id,
            )
            service.accept_embargo_invite(
                case_id=case_id,
                embargo_id=embargo_id,
                actor_id=accepting_actor_id,
                transition_mode=TransitionMode.OBSERVED,
            )
            logger.info(
                "accept_invite_to_embargo_on_case: late Accept honored"
                " for actor '%s' on case '%s' (embargo '%s' still active;"
                " EMB-17-001)",
                accepting_actor_id,
                case_id,
                embargo_id,
            )

        elif em_state in (EM.ACTIVE, EM.REVISE, EM.PROPOSED):
            # AC-3 of #2213: stale embargo — re-invite with current embargo.
            if (
                self._trigger_activity is not None
                and active_embargo_id
                and accepting_actor_id
            ):
                from vultron.core.use_cases.triggers._helpers import (
                    _prepare_delegated_context,
                )

                actor_id, _ = _prepare_delegated_context(
                    self._dl, case_id, receiving_actor_id
                )
                new_invite_id, _ = self._trigger_activity.propose_embargo(
                    embargo_id=active_embargo_id,
                    case_id=case_id,
                    actor=actor_id,
                    to=[accepting_actor_id],
                )
                add_activity_to_outbox(actor_id, new_invite_id, self._dl)
                service.record_participant_consent(
                    case_id=case_id,
                    actor_id=accepting_actor_id,
                    pec_trigger=PEC_Trigger.INVITE,
                    embargo_id=active_embargo_id,
                )
                logger.info(
                    "accept_invite_to_embargo_on_case: late Accept for"
                    " stale embargo '%s' on case '%s' — re-invited actor"
                    " '%s' to current embargo '%s' (EMB-17-002)",
                    embargo_id,
                    case_id,
                    accepting_actor_id,
                    active_embargo_id,
                )
            else:
                logger.warning(
                    "accept_invite_to_embargo_on_case: late Accept for"
                    " stale embargo on case '%s' — trigger_activity"
                    " unavailable, re-invite not emitted",
                    case_id,
                )

        else:
            # AC-4 of #2213: EM EXITED or NONE — ack no-op.
            service.record_participant_consent(
                case_id=case_id,
                actor_id=accepting_actor_id,
                pec_trigger=PEC_Trigger.RESET,
            )
            logger.info(
                "accept_invite_to_embargo_on_case: late Accept for case"
                " '%s' with EM '%s' — ack no-op; actor '%s' stays in"
                " case (EMB-17-003)",
                case_id,
                em_state,
                accepting_actor_id,
            )

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

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        _case = _resolve_case_for_embargo_acceptance(self._dl, request)
        if _case is None:
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

        # Lazy lapse detection (AC-2 of #2212, CM-28, EP-07-001).
        now = datetime.now(tz=timezone.utc)
        service = EmbargoLifecycle(persistence=self._dl)
        lapse_result = service.detect_and_apply_lapse(
            case_id=case_id,
            actor_id=accepting_actor_id,
            now=now,
        )

        if lapse_result.is_lapsed:
            # CM-28-009: author a distinct ledger entry for the lapse event
            # (CM-28-005) then route via EMB-17 compatibility branches.
            self._commit_lapse_ledger_entry(
                case_id=case_id,
                invite_id=invite_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
                receiving_actor_id=receiving_actor_id,
                has_pec_change=bool(lapse_result.participant_changes),
            )
            self._handle_emb17_routing(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
                receiving_actor_id=receiving_actor_id,
                service=service,
            )
            return

        # Normal path (invite still open): record acceptance via BT.
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

        case_id = request.case_id
        embargo_id = request.embargo_id

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
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
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
