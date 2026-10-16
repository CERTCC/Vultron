"""Received ``Accept(Invite(EmbargoEvent))`` (EA, EC) and late-Accept routing."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.embargo.admission_backfill_tree import (
    embargo_admission_backfill_tree,
)
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    accept_invite_to_embargo_tree,
)
from vultron.core.behaviors.embargo.expiry_tree import (
    IS_EXPIRED_KEY,
    create_honour_late_accept_tree,
    create_noop_ledger_entry_tree,
    create_reinvite_stale_accepter_tree,
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
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    embargo_answer_repeat_verdict,
    not_case_manager_refusal,
    verdict_from_bt,
)
from vultron.core.use_cases.received._embargo_pxa import (
    pxa_embargo_ineligible,
    run_pxa_refusal_tree,
)
from vultron.core.use_cases.received._sender_preflight import (
    door_refusal,
    repeat_answer_skip,
)
from vultron.errors import VultronBTInternalError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext

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
    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.INVITEE
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
        skipped = run_pxa_refusal_tree(
            self._dl,
            self._trigger_activity,
            self._wire_render_port,
            self._sync_port,
            invite_id=invite_id,
            case_id=case_id,
            actor_id=receiving_actor_id,
            recipient_id=accepting_actor_id,
            store_invite=False,
            activity=self._request,
            label="accept_invite_to_embargo_on_case",
        )
        if skipped is not None:
            return HandlerResult.skipped(
                f"EA for Invite '{invite_id}' on case '{case_id}' not"
                f" refused again: {skipped}"
            )
        return HandlerResult.refused(
            f"EMB-02-002: P/X/A set on case '{case_id}'; embargo"
            " acceptance rejected"
        )

    def _backfill_admitted(
        self, *, case_id: str, receiving_actor_id: str
    ) -> None:
        tree = embargo_admission_backfill_tree(case_id, self._actor_config)
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
        )
        applied_or_raise(tree, result, label="EmbargoAdmissionBackfillBT")

    def _commit_noop_ledger_entry(
        self,
        *,
        case_id: str,
        receiving_actor_id: str,
    ) -> None:
        """Commit the EMB-17-004 no-op acknowledgement entry (ADR-0118, RSH-08-004).

        The entry is the CASE_MANAGER's factory-built ``Ignore`` of the late
        Accept (CLP-07-013, VM-08-003), so the tree reads the received Accept
        from ``activity`` and builds it through ``trigger_activity``.

        Gated on CASE_MANAGER (BT-17-001): only the CASE_MANAGER commits the
        no-op entry.  A non-manager receiving the same late Accept is refused
        by the normal Accept path; this method must never be called for it.
        The gate is the belt-and-suspenders guard that ensures the ledger
        integrity invariant is never accidentally violated if the caller
        ordering changes.
        """
        tree = create_noop_ledger_entry_tree(case_id=case_id)
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=self._request,
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
        em_state = _fresh_case.em_state if _fresh_case is not None else EM.NONE
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
            # became a signatory (RSH-08-004, ADR-0118, CLP-10-006).  The tree
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
                # The AGREED row is the CASE_MANAGER's own Update entry,
                # built through the factory (ADR-0124).
                trigger_activity=self._trigger_activity,
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
                # The CASE_MANAGER-gated tree stamps a fresh deadline the
                # manager records (ASK-03-004, CM-28-012, CM-28-013), queues
                # the re-invite and then commits it (ADR-0119, BT-17-001);
                # the lapsed deadline would lapse it again.
                reinvite_tree = create_reinvite_stale_accepter_tree(
                    case_id=case_id,
                    embargo_id=active_embargo_id,
                    invitee_id=accepting_actor_id,
                    actor_config=self._actor_config,
                    answers=self._request.activity_id,
                )
                result = BTBridge(
                    datalayer=self._dl,
                    trigger_activity=self._trigger_activity,
                    wire_render_port=self._wire_render_port,
                    sync_port=self._sync_port,
                ).execute_with_setup(
                    tree=reinvite_tree,
                    actor_id=receiving_actor_id,
                )
                applied_or_raise(
                    reinvite_tree, result, label="ReinviteStaleAccepterBT"
                )
                logger.info(
                    "accept_invite_to_embargo_on_case: late Accept for"
                    " stale embargo '%s' on case '%s' — re-invited actor"
                    " '%s' to current embargo '%s' (EMB-17-003)",
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
            # change (EMB-17-004, ADR-0118).  In EXITED nothing can be consented
            # to any more; in NONE the embargo register is empty, so there is
            # no row to change — a timed-out participant's row for an earlier
            # embargo stays TIMED_OUT, and a later embargo may invite it.
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
                receiving_actor_id=receiving_actor_id,
            )

    def _route_late_accept(
        self,
        result: BTExecutionResult,
        *,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        receiving_actor_id: str,
        invite_id: str,
    ) -> HandlerResult:
        """Route an Accept the tree's clock decision found late (EMB-17).

        The tree's FAILURE is the expiry guard refusing the late Accept as
        an answer, which this routing replaces; an internal error is still
        the handler's to raise (ADR-0095).  The clock decision has already
        committed the expiry entry (CM-28-009), logged its refused commit,
        or found the row already closed, so nothing here commits it.
        """
        if result.internal_error:
            raise VultronBTInternalError(
                f"AcceptInviteToEmbargoBT: {result.feedback_message}"
            )
        self._handle_emb17_routing(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=accepting_actor_id,
            receiving_actor_id=receiving_actor_id,
            invite_id=invite_id,
        )
        return HandlerResult.applied()

    def execute(self) -> HandlerResult:
        request = self._request
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        # The invitee is read from the recorded Invite (EP-09-010), so an
        # Accept that names none has no invitee to be.
        embargo_id, invite_id = request.embargo_id, request.invite_id
        if embargo_id is None or not invite_id:
            missing = "embargo id" if embargo_id is None else "Invite id"
            logger.error(
                "accept_invite_to_embargo_on_case: missing %s on request",
                missing,
            )
            return HandlerResult.refused(
                f"Accept(Invite(EmbargoEvent)) is missing its {missing}"
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

        # Before any tree or write, since the P/X/A path below writes or
        # sends before the received tree runs: the case must not be fully closed
        # (CM-23-013), the copy must be addressed here (HP-01-005, ADR-0118),
        # and the sender must be the Invite's invitee (EP-09-010, HP-01-006).
        if (
            refusal := door_refusal(
                self._dl,
                receiving_actor_id,
                request,
                self.sender_entitlement,
                SenderCheckContext(
                    sender_id=accepting_actor_id,
                    case_id=case_id,
                    invite_id=invite_id,
                ),
                label="Accept(Invite(EmbargoEvent))",
                sync_port=self._sync_port,
            )
        ) is not None:
            return refusal

        if (
            repeat := repeat_answer_skip(
                self._dl,
                receiving_actor_id,
                case_id=case_id,
                embargo_id=embargo_id,
                answering_actor_id=accepting_actor_id,
                answer=EmbargoConsentState.AGREED,
                sync_port=self._sync_port,
            )
        ) is not None:
            return repeat

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

        # One received tree (CLP-10-005).  Its clock decision evaluates the
        # Invite's RSVP deadline at the CASE_MANAGER and ledgers an expiry
        # (CM-28-009, CM-28-014, CLP-10-025); a late Accept is then refused
        # as an answer and routed below.  accepting_actor_id is passed so the
        # node records acceptance for the right actor when receiving !=
        # accepting.
        expiry_out: dict[str, object] = {}
        tree = accept_invite_to_embargo_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=accepting_actor_id,
            invite_id=invite_id,
            sender_rule=self.sender_entitlement,
            now=datetime.now(tz=UTC),
            published=claimed_published_iso(request.activity),
            expiry_out=expiry_out,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            # The owner's acceptance of a shorter revision is announced to
            # the bound signatories the ledger no longer reaches (CM-31-009).
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )

        if bool(expiry_out.get(IS_EXPIRED_KEY)):
            return self._route_late_accept(
                result,
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
                receiving_actor_id=receiving_actor_id,
                invite_id=invite_id,
            )

        verdict = embargo_answer_repeat_verdict(
            tree,
            verdict_from_bt(tree, result, label="AcceptInviteToEmbargoBT"),
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
