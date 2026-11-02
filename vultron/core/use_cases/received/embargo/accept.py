"""Received ``Accept(Invite(EmbargoEvent))`` and its late Accept.

The Accept is the sender's own consent to the proposed terms and carries no
protocol shorthand (MSM-02-010): EA and EC are the Case Owner's decision,
``Accept(EmbargoEvent)[target=VulnerabilityCase]`` (:mod:`.owner_decision`).

One tree per delivery (CLP-10-005, ADR-0135): the door guards, the Invite
expiry, the repeat guard, the P/X/A refusal and the late-Accept routing are
all stages and diversions of
:func:`~vultron.core.behaviors.embargo.answer_trees.accept_invite_to_embargo_tree`,
and the handler only reads how the run ended.
"""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.ports.wire_render import WireRenderPort

import py_trees

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    accept_invite_to_embargo_tree,
)
from vultron.core.behaviors.embargo.expiry_tree import (
    LATE_ACCEPT_DIVERSIONS,
)
from vultron.core.behaviors.embargo.nodes.late_accept import LateAcceptRoute
from vultron.core.behaviors.embargo.refusal_tree import PXA_ACCEPT_REFUSAL
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    case_manager_verdict,
    embargo_answer_repeat_verdict,
    failure_reason,
    pxa_refusal_verdict,
    taken_diversion,
    verdict_from_bt,
)
from vultron.errors import VultronBTInternalError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)

_TREE_LABEL = "AcceptInviteToEmbargoBT"


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

        # One received tree (CLP-10-005).  accepting_actor_id is passed so
        # the tree records acceptance for the right actor when receiving !=
        # accepting.
        tree = accept_invite_to_embargo_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=request.actor_id,
            invite_id=invite_id,
            sender_rule=self.sender_entitlement,
            now=now_utc(),
            accept_id=request.activity_id,
            actor_config=self._actor_config,
        )
        result = BTBridge(
            datalayer=self._dl,
            # The P/X/A Reject of the Invite, the late-Accept answers and the
            # owner's acceptance of a shorter revision all emit (CM-31-009,
            # EMB-17, EMB-02-004).
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        verdict = self._verdict(
            tree, result, case_id=case_id, invite_id=invite_id
        )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            # A correct no-op is not a warning (SL-01-001).
            log = (
                logger.info
                if verdict.disposition is HandlerDisposition.SKIPPED
                else logger.warning
            )
            log(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict

    def _verdict(
        self,
        tree: py_trees.behaviour.Behaviour,
        result: BTExecutionResult,
        *,
        case_id: str,
        invite_id: str,
    ) -> HandlerResult:
        """Read how the one run ended (ADR-0095).

        Raises:
            VultronBTInternalError: the run failed on an internal error, or a
                late-Accept answer the tree took did not complete.
        """
        verdict = verdict_from_bt(tree, result, label=_TREE_LABEL)
        if verdict.disposition is not HandlerDisposition.REFUSED:
            return self._applied_verdict(tree, verdict, case_id)
        if (
            refusal := pxa_refusal_verdict(
                tree,
                PXA_ACCEPT_REFUSAL,
                f"Accept of Invite '{invite_id}' on case '{case_id}'",
            )
        ) is not None:
            return refusal
        for route, name in LATE_ACCEPT_DIVERSIONS.items():
            if (stage := taken_diversion(tree, name)) is None:
                continue
            if not stage.effects_succeeded:
                raise VultronBTInternalError(
                    f"{name}: {failure_reason(stage.effects, result)}"
                )
            if route is LateAcceptRoute.UNBOUND:
                # Nothing to bind, so nothing changed (EMB-17-004).
                return HandlerResult.skipped(
                    f"late Accept of Invite '{invite_id}' on case"
                    f" '{case_id}': the case holds no embargo for it to bind"
                    " (EMB-17-004)"
                )
            # The late Accept was answered, not recorded (EMB-17-001).
            return HandlerResult.applied()
        return embargo_answer_repeat_verdict(tree, verdict)

    def _applied_verdict(
        self,
        tree: py_trees.behaviour.Behaviour,
        verdict: HandlerResult,
        case_id: str,
    ) -> HandlerResult:
        """An applied run, unless this receiver is not the CASE_MANAGER.

        Only the CASE_MANAGER records an answer; a replica learns it from the
        ledger broadcast (BT-17-001, HP-01-005).
        """
        return case_manager_verdict(tree, verdict, self._dl, case_id)
