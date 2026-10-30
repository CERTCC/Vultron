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
post-adoption CaseStatus, adding every P, X or A latch the sender reported and
clearing none, directly to the case ledger without routing through the inbox
seam (RSH-01-003, RSH-04-006).  The embargo teardown and the CSB-18 diagnostic follow it
(RSH-01-004).  This tree is the only received path by which a participant's
P, X or A report reaches the case status: ``Add(CaseStatus)`` is the
CASE_MANAGER's alone (RSH-04-001, RSH-04-005).

    AddParticipantStatusBT (Sequence)
    ├─ [IntakeReceivedActivityNode]           # Always first (CLP-10-017)
    ├─ SenderRuleGuard                        # Declared sender rule (HP-01-008, RSH-08-007)
    ├─ PreconditionGuardStage                 # Refusal-effects stage (CLP-10-022)
    │   ├─ CarriedObjectInTargetCaseNode      # Guard: status of this case (HP-08-007)
    │   ├─ [OnBehalfStatusGuard]              # Another's record: only v→V/d→D (RSH-08-007)
    │   ├─ CheckParticipantStatusAcceptableNode  # Guard: accept whole or refuse whole (RSH-09)
    │   └─ RefusalEffects → IfCaseManager[EmitRMGapNoteNode]  # Note on a wholly refused regression (RSH-06-004)
    └─ AddParticipantStatusBTAct (ActTransaction, only if case_id)  # One act (CLP-07-015)
        ├─ GuardedCommitOrSkip (Selector)  # Record receipt first (CLP-10-006)
        │   ├─ Sequence("SkipIfNotCaseManager")
        │   │   └─ Inverter(CheckIsCaseManagerNode)
        │   └─ CommitCaseLedgerEntryNode
        └─ AdoptParticipantStatusIfCaseManager (CaseManagerGate, from the factory)  # RSH-08-003
            └─ Body (Sequence)                 # CASE_MANAGER only (#3814)
                ├─ AppendParticipantStatusNode # Step 2: append status to participant record
                └─ AdoptOrWithhold (Selector)  # A withheld adoption keeps the act
                    ├─ AdoptionWithheld (Inverter)
                    │   └─ StatusAdoptionGate (Selector)  # Authorization (RSH-01-002)
                    │       ├─ CheckIsCaseOwnerNode       # Hard bypass: CASE_OWNER gospel
                    │       └─ CaseOwnerApprovesStatusUpdate  # Call-out: non-owners
                    └─ AdoptStatus (Sequence)
                        ├─ EmitCaseStatusUpdateNode  # Adopted P/X/A (RSH-01-003)
                        ├─ TeardownEffectsOrSkip (FailureIsSuccess)
                        │   └─ TeardownEffects (Sequence)
                        │       ├─ EmbargoTeardownAuthorizationGate  # RSH-02-001
                        │       └─ ThreatTerminationBranchNode       # RSH-03-001
                        ├─ PxaEmInvariantDiagnosticNode  # CSB-18-002..004 check (#4829)
                        └─ EmitRMGapNoteNode  # add_note_to_case on RM anomaly (RSH-06-004)

    A replica holding a copy of the ``Add(ParticipantStatus)`` writes nothing: the whole
    adoption body runs only at the CASE_MANAGER, and the replica takes the move
    from the committed ``add_participant_status_to_participant`` ledger entry
    (RSH-08-003, PCR-03-001).

``CheckParticipantStatusAcceptableNode`` judges the received status as a whole
before the commit: it is accepted as sent, or refused whole, with every refused
dimension and its reason reported to the sender in the refusal notice
(RSH-09-001, RSH-09-002, CLP-05-001).  A refused status is never rewritten into
one the sender did not send (ADR-0107), so a refusal returns FAILURE here,
before any canonical ledger entry is committed.  When the refused status
carried an RM anomaly, the factory's refusal-effects stage posts the RSH-06-004
note before the tree fails (CLP-10-022).

