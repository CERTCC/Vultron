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

"""Tree factory for received Announce(VulnerabilityCase) activities.

Composes ``SeedAnnouncedCaseNode`` through ``create_receive_activity_tree`` so
intake archives the Announce first (CLP-10-017).

``("Announce", "VulnerabilityCase")`` is a canonical signature, yet the tree
carries no ``case_id`` and commits nothing — a documented exemption from
CLP-10-013, not an oversight.  Only the CASE_MANAGER sends this Announce, and
the sender guard admits it only from the CASE_MANAGER the receiver already
knows (PCR-03-001, PCR-03-004), so the receiver is a participant replica, not
the manager the commit stage is gated on (a manager's self-Announce would only
duplicate the entry it already holds).  A replica learns of case state from
the ledger fan-out (SYNC-02-002).  The commit gate here could only ever skip,
and the effect node cannot move ahead of a commit as a guard: seeding the
case is itself the write.
"""

import logging
from typing import Any

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.announce import (
    SeedAnnouncedCaseNode,
    announced_case_id,
)
from vultron.core.behaviors.case.nodes.case_copy import (
    CaseCopyNotStaleNode,
    RequestCaseCopyBackfillNode,
    StateSeededLedgerPositionNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sync.nodes.replay_held import (
    ReplayHeldSuccessorNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)

_NAME = "AnnounceVulnerabilityCaseReceivedBT"


def create_announce_vulnerability_case_received_tree(
    case_obj: VulnerabilityCase | Any,
    request: AnnounceVulnerabilityCaseReceivedEvent,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``AnnounceVulnerabilityCaseReceivedUseCase``.

    Structure (the CLP-10-010 stages, ADR-0111)::

        AnnounceVulnerabilityCaseReceivedBT (Sequence)
        ├── IntakeReceivedActivityNode        # intake
        ├── CaseOpenToExternalWrites          # post-close boundary
        ├── SenderIsCaseManagerNode           # sender guard (anchored)
        ├── CaseCopyNotStaleNode              # guard (SYNC-16-006)
        ├── SeedAnnouncedCaseNode             # effect (seed or replace)
        ├── RequestCaseCopyBackfillNode       # effect (SYNC-16-007)
        ├── ReplayHeldSuccessorNode           # effect (SYNC-14-009)
        └── StateSeededLedgerPositionNode     # effect (SYNC-17-008)

    A replica that already holds the case replaces it only with a copy whose
    ledger position is current against its own; a stale copy is skipped and
    a conflicting one refused, with the case unchanged (SYNC-16-006).  A copy
    ahead of the chain is backfilled: the case takes the copy's position and
    the replica asks for the missing entries (SYNC-16-007).  A first seed
    instead states the position the copy seeded the replica at, to the case's
    CASE_MANAGER, so it can resend an Invite the participant dropped before
    the copy arrived (SYNC-17-008, ADR-0163).

    An Announce that carries no ``VulnerabilityCase`` with an id is refused
    by the same tree's guard instead
    (:func:`~vultron.core.behaviors.case.intake_only_received_tree.create_incomplete_activity_received_tree`),
    so either way the delivery runs one tree and is archived (CLP-10-005,
    CLP-10-018).

    The factory composes the sender guard from *sender_rule* (HP-01-008):
    the sender must be the CASE_MANAGER this store has trusted for the case,
    the one its bootstrap recorded on a completed ``ReportCaseLink``
    (CBT-01-006, CBT-02-003), else the one the replica names, else the one
    the stub Invite recorded as the trust anchor; with none the Announce is
    refused (``case_manager_anchored``, PCR-03-001, PCR-03-004).  No refusal
    effect: only a participant replica receives this Announce, and it owes
    the CASE_MANAGER no answer.  No clock decision either: the tree names no
    case for the CASE_MANAGER gate, and a replica takes none (CLP-10-025).

    Args:
        case_obj: The Announce's ``object``, as received; anything but a
            ``VulnerabilityCase`` with an id is refused.
        request: The received event carrying the full activity context.
        sender_rule: The use case's declared sender rule (HP-01-008).

    Returns:
        The root ``Sequence``, ready for ``BTBridge.execute_with_setup()``.
    """
    try:
        case_id = announced_case_id(request, case_obj)
    except VultronValidationError as exc:
        return create_incomplete_activity_received_tree(_NAME, str(exc))
    root = create_receive_activity_tree(
        name=_NAME,
        case_id=None,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=request.actor_id,
            case_id=case_id,
            case_manager_anchored=True,
        ),
        precondition_guards=[
            CaseCopyNotStaleNode(
                case_id=case_id,
                case_obj=case_obj,
                request=request,
            ),
        ],
        replica_effects=[
            SeedAnnouncedCaseNode(
                case_id=case_id,
                case_obj=case_obj,
                request=request,
            ),
            RequestCaseCopyBackfillNode(
                case_id=case_id,
                case_obj=case_obj,
                request=request,
            ),
            # Seeding anchors the genesis hash, so an Announce held in the
            # pre-genesis window may now extend the chain: replay it, as it
            # was received, through this actor's inbox as a delivery of its
            # own (SYNC-15-005, SYNC-14-009).  After a replacement, an entry
            # held because the old case refused it extends the chain too, and
            # is stored as a no-op if the copy reflects it (SYNC-16-007).
            ReplayHeldSuccessorNode(
                case_id=case_id, name="ReplayHeldPreGenesisEntry"
            ),
            # Last, so a failed statement leaves every other effect done.
            StateSeededLedgerPositionNode(case_id=case_id),
        ],
    )
    logger.debug("Created %s for case='%s'", _NAME, case_id)
    return root
