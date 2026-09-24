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

- **Owner Leave** (sender holds ``CVDRole.CASE_OWNER``): advances the leaving
  participant to ``RM.CLOSED``, advances the CaseActor to ``RM.CLOSED``,
  commits a ``case_fully_closed`` CaseLedgerEntry, and fans out to
  non-RM.CLOSED participants (CM-23-002, CM-23-004) — **unless** an embargo is
  still live, in which case the close is declined with an ``as:Reject`` and
  none of the closure effects run (CM-23-011).
- **Non-owner Leave**: advances only the leaving participant to ``RM.CLOSED``;
  the case remains open for remaining participants (CM-23-003).

The role check is performed by :class:`~vultron.core.behaviors.case.nodes
.vfd_role_guards.CheckIsCaseOwnerNode` as a tree-level condition node, per
BTND-08-001/BTND-08-002 (role checks MUST be in the tree, not in action node
``update()`` logic).

Per ADR-0050: ``Leave(VulnerabilityCase)`` is the only canonical RM closure
path.  The ``case_fully_closed`` ledger entry is written here on the Case Actor
receive path; all other replicas learn via Announce(CaseLedgerEntry) fan-out.
"""

import logging
from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.leave import (
    AdvanceCaseActorToRMClosedNode,
    AdvanceParticipantToRMClosedNode,
    CommitCaseActorRMClosedEntryNode,
    EmitRejectCloseCaseNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckIsCaseOwnerNode,
)
from vultron.core.behaviors.embargo.nodes import (
    HasCaseStatusesNode,
    IsCloseBlockedByActiveEmbargoNode,
    ReadEmStateNode,
)
from vultron.core.behaviors.report.nodes.storage import StoreActivityNode
from vultron.core.behaviors.sync.nodes import (
    CreateLogEntryNode,
    FanOutLogEntryNode,
    PersistLogEntryNode,
    ReconstructChainTailNode,
)
from vultron.core.models._helpers import claimed_published_iso

logger = logging.getLogger(__name__)


def create_close_case_received_tree(
    case_id: str,
    activity_id: str,
    activity_obj: Any,
    sender_actor_id: str | None = None,
    receiving_actor_id: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Single-BT received-side tree for CloseCaseReceived (ADR-0022).

    When ``sender_actor_id`` is provided, the tree branches on the sender's
    ``CVDRole.CASE_OWNER`` role (CM-23-002/CM-23-003):

    - Owner Leave, no active embargo → advance leaving participant to
      ``RM.CLOSED``, then advance the CaseActor to ``RM.CLOSED`` (owner path,
      CM-23-002).
    - Owner Leave while an embargo is live (``active_embargo`` non-None and EM
      state ``ACTIVE`` or ``REVISE``) → decline the close with an ``as:Reject``
      and run **none** of the CM-23-002 closure effects (CM-23-011). The owner
      must terminate the embargo first, then re-issue the close.
    - Non-owner Leave → advance only the leaving participant to ``RM.CLOSED``;
      case remains open (non-owner path, CM-23-003).

    When ``sender_actor_id`` is ``None`` (e.g., in legacy paths or tests that
    do not supply it), the tree falls back to the pre-#1901 behaviour:
    ``StoreActivityNode`` only, no participant state mutation.

    Structure (with role semantics)::

        CloseCaseBT (Selector)                          # close unless declined
        ├── ReceiveAndCloseUnlessDeclined (Sequence)
        │   ├── Inverter(OwnerCloseBlockedByEmbargoCheck)  # SUCCESS iff NOT declining
        │   │   └── Sequence: CheckIsCaseOwner → HasCaseStatuses
        │   │              → ReadEmState → IsCloseBlockedByActiveEmbargo
        │   └── CloseCaseReceive (Sequence)             # normal receive-and-close
        │       ├── GuardedCommitOrSkip (Selector)      # Record receipt (CLP-10-006)
        │       │   ├── Sequence(SkipIfNotCaseManager)
        │       │   │   └── Inverter(CheckIsCaseManagerNode)
        │       │   └── CommitCaseLedgerEntryNode       # commits the close_case entry
        │       ├── OwnerOrNonOwnerEffects (Selector)    # Role discriminator
        │       │   ├── OwnerLeaveSeq (Sequence)        # Owner path (CM-23-002)
        │       │   │   ├── CheckIsCaseOwnerNode        # guard: sender IS CASE_OWNER
        │       │   │   ├── AdvanceParticipantToRMClosedNode  # step 1: owner → RM.CLOSED
        │       │   │   ├── AdvanceCaseActorToRMClosedNode    # step 2: CaseActor → RM.CLOSED
        │       │   │   ├── CommitCaseActorRMClosedEntryNode  # step 2 on the ledger (CM-23-005)
        │       │   │   └── CommitCaseFullyClosedBT (Sequence)  # steps 3-4: commit + fan-out
        │       │   │       ├── ReconstructChainTailNode        # step 3a: tail hash
        │       │   │       ├── CreateCaseFullyClosedEntry      # step 3b: build entry
        │       │   │       ├── PersistCaseFullyClosedEntry     # step 3c: write to DataLayer
        │       │   │       └── FanOutLogEntryNode              # step 4: fan-out
        │       │   └── NonOwnerLeaveFallbackSeq (Sequence)  # Non-owner (CM-23-003)
        │       │       └── AdvanceParticipantToRMClosedNode  # departing → RM.CLOSED
        │       └── StoreActivityNode("Leave")          # Persist inbound Leave
        └── DeclineOwnerCloseIfEmbargoed (Sequence)     # CM-23-011 decline arm
            ├── CheckIsCaseOwner → HasCaseStatuses
            │        → ReadEmState → IsCloseBlockedByActiveEmbargo  # decline decision
            ├── EmitRejectCloseCase                     # decline via as:Reject
            └── StoreActivityNode("Leave")              # persist inbound Leave

    The same decline decision (owner + live embargo) gates both arms: the close
    arm runs only when the decision is inverted-false, and the decline arm runs
    only when it is true. So even if the ``as:Reject`` emit fails, the close arm
    has already been skipped and the case cannot be closed. Suppressing the
    ``GuardedCommitOrSkip`` receipt commit is essential, because committing and
    fanning out the ``close_case`` ledger entry is exactly what advances
    participants to ``RM.CLOSED`` on the replicas (CLP-10-001); declining
    therefore leaves the case untouched and only emits the ``as:Reject``
    (CM-23-011).

    Running under ``actor_id=receiving_actor_id`` means
    ``CheckIsCaseManagerNode`` naturally gates the commit to the actor that
    holds ``CVDRole.CASE_MANAGER`` — no identity comparison needed in Python.

    Args:
        case_id: ID of the VulnerabilityCase being closed.
        activity_id: ID of the inbound Leave activity to store idempotently.
        activity_obj: The wire activity object to persist.
        sender_actor_id: Actor URI of the Leave sender (resolved from the
            inbound Leave activity's ``actor`` field).  When provided, the tree
            applies role-discriminating RM closure effects (CM-23-002/003) and
            the CM-23-011 embargo decline. When ``None``, only
            ``StoreActivityNode`` runs as a fallback.
        receiving_actor_id: Actor URI of the receiving actor.  Used as the
            ``case_actor_id`` argument of :class:`AdvanceCaseActorToRMClosedNode`
            and :class:`CommitCaseActorRMClosedEntryNode`, so that on owner Leave
            the CaseActor's own RM state is advanced *and* that transition is
            recorded as a canonical ledger entry (CM-23-005).  When ``None``,
            both are omitted and the CaseActor's closure is neither applied nor
            recorded.

    Returns:
        Root ``CloseCaseBT`` node (a Selector, or the fallback Sequence when
        ``sender_actor_id`` is ``None``).
    """
    store_node = StoreActivityNode(
        activity_id=activity_id,
        activity_obj=activity_obj,
        label="Leave",
    )

    if sender_actor_id is None:
        return create_receive_activity_tree(
            name="CloseCaseBT",
            case_id=case_id,
            precondition_guards=[],
            effect_nodes=[store_node],
        )

    advance_leaving_participant = AdvanceParticipantToRMClosedNode(
        leaving_actor_id=sender_actor_id,
        case_id=case_id,
        name="AdvanceLeavingParticipantToRMClosed",
    )

    case_fully_closed_commit = py_trees.composites.Sequence(
        name="CommitCaseFullyClosedBT",
        memory=False,
        children=[
            ReconstructChainTailNode(
                case_id=case_id, name="ReconstructChainTail"
            ),
            CreateLogEntryNode(
                # CLP-07-003: actor is sourced from sender_actor_id, which is
                # extracted from the trusted inbound Leave by the framework —
                # not from the unverified payload — so the identity invariant
                # holds without going through CommitCaseLedgerEntryNode.
                case_id=case_id,
                object_id=activity_id,
                event_type="case_fully_closed",
                payload_snapshot={
                    "type": "Leave",
                    "actor": sender_actor_id,
                    # The snapshot is attributed to the *sender*, so its
                    # ``published`` must be the sender's claimed time, taken
                    # from the inbound Leave. Stamping the CaseActor's own clock
                    # here would put a foreign clock into the sender's claimed
                    # stream, which CLP-15-003 then reads as a regression, and
                    # would leave CLP-14-007/008 comparing the receiver's clock
                    # against itself on this path (ISSUE-3149). The inbound
                    # activity always carries one — the parser refuses it
                    # otherwise — so the fallback is defence in depth only.
                    "published": claimed_published_iso(activity_obj),
                    "object_": {"type": "VulnerabilityCase", "id_": case_id},
                    "context": case_id,
                },
                name="CreateCaseFullyClosedEntry",
            ),
            PersistLogEntryNode(name="PersistCaseFullyClosedEntry"),
            FanOutLogEntryNode(
                case_id=case_id,
                name="FanOutCaseFullyClosed",
            ),
        ],
    )

    owner_leave_children: list[py_trees.behaviour.Behaviour] = [
        CheckIsCaseOwnerNode(
            sender_actor_id=sender_actor_id,
            case_id=case_id,
            name="CheckIsCaseOwnerForLeave",
        ),
        AdvanceParticipantToRMClosedNode(
            leaving_actor_id=sender_actor_id,
            case_id=case_id,
            name="AdvanceOwnerToRMClosed",
        ),
    ]
    if receiving_actor_id is not None:
        owner_leave_children.append(
            AdvanceCaseActorToRMClosedNode(
                case_actor_id=receiving_actor_id,
                case_id=case_id,
                name="AdvanceCaseActorToRMClosed",
            )
        )
        # The advance above is store-local. Without this entry the CASE_MANAGER
        # stays RM.ACCEPTED on every replica forever (ISSUE-2505): no effect
        # node derives its closure, because ``close_case`` names the departing
        # actor and ``case_fully_closed`` is attributed to the owner.
        #
        # The node records best-effort — it warns and returns SUCCESS rather
        # than failing. That is load-bearing *here*, not merely defensive: this
        # Sequence runs the entry before ``case_fully_closed``, so a FAILURE
        # would skip steps 3 and 4, and the Selector below would then read the
        # failed owner arm as "the sender is not the Case Owner" and report
        # SUCCESS down the non-owner path — a half-closed case with no
        # diagnostic. Do not "harden" the node into failing without first
        # making this arm's failure propagate past that Selector.
        owner_leave_children.append(
            CommitCaseActorRMClosedEntryNode(
                case_actor_id=receiving_actor_id,
                case_id=case_id,
                name="CommitCaseActorRMClosedEntry",
            )
        )
    owner_leave_children.append(case_fully_closed_commit)

    owner_or_non_owner_effects = py_trees.composites.Selector(
        name="OwnerOrNonOwnerEffects",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="OwnerLeaveSeq",
                memory=False,
                children=owner_leave_children,
            ),
            py_trees.composites.Sequence(
                name="NonOwnerLeaveFallbackSeq",
                memory=False,
                children=[advance_leaving_participant],
            ),
        ],
    )

    # Normal receive: record receipt (commits the close_case ledger entry that
    # drives replica closure, CLP-10-001/006) then run the role-discriminating
    # RM closure effects (CM-23-002/003).
    normal_receive = create_receive_activity_tree(
        name="CloseCaseReceive",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            owner_or_non_owner_effects,
            store_node,
        ],
    )

    # CM-23-011 decline decision (read-only): SUCCESS iff the sender is the Case
    # Owner AND an embargo is live (active_embargo non-None, EM state
    # ACTIVE/REVISE). This same decision gates BOTH arms below, so once a decline
    # is warranted the close can NEVER run — not even if the as:Reject emit
    # fails. That matters because committing and fanning out the close_case
    # ledger entry is precisely what advances participants to RM.CLOSED on the
    # replicas (CLP-10-001); a decline must therefore suppress the receipt commit
    # itself, not merely the local RM effects. ReadEmStateNode publishes
    # ``em_before`` for IsCloseBlockedByActiveEmbargoNode (AC-1: EM-state reads go
    # through Read*StateNode, never inline). Each arm gets its own result_out
    # dict since the two guard chains are distinct node instances.
    def _decline_decision_guards(
        result_out: dict[str, object],
    ) -> list[py_trees.behaviour.Behaviour]:
        return [
            CheckIsCaseOwnerNode(
                sender_actor_id=sender_actor_id,
                case_id=case_id,
                name="CheckIsCaseOwnerForClose",
            ),
            # Precondition for the EM read: fail quietly (no misleading WARNING)
            # when the case carries no CaseStatus, rather than letting
            # ReadEmStateNode log a no-status warning on every routine close.
            HasCaseStatusesNode(
                case_id=case_id,
                name="HasCaseStatusesForCloseGuard",
            ),
            ReadEmStateNode(
                case_id=case_id,
                result_out=result_out,
                name="ReadEmStateForCloseGuard",
            ),
            IsCloseBlockedByActiveEmbargoNode(
                case_id=case_id,
                result_out=result_out,
                name="IsCloseBlockedByActiveEmbargo",
            ),
        ]

    # Close arm: run the normal receive-and-close ONLY when the decline decision
    # does NOT fire. The inverted guard makes an emit failure in the decline arm
    # structurally unable to leak through into closing an embargoed case.
    close_arm = py_trees.composites.Sequence(
        name="ReceiveAndCloseUnlessDeclined",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="NotOwnerCloseBlockedByEmbargo",
                child=py_trees.composites.Sequence(
                    name="OwnerCloseBlockedByEmbargoCheck",
                    memory=False,
                    children=_decline_decision_guards({}),
                ),
            ),
            normal_receive,
        ],
    )

    # Decline arm: emit an as:Reject and persist the inbound Leave; commit
    # nothing (CM-23-011).
    decline_arm = py_trees.composites.Sequence(
        name="DeclineOwnerCloseIfEmbargoed",
        memory=False,
        children=[
            *_decline_decision_guards({}),
            EmitRejectCloseCaseNode(
                case_id=case_id,
                close_sender_id=sender_actor_id,
                close_activity_id=activity_id,
                name="EmitRejectCloseCase",
            ),
            StoreActivityNode(
                activity_id=activity_id,
                activity_obj=activity_obj,
                label="Leave",
            ),
        ],
    )

    # Close first (the common path); fall through to the decline arm only when
    # the close arm's inverted embargo guard blocks it.
    return py_trees.composites.Selector(
        name="CloseCaseBT",
        memory=False,
        children=[close_arm, decline_arm],
    )
