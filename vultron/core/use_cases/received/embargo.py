"""Use cases for embargo management activities."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    accept_invite_to_embargo_tree,
    add_embargo_to_case_tree,
    embargo_admission_backfill_tree,
    invite_to_embargo_on_case_tree,
    reject_invite_to_embargo_tree,
    remove_embargo_from_case_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    EmbargoProposalNotYetRecordedNode,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    ALREADY_DECLINED_PREFIX,
)
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import _as_id, claimed_published_iso
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    AddEmbargoEventToCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import same_actor_id
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.cs import (
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC_Trigger
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    add_activity_to_outbox,
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    node_failed,
    not_case_manager_refusal,
    verdict_from_bt,
)
from vultron.core.use_cases.received._pending_refusal import (
    close_refused_embargo_proposal,
)
from vultron.core.use_cases.triggers._helpers import (
    _prepare_delegated_context,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronProtocolViolationError,
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
    request: InviteToEmbargoOnCaseReceivedEvent, invite_id: str
) -> str:
    """Return the invitee of an ``Invite(EmbargoEvent)``: its sole ``to``.

    The invitee is a *message subject*, read from the message and never from
    the store it reached (ADR-0022, CLP-10-015).  Every emitter sends one
    recipient — a participant to the CASE_MANAGER, the CASE_MANAGER to one
    participant per relayed Invite (EP-09-002) — so an Invite naming none or
    several is a misrouting, refused rather than guessed at (EP-09-010).  The
    recipient is returned in its canonical spelling, so a trailing slash still
    names the actor (#2667), and two spellings of one actor are one recipient.

    Raises:
        VultronProtocolViolationError: ``to`` names no recipient or more
            than one; the message gives the count.
    """
    invitee_id = request.invitee_id
    if invitee_id is None:
        raise VultronProtocolViolationError(
            f"Invite(EmbargoEvent) '{invite_id}' names"
            f" {len(request.to_recipients)} 'to' recipients; its invitee is"
            " its sole recipient, so it is refused as a misrouting"
            " (EP-09-010, OX-08-001)"
        )
    return invitee_id


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


def resolve_proposer_id(
    request: InviteToEmbargoOnCaseReceivedEvent, dl: CasePersistence
) -> str:
    """Return the actor whose terms a received ``Invite(EmbargoEvent)`` carries.

    The proposer is the Invite's ``actor`` — or its ``attributedTo`` when the
    proposal was itself relayed, since a relayed Invite is sent as the
    CASE_MANAGER with the proposer attributed (CM-24-001, CM-24-002).  The
    CASE_MANAGER adjudicating the proposal records *this* actor's consent to
    the terms (ADR-0093) and excludes it from the relay (EP-09-002).

    Only a relay may attribute: ``attributedTo`` is honoured when the Invite's
    ``actor`` holds ``CVDRole.CASE_MANAGER`` for the case and ignored
    otherwise, so a participant cannot have a third party's consent recorded
    — or that party left out of the Invites — by naming it on its own
    proposal (no identity spoofing on the received side, PCR-08-010).
    """
    attributed_to = request.activity.attributed_to
    if not attributed_to:
        return request.actor_id
    case = dl.read_case(request.context_id) if request.context_id else None
    if case is None:
        logger.warning(
            "invite_to_embargo_on_case: invite '%s' from '%s' attributes its"
            " proposal to '%s', but this store holds no case '%s' to resolve"
            " the CASE_MANAGER from — treating the sender as the proposer",
            request.activity_id,
            request.actor_id,
            attributed_to,
            request.context_id,
        )
        return request.actor_id
    if request.actor_id == resolve_case_manager_id(case, dl):
        return attributed_to
    logger.warning(
        "invite_to_embargo_on_case: invite '%s' from '%s' attributes its"
        " proposal to '%s', but only the CASE_MANAGER relays — treating the"
        " sender as the proposer",
        request.activity_id,
        request.actor_id,
        attributed_to,
    )
    return request.actor_id


def _store_invite_deadline(
    dl: CasePersistence,
    case_id: str,
    actor_id: str,
    rsvp_deadline: datetime,
) -> None:
    """Store RSVP deadline on the invitee's record for lazy lapse detection.

    A proposal addressed to the CASE_MANAGER names it as the sole recipient,
    but the manager adjudicates that Invite and is never its invitee
    (EP-09-010): its record gets no deadline, so the enforcer of invite
    expiry is never the record expiry is evaluated on (CM-28-003).
    """
    case = dl.read_case(case_id)
    if case is None:
        return
    manager_id = resolve_case_manager_id(case, dl)
    if manager_id is None:
        # No enforcer to tell from the invitee (CM-24-006, CM-28-003).
        raise VultronNotFoundError("CASE_MANAGER of case", case_id)
    if same_actor_id(actor_id, manager_id):
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
        self,
        dl: CasePersistence,
        request: CreateEmbargoEventReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CreateEmbargoEventReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        return _idempotent_create(
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
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AddEmbargoEventToCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request
        embargo_id = request.embargo_id
        case_id = request.case_id
        if embargo_id is None or case_id is None:
            logger.warning(
                "add_embargo_event_to_case: missing embargo_id or case_id"
            )
            return HandlerResult.refused(
                "Add(EmbargoEvent) is missing its embargo id or case id"
            )

        tree = add_embargo_to_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            # The commit fans the entry out to every participant replica
            # (EP-09-007, RSH-08-004); without the port nothing replays it.
            sync_port=self._sync_port,
        )
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

        verdict = verdict_from_bt(tree, result, label="AddEmbargoToCaseBT")
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict


class RemoveEmbargoEventFromCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RemoveEmbargoEventFromCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: RemoveEmbargoEventFromCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request
        embargo_id = request.embargo_id
        case_id = request.case_id
        if embargo_id is None or case_id is None:
            logger.warning(
                "remove_embargo_from_case: missing embargo_id or case_id"
            )
            return HandlerResult.refused(
                "Remove(EmbargoEvent) is missing its embargo id or case id"
            )

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
        bridge = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )

        verdict = verdict_from_bt(
            tree, result, label="RemoveEmbargoFromCaseBT"
        )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict


class AnnounceEmbargoEventToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceEmbargoEventToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AnnounceEmbargoEventToCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        logger.info(
            "Received embargo announcement '%s' — no receiver-side state"
            " change required",
            self._request.activity_id,
        )
        return HandlerResult.skipped("no receiver-side state change")


class InviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: InviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def _refuse_pxa_ineligible(
        self, case_id: str, invite_id: str, receiving_actor_id: str
    ) -> HandlerResult:
        """Refuse an EP on a public/exploited/attacked case and emit ER.

        EMB-01-002: MUST NOT process EP when P/X/A is set; MUST emit ER.
        """
        request = self._request
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
        return HandlerResult.refused(
            f"EMB-01-002: P/X/A set on case '{case_id}'; embargo"
            " proposal rejected"
        )

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.context_id or ""
        invite_id = request.activity_id

        if not invite_id:
            logger.warning("invite_to_embargo_on_case: missing activity_id")
            return HandlerResult.refused(
                "Invite(EmbargoEvent) is missing its activity id"
            )

        embargo_id = request.object_id
        if not embargo_id:
            logger.warning(
                "invite_to_embargo_on_case: invite '%s' names no embargo",
                invite_id,
            )
            return HandlerResult.refused(
                f"Invite(EmbargoEvent) '{invite_id}' names no embargo"
            )

        # The invitee is a subject the message names, not the actor whose
        # replica this is (ADR-0022): the Invite's sole `to` recipient.  An
        # Invite naming none or several is a misrouting, refused before the
        # P/X/A check answers it (EP-09-010, HP-01-005).
        try:
            invitee_id = resolve_invitee_id(request, invite_id)
        except VultronProtocolViolationError as exc:
            logger.warning(
                "invite_to_embargo_on_case: refusing invite '%s' from actor"
                " '%s' at receiving actor '%s': %s",
                invite_id,
                request.actor_id,
                request.receiving_actor_id,
                exc,
            )
            return HandlerResult.refused(str(exc))

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        if case_id and _pxa_embargo_ineligible(self._dl, case_id):
            return self._refuse_pxa_ineligible(
                case_id, invite_id, receiving_actor_id
            )

        # Single BT execution under receiving_actor_id (ADR-0022 / CLP-10-005).
        # invitee_id is threaded into the tree as a node constructor arg so
        # only the addressee's store answers the Invite, even when
        # receiving_actor_id != invitee_id.  The tree's two arms are
        # role-gated in-tree (BT-17-001): the CASE_MANAGER adjudicates and
        # relays the proposal of ``proposer_id`` (EP-09-001, EP-09-002); the
        # addressee's replica answers the Invite to the CASE_MANAGER and
        # writes no EM or consent state (EP-09-003).
        tree = invite_to_embargo_on_case_tree(
            case_id=case_id,
            invitee_id=invitee_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            proposer_id=resolve_proposer_id(request, self._dl),
            embargo=(
                request.object_
                if isinstance(request.object_, EmbargoEvent)
                else None
            ),
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )

        verdict = verdict_from_bt(
            tree, result, label="InviteToEmbargoOnCaseBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED and node_failed(
            tree, EmbargoProposalNotYetRecordedNode
        ):
            # The same Invite, delivered again (CLP-13-001, HP-01-003).
            verdict = HandlerResult.skipped(
                f"invite '{invite_id}' was already applied on case '{case_id}'"
            )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning("%s (invite '%s')", verdict.reason, invite_id)
            return verdict

        # Record embargo_id → invite_id in core state so accept/reject
        # trigger use cases can correlate without re-reading the Invite wire
        # activity (ADR-0035 DL-06).  A partial replica that holds no copy
        # of the case keeps the Invite and indexes nothing (Regime 2,
        # ADR-0087); CanAnswerEmbargoInviteNode has already warned.
        if case_id and embargo_id and invite_id:
            try:
                record_embargo_proposal_index(
                    self._dl, case_id, embargo_id, invite_id
                )
            except VultronNotFoundError:
                logger.info(
                    "invite '%s': case '%s' not held here — proposal not"
                    " indexed",
                    invite_id,
                    case_id,
                )

        # Store RSVP deadline on the invitee's participant record so
        # detect_and_apply_lapse() can check it without reading the stored
        # invite activity (CM-28, EP-07-001).
        if case_id and request.rsvp_deadline:
            _store_invite_deadline(
                self._dl, case_id, invitee_id, request.rsvp_deadline
            )
        return verdict


class AcceptInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
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

        tree = create_commit_log_entry_tree(
            case_id=case_id,
            object_id=invite_id or case_id,
            event_type="invite_to_embargo_on_case_lapsed",
            payload_snapshot={
                "type": "Lapse",
                "actor": accepting_actor_id,
                "context": case_id,
                # The lapse is CaseActor-synthesised (CM-28-009) but the
                # snapshot is attributed to the accepting participant, so its
                # claimed time must come from that participant's own clock —
                # the triggering Accept — not the CaseActor's.  Mixing the two
                # inside one actor's claimed stream is what CLP-15-003 reads as
                # a regression.  ``include_activity=True`` on the
                # ACCEPT_INVITE_TO_EMBARGO_ON_CASE registry entry guarantees the
                # activity is present; the fallback is defence in depth.
                "published": claimed_published_iso(self._request.activity),
                "object": {
                    "type": "Invite",
                    "id": invite_id or case_id,
                    "object": {"type": "EmbargoEvent", "id": embargo_id},
                },
            },
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
        )
        # The lapse is already applied to the replica; an unrecorded lapse
        # would diverge the replicas silently (CM-28-009).
        applied_or_raise(tree, result, label="CommitLapseLedgerEntryBT")

    def _backfill_admitted(
        self, *, case_id: str, receiving_actor_id: str
    ) -> None:
        tree = embargo_admission_backfill_tree(case_id)
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
        )
        applied_or_raise(tree, result, label="EmbargoAdmissionBackfillBT")

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

        if (
            em_state in (EM.ACTIVE, EM.REVISE)
            and active_embargo_id == embargo_id
        ):
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
            # CM-10-006: the honored Accept admits the participant to case
            # content, so send it what the embargo gate withheld.
            self._backfill_admitted(
                case_id=case_id, receiving_actor_id=receiving_actor_id
            )

        elif em_state in (EM.ACTIVE, EM.REVISE, EM.PROPOSED):
            # AC-3 of #2213: stale embargo — re-invite with current embargo.
            if (
                self._trigger_activity is not None
                and active_embargo_id
                and accepting_actor_id
            ):
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
            elif not active_embargo_id:
                logger.warning(
                    "accept_invite_to_embargo_on_case: late Accept for"
                    " case '%s' in EM.%s — no active embargo to re-invite to",
                    case_id,
                    em_state.name,
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

    def execute(self) -> HandlerResult:
        request = self._request
        embargo_id = request.embargo_id
        if embargo_id is None:
            logger.error(
                "accept_invite_to_embargo_on_case: missing embargo_id on request"
            )
            return HandlerResult.refused(
                "Accept(Invite(EmbargoEvent)) is missing its embargo id"
            )

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        _case = _resolve_case_for_embargo_acceptance(self._dl, request)
        if _case is None:
            logger.error("accept_invite_to_embargo_on_case: case not found")
            return HandlerResult.refused(
                f"Accept(Invite(EmbargoEvent)) names an unknown case"
                f" '{request.case_id}'"
            )

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
            return HandlerResult.refused(
                f"EMB-02-002: P/X/A set on case '{case_id}'; embargo"
                " acceptance rejected"
            )

        # Lazy lapse detection (AC-2 of #2212, CM-28, EP-07-001).
        now = datetime.now(tz=UTC)
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
            return HandlerResult.applied()

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
        bridge = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )

        verdict = verdict_from_bt(
            tree, result, label="AcceptInviteToEmbargoBT"
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            # Only the CASE_MANAGER records an answer; a replica learns it
            # from the ledger broadcast (BT-17-001, HP-01-005).
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict


class RejectInviteToEmbargoOnCaseReceivedUseCase:
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
        # The owner's Reject of a revision after disclosure terminates the
        # embargo, and the CASE_MANAGER tells the participants (EMB-04-002).
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        rejecting_actor_id = request.actor_id
        invite_id = request.invite_id

        logger.info(
            "'%s' rejected embargo '%s'", rejecting_actor_id, invite_id
        )
        close_refused_embargo_proposal(self._dl, request)  # EP-09-008
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

        tree = reject_invite_to_embargo_tree(
            case_id=case_id,
            rejecting_actor_id=rejecting_actor_id,
            invite_id=invite_id or "",
            embargo_id=embargo_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            # The commit fans the entry out to every participant replica
            # (EP-09-007, RSH-08-004); without the port nothing replays it.
            sync_port=self._sync_port,
        )
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

        verdict = verdict_from_bt(
            tree, result, label="RejectInviteToEmbargoBT"
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            # Only the CASE_MANAGER records an answer; a replica learns it
            # from the ledger broadcast (BT-17-001, HP-01-005).
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if (
            verdict.disposition is HandlerDisposition.REFUSED
            and ALREADY_DECLINED_PREFIX in (verdict.reason or "")
        ):
            # The node named this Reject a repeat of one already recorded
            # (#2255).  Keyed on the node's verdict, not on the store: a
            # DECLINED actor's Reject of an *unknown* embargo is still a
            # refusal (HP-01-003).
            verdict = HandlerResult.skipped(
                f"'{rejecting_actor_id}' already declined on case '{case_id}'"
            )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (invite '%s', case '%s')",
                verdict.reason,
                invite_id,
                case_id,
            )
        return verdict
