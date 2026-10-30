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

"""Received-side BT factory for the close-case workflow (ADR-0022).

Implements receiver-side role semantics for Leave(VulnerabilityCase):

- **Owner Leave** (sender holds ``CVDRole.CASE_OWNER``): expires every
  embargo Invite still awaiting a reply (CM-23-014), advances the leaving
  participant to ``RM.CLOSED``, then advances the CaseActor to ``RM.CLOSED``, committing
  one status entry per RM transition for each and fanning each out to the
  participants not at ``RM.CLOSED`` (CM-23-001, CM-23-002, CM-23-004,
  CM-23-005).  The CaseActor's own ``RM.CLOSED`` status entry is the last
  entry of the closure and the owner-close write boundary (ADR-0085); no
  entry marks the closure itself (ADR-0152) — **unless** an embargo is still
  live, in which case the close is declined with an ``as:Reject`` and none of
  the closure effects run (CM-23-011).
- **Non-owner Leave**: advances only the leaving participant to ``RM.CLOSED``,
  committing one status entry per RM transition; the case remains open for
  remaining participants (CM-23-003).

Every RM closure step the CASE_MANAGER writes is its own ledger entry, after
the ``close_case`` entry that records the Leave.  A replica applies those
status entries and never works out a closure path itself; applying
``close_case`` changes no RM state (CM-23-001, CM-23-016).
- **Any Leave after the case is fully closed**: the factory's post-close guard
  refuses it ahead of both arms, so no ``close_case`` entry is committed or
  fanned out and no one advances (CM-23-013).  Under
  ``PostCloseReply.REJECT`` the sender gets ``Reject(Leave(VulnerabilityCase))``;
  under the default ``DROP`` it gets nothing (ADR-0131).
- **A Leave from a sender with no standing**: the sender guard the factory
  composes from the use case's declared rule refuses it before the
  close/decline decision, so nothing is committed, declined or sent
  (HP-01-006, HP-01-008).  A Leave from a sender whose closure the case
  already records never reaches this tree: the use case reports it
  ``SKIPPED`` first (CM-23-018, ID-05-003).

The role check is performed by :class:`~vultron.core.behaviors.case.nodes
.vfd_role_guards.SenderIsCaseOwnerNode` as a tree-level condition node, per
BTND-08-001/BTND-08-002 (role checks MUST be in the tree, not in action node
``update()`` logic).

Per ADR-0050: ``Leave(VulnerabilityCase)`` is the only canonical RM closure
path.  The CaseActor's closure entries are written here on the Case Actor
receive path; every replica whose closure the ledger does not already record
learns of them via Announce(CaseLedgerEntry) fan-out.  A participant at RM
``CLOSED`` — every earlier leaver, and the Case Owner once its own status
entries are committed — is not sent them (CM-23-004): it receives the entries
that record its own closure and nothing after them.
"""

import logging

import py_trees

from vultron.config.actor import DEFAULT_POST_CLOSE_REPLY, PostCloseReply
from vultron.core.behaviors.case.nodes.addressee import (
    ENCLOSING_TREE_ADDRESSEE_CHECK,
)
from vultron.core.behaviors.case.nodes.leave import (
    LATE_LEAVE_DECLINE,
    AdvanceCaseActorToRMClosedNode,
    AdvanceParticipantToRMClosedNode,
    CaseManagerLeavesOnlyAsCaseOwnerNode,
    CommitRMClosureEntriesNode,
    EmitRejectCloseCaseNode,
    ExpirePendingInvitesOnCloseNode,
)
from vultron.core.behaviors.case.nodes.post_close import PostCloseExemption
from vultron.core.behaviors.case.nodes.refusal_notice import (
    OWNER_CLOSE_DECLINE,
)
from vultron.core.behaviors.case.owner_close_embargo_guards import (
    owner_close_blocked_by_embargo_guards,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsCaseOwnerNode,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    SenderCheckContext,
)
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


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
    (CM-23-001, CM-23-005).
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


