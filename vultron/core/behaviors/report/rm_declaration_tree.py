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

The write is :class:`~vultron.core.behaviors.case.nodes.participant.status\
.CreateParticipantStatusNode` with ``rm_rule=RMRule.DECLARATION``: it keeps its
own call to the shared evaluator (BTND-10-003), held to the received-side rule
rather than adjacency, so the non-adjacent forward move the guard accepted is
not refused at the write.

Placement in the tree::

    <HandlerBT> (create_receive_activity_tree)
    ├─ Intake
    ├─ SenderIsActiveParticipantNode         # sender guard (HP-01-006)
    ├─ PreconditionGuardStage                # refusal_effects (CLP-10-022)
    │   ├─ PreconditionGuards (Sequence)
    │   │   ├─ … handler guards …
    │   │   └─ AdjudicateRMDeclarationNode   # rm_declaration_guard
    │   └─ RefusalEffects → EmitRMGapNoteNode  # only on a refusal
    ├─ [GuardedCommit]
    ├─ Idempotent<name> (Selector)           # record_rm_declaration
    │   ├─ CheckParticipantRMState           # already recorded → skip
    │   └─ CreateParticipantStatusNode(rm_rule=DECLARATION)
    └─ EmitRMGapNoteNode                     # RSH-06-004
"""

import py_trees

from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckParticipantRMState,
)
from vultron.core.behaviors.status.nodes.rm_anomaly import rm_gap_note
from vultron.core.behaviors.status.nodes.rm_declaration import (
    AdjudicateRMDeclarationNode,
)
from vultron.core.states.rm import RM, RMRule

__all__ = ["record_rm_declaration", "rm_declaration_guard", "rm_gap_note"]


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

    Args:
        sender_actor_id: The subject — ``request.actor_id`` (RSH-08-001).
        declared_rm: The RM state the activity declares.
        case_id: The case the declaration is about.
        name: Name of the write node (e.g. ``"TransitionRMtoInvalid"``); the
            idempotent Selector around it is named ``Idempotent<name>``.
    """
    return [
        py_trees.composites.Selector(
            name=f"Idempotent{name}",
            memory=False,
            children=[
                CheckParticipantRMState(
                    case_id=case_id,
                    actor_id=sender_actor_id,
                    target_rm=declared_rm,
                    name=f"AlreadyRecorded{declared_rm.name.title()}",
                ),
                CreateParticipantStatusNode(
                    actor_id=sender_actor_id,
                    rm_state=declared_rm,
                    vf_state=None,
                    d_state=None,
                    pxa_state=None,
                    name=name,
                    rm_rule=RMRule.DECLARATION,
                ),
            ],
        ),
        rm_gap_note(sender_actor_id, case_id),
    ]
