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
behind its role gate (CM-28-003, CM-28-016, BT-17-001, ADR-0118).

The expiry is a clock decision of the Invite Accept tree (CLP-10-025): the
received-tree factory runs it after the door guards and before the
precondition guards, behind its CASE_MANAGER gate.  It uses the canonical
guard → commit → effect pattern (CLP-10-006, BT-06-006)::

    EvaluateInviteExpiry (Sequence; gated by the factory)
    ├─ EvaluateInviteExpiryNode        # READ-ONLY: assess deadline, no writes
    └─ CommitAndApplyExpiryIfDue (Selector)
       ├─ Inverter(InviteExpiryNeedsApplyNode)   # nothing to commit
       └─ CommitAndApplyInviteExpiryNode
          # commit the CASE_MANAGER's Update(EmbargoConsent) carrying the
          # TIMED_OUT row; only then write INVITED → TIMED_OUT

A failed commit leaves the invitee unchanged: the row is written only once
its entry has committed (CLP-07-013, ADR-0124).

A store that is not the CASE_MANAGER runs nothing and leaves ``result_out``
unset; the Accept tree's late-Accept arms and its expiry guard read
``IS_EXPIRED_KEY`` as False, and the Accept's own effects are gated on the
CASE_MANAGER too (BT-17-001, HP-01-005).
A replica copies the row from the ``Update`` entry (CM-23-016).

A late Accept is then answered by its compatibility with the case's embargo
(EMB-17-001).  One the case's current embargo still binds is honoured: it is
recorded as an on-time Accept is, its own entry carrying the row it states
(EMB-17-002, ADR-0152).  The other two are CASE_MANAGER diversions of the
Accept tree (:func:`late_accept_diversions`, CLP-10-026); the re-invite
changes the case and follows commit → effect, and the other changes
nothing::

    ReinviteLateAccepter (DiversionStage)
    ├─ LateAcceptReinvite: Inverter(InviteNotExpired), LateAcceptRouteIs(REINVITE)
    └─ ReinviteLateAccepterNode  # stamp → build → outbox → commit → PEC INVITE
    LateAcceptBindsNothing (DiversionStage)
    ├─ LateAcceptUnbound: …, LateAcceptRouteIs(UNBOUND)
    └─ LateAcceptChangesNothingNode   # nothing recorded, nothing sent

The re-invite is a relayed Invite, attributed to the embargo's proposer, and
replicas replay it through the relay slot
(:class:`~vultron.core.behaviors.embargo.nodes.relay_effect.ApplyEmbargoInviteFromLedgerNode`).
"""

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import py_trees

from vultron.core.behaviors.case.nodes.diversion_stage import Diversion
from vultron.core.behaviors.embargo.nodes.expiry import (
    IS_EXPIRED_KEY,
    NEEDS_APPLY_KEY,
    EvaluateInviteExpiryNode,
    InviteExpiryNeedsApplyNode,
    InviteNotExpiredNode,
)
from vultron.core.behaviors.embargo.nodes.expiry_commit import (
    CommitAndApplyInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.late_accept import (
    LateAcceptChangesNothingNode,
    LateAcceptRoute,
    LateAcceptRouteIsNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteLateAccepterNode,
)

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig

# Keep the old alias so existing imports of CONSENT_CHANGED_KEY from this
# module still work.
CONSENT_CHANGED_KEY = NEEDS_APPLY_KEY


def create_commit_and_record_expiry_tree(
    *,
    case_id: str,
    invitee_id: str,
    invite_id: str | None,
    embargo_id: str,
) -> py_trees.behaviour.Behaviour:
    """Commit one expired invitation's ``TIMED_OUT`` row, then apply it.

    The commit → effect half of the CM-28-009 expiry, shared by the lazy
    late-Accept evaluation (:func:`invite_expiry_decision`), the
    owner-close settle step (CM-23-014) and the overdue-invitation sweep
    (CM-28-015), which both reach it through
    :class:`~vultron.core.behaviors.embargo.nodes.invitation_expiry.ExpireInvitationsNode`.
    The caller decides *that* the invitation has expired, the occasion; this
    node commits the CASE_MANAGER's act on it, the factory-built
    ``Update(EmbargoConsent)`` carrying the row, and only then writes it, so
    a failed commit leaves the invitee unchanged (CLP-07-013, ADR-0124).  It
    is not gated: the caller places it behind the CASE_MANAGER role gate
    (CM-28-016, BT-17-001).

    Args:
        case_id: The case the Invite was for.
        invitee_id: The participant whose invitation expires.
        invite_id: The expired Invite, which seeds the ``Update``'s id;
            ``None`` when the caller cannot name it, and the case seeds it.
        embargo_id: The embargo the Invite proposed.
    """
    return CommitAndApplyInviteExpiryNode(
        case_id=case_id,
        invitee_id=invitee_id,
        embargo_id=embargo_id,
        cause_object_id=invite_id or case_id,
        name="CommitAndApplyExpiry",
    )


def invite_expiry_decision(
    *,
    case_id: str,
    invitee_id: str,
    invite_id: str,
    embargo_id: str,
    now: datetime,
    result_out: dict[str, Any],
) -> py_trees.behaviour.Behaviour:
    """The CASE_MANAGER's lazy expiry of one invitee's Invite, a clock decision.

    Passed to
    :func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
    as ``clock_decisions`` by the Invite Accept tree
    (:func:`~vultron.core.behaviors.embargo.answer_trees.accept_invite_to_embargo_tree`),
    which runs it after the door guards and before the precondition guards,
    behind the factory's CASE_MANAGER gate (CLP-10-025, CM-28-016,
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
    never the evidence.

    Args:
        case_id: The case the Invite was for.
        invitee_id: The participant answering.
        invite_id: The answered Invite, which seeds the ``Update``'s id.
        embargo_id: The embargo the Invite proposed.
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


