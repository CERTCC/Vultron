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

"""Received-side BT factories for the target's answer to a role Offer (CM-33).

The target of a role ``Offer(CaseParticipantRole)`` answers the CASE_MANAGER
with ``Accept`` or ``Reject`` (CM-33-004).  The CASE_MANAGER checks that the
sender is the target of a role Offer it recorded and that the Offer is open
(CM-33-005), commits the answer and broadcasts ``Announce(CaseLedgerEntry)``
(CM-33-006, CLP-02-012), and on an Accept grants the role on its own replica
(CM-02-016).  Every other participant learns the grant by replaying the
entry (``ApplyCaseParticipantRoleGrantFromLedgerNode``).

Structure::

    Accept/RejectCaseParticipantRoleReceivedBT (Sequence)
    ├── IntakeReceivedActivityNode      # archives the answer (CLP-10-017)
    ├── CaseOpenToExternalWrites
    ├── SenderRuleGuard                 # the recorded Offer's target, at the
    │                                   # CASE_MANAGER only (CM-33-005)
    ├── RoleOfferOpenNode               # open, not a redelivery (CM-33-005)
    ├── GuardedCommit                   # CASE_MANAGER only (CM-33-006)
    └── GrantRoleIfCaseManager          # Accept only (CM-02-016)
        └── GrantCaseParticipantRoleNode

Provides:

- :func:`create_accept_case_participant_role_tree`
- :func:`create_reject_case_participant_role_tree`
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.delegation import (
    GrantCaseParticipantRoleNode,
)
from vultron.core.behaviors.case.nodes.role_offer_guard import (
    RoleOfferOpenNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    RoleOfferRequest,
    SenderCheckContext,
)
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def _answer_tree(
    name: str,
    case_id: str,
    offer_id: str | None,
    sender_id: str,
    answer_id: str,
    carried_role: CVDRole | None,
    carried_target_id: str | None,
    sender_rule: SenderRule,
    grants_role: bool,
) -> py_trees.composites.Sequence:
    """The received tree both answers share; the Accept adds the grant.

    The grant takes the carried role and target, which the open-Offer guard
    checks against the recorded Offer before the commit, so the CASE_MANAGER
    grants what every replica grants from the entry.  An answer that carries
    no role or target has nothing to grant, and the guard refuses it.
    """
    manager_effects: list[py_trees.behaviour.Behaviour] | None = (
        [
            GrantCaseParticipantRoleNode(
                case_id=case_id,
                role=carried_role,
                target_actor_id=carried_target_id,
            )
        ]
        if grants_role and carried_role is not None and carried_target_id
        else None
    )
    tree = create_receive_activity_tree(
        name=name,
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id,
            case_id=case_id,
            request=RoleOfferRequest(offer_id=offer_id),
            case_manager_required=True,
        ),
        precondition_guards=[
            RoleOfferOpenNode(
                case_id=case_id,
                offer_id=offer_id,
                reply_id=answer_id,
                carried_role=carried_role,
                carried_target_id=carried_target_id,
            )
        ],
        manager_effects=manager_effects,
        manager_case_id=case_id if manager_effects else None,
        manager_gate_name="GrantRoleIfCaseManager"
        if manager_effects
        else None,
    )
    logger.debug(
        "Created %s for case='%s' offer='%s'", name, case_id, offer_id
    )
    return tree


def create_accept_case_participant_role_tree(
    case_id: str,
    offer_id: str | None,
    sender_id: str,
    answer_id: str,
    carried_role: CVDRole | None,
    carried_target_id: str | None,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Create the BT for ``AcceptCaseParticipantRoleReceivedUseCase``.

    The guards admit only the target of an open role Offer the CASE_MANAGER
    recorded, answering with a copy of that Offer (CM-33-005); the guarded
    commit ledgers the Accept and broadcasts it (CM-33-006); then the
    CASE_MANAGER grants the role on its own replica (CM-02-016).

    Args:
        case_id: The case the Accept names.
        offer_id: The Offer the Accept names: the recorded Offer or the
            CASE_MANAGER's forward of it.
        sender_id: The Accept's sender.
        answer_id: The Accept's own id, so a redelivery is recognised.
        carried_role: The role the Offer the Accept carries names.
        carried_target_id: The target the Offer the Accept carries names.
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    return _answer_tree(
        "AcceptCaseParticipantRoleReceivedBT",
        case_id,
        offer_id,
        sender_id,
        answer_id,
        carried_role,
        carried_target_id,
        sender_rule,
        grants_role=True,
    )


def create_reject_case_participant_role_tree(
    case_id: str,
    offer_id: str | None,
    sender_id: str,
    answer_id: str,
    carried_role: CVDRole | None,
    carried_target_id: str | None,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Create the BT for ``RejectCaseParticipantRoleReceivedUseCase``.

    The Accept's tree with no effects: the guards admit only the target of
    an open role Offer the CASE_MANAGER recorded (CM-33-005), and the guarded
    commit ledgers the Reject and broadcasts it (CM-33-006, CLP-02-012).  That
    entry closes the Offer; no role changes.

    Args:
        case_id: The case the Reject names.
        offer_id: The Offer the Reject names: the recorded Offer or the
            CASE_MANAGER's forward of it.
        sender_id: The Reject's sender.
        answer_id: The Reject's own id, so a redelivery is recognised.
        carried_role: The role the Offer the Reject carries names.
        carried_target_id: The target the Offer the Reject carries names.
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    return _answer_tree(
        "RejectCaseParticipantRoleReceivedBT",
        case_id,
        offer_id,
        sender_id,
        answer_id,
        carried_role,
        carried_target_id,
        sender_rule,
        grants_role=False,
    )


__all__ = [
    "create_accept_case_participant_role_tree",
    "create_reject_case_participant_role_tree",
]