def create_close_case_received_tree(
    case_id: str,
    activity_id: str,
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
      state ``ACTIVE`` or ``REVISE``) → decline the close with an ``as:Reject``
      and run **none** of the CM-23-002 closure effects (CM-23-011). The owner
      must terminate the embargo first, then re-issue the close.
    - Non-owner Leave → advance only the leaving participant to ``RM.CLOSED``;
      case remains open (non-owner path, CM-23-003).
    - Any Leave after the case is fully closed → refused by the post-close guard
      before the ``CloseOrDecline`` decision, so the receipt
      ``GuardedCommitOrSkip`` never runs: nothing is committed or fanned out
      (CM-23-013).  The same shape as the CM-23-011 decline: the decision
      gates the receipt commit itself.

    When ``sender_actor_id`` is ``None`` (e.g., in legacy paths or tests that
    do not supply it), the tree falls back to the pre-#1901 behaviour: intake
    and the guarded receipt commit only, no participant state mutation.

    Structure (with role semantics)::

        CloseCaseBT (Sequence, via create_receive_activity_tree)
        ├── IntakeReceivedActivityNode                  # archive the Leave (CLP-10-017)
        ├── CaseOpenToExternalWrites                    # post-close boundary (CM-23-013)
        │       (under PostCloseReply.REJECT: a PostCloseStage whose refusal
        │        arm emits EmitRejectLateLeave at the CASE_MANAGER)
        ├── SenderRuleGuard                             # composed from sender_rule (HP-01-025)
        ├── ClockDecisions (CaseManagerGate)            # embargo end-time check (CLP-10-025)
        └── CloseOrDeclineIfCaseManager (CaseManagerGate)  # BT-17-008, #3825
            └── CloseOrDecline (Selector)               # close unless declined
                ├── CloseCaseReceive (Sequence, via create_receive_activity_tree)
                │   ├── IntakeReceivedActivityNode          # finds the archive; no-op
                │   │   (no post-close guard: CloseCaseBT's guard runs first)
                │   ├── CaseManagerLeavesOnlyAsCaseOwner    # guard: CM-23-010
                │   ├── Inverter(OwnerCloseBlockedByEmbargoCheck)  # guard: SUCCESS iff NOT declining
                │   │   └── Sequence: CheckIsCaseOwner → ReadEmState
                │   │              → IsCloseBlockedByActiveEmbargo
                │   ├── GuardedCommitOrSkip (Selector)      # Record receipt (CLP-10-006)
                │   │   ├── Sequence(SkipIfNotCaseManager)
                │   │   │   └── Inverter(CheckIsCaseManagerNode)
                │   │   └── CommitCaseLedgerEntryNode       # commits the close_case entry
                │   └── CloseCaseEffectsIfCaseManager (CaseManagerGate)  # RSH-08-003, #3814
                │       └── OwnerOrNonOwnerEffects (Sequence)   # one arm per role
                │           ├── OwnerLeaveArm (Selector)        # Owner path (CM-23-002)
                │           │   ├── Inverter(SenderIsCaseOwnerNode)  # skip: not CASE_OWNER
                │           │   └── OwnerLeaveSeq (Sequence)
                │           │       ├── ExpirePendingInvitesOnCloseNode   # settle pending Invites (CM-23-014)
                │           │       ├── AdvanceParticipantToRMClosedNode  # step 1: owner → RM.CLOSED
                │           │       ├── CommitRMClosureEntriesNode   # step 1 on the ledger (CM-23-001)
                │           │       ├── AdvanceCaseActorToRMClosedNode    # step 2: CaseActor → RM.CLOSED
                │           │       └── CommitRMClosureEntriesNode   # step 2: the boundary
                │           └── NonOwnerLeaveArm (Selector)     # Non-owner (CM-23-003)
                │               ├── SenderIsCaseOwnerNode            # skip: sender is CASE_OWNER
                │               └── NonOwnerLeaveSeq (Sequence)
                │                   ├── AdvanceParticipantToRMClosedNode  # departing → RM.CLOSED
                │                   └── CommitRMClosureEntriesNode   # each step on the ledger (CM-23-001)
                └── DeclineOwnerCloseIfEmbargoed (Sequence)  # CM-23-011 decline arm
                    ├── CheckIsCaseOwner → ReadEmState
                    │        → IsCloseBlockedByActiveEmbargo  # decline decision
                    └── EmitRejectCloseCase                 # decline via as:Reject

    Intake runs first, ahead of the gate, so the inbound Leave is archived on
    every replica whether or not the receiver is the CASE_MANAGER (CLP-10-017,
    CLP-10-018); the per-arm ``StoreActivityNode`` this tree once carried
    duplicated it and was removed (CLP-10-019).  The inner ``CloseCaseReceive``
    is built by the same factory because only the factory supplies the guarded
    receipt commit; its intake node finds the archive already present and
    writes nothing.

    The ``CloseOrDecline`` Selector is passed as the factory's
    ``manager_effects``, so the factory wraps the whole close/decline decision
    in a CASE_MANAGER gate (BT-17-008).  Only the case's CASE_MANAGER declines
    an owner close (CM-23-011) or runs its closure effects (CM-23-002/003); a
    replica holding a copy of the Leave skips the gate, emits no ``as:Reject`` (the
    #3825 defect), writes nothing, and takes any resulting closure from the
    ledger fan-out (CLP-10-001, RSH-08-003, HP-01-005).  The two arms stay in
    one Selector because the close arm FAILS when a decline is warranted and
    only a Selector lets the decline arm run next.

    The same decline decision (owner + live embargo) gates both arms: the close
    arm runs only when the decision is inverted-false, and the decline arm runs
    only when it is true. So even if the ``as:Reject`` emit fails, the close arm
    has already been skipped and the case cannot be closed. Suppressing the
    ``GuardedCommitOrSkip`` receipt commit is essential, because committing and
    fanning out the ``close_case`` ledger entry is exactly what advances
    participants to ``RM.CLOSED`` on the replicas (CLP-10-001); declining
    therefore leaves the case untouched and only emits the ``as:Reject``
    (CM-23-011).

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
        activity_id: ID of the inbound Leave activity; the CM-23-011 and
            CM-23-013 replies thread to it.
        sender_actor_id: Actor URI of the Leave sender (resolved from the
            inbound Leave activity's ``actor`` field).  When provided, the tree
            applies role-discriminating RM closure effects (CM-23-002/003) and
            the CM-23-011 embargo decline. When ``None``, only intake and
            the guarded receipt commit run.
        post_close_reply: The CASE_MANAGER's reply policy for a Leave that
            arrives after the case is fully closed (``ActorConfig.post_close_reply``,
            CM-23-013).  ``REJECT`` answers it with
            ``Reject(Leave(VulnerabilityCase))``; ``DROP`` sends nothing.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it, on the case, ahead of the
            close/decline decision (HP-01-008).  A sender with no standing
            is refused before the CASE_MANAGER writes, declines or replies
            to anything (HP-01-006).  Required with ``sender_actor_id``.
        receiving_actor_id: Actor URI of the receiving actor.  Used as the
            ``case_actor_id`` argument of :class:`AdvanceCaseActorToRMClosedNode`
            and the closing actor of its :class:`CommitRMClosureEntriesNode`, so that on owner Leave
            the CaseActor's own RM state is advanced *and* that transition is
            recorded as a canonical ledger entry (CM-23-005).  When ``None``,
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
    owner_or_non_owner_effects = py_trees.composites.Sequence(
        name="OwnerOrNonOwnerEffects",
        memory=False,
        children=[
            py_trees.composites.Selector(
                name="OwnerLeaveArm",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="SenderIsNotCaseOwner",
                        child=SenderIsCaseOwnerNode(
                            sender_actor_id=sender_actor_id,
                            case_id=case_id,
                            name="CheckIsCaseOwnerForLeave",
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
                    SenderIsCaseOwnerNode(
                        sender_actor_id=sender_actor_id,
                        case_id=case_id,
                        name="CheckIsCaseOwnerForNonOwnerLeave",
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

    # CM-23-011 decline decision (read-only): SUCCESS iff the sender is the Case
    # Owner AND an embargo is live (active_embargo non-None, EM state
    # ACTIVE/REVISE). This same decision gates BOTH arms below, so once a decline
    # is warranted the close can NEVER run — not even if the as:Reject emit
    # fails. That matters because committing and fanning out the close_case
    # ledger entry is precisely what advances participants to RM.CLOSED on the
    # replicas (CLP-10-001); a decline must therefore suppress the receipt commit
    # itself, not merely the local RM effects. The guards are shared with the
    # leave-case trigger, which makes the same check before it sends
    # (TRIG-13-003). Each arm gets its own result_out dict since the two guard
    # chains are distinct node instances.

    # Close arm: run the normal receive-and-close ONLY when the decline decision
    # does NOT fire. The inverted guard is a read-only precondition of the
    # receive tree, so it runs before the receipt commit (CLP-10-006) and makes
    # an emit failure in the decline arm structurally unable to leak through
    # into closing an embargoed case. The commit records receipt (the
    # close_case ledger entry that drives replica closure, CLP-10-001/006) and
    # then the role-discriminating RM closure effects run (CM-23-002/003).
    close_arm = create_receive_activity_tree(
        name="CloseCaseReceive",
        case_id=case_id,
        # The decline arm answers the one refusal the close arm makes, with
        # the CM-23-011 Reject(Leave), so the factory adds no refusal notice.
        refusal_notice_exemption=OWNER_CLOSE_DECLINE,
        precondition_guards=[
            # CM-23-010: the CASE_MANAGER's RM.CLOSED is the write boundary,
            # so a CASE_MANAGER that is not the Case Owner cannot leave as an
            # ordinary leaver; refused before the receipt commit.
            CaseManagerLeavesOnlyAsCaseOwnerNode(
                case_id=case_id,
                sender_actor_id=sender_actor_id,
                name="CaseManagerLeavesOnlyAsCaseOwner",
            ),
            py_trees.decorators.Inverter(
                name="NotOwnerCloseBlockedByEmbargo",
                child=py_trees.composites.Sequence(
                    name="OwnerCloseBlockedByEmbargoCheck",
                    memory=False,
                    children=owner_close_blocked_by_embargo_guards(
                        closing_actor_id=sender_actor_id,
                        case_id=case_id,
                        result_out={},
                    ),
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

    # Decline arm: emit an as:Reject; commit nothing (CM-23-011). The Leave is
    # already archived by the root intake node.
    decline_arm = py_trees.composites.Sequence(
        name="DeclineOwnerCloseIfEmbargoed",
        memory=False,
        children=[
            *owner_close_blocked_by_embargo_guards(
                closing_actor_id=sender_actor_id,
                case_id=case_id,
                result_out={},
            ),
            EmitRejectCloseCaseNode(
                case_id=case_id,
                close_sender_id=sender_actor_id,
                close_activity_id=activity_id,
                name="EmitRejectCloseCase",
            ),
        ],
    )

    # Close first (the common path); fall through to the decline arm only when
    # the close arm's inverted embargo guard blocks it. Intake sits ahead of
    # the Selector so both arms leave the archive in place (CLP-10-018); no
    # commit at this level — the receipt commit belongs to the close arm.
    #
    # The whole Selector is passed as ``manager_effects`` so the factory wraps
    # it in a CASE_MANAGER gate (BT-17-008): the decline arm's
    # ``EmitRejectCloseCaseNode`` is emit-capable, and only the case's
    # CASE_MANAGER declines an owner close (CM-23-011, BT-17-001). The close
    # arm's own effects are already CASE_MANAGER-gated internally and its
    # commit is role-gated, so on a replica holding a copy of the Leave the gate skips
    # the whole decision: nothing is written, nothing is emitted, and the
    # replica takes any resulting closure from the ledger fan-out
    # (CLP-10-001, RSH-08-003). The close/decline arms stay in one Selector —
    # the close arm FAILS when a decline is warranted, and only a Selector lets
    # the decline arm run next, which a side-by-side Sequence placement in
    # ``replica_effects``/``manager_effects`` could not express. ``case_id`` is
    # ``None`` (no commit at this level); ``manager_case_id`` names the case
    # whose CASE_MANAGER gates the Selector.
    # CM-23-013: a Leave after the case is fully closed is refused by the factory's
    # post-close guard ahead of the CloseOrDecline decision, so neither arm
    # runs and the receipt commit is gated by the boundary itself.  The reply
    # is the one policy point's choice (ADR-0131).
    late_leave_reply: list[py_trees.behaviour.Behaviour] = (
        [
            EmitRejectCloseCaseNode(
                case_id=case_id,
                close_sender_id=sender_actor_id,
                close_activity_id=activity_id,
                name="EmitRejectLateLeave",
                decline_reason=LATE_LEAVE_DECLINE,
            )
        ]
        if post_close_reply is PostCloseReply.REJECT
        else []
    )
    return create_receive_activity_tree(
        name="CloseCaseBT",
        case_id=None,
        precondition_guards=[],
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
        manager_effects=[
            py_trees.composites.Selector(
                name="CloseOrDecline",
                memory=False,
                children=[close_arm, decline_arm],
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="CloseOrDeclineIfCaseManager",
    )
