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

``Add(CaseStatus)`` is the CASE_MANAGER's record of the case status it
adopted, which it alone sends, and only to a participant (RSH-04-001,
RSH-04-005).  The factory's sender guard refuses it from any other sender
and at the CASE_MANAGER, so this tree runs only at a participant replica.
A replica writes no case state on receipt: it takes the CASE_MANAGER's
status from the ``Announce(CaseLedgerEntry)`` fan-out (RSH-08-003,
PCR-03-001).  The CASE_MANAGER's own status writes, including a
participant's adopted P, X or A, are in ``add_participant_status_tree`` and
the embargo trees (RSH-01-003, RSH-04-004).

    AddCaseStatusToCaseBT (Sequence)
    ├─ <intake, post-close guard, sender guard, clock decisions>  # factory
    ├─ CheckCaseStatusIdempotencyNode              # precondition guard (CLP-10-009)
    ├─ CarriedObjectInTargetCaseNode               # this case only (HP-08-007)
    ├─ CheckCsEphemeralStateNode                   # pX ephemeral guard (CSB-17-012, ISSUE-2524)
    ├─ CheckCsHistoryPrefixNode                    # history prefix guard (CSB-17-005, ISSUE-2524)
    ├─ CheckCaseStatusAcceptableNode               # accept whole or refuse whole (RSH-09-005)
    └─ GuardedCommitOrSkip                         # declined off the CASE_MANAGER (CLP-10-006)

Per issue #758 (BT-SM Integration: AddCaseStatusToCaseReceivedUseCase),
CLP-10-006, CLP-10-009.
Per issue #2524 (CS invariants: ephemeral-state and history guards), CSB-17-012,
CSB-17-005.
Per issue #4851, RSH-04-005.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.carried_object_case import (
    CarriedObjectInTargetCaseNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.behaviors.status.nodes import (
    CheckCaseStatusIdempotencyNode,
)
from vultron.core.behaviors.status.nodes.case_status_acceptance import (
    CheckCaseStatusAcceptableNode,
)
from vultron.core.behaviors.status.nodes.cs_invariant_guards import (
    CheckCsEphemeralStateNode,
    CheckCsHistoryPrefixNode,
)
from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent

logger = logging.getLogger(__name__)


def add_case_status_tree(
    request: AddCaseStatusToCaseReceivedEvent,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddCaseStatusToCase workflow.

    Handles receipt of an ``Add(CaseStatus, VulnerabilityCase)`` activity at
    a participant replica, from the case's CASE_MANAGER (RSH-04-005).  After
    the factory's intake and guards, five precondition guards run in a
    Sequence:

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

    The tree has no effects: a replica writes no case state on receipt and
    takes the status from the ledger fan-out (RSH-08-003), and it asks for no
    embargo teardown, since the CASE_MANAGER declared the status (RSH-03-004).

    Args:
        request: The parsed inbound domain event.
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
        # A replica admits it from the CASE_MANAGER alone, so with no
        # CASE_MANAGER to check against it refuses (RSH-04-005, PCR-03-001).
        sender_context=SenderCheckContext(
            sender_id=sender_actor_id,
            case_id=case_id,
            case_manager_required=True,
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
    )
    logger.debug(
        "Created AddCaseStatusToCaseBT for status=%s case=%s actor=%s",
        status_id,
        case_id,
        request.actor_id,
    )
    return root
