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
Case prioritization behavior tree composition.

This module composes the engage_case and defer_case workflows as behavior
trees. These handle the receive-side of RmEngageCaseActivity (Join(VulnerabilityCase))
and RmDeferCaseActivity (Ignore(VulnerabilityCase)) activities.

Background: RM is a participant-specific state machine. Each CaseParticipant
wraps an Actor within a case and carries its own RM state via
CaseParticipant.participant_status[].rm_state. The trees here update that
state when an actor notifies us they have engaged or deferred the case.

Per specs/behavior-tree-integration.yaml BT-06 requirements.

Structure:

    EngageCaseBT (Sequence)
    ├─ Intake
    ├─ HoldCarriedEmbargoNode                        # Only when the Engage carried a case snapshot
    ├─ StoreEmbeddedParticipantsNode                 # Only when the Engage carried a case snapshot
    ├─ SenderIsActiveParticipantNode                 # Sender guard (HP-01-006)
    ├─ AdjudicateRMDeclarationNode(ACCEPTED)         # RM acceptance rule (RSH-06-006)
    ├─ GuardedCommitCaseLedgerEntryBT                # Record receipt before effects (CLP-10-006)
    ├─ IdempotentTransitionRMtoAccepted              # Record the sender's ACCEPTED (RSH-08-001)
    ├─ EmitRMGapNoteNode                             # RSH-06-004 note on a non-adjacent jump
    └─ GuardedBroadcastEngageCaseBT                  # CASE_MANAGER only (CM-06-001)
       ├─ CaptureCaseUpdateBroadcastExclusionsNode   # Resolve embargo-based exclusions
       └─ BroadcastCaseUpdateNode                    # Announce(VulnerabilityCase) → all participants

    DeferCaseBT (Sequence)
    ├─ Intake
    ├─ SenderIsActiveParticipantNode            # Sender guard (HP-01-006)
    ├─ AdjudicateRMDeclarationNode(DEFERRED)    # RM acceptance rule (RSH-06-006)
    ├─ GuardedCommitCaseLedgerEntryBT           # Record receipt before effects (CLP-10-006)
    ├─ IdempotentTransitionRMtoDeferred         # Record the sender's DEFERRED (RSH-08-001)
    └─ EmitRMGapNoteNode                        # RSH-06-004 note on a non-adjacent jump

The RM stages are shared with the report-verdict handlers through
:mod:`vultron.core.behaviors.report.rm_declaration_tree`, so every
activity-typed RM handler applies the acceptance rule of
``Add(ParticipantStatus)``: a forward move is recorded, a non-adjacent one
included, and a backward one is refused before the commit (RSH-06-006).

