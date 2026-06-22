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

"""Received-side BT factory for the add-note-to-case workflow (ADR-0022).

The canonical notification mechanism for note additions is
``Announce(CaseLedgerEntry)`` fan-out from the guarded-commit step
(SYNC-02-002), **not** a direct ``AddNoteToCase`` broadcast to participants.
Only the CaseActor may update the canonical case replica; non-CaseActor
participants must not modify their local replica directly from
``Add(Note, Case)`` messages.
See ``notes/case-communication-model.md`` for the full communication model.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.note.nodes.storage import AttachNoteToCaseNode

logger = logging.getLogger(__name__)


def create_add_note_to_case_received_tree(
    note_id: str,
    case_id: str,
) -> py_trees.composites.Selector:
    """Single-BT received-side tree for AddNoteToCase (ADR-0022).

    Only the CaseActor (actor holding ``CVDRole.CASE_MANAGER``) attaches the
    note to the local case replica and commits a canonical
    ``CaseLedgerEntry`` whose ``Announce`` fan-out (via ``sync_port``)
    notifies all participants.  Non-CaseActors MUST NOT update their case
    replica directly from ``Add(Note, Case)`` messages — they receive the
    note attachment notification exclusively via ``Announce(CaseLedgerEntry)``
    fan-out (SYNC-02-002).

    Structure::

        GuardedAttachAndCommitBT (Selector)
        ├── Sequence (CaseManager path)
        │   ├── CheckIsCaseManagerNode
        │   ├── AttachNoteToCaseNode(note_id, case_id)
        │   └── CommitCaseLedgerEntryNode(case_id)
        └── Success("AttachAndCommitSkippedNotCaseManager")

    Args:
        note_id: ID of the Note being attached to the case.
        case_id: ID of the VulnerabilityCase receiving the note.

    Returns:
        Root ``GuardedAttachAndCommitBT`` Selector node.
    """
    return py_trees.composites.Selector(
        name="GuardedAttachAndCommitBT",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="AttachAndCommitIfCaseManager",
                memory=False,
                children=[
                    CheckIsCaseManagerNode(case_id=case_id),
                    AttachNoteToCaseNode(note_id=note_id, case_id=case_id),
                    CommitCaseLedgerEntryNode(case_id=case_id),
                ],
            ),
            py_trees.behaviours.Success(
                name="AttachAndCommitSkippedNotCaseManager"
            ),
        ],
    )
