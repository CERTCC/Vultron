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

"""The close-case received-tree factory (ADR-0022, CM-23)."""

import py_trees

from vultron.config.actor import DEFAULT_POST_CLOSE_REPLY, PostCloseReply
from vultron.core.behaviors.case.nodes.addressee import (
    ENCLOSING_TREE_ADDRESSEE_CHECK,
)
from vultron.core.behaviors.case.nodes.held_case import (
    CaseNamedByReference,
)
from vultron.core.behaviors.case.nodes.leave import (
    CaseManagerLeavesOnlyAsCaseOwnerNode,
    RefuseOwnerCloseWhileEmbargoedNode,
)
from vultron.core.behaviors.case.nodes.post_close import PostCloseExemption
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.nodes.refusal_notice import refusal_notice
from vultron.core.behaviors.case.owner_close_embargo_guards import (
    owner_close_not_blocked_by_embargo,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.receive_close_case_tree.closure_effects import (
    owner_or_non_owner_effects as build_owner_or_non_owner_effects,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    SenderCheckContext,
)
from vultron.errors import VultronWiringError


def create_close_case_received_tree(
    case_id: str,
    sender_actor_id: str | None = None,
    receiving_actor_id: str | None = None,
    post_close_reply: PostCloseReply = DEFAULT_POST_CLOSE_REPLY,
    *,
    sender_rule: SenderRule | None = None,
) -> py_trees.behaviour.Behaviour:
    """Single-BT received-side tree for CloseCaseReceived (ADR-0022).

    When ``sender_actor_id`` is provided, the tree branches on the sender's
    ``CVDRole.CASE_OWNER`` role (CM-23-002/CM-23-003):

    - Owner Leave, no active embargo → expire pending embargo Invites,
      advance leaving participant to ``RM.CLOSED``, then advance the
      CaseActor to ``RM.CLOSED`` (owner path, CM-23-002).
    - Owner Leave while an embargo is live (``active_embargo`` non-None and EM
      state ``ACTIVE`` or ``REVISE``) → the close's guard refuses it, so
      **none** of the CM-23-002 closure effects runs and nothing is committed;
      the factory answers the owner with the standard refusal notice, a
      ``Refuse`` of the Leave (CM-23-011, ADR-0196).  The owner must terminate
      the embargo first, then send its Leave again.
    - Non-owner Leave → advance only the leaving participant to ``RM.CLOSED``;
      case remains open (non-owner path, CM-23-003, CM-23-030).
    - Any Leave after the case is fully closed → refused by the post-close guard
      before the close, so the receipt ``GuardedCommitOrSkip`` never runs:
      nothing is committed or fanned out (CM-23-013).  The same shape as the
      CM-23-011 refusal: the guard gates the receipt commit itself.

    When ``sender_actor_id`` is ``None`` (e.g., in legacy paths or tests that
    do not supply it), the tree falls back to the pre-#1901 behaviour: intake
    and the guarded receipt commit only, no participant state mutation.

    Structure (with role semantics)::

        CloseCaseBT (Sequence, via create_receive_activity_tree)
        ├── ActivityAddressedToReceiverNode             # addressee door (HP-01-005)
        ├── ActivityNotSeenBeforeNode                   # seen-before door
        ├── ReceivedPathNode                            # manager path only
        ├── CaseOpenToExternalWrites                    # post-close boundary (CM-23-013)
        │       (under PostCloseReply.REJECT: a PostCloseStage whose refusal
        │        arm sends the refusal notice at the CASE_MANAGER)
        ├── SenderRuleGuard                             # composed from sender_rule (HP-01-025)
        ├── IntakeReceivedActivityNode                  # record the Leave (CLP-10-017)
        ├── ClockDecisions (CaseManagerGate)            # embargo end-time check (CLP-10-051)
        └── CloseIfCaseManager (CaseManagerGate)        # BT-17-008, #3825
            └── CloseCaseReceive (Sequence, via create_receive_activity_tree)
                │   (nested=True: no seen-before door or intake, and no
                │    addressee or post-close door: CloseCaseBT's ran first)
                ├── PreconditionGuardStage              # refusal → notice (CLP-02-005)
                │   ├── CaseManagerLeavesOnlyAsCaseOwner    # guard: CM-23-010
                │   ├── OwnerCloseNotBlockedByEmbargo (Selector)  # guard: CM-23-011
                │   │   ├── Inverter(OwnerCloseBlockedByEmbargoCheck)
                │   │   │   └── Sequence: CheckIsCaseOwner → ReadEmState
                │   │   │              → IsCloseBlockedByActiveEmbargo
                │   │   └── RefuseOwnerCloseWhileEmbargoed   # FAILURE, the reason
                │   └── (on refusal) EmitRefusalNotice      # Refuse(Leave) to the sender
                ├── GuardedCommitOrSkip (Selector)      # Record receipt (CLP-10-006)
                │   ├── Sequence(SkipIfNotCaseManager)
                │   │   └── Inverter(CheckIsCaseManagerNode)
                │   └── CommitCaseLedgerEntryNode       # commits the close_case entry
                └── CloseCaseEffectsIfCaseManager (CaseManagerGate)  # RSH-08-003, #3814
                    └── OwnerOrNonOwnerEffects (Sequence)   # one arm per role
                        ├── OwnerLeaveArm (Selector)        # Owner path (CM-23-002)
                        │   ├── Inverter(SenderIsCaseOwnerNode)  # skip: not CASE_OWNER
                        │   └── OwnerLeaveSeq (Sequence)
                        │       ├── ExpirePendingInvitesOnCloseNode   # pending Invites (CM-23-014)
                        │       ├── AdvanceParticipantToRMClosedNode  # step 1: owner → RM.CLOSED
                        │       ├── CommitRMClosureEntriesNode   # step 1, ledgered (CM-23-022)
                        │       ├── AdvanceCaseActorToRMClosedNode  # step 2: CaseActor
                        │       └── CommitRMClosureEntriesNode   # step 2: the boundary
                        └── NonOwnerLeaveArm (Selector)     # Non-owner (CM-23-003)
                            ├── SenderIsCaseOwnerNode            # skip: sender is CASE_OWNER
                            └── NonOwnerLeaveSeq (Sequence)
                                ├── AdvanceParticipantToRMClosedNode  # departing → RM.CLOSED
                                └── CommitRMClosureEntriesNode   # ledgered (CM-23-022)

    Intake runs after the doors, ahead of the gate, so the inbound Leave is
    recorded once the doors admit it (CLP-10-010, CLP-10-017); the doors admit
    only the case's CASE_MANAGER, since the tree declares the manager path
    alone (HP-01-038, #6394).  The per-arm ``StoreActivityNode``
    this tree once carried duplicated it and was removed (CLP-10-019).  The
    inner ``CloseCaseReceive`` is built by the same factory because only the
    factory supplies the guarded receipt commit.  It is built ``nested``, with
    no seen-before door or intake of its own: the outer tree's door answered
    the delivery and its intake recorded it, so an inner intake would meet
    that record and read the first run as a re-run (ADR-0154).

    ``CloseCaseReceive`` is passed as the factory's ``manager_effects``, so
    the factory wraps the whole close in a CASE_MANAGER gate (BT-17-008).
    Only the case's CASE_MANAGER refuses an owner close (CM-23-011) or runs
    its closure effects (CM-23-002/003); a replica holding a copy of the
    Leave is refused at the path stage, sends nothing (the #3825 defect),
    writes nothing, and takes any resulting closure from the ledger fan-out
    (CLP-10-001, RSH-08-003, HP-01-005).

    A refused close commits nothing.  That matters, because committing and
    fanning out the ``close_case`` ledger entry is exactly what advances
    participants to ``RM.CLOSED`` on the replicas (CLP-10-001); so a refused
    close leaves the case untouched and only sends the refusal notice, and
    the notice's own failure (no trigger port) cannot let the close run.

    The owner arm's ledger order is therefore: ``close_case``, one
    ``TIMED_OUT`` ``Update(EmbargoConsent)`` per pending embargo Invite, the
    Case Owner's status entries, then the CASE_MANAGER's own status entries,
    the one reaching ``RM.CLOSED`` last: it is the write boundary (CM-23-002,
    CM-23-013, CM-23-014).  A Case Owner that also holds CASE_MANAGER is
    closed once, and its own ``RM.CLOSED`` entry is then the boundary.  Each
    advance shares a ``closure_steps`` list with the record node after it, so the record
    commits exactly the statuses that advance wrote, in order.

    Running under ``actor_id=receiving_actor_id`` means
    ``CheckIsCaseManagerNode`` naturally gates the commit to the actor that
    holds ``CVDRole.CASE_MANAGER`` — no identity comparison needed in Python.

    Args:
        case_id: ID of the VulnerabilityCase being closed.
        sender_actor_id: Actor URI of the Leave sender (resolved from the
            inbound Leave activity's ``actor`` field).  When provided, the tree
            applies role-discriminating RM closure effects (CM-23-002/003) and
            the CM-23-011 embargo refusal. When ``None``, only intake and
            the guarded receipt commit run.
        post_close_reply: The CASE_MANAGER's reply policy for a Leave that
            arrives after the case is fully closed (``ActorConfig.post_close_reply``,
            CM-23-017).  ``REJECT`` answers it with the refusal notice, a
            ``Refuse`` of the Leave (CM-23-057, ADR-0196); ``DROP`` sends
            nothing.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it, on the case, ahead of the
            close (HP-01-008).  A sender with no standing is refused before
            the CASE_MANAGER writes or replies to anything (HP-01-006).  Required with ``sender_actor_id``.
        receiving_actor_id: Actor URI of the receiving actor.  Used as the
            ``case_actor_id`` argument of
            :class:`~vultron.core.behaviors.case.nodes.leave.advance.AdvanceCaseActorToRMClosedNode`
            and the closing actor of its
            :class:`~vultron.core.behaviors.case.nodes.leave.record.CommitRMClosureEntriesNode`,
            so that on owner Leave the CaseActor's own RM state is advanced
            *and* that transition is recorded as a canonical ledger entry
            (CM-23-033).  When ``None``,
            both are omitted and the CaseActor's closure is neither applied nor
            recorded.

    Returns:
        Root ``CloseCaseBT`` Sequence node.
    """
    if sender_actor_id is None:
        return create_receive_activity_tree(
            name="CloseCaseBT",
            case_id=case_id,
            precondition_guards=[],
        )
    if sender_rule is None:
        raise VultronWiringError(
            "create_close_case_received_tree: a Leave with a sender needs the"
            " use case's sender_rule (HP-01-007, HP-01-008)"
        )

    owner_or_non_owner_effects = build_owner_or_non_owner_effects(
        case_id, sender_actor_id, receiving_actor_id
    )

    # The close: run the normal receive-and-close unless a guard refuses it.
    # Both guards are read-only preconditions, so they run before the
    # receipt commit (CLP-10-006).  A refusal commits nothing: committing and
    # fanning out the close_case ledger entry is exactly what advances the
    # participants to RM.CLOSED on the replicas (CLP-10-001), so a refused
    # close leaves the case untouched.  The factory answers either refusal
    # with the standard refusal notice to the Leave's sender, a Refuse of the
    # Leave carrying the guard's reason (CLP-02-005, CLP-05-001, ADR-0196);
    # the notice's own failure (no trigger port) never lets the close run.
    # The commit records receipt (CLP-10-001/006), and then the
    # role-discriminating RM closure effects run (CM-23-002/003).
    close = create_receive_activity_tree(
        name="CloseCaseReceive",
        case_id=case_id,
        # CloseCaseBT's doors and intake ran for this delivery (ADR-0154).
        nested=True,
        precondition_guards=[
            # CM-23-010: the CASE_MANAGER's RM.CLOSED is the write boundary,
            # so a CASE_MANAGER that is not the Case Owner cannot leave as an
            # ordinary leaver; refused before the receipt commit.
            CaseManagerLeavesOnlyAsCaseOwnerNode(
                case_id=case_id,
                sender_actor_id=sender_actor_id,
                name="CaseManagerLeavesOnlyAsCaseOwner",
            ),
            # CM-23-011: the Case Owner's Leave while an embargo is in force
            # (active_embargo set, EM ACTIVE or REVISE) is refused.  The
            # check is shared with the leave-case trigger, which makes it
            # before it sends (TRIG-13-003).
            owner_close_not_blocked_by_embargo(
                "OwnerClose",
                closing_actor_id=sender_actor_id,
                case_id=case_id,
                refusal=RefuseOwnerCloseWhileEmbargoedNode(
                    case_id=case_id,
                    sender_actor_id=sender_actor_id,
                    name="RefuseOwnerCloseWhileEmbargoed",
                ),
            ),
        ],
        # RSH-08-003: the RM-closure effects advance the leaving participant
        # (and, on an owner Leave, the CaseActor) to ``RM.CLOSED`` and commit
        # the ``close_case`` entry and the status entries that drive replica
        # closure.  Those are canonical case state only the CASE_MANAGER
        # writes; the status entries are committed and replayed
        # (ParticipantStatus slot), so a replica holding
        # a copy of the Leave writes nothing and takes the closure from the ledger
        # fan-out (#3814, CLP-10-001).
        manager_effects=[owner_or_non_owner_effects],
        manager_case_id=case_id,
        manager_gate_name="CloseCaseEffectsIfCaseManager",
        post_close_exemption=PostCloseExemption.ENCLOSING_TREE_GUARDS,
        addressee_exemption=ENCLOSING_TREE_ADDRESSEE_CHECK,
    )

    # The close is passed as ``manager_effects`` so the factory wraps it in
    # a CASE_MANAGER gate (BT-17-008): only the case's CASE_MANAGER refuses
    # an owner close (CM-23-011) or runs its closure effects (CM-23-002/003).
    # A replica holding a copy of the Leave never gets here, because the
    # path stage refuses it, and it takes any resulting closure from the
    # ledger fan-out (CLP-10-001, RSH-08-003).  ``case_id`` is ``None`` (no
    # commit at this level); ``manager_case_id`` names the case whose
    # CASE_MANAGER gates the close.
    # CM-23-013: a Leave after the case is fully closed is refused by the
    # factory's post-close guard ahead of the close, so it never runs and the
    # receipt commit is gated by the boundary itself.  The reply is the one
    # policy point's choice (ADR-0131): under REJECT it is the refusal
    # notice, a Refuse of the late Leave (CM-23-057, ADR-0196).
    late_leave_reply: list[py_trees.behaviour.Behaviour] = (
        [refusal_notice(case_id)]
        if post_close_reply is PostCloseReply.REJECT
        else []
    )
    return create_receive_activity_tree(
        name="CloseCaseBT",
        case_id=None,
        # The Leave names the case (ADR-0165): the path stage refuses one
        # this store does not hold, naming the activity and the case
        # (AKM-03-006).
        held_case=CaseNamedByReference.LEAVE,
        precondition_guards=[],
        # The leaver asks the CASE_MANAGER alone, which closes the case or
        # refuses the close (CM-23-002, PCR-08-001); a participant replica takes
        # the closure from the ledger fan-out (CLP-10-001, RSH-08-003), so
        # the path stage refuses a copy there (HP-01-005, HP-01-038).  The
        # close arm inside the manager gate declares no paths of its own:
        # this tree's stage already answered the question for the delivery
        # (HP-01-037).
        paths={ReceivedPath.CASE_MANAGER},
        # A sender whose closure the case records repeats a closing act; the
        # Case Owner's Leave also closes the case, so while the case is not
        # fully closed its Leave runs to close it (CM-23-018, CM-23-002).
        closed_sender=ClosedSenderCheck(
            sender_id=sender_actor_id, case_owner_completes=True
        ),
        sender_rule=sender_rule,
        # The owner's Leave closes the case, so its CASE_OWNER standing is
        # the role alone; the closed-sender door decides a repeat.
        sender_context=SenderCheckContext(
            sender_id=sender_actor_id,
            case_id=case_id,
            closing_case_owner=True,
        ),
        post_close_reply=late_leave_reply,
        manager_effects=[close],
        manager_case_id=case_id,
        manager_gate_name="CloseIfCaseManager",
    )
