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
(SYNC-02-001, SYNC-02-003), **not** a direct ``AddNoteToCase`` broadcast to
participants.
Only the CaseActor may update the canonical case replica; non-CaseActor
participants must not modify their local replica directly from
``Add(Note)[target=VulnerabilityCase]`` messages.
See ``notes/case-communication-model.md`` for the full communication model.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.carried_object_case import (
    CarriedObjectInTargetCaseNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.note.nodes.storage import (
    AttachNoteToCaseNode,
    NoteIdNotTakenNode,
    StoreNoteIfAbsentNode,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.models.note import VultronNote

logger = logging.getLogger(__name__)


def create_add_note_to_case_received_tree(
    note_obj: VultronNote,
    case_id: str,
    sender_id: str,
    activity_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Single-BT received-side tree for AddNoteToCase (ADR-0022, ADR-0111).

    Only the CaseActor (actor holding ``CVDRole.CASE_MANAGER``) commits a
    canonical ``CaseLedgerEntry`` for the ``Add(Note)[target=VulnerabilityCase]`` and
    attaches the
    note to the local case replica; the entry's ``Announce`` fan-out (via
    ``sync_port``) notifies all participants.  Non-CaseActors MUST NOT update
    their case replica directly from ``Add(Note)[target=VulnerabilityCase]`` messages — they
    receive the note attachment notification exclusively via
    ``Announce(CaseLedgerEntry)`` fan-out (SYNC-02-001, SYNC-02-003).

    Structure (the four CLP-10-010 stages)::

        GuardedAttachAndCommitBT (Sequence)
        ├── IntakeReceivedActivityNode                 # intake
        ├── CaseOpenToExternalWrites                   # post-close boundary
        ├── ActivityAddressedToReceiverNode            # addressee door
        ├── ReceivedPathNode                           # manager or replica
        ├── SenderRuleGuard (Sequence)                 # sender guard
        ├── CaseManagerGate[ClockDecisionStage]        # embargo end-time check
        ├── PreconditionGuards
        │   ├── NoteIdNotTakenNode(note_id)            # guard
        │   └── CarriedObjectInTargetCaseNode(note)    # guard
        ├── GuardedCommitCaseLedgerEntryBT (Selector)  # commit
        │   ├── SkipIfNotCaseManager
        │   └── CommitCaseLedgerEntryNode(case_id)
        └── GuardedAttachNoteBT (Selector)             # effect
            ├── SkipIfNotCaseManager
            └── Sequence
                ├── StoreNoteIfAbsentNode(note_obj)
                └── AttachNoteToCaseNode(note_obj.id_, case_id)

    The ``Add`` carries the note inline (VAM-01-015), so the CASE_MANAGER
    stores the note before attaching it, and the case never references a
    note the CASE_MANAGER cannot read.  Storing it is part of what the
    ``Add`` states, so it is part of the change the ``add_note_to_case``
    entry records (CLP-07-013); a replica stores the same note from the
    entry's snapshot.  An ``Add`` introduces a new note, so the guards
    refuse one whose note id is already stored, whatever it carries (a
    change is an ``Update(Note)``), unless it is a redelivery of the
    ``Add`` the ledger already records, which is ``SKIPPED``; and they
    refuse a note whose own ``context`` is not this case (HP-08-006).  The
    inbox's routing rebuild hands the tree the stored note in place of the
    carried one (IO-03-004), so neither guard compares the two copies.

    Composed through :func:`create_receive_activity_tree`, which supplies the
    intake node and the guarded commit, so the tree cannot opt out of either
    (CLP-10-017) and the ordering ratchet can assert factory coverage.  The
    attach effect is passed as ``manager_effects``, so the factory gates it
    with :func:`create_case_manager_gated_tree` (BT-17-008) rather than a
    hand-rolled Selector: the obvious ``Success`` fallback could not
    distinguish "not the case manager" from "am the case manager and the
    attach failed" (BTND-07-005; cf. the fake-SUCCESS rule in ``AGENTS.md``).

    The factory composes the sender guard from *sender_rule* (HP-01-025):
    at the CASE_MANAGER the sender must be an active participant whose
    closure the case does not record (CM-23-018), and a replica takes the
    attachment from the CASE_MANAGER alone (PCR-03-001).  Those are the two
    non-empty sides of the rule, so they are the two paths the tree declares
    (HP-01-038); the path stage then answers the role question once and the
    guard's arms read its answer rather than asking again (HP-01-036).

    Args:
        note_obj: The note the ``Add`` carries inline.
        case_id: ID of the VulnerabilityCase receiving the note.
        sender_id: The ``Add(Note)``'s sender.
        activity_id: The ``Add(Note)``'s id, to recognise a redelivery.
        sender_rule: The use case's declared sender rule (HP-01-008).

    Returns:
        Root ``GuardedAttachAndCommitBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="GuardedAttachAndCommitBT",
        # An active participant asks the CASE_MANAGER to attach the note, and
        # a replica takes the attachment from the CASE_MANAGER alone
        # (PCR-03-001, PCR-08-001): the two non-empty sides of the sender
        # rule, so the two declared paths (HP-01-038).  The replica path
        # carries no effect of its own — RSH-08-003 keeps every write at the
        # CASE_MANAGER, so the note reaches a replica as the entry's Announce
        # fan-out (SYNC-02-001, SYNC-02-003) and a direct Add(Note) there is
        # refused (HP-01-005).  It is declared all the same: the act is the
        # CASE_MANAGER's to relay (PCR-03-001), and naming fewer paths than
        # the type works on would refuse at the door a delivery the sender
        # guard admits (HP-01-038).
        paths={ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id
        ),
        precondition_guards=[
            NoteIdNotTakenNode(
                note_id=note_obj.id_, case_id=case_id, activity_id=activity_id
            ),
            CarriedObjectInTargetCaseNode(
                object_id=note_obj.id_, carried=note_obj, case_id=case_id
            ),
        ],
        manager_effects=[
            StoreNoteIfAbsentNode(note_obj=note_obj),
            AttachNoteToCaseNode(note_id=note_obj.id_, case_id=case_id),
        ],
        manager_case_id=case_id,
        manager_gate_name="GuardedAttachNoteBT",
    )
