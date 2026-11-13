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


"""Received-side BT factory for ``Remove(Note)[target=VulnerabilityCase]``.

Removing a note is not supported.  The case ledger is append-only, so a
removal would need a defined meaning for erasing what an entry already
records — a tombstone, hiding the note while its entry stays, or a ledger
that keeps the order of events but not their content — and the protocol
defines none yet (#6430, CM-30-003).  The message type stays known: its
pattern matches and its vocabulary parses.  Every receiver refuses it in its
one received tree, and nothing is detached, committed or sent but the
refusal notice the CASE_MANAGER owes the sender (CLP-05-001).
"""

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityUnsupportedNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    AuthoredNote,
    SenderCheckContext,
)

#: Why every ``Remove(Note)`` is refused (CM-30-003, #6430).
REMOVE_NOTE_UNSUPPORTED = (
    "Remove(Note)[target=VulnerabilityCase] is not supported: the case"
    " ledger is append-only and removing ledgered content has no defined"
    " meaning (CM-30-003)"
)

_TREE_NAME = "RefuseRemoveNoteBT"


def create_remove_note_from_case_received_tree(
    note_id: str | None,
    case_id: str | None,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Single-BT received-side tree for ``Remove(Note)[target=VulnerabilityCase]``.

    Structure (the CLP-10-010 stages)::

        RefuseRemoveNoteBT (Sequence)
        ├── ActivityAddressedToReceiverNode    # addressee door
        ├── ActivityNotSeenBeforeNode          # seen-before door
        ├── ReceivedPathNode                   # manager path only
        ├── CaseOpenToExternalWrites           # post-close boundary
        ├── SenderRuleGuard (Sequence)         # sender guard
        ├── SenderSequenceGate                 # the sender's number
        ├── IntakeReceivedActivityNode         # intake
        └── PreconditionGuardStage
            └── ActivityUnsupportedNode        # refuses every Remove(Note)

    The refusal is the tree's own guard, not a check in the use case
    (CM-30-003, #6430).  A replica is refused at the path stage, since only
    the CASE_MANAGER is addressed (PCR-08-001).  At the CASE_MANAGER the
    sender guard and the sender-sequence stage run first, so the sender's
    number is still counted (SYNC-21-008), and then the guard refuses even
    an entitled sender.  The commit the factory composes after the guards
    is never reached, so the note stays attached and nothing is ledgered.

    A ``Remove`` that names no note or no case is archived and refused as
    incomplete (CLP-10-018).

    Args:
        note_id: ID of the note the ``Remove`` names.
        case_id: ID of the case it names.
        sender_id: The activity's sender.
        sender_rule: The use case's declared sender rule (HP-01-008).

    Returns:
        Root ``RefuseRemoveNoteBT`` Sequence node.
    """
    if note_id is None or case_id is None:
        return create_incomplete_activity_received_tree(
            _TREE_NAME,
            "Remove(Note)[target=VulnerabilityCase] is missing its note id"
            " or case id",
        )
    return create_receive_activity_tree(
        name=_TREE_NAME,
        # The note's author or the Case Owner addresses the CASE_MANAGER
        # alone (PCR-08-001); no replica acts on a copy (HP-01-038).
        paths={ReceivedPath.CASE_MANAGER},
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id,
            case_id=case_id,
            authored_object=AuthoredNote(note_id=note_id),
        ),
        precondition_guards=[ActivityUnsupportedNode(REMOVE_NOTE_UNSUPPORTED)],
    )
