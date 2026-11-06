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

"""The RM-closure effects of the close-case received tree (CM-23-002, CM-23-003).

One arm per role: the Case Owner's Leave closes the owner and then the
CaseActor, an ordinary participant's Leave closes only the leaver, and each
closure step is committed as its own status entry (CM-23-022, CM-23-033).
"""

import py_trees

from vultron.core.behaviors.case.nodes.leave import (
    AdvanceCaseActorToRMClosedNode,
    AdvanceParticipantToRMClosedNode,
    CommitRMClosureEntriesNode,
    ExpirePendingInvitesOnCloseNode,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.role_condition import ActorHoldsRoleInCaseNode
from vultron.enums.roles import CVDRole


def _close_and_record(
    case_id: str,
    closing_actor_id: str,
    label: str,
    *,
    case_manager: bool = False,
) -> list[py_trees.behaviour.Behaviour]:
    """The advance for *closing_actor_id* and the record of its steps.

    The two nodes share one ``closure_steps`` list: the advance fills it
    with the id of each status it writes, and the record commits one
    ``add_participant_status_to_participant`` entry per id, in order
    (CM-23-022, CM-23-033).
    """
    closure_steps: list[str] = []
    advance: py_trees.behaviour.Behaviour = (
        AdvanceCaseActorToRMClosedNode(
            case_actor_id=closing_actor_id,
            case_id=case_id,
            closure_steps=closure_steps,
            name=f"Advance{label}ToRMClosed",
        )
        if case_manager
        else AdvanceParticipantToRMClosedNode(
            leaving_actor_id=closing_actor_id,
            case_id=case_id,
            closure_steps=closure_steps,
            name=f"Advance{label}ToRMClosed",
        )
    )

    # A refused step fails the act, which keeps none of it (CLP-07-015).
    return [
        advance,
        CommitRMClosureEntriesNode(
            closing_actor_id=closing_actor_id,
            case_id=case_id,
            closure_steps=closure_steps,
            name=f"Commit{label}RMClosureEntries",
        ),
    ]


def owner_or_non_owner_effects(
    case_id: str,
    sender_actor_id: str,
    receiving_actor_id: str | None,
) -> py_trees.composites.Sequence:
    """Build ``OwnerOrNonOwnerEffects``, the closure the Leave's sender's role picks."""
    # CM-23-014: after close a pending Invite can only expire, so expire each
    # one first, before any closure entry, rather than leave the CASE_MANAGER
    # waiting on its RSVP deadline.  It runs ahead of the Case Owner's own
    # closure because a Case Owner may also hold CASE_MANAGER, and then its
    # RM.CLOSED entry is already the write boundary (CM-23-013).  Best-effort:
    # a refused expiry commit writes nothing (the commit precedes the consent
    # write), so it does not stop the closure.
    owner_leave_children: list[py_trees.behaviour.Behaviour] = (
        [
            ExpirePendingInvitesOnCloseNode(
                case_id=case_id, name="ExpirePendingInvitesOnClose"
            )
        ]
        if receiving_actor_id is not None
        else []
    )
    # CM-23-002 step 1: the Case Owner's closure, each step on the ledger.
    owner_leave_children.extend(
        _close_and_record(case_id, sender_actor_id, "Owner")
    )
    if receiving_actor_id is not None:
        # CM-23-002 step 2: the CASE_MANAGER's own closure.  The advance is
        # store-local; without its entries the CASE_MANAGER stays RM.ACCEPTED
        # on every replica forever (ISSUE-2505): no effect node derives its
        # closure, because ``close_case`` names the departing actor.  Its
        # status entry reaching RM.CLOSED is the owner-close write boundary
        # (CM-23-013, ADR-0085), so it is the closure's last entry; no entry
        # marks the closure itself (ADR-0152).  A Case Owner that also holds
        # CASE_MANAGER is closed by step 1, and this step writes nothing.
        #
        # Every record node fails closed: a step whose entry does not commit
        # is withdrawn and the node fails (CLP-07-013).
        owner_leave_children.extend(
            _close_and_record(
                case_id, receiving_actor_id, "CaseActor", case_manager=True
            )
        )

    # One arm per role, each a Selector "not my role, or run my closure",
    # run in sequence.  Exactly one arm runs its closure, and a closure that
    # fails fails the whole Sequence with *its* reason as the last failed
    # child (BTBridge.get_failure_reason): a Case Owner whose closure failed
    # part-way is neither closed as an ordinary leaver nor reported with the
    # role check's feedback (CLP-07-013, #4442).
    return py_trees.composites.Sequence(
        name="OwnerOrNonOwnerEffects",
        memory=False,
        children=[
            py_trees.composites.Selector(
                name="OwnerLeaveArm",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="SenderIsNotCaseOwner",
                        child=with_case_id(
                            ActorHoldsRoleInCaseNode(
                                actor_id=sender_actor_id,
                                role=CVDRole.CASE_OWNER,
                                name="CheckIsCaseOwnerForLeave",
                            ),
                            case_id,
                        ),
                    ),
                    py_trees.composites.Sequence(
                        name="OwnerLeaveSeq",
                        memory=False,
                        children=owner_leave_children,
                    ),
                ],
            ),
            py_trees.composites.Selector(
                name="NonOwnerLeaveArm",
                memory=False,
                children=[
                    with_case_id(
                        ActorHoldsRoleInCaseNode(
                            actor_id=sender_actor_id,
                            role=CVDRole.CASE_OWNER,
                            name="CheckIsCaseOwnerForNonOwnerLeave",
                        ),
                        case_id,
                    ),
                    py_trees.composites.Sequence(
                        name="NonOwnerLeaveSeq",
                        memory=False,
                        # CM-23-003: only the leaver closes, each step on
                        # the ledger.
                        children=_close_and_record(
                            case_id, sender_actor_id, "LeavingParticipant"
                        ),
                    ),
                ],
            ),
        ],
    )
