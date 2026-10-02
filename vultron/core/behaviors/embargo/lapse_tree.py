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

"""The CASE_MANAGER's evaluation and commit of an embargo invite lapse.

Only the CASE_MANAGER evaluates lapse, and its lapse entry is committed behind
its role gate (CM-28-003, CM-28-014, BT-17-001)::

    EvaluateInviteLapseBT (CASE_MANAGER-gated Selector)
    └─ EvaluateInviteLapse (Sequence)
       ├─ EvaluateInviteLapseNode             # read only: lapsed? declines?
       └─ CommitAndApplyLapseIfDue (Selector)
          ├─ Inverter(InviteLapseDeclinesNode)  # nothing to lapse
          └─ CommitAndApplyLapse (Sequence)
             ├─ CommitLogEntryBT              # the CM-28-009 lapse entry
             └─ RecordInviteLapseNode         # PEC INVITED → DECLINED

The guard reads, the commit follows and the effect comes last (CLP-10-006).
That order is what makes a retry safe: a commit that fails has applied
nothing, so the redelivered answer finds the invitee still ``INVITED`` and
commits the lapse, where "decline first, commit if consent changed" would
find it ``DECLINED`` and skip the entry for good.

The inner Selector is the "skip unless" shape ``vultron/core/behaviors/AGENTS.md``
otherwise discourages, on purpose: "nothing to lapse" is a successful
evaluation, and a Sequence that FAILed there would make the caller's
``applied_or_raise`` raise.  It is not a refusal arm: a non-manager never
reaches it, and the Accept tree's own gate refuses that store's answer.

A store that is not the CASE_MANAGER runs nothing and leaves ``result_out``
unset; the caller reads that as "no lapse here" and lets its own gate refuse
the answer.  The entry's replica apply node is
:class:`~vultron.core.behaviors.embargo.nodes.lapse.ApplyInviteLapseFromLedgerNode`.
"""

from datetime import datetime
from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.nodes.lapse import (
    EvaluateInviteLapseNode,
    InviteLapseDeclinesNode,
    RecordInviteLapseNode,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    INVITE_LAPSED_EVENT_TYPE,
)


def lapse_payload_snapshot(
    *,
    case_id: str,
    invitee_id: str,
    invite_id: str,
    embargo_id: str,
    published: str,
) -> dict[str, Any]:
    """The CM-28-009 lapse entry's snapshot, attributed to the lapsed invitee.

    *published* is the invitee's own claimed time — its late answer's — not
    the CASE_MANAGER's clock: mixing the two inside one actor's claimed stream
    is what CLP-15-003 reads as a regression.
    """
    return {
        "type": "Lapse",
        "actor": invitee_id,
        "context": case_id,
        "published": published,
        "object": {
            "type": "Invite",
            "id": invite_id,
            "object": {"type": "EmbargoEvent", "id": embargo_id},
        },
    }


def create_invite_lapse_tree(
    *,
    case_id: str,
    invitee_id: str,
    invite_id: str,
    embargo_id: str,
    published: str,
    now: datetime,
    result_out: dict[str, Any],
) -> py_trees.behaviour.Behaviour:
    """Build the CASE_MANAGER-gated lapse evaluation for one invitee's answer.

    Args:
        case_id: The case the Invite was for.
        invitee_id: The participant answering late.
        invite_id: The answered Invite; the entry's object id.
        embargo_id: The embargo the Invite proposed.
        published: The answer's claimed time (see
            :func:`lapse_payload_snapshot`).
        now: The instant the deadline is compared against.
        result_out: Receives ``is_lapsed`` and ``declines`` from
            :class:`EvaluateInviteLapseNode` when the gate passes.
    """
    commit_if_lapsed = py_trees.composites.Selector(
        name="CommitAndApplyLapseIfDue",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="NoLapseDue",
                child=InviteLapseDeclinesNode(result_out=result_out),
            ),
            py_trees.composites.Sequence(
                name="CommitAndApplyLapse",
                memory=False,
                children=[
                    create_commit_log_entry_tree(
                        case_id=case_id,
                        object_id=invite_id,
                        event_type=INVITE_LAPSED_EVENT_TYPE,
                        payload_snapshot=lapse_payload_snapshot(
                            case_id=case_id,
                            invitee_id=invitee_id,
                            invite_id=invite_id,
                            embargo_id=embargo_id,
                            published=published,
                        ),
                    ),
                    RecordInviteLapseNode(
                        case_id=case_id, invitee_id=invitee_id
                    ),
                ],
            ),
        ],
    )
    return create_case_manager_gated_tree(
        name="EvaluateInviteLapseBT",
        case_id=case_id,
        children=[
            EvaluateInviteLapseNode(
                case_id=case_id,
                invitee_id=invitee_id,
                now=now,
                result_out=result_out,
            ),
            commit_if_lapsed,
        ],
        body_name="EvaluateInviteLapse",
    )


__all__ = ["create_invite_lapse_tree", "lapse_payload_snapshot"]
