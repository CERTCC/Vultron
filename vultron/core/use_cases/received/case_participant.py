"""Use cases for the Case Owner's removal and reinstatement acts (ADR-0199).

The Case Owner sends the CASE_MANAGER its own act, naming the actor:
``Remove(<Actor>, origin=<case>)`` (CM-31-004) or
``Add(<Actor>, target=<case>)`` (CM-31-011).  The CASE_MANAGER refuses an act
from a sender that does not hold ``CASE_OWNER`` with no refusal notice
(CLP-05-006), refuses an Owner's act that breaks the rules with one, or
admits it as the move's one ledger entry, changes the record and announces the act to the actor it names
with ``Announce(<the Owner's act>)``.  It sends no ``Accept`` and makes no
act of its own.  The announced actor's replica records the ``Announce``
(:class:`AnnounceAdmittedActReceivedUseCase`) and takes the change from the
ledger entry alone (CM-31-029, CM-31-045).
"""

import logging
from typing import ClassVar

import py_trees

from vultron.core.behaviors.case.announce_admitted_act_received_tree import (
    ANNOUNCE_ADMITTED_ACT_TREE,
    announce_admitted_act_received_tree,
)
from vultron.core.behaviors.case.case_participant_received_tree import (
    REINSTATEMENT_ACT,
    REMOVAL_ACT,
    create_add_case_participant_received_tree,
    create_remove_case_participant_received_tree,
    missing_ids_reason,
)
from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.case_participant_received import (
    AnnounceParticipantMoveNode,
    RecordParticipantRemovalNode,
)
from vultron.core.behaviors.case.nodes.participant_reinstatement import (
    ClearParticipantRemovalNode,
)
from vultron.core.behaviors.case.received_run import (
    OutcomeReader,
    ReceivedOutcome,
    node_failed,
    run_received_tree,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    InviteReinstatedParticipantToEmbargoNode,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.models.events.case_participant import (
    AnnounceAdmittedActReceivedEvent,
    ReinstateParticipantInCaseReceivedEvent,
    RemoveParticipantFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.errors import VultronBTInternalError

logger = logging.getLogger(__name__)


class _CaseOwnerParticipantMoveUseCase[
    MoveEvent: (
        ReinstateParticipantInCaseReceivedEvent,
        RemoveParticipantFromCaseReceivedEvent,
    )
]:
    """Shared frame of the Case Owner's two participant moves (ADR-0199).

    Both are the Case Owner's own act, sent to the CASE_MANAGER only, run
    the same staged tree (intake, sender guard, guards, commit, gated
    effects), and are judged the same way: a guard failure is ``REFUSED``,
    a failed effect after the commit is an internal fault.  The trees
    declare the manager path alone, so any other receiver refuses the act
    at the path stage: a replica takes the move from the ledger entry
    (HP-01-038, RSH-08-003).
    """

    # The Case Owner sends the act to the CASE_MANAGER only; no other
    # receiver acts on it (HP-01-038, PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
        SenderEntitlementKind.CASE_OWNER
    )

    #: The tree's name, for log lines and refusals.
    _LABEL: ClassVar[str]
    #: The act, in its own words, for log lines and refusals.
    _MESSAGE: ClassVar[str]
    #: Effects whose ``FAILURE`` is an internal fault: the move is committed.
    _EFFECTS: ClassVar[tuple[type[py_trees.behaviour.Behaviour], ...]]

    def __init__(
        self,
        dl: CasePersistence,
        request: MoveEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._request: MoveEvent = request

    def _build_tree(self, case_id: str | None) -> py_trees.behaviour.Behaviour:
        """The move's received tree; subclasses implement it.

        The tree refuses a move naming no case itself (CLP-10-005), so the
        id may be ``None`` here.
        """
        raise NotImplementedError

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        tree: py_trees.behaviour.Behaviour
        if request.participant_actor_id is None:
            # The tree declares the named actor as a seeded input, so an act
            # naming none is refused by the incomplete-activity tree instead
            # (CLP-10-005, CLP-10-018).
            tree = create_incomplete_activity_received_tree(
                self._LABEL, missing_ids_reason(self._MESSAGE)
            )
        else:
            tree = self._build_tree(case_id)
        # A guard failure that is an idempotent repeat (removing an
        # already-removed participant) the runner reports SKIPPED.
        verdict = run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label=self._LABEL,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            reader=_effect_fault_reader(self._EFFECTS),
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            logger.info(
                "%s admitted %s naming '%s' in case '%s'",
                self._LABEL,
                self._MESSAGE,
                request.participant_actor_id,
                case_id,
            )
        return verdict


def _effect_fault_reader(
    effects: tuple[type[py_trees.behaviour.Behaviour], ...],
) -> OutcomeReader:
    """Raise when an effect after the commit failed: the move is committed.

    The guards admitted the move; a fact that could not be recorded, or an
    announcement that could not be built or queued, is our fault, not the
    sender's (ADR-0095, BT-14-001).  The act's transaction keeps nothing of
    it (CLP-07-015).
    """

    def read(outcome: ReceivedOutcome) -> HandlerResult | None:
        if any(node_failed(outcome.tree, effect) for effect in effects):
            raise VultronBTInternalError(
                f"{outcome.label}: {outcome.failure_reason}"
            )
        return None

    return read


class ReinstateParticipantInCaseReceivedUseCase(
    _CaseOwnerParticipantMoveUseCase[ReinstateParticipantInCaseReceivedEvent]
):
    """The Case Owner reinstates a removed participant (CM-31-011).

    At the CASE_MANAGER: a sender that does not hold ``CASE_OWNER`` is
    ``REFUSED`` with nothing committed and no refusal notice (CM-31-043,
    CLP-05-006); the received runner logs it at WARNING (SL-03-002).  A
    reinstatement naming the CASE_MANAGER, the Case Owner, an actor with no
    record on the case, one that never joined, or one that is not removed
    (CM-31-036), is ``REFUSED`` with a refusal notice and nothing
    committed.  An admitted reinstatement commits the Owner's
    act as the one ledger entry (CM-31-044), clears the removal fact without
    asking the participant to accept again (CM-31-034, CM-31-035), backfills
    it once it is active (CM-10-006), announces the Owner's act to it
    (CM-31-044), and sends it the active embargo's Invite when it is not a
    signatory to it (CM-31-040).
    """

    # Re-declared so ``request`` names this handler's own event class, the
    # one its semantic-registry row routes (SE-02).
    def __init__(
        self,
        dl: CasePersistence,
        request: ReinstateParticipantInCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        super().__init__(
            dl,
            request,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
        )

    _LABEL: ClassVar[str] = "ReinstateParticipantReceivedBT"
    _MESSAGE: ClassVar[str] = REINSTATEMENT_ACT
    _EFFECTS: ClassVar[tuple[type[py_trees.behaviour.Behaviour], ...]] = (
        ClearParticipantRemovalNode,
        BackfillAdmittedParticipantsNode,
        AnnounceParticipantMoveNode,
        InviteReinstatedParticipantToEmbargoNode,
    )

    def _build_tree(self, case_id: str | None) -> py_trees.behaviour.Behaviour:
        return create_add_case_participant_received_tree(
            case_id=case_id,
            sender_id=self._request.actor_id,
            activity_id=self._request.activity_id,
            sender_rule=self.sender_entitlement,
        )


class RemoveParticipantFromCaseReceivedUseCase(
    _CaseOwnerParticipantMoveUseCase[RemoveParticipantFromCaseReceivedEvent]
):
    """The Case Owner removes a participant from active participation (CM-31-004).

    At the CASE_MANAGER: a sender that does not hold ``CASE_OWNER`` is
    ``REFUSED`` with nothing committed and no refusal notice (CLP-05-006);
    the received runner logs it at WARNING (SL-03-002).  A removal naming
    the CASE_MANAGER, the Case Owner or an actor with no record on the case
    is ``REFUSED`` with a refusal notice and nothing committed; removing an already-removed participant is ``SKIPPED``
    (CM-31-022).  An admitted removal commits the Owner's act as the one
    ledger entry (CM-31-005, CM-31-025), sets the removal fact while keeping
    the record (CM-31-001, CM-31-015), and announces the Owner's act to the
    removed actor (ADR-0199).
    """

    # Re-declared so ``request`` names this handler's own event class, the
    # one its semantic-registry row routes (SE-02).
    def __init__(
        self,
        dl: CasePersistence,
        request: RemoveParticipantFromCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        super().__init__(
            dl,
            request,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
        )

    _LABEL: ClassVar[str] = "RemoveParticipantReceivedBT"
    _MESSAGE: ClassVar[str] = REMOVAL_ACT
    _EFFECTS: ClassVar[tuple[type[py_trees.behaviour.Behaviour], ...]] = (
        RecordParticipantRemovalNode,
        AnnounceParticipantMoveNode,
    )

    def _build_tree(self, case_id: str | None) -> py_trees.behaviour.Behaviour:
        return create_remove_case_participant_received_tree(
            case_id=case_id,
            sender_id=self._request.actor_id,
            sender_rule=self.sender_entitlement,
        )


class AnnounceAdmittedActReceivedUseCase:
    """Record the CASE_MANAGER's ``Announce`` of an act it admitted (ADR-0199).

    Sent to an actor the act concerns that the entry's fan-out does not
    reach, such as a removed or reinstated participant (CM-31-044).  Only
    the case's CASE_MANAGER sends one, so any other sender, and any
    ``Announce`` reaching the CASE_MANAGER itself, is refused (HP-01-006,
    HP-01-038).  The participant records it and writes nothing else: it
    takes the change from the ledger entry that carries the act (CM-31-029,
    CM-31-045).  ``APPLIED`` on first receipt; a redelivery is ``SKIPPED``
    by the seen-before door (HP-01-014).
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_participant=any_of(SenderEntitlementKind.CASE_MANAGER)
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceAdmittedActReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port

    def execute(self) -> HandlerResult:
        request = self._request
        tree = announce_admitted_act_received_tree(
            sender_rule=self.sender_entitlement,
            # A case naming no CASE_MANAGER refuses the sender rather than
            # passing it (Regime 1, ADR-0087).
            sender_context=SenderCheckContext(
                sender_id=request.actor_id,
                case_id=request.case_id,
                case_manager_required=True,
            ),
        )
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label=ANNOUNCE_ADMITTED_ACT_TREE,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