Per specs/multi-actor-demo.yaml DEMOMA-07-003, DEMOMA-07-005.
Per specs/received-status-handling.yaml RSH-01-001 to RSH-01-004, RSH-09.
Per ADR-0050: canonical RM closure is routed through Leave(VulnerabilityCase)
receive path in receive_close_case_tree, not here.
"""

import logging

import py_trees

from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    StatusAuthorizationCallOutBundle,
)
from vultron.core.behaviors.case.nodes.carried_object_case import (
    CarriedObjectInTargetCaseNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case_status_snapshot import (
    EmitCaseStatusUpdateNode,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsCaseOwnerNode,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    AuthoredParticipantRecord,
    SenderCheckContext,
)
from vultron.core.behaviors.status.append_participant_status_tree import (
    append_participant_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    CheckParticipantStatusAcceptableNode,
    rm_gap_note,
)
from vultron.core.behaviors.status.nodes.cs_invariant_diagnostic import (
    PxaEmInvariantDiagnosticNode,
)
from vultron.core.behaviors.status.nodes.status_subject import (
    on_behalf_status_guard,
)
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)
from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.primitives import same_actor_id

logger = logging.getLogger(__name__)


def _adopt_or_withhold(
    adoption_gate: py_trees.behaviour.Behaviour,
    adoption: list[py_trees.behaviour.Behaviour],
) -> py_trees.behaviour.Behaviour:
    """Adopt the status when *adoption_gate* passes; else withhold, and succeed.

    A withheld adoption is not a failure of the act: the raw claim is on the
    participant record and its entry is committed (RSH-01-001, RSH-09-008).
    So the act keeps them, and only a failure of *adoption* itself fails the
    act and rolls it back (CLP-07-015).  The shape is the CASE_MANAGER
    gate's: the ``Inverter`` makes a withheld adoption the Selector's
    success, and a failed adoption its failure::

        AdoptOrWithhold (Selector)
        ├── AdoptionWithheld (Inverter(adoption_gate))
        └── AdoptStatus (Sequence[*adoption])
    """
    return py_trees.composites.Selector(
        name="AdoptOrWithhold",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="AdoptionWithheld", child=adoption_gate
            ),
            py_trees.composites.Sequence(
                name="AdoptStatus", memory=False, children=adoption
            ),
        ],
    )


def add_participant_status_tree(
    request: AddParticipantStatusToParticipantReceivedEvent,
    case_id: str | None = None,
    call_out: StatusAuthorizationCallOutBundle = STATUS_AUTHORIZATION_DETERMINISTIC,
    *,
    sender_rule: SenderRule,
    target_actor_id: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddParticipantStatus workflow.

    Handles receipt of an ``Add(ParticipantStatus, CaseParticipant)``
    activity.  Implements the DEMOMA-07-003 workflow with StatusAdoptionGate
    authorization (ADR-0046, RSH-01-001 to RSH-01-004).

    When ``case_id`` is provided, a guarded-commit subtree is inserted
    after precondition guards so the canonical ledger records receipt of the
    triggering activity before any protocol effects run (CLP-10-006).
    Running the tree with ``actor_id=receiving_actor_id`` (ADR-0022
    single-BT shape) means ``CheckIsCaseManagerNode`` in that subtree
    correctly fires only when the receiving actor holds
    ``CVDRole.CASE_MANAGER``.

    The *case_id* for the commit and all children is the target
    participant's own case, which the use case reads from the receiver's
    record of the participant (HP-08-008); the status's ``context`` never
    chooses it.  ``CarriedObjectInTargetCaseNode`` refuses, before the
    commit, a status whose ``context`` names another case or none
    (HP-08-007).  With no case known, the sender guard refuses, because the
    declared rule states no side for an activity outside any case
    (HP-01-024).

    After ``AppendParticipantStatusNode`` records the raw peer update, a
    ``StatusAdoptionGate`` (Selector/Fallback) decides whether the CaseActor
    should adopt the status:

    - ``CheckIsCaseOwnerNode`` — hard bypass for CASE_OWNER gospel (RSH-01-002)
    - ``CaseOwnerApprovesStatusUpdate`` — call-out backed by
      ``call_out.status_adoption_gate_factory``; default is ``AlwaysSucceed``

    When the gate passes, ``EmitCaseStatusUpdateNode`` writes the post-adoption
    CaseStatus, adding every P, X or A latch the report sets and clearing
    none, directly to the case ledger and fans it out to participants
    (RSH-01-003, RSH-04-006).  A ``FailureIsSuccess``-wrapped
    ``TeardownEffects`` Sequence then attempts embargo teardown: the
    ``EmbargoTeardownAuthorizationGate`` call-out gates execution, and
    ``ThreatTerminationBranchNode`` fires when the received CaseStatus has
    P=True, X=True, or A=True (RSH-03-001 to RSH-03-003).
    The ``FailureIsSuccess`` wrapper ensures the tree still returns SUCCESS when
    the gate blocks teardown, mirroring the tolerant semantics in the use case
    layer.  ``PxaEmInvariantDiagnosticNode`` then reads the post-teardown EM and
    commits a CSB-18 note when an adopted P, X or A sits beside an embargo that
    is still in force (CSB-18-002..004, #4829).

    Args:
        request: The parsed inbound domain event.
        case_id: ID of the target participant's VulnerabilityCase
            (HP-08-008).  When provided, a guarded-commit subtree is
            inserted after precondition guards so the receiving CaseActor
            writes a canonical ledger entry (CLP-10-005).  ``None`` leaves
            no case, and the sender guard refuses (HP-01-024).
        call_out: Call-out backend bundle for ``StatusAdoptionGate``.
            Defaults to :data:`STATUS_AUTHORIZATION_DETERMINISTIC` which
            approves all non-CASE_OWNER updates (historical behavior).
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).
        target_actor_id: The actor the receiver's stored record of the
            target participant names.  When it is not the sender, the
            status is an on-behalf assertion, and the tree admits only the
            v→V or d→D a CASE_MANAGER or Case Owner may assert for this
            actor (RSH-08-007, PRM-06-003/004).  The sender guard has
            already refused any other sender of such a status.

    Returns:
        Root node of the ``AddParticipantStatusBT`` Sequence.
    """
    status_id = request.status_id or ""
    participant_id = request.participant_id or ""
    actor_id = request.actor_id
    status_obj = request.status

    # The case is the target participant's own, resolved by the use case
    # from the receiver's record (HP-08-008); the status never chooses it.
    tree_case_id: str | None = case_id

    # StatusAdoptionGate (RSH-01-002): CASE_OWNER gospel bypass first; all
    # others route through the CaseOwnerApprovesStatusUpdate call-out.
    status_adoption_gate = py_trees.composites.Selector(
        name="StatusAdoptionGate",
        memory=False,
        children=[
            SenderIsCaseOwnerNode(
                sender_actor_id=actor_id,
                case_id=tree_case_id,
                name="SenderIsCaseOwner",
            ),
            call_out.status_adoption_gate_factory(
                "CaseOwnerApprovesStatusUpdate"
            ),
        ],
    )

    root = create_receive_activity_tree(
        name="AddParticipantStatusBT",
        case_id=tree_case_id,
        sender_rule=sender_rule,
        # A replica takes the update from the CASE_MANAGER alone, so with no
        # CASE_MANAGER to check against it refuses (PCR-03-001, #4646).
        # At the CASE_MANAGER the sender is the participant the target
        # record names, or the CASE_MANAGER or Case Owner (RSH-08-007).
        sender_context=SenderCheckContext(
            sender_id=actor_id,
            case_id=tree_case_id,
            case_manager_required=True,
            authored_object=AuthoredParticipantRecord(
                participant_id=participant_id
            ),
        ),
        precondition_guards=[
            # HP-08-007: a status of another case never joins this one.
            # RSH-08-007: only the participant asserts its own status, save
            # the on-behalf v→V and d→D of PRM-06-003/004.
            *(
                [
                    CarriedObjectInTargetCaseNode(
                        object_id=status_id,
                        carried=status_obj,
                        case_id=tree_case_id,
                    ),
                ]
                if tree_case_id
                else []
            ),
            *(
                [
                    on_behalf_status_guard(
                        case_id=tree_case_id,
                        participant_id=participant_id,
                        target_actor_id=target_actor_id,
                        status_id=status_id,
                        status_obj=status_obj,
                    )
                ]
                if tree_case_id
                and target_actor_id is not None
                and not same_actor_id(target_actor_id, actor_id)
                else []
            ),
            CheckParticipantStatusAcceptableNode(
                participant_id=participant_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
        ],
        # RSH-08-003: the two-seam adoption pipeline — append the raw peer
        # status, decide adoption, write the canonical ``CaseStatus``, run the
        # teardown side-effects, and post the RSH-06-004 gap note — is all the
        # CASE_MANAGER's work.  ``add_participant_status_to_participant`` is
        # committed and replayed (ParticipantStatus slot), so a replica holding a
        # copy of the ``Add(ParticipantStatus)`` writes nothing and takes the move from
        # the ledger fan-out (#3814).  The pipeline is ordered (adoption gates
        # the emit, teardown reads the emitted status), so it moves under the
        # gate as one unit.
        manager_effects=[
            append_participant_status_tree(
                status_id=status_id,
                participant_id=participant_id,
                status_obj_fallback=status_obj,
                validate_rm=False,
            ),
            _adopt_or_withhold(
                status_adoption_gate,
                [
                    # The canonical CaseStatus adds every P, X or A latch the sender
                    # reported in its embedded case status, clearing none
                    # (RSH-01-003, #4956).
                    EmitCaseStatusUpdateNode(
                        case_id=tree_case_id,
                        name="EmitCaseStatusUpdate",
                        # The case adopts the report's P/X/A here, read at tick after
                        # the append, so a status received by reference is adopted
                        # too (RSH-01-003).
                        reported_status_id=status_id or None,
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
                                    # Prefer the peer's embedded CaseStatus for the
                                    # PXA check: it was accepted whole, so it is the
                                    # stored copy the emit adopted (RSH-09-001).
                                    # Enable DataLayer fallback so that when it is
                                    # absent _threat_present reads the case's
                                    # current_status (written by
                                    # EmitCaseStatusUpdateNode just above).
                                    status_obj=getattr(
                                        status_obj, "case_status", None
                                    ),
                                    case_id=tree_case_id,
                                    name="ThreatTerminationBranch",
                                    use_datalayer_fallback=True,
                                ),
                            ],
                        ),
                    ),
                    # The CSB-18 note is the CASE_MANAGER's own act, committed and
                    # replicated (#4829); it reads the post-teardown EM, so a gate
                    # that blocked the teardown is reported (CSB-18-002..004).
                    PxaEmInvariantDiagnosticNode(
                        status_obj=status_obj,
                        case_id=tree_case_id,
                        name="PxaEmInvariantDiagnostic",
                    ),
                    rm_gap_note(actor_id, tree_case_id),
                ],
            ),
        ]
        if tree_case_id
        else None,
        manager_case_id=tree_case_id if tree_case_id else None,
        manager_gate_name=(
            "AdoptParticipantStatusIfCaseManager" if tree_case_id else None
        ),
        # A refused regression owes the sender the same note
        # (RSH-06-004); the factory runs it only on the refusal, at the
        # CASE_MANAGER, once per received activity (CLP-10-022).
        refusal_effects=[rm_gap_note(actor_id, tree_case_id)],
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
