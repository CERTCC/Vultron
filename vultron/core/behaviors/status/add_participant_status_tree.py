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

"""
AddParticipantStatus behavior tree composition.

Composes the DEMOMA-07-003 workflow as a Sequence BT
(step 3 raw peer re-broadcast removed per DEMOMA-07-005).

StatusAdoptionGate of the two-seam authorization model (ADR-0046, RSH-01-001 to RSH-01-004):
after ``AppendParticipantStatusNode`` records the raw peer update, a
``StatusAdoptionGate`` (Selector/Fallback) decides whether the CaseActor
should adopt the status, then ``EmitCaseStatusUpdateNode`` writes the
post-adoption CaseStatus directly to the case ledger without routing through
the inbox seam (RSH-04-004).  Side-effects (embargo teardown) belong in
``add_case_status_tree``; this tree does not execute them directly (RSH-01-004).

    AddParticipantStatusBT (Sequence)
    ├─ VerifySenderIsParticipantNode          # Step 1: sender must be known participant
    ├─ FilterParticipantStatusDimensionsNode  # Guard: adjudicate rm/vfd/pxa separately (RSH-05)
    ├─ GuardedCommitOrSkip (Selector, only if case_id)  # Record receipt first (CLP-10-006)
    │   ├─ Sequence("SkipIfNotCaseManager")
    │   │   └─ Inverter(CheckIsCaseManagerNode)
    │   └─ CommitCaseLedgerEntryNode
    ├─ AppendParticipantStatusNode            # Step 2: append status to participant record
    ├─ StatusAdoptionGate (Selector)           # StatusAdoptionGate authorization (RSH-01-002)
    │   ├─ CheckIsCaseOwnerNode               # Hard bypass: CASE_OWNER gospel (RSH-01-002)
    │   └─ CaseOwnerApprovesStatusUpdate      # Call-out: non-owners need approval
    ├─ EmitCaseStatusUpdateNode               # Direct ledger write (RSH-04-004, RSH-01-003)
    ├─ TeardownEffectsOrSkip (FailureIsSuccess)
    │   └─ TeardownEffects (Sequence)
    │       ├─ EmbargoTeardownAuthorizationGate  # Call-out gate (RSH-02-001)
    │       └─ ThreatTerminationBranchNode       # Embargo teardown on P/X/A (RSH-03-001)
    └─ EmitRMGapNoteNode                      # Emit Add(Note,Case) on RM anomaly (RSH-06-004)

``FilterParticipantStatusDimensionsNode`` adjudicates ``rm``, ``vfd`` and
``pxa`` independently before the commit, so an unacceptable value in one
dimension no longer discards the accepted dimensions or aborts the Sequence
before the StatusAdoptionGate emit (RSH-05, ISSUE-2235).  It replaced the
former ``CheckParticipantRMNotClosedNode`` guard (now removed), subsuming the
terminal-``RM.CLOSED`` check: a wholly refused assertion still returns FAILURE
here, before any canonical ledger entry is committed.

Per specs/multi-actor-demo.yaml DEMOMA-07-003, DEMOMA-07-005.
Per specs/received-status-handling.yaml RSH-01-001 to RSH-01-004, RSH-05.
Per ADR-0050: canonical RM closure is routed through Leave(VulnerabilityCase)
receive path in receive_close_case_tree, not here.
"""

import logging

import py_trees

from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    StatusAuthorizationCallOutBundle,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckIsCaseOwnerNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.status.append_participant_status_tree import (
    append_participant_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    EmitCaseStatusUpdateNode,
    EmitRMGapNoteNode,
    FilterParticipantStatusDimensionsNode,
    VerifySenderIsParticipantNode,
)
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)
from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)

logger = logging.getLogger(__name__)


