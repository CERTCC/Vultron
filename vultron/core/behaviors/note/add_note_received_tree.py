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

from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.note.nodes.storage import AttachNoteToCaseNode
from vultron.core.models.note import VultronNote

logger = logging.getLogger(__name__)


def create_add_note_to_case_received_tree(
    note_id: str,
    case_id: str,
    note: VultronNote | None = None,
    activity_id: str | None = None,
) -> py_trees.composites.Sequence:
    """Single-BT received-side tree for AddNoteToCase (ADR-0022, ADR-0111).

    Only the CaseActor (actor holding ``CVDRole.CASE_MANAGER``) commits a
    canonical ``CaseLedgerEntry`` for the ``Add(Note, Case)`` and attaches the
    note to the local case replica; the entry's ``Announce`` fan-out (via
    ``sync_port``) notifies all participants.  Non-CaseActors MUST NOT update
    their case replica directly from ``Add(Note, Case)`` messages — they
    receive the note attachment notification exclusively via
    ``Announce(CaseLedgerEntry)`` fan-out (SYNC-02-002).

    Structure (the four CLP-10-010 stages)::

        GuardedAttachAndCommitBT (Sequence)
        ├── IntakeReceivedActivityNode                 # intake
        ├── GuardedCommitCaseLedgerEntryBT (Selector)  # commit
        │   ├── SkipIfNotCaseManager
        │   └── CommitCaseLedgerEntryNode(case_id)
        └── GuardedAttachNoteBT (Selector)             # effect
            ├── SkipIfNotCaseManager
            └── Sequence
                ├── StoreReceivedNote(note)
                └── AttachNoteToCaseNode(note_id, case_id)

    Composed through :func:`create_receive_activity_tree`, which supplies the
    intake node and the guarded commit, so the tree cannot opt out of either
    (CLP-10-017) and the ordering ratchet can assert factory coverage.  The
    attach effect is passed as ``manager_effects``, so the factory gates it
    with :func:`create_case_manager_gated_tree` (BT-17-008) rather than a
    hand-rolled Selector: the obvious ``Success`` fallback could not
    distinguish "not the case manager" from "am the case manager and the
    attach failed" (BTND-07-005; cf. the fake-SUCCESS rule in ``AGENTS.md``).

    The CASE_MANAGER stores the Note from the copy the event carries before
    attaching it, unless it already holds one under that id.  Ingress stores
    nothing from an inline object (CLP-10-017), so this effect is the only
    write of the Note at the CASE_MANAGER (#3763).  A Note named by bare
    reference has nothing to store and is attached by id alone.

    Args:
        note_id: ID of the Note being attached to the case.
        case_id: ID of the VulnerabilityCase receiving the note.
        note: The Note the event carries, when the sender inlined it.
        activity_id: The received activity's id, for the store's log line.

    Returns:
        Root ``GuardedAttachAndCommitBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="GuardedAttachAndCommitBT",
        case_id=case_id,
        precondition_guards=[],
        manager_effects=[
            StoreReceivedObjectNode(
                note.type_ if note is not None else None,
                note_id,
                note,
                "Note",
                activity_id,
                name="StoreReceivedNote",
            ),
            AttachNoteToCaseNode(note_id=note_id, case_id=case_id),
        ],
        manager_case_id=case_id,
        manager_gate_name="GuardedAttachNoteBT",
    )
