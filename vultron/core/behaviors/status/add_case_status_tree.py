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
then verifies the CSB-18-002..004 invariant and, at the CASE_MANAGER, commits a
note as its own ``add_note_to_case`` entry if the invariant is still violated
(e.g. authorization gate blocked teardown; #4829).

    AddCaseStatusToCaseBT (Sequence)
    ├─ <intake, post-close guard, sender guard, clock decisions>  # factory
    ├─ CheckCaseStatusIdempotencyNode              # precondition guard (CLP-10-009)
    ├─ CheckCsEphemeralStateNode                   # pX ephemeral guard (CSB-17-012, ISSUE-2524)
    ├─ CheckCsHistoryPrefixNode                    # history prefix guard (CSB-17-005, ISSUE-2524)
    ├─ CheckCaseStatusAcceptableNode               # accept whole or refuse whole (RSH-09-005)
    ├─ GuardedCommitOrSkip                         # canonical ledger commit (CLP-10-006)
    ├─ TeardownEffectsOrSkip (FailureIsSuccess)    # RSH-03-001 to RSH-03-003 (ungated)
    │   └─ TeardownEffects (Sequence)
    │       ├─ EmbargoTeardownAuthorizationGate    # call-out (RSH-02-001)
    │       └─ ThreatTerminationBranchNode         # Embargo teardown (RSH-03-001)
    └─ AppendCaseStatusIfCaseManager (CaseManagerGate, from the factory)
        ├─ AppendCaseStatusToCaseNode              # AC-1: append status and persist
        └─ PxaEmInvariantDiagnosticNode            # CSB-18-002..004 post-cascade check

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
from vultron.core.behaviors.case.nodes.carried_object_case import (
    CarriedObjectInTargetCaseNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.replica_emit_exemptions import CASE_STATUS
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.behaviors.status.nodes import (
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
)
from vultron.core.behaviors.status.nodes.case_status_acceptance import (
    CheckCaseStatusAcceptableNode,
)
from vultron.core.behaviors.status.nodes.cs_invariant_diagnostic import (
    PxaEmInvariantDiagnosticNode,
)
from vultron.core.behaviors.status.nodes.cs_invariant_guards import (
    CheckCsEphemeralStateNode,
    CheckCsHistoryPrefixNode,
)
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)
from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent

logger = logging.getLogger(__name__)


def add_case_status_tree(
    request: AddCaseStatusToCaseReceivedEvent,
    call_out: StatusAuthorizationCallOutBundle = STATUS_AUTHORIZATION_DETERMINISTIC,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddCaseStatusToCase workflow.

    Handles receipt of an ``Add(CaseStatus, VulnerabilityCase)`` activity.
    Implements eight nodes in a Sequence:

    1. Idempotency check — fail fast if the status is already present.
    2. Case check — refuse a status whose ``context`` is not this case
       (HP-08-007, #4831).
    3. Ephemeral-state guard — rejects CaseStatus that violates the pX→P
       constraint (CSB-17-012, ISSUE-2524).
    4. History-prefix guard — rejects single-step PXA transitions that would
       produce an invalid CS history prefix (CSB-17-005, ISSUE-2524).
    5. Acceptance — the status is accepted as sent when its EM is the case's
       and its P/X/A confirms or advances the case's, and refused whole
       otherwise; also FAILURE when the case or the status cannot be resolved
       (CLP-10-009, RSH-09-005).
    6. Append and persist — write the CaseStatus to the case record.
    7. ``TeardownEffectsOrSkip`` (``FailureIsSuccess`` decorator) — wraps a
       Sequence of the ``EmbargoTeardownAuthorizationGate`` call-out
       (RSH-02-001) and ``ThreatTerminationBranchNode`` (RSH-03-001 to
       RSH-03-003). Decorated so that authorization-gate FAILURE does not
       abort the outer Sequence — teardown side-effects are optional.
    8. ``PxaEmInvariantDiagnosticNode`` — at the CASE_MANAGER only, reads
       fresh EM state from the DataLayer after the teardown block and commits
       a note as its own ``add_note_to_case`` entry if the CSB-18-002..004
       invariant is still violated (e.g. gate blocked teardown). A missing
       trigger-activity port or a refused commit is logged and succeeds; an
       internal error propagates. (CONCERN-3008, #4829)

    Args:
        request: The parsed inbound domain event.
        call_out: Call-out backend bundle for the ``EmbargoTeardownAuthorizationGate``.
            Defaults to :data:`STATUS_AUTHORIZATION_DETERMINISTIC` which
            approves all side-effects (historical behavior).
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it, ahead of every guard listed
            above (HP-01-008).

    Returns:
        Root node of the ``AddCaseStatusToCaseBT`` Sequence.
    """
    status_id = request.status_id or ""
    case_id: str | None = request.case_id or None
    status_obj = request.status
    sender_actor_id = request.actor_id

    root = create_receive_activity_tree(
        name="AddCaseStatusToCaseBT",
        case_id=case_id or None,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_actor_id, case_id=case_id
        ),
        precondition_guards=[
            CheckCaseStatusIdempotencyNode(
                case_id=case_id,
                status_id=status_id,
            ),
            # HP-08-007: a status of another case never joins this one.
            *(
                [
                    CarriedObjectInTargetCaseNode(
                        object_id=status_id,
                        carried=status_obj,
                        case_id=case_id,
                    )
                ]
                if case_id
                else []
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
            CheckCaseStatusAcceptableNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
        ],
        # RSH-08-003: appending the canonical ``CaseStatus`` moves PXA, which is
        # case state only the CASE_MANAGER writes; ``add_case_status_to_case`` is
        # committed and replayed (CaseStatus slot), so a replica cc'd on the
        # ``Add(CaseStatus)`` writes nothing and takes the move from the ledger
        # fan-out (#3814).  Only the append is gated.
        manager_effects=[
            AppendCaseStatusToCaseNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
            # The CSB-18 note is the CASE_MANAGER's own act, committed and
            # replicated (#4829), so it runs only where the commit can.
            PxaEmInvariantDiagnosticNode(
                status_obj=status_obj,
                case_id=case_id,
                name="PxaEmInvariantDiagnostic",
            ),
        ]
        if case_id
        else None,
        manager_case_id=case_id if case_id else None,
        manager_gate_name=(
            "AppendCaseStatusIfCaseManager" if case_id else None
        ),
        # The teardown side-effects stay ungated (CASE_STATUS exemption): on
        # the CASE_MANAGER they tear down after the adopted move; on a
        # participant replica they do not write case state — the threat
        # teardown's terminate request only *asks* the CASE_MANAGER
        # (RSH-03-001, EP-09-008).  They read the asserted ``status_obj`` and
        # the register-derived EM, so their position ahead of the gated append
        # does not matter (ADR-0122).
        replica_effects=[
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
                            sender_actor_id=sender_actor_id,
                        ),
                    ],
                ),
            ),
        ],
        replica_emit_exemption=CASE_STATUS,
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
