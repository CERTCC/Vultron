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
ADR-0113).  Each of the five trigger trees therefore splits, after its
read-only routing guards, into two mutually exclusive arms
(``create_case_manager_gated_tree`` beside
``create_participant_replica_gated_tree``, BT-17-001):

- **As the CASE_MANAGER** the actor's decision is canonical: the
  ``EmbargoLifecycle`` write runs ``STRICT``, the decision activity is
  committed as a ledger entry the announce slots replay (EP-09-007,
  RSH-08-004, #4085), and the ``Add(CaseStatus)`` declaration follows.
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

import py_trees

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case_status_snapshot import (
    EmitCaseStatusUpdateNode,
)
from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_INVITE_EVENT_TYPE,
    EMBARGO_TEARDOWN_EVENT_TYPE,
    AcceptEmbargoLifecycleNode,
    CollectEmbargoInviteRecipientsNode,
    CommitEmbargoDecisionNode,
    CommitEmbargoTeardownNode,
    EmbargoActivityBuilder,
    HasActiveEmbargoNode,
    IsProposedEmbargoNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    ReadEmbargoIdNode,
    ReadEmStateNode,
    ReadProposedEmbargoIdNode,
    RejectEmbargoLifecycleNode,
    RejectProposedEmbargoLifecycleNode,
    RelayEmbargoInviteToEachNode,
    SendRejectEmbargoActivityNode,
    SendTerminateEmbargoActivityNode,
    TerminateEmbargoLifecycleNode,
    ValidateEmbargoRevisionStateNode,
)
from vultron.core.behaviors.sender.nodes import (
    ConstructActivitiesNode,
    QueueToOutboxNode,
    ResolveCaseManagerNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import (
    ASSERTED_ACTIVITY_KEY,
)

_ACCEPT_EVENT_TYPE = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
_REJECT_EVENT_TYPE = MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value


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


def _by_role(
    name: str,
    case_id: str,
    as_case_manager: list[py_trees.behaviour.Behaviour],
    otherwise: list[py_trees.behaviour.Behaviour],
) -> list[py_trees.behaviour.Behaviour]:
    """The two mutually exclusive arms every embargo trigger tree ends with."""
    return [
        create_case_manager_gated_tree(
            name=f"{name}AsCaseManager",
            case_id=case_id,
            children=as_case_manager,
        ),
        create_participant_replica_gated_tree(
            name=f"{name}AskCaseManager",
            case_id=case_id,
            children=otherwise,
        ),
    ]


def _answer_arms(
    name: str,
    case_id: str,
    lifecycle_node: py_trees.behaviour.Behaviour,
    event_type: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> list[py_trees.behaviour.Behaviour]:
    """Manager: write, commit, declare; otherwise: ask the manager.

    The manager's Accept or Reject is addressed to nobody: every replica
    learns it from the committed entry (EP-09-007).
    """
    return _by_role(
        name,
        case_id,
        as_case_manager=[
            lifecycle_node,
            CommitEmbargoDecisionNode(
                case_id=case_id,
                event_type=event_type,
                builder=activity_builder,
            ),
            _make_emit_node(case_id),
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
    (EP-09-001, EP-09-002): collect the invitees before the EM write
    (BT-19-001), write ``STRICT``, commit the proposal, then relay one
    ``Invite`` per participant.  ``PersistEmbargoEventNode`` runs in both
    arms — the factory renders the stored record — and stores the object,
    not case state (EP-09-003).
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
            ),
            PersistEmbargoEventNode(embargo=embargo),
            CommitEmbargoDecisionNode(
                case_id=case_id,
                event_type=EMBARGO_INVITE_EVENT_TYPE,
                builder=activity_builder,
            ),
            _make_emit_node(case_id),
            RelayEmbargoInviteToEachNode(
                case_id=case_id,
                embargo_id=embargo.id_,
                proposer_id=actor_id,
            ),
        ],
        otherwise=[
            PersistEmbargoEventNode(embargo=embargo),
            sender_side_bt(
                case_id=case_id,
                activity_builder=_asserting(activity_builder, result_out),
            ),
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
    """Build trigger-side BT for proposing an embargo (EP-09-008)."""
    return py_trees.composites.Sequence(
        name="ProposeEmbargoTriggerBT",
        memory=False,
        children=_propose_arms(
            "ProposeEmbargo",
            case_id,
            actor_id,
            embargo,
            result_out,
            activity_builder,
        ),
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
    """Build trigger-side BT for accepting an embargo invite (EP-09-008)."""
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
    """Build trigger-side BT for rejecting an embargo invite (EP-09-008)."""
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


def reject_proposed_embargo_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
) -> py_trees.behaviour.Behaviour:
    """Shared BT for abandoning a proposed embargo (EMB-16-001).

    Used by :class:`PublicDisclosureBranchNode` when CS.P/X/A fires while the
    case EM state is PROPOSED.  Mirrors the routing-guard ordering of
    :func:`terminate_embargo_bt`:

    1. ``ReadEmStateNode`` — read EM state into ``result_out["em_before"]``
       (AC-1: EM-state reads go through ``Read*StateNode``).
    2. ``IsProposedEmbargoNode`` — guard: EM must be PROPOSED; FAILURE otherwise.
    3. ``ReadProposedEmbargoIdNode`` — read embargo_id from proposed_embargoes.
    4. ``ResolveCaseManagerNode`` — routing guard; FAILURE = no state change.
    5. ``RejectProposedEmbargoLifecycleNode`` — EM state mutation (PROPOSED → NONE).
    6. ``SendRejectEmbargoActivityNode`` — queue ER to Case Manager.

    Both the routing guard (step 4) and state mutation (step 5) are ordered per
    BT-19-001/BT-19-002 so that routing prerequisites are always verified before
    the DataLayer state change is committed.
    """
    return py_trees.composites.Sequence(
        name="RejectProposedEmbargoBT",
        memory=True,
        children=[
            ReadEmStateNode(case_id=case_id, result_out=result_out),
            IsProposedEmbargoNode(case_id=case_id, result_out=result_out),
            ReadProposedEmbargoIdNode(case_id=case_id),
            ResolveCaseManagerNode(case_id=case_id),
            RejectProposedEmbargoLifecycleNode(
                case_id=case_id,
                result_out=result_out,
            ),
            _make_emit_node(case_id),
            SendRejectEmbargoActivityNode(case_id=case_id),
        ],
    )


def terminate_embargo_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder | None = None,
) -> py_trees.behaviour.Behaviour:
    """Shared BT for terminating the active embargo (BT-19-001, EP-09-008).

    Satisfies the routing-gated state-mutation ordering:

    1. ``HasActiveEmbargoNode`` / ``ReadEmbargoIdNode`` — read embargo_id
       from the case; FAILURE if absent.
    2. ``ResolveCaseManagerNode`` — routing guard; FAILURE = no state change.
    3. As the CASE_MANAGER: ``TerminateEmbargoLifecycleNode`` (EM write), then
       commit the ``Remove(EmbargoEvent)`` as the canonical entry the
       ``EmbargoTeardown`` slot replays, addressed to every other participant
       and never to the manager (EMB-19-001, CLP-10-001, #4112), then the
       ``Add(CaseStatus)`` declaration.
    4. As any other participant: no EM write; the ``Remove`` is queued to the
       CASE_MANAGER as a request (PCR-08-001).

    With ``activity_builder`` (the trigger path) the use case builds the
    activity; with ``None`` (the CS.P/X/A and threat cascades) the nodes read
    ``/embargo_id`` and the factory from the blackboard.  Every path MUST use
    this factory so routing prerequisites are verified before the DataLayer
    state change is committed (BT-19-002).
    """
    if activity_builder is not None:
        commit: py_trees.behaviour.Behaviour = CommitEmbargoDecisionNode(
            case_id=case_id,
            event_type=EMBARGO_TEARDOWN_EVENT_TYPE,
            builder=activity_builder,
            notify_participants=True,
        )
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
        commit = CommitEmbargoTeardownNode(case_id=case_id)
        ask = SendTerminateEmbargoActivityNode(case_id=case_id)

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
                    TerminateEmbargoLifecycleNode(
                        case_id=case_id, result_out=result_out
                    ),
                    commit,
                    _make_emit_node(case_id),
                ],
                otherwise=[ask],
            ),
        ],
    )
