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
    ├─ CheckParticipantExists                        # Precondition: actor has a participant record
    ├─ GuardedCommitCaseLedgerEntryBT                  # Record receipt before effects (CLP-10-006)
    ├─ TransitionParticipantRMtoAccepted             # Update RM state to ACCEPTED
    ├─ CaptureCaseUpdateBroadcastExclusionsNode      # Resolve embargo-based exclusions
    └─ BroadcastCaseUpdateNode                       # Announce(VulnerabilityCase) → all participants

    DeferCaseBT (Sequence)
    ├─ CheckParticipantExists              # Precondition: actor has a participant record
    ├─ GuardedCommitCaseLedgerEntryBT         # Record receipt before effects (CLP-10-006)
    └─ TransitionParticipantRMtoDeferred   # Update RM state to DEFERRED

Note: EvaluateCasePriority (in nodes.py) is the stub node for the outgoing
direction — when the local actor decides whether to engage or defer. It is
not used in these receive-side trees but is exported for future use.
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory
from vultron.core.behaviors.case.engage_defer_trigger_tree import (
    defer_case_trigger_bt,
    engage_case_trigger_bt,
)
from vultron.core.behaviors.case.nodes import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.nodes.update import (
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
)
from vultron.core.behaviors.report.nodes import (
    CheckParticipantExists,
    EvaluateCasePriority,
    TransitionParticipantRMtoAccepted,
    TransitionParticipantRMtoDeferred,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort


def _default_on_accept_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.prioritize import OnAccept

    return OnAccept(name)


def _default_on_defer_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.prioritize import OnDefer

    return OnDefer(name)


logger = logging.getLogger(__name__)


def create_engage_case_tree(
    case_id: str,
    actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for the engage_case workflow.

    Handles receipt of RmEngageCaseActivity (Join(VulnerabilityCase)): the sending
    actor has decided to engage the case, so we record their RM state
    transition to ACCEPTED in their CaseParticipant.participant_status.
    After committing the log entry, broadcasts an Announce(VulnerabilityCase)
    to all eligible participants so they receive the updated case state
    (including embedded CaseParticipant objects for #572/#573 coverage).

    Args:
        case_id: ID of VulnerabilityCase being engaged
        actor_id: ID of Actor whose RM state transitions to ACCEPTED

    Returns:
        Root node of the engage_case behavior tree (Sequence)
    """
    root = create_receive_activity_tree(
        name="EngageCaseBT",
        case_id=case_id,
        precondition_guards=[
            CheckParticipantExists(case_id=case_id, actor_id=actor_id),
        ],
        effect_nodes=[
            TransitionParticipantRMtoAccepted(
                case_id=case_id, actor_id=actor_id
            ),
            CaptureCaseUpdateBroadcastExclusionsNode(case_id=case_id),
            BroadcastCaseUpdateNode(case_id=case_id),
        ],
    )

    logger.info(f"Created EngageCaseBT for case={case_id}, actor={actor_id}")
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
        actor_id: ID of Actor whose RM state transitions to DEFERRED

    Returns:
        Root node of the defer_case behavior tree (Sequence)
    """
    root = create_receive_activity_tree(
        name="DeferCaseBT",
        case_id=case_id,
        precondition_guards=[
            CheckParticipantExists(case_id=case_id, actor_id=actor_id),
        ],
        effect_nodes=[
            TransitionParticipantRMtoDeferred(
                case_id=case_id, actor_id=actor_id
            ),
        ],
    )

    logger.info(f"Created DeferCaseBT for case={case_id}, actor={actor_id}")
    return root


def create_prioritize_subtree(
    case_id: str,
    actor_id: str,
    trigger_activity: "TriggerActivityPort | None" = None,
    on_accept_factory: CallOutBackendFactory = _default_on_accept_factory,
    on_defer_factory: CallOutBackendFactory = _default_on_defer_factory,
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
        on_accept_factory: Factory for the Actuator call-out point that
            fires integration hooks when the report is accepted.  Defaults
            to the fuzzer backend (BT-18-004).
        on_defer_factory: Factory for the Actuator call-out point that
            fires integration hooks when the report is deferred.  Defaults
            to the fuzzer backend (BT-18-004).

    Returns:
        Root node of the prioritize behavior tree (Selector)
    """
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
            EvaluateCasePriority(case_id=case_id),
            engage_case_trigger_bt(
                case_id=case_id,
                actor_id=actor_id,
                activity_builder=_build_engage,
            ),
            on_accept_factory("OnAccept"),
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
            on_defer_factory("OnDefer"),
        ],
    )
    root = py_trees.composites.Selector(
        name="PrioritizeBT",
        memory=False,
        children=[engage_path, defer_path],
    )
    logger.info(f"Created PrioritizeBT for case={case_id}, actor={actor_id}")
    return root
