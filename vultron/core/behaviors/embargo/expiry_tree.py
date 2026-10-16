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
       └─ CommitAndApplyExpiry (Sequence)
          ├─ CommitLogEntryBT          # commit INVITE_EXPIRED_EVENT_TYPE entry
          └─ RecordInviteExpiryNode    # EFFECT: apply INVITED → TIMED_OUT

A failed commit leaves the invitee unchanged; ``RecordInviteExpiryNode`` only
runs after a successful commit.

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
    └─ CommitLogEntryBT → HonourLateAcceptNode → backfill → stub re-issue
    ReinviteLateAccepter (DiversionStage)
    ├─ LateAcceptReinvite: …, LateAcceptRouteIs(REINVITE)
    └─ ReinviteLateAccepterNode  # stamp → build → outbox → commit → PEC INVITE
    AcknowledgeLateAccept (DiversionStage)
    ├─ LateAcceptAcknowledge: …, LateAcceptRouteIs(ACKNOWLEDGE)
    └─ CommitLateAcceptAcknowledgementNode   # the CASE_MANAGER's Ignore

Replicas replay the re-invite through
:class:`~vultron.core.behaviors.embargo.nodes.relay_effect.ApplyEmbargoReinviteFromLedgerNode`.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

import py_trees

from vultron.core.behaviors.case.nodes.diversion_stage import Diversion
from vultron.core.behaviors.embargo.admission_backfill_tree import (
    embargo_admission_backfill_nodes,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    IS_EXPIRED_KEY,
    NEEDS_APPLY_KEY,
    EvaluateInviteExpiryNode,
    HonourLateAcceptNode,
    InviteExpiryNeedsApplyNode,
    InviteNotExpiredNode,
    RecordInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.late_accept import (
    CommitLateAcceptAcknowledgementNode,
    LateAcceptRoute,
    LateAcceptRouteIsNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteLateAccepterNode,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.rsvp_deadline import (
    HONOUR_LATE_ACCEPT_EVENT_TYPE,
    HONOUR_LATE_ACCEPT_SNAPSHOT_TYPE,
    INVITE_EXPIRED_EVENT_TYPE,
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
    """Commit one expired-invitation entry, then apply ``INVITED → TIMED_OUT``.

    The commit → effect half of the CM-28-009 expiry, shared by the lazy
    late-Accept evaluation (:func:`invite_expiry_decision`) and the
    owner-close settle step (CM-23-014).  The caller decides *that* the
    invitation has expired; this subtree only records and applies it, so a
    failed commit leaves the invitee unchanged (CLP-10-006).  It is not
    gated: the caller places it behind the CASE_MANAGER role gate
    (CM-28-014, BT-17-001).

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
    return py_trees.composites.Sequence(
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
    reads the deadline **without writing**, the commit node persists the
    ledger entry, and only then
    :class:`~vultron.core.behaviors.embargo.nodes.expiry.RecordInviteExpiryNode`
    applies ``INVITED → TIMED_OUT`` to the invitation's row.  A failed commit
    therefore leaves the invitee unchanged, and the stage logs it and goes on.

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


#: The names of the late-Accept diversions, honour, re-invite, acknowledge.
LATE_ACCEPT_DIVERSIONS: tuple[str, str, str] = (
    "HonourLateAccept",
    "ReinviteLateAccepter",
    "AcknowledgeLateAccept",
)


def _late_accept_condition(
    *,
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    route: LateAcceptRoute,
    result_out: dict[str, Any],
) -> py_trees.behaviour.Behaviour:
    """The Invite expired, and its late Accept takes the *route* arm."""
    return py_trees.composites.Sequence(
        name=f"LateAccept{route.value.title()}",
        memory=False,
        children=[
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
        ],
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

    - **Honour** (EMB-17-002, EMB-17-009): commit the honour entry, then move
      the accepter's row to ``AGREED`` (CLP-10-006), then send what the
      embargo gate withheld from it and re-issue stale stub Invites
      (CM-10-006, CM-11-016).  Replicas replay the entry through
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
        name=LATE_ACCEPT_DIVERSIONS[0],
        condition=condition(LateAcceptRoute.HONOUR),
        effects=(
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
            *embargo_admission_backfill_nodes(case_id, actor_config),
        ),
    )
    reinvite = Diversion(
        name=LATE_ACCEPT_DIVERSIONS[1],
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
        name=LATE_ACCEPT_DIVERSIONS[2],
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
    "create_commit_and_record_expiry_tree",
    "expiry_payload_snapshot",
    "honour_late_accept_payload_snapshot",
    "invite_expiry_decision",
    "late_accept_diversions",
]
