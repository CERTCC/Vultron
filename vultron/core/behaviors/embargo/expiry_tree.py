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

The expiry is a clock decision of the Invite Accept tree (CLP-10-025): the
received-tree factory runs it after the door guards and before the
precondition guards, behind its CASE_MANAGER gate.  It uses the canonical
guard → commit → effect pattern (CLP-10-006, BT-06-006)::

    EvaluateInviteExpiry (Sequence; gated by the factory)
    ├─ EvaluateInviteExpiryNode        # READ-ONLY: assess deadline, no writes
    └─ CommitAndApplyExpiryIfDue (Selector)
       ├─ Inverter(InviteExpiryNeedsApplyNode)   # nothing to commit
       └─ CommitAndApplyInviteExpiryNode
          # commit INVITE_EXPIRED_SEMANTIC_TYPE, then Update(EmbargoConsent)
          # carrying the TIMED_OUT row; only then write INVITED → TIMED_OUT

A failed commit leaves the invitee unchanged: the row is written only once
both entries have committed (CLP-07-013, ADR-0124).

A store that is not the CASE_MANAGER runs nothing and leaves ``result_out``
unset; the Accept tree's late-Accept arms and its expiry guard read
``IS_EXPIRED_KEY`` as False, and the Accept's own effects are gated on the
CASE_MANAGER too (BT-17-001, HP-01-005).
The entry's replica apply node is
:class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyInviteExpiryFromLedgerNode`.

A late Accept is then answered by one of three CASE_MANAGER diversions of the
Accept tree (:func:`late_accept_diversions`, EMB-17, CLP-10-026), each
following commit → effect::

    HonourLateAccept (DiversionStage)
    ├─ LateAcceptHonour: Inverter(InviteNotExpired), LateAcceptRouteIs(HONOUR)
    └─ CommitAndApplyHonourLateAcceptNode → backfill → stub re-issue
    ReinviteLateAccepter (DiversionStage)
    ├─ LateAcceptReinvite: …, LateAcceptRouteIs(REINVITE)
    └─ ReinviteLateAccepterNode  # stamp → build → outbox → commit → PEC INVITE
    AcknowledgeLateAccept (DiversionStage)
    ├─ LateAcceptAcknowledge: …, LateAcceptRouteIs(ACKNOWLEDGE),
    │    LateAcceptAcknowledgeable
    └─ CommitLateAcceptAcknowledgementNode   # the CASE_MANAGER's Ignore

Replicas replay the re-invite through
:class:`~vultron.core.behaviors.embargo.nodes.relay_effect.ApplyEmbargoReinviteFromLedgerNode`.
"""

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import py_trees

from vultron.core.behaviors.act_transaction import ActTransaction
from vultron.core.behaviors.case.nodes.diversion_stage import Diversion
from vultron.core.behaviors.embargo.admission_backfill_tree import (
    embargo_admission_backfill_nodes,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    IS_EXPIRED_KEY,
    NEEDS_APPLY_KEY,
    EvaluateInviteExpiryNode,
    InviteExpiryNeedsApplyNode,
    InviteNotExpiredNode,
)
from vultron.core.behaviors.embargo.nodes.expiry_commit import (
    CommitAndApplyHonourLateAcceptNode,
    CommitAndApplyInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.late_accept import (
    CommitLateAcceptAcknowledgementNode,
    LateAcceptAcknowledgeableNode,
    LateAcceptRoute,
    LateAcceptRouteIsNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteLateAccepterNode,
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
    (CM-23-014) and the overdue-invitation sweep (CM-28-015) have no answer
    to take a time from, so they pass the CASE_MANAGER's own.

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
    late-Accept evaluation (:func:`invite_expiry_decision`), the
    owner-close settle step (CM-23-014) and the overdue-invitation sweep
    (CM-28-015), which both reach it through
    :class:`~vultron.core.behaviors.embargo.nodes.invitation_expiry.ExpireInvitationsNode`.
    The caller decides *that* the invitation has expired; this node commits
    the expired-invitation entry, then the CASE_MANAGER's
    ``Update(EmbargoConsent)`` carrying the row, and only then writes it,
    so a failed commit leaves the invitee unchanged
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


def create_commit_and_honour_late_accept_tree(
    *,
    case_id: str,
    accepting_actor_id: str,
    invite_id: str,
    embargo_id: str,
    published: str,
) -> py_trees.behaviour.Behaviour:
    """Commit an honoured late Accept and its ``AGREED`` row, then apply it.

    The commit → effect half of the EMB-17-001 honour: the node commits the
    :data:`~vultron.core.models.rsvp_deadline.HONOUR_LATE_ACCEPT_SEMANTIC_TYPE`
    entry, then the CASE_MANAGER's ``Update(EmbargoConsent)`` carrying the
    accepter's row, and only then writes ``TIMED_OUT → AGREED`` or
    ``DECLINED → AGREED`` (CLP-10-006, ADR-0124).  It is not gated: the honour
    diversion of :func:`late_accept_diversions` places it behind the
    CASE_MANAGER gate (BT-17-001, CLP-10-026).

    Args:
        case_id: The case the Invite was for.
        accepting_actor_id: The participant whose late Accept is honoured.
        invite_id: The answered Invite; the entry's object id.
        embargo_id: The active embargo being accepted.
        published: The answer's claimed time.
    """
    return CommitAndApplyHonourLateAcceptNode(
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
        name="CommitAndApplyHonourLateAccept",
    )


def invite_expiry_decision(
    *,
    case_id: str,
    invitee_id: str,
    invite_id: str,
    embargo_id: str,
    published: str,
    now: datetime,
    result_out: dict[str, Any],
) -> py_trees.behaviour.Behaviour:
    """The CASE_MANAGER's lazy expiry of one invitee's Invite, a clock decision.

    Passed to
    :func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
    as ``clock_decisions`` by the Invite Accept tree
    (:func:`~vultron.core.behaviors.embargo.answer_trees.accept_invite_to_embargo_tree`),
    which runs it after the door guards and before the precondition guards,
    behind the factory's CASE_MANAGER gate (CLP-10-025, CM-28-014,
    BT-17-001).  It is not gated here.

    The decision follows the guard → commit → effect pattern (CLP-10-006):
    :class:`~vultron.core.behaviors.embargo.nodes.expiry.EvaluateInviteExpiryNode`
    reads the deadline **without writing**, and
    :class:`~vultron.core.behaviors.embargo.nodes.expiry_commit.CommitAndApplyInviteExpiryNode`
    commits the expiry and the invitee's ``TIMED_OUT`` row before it writes
    the row.  A failed commit therefore leaves the invitee unchanged, and the
    stage logs it and goes on.

    The deadline is compared against *now*, the CASE_MANAGER's clock; the
    Accept only names the invitee and the embargo, so its claimed time is
    never the evidence.  The entry carries that claimed time as received
    (*published*, CLP-15-003), which decides nothing.

    Args:
        case_id: The case the Invite was for.
        invitee_id: The participant answering.
        invite_id: The answered Invite; the entry's object id.
        embargo_id: The embargo the Invite proposed.
        published: The answer's claimed time (see :func:`expiry_payload_snapshot`).
        now: The instant the deadline is compared against.
        result_out: Receives ``IS_EXPIRED_KEY`` and ``NEEDS_APPLY_KEY``
            from :class:`EvaluateInviteExpiryNode`; left unset on a store
            that is not the CASE_MANAGER, whose gate skips the decision.
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
    return py_trees.composites.Sequence(
        name="EvaluateInviteExpiry",
        memory=False,
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
    )


#: The name of the late-Accept diversion that takes each route.
LATE_ACCEPT_DIVERSIONS: Mapping[LateAcceptRoute, str] = MappingProxyType(
    {
        LateAcceptRoute.HONOUR: "HonourLateAccept",
        LateAcceptRoute.REINVITE: "ReinviteLateAccepter",
        LateAcceptRoute.ACKNOWLEDGE: "AcknowledgeLateAccept",
    }
)


def _late_accept_condition(
    *,
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    route: LateAcceptRoute,
    result_out: dict[str, Any],
) -> py_trees.behaviour.Behaviour:
    """The Invite expired, and its late Accept takes the *route* arm.

    The acknowledgement arm also needs a delivery it can answer
    (:class:`LateAcceptAcknowledgeableNode`): a resend with no received body
    and no acknowledgement recorded falls through to the late-Accept guard,
    which refuses it (CLP-10-026).
    """
    children: list[py_trees.behaviour.Behaviour] = [
        py_trees.decorators.Inverter(
            name="InviteExpired",
            child=InviteNotExpiredNode(
                result_out=result_out,
                invitee_id=accepting_actor_id,
                case_id=case_id,
            ),
        ),
        LateAcceptRouteIsNode(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=accepting_actor_id,
            route=route,
        ),
    ]
    if route is LateAcceptRoute.ACKNOWLEDGE:
        children.append(LateAcceptAcknowledgeableNode(case_id=case_id))
    return py_trees.composites.Sequence(
        name=f"LateAccept{route.value.title()}",
        memory=False,
        children=children,
    )


def late_accept_diversions(
    *,
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    invite_id: str,
    published: str,
    answers: str | None,
    result_out: dict[str, Any],
    actor_config: "ActorConfig | None" = None,
) -> list[Diversion]:
    """The CASE_MANAGER's three answers to a late embargo Accept (EMB-17).

    The Invite Accept tree passes them among its precondition guards, after
    its repeat guard and P/X/A refusal and before the guard that keeps a late
    Accept from being recorded as an answer.  Each is a ``CASE_MANAGER``
    diversion (CLP-10-026) whose condition is the Invite expiry's finding
    (*result_out*, written by :func:`invite_expiry_decision`) and the arm
    :class:`~vultron.core.behaviors.embargo.nodes.late_accept.LateAcceptRouteIsNode`
    reads from the case; the three conditions are exclusive, so one answer
    runs at most, and the late Accept itself is never committed.

    - **Honour** (EMB-17-002, EMB-17-009): commit the honour entry and the
      CASE_MANAGER's ``Update(EmbargoConsent)`` carrying the accepter's
      ``AGREED`` row, and only then write the row (CLP-10-006, ADR-0124);
      then send what the embargo gate withheld from it and re-issue stale
      stub Invites (CM-10-006, CM-11-016).  Replicas copy the row from its
      own entry and recognise the honour entry through
      :class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyHonourLateAcceptFromLedgerNode`
      (RSH-08-004, ADR-0118).
    - **Re-invite** (EMB-17-003, EMB-17-011): invite the accepter to the
      embargo in force; the node stamps a fresh deadline, queues the Invite,
      commits it once queued and applies PEC ``INVITE`` (ADR-0119,
      CM-28-013).
    - **Acknowledge** (EMB-17-004, EMB-17-010): commit the CASE_MANAGER's
      ``Ignore`` of the late Accept and change no consent row.

    Args:
        case_id: The case the Invite was for.
        embargo_id: The embargo the late Accept names.
        accepting_actor_id: The late accepter.
        invite_id: The answered Invite; the honour entry's object id.
        published: The Accept's claimed time, carried on the honour entry.
        answers: The late Accept's id; the re-invite's id derives from it.
        result_out: The Invite expiry decision's findings.
        actor_config: The CASE_MANAGER's configuration (RSVP window, stub
            re-issue).
    """

    def condition(route: LateAcceptRoute) -> py_trees.behaviour.Behaviour:
        return _late_accept_condition(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=accepting_actor_id,
            route=route,
            result_out=result_out,
        )

    honour = Diversion(
        name=LATE_ACCEPT_DIVERSIONS[LateAcceptRoute.HONOUR],
        condition=condition(LateAcceptRoute.HONOUR),
        # The honour, the backfill and the stub re-issue are one act
        # (CLP-07-015, ADR-0146).
        effects=(
            ActTransaction(
                name="HonourLateAcceptAsOneAct",
                children=[
                    create_commit_and_honour_late_accept_tree(
                        case_id=case_id,
                        accepting_actor_id=accepting_actor_id,
                        invite_id=invite_id,
                        embargo_id=embargo_id,
                        published=published,
                    ),
                    *embargo_admission_backfill_nodes(case_id, actor_config),
                ],
            ),
        ),
    )
    reinvite = Diversion(
        name=LATE_ACCEPT_DIVERSIONS[LateAcceptRoute.REINVITE],
        condition=condition(LateAcceptRoute.REINVITE),
        effects=(
            ReinviteLateAccepterNode(
                case_id=case_id,
                invitee_id=accepting_actor_id,
                actor_config=actor_config,
                answers=answers,
            ),
        ),
    )
    acknowledge = Diversion(
        name=LATE_ACCEPT_DIVERSIONS[LateAcceptRoute.ACKNOWLEDGE],
        condition=condition(LateAcceptRoute.ACKNOWLEDGE),
        effects=(
            CommitLateAcceptAcknowledgementNode(
                case_id=case_id, name="CommitLateAcceptAcknowledgement"
            ),
        ),
    )
    return [honour, reinvite, acknowledge]


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "LATE_ACCEPT_DIVERSIONS",
    "NEEDS_APPLY_KEY",
    "create_commit_and_honour_late_accept_tree",
    "create_commit_and_record_expiry_tree",
    "expiry_payload_snapshot",
    "honour_late_accept_payload_snapshot",
    "invite_expiry_decision",
    "late_accept_diversions",
]
