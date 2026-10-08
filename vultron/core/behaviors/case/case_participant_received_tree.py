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

"""Tree factories for received Add/Remove CaseParticipant activities.

Each factory composes its leaf nodes through
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
so intake archives the received activity first (CLP-10-017) and a refused
delivery still leaves its record (CLP-10-018).

Both trees are Case Owner requests to the CASE_MANAGER (ADR-0116): ``Remove``
takes a participant out of active participation (CM-31-004), and ``Add``
reinstates a removed one (CM-31-011).  Each received activity is the move's
one ledger entry (CM-31-005), and every write is gated on the CASE_MANAGER
role, so a replica that receives either stores the activity and writes
nothing (RSH-08-003); the replica takes the move from the ledger entry
instead (CM-31-007).
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.case_participant_received import (
    EmitParticipantRemovalNoticeNode,
    RemoveCaseParticipantFromCaseReceivedNode,
    case_manager_admits_removal_guard,
)
from vultron.core.behaviors.case.nodes.participant_reinstatement import (
    EmitParticipantReinstatementNoticeNode,
    ReinstateCaseParticipantReceivedNode,
    case_manager_admits_reinstatement_guard,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_role_scoped_sender_guard,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    InviteReinstatedParticipantToEmbargoNode,
)
from vultron.core.behaviors.sender_entitlement import SenderIsCaseOwnerNode
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)

logger = logging.getLogger(__name__)


def create_add_case_participant_received_tree(
    participant_id: str,
    case_id: str,
    sender_id: str,
    claimed_actor_id: str | None = None,
) -> py_trees.composites.Sequence:
    """Create the BT for ``AddCaseParticipantToCaseReceivedUseCase``.

    ``Add(CaseParticipant)`` is the Case Owner's request to reinstate a
    removed participant (CM-31-011, ADR-0116), and mirrors the removal tree
    stage for stage (the CLP-10-010 stages, ADR-0111)::

        AddCaseParticipantReceivedBT (Sequence)
        ├── IntakeReceivedActivityNode                       # intake
        ├── AddParticipantSenderGuard (Selector)             # sender guard
        ├── ReinstatementAdmissibleIfCaseManager (Selector)  # guards (manager only)
        │   ├── MoveNamesCaseParticipantNode
        │   ├── ParticipantHasJoinedNode
        │   └── ParticipantIsRemovedNode
        ├── GuardedCommitCaseLedgerEntryBT (Selector)        # commit
        └── GuardedReinstateParticipantBT (Selector)         # effects (manager only)
            ├── ReinstateCaseParticipantReceivedNode
            ├── BackfillAdmittedParticipantsNode
            ├── EmitParticipantReinstatementNoticeNode
            └── InviteReinstatedParticipantToEmbargoNode

    The sender guard admits the Case Owner at the CASE_MANAGER and only the
    CASE_MANAGER at any other replica (ADR-0115, PCR-03-001), which is how
    the reinstated participant's own replica accepts the direct notice.  The
    commit runs before the effect, so the entry's fan-out withholds it from
    the participant, still removed, and records it in that participant's
    paused stream.  Once the fact is cleared, the admission backfill sends
    the participant every entry from the first one withheld after its
    removal entry, the reinstatement entry included, in log order
    (CM-10-006); a participant that is not ``SIGNATORY`` to the active
    embargo is not admitted yet, so it is sent that embargo's Invite instead
    and its backfill waits for its consent (CM-31-013).  At a replica every
    gated stage skips: intake is its only write (RSH-08-003).

    Args:
        participant_id: URI of the ``CaseParticipant`` the ``Add`` names.
        case_id: URI of the case.
        sender_id: The activity's sender, who must be the Case Owner.
        claimed_actor_id: The actor the inline participant is attributed to,
            when it names one; it must match the stored record's actor
            (CM-31-011), because a replica resolves the record by it.  The
            notice and any embargo Invite go to the stored record's actor.

    Returns:
        The root ``Sequence``, ready for ``BTBridge.execute_with_setup()``.
    """
    root = create_receive_activity_tree(
        name="AddCaseParticipantReceivedBT",
        case_id=case_id,
        sender_guard=create_role_scoped_sender_guard(
            name="AddParticipantSenderGuard",
            case_id=case_id,
            at_case_manager=SenderIsCaseOwnerNode(
                sender_actor_id=sender_id, case_id=case_id
            ),
        ),
        precondition_guards=[
            case_manager_admits_reinstatement_guard(
                participant_id=participant_id,
                case_id=case_id,
                claimed_actor_id=claimed_actor_id,
            )
        ],
        manager_case_id=case_id,
        manager_gate_name="GuardedReinstateParticipantBT",
        manager_effects=[
            ReinstateCaseParticipantReceivedNode(
                participant_id=participant_id, case_id=case_id
            ),
            BackfillAdmittedParticipantsNode(case_id=case_id),
            EmitParticipantReinstatementNoticeNode(
                participant_id=participant_id,
                case_id=case_id,
                requesting_actor_id=sender_id,
            ),
            InviteReinstatedParticipantToEmbargoNode(
                case_id=case_id,
                participant_id=participant_id,
            ),
        ],
    )
    logger.debug(
        "Created AddCaseParticipantReceivedBT for participant='%s' case='%s'",
        participant_id,
        case_id,
    )
    return root


def create_remove_case_participant_received_tree(
    participant_id: str,
    case_id: str,
    sender_id: str,
    removal_activity_id: str,
    claimed_actor_id: str | None = None,
) -> py_trees.composites.Sequence:
    """Create the BT for ``RemoveCaseParticipantFromCaseReceivedUseCase``.

    Structure (the CLP-10-010 stages, ADR-0111)::

        RemoveCaseParticipantReceivedBT (Sequence)
        ├── IntakeReceivedActivityNode                  # intake
        ├── RemoveParticipantSenderGuard (Selector)     # sender guard
        ├── RemovalAdmissibleIfCaseManager (Selector)   # guards (manager only)
        │   ├── MoveNamesCaseParticipantNode
        │   ├── RemovalTargetIsRemovableNode
        │   └── ParticipantNotYetRemovedNode            # idempotency
        ├── GuardedCommitCaseLedgerEntryBT (Selector)   # commit
        └── GuardedRemoveParticipantBT (Selector)       # effects (manager only)
            ├── RemoveCaseParticipantFromCaseReceivedNode
            └── EmitParticipantRemovalNoticeNode

    The sender guard admits the Case Owner at the CASE_MANAGER and only the
    CASE_MANAGER at any other replica (ADR-0115, PCR-03-001), which is how
    the removed participant's own replica accepts the direct notice.  The
    commit runs before the effect, so the entry's fan-out selects its
    recipients while the removed participant is still active (CM-31-006).
    At a replica every gated stage skips: intake is its only write
    (RSH-08-003).

    Args:
        participant_id: URI of the ``CaseParticipant`` the removal names.
        case_id: URI of the case.
        sender_id: The activity's sender, who must be the Case Owner.
        removal_activity_id: The received ``Remove`` activity's id, recorded
            as the removal fact (CM-31-001).
        claimed_actor_id: The actor the inline participant is attributed to,
            when it names one; it must match the stored record's actor
            (CM-31-004), because a replica resolves the record by it.

    Returns:
        The root ``Sequence``, ready for ``BTBridge.execute_with_setup()``.
    """
    root = create_receive_activity_tree(
        name="RemoveCaseParticipantReceivedBT",
        case_id=case_id,
        sender_guard=create_role_scoped_sender_guard(
            name="RemoveParticipantSenderGuard",
            case_id=case_id,
            at_case_manager=SenderIsCaseOwnerNode(
                sender_actor_id=sender_id, case_id=case_id
            ),
        ),
        precondition_guards=[
            case_manager_admits_removal_guard(
                participant_id=participant_id,
                case_id=case_id,
                claimed_actor_id=claimed_actor_id,
            )
        ],
        manager_case_id=case_id,
        manager_gate_name="GuardedRemoveParticipantBT",
        manager_effects=[
            RemoveCaseParticipantFromCaseReceivedNode(
                participant_id=participant_id,
                case_id=case_id,
                removal_activity_id=removal_activity_id,
            ),
            EmitParticipantRemovalNoticeNode(
                participant_id=participant_id,
                case_id=case_id,
                requesting_actor_id=sender_id,
            ),
        ],
    )
    logger.debug(
        "Created RemoveCaseParticipantReceivedBT"
        " for participant='%s' case='%s'",
        participant_id,
        case_id,
    )
    return root
