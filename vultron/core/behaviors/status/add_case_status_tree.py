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
AddCaseStatus behavior tree composition.

Two-seam authorization model (ADR-0046, RSH-02-001 to RSH-03-003): after the
canonical CaseStatus write, a ``FailureIsSuccess``-wrapped ``TeardownEffects``
Sequence gates and fires embargo teardown when the CaseStatus signals a threat
(P=True OR X=True OR A=True).  A post-cascade ``PxaEmInvariantDiagnosticNode``
then verifies the CSB-18-002..004 invariant and posts a Note to the case if the
invariant is still violated (e.g. authorization gate blocked teardown).

    AddCaseStatusToCaseBT (Sequence)
    ├─ CheckCaseStatusIdempotencyNode              # precondition guard (CLP-10-009)
    ├─ CheckCsEphemeralStateNode                   # pX ephemeral guard (CSB-17-012, ISSUE-2524)
    ├─ CheckCsHistoryPrefixNode                    # history prefix guard (CSB-17-005, ISSUE-2524)
    ├─ FilterCsEmDimensionNode                     # per-dim EM adjudication (RSH-05, ISSUE-2256)
    ├─ FilterCsPxaDimensionNode                    # per-dim PXA adjudication (RSH-05, ISSUE-2256)
    ├─ FinalizeCsFilterNode                        # whole-refusal gate; FAILURE if nothing new
    ├─ GuardedCommitOrSkip                         # canonical ledger commit (CLP-10-006)
    ├─ AppendCaseStatusToCaseNode                  # AC-1: append status and persist
    ├─ TeardownEffectsOrSkip (FailureIsSuccess)    # RSH-03-001 to RSH-03-003
    │   └─ TeardownEffects (Sequence)
    │       ├─ EmbargoTeardownAuthorizationGate    # call-out (RSH-02-001)
    │       └─ ThreatTerminationBranchNode         # Embargo teardown (RSH-03-001)
    └─ PxaEmInvariantDiagnosticNode                # CSB-18-002..004 post-cascade check

Per issue #758 (BT-SM Integration: AddCaseStatusToCaseReceivedUseCase),
RSH-02-001 to RSH-03-003, ADR-0046, CLP-10-006, CLP-10-009.
Per issue #2524 (CS invariants: ephemeral-state and history guards), CSB-17-012,
CSB-17-005.
Per CONCERN-3008 (PXA↔EM entailment enforcement), CSB-18-002..004.
"""

import logging

import py_trees

from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    StatusAuthorizationCallOutBundle,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent
from vultron.core.behaviors.status.nodes import (
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
)
from vultron.core.behaviors.status.nodes.cs_dimension_filter import (
    FilterCsEmDimensionNode,
    FilterCsPxaDimensionNode,
    FinalizeCsFilterNode,
)
from vultron.core.behaviors.status.nodes.cs_invariant_guards import (
    CheckCsEphemeralStateNode,
    CheckCsHistoryPrefixNode,
)
from vultron.core.behaviors.status.nodes.cs_invariant_diagnostic import (
    PxaEmInvariantDiagnosticNode,
)
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)

logger = logging.getLogger(__name__)


def add_case_status_tree(
    request: AddCaseStatusToCaseReceivedEvent,
    call_out: StatusAuthorizationCallOutBundle = STATUS_AUTHORIZATION_DETERMINISTIC,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddCaseStatusToCase workflow.

    Handles receipt of an ``Add(CaseStatus, VulnerabilityCase)`` activity.
    Implements nine nodes in a Sequence:

    1. Idempotency check — fail fast if the status is already present.
    2. Ephemeral-state guard — rejects CaseStatus that violates the pX→P
       constraint (CSB-17-012, ISSUE-2524).
    3. History-prefix guard — rejects single-step PXA transitions that would
       produce an invalid CS history prefix (CSB-17-005, ISSUE-2524).
    4. Per-dimension EM adjudication — accept valid advances, carry forward
       refused EM; returns FAILURE when the case is not found in the DataLayer
       (CLP-10-009), otherwise SUCCESS (RSH-05, ISSUE-2256).
    5. Per-dimension PXA adjudication — accepts monotone-forward PXA moves,
       carries forward refused PXA; always returns SUCCESS (RSH-05, ISSUE-2256).
    6. Whole-refusal gate — returns FAILURE if no dimension carries new state;
       returns SUCCESS otherwise, publishing the filtered CaseStatus.
    7. Append and persist — write the filtered CaseStatus to the case record.
    8. ``TeardownEffectsOrSkip`` (``FailureIsSuccess`` decorator) — wraps a
       Sequence of the ``EmbargoTeardownAuthorizationGate`` call-out
       (RSH-02-001) and ``ThreatTerminationBranchNode`` (RSH-03-001 to
       RSH-03-003). Decorated so that authorization-gate FAILURE does not
       abort the outer Sequence — teardown side-effects are optional.
    9. ``PxaEmInvariantDiagnosticNode`` — reads fresh EM state from the
       DataLayer after the teardown block and posts a ``Note`` to the case
       if the CSB-18-002..004 invariant is still violated (e.g. gate blocked
       teardown). Always returns SUCCESS. (CONCERN-3008)

    Args:
        request: The parsed inbound domain event.
        call_out: Call-out backend bundle for the ``EmbargoTeardownAuthorizationGate``.
            Defaults to :data:`STATUS_AUTHORIZATION_DETERMINISTIC` which
            approves all side-effects (historical behavior).

    Returns:
        Root node of the ``AddCaseStatusToCaseBT`` Sequence.
    """
    status_id = request.status_id or ""
    case_id: str | None = request.case_id or None
    status_obj = request.status
    sender_actor_id = request.actor_id or None

    root = create_receive_activity_tree(
        name="AddCaseStatusToCaseBT",
        case_id=case_id or None,
        precondition_guards=[
            CheckCaseStatusIdempotencyNode(
                case_id=case_id,
                status_id=status_id,
            ),
            CheckCsEphemeralStateNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
            CheckCsHistoryPrefixNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
            FilterCsEmDimensionNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
            FilterCsPxaDimensionNode(),
            FinalizeCsFilterNode(),
        ],
        effect_nodes=[
            AppendCaseStatusToCaseNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
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
                            case_id=case_id or None,
                            name="ThreatTerminationBranch",
                        ),
                    ],
                ),
            ),
            PxaEmInvariantDiagnosticNode(
                status_obj=status_obj,
                case_id=case_id,
                sender_actor_id=sender_actor_id,
                name="PxaEmInvariantDiagnostic",
            ),
        ],
    )
    logger.debug(
        "Created AddCaseStatusToCaseBT for status=%s case=%s actor=%s"
        " (EmbargoTeardownAuthorizationGate call-out: %s)",
        status_id,
        case_id,
        request.actor_id,
        call_out.__class__.__name__,
    )
    return root