EvaluateCasePriority is now injected via bundle.evaluate_priority_factory
in create_prioritize_subtree (BT-18-004). The core class in
nodes/conditions.py is no longer instantiated directly here.
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.call_out.bundles.prioritization import (
    PRIORITIZATION_DETERMINISTIC,
)
from vultron.core.behaviors.case.engage_defer_trigger_tree import (
    defer_case_trigger_bt,
    engage_case_trigger_bt,
)
from vultron.core.behaviors.case.nodes.carried_snapshot import (
    HoldCarriedEmbargoNode,
    StoreEmbeddedParticipantsNode,
)
from vultron.core.behaviors.case.nodes.update import (
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.replica_emit_exemptions import (
    DEFER_RM_DECLARATION,
    ENGAGE_RM_DECLARATION,
)
from vultron.core.behaviors.report.rm_declaration_tree import (
    record_rm_declaration,
    rm_declaration_guard,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsActiveParticipantNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.rm import RM

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.prioritization import (
        PrioritizationCallOutBundle,
    )
    from vultron.core.ports.trigger_activity import TriggerActivityPort


logger = logging.getLogger(__name__)


def create_engage_case_tree(
    case_id: str,
    actor_id: str,
    case_obj: VulnerabilityCase | None = None,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for the engage_case workflow.

    Handles receipt of RmEngageCaseActivity (Join(VulnerabilityCase)): the sending
    actor has decided to engage the case, so we record their RM state
    transition to ACCEPTED in their CaseParticipant.participant_status.
    After committing the log entry, the CASE_MANAGER — and only the
    CASE_MANAGER — broadcasts an Announce(VulnerabilityCase)
    to all eligible participants so they receive the updated case state
    (including embedded CaseParticipant objects for #572/#573 coverage).

    Args:
        case_id: ID of VulnerabilityCase being engaged
        actor_id: The sender, whose declared RM state (ACCEPTED) is recorded
            (RSH-08-001)
        case_obj: The case snapshot the Engage carried, if any.  Its embargo
            is held and its inline participants are stored before the
            participant guard looks for them (CBT-05-005, EMB-18-003).

    Returns:
        Root node of the engage_case behavior tree (Sequence)
    """
    snapshot_steps: list[py_trees.behaviour.Behaviour] = (
        []
        if case_obj is None
        else [
            HoldCarriedEmbargoNode(case_obj, case_id),
            StoreEmbeddedParticipantsNode(case_obj, case_id),
        ]
    )
    root = create_receive_activity_tree(
        name="EngageCaseBT",
        case_id=case_id,
        precondition_guards=[
            *snapshot_steps,
            # After the snapshot steps, not in the factory's sender-guard
            # slot: an Engage may carry the sender's own participant inline.
            SenderIsActiveParticipantNode(
                status_id="", sender_actor_id=actor_id, case_id=case_id
            ),
            rm_declaration_guard(actor_id, RM.ACCEPTED, case_id),
        ],
        replica_effects=record_rm_declaration(
            actor_id, RM.ACCEPTED, case_id, name="TransitionRMtoAccepted"
        ),
        replica_emit_exemption=ENGAGE_RM_DECLARATION,
        # Only the CASE_MANAGER announces canonical case state: the
        # broadcast is authored as the executing actor (CM-06-001).
        manager_effects=[
            CaptureCaseUpdateBroadcastExclusionsNode(case_id=case_id),
            BroadcastCaseUpdateNode(case_id=case_id),
        ],
        manager_case_id=case_id,
        manager_gate_name="GuardedBroadcastEngageCaseBT",
    )

    logger.info(
        "Created EngageCaseBT for case=%s, actor=%s", case_id, actor_id
    )
    return root


def create_defer_case_tree(
    case_id: str,
    actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for the defer_case workflow.

    Handles receipt of RmDeferCaseActivity (Ignore(VulnerabilityCase)): the sending
    actor has decided to defer the case, so we record their RM state
    transition to DEFERRED in their CaseParticipant.participant_status.

    Args:
        case_id: ID of VulnerabilityCase being deferred
        actor_id: The sender, whose declared RM state (DEFERRED) is recorded
            (RSH-08-001)

    Returns:
        Root node of the defer_case behavior tree (Sequence)
    """
    root = create_receive_activity_tree(
        name="DeferCaseBT",
        case_id=case_id,
        sender_guard=SenderIsActiveParticipantNode(
            status_id="", sender_actor_id=actor_id, case_id=case_id
        ),
        precondition_guards=[
            rm_declaration_guard(actor_id, RM.DEFERRED, case_id),
        ],
        replica_effects=record_rm_declaration(
            actor_id, RM.DEFERRED, case_id, name="TransitionRMtoDeferred"
        ),
        replica_emit_exemption=DEFER_RM_DECLARATION,
    )

    logger.info("Created DeferCaseBT for case=%s, actor=%s", case_id, actor_id)
    return root


def create_prioritize_subtree(
    case_id: str,
    actor_id: str,
    trigger_activity: "TriggerActivityPort | None" = None,
    call_out: "PrioritizationCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree subtree for case prioritization (engage or defer).

    Phase 1: EvaluateCasePriority always returns SUCCESS → engage path.
    Future: Plug in SSVC or other priority evaluator (IDEA-26041004).

    Uses the canonical :func:`sender_side_bt` pattern (PCR-08-001) via
    :func:`engage_case_trigger_bt` and :func:`defer_case_trigger_bt`, which
    resolve the Case Manager and address outbound activities exclusively to
    that actor.

    Structure::

        PrioritizeBT (Selector)
        ├─ EngagePath (Sequence)
        │    ├─ EvaluateCasePriority                # stub: SUCCESS = engage
        │    ├─ EngageCaseTriggerBT (Sequence)      # RM → ACCEPTED, emit Join
        │    │    ├─ TransitionParticipantRMtoAccepted
        │    │    └─ SenderSideBT (Sequence)
        │    │         ├─ ResolveCaseManagerNode
        │    │         ├─ ConstructActivitiesNode
        │    │         └─ QueueToOutboxNode
        │    └─ OnAccept                            # Actuator call-out point
        └─ DeferPath (Sequence)
             ├─ DeferCaseTriggerBT (Sequence)       # RM → DEFERRED, emit Ignore
             │    ├─ TransitionParticipantRMtoDeferred
             │    └─ SenderSideBT (Sequence)
             │         ├─ ResolveCaseManagerNode
             │         ├─ ConstructActivitiesNode
             │         └─ QueueToOutboxNode
             └─ OnDefer                             # Actuator call-out point

    Per specs/behavior-tree-integration.yaml BT-06-005, BT-06-006.
    Per specs/participant-case-replica.yaml PCR-08-001, PCR-08-002.
    This is the SSVC evaluator connection point (IDEA-26041004).

    Args:
        case_id: ID of VulnerabilityCase to prioritize
        actor_id: ID of Actor making the engage/defer decision
        trigger_activity: Port for constructing outbound AS2 activities.
            When ``None``, the sender-side subtrees will fail at execution
            time with a descriptive error (consistent with the behaviour
            when the blackboard does not carry a factory).
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to :data:`~vultron.core.behaviors.call_out.bundles.prioritization.PRIORITIZATION_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the prioritize behavior tree (Selector)
    """
    bundle = call_out if call_out is not None else PRIORITIZATION_DETERMINISTIC
    # Phase 2: bundle.enough_info_factory and bundle.gather_info_factory are reserved for
    # the prioritization info-gathering loop and are not wired into the Phase 1 tree.
    factory = trigger_activity

    def _build_engage(case_manager_id: str) -> list[str]:
        if factory is None:
            raise RuntimeError(
                "create_prioritize_subtree: no TriggerActivityPort; "
                "cannot build engage_case activity"
            )
        activity_id, _ = factory.engage_case(
            case_id=case_id,
            actor=actor_id,
            to=[case_manager_id],
        )
        return [activity_id]

    def _build_defer(case_manager_id: str) -> list[str]:
        if factory is None:
            raise RuntimeError(
                "create_prioritize_subtree: no TriggerActivityPort; "
                "cannot build defer_case activity"
            )
        activity_id, _ = factory.defer_case(
            case_id=case_id,
            actor=actor_id,
            to=[case_manager_id],
        )
        return [activity_id]

    engage_path = py_trees.composites.Sequence(
        name="EngagePath",
        memory=False,
        children=[
            bundle.evaluate_priority_factory("EvaluateCasePriority"),
            engage_case_trigger_bt(
                case_id=case_id,
                actor_id=actor_id,
                activity_builder=_build_engage,
            ),
            bundle.on_accept_factory("OnAccept"),
        ],
    )
    defer_path = py_trees.composites.Sequence(
        name="DeferPath",
        memory=False,
        children=[
            defer_case_trigger_bt(
                case_id=case_id,
                actor_id=actor_id,
                activity_builder=_build_defer,
            ),
            bundle.on_defer_factory("OnDefer"),
        ],
    )
    root = py_trees.composites.Selector(
        name="PrioritizeBT",
        memory=False,
        children=[engage_path, defer_path],
    )
    logger.info(
        "Created PrioritizeBT for case=%s, actor=%s", case_id, actor_id
    )
    return root
