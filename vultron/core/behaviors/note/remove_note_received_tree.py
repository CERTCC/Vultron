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

"""Received-side BT factory for ``Remove(Note, Case)``.

Mirror of :mod:`add_note_received_tree`: only the CASE_MANAGER detaches the note
and commits the canonical ledger entry; replicas apply the entry's fan-out
(SYNC-02-002, RSH-08-004).  At the manager the sender must be the note's author
(while an active participant) or the Case Owner (CM-30-001, ADR-0115).
"""

import py_trees

from vultron.core.behaviors.case.nodes.reference_list import (
    CaseReferenceEditPendingNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_role_scoped_sender_guard,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.note.nodes.storage import DetachNoteFromCaseNode
from vultron.core.behaviors.sender_entitlement import (
    SenderIsCaseOwnerNode,
    SenderIsNoteAuthorNode,
)


def create_remove_note_from_case_received_tree(
    note_id: str,
    case_id: str,
    sender_id: str,
) -> py_trees.composites.Sequence:
    """Single-BT received-side tree for ``Remove(Note, Case)`` (ADR-0111).

    Structure (the CLP-10-010 stages)::

        GuardedDetachAndCommitBT (Sequence)
        ├── IntakeReceivedActivityNode                    # intake
        ├── RemoveNoteSenderGuard (Selector)              # sender guard
        ├── CaseReferenceEditPendingNode                  # duplicate guard
        ├── GuardedCommitCaseLedgerEntryBT (Selector)     # commit
        └── GuardedDetachNoteBT (Selector)                # effect

    A note the case does not hold fails the duplicate guard before anything is
    committed; the handler reports it as ``SKIPPED``.

    Args:
        note_id: ID of the note being removed.
        case_id: ID of the case the note leaves.
        sender_id: The activity's sender.
    """
    author_or_owner = py_trees.composites.Selector(
        name="NoteAuthorOrCaseOwner",
        memory=False,
        children=[
            SenderIsNoteAuthorNode(
                note_id=note_id, sender_actor_id=sender_id, case_id=case_id
            ),
            SenderIsCaseOwnerNode(sender_actor_id=sender_id, case_id=case_id),
        ],
    )
    return create_receive_activity_tree(
        name="GuardedDetachAndCommitBT",
        case_id=case_id,
        sender_guard=create_role_scoped_sender_guard(
            name="RemoveNoteSenderGuard",
            case_id=case_id,
            at_case_manager=author_or_owner,
        ),
        precondition_guards=[
            CaseReferenceEditPendingNode(
                ref_id=note_id, case_id=case_id, field="notes", attach=False
            )
        ],
        effect_nodes=[
            create_case_manager_gated_tree(
                name="GuardedDetachNoteBT",
                case_id=case_id,
                children=[
                    DetachNoteFromCaseNode(note_id=note_id, case_id=case_id)
                ],
            )
        ],
    )
