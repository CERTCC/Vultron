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

"""The CASE_MANAGER's stub Invite for the Case Owner's decision to invite.

One subtree, :func:`owner_decided_stub_invite`, composed by both places the
Owner's decision reaches the CASE_MANAGER: the received tree of the Owner's
own ``Invite(<case preview>)[target=<invitee>]`` (CM-17-007), and the
direct-invite trigger of an Owner that holds the CASE_MANAGER role itself
(CM-24-021).  So the two cannot drift apart on the re-invite rule or the
order of the writes.
"""

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.invite_actor_emit import (
    EmitInviteActorToCaseNode,
)
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    CreateInertInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.stub_invite_lifetime import (
    ReinviteAwaitingNode,
)


def owner_decided_stub_invite(
    invitee_id: str,
    case_id: str,
    roles: list[str],
    *,
    owner_id: str | None,
    owner_invite_id: str | None,
    actor_config: ActorConfig | None = None,
    captured: dict | None = None,
) -> py_trees.composites.Selector:
    """Send the invitee the CASE_MANAGER's stub Invite, first or replacement.

    ``Selector(Reinvite, FirstInvite)``, both arms the CASE_MANAGER's:

    - **Reinvite** — the invitee has an inert record that has not answered:
      a fresh stub Invite goes out on that record, with a new deadline,
      naming the stub it supersedes in ``inReplyTo`` (CM-11-015, CM-11-044).
      No new participant is created.
    - **FirstInvite** — no such record: the stub Invite goes out, then the
      inert participant is created and added to the case in the same act
      (CM-11-006, CM-11-023).

    The first arm re-checks the record, and the second is guarded by its
    inverse, so a failed re-invite surfaces as a failure rather than
    falling through to seating a second record.  Each emit commits its
    Invite once it is in the outbox (CM-17-006).

    Args:
        invitee_id: The invited actor, the Owner's Invite's ``target``.
        case_id: The case.
        roles: The roles the Owner named; never empty (CM-11-019): the
            caller has refused an Invite without one.
        owner_id: The Case Owner whose decision this carries out, for
            ``attributedTo`` (CM-24-002); ``None`` when the Owner is the
            CASE_MANAGER and the Invite is its own (CM-24-021).
        owner_invite_id: The Owner's Invite the stub carries out: its
            ``inReplyTo`` on a first Invite (CM-24-020), and the request its
            id derives from, so a retry rebuilds the same stub (OX-06-002).
            ``None`` with ``owner_id``: the trigger mints the id.
        actor_config: The CASE_MANAGER's configuration, for the RSVP window
            (CM-11-014, CM-28-012).
        captured: Optional dict; ``captured["activity"]`` is set to the
            stub Invite sent.
    """

    def _emit(*, replaces_previous_stub: bool) -> EmitInviteActorToCaseNode:
        return EmitInviteActorToCaseNode(
            invitee_id=invitee_id,
            case_id=case_id,
            attributed_to=owner_id,
            roles=roles,
            captured=captured,
            replaces_previous_stub=replaces_previous_stub,
            actor_config=actor_config,
            answers=owner_invite_id,
            name=(
                "EmitReplacementStubInvite"
                if replaces_previous_stub
                else "EmitStubInvite"
            ),
        )

    reinvite = py_trees.composites.Sequence(
        name="Reinvite",
        memory=False,
        children=[
            ReinviteAwaitingNode(
                invitee_id=invitee_id,
                case_id=case_id,
                name="InviteeAwaitsReply",
            ),
            # The record is already on the roster: only the Invite goes out.
            _emit(replaces_previous_stub=True),
        ],
    )
    first_invite = py_trees.composites.Sequence(
        name="FirstInvite",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="InviteeHasNoAwaitingRecord",
                child=ReinviteAwaitingNode(
                    invitee_id=invitee_id,
                    case_id=case_id,
                    name="InviteeAwaitsReplyCheck",
                ),
            ),
            _emit(replaces_previous_stub=False),
            # CM-11-006: the inert participant is recorded as the Invite is
            # sent, with the Invite's roles (ADR-0114).
            CreateInertInviteeParticipantNode(
                invitee_id=invitee_id, case_id=case_id, roles=roles
            ),
        ],
    )
    return py_trees.composites.Selector(
        name="OwnerDecidedStubInvite",
        memory=False,
        children=[reinvite, first_invite],
    )


__all__ = ["owner_decided_stub_invite"]
