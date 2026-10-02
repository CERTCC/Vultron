"""Received ``Accept(Invite(EmbargoEvent))`` (EA, EC) and late-Accept routing."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    accept_invite_to_embargo_tree,
    embargo_admission_backfill_tree,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import _as_id, claimed_published_iso
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.rsvp_deadline import (
    INVITE_EXPIRED_EVENT_TYPE,
    INVITE_EXPIRED_SNAPSHOT_TYPE,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC_Trigger
from vultron.core.use_cases._helpers import (
    add_activity_to_outbox,
    resolve_receiving_actor_id,
    unaddressed_copy_refusal,
)
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    not_case_manager_refusal,
    verdict_from_bt,
)
from vultron.core.use_cases.received._embargo_pxa import (
    pxa_embargo_ineligible,
    queue_pxa_reject,
)
from vultron.core.use_cases.triggers._helpers import (
    _prepare_delegated_context,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


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


def _needs_reinvite_to_accept(
    dl: CasePersistence, case: "VulnerabilityCase", actor_id: str
) -> bool:
    """True when *actor_id*'s consent must be re-invited before ACCEPT.

    ``ACCEPT`` is legal from ``EXPIRED`` (ADR-0117) but not from ``DECLINED``
    (CM-18-003); a declined participant whose late Accept is honoured goes
    ``DECLINED → INVITED → SIGNATORY``.  An actor with no readable
    participant record needs nothing here: the consent write that follows
    warns and skips it.
    """
    participant_id = case.actor_participant_index.get(actor_id)
    participant = dl.read(participant_id) if participant_id else None
    if not isinstance(participant, CaseParticipant):
        return False
    return not participant.accepts_pec_trigger(
        PEC_Trigger.ACCEPT
    ) and participant.accepts_pec_trigger(PEC_Trigger.INVITE)


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

    def _commit_expiry_ledger_entry(
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
            event_type=INVITE_EXPIRED_EVENT_TYPE,
            payload_snapshot={
                "type": INVITE_EXPIRED_SNAPSHOT_TYPE,
                "actor": accepting_actor_id,
                "context": case_id,
                # The expiry is CASE_MANAGER-synthesised (CM-28-009) but the
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
        # The expiry is already applied to this store; an unrecorded expiry
        # would diverge the replicas silently (CM-28-009).
        applied_or_raise(tree, result, label="CommitExpiryLedgerEntryBT")

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
        """EMB-17: late-Accept compatibility routing after an invite expired."""
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
            # AC-2 of #2213: current embargo still matches — honor.  An
            # EXPIRED participant accepts directly (EXPIRED → SIGNATORY,
            # ADR-0117); one that declined is re-invited first, since ACCEPT
            # is not legal from DECLINED (CM-18-003).
            if _fresh_case is not None and _needs_reinvite_to_accept(
                self._dl, _fresh_case, accepting_actor_id
            ):
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
            # AC-4 of #2213: EM EXITED or NONE — ack no-op, no consent
            # change (EMB-17-004, ADR-0117).  In EXITED the termination cascade
            # already moved the participant to the terminal UNBOUND_EXITED; in
            # NONE an expired participant stays EXPIRED, which a later embargo
            # may re-invite.
            logger.info(
                "accept_invite_to_embargo_on_case: late Accept for case"
                " '%s' with EM '%s' — ack no-op; actor '%s' stays in"
                " case (EMB-17-004)",
                case_id,
                em_state,
                accepting_actor_id,
            )

    def execute(self) -> HandlerResult:
        request = self._request
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        embargo_id = request.embargo_id
        if embargo_id is None:
            logger.error(
                "accept_invite_to_embargo_on_case: missing embargo_id on request"
            )
            return HandlerResult.refused(
                "Accept(Invite(EmbargoEvent)) is missing its embargo id"
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

        # Door check before any tree or write, after the shape checks
        # that write nothing: an unaddressed copy is refused (HP-01-005,
        # ADR-0117).
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id,
                request,
                label="Accept(Invite(EmbargoEvent))",
            )
        ) is not None:
            return refusal

        # EMB-02-002: MUST NOT process EA to transition EM to Active when P/X/A
        # is set; MUST emit ER instead.
        if pxa_embargo_ineligible(self._dl, case_id):
            logger.info(
                "accept_invite_to_embargo_on_case: P/X/A set on case '%s'"
                " — rejecting EA (EMB-02-002)",
                case_id,
            )
            if invite_id:
                queue_pxa_reject(
                    self._dl,
                    self._trigger_activity,
                    invite_id=invite_id,
                    case_id=case_id,
                    actor_id=receiving_actor_id,
                    recipient_id=request.actor_id,
                    label="accept_invite_to_embargo_on_case",
                )
            else:
                logger.warning(
                    "accept_invite_to_embargo_on_case: missing invite_id"
                    " — ER not emitted for EA on case '%s'",
                    case_id,
                )
            return HandlerResult.refused(
                f"EMB-02-002: P/X/A set on case '{case_id}'; embargo"
                " acceptance rejected"
            )

        # Lazy invite-expiry detection (AC-2 of #2212, CM-28, EP-07-001).
        now = datetime.now(tz=UTC)
        service = EmbargoLifecycle(persistence=self._dl)
        expiry_result = service.detect_and_apply_expiry(
            case_id=case_id,
            actor_id=accepting_actor_id,
            now=now,
        )

        if expiry_result.is_expired:
            # CM-28-009: author a distinct ledger entry for the expiry event
            # (CM-28-005) then route via EMB-17 compatibility branches.
            self._commit_expiry_ledger_entry(
                case_id=case_id,
                invite_id=invite_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
                receiving_actor_id=receiving_actor_id,
                has_pec_change=bool(expiry_result.participant_changes),
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
