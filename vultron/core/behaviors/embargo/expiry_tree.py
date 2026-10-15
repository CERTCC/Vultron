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
       └─ CommitAndApplyInviteExpiryNode
          # commit INVITE_EXPIRED_EVENT_TYPE, then Update(EmbargoConsent)
          # carrying the TIMED_OUT row; only then write INVITED → TIMED_OUT

A failed commit leaves the invitee unchanged: the row is written only once
both entries have committed (CLP-07-013, ADR-0124).

A store that is not the CASE_MANAGER runs nothing and leaves ``result_out``
unset; the caller reads ``IS_EXPIRED_KEY`` as False and proceeds to the
normal Accept tree, which also gates on CASE_MANAGER (BT-17-001, HP-01-005).
The entry's replica apply node is
:class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyInviteExpiryFromLedgerNode`.

The honour-late-accept tree (EMB-17-001) similarly follows guard → commit →
effect::

    HonourLateAcceptBT (CASE_MANAGER-gated Sequence)
    └─ CommitAndApplyHonourLateAcceptNode
       # commit HONOUR_LATE_ACCEPT_EVENT_TYPE, then Update(EmbargoConsent)
       # carrying the AGREED row; only then write TIMED_OUT/DECLINED → AGREED

The re-invite of a stale accepter (EMB-17-003) is a CASE_MANAGER-gated commit →
effect node of the relay's frame::

    ReinviteStaleAccepterBT (CASE_MANAGER-gated)
    └─ ReinviteStaleAccepterNode     # stamp → build → outbox → commit → PEC INVITE

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
    InviteExpiryNeedsApplyNode,
)
from vultron.core.behaviors.embargo.nodes.expiry_commit import (
    CommitAndApplyHonourLateAcceptNode,
    CommitAndApplyInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.late_accept import (
    CommitLateAcceptAcknowledgementNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteStaleAccepterNode,
)
from vultron.core.models.rsvp_deadline import (
    HONOUR_LATE_ACCEPT_SNAPSHOT_TYPE,
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
    invite_id: str | None,
    embargo_id: str,
    published: str,
) -> dict[str, Any]:
    """The CM-28-009 expiry entry's snapshot, attributed to the expired invitee.

    *published* is the invitee's own claimed time when it answered late — not
    the CASE_MANAGER's clock: mixing the two inside one actor's claimed stream
    is what CLP-15-003 reads as a regression.  The owner-close settle step
    (CM-23-014) has no answer to take a time from, so it passes its own.

    The Invite carries no ``id`` when *invite_id* is ``None`` or empty: a
    blank id is not an id (CS-08-002), and the replica apply node reads only
    the invitee and the embargo.
    """
    invite: dict[str, Any] = {"type": "Invite"}
    if invite_id:
        invite["id"] = invite_id
    invite["object"] = {"type": "EmbargoEvent", "id": embargo_id}
    return {
        "type": INVITE_EXPIRED_SNAPSHOT_TYPE,
        "actor": invitee_id,
        "context": case_id,
        "published": published,
        "object": invite,
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


def create_commit_and_record_expiry_tree(
    *,
    case_id: str,
    invitee_id: str,
    invite_id: str | None,
    embargo_id: str,
    published: str,
) -> py_trees.behaviour.Behaviour:
    """Commit one expired invitation and its ``TIMED_OUT`` row, then apply it.

    The commit → effect half of the CM-28-009 expiry, shared by the lazy
    late-Accept evaluation (:func:`create_invite_expiry_tree`) and the
    owner-close settle step (CM-23-014), and the one expiry path a sweep of
    overdue invitations reuses.  The caller decides *that* the invitation
    has expired; this node commits the expired-invitation entry, then the
    CASE_MANAGER's ``Update(EmbargoConsent)`` carrying the row, and only
    then writes it, so a failed commit leaves the invitee unchanged
    (CLP-07-013, ADR-0124).  It is not gated: the caller places it behind
    the CASE_MANAGER role gate (CM-28-014, BT-17-001).

    Args:
        case_id: The case the Invite was for.
        invitee_id: The participant whose invitation expires.
        invite_id: The expired Invite; the entry's object id.  ``None`` when
            the caller cannot name it, in which case the entry's object is
            the case and the snapshot's Invite carries no ``id``.
        embargo_id: The embargo the Invite proposed.
        published: The snapshot's claimed time (see
            :func:`expiry_payload_snapshot`).
    """
    return CommitAndApplyInviteExpiryNode(
        case_id=case_id,
        invitee_id=invitee_id,
        embargo_id=embargo_id,
        act_object_id=invite_id or case_id,
        act_snapshot=expiry_payload_snapshot(
            case_id=case_id,
            invitee_id=invitee_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            published=published,
        ),
        name="CommitAndApplyExpiry",
    )


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
    reads the deadline **without writing**, and
    :class:`~vultron.core.behaviors.embargo.nodes.expiry_commit.CommitAndApplyInviteExpiryNode`
    commits the expiry and the invitee's ``TIMED_OUT`` row before it writes
    the row.  A failed commit therefore leaves the invitee unchanged.

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
    commit_and_apply = create_commit_and_record_expiry_tree(
        case_id=case_id,
        invitee_id=invitee_id,
        invite_id=invite_id,
        embargo_id=embargo_id,
        published=published,
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
    :class:`~vultron.core.behaviors.embargo.nodes.expiry_commit.CommitAndApplyHonourLateAcceptNode`
    commits the :data:`HONOUR_LATE_ACCEPT_EVENT_TYPE` entry and the
    participant's ``AGREED`` row, and only then writes
    ``TIMED_OUT → AGREED`` or ``DECLINED → AGREED`` (ADR-0124).

    Replicas copy the row from its ``Update(EmbargoConsent)`` entry; the
    honour entry itself is recognised by
    :class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyHonourLateAcceptFromLedgerNode`
    in ``AnnounceLogEntryReceivedBT`` (RSH-08-004, ADR-0118).

    Args:
        case_id: The case the Invite was for.
        accepting_actor_id: The participant whose late Accept is honoured.
        invite_id: The answered Invite; the entry's object id.
        embargo_id: The active embargo being accepted.
        published: The answer's claimed time.
    """
    honour = CommitAndApplyHonourLateAcceptNode(
        case_id=case_id,
        invitee_id=accepting_actor_id,
        embargo_id=embargo_id,
        act_object_id=invite_id or case_id,
        act_snapshot=honour_late_accept_payload_snapshot(
            case_id=case_id,
            accepting_actor_id=accepting_actor_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            published=published,
        ),
        name="HonourLateAccept",
    )
    return create_case_manager_gated_tree(
        name="HonourLateAcceptBT",
        case_id=case_id,
        children=[honour],
        body_name="HonourLateAcceptBody",
    )


def create_noop_ledger_entry_tree(
    *,
    case_id: str,
) -> py_trees.behaviour.Behaviour:
    """Build the CASE_MANAGER-gated no-op acknowledgement tree (EMB-17-004).

    Commits :data:`~vultron.core.models.rsvp_deadline.INVITE_EXPIRED_NOOP_EVENT_TYPE`
    with the CASE_MANAGER's factory-built ``Ignore`` of the late ``Accept``
    as its snapshot (CLP-07-013, VM-08-003), so replicas can replay the
    acknowledgement without writing a commit from a non-manager store
    (BT-17-001, RSH-08-004, ADR-0118).  The late Accept is read from
    ``/activity``; the bridge needs the trigger-activity factory and the
    wire-render port.

    Args:
        case_id: The case the Invite was for.
    """
    return create_case_manager_gated_tree(
        name="CommitNoopLedgerEntryBT",
        case_id=case_id,
        children=[
            CommitLateAcceptAcknowledgementNode(
                case_id=case_id, name="CommitLateAcceptAcknowledgement"
            )
        ],
        body_name="CommitNoopLedgerEntry",
    )


def create_reinvite_stale_accepter_tree(
    *,
    case_id: str,
    embargo_id: str,
    invitee_id: str,
    actor_config: "ActorConfig | None" = None,
    answers: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Build the CASE_MANAGER-gated EMB-17-003 re-invite tree.

    The gate is the role guard; the node queues the re-invite, commits it as
    a canonical entry once queued (ADR-0119, BT-17-001) and then applies PEC
    ``INVITE`` to the invitee, recording the fresh deadline the Invite carries
    (CM-28-013).  Replicas learn both from the entry.

    Args:
        case_id: The case the late Accept was for.
        embargo_id: The case's *current* embargo, which the re-invite carries.
        invitee_id: The accepting participant being asked again.
        actor_config: The manager's configuration; sets the RSVP window.
        answers: The late Accept's id; the re-invite's id is derived from it.
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
                answers=answers,
            )
        ],
        body_name="ReinviteStaleAccepter",
    )


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "NEEDS_APPLY_KEY",
    "create_commit_and_record_expiry_tree",
    "create_honour_late_accept_tree",
    "create_invite_expiry_tree",
    "create_noop_ledger_entry_tree",
    "create_reinvite_stale_accepter_tree",
    "expiry_payload_snapshot",
    "honour_late_accept_payload_snapshot",
]
