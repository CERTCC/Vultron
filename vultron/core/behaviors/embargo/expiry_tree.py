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

"""The CASE_MANAGER's evaluation and commit of an embargo invite expiry.

Only the CASE_MANAGER evaluates expiry, and its expiry entry is committed
behind its role gate (CM-28-003, CM-28-014, BT-17-001, ADR-0118)::

    EvaluateInviteExpiryBT (CASE_MANAGER-gated Selector)
    └─ EvaluateInviteExpiry (Sequence)
       ├─ EvaluateInviteExpiryNode          # applies PEC EXPIRE if deadline passed
       └─ CommitExpiryIfConsentChanged (Selector)
          ├─ Inverter(InviteExpiryChangedConsentNode)  # nothing expired now
          └─ CommitLogEntryBT               # the CM-28-009 expiry entry

The inner Selector is the "skip unless" shape ``vultron/core/behaviors/AGENTS.md``
otherwise discourages, on purpose: "nothing expired" is a successful
evaluation, and a Sequence that FAILed there would make the caller's
result_out check raise.

A store that is not the CASE_MANAGER runs nothing and leaves ``result_out``
unset; the caller reads ``IS_EXPIRED_KEY`` as False and proceeds to the
normal Accept tree, which also gates on CASE_MANAGER (BT-17-001, HP-01-005).
The entry's replica apply node is
:class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyInviteExpiryFromLedgerNode`.
"""

from datetime import datetime
from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    CONSENT_CHANGED_KEY,
    IS_EXPIRED_KEY,
    EvaluateInviteExpiryNode,
    InviteExpiryChangedConsentNode,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.rsvp_deadline import (
    INVITE_EXPIRED_EVENT_TYPE,
    INVITE_EXPIRED_SNAPSHOT_TYPE,
)


def expiry_payload_snapshot(
    *,
    case_id: str,
    invitee_id: str,
    invite_id: str,
    embargo_id: str,
    published: str,
) -> dict[str, Any]:
    """The CM-28-009 expiry entry's snapshot, attributed to the expired invitee.

    *published* is the invitee's own claimed time — its late answer's — not
    the CASE_MANAGER's clock: mixing the two inside one actor's claimed stream
    is what CLP-15-003 reads as a regression.
    """
    return {
        "type": INVITE_EXPIRED_SNAPSHOT_TYPE,
        "actor": invitee_id,
        "context": case_id,
        "published": published,
        "object": {
            "type": "Invite",
            "id": invite_id,
            "object": {"type": "EmbargoEvent", "id": embargo_id},
        },
    }


def create_invite_expiry_tree(
    *,
    case_id: str,
    invitee_id: str,
    invite_id: str,
    embargo_id: str,
    published: str,
    now: datetime,
    result_out: dict[str, Any],
) -> py_trees.behaviour.Behaviour:
    """Build the CASE_MANAGER-gated expiry evaluation for one invitee's answer.

    Args:
        case_id: The case the Invite was for.
        invitee_id: The participant answering late.
        invite_id: The answered Invite; the entry's object id.
        embargo_id: The embargo the Invite proposed.
        published: The answer's claimed time (see :func:`expiry_payload_snapshot`).
        now: The instant the deadline is compared against.
        result_out: Receives ``IS_EXPIRED_KEY`` and ``CONSENT_CHANGED_KEY``
            from :class:`EvaluateInviteExpiryNode` when the gate passes.
    """
    commit_if_expired = py_trees.composites.Selector(
        name="CommitExpiryIfConsentChanged",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="NoExpiryApplied",
                child=InviteExpiryChangedConsentNode(result_out=result_out),
            ),
            create_commit_log_entry_tree(
                case_id=case_id,
                object_id=invite_id or case_id,
                event_type=INVITE_EXPIRED_EVENT_TYPE,
                payload_snapshot=expiry_payload_snapshot(
                    case_id=case_id,
                    invitee_id=invitee_id,
                    invite_id=invite_id,
                    embargo_id=embargo_id,
                    published=published,
                ),
            ),
        ],
    )
    return create_case_manager_gated_tree(
        name="EvaluateInviteExpiryBT",
        case_id=case_id,
        children=[
            EvaluateInviteExpiryNode(
                case_id=case_id,
                invitee_id=invitee_id,
                now=now,
                result_out=result_out,
            ),
            commit_if_expired,
        ],
        body_name="EvaluateInviteExpiry",
    )


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "create_invite_expiry_tree",
    "expiry_payload_snapshot",
]
