"""Received ``Accept(Invite(EmbargoEvent))`` and its late Accept.

The Accept is the sender's own consent to the proposed terms and carries no
protocol shorthand (MSM-02-010): EA and EC are the Case Owner's decision,
``Add(EmbargoEvent)[target=VulnerabilityCase]`` (:mod:`.owner_decision`).

One tree per delivery (CLP-10-005, ADR-0135): the door guards, the Invite
expiry, the repeat guard, the P/X/A refusal and the answers to an embargo
that is not available (MSM-07-012, MSM-07-039) are all stages and diversions
of
:func:`~vultron.core.behaviors.embargo.answer_trees.accept_invite_to_embargo_tree`,
and the handler only reads how the run ended.
"""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.case.received_run import (
    OutcomeReader,
    ReceivedOutcome,
    failure_reason,
    first_reading,
    pxa_refusal_reader,
    run_received_tree,
    taken_diversion,
)
from vultron.core.behaviors.embargo.accept_availability_tree import (
    NEVER_HELD_EMBARGO_FAULT,
    UNAVAILABLE_EMBARGO_REFUSAL,
)
from vultron.core.behaviors.embargo.answer_trees import (
    accept_invite_to_embargo_tree,
)
from vultron.core.behaviors.embargo.refusal_tree import PXA_ACCEPT_REFUSAL
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronBTInternalError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort


logger = logging.getLogger(__name__)

_TREE_LABEL = "AcceptInviteToEmbargoBT"


def _unavailable_embargo_reader(where: str) -> OutcomeReader:
    """The verdict of an Accept a not-available-embargo diversion answered.

    The Accept was answered, never recorded: a fault for terms the register
    never held (MSM-07-039), the refusal notice for terms no longer
    available (MSM-07-012).  *where* names the Invite and the case.

    Raises:
        VultronBTInternalError: the diversion's answer did not complete.
    """

    def read(outcome: ReceivedOutcome) -> HandlerResult | None:
        for name in (NEVER_HELD_EMBARGO_FAULT, UNAVAILABLE_EMBARGO_REFUSAL):
            if (stage := taken_diversion(outcome.tree, name)) is None:
                continue
            if not stage.effects_succeeded:
                raise VultronBTInternalError(
                    f"{name}: {failure_reason(stage.effects, outcome.result)}"
                )
            return HandlerResult.refused(
                stage.condition.feedback_message
                or f"{name}: {where} answered, not recorded"
            )
        return None

    return read


class AcceptInviteToEmbargoOnCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
        SenderEntitlementKind.INVITEE
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteToEmbargoOnCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        actor_config: ActorConfig | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AcceptInviteToEmbargoOnCaseReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._actor_config = actor_config

    def execute(self) -> HandlerResult:
        request = self._request
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

        # A case this store does not hold puts the Accept on the no-case
        # path, which the tree's path stage refuses (HP-01-039); one naming
        # no case is refused by the incomplete-activity guard (CLP-10-018).
        case_id = request.case_id

        # One received tree (CLP-10-005).  accepting_actor_id is passed so
        # the tree records acceptance for the right actor when receiving !=
        # accepting.  Only the CASE_MANAGER records an answer: the tree
        # declares the manager path alone, so its path stage refuses a
        # replica, which learns it from the ledger broadcast (BT-17-001,
        # HP-01-005).
        tree = accept_invite_to_embargo_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=request.actor_id,
            invite_id=invite_id,
            sender_rule=self.sender_entitlement,
            accept_id=request.activity_id,
            actor_config=self._actor_config,
        )
        where = f"Accept of Invite '{invite_id}' on case '{case_id}'"
        verdict = run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label=_TREE_LABEL,
            # The P/X/A Reject of the Invite, the fault, refusal notice and
            # re-invite that answer an embargo not available, and the
            # owner's acceptance of a shorter revision all emit (CM-31-009,
            # MSM-07-012, MSM-07-039, EMB-17-003, EMB-02-004).
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
            # A diversion answered the Accept itself; a repeat of an answer
            # already recorded the runner reports SKIPPED from the repeat
            # guard's declaration (CM-13-005, HP-01-014).
            reader=first_reading(
                pxa_refusal_reader(PXA_ACCEPT_REFUSAL, where),
                _unavailable_embargo_reader(where),
            ),
        )
        if verdict.disposition is HandlerDisposition.SKIPPED:
            # A correct no-op is not a warning (SL-01-001); a refusal the
            # runner has already logged.
            logger.info(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict
