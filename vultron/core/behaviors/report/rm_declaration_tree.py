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

"""The stages every activity-typed RM handler shares (RSH-06-006, RSH-08-001).

Report valid / invalid / closed (``Accept``, ``TentativeReject`` and
``Reject(Offer(VulnerabilityReport))``) and engage / defer (``Join`` and
``Ignore(VulnerabilityCase)``) each declare one RM state for their **sender**.
They are built from the two pieces here, so one acceptance rule governs all of
them and the ``Add(ParticipantStatus)`` path alike:

- :func:`rm_declaration_guard` — the precondition guard
  (:class:`~vultron.core.behaviors.status.nodes.rm_declaration\
.AdjudicateRMDeclarationNode`), which refuses a regression before the commit
  (CLP-10-006, CLP-10-009) and flags an anomaly;
- :func:`record_rm_declaration` — the effects: record the declared state for
  the sender unless it is already recorded (RSH-08-002), then post the
  RSH-06-004 clarification note when the guard flagged an anomaly.
- :func:`rm_gap_note` — the refusal effect: a tree passes it as
  ``refusal_effects`` so a refused regression still posts the RSH-06-004 note
  (CLP-10-022).
- :func:`unless_rm_already_recorded` — the repeat guard the effects above are
  built from, and which a tree hanging further effects on the move wraps those
  in too, so one question is asked about one subject (ID-05-003, #5006).

The write is :class:`~vultron.core.behaviors.case.nodes.participant.status\
.CreateParticipantStatusNode` with ``rm_rule=RMRule.DECLARATION``: it keeps its
own call to the shared evaluator (BTND-10-003), held to the received-side rule
rather than adjacency, so the non-adjacent forward move the guard accepted is
not refused at the write.

Placement in the tree::

    <HandlerBT> (create_receive_activity_tree)
    ├─ Intake
    ├─ SenderIsParticipantNode               # sender guard (HP-01-006)
    ├─ PreconditionGuardStage                # refusal_effects (CLP-10-022)
    │   ├─ PreconditionGuards (Sequence)
    │   │   ├─ … handler guards …
    │   │   └─ AdjudicateRMDeclarationNode   # rm_declaration_guard
    │   └─ RefusalEffects → EmitRMGapNoteNode  # only on a refusal
    ├─ [GuardedCommit]
    ├─ Idempotent<name> (Selector)           # record_rm_declaration
    │   ├─ CheckParticipantRMState           # already recorded → skip
    │   └─ CreateParticipantStatusNode(rm_rule=DECLARATION)
    ├─ Record<name>                          # the status as its own entry
    └─ EmitRMGapNoteNode                     # RSH-06-004
"""

import py_trees

from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.case.nodes.participant.status_entries import (
    CommitParticipantStatusEntriesNode,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckParticipantRMState,
)
from vultron.core.behaviors.status.nodes.rm_anomaly import rm_gap_note
from vultron.core.behaviors.status.nodes.rm_declaration import (
    AdjudicateRMDeclarationNode,
)
from vultron.core.states.rm import RM, RMRule

__all__ = [
    "record_rm_declaration",
    "rm_declaration_guard",
    "rm_gap_note",
    "unless_rm_already_recorded",
]


def unless_rm_already_recorded(
    sender_actor_id: str,
    declared_rm: RM,
    case_id: str | None,
    *,
    name: str,
    guard_name: str,
    children: list[py_trees.behaviour.Behaviour],
) -> py_trees.composites.Selector:
    """Run *children* unless the sender is already recorded at *declared_rm*.

    The one shape for "a declaration that moves nothing does nothing": a
    Selector whose **first** child reads the sender's recorded RM state and
    whose second is the work.  Reading first is what makes the answer
    meaningful — a guard asked after the write would always find
    *declared_rm* and the work would never run (RSH-08-002, ID-05-003).

    Both the RM write itself (:func:`record_rm_declaration`) and a tree that
    hangs further effects on the move build their repeat guard from here, so
    the two cannot drift on what "already recorded" means, and every
    :class:`~vultron.core.behaviors.report.nodes.conditions\
.CheckParticipantRMState` a tree holds asks one question.  That matters
    because :func:`~vultron.core.use_cases.received._bt_verdict\
.rm_declaration_verdict` reads the answer by node *type* (CS-22-001, #5006).

    There is deliberately no ``Success`` fallback: a failure of *children*
    propagates as FAILURE rather than reading as a benign skip.  The engage
    tree's children end in a peer broadcast, and a guaranteed SUCCESS beside
    a fan-out would mask a delivery failure (BT-14-001).

    Args:
        sender_actor_id: The subject — ``request.actor_id`` (RSH-08-001).
        declared_rm: The RM state the activity declares.
        case_id: The case the declaration is about.
        name: Name of the Selector.
        guard_name: Name of the condition node, so a tree dump says which
            question was asked (BTND-08-002).
        children: The work to skip when the state is already recorded.
    """
    return py_trees.composites.Selector(
        name=name,
        memory=False,
        children=[
            CheckParticipantRMState(
                case_id=case_id,
                actor_id=sender_actor_id,
                target_rm=declared_rm,
                name=guard_name,
            ),
            *children,
        ],
    )


def rm_declaration_guard(
    sender_actor_id: str, declared_rm: RM, case_id: str | None
) -> AdjudicateRMDeclarationNode:
    """Return the precondition guard for the sender's RM declaration."""
    return AdjudicateRMDeclarationNode(
        sender_actor_id=sender_actor_id,
        declared_rm=declared_rm,
        case_id=case_id,
    )


def record_rm_declaration(
    sender_actor_id: str,
    declared_rm: RM,
    case_id: str | None,
    name: str,
) -> list[py_trees.behaviour.Behaviour]:
    """Return the effect nodes that record the sender's declared RM state.

    The status the write appends is committed as its own
    ``add_participant_status_to_participant`` entry right after it, so a
    replica copies the CASE_MANAGER's status instead of building its own
    (CLP-07-013, CM-23-016).  A status whose entry does not commit is taken
    back.  An already-recorded state writes and commits nothing.

    Args:
        sender_actor_id: The subject — ``request.actor_id`` (RSH-08-001).
        declared_rm: The RM state the activity declares.
        case_id: The case the declaration is about.
        name: Name of the write node (e.g. ``"TransitionRMtoInvalid"``); the
            idempotent Selector around it is named ``Idempotent<name>``.
    """
    written: list[str] = []
    return [
        unless_rm_already_recorded(
            sender_actor_id,
            declared_rm,
            case_id,
            name=f"Idempotent{name}",
            guard_name=f"AlreadyRecorded{declared_rm.name.title()}",
            children=[
                CreateParticipantStatusNode(
                    actor_id=sender_actor_id,
                    rm_state=declared_rm,
                    vf_state=None,
                    d_state=None,
                    pxa_state=None,
                    name=name,
                    rm_rule=RMRule.DECLARATION,
                    written_ids=written,
                ),
            ],
        ),
        CommitParticipantStatusEntriesNode(
            subject_actor_id=sender_actor_id,
            case_id=case_id,
            status_ids=written,
            name=f"Record{name}",
        ),
        rm_gap_note(sender_actor_id, case_id),
    ]
