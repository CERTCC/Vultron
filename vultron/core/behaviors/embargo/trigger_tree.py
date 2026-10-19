#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Trigger-side embargo BT compositions.

A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008,
ADR-0113).  Each trigger tree therefore splits, after its
read-only routing guards, into two mutually exclusive arms
(``create_case_manager_gated_tree`` beside
``create_participant_replica_gated_tree``, BT-17-001):

- **As the CASE_MANAGER** the actor's decision is canonical: the
  ``EmbargoLifecycle`` operation runs ``STRICT``, the decision activity is
  committed as a ledger entry the announce slots replay (EP-09-007,
  RSH-08-004, #4085), and the ``Add(CaseStatus)`` declaration follows.  The
  propose and answer arms decide on a staged store and commit the act, then
  each consent row it changes, before applying them by copying (ADR-0124,
  CLP-07-013).
  Nothing is addressed to the manager itself (CLP-10-001): its own proposal
  is relayed to each participant (EP-09-002) and its teardown is told to
  every other one (EMB-19-001, #4112).
- **As any other participant** the tree writes no EM state and declares none:
  it builds the activity, queues it to the CASE_MANAGER (PCR-08-001) and
  writes the activity id to ``result_out[ASSERTED_ACTIVITY_KEY]``, which the
  use case records in the pending-assertion store (SYNC-11-002).  The replica
  moves when the manager's commit is announced.
"""

from collections.abc import Callable
from datetime import datetime

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.case_status_snapshot import (
    EmitCaseStatusUpdateNode,
)
from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_INVITE_EVENT_TYPE,
    EMBARGO_PROPOSAL_REJECTION_EVENT_TYPE,
    AbandonEmbargoProposalsLifecycleNode,
    AcceptEmbargoLifecycleNode,
    CollectEmbargoInviteRecipientsNode,
    CommitAndApplyEmbargoActivationNode,
    CommitAndApplyEmbargoTerminationNode,
    CommitEmbargoDecisionNode,
    CommitEmbargoProposalNode,
    EmbargoActivityBuilder,
    HasActiveEmbargoNode,
    IndexOwnEmbargoProposalNode,
    IsProposedEmbargoNode,
    LeaveAbandonmentToCaseManagerNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    ReadEmbargoIdNode,
    ReadEmStateNode,
    ReadOpenEmbargoProposalsNode,
    RejectEmbargoLifecycleNode,
    RejectEmbargoProposalLifecycleNode,
    RelayEmbargoInviteToEachNode,
    ValidateEmbargoProposalStateNode,
    ValidateEmbargoRevisionStateNode,
    WithdrawEmbargoLifecycleNode,
    ask_case_manager_to_terminate_once,
    embargo_ending_notice_nodes,
)
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    _EmbargoLifecycleNode,
)
from vultron.core.behaviors.sender.nodes import (
    ConstructActivitiesNode,
    QueueToOutboxNode,
    ResolveCaseManagerNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import (
    TerminationRequest,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import (
    ASSERTED_ACTIVITY_KEY,
)

_ACCEPT_EVENT_TYPE = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
_REJECT_EVENT_TYPE = MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
_WITHDRAW_EVENT_TYPE = MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value


def _make_emit_node(case_id: str) -> py_trees.behaviour.Behaviour:
    return EmitCaseStatusUpdateNode(
        case_id=case_id, name="EmitCaseStatusUpdate"
    )


def _asserting(
    builder: EmbargoActivityBuilder, result_out: dict[str, object]
) -> Callable[[str], list[str]]:
    """Adapt *builder* to the sender nodes' one-recipient shape.

    The activity goes to the CASE_MANAGER alone, and its id is written to
    ``result_out[ASSERTED_ACTIVITY_KEY]`` for the pending-assertion record.
    """

    def _build(case_manager_id: str) -> list[str]:
        activity_id, _blob = builder([case_manager_id])
        result_out[ASSERTED_ACTIVITY_KEY] = activity_id
        return [activity_id]

    return _build


#: Name suffix of ``reject_proposed_embargo_bt``'s non-manager arm, which
#: asks nothing (EMB-16-002).
ABANDONMENT_LEFT_TO_CASE_MANAGER = "LeaveToCaseManager"


def _by_role(
    name: str,
    case_id: str,
    as_case_manager: list[py_trees.behaviour.Behaviour],
    otherwise: list[py_trees.behaviour.Behaviour],
    otherwise_suffix: str = "AskCaseManager",
) -> list[py_trees.behaviour.Behaviour]:
    """The two mutually exclusive arms every embargo trigger tree ends with.

    *otherwise_suffix* names the non-manager arm for what it does; the
    default fits every arm that asks the CASE_MANAGER.
    """
    return [
        create_case_manager_gated_tree(
            name=f"{name}AsCaseManager",
            case_id=case_id,
            children=as_case_manager,
        ),
        create_participant_replica_gated_tree(
            name=f"{name}{otherwise_suffix}",
            case_id=case_id,
            children=otherwise,
        ),
    ]


def _answer_arms(
    name: str,
    case_id: str,
    lifecycle_node: _EmbargoLifecycleNode,
    event_type: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
    actor_config: ActorConfig | None = None,
) -> list[py_trees.behaviour.Behaviour]:
    """Manager: decide, commit, apply, declare; otherwise: ask the manager.

    The manager's Accept or Reject — of an Invite (the sender's consent), or
    as the case owner of the embargo itself (ADR-0122) — is addressed to
    nobody: every replica learns it from the committed entry (EP-09-007).  An
    Accept that activates a shorter revision is announced to the bound
    signatories the ledger no longer reaches (CM-31-009).

    The manager arm commits before it writes (ADR-0124, CLP-07-013): the
    lifecycle node only decides, on a staged store, and the commit node
    commits the act's entry (carrying any register step), then one
    CASE_MANAGER entry per consent row the decision changes, and applies them
    by copying.  *lifecycle_node* is built with *result_out*, where it leaves
    the decision.
    """
    return _decision_arms(
        name,
        case_id,
        [
            lifecycle_node.deciding(),
            CommitEmbargoDecisionNode(
                case_id=case_id,
                event_type=event_type,
                builder=activity_builder,
                decision_from=result_out,
            ),
        ],
        result_out,
        activity_builder,
        actor_config,
    )


def _decision_arms(
    name: str,
    case_id: str,
    decide_and_commit: list[py_trees.behaviour.Behaviour],
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
    actor_config: ActorConfig | None = None,
) -> list[py_trees.behaviour.Behaviour]:
    """The two arms of an answer or decision, around *decide_and_commit*.

    As the manager: capture the signatories bound before the change, run
    *decide_and_commit*, declare the ``Add(CaseStatus)``, announce a shorter
    revision to the bound signatories the ledger no longer reaches
    (CM-31-009), and re-issue stale stub Invites (CM-11-016).  Otherwise:
    ask the manager.  Shared by :func:`_answer_arms` and the activation arm;
    each decides before it commits and commits before it writes (ADR-0124).
    """
    capture, notices = embargo_ending_notice_nodes(case_id)
    return _by_role(
        name,
        case_id,
        as_case_manager=[
            capture,
            *decide_and_commit,
            _make_emit_node(case_id),
            notices,
            # The owner's accept of a revision changes the active embargo
            # under any outstanding stub Invite (CM-11-016).  The node compares
            # each stub's terms with the embargo in force and does nothing
            # while a proposal is open, so a reject or a participant's accept
            # re-issues nothing.
            ReissueStubInvitesNode(case_id=case_id, actor_config=actor_config),
        ],
        otherwise=[
            sender_side_bt(
                case_id=case_id,
                activity_builder=_asserting(activity_builder, result_out),
            )
        ],
    )


def _propose_arms(
    name: str,
    case_id: str,
    actor_id: str,
    embargo: EmbargoEvent,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> list[py_trees.behaviour.Behaviour]:
    """Manager: adjudicate and relay its own terms; otherwise: ask.

    The CASE_MANAGER's own proposal takes the shape of one it receives
    (EP-09-001, EP-09-002): collect the invitees before deciding
    (BT-19-001), decide ``STRICT`` on a staged store, commit the proposal —
    the ``Invite(EmbargoEvent)`` whose entry is the ``PROPOSE`` step —
    then one ``Create(EmbargoConsent)`` per participant's new row (the
    proposer's ``AGREED``, every other one ``UNINVITED``), apply them by
    copying (ADR-0124, CLP-07-013), relay one ``Invite`` per participant,
    and only then index the proposal the manager will answer (ID-04-005).
    The factory renders the stored ``EmbargoEvent``, the object and not case
    state (EP-09-003): in the manager arm ``CommitEmbargoProposalNode``
    stores it as it builds the proposal and takes it back out when the
    proposal does not commit; in the other arm ``PersistEmbargoEventNode``
    runs after the CASE_MANAGER is resolved.  Neither a refused or failed
    proposal nor a failed routing guard leaves an orphan record (BT-19-001).
    """
    return _by_role(
        name,
        case_id,
        as_case_manager=[
            CollectEmbargoInviteRecipientsNode(
                case_id=case_id, proposer_id=actor_id
            ),
            ProposeEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo.id_,
                result_out=result_out,
                embargo=embargo,
            ).deciding(),
            CommitEmbargoProposalNode(
                case_id=case_id,
                event_type=EMBARGO_INVITE_EVENT_TYPE,
                builder=activity_builder,
                embargo=embargo,
                result_out=result_out,
            ),
            _make_emit_node(case_id),
            RelayEmbargoInviteToEachNode(
                case_id=case_id,
                embargo_id=embargo.id_,
                proposer_id=actor_id,
                # The manager's own proposal is the request each relayed
                # Invite answers.  A repeated trigger proposes a new embargo,
                # so no retry rebuilds these Invites: one whose commit fails
                # is withdrawn instead (CLP-07-013).
                answers=embargo.id_,
                withdraw_unrecorded=True,
            ),
            IndexOwnEmbargoProposalNode(
                case_id=case_id,
                embargo_id=embargo.id_,
                result_out=result_out,
            ),
        ],
        otherwise=[
            ResolveCaseManagerNode(case_id=case_id),
            PersistEmbargoEventNode(embargo=embargo),
            ConstructActivitiesNode(
                activity_builder=_asserting(activity_builder, result_out)
            ),
            QueueToOutboxNode(),
        ],
    )


def propose_embargo_trigger_bt(
    *,
    case_id: str,
    actor_id: str,
    embargo: EmbargoEvent,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for proposing an embargo (EP-09-008).

    ``ValidateEmbargoProposalStateNode`` refuses an ``EXITED`` case before
    either arm runs, so a participant that is not the CASE_MANAGER fails
    fast rather than asking for a proposal the manager will not take.
    """
    return py_trees.composites.Sequence(
        name="ProposeEmbargoTriggerBT",
        memory=False,
        children=[
            ValidateEmbargoProposalStateNode(
                case_id=case_id, result_out=result_out
            ),
            *_propose_arms(
                "ProposeEmbargo",
                case_id,
                actor_id,
                embargo,
                result_out,
                activity_builder,
            ),
        ],
    )


def propose_embargo_revision_trigger_bt(
    *,
    case_id: str,
    actor_id: str,
    embargo: EmbargoEvent,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for proposing an embargo revision.

    Differs from :func:`propose_embargo_trigger_bt` by first asserting that
    the case EM state is ACTIVE or REVISE (a revision requires an existing
    active embargo).  The role arms are otherwise identical.
    """
    return py_trees.composites.Sequence(
        name="ProposeEmbargoRevisionTriggerBT",
        memory=False,
        children=[
            ValidateEmbargoRevisionStateNode(
                case_id=case_id,
                result_out=result_out,
            ),
            *_propose_arms(
                "ProposeEmbargoRevision",
                case_id,
                actor_id,
                embargo,
                result_out,
                activity_builder,
            ),
        ],
    )


def accept_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for accepting an embargo invite (EP-09-008).

    ``Accept(Invite(EmbargoEvent))``: the actor's own consent; it moves no
    register entry (ADR-0122).
    """
    return py_trees.composites.Sequence(
        name="AcceptEmbargoTriggerBT",
        memory=False,
        children=_answer_arms(
            "AcceptEmbargo",
            case_id,
            AcceptEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            _ACCEPT_EVENT_TYPE,
            result_out,
            activity_builder,
        ),
    )


def reject_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for rejecting an embargo invite (EP-09-008).

    ``Reject(Invite(EmbargoEvent))``: the actor's own consent; it moves no
    register entry (ADR-0122).
    """
    return py_trees.composites.Sequence(
        name="RejectEmbargoTriggerBT",
        memory=False,
        children=_answer_arms(
            "RejectEmbargo",
            case_id,
            RejectEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            _REJECT_EVENT_TYPE,
            result_out,
            activity_builder,
        ),
    )


def withdraw_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for withdrawing from the embargo in force (EP-09-013).

    ``Leave(EmbargoEvent)`` (MSM-07-010): the actor's own consent ends; it
    moves no register entry.  As the CASE_MANAGER the actor records its own
    withdrawal and commits the Leave; any other participant sends it to the
    CASE_MANAGER (PCR-08).  The use case refuses an actor that cannot
    withdraw before this tree is built.
    """
    return py_trees.composites.Sequence(
        name="WithdrawEmbargoTriggerBT",
        memory=False,
        children=_answer_arms(
            "WithdrawEmbargo",
            case_id,
            WithdrawEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            _WITHDRAW_EVENT_TYPE,
            result_out,
            activity_builder,
        ),
    )


def activate_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for the case owner's activation (EP-09-008).

    ``Accept(EmbargoEvent, target=Case)`` (ADR-0122): as the CASE_MANAGER the
    owner decides the activation ``STRICT``, commits the ``Accept`` (the
    whole ``ACTIVATE`` step and its own agreement) and then one
    ``Update(EmbargoConsent)`` per ``CARRY_OVER`` row, and only then writes
    the case file (:class:`CommitAndApplyEmbargoActivationNode`, ADR-0124);
    any other owner asks the CASE_MANAGER.  The rest of both arms is
    :func:`_decision_arms`, shared with :func:`_answer_arms`; the ``Accept``
    is addressed to nobody.
    """
    return py_trees.composites.Sequence(
        name="ActivateEmbargoTriggerBT",
        memory=False,
        children=_decision_arms(
            "ActivateEmbargo",
            case_id,
            [
                CommitAndApplyEmbargoActivationNode(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    result_out=result_out,
                    builder=activity_builder,
                )
            ],
            result_out,
            activity_builder,
        ),
    )


def reject_embargo_proposal_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for the case owner's rejection (EP-09-008).

    ``Reject(EmbargoEvent, target=Case)`` (ADR-0122): as the CASE_MANAGER the
    owner rejects the proposal ``STRICT`` and commits its decision; any other
    owner asks the CASE_MANAGER.
    """
    return py_trees.composites.Sequence(
        name="RejectEmbargoProposalTriggerBT",
        memory=False,
        children=_answer_arms(
            "RejectEmbargoProposal",
            case_id,
            RejectEmbargoProposalLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            EMBARGO_PROPOSAL_REJECTION_EVENT_TYPE,
            result_out,
            activity_builder,
        ),
    )


def reject_proposed_embargo_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
) -> py_trees.behaviour.Behaviour:
    """Shared BT for abandoning the open embargo proposals (EMB-16-001).

    Used through ``pxa_embargo_teardown_bt`` (``ThreatTerminationBranchNode``)
    when CS.P/X/A fires while the case EM state is PROPOSED: no proposal can be accepted any more
    (EMB-02-002), so every open one is abandoned.  Mirrors the routing-guard
    ordering of :func:`terminate_embargo_bt`:

    1. ``ReadEmStateNode`` / ``IsProposedEmbargoNode`` — EM must be PROPOSED.
    2. ``ResolveCaseManagerNode`` — routing guard; FAILURE = no state change.
    3. As the CASE_MANAGER (EP-09-008): ``ReadOpenEmbargoProposalsNode``
       maps each open proposal to the readable Invite its ER answers
       (FAILURE before anything moves when one has none),
       ``AbandonEmbargoProposalsLifecycleNode`` then, per proposal, commits
       one ER as an ``EMBARGO_ABANDONMENT_EVENT_TYPE`` entry the
       ``EmbargoAbandonment`` slot replays (EP-09-007), addressed to nobody
       (CLP-10-001), and only then cancels that proposal, so EM reaches
       ``NONE`` with the last one and a proposal whose entry does not commit
       stays open (CLP-07-013); then the ``Add(CaseStatus)`` declaration.
    4. As any other participant: no EM write and no ask (EMB-16-002,
       #4148).  The manager has the P/X/A signal from the status
       declaration and abandons on its own detection; an ER sent on the
       case's behalf would read as this participant's DECLINE.  A
       proposal, Invite or revision the participant *receives* while the
       case is at P/X/A is a different matter: it answers that with ER
       (EMB-01-002) on the received path, not here.
    """
    return py_trees.composites.Sequence(
        name="RejectProposedEmbargoBT",
        memory=True,
        children=[
            ReadEmStateNode(case_id=case_id, result_out=result_out),
            IsProposedEmbargoNode(case_id=case_id, result_out=result_out),
            ResolveCaseManagerNode(case_id=case_id),
            *_by_role(
                "AbandonProposedEmbargo",
                case_id,
                as_case_manager=[
                    ReadOpenEmbargoProposalsNode(case_id=case_id),
                    AbandonEmbargoProposalsLifecycleNode(
                        case_id=case_id, result_out=result_out
                    ),
                    _make_emit_node(case_id),
                ],
                otherwise=[LeaveAbandonmentToCaseManagerNode(case_id=case_id)],
                otherwise_suffix=ABANDONMENT_LEFT_TO_CASE_MANAGER,
            ),
        ],
    )


def terminate_embargo_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
    termination: TerminationRequest,
    activity_builder: EmbargoActivityBuilder | None = None,
    requested_by: str | None = None,
    actor_config: ActorConfig | None = None,
    terminated_at: datetime | None = None,
) -> py_trees.behaviour.Behaviour:
    """Shared BT for terminating the active embargo (BT-19-001, EP-09-008).

    *termination* is how the embargo ends (ADR-0122): ``EARLY`` with the
    cause the requester names, or none, for a participant's own decision;
    :class:`ThreatSignalTermination` for the CS ``P``/``X``/``A`` cascades
    (``EARLY``, caused by the signals the case carries at the write); and
    ``END_TIME_REACHED``, with no cause, for the end-time paths, claimed at
    *terminated_at* and refused before the embargo's end time.  The
    CASE_MANAGER's ``Remove`` carries the what in ``content`` and the cause
    its ``TERMINATED`` entry records as ``terminationCause`` (EMB-13-005).
    A participant's ask carries the what and any cause it may name
    (``participant_cause``): only the CASE_MANAGER may name a
    ``THREAT_SIGNAL`` cause, and it learns the signals from the case status
    update instead.

    Satisfies the routing-gated state-mutation ordering:

    1. ``HasActiveEmbargoNode`` / ``ReadEmbargoIdNode`` — read embargo_id
       from the case; FAILURE if absent.
    2. ``ResolveCaseManagerNode`` — routing guard; FAILURE = no state change.
    3. As the CASE_MANAGER: ``CommitAndApplyEmbargoTerminationNode`` decides
       the ``TERMINATE`` step, commits the ``Remove(EmbargoEvent)`` that
       carries it as the canonical entry the ``EmbargoTeardown`` slot copies,
       addressed to every other participant and never to the manager
       (EMB-19-001, CLP-10-001, #4112), and only then applies the step
       through the one apply function (ADR-0124), so a failed commit writes
       nothing; then the ``Add(CaseStatus)`` declaration, then a direct
       ``Remove(EmbargoEvent)`` to each bound signatory the ledger no longer
       reaches (CM-31-009), crediting *requested_by* when another actor
       asked for the end.
    4. As any other participant: no EM write; the ``Remove`` is queued to the
       CASE_MANAGER as a request (PCR-08-001) and recorded as a pending
       assertion keyed by the ended embargo (EP-09-008, SYNC-11-002) — by
       the use case on the trigger path, by the ask subtree on the cascades.

    With ``activity_builder`` (the trigger path) the use case builds the
    activity; with ``None`` (the CS.P/X/A and threat cascades) the nodes read
    ``/embargo_id`` and the factory from the blackboard.  Every path MUST use
    this factory so routing prerequisites are verified before the DataLayer
    state change is committed (BT-19-002).

    *actor_config* sets the RSVP window of the stub Invites the CASE_MANAGER
    re-issues once the embargo ends; ``None`` applies the ``ActorConfig``
    defaults.
    """
    if activity_builder is not None:
        ask: py_trees.behaviour.Behaviour = py_trees.composites.Sequence(
            name="QueueToCaseManager",
            memory=False,
            children=[
                ConstructActivitiesNode(
                    activity_builder=_asserting(activity_builder, result_out)
                ),
                QueueToOutboxNode(),
            ],
        )
    else:
        # The ask carries the what and any cause a participant may name.  A
        # threat-signal termination is EARLY and its ask names no cause: a
        # THREAT_SIGNAL cause from anyone but the CASE_MANAGER is refused
        # (EMB-13-005).
        ask = ask_case_manager_to_terminate_once(
            case_id, termination.reason, termination.participant_cause
        )
    capture, notices = embargo_ending_notice_nodes(
        case_id, requested_by=requested_by
    )

    return py_trees.composites.Sequence(
        name="TerminateEmbargoBT",
        memory=True,
        children=[
            HasActiveEmbargoNode(case_id=case_id, result_out=result_out),
            ReadEmbargoIdNode(case_id=case_id),
            ResolveCaseManagerNode(case_id=case_id),
            *_by_role(
                "TerminateEmbargo",
                case_id,
                as_case_manager=[
                    capture,
                    # Decide, commit the Remove, then apply it (ADR-0124).
                    CommitAndApplyEmbargoTerminationNode(
                        case_id=case_id,
                        result_out=result_out,
                        termination=termination,
                        terminated_at=terminated_at,
                        builder=activity_builder,
                    ),
                    _make_emit_node(case_id),
                    notices,
                    # Termination changes the terms of every stub Invite still
                    # outstanding (CM-11-016).
                    ReissueStubInvitesNode(
                        case_id=case_id, actor_config=actor_config
                    ),
                ],
                otherwise=[ask],
            ),
        ],
    )