#: The name of the late-Accept diversion that takes each route.  An honoured
#: late Accept is no diversion: it is recorded as an on-time Accept is
#: (EMB-17-002, ADR-0152).
LATE_ACCEPT_DIVERSIONS: Mapping[LateAcceptRoute, str] = MappingProxyType(
    {
        LateAcceptRoute.REINVITE: "ReinviteLateAccepter",
        LateAcceptRoute.UNBOUND: "LateAcceptBindsNothing",
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
    """The Invite expired, and its late Accept takes the *route* arm."""
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
    answers: str | None,
    result_out: dict[str, Any],
    actor_config: "ActorConfig | None" = None,
) -> list[Diversion]:
    """The CASE_MANAGER's two diverted answers to a late embargo Accept (EMB-17).

    The Invite Accept tree passes them among its precondition guards, after
    its repeat guard and P/X/A refusal and before the guard that lets only an
    honoured late Accept be recorded.  Each is a ``CASE_MANAGER`` diversion
    (CLP-10-026) whose condition is the Invite expiry's finding
    (*result_out*, written by :func:`invite_expiry_decision`) and the arm
    :class:`~vultron.core.behaviors.embargo.nodes.late_accept.LateAcceptRouteIsNode`
    reads from the case; the conditions are exclusive, so one answer runs
    at most, and the late Accept itself is not committed.  A late Accept of
    the embargo in force takes neither: it is honoured by being recorded as
    an on-time Accept is (EMB-17-002, ADR-0152).

    - **Re-invite** (EMB-17-003): invite the accepter to the embargo in
      force with a relayed Invite attributed to its proposer; the node stamps
      a fresh deadline, queues the Invite, commits it once queued and applies
      PEC ``INVITE`` (ADR-0119, CM-28-013, ADR-0152).
    - **Bind nothing** (EMB-17-004): the case holds no embargo for the Accept
      to bind, so it changes nothing: no entry, nothing sent, no consent row
      moved (ADR-0152).

    Args:
        case_id: The case the Invite was for.
        embargo_id: The embargo the late Accept names.
        accepting_actor_id: The late accepter.
        answers: The late Accept's id; the re-invite's id derives from it.
        result_out: The Invite expiry decision's findings.
        actor_config: The CASE_MANAGER's configuration (RSVP window).
    """

    def condition(route: LateAcceptRoute) -> py_trees.behaviour.Behaviour:
        return _late_accept_condition(
            case_id=case_id,
            embargo_id=embargo_id,
            accepting_actor_id=accepting_actor_id,
            route=route,
            result_out=result_out,
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
        name=LATE_ACCEPT_DIVERSIONS[LateAcceptRoute.UNBOUND],
        condition=condition(LateAcceptRoute.UNBOUND),
        effects=(
            LateAcceptChangesNothingNode(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
            ),
        ),
    )
    return [reinvite, acknowledge]


def on_time_or_honoured_accept(
    *,
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    result_out: dict[str, Any],
) -> py_trees.behaviour.Behaviour:
    """Guard: the Accept is on time, or a late Accept the case honours.

    The backstop after :func:`late_accept_diversions`: an Accept the Invite
    expiry found late is recorded as an answer only when the accepted embargo
    is the case's current one (EMB-17-002), exactly as an on-time Accept is,
    its entry carrying the row it states (ADR-0152).  Any other late Accept
    was answered by a diversion, and is never recorded (EMB-17-005).
    """
    return py_trees.composites.Selector(
        name="OnTimeOrHonouredAccept",
        memory=False,
        children=[
            InviteNotExpiredNode(
                result_out=result_out,
                invitee_id=accepting_actor_id,
                case_id=case_id,
            ),
            LateAcceptRouteIsNode(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
                route=LateAcceptRoute.HONOUR,
            ),
        ],
    )


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "LATE_ACCEPT_DIVERSIONS",
    "NEEDS_APPLY_KEY",
    "create_commit_and_record_expiry_tree",
    "invite_expiry_decision",
    "late_accept_diversions",
    "on_time_or_honoured_accept",
]
