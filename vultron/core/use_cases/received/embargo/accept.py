"""Received ``Accept(Invite(EmbargoEvent))`` (EA, EC) and late-Accept routing."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    accept_invite_to_embargo_tree,
    embargo_admission_backfill_tree,
)
from vultron.core.behaviors.embargo.expiry_tree import (
    IS_EXPIRED_KEY,
    create_honour_late_accept_tree,
    create_invite_expiry_tree,
    create_noop_ledger_entry_tree,
)
from vultron.core.behaviors.embargo.rsvp_stamp import (
    stamp_invite_rsvp_deadline,
)
from vultron.core.models._helpers import _as_id, claimed_published_iso
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.em import EM
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
from vultron.errors import VultronNotFoundError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    exempt,
)

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


class AcceptInviteToEmbargoOnCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4074", "no sender check for embargo accept"
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteToEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AcceptInviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._actor_config = actor_config

    def _pxa_refusal(
        self,
        *,
        case_id: str,
        invite_id: str,
        receiving_actor_id: str,
        accepting_actor_id: str,
    ) -> "HandlerResult | None":
        """Return a refusal if P/X/A is set, otherwise ``None`` (EMB-02-002)."""
        if not pxa_embargo_ineligible(self._dl, case_id):
            return None
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
                recipient_id=accepting_actor_id,
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

    def _run_expiry_tree(
        self,
        *,
        case_id: str,
        accepting_actor_id: str,
        invite_id: str,
        embargo_id: str,
        receiving_actor_id: str,
        now: "datetime",
    ) -> dict[str, object]:
        """Run the gated expiry evaluation; extracted for CLP-10-005 (ADR-0022)."""
        expiry_out: dict[str, object] = {}
        expiry_tree = create_invite_expiry_tree(
            case_id=case_id,
            invitee_id=accepting_actor_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            published=claimed_published_iso(self._request.activity),
            now=now,
            result_out=expiry_out,
        )
        BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(tree=expiry_tree, actor_id=receiving_actor_id)
        return expiry_out

    def _commit_noop_ledger_entry(
        self,
        *,
        case_id: str,
        invite_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        receiving_actor_id: str,
    ) -> None:
        """Commit the EMB-17-004 no-op acknowledgement entry (ADR-0118, RSH-08-004).

        Gated on CASE_MANAGER (BT-17-001): only the CASE_MANAGER commits the
        no-op entry.  A non-manager receiving the same late Accept is refused
        by the normal Accept path; this method must never be called for it.
        The gate is the belt-and-suspenders guard that ensures the ledger
        integrity invariant is never accidentally violated if the caller
        ordering changes.
        """
        tree = create_noop_ledger_entry_tree(
            case_id=case_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            accepting_actor_id=accepting_actor_id,
            published=claimed_published_iso(self._request.activity),
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
        )
        applied_or_raise(tree, result, label="CommitNoopLedgerEntryBT")

    def _handle_emb17_routing(
        self,
        *,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        receiving_actor_id: str,
        invite_id: str,
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
            # AC-2 of #2213: current embargo still matches — honour.
            # Commit the honour entry first so replicas learn the participant
            # became SIGNATORY (RSH-08-004, ADR-0118, CLP-10-006).  The tree
            # is gated on CASE_MANAGER (BT-17-001).
            honour_tree = create_honour_late_accept_tree(
                case_id=case_id,
                accepting_actor_id=accepting_actor_id,
                invite_id=invite_id,
                embargo_id=embargo_id,
                published=claimed_published_iso(self._request.activity),
            )
            result = BTBridge(
                datalayer=self._dl,
                wire_render_port=self._wire_render_port,
                sync_port=self._sync_port,
            ).execute_with_setup(
                tree=honour_tree,
                actor_id=receiving_actor_id,
            )
            applied_or_raise(honour_tree, result, label="HonourLateAcceptBT")
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
                # The re-invite is a fresh ask, so it carries a fresh deadline
                # the manager records (ASK-03-004, CM-28-012, CM-28-013);
                # the lapsed one would lapse it again on the next answer.
                try:
                    stamp = stamp_invite_rsvp_deadline(
                        self._dl, active_embargo_id, self._actor_config
                    )
                except VultronNotFoundError as exc:
                    # The case names this embargo as active, so a missing
                    # record is the manager's own store's fault (ADR-0087).
                    raise RuntimeError(
                        f"cannot stamp the re-invite to embargo"
                        f" '{active_embargo_id}' on case '{case_id}': {exc}"
                    ) from exc
                new_invite_id, _ = self._trigger_activity.propose_embargo(
                    embargo_id=active_embargo_id,
                    case_id=case_id,
                    actor=actor_id,
                    to=[accepting_actor_id],
                    rsvp_deadline=stamp.rsvp_deadline,
                    published=stamp.published,
                    min_rsvp_window=stamp.min_rsvp_window,
                )
                add_activity_to_outbox(actor_id, new_invite_id, self._dl)
                EmbargoLifecycle(persistence=self._dl).record_embargo_invite(
                    case_id=case_id,
                    invitee_id=accepting_actor_id,
                    rsvp_deadline=stamp.rsvp_deadline,
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
            # change (EMB-17-004, ADR-0118).  In EXITED the termination cascade
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
            # Commit so replicas can replay (RSH-08-004, ADR-0118).
            self._commit_noop_ledger_entry(
                case_id=case_id,
                invite_id=invite_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
                receiving_actor_id=receiving_actor_id,
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
        # ADR-0118).
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
        if (
            pxa_refusal := self._pxa_refusal(
                case_id=case_id,
                invite_id=invite_id,
                receiving_actor_id=receiving_actor_id,
                accepting_actor_id=accepting_actor_id,
            )
        ) is not None:
            return pxa_refusal

        # Expiry eval gated on CASE_MANAGER (CM-28-014, BT-17-001, CLP-10-005).
        expiry_out = self._run_expiry_tree(
            case_id=case_id,
            accepting_actor_id=accepting_actor_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            receiving_actor_id=receiving_actor_id,
            now=datetime.now(tz=UTC),
        )

        if bool(expiry_out.get(IS_EXPIRED_KEY)):
            # CM-28-009: expiry entry already committed by the tree above.
            # Route via EMB-17 compatibility branches.
            self._handle_emb17_routing(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
                receiving_actor_id=receiving_actor_id,
                invite_id=invite_id,
            )
            return HandlerResult.applied()

        # Normal path: invite still open.  accepting_actor_id is passed so the
        # node records acceptance for the right actor when receiving != accepting.
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
