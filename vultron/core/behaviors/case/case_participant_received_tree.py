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


"""Tree factories for the Case Owner's received removal and reinstatement acts.

Each factory composes its leaf nodes through
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
so intake records the received activity once its doors admit it
(CLP-10-017) and a refused delivery still leaves a receipt stub (CLP-10-018).

The Case Owner decides both moves and sends each as its own act, to the
CASE_MANAGER only (ADR-0199): ``Remove(<Actor>, origin=<case>)`` takes a
participant out of active participation (CM-31-004), and
``Add(<Actor>, target=<case>)`` reinstates a removed one (CM-31-011).  The
CASE_MANAGER refuses an act that breaks the rules with a refusal notice and
commits nothing; otherwise it admits the Owner's act as the move's one ledger
entry (CM-31-005, CM-31-044), changes the record, and announces the act to
the actor it names.  It sends no ``Accept`` and makes no act of its own.  A
replica takes the move from the ledger entry (CM-31-007, CM-31-045), never
from the act or its ``Announce``, so the trees declare the manager path
alone and any other receiver is refused at the path stage (HP-01-038).

Both trees declare ``/participant_actor_id``, the actor the act names, as an
input the runner seeds from the act (BT-25-006, BT-25-007).
"""

import logging

import py_trees

from vultron.core.behaviors.act_inputs import declare_inputs
from vultron.core.behaviors.act_keys import PARTICIPANT_ACTOR_ID
from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.case_participant_received import (
    AnnounceParticipantMoveNode,
    RecordParticipantRemovalNode,
    case_manager_admits_removal_guard,
)
from vultron.core.behaviors.case.nodes.participant_reinstatement import (
    ClearParticipantRemovalNode,
    case_manager_admits_reinstatement_guard,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.embargo.nodes.reinvite import (
    InviteReinstatedParticipantToEmbargoNode,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)

logger = logging.getLogger(__name__)

#: The act each tree refuses when it names no case (CLP-10-018).
REINSTATEMENT_ACT = "Add(<Actor>, target=VulnerabilityCase)"
REMOVAL_ACT = "Remove(<Actor>, origin=VulnerabilityCase)"


def missing_ids_reason(act: str) -> str:
    """The refusal of a move naming no actor or no case (CLP-10-018)."""
    return f"{act} is missing the actor it names or its case"


def create_add_case_participant_received_tree(
    case_id: str | None,
    sender_id: str,
    activity_id: str | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``ReinstateParticipantInCaseReceivedUseCase``.

    ``Add(<Actor>, target=<case>)`` is the Case Owner's reinstatement of a
    removed participant (CM-31-011, ADR-0199), and mirrors the removal tree
    stage for stage (the CLP-10-010 stages, ADR-0111)::

        ReinstateParticipantReceivedBT (Sequence)
        ├── ActivityAddressedToReceiverNode                  # addressee door
        ├── ActivityNotSeenBeforeNode                        # seen-before door
        ├── ReceivedPathNode                                 # manager only
        ├── SenderRuleGuard (Sequence)                       # the Case Owner
        ├── IntakeReceivedActivityNode                       # intake
        ├── ReinstatementAdmissible (Sequence)               # guards
        │   ├── ActivityNotYetLedgeredNode                   # repeat: SKIPPED
        │   ├── NamedParticipantIsNotProtectedNode
        │   ├── ParticipantHasJoinedNode
        │   └── ParticipantIsRemovedNode
        ├── GuardedCommitCaseLedgerEntryBT (Selector)        # commit
        └── GuardedReinstateParticipantBT (Selector)         # effects
            ├── ClearParticipantRemovalNode
            ├── BackfillAdmittedParticipantsNode
            ├── AnnounceParticipantMoveNode
            └── InviteReinstatedParticipantToEmbargoNode

    The commit runs before the effects, so the entry's fan-out withholds it
    from the participant, still removed, and records it in that
    participant's paused stream.  Once the fact is cleared, the admission
    backfill sends the participant every entry from the first one withheld
    after its removal entry, the reinstatement entry included, in log order
    (CM-10-006); a participant that is not a signatory to the active
    embargo is not admitted yet, so it is sent that embargo's Invite instead
    and its backfill waits for its consent (CM-31-040).  The reinstated
    actor is also sent the CASE_MANAGER's ``Announce`` of the Owner's act
    (CM-31-044).

    A reinstatement naming no case is refused by the same tree's guard
    instead (``ActivityIncompleteNode``), so either way the delivery runs
    one tree and is archived (CLP-10-005, CLP-10-018).

    Args:
        case_id: URI of the case.
        sender_id: The activity's sender, who must be the Case Owner.
        activity_id: The Owner's ``Add``'s id; the embargo Invite's id is
            derived from it, so a redelivery rebuilds the same Invite
            (OX-06-002).
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        The root node, ready for ``BTBridge.execute_with_setup()``.
    """
    name = "ReinstateParticipantReceivedBT"
    if case_id is None:
        return create_incomplete_activity_received_tree(
            name, missing_ids_reason(REINSTATEMENT_ACT)
        )
    root = create_receive_activity_tree(
        name=name,
        case_id=case_id,
        # The Case Owner sends the act to the CASE_MANAGER only; a replica
        # takes the move from the ledger entry, so any other receiver is
        # refused at the path stage (HP-01-038, RSH-08-003).
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id, case_manager_required=True
        ),
        precondition_guards=[case_manager_admits_reinstatement_guard(case_id)],
        manager_case_id=case_id,
        manager_gate_name="GuardedReinstateParticipantBT",
        manager_effects=[
            with_case_id(ClearParticipantRemovalNode(), case_id),
            with_case_id(BackfillAdmittedParticipantsNode(), case_id),
            with_case_id(AnnounceParticipantMoveNode(), case_id),
            InviteReinstatedParticipantToEmbargoNode(
                case_id=case_id, answers=activity_id
            ),
        ],
    )
    declare_inputs(root, seeded=[PARTICIPANT_ACTOR_ID])
    logger.debug(
        "Created ReinstateParticipantReceivedBT for case='%s'", case_id
    )
    return root


def create_remove_case_participant_received_tree(
    case_id: str | None,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``RemoveParticipantFromCaseReceivedUseCase``.

    Structure (the CLP-10-010 stages, ADR-0111)::

        RemoveParticipantReceivedBT (Sequence)
        ├── ActivityAddressedToReceiverNode             # addressee door
        ├── ActivityNotSeenBeforeNode                   # seen-before door
        ├── ReceivedPathNode                            # manager only
        ├── SenderRuleGuard (Sequence)                  # the Case Owner
        ├── IntakeReceivedActivityNode                  # intake
        ├── RemovalAdmissible (Sequence)                # guards
        │   ├── NamedParticipantIsNotProtectedNode
        │   └── ParticipantNotYetRemovedNode            # idempotency
        ├── GuardedCommitCaseLedgerEntryBT (Selector)   # commit
        └── GuardedRemoveParticipantBT (Selector)       # effects
            ├── RecordParticipantRemovalNode
            └── AnnounceParticipantMoveNode

    The commit runs before the effects, so the entry's fan-out selects its
    recipients while the removed participant is still active (CM-31-027).
    The removed actor is also sent the CASE_MANAGER's ``Announce`` of the
    Owner's act (ADR-0199).

    A removal naming no case is refused by the same tree's guard instead,
    as for the reinstatement tree.

    Args:
        case_id: URI of the case.
        sender_id: The activity's sender, who must be the Case Owner.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        The root node, ready for ``BTBridge.execute_with_setup()``.
    """
    name = "RemoveParticipantReceivedBT"
    if case_id is None:
        return create_incomplete_activity_received_tree(
            name, missing_ids_reason(REMOVAL_ACT)
        )
    root = create_receive_activity_tree(
        name=name,
        case_id=case_id,
        # The Case Owner sends the act to the CASE_MANAGER only; a replica
        # takes the move from the ledger entry, so any other receiver is
        # refused at the path stage (HP-01-038, RSH-08-003).
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id, case_manager_required=True
        ),
        precondition_guards=[case_manager_admits_removal_guard(case_id)],
        manager_case_id=case_id,
        manager_gate_name="GuardedRemoveParticipantBT",
        manager_effects=[
            with_case_id(RecordParticipantRemovalNode(), case_id),
            with_case_id(AnnounceParticipantMoveNode(), case_id),
        ],
    )
    declare_inputs(root, seeded=[PARTICIPANT_ACTOR_ID])
    logger.debug("Created RemoveParticipantReceivedBT for case='%s'", case_id)
    return root
