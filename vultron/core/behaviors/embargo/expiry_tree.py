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
behind its role gate (CM-28-003, CM-28-014, BT-17-001, ADR-0118).

The expiry tree uses the canonical guard → commit → effect pattern
(CLP-10-006, BT-06-006)::

    EvaluateInviteExpiryBT (CASE_MANAGER-gated Sequence)
    ├─ EvaluateInviteExpiryNode        # READ-ONLY: assess deadline, no writes
    └─ CommitAndApplyExpiryIfDue (Selector)
       ├─ Inverter(InviteExpiryNeedsApplyNode)   # nothing to commit
       └─ CommitAndApplyExpiry (Sequence)
          ├─ CommitLogEntryBT          # commit INVITE_EXPIRED_EVENT_TYPE entry
          └─ RecordInviteExpiryNode    # EFFECT: apply INVITED → TIMED_OUT

A failed commit leaves the invitee unchanged; ``RecordInviteExpiryNode`` only
runs after a successful commit.

A store that is not the CASE_MANAGER runs nothing and leaves ``result_out``
unset; the caller reads ``IS_EXPIRED_KEY`` as False and proceeds to the
normal Accept tree, which also gates on CASE_MANAGER (BT-17-001, HP-01-005).
The entry's replica apply node is
:class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyInviteExpiryFromLedgerNode`.

The honour-late-accept tree (EMB-17-001) similarly follows guard → commit →
effect::

    HonourLateAcceptBT (CASE_MANAGER-gated Sequence)
    └─ HonourLateAccept (Sequence)
       ├─ CommitLogEntryBT             # commit HONOUR_LATE_ACCEPT_EVENT_TYPE
       └─ HonourLateAcceptNode         # EFFECT: apply TIMED_OUT/DECLINED → AGREED

The re-invite of a stale accepter (EMB-17-003) is a CASE_MANAGER-gated commit →
effect node of the relay's frame::

    ReinviteStaleAccepterBT (CASE_MANAGER-gated)
    └─ ReinviteStaleAccepterNode     # stamp → build → commit → outbox → PEC INVITE

Replicas replay it through
:class:`~vultron.core.behaviors.embargo.nodes.relay_effect.ApplyEmbargoReinviteFromLedgerNode`.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

import py_trees

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    IS_EXPIRED_KEY,
    NEEDS_APPLY_KEY,
    EvaluateInviteExpiryNode,
    HonourLateAcceptNode,
    InviteExpiryNeedsApplyNode,
    RecordInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteStaleAccepterNode,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.rsvp_deadline import (
    HONOUR_LATE_ACCEPT_EVENT_TYPE,
    HONOUR_LATE_ACCEPT_SNAPSHOT_TYPE,
    INVITE_EXPIRED_EVENT_TYPE,
    INVITE_EXPIRED_NOOP_EVENT_TYPE,
    INVITE_EXPIRED_NOOP_SNAPSHOT_TYPE,
    INVITE_EXPIRED_SNAPSHOT_TYPE,
)

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig

# Keep the old alias so existing imports of CONSENT_CHANGED_KEY from this
# module still work.
CONSENT_CHANGED_KEY = NEEDS_APPLY_KEY


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


def honour_late_accept_payload_snapshot(
    *,
    case_id: str,
    accepting_actor_id: str,
    invite_id: str,
    embargo_id: str,
    published: str,
) -> dict[str, Any]:
    """Snapshot for the honour-late-accept entry (EMB-17-001, ADR-0118).

    Attributed to *accepting_actor_id*, so replicas can extract who
    agreed from the entry's ``actor`` field.
    """
    return {
        "type": HONOUR_LATE_ACCEPT_SNAPSHOT_TYPE,
        "actor": accepting_actor_id,
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

    The tree follows the guard → commit → effect pattern (CLP-10-006):
    :class:`~vultron.core.behaviors.embargo.nodes.expiry.EvaluateInviteExpiryNode`
    reads the deadline **without writing**, the commit node persists the
    ledger entry, and only then
    :class:`~vultron.core.behaviors.embargo.nodes.expiry.RecordInviteExpiryNode`
    applies ``INVITED → TIMED_OUT`` to the invitation's row.  A failed commit
    therefore leaves the
    invitee unchanged.

    Args:
        case_id: The case the Invite was for.
        invitee_id: The participant answering late.
        invite_id: The answered Invite; the entry's object id.
        embargo_id: The embargo the Invite proposed.
        published: The answer's claimed time (see :func:`expiry_payload_snapshot`).
        now: The instant the deadline is compared against.
        result_out: Receives ``IS_EXPIRED_KEY`` and ``NEEDS_APPLY_KEY``
            from :class:`EvaluateInviteExpiryNode` when the gate passes.
    """
    commit_and_apply = py_trees.composites.Sequence(
        name="CommitAndApplyExpiry",
        memory=False,
        children=[
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
            RecordInviteExpiryNode(
                case_id=case_id,
                invitee_id=invitee_id,
                embargo_id=embargo_id,
            ),
        ],
    )
    commit_and_apply_if_due = py_trees.composites.Selector(
        name="CommitAndApplyExpiryIfDue",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="NoExpiryNeedsApply",
                child=InviteExpiryNeedsApplyNode(result_out=result_out),
            ),
            commit_and_apply,
        ],
    )
    return create_case_manager_gated_tree(
        name="EvaluateInviteExpiryBT",
        case_id=case_id,
        children=[
            EvaluateInviteExpiryNode(
                case_id=case_id,
                invitee_id=invitee_id,
                embargo_id=embargo_id,
                now=now,
                result_out=result_out,
            ),
            commit_and_apply_if_due,
        ],
        body_name="EvaluateInviteExpiry",
    )


def create_honour_late_accept_tree(
    *,
    case_id: str,
    accepting_actor_id: str,
    invite_id: str,
    embargo_id: str,
    published: str,
) -> py_trees.behaviour.Behaviour:
    """Build the CASE_MANAGER-gated honour-late-accept tree (EMB-17-001).

    The tree follows the commit → effect pattern (CLP-10-006):
    the commit node persists the :data:`HONOUR_LATE_ACCEPT_EVENT_TYPE` entry,
    and only then
    :class:`~vultron.core.behaviors.embargo.nodes.expiry.HonourLateAcceptNode`
    applies ``TIMED_OUT → AGREED`` (or ``DECLINED → INVITED → AGREED``).

    Replicas learn the honour decision via
    :class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyHonourLateAcceptFromLedgerNode`
    in ``AnnounceLogEntryReceivedBT`` (RSH-08-004, ADR-0118).

    Args:
        case_id: The case the Invite was for.
        accepting_actor_id: The participant whose late Accept is honoured.
        invite_id: The answered Invite; the entry's object id.
        embargo_id: The active embargo being accepted.
        published: The answer's claimed time.
    """
    honour_sequence = py_trees.composites.Sequence(
        name="HonourLateAccept",
        memory=False,
        children=[
            create_commit_log_entry_tree(
                case_id=case_id,
                object_id=invite_id or case_id,
                event_type=HONOUR_LATE_ACCEPT_EVENT_TYPE,
                payload_snapshot=honour_late_accept_payload_snapshot(
                    case_id=case_id,
                    accepting_actor_id=accepting_actor_id,
                    invite_id=invite_id,
                    embargo_id=embargo_id,
                    published=published,
                ),
            ),
            HonourLateAcceptNode(
                case_id=case_id,
                actor_id=accepting_actor_id,
                embargo_id=embargo_id,
            ),
        ],
    )
    return create_case_manager_gated_tree(
        name="HonourLateAcceptBT",
        case_id=case_id,
        children=[honour_sequence],
        body_name="HonourLateAcceptBody",
    )


def create_noop_ledger_entry_tree(
    *,
    case_id: str,
    invite_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    published: str,
) -> py_trees.behaviour.Behaviour:
    """Build the CASE_MANAGER-gated no-op acknowledgement tree (EMB-17-004).

    Commits :data:`~vultron.core.models.rsvp_deadline.INVITE_EXPIRED_NOOP_EVENT_TYPE`
    so replicas can replay the acknowledgement without writing a commit from
    a non-manager store (BT-17-001, RSH-08-004, ADR-0118).

    Args:
        case_id: The case the Invite was for.
        invite_id: The late Invite; the entry's object id.
        embargo_id: The embargo the Invite proposed.
        accepting_actor_id: The actor whose late Accept is acknowledged.
        published: The answer's claimed time.
    """
    commit_tree = create_commit_log_entry_tree(
        case_id=case_id,
        object_id=invite_id or case_id,
        event_type=INVITE_EXPIRED_NOOP_EVENT_TYPE,
        payload_snapshot={
            "type": INVITE_EXPIRED_NOOP_SNAPSHOT_TYPE,
            "actor": accepting_actor_id,
            "context": case_id,
            "published": published,
            "object": {
                "type": "Invite",
                "id": invite_id or case_id,
                "object": {"type": "EmbargoEvent", "id": embargo_id},
            },
        },
    )
    return create_case_manager_gated_tree(
        name="CommitNoopLedgerEntryBT",
        case_id=case_id,
        children=[commit_tree],
        body_name="CommitNoopLedgerEntry",
    )


def create_reinvite_stale_accepter_tree(
    *,
    case_id: str,
    embargo_id: str,
    invitee_id: str,
    actor_config: "ActorConfig | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Build the CASE_MANAGER-gated EMB-17-003 re-invite tree.

    The gate is the role guard; the node commits the re-invite as a canonical
    entry before it queues it (CLP-10-006, BT-17-001) and then applies PEC
    ``INVITE`` to the invitee, recording the fresh deadline the Invite carries
    (CM-28-013).  Replicas learn both from the entry.

    Args:
        case_id: The case the late Accept was for.
        embargo_id: The case's *current* embargo, which the re-invite carries.
        invitee_id: The accepting participant being asked again.
        actor_config: The manager's configuration; sets the RSVP window.
    """
    return create_case_manager_gated_tree(
        name="ReinviteStaleAccepterBT",
        case_id=case_id,
        children=[
            ReinviteStaleAccepterNode(
                case_id=case_id,
                embargo_id=embargo_id,
                invitee_id=invitee_id,
                actor_config=actor_config,
            )
        ],
        body_name="ReinviteStaleAccepter",
    )


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "NEEDS_APPLY_KEY",
    "create_honour_late_accept_tree",
    "create_invite_expiry_tree",
    "create_noop_ledger_entry_tree",
    "create_reinvite_stale_accepter_tree",
    "expiry_payload_snapshot",
    "honour_late_accept_payload_snapshot",
]