def add_participant_status_tree(
    request: AddParticipantStatusToParticipantReceivedEvent,
    case_id: str | None = None,
    call_out: StatusAuthorizationCallOutBundle = STATUS_AUTHORIZATION_DETERMINISTIC,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddParticipantStatus workflow.

    Handles receipt of an ``Add(ParticipantStatus, CaseParticipant)``
    activity.  Implements the DEMOMA-07-003 workflow with StatusAdoptionGate
    authorization (ADR-0046, RSH-01-001 to RSH-01-004).

    When ``case_id`` is provided (or derived from the inline status object),
    a guarded-commit subtree is inserted after precondition guards so the
    canonical ledger records receipt of the triggering activity before any
    protocol effects run (CLP-10-006).  Running the tree with
    ``actor_id=receiving_actor_id`` (ADR-0022 single-BT shape) means
    ``CheckIsCaseManagerNode`` in that subtree correctly fires only when
    the receiving actor holds ``CVDRole.CASE_MANAGER``.

    The *case_id* for the commit and all children is derived from the inline
    ``request.status.context`` field when not supplied explicitly.  If it
    is not available in the inline object, the
    ``VerifySenderIsParticipantNode`` will perform a DataLayer lookup.

    After ``AppendParticipantStatusNode`` records the raw peer update, a
    ``StatusAdoptionGate`` (Selector/Fallback) decides whether the CaseActor
    should adopt the status:

    - ``CheckIsCaseOwnerNode`` — hard bypass for CASE_OWNER gospel (RSH-01-002)
    - ``CaseOwnerApprovesStatusUpdate`` — call-out backed by
      ``call_out.status_adoption_gate_factory``; default is ``AlwaysSucceed``

    When the gate passes, ``EmitCaseStatusUpdateNode`` writes the post-adoption
    CaseStatus directly to the case ledger and fans it out to participants
    (RSH-01-003, RSH-04-004).  A ``FailureIsSuccess``-wrapped ``TeardownEffects``
    Sequence then attempts embargo teardown: the ``EmbargoTeardownAuthorizationGate``
    call-out gates execution, and ``ThreatTerminationBranchNode`` fires when the
    received CaseStatus has P=True, X=True, or A=True (RSH-03-001 to RSH-03-003).
    The ``FailureIsSuccess`` wrapper ensures the tree still returns SUCCESS when
    the gate blocks teardown, mirroring the tolerant semantics in the use case
    layer.  This replaces the side-effect handling previously routed via the
    ``add_case_status_tree`` inbox-loopback (RSH-04-004).

    Args:
        request: The parsed inbound domain event.
        case_id: ID of the VulnerabilityCase.  When provided (or derivable
            from the inline status object), a guarded-commit subtree is
            inserted after precondition guards so the receiving CaseActor
            writes a canonical ledger entry (CLP-10-005).  Pass ``None``
            (with no derivable context) to skip the commit.
        call_out: Call-out backend bundle for ``StatusAdoptionGate``.
            Defaults to :data:`STATUS_AUTHORIZATION_DETERMINISTIC` which
            approves all non-CASE_OWNER updates (historical behavior).

    Returns:
        Root node of the ``AddParticipantStatusBT`` Sequence.
    """
    status_id = request.status_id or ""
    participant_id = request.participant_id or ""
    actor_id = request.actor_id
    status_obj = request.status

    # Derive case_id from the inline status object when not supplied explicitly.
    # VerifySenderIsParticipantNode falls back to a DataLayer lookup when None.
    tree_case_id: str | None = case_id
    if tree_case_id is None and status_obj is not None:
        context_field = getattr(status_obj, "context", None)
        if context_field:
            tree_case_id = str(context_field)

    # StatusAdoptionGate (RSH-01-002): CASE_OWNER gospel bypass first; all
    # others route through the CaseOwnerApprovesStatusUpdate call-out.
    status_adoption_gate = py_trees.composites.Selector(
        name="StatusAdoptionGate",
        memory=False,
        children=[
            CheckIsCaseOwnerNode(
                sender_actor_id=actor_id,
                case_id=tree_case_id,
                name="CheckIsCaseOwner",
            ),
            call_out.status_adoption_gate_factory(
                "CaseOwnerApprovesStatusUpdate"
            ),
        ],
    )

    root = create_receive_activity_tree(
        name="AddParticipantStatusBT",
        case_id=tree_case_id,
        precondition_guards=[
            VerifySenderIsParticipantNode(
                status_id=status_id,
                sender_actor_id=actor_id,
                case_id=tree_case_id,
            ),
            FilterParticipantStatusDimensionsNode(
                participant_id=participant_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
        ],
        effect_nodes=[
            append_participant_status_tree(
                status_id=status_id,
                participant_id=participant_id,
                status_obj_fallback=status_obj,
                validate_rm=False,
            ),
            status_adoption_gate,
            EmitCaseStatusUpdateNode(
                case_id=tree_case_id or "",
                name="EmitCaseStatusUpdate",
            ),
            py_trees.decorators.FailureIsSuccess(
                name="TeardownEffectsOrSkip",
                child=py_trees.composites.Sequence(
                    name="TeardownEffects",
                    memory=False,
                    children=[
                        call_out.embargo_teardown_authorization_gate_factory(
                            "EmbargoTeardownAuthorizationGate"
                        ),
                        ThreatTerminationBranchNode(
                            status_obj=status_obj,
                            case_id=tree_case_id,
                            name="ThreatTerminationBranch",
                        ),
                    ],
                ),
            ),
            EmitRMGapNoteNode(
                sender_actor_id=actor_id,
                case_id=tree_case_id,
                name="EmitRMGapNote",
            ),
        ],
    )
    logger.debug(
        "Created AddParticipantStatusBT for status=%s participant=%s"
        " actor=%s case=%s (StatusAdoptionGate: %s)",
        status_id,
        participant_id,
        actor_id,
        tree_case_id,
        call_out.__class__.__name__,
    )
    return root
