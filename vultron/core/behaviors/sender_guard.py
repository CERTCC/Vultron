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

"""Compose a sender guard from a declared :class:`SenderRule` (HP-01-008).

The receive-tree factory calls :func:`compose_sender_guard` with the use
case's declared rule and a :class:`SenderCheckContext` naming the records the
kinds' condition nodes read.  The predicates themselves stay in
:mod:`vultron.core.behaviors.sender_entitlement` (HP-01-007); this module only
chooses and arranges them.

Composition:

- An activity that names no case is checked against the rule's
  ``outside_case`` side.
- Otherwise, when the CASE_MANAGER and participant sides name the same kinds,
  the guard is those kinds' any-of selector, whoever receives the activity.
- Otherwise the guard dispatches on the receiver's side::

      SenderRuleGuard (Sequence)
      ├── AtCaseManager (Selector): Inverter(CheckIsCaseManager), <manager kinds>
      └── AtParticipant (Selector): CheckIsCaseManager, <participant kinds>

  Each arm passes on the other side, and on its own side fails on its own
  kinds' failure, so the refusal reason is the failing kind's (BT-13-001).

An empty side composes :class:`NoSenderAdmittedNode`, so an activity that
names no case is refused under a rule with no ``outside_case`` side; ``ANY_ACTOR`` composes
no node, so a rule that admits any actor composes no guard at all.
"""

from dataclasses import dataclass

import py_trees

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.sender_entitlement import (
    NoSenderAdmittedNode,
    SenderEntitlementKind,
    SenderIsActiveParticipantNode,
    SenderIsCaseManagerNode,
    SenderIsCaseOwnerNode,
    SenderIsInviteeNode,
    SenderRule,
)
from vultron.errors import VultronWiringError

__all__ = ["SenderCheckContext", "compose_sender_guard"]


@dataclass(frozen=True)
class SenderCheckContext:
    """What the kinds' condition nodes need to check one received activity.

    Attributes:
        sender_id: The activity's sender.
        case_id: The case the activity names; ``None`` for an activity sent
            before any case exists, which is checked against the rule's
            ``outside_case`` side.
        invite_id: The recorded Invite an ``INVITEE`` sender answers.
        invite_is_case_join: The Invite is a case-join Invite, so the record
            must also be one this CASE_MANAGER issued for ``case_id``
            (CM-11-017).
        case_manager_anchored: A ``CASE_MANAGER`` sender is matched against the
            trust anchor the receiver recorded with the stub Invite when the
            replica names no CASE_MANAGER (PCR-03-004).
    """

    sender_id: str
    case_id: str | None = None
    invite_id: str | None = None
    invite_is_case_join: bool = False
    case_manager_anchored: bool = False


def _kind_node(
    kind: SenderEntitlementKind, ctx: SenderCheckContext
) -> py_trees.behaviour.Behaviour:
    """The condition node that checks *kind* for the activity in *ctx*."""
    if kind is SenderEntitlementKind.ACTIVE_PARTICIPANT:
        return SenderIsActiveParticipantNode(
            status_id="", sender_actor_id=ctx.sender_id, case_id=ctx.case_id
        )
    if kind is SenderEntitlementKind.CASE_MANAGER:
        return SenderIsCaseManagerNode(
            case_id=ctx.case_id, anchored=ctx.case_manager_anchored
        )
    if kind is SenderEntitlementKind.CASE_OWNER:
        return SenderIsCaseOwnerNode(
            sender_actor_id=ctx.sender_id, case_id=ctx.case_id
        )
    if kind is SenderEntitlementKind.INVITEE:
        return SenderIsInviteeNode(
            invite_id=ctx.invite_id,
            sender_actor_id=ctx.sender_id,
            case_id=ctx.case_id if ctx.invite_is_case_join else None,
        )
    # NAMED_ACTOR: its guards read different records (the report case link,
    # the Offer record, the ownership Offer); one addressee guard is #4437's
    # next piece, so its trees still pass their own ``sender_guard``.
    raise VultronWiringError(
        f"compose_sender_guard: no factory guard for {kind.name} yet (#4437);"
        " its tree passes sender_guard and is on the ratchet allow-list"
    )


def _any_of(
    kinds: frozenset[SenderEntitlementKind],
    ctx: SenderCheckContext,
    side: str,
) -> py_trees.behaviour.Behaviour | None:
    """The guard for one side: ``None`` when it admits any actor."""
    if not kinds:
        return NoSenderAdmittedNode(side=side)
    if SenderEntitlementKind.ANY_ACTOR in kinds:
        return None
    nodes = [_kind_node(kind, ctx) for kind in sorted(kinds, key=_order)]
    if len(nodes) == 1:
        return nodes[0]
    return py_trees.composites.Selector(
        name="AnyOfSenderKinds",
        memory=False,
        children=nodes,
    )


def _order(kind: SenderEntitlementKind) -> int:
    """Declaration order of the enum, so composition is deterministic."""
    return list(SenderEntitlementKind).index(kind)


def _or_pass(
    guard: py_trees.behaviour.Behaviour | None, name: str
) -> py_trees.behaviour.Behaviour:
    """*guard*, or a success leaf for a side that admits any actor."""
    if guard is not None:
        return guard
    return py_trees.behaviours.Success(name=f"{name}AnyActor")


def compose_sender_guard(
    rule: SenderRule, ctx: SenderCheckContext
) -> py_trees.behaviour.Behaviour | None:
    """Compose the guard *rule* requires for the activity *ctx* describes.

    Args:
        rule: The use case's declared sender rule.
        ctx: The sender and the records its kinds are checked against.

    Returns:
        The guard, or ``None`` when the receiver's side admits any actor.

    Raises:
        VultronWiringError: The rule names a kind with no factory guard yet
            (``NAMED_ACTOR``).
    """
    if ctx.case_id is None:
        return _any_of(
            rule.outside_case,
            ctx,
            "an actor outside any case (the activity names no case this"
            " store holds)",
        )
    if rule.at_case_manager == rule.at_participant:
        return _any_of(rule.at_case_manager, ctx, "a case actor")
    manager = _or_pass(
        _any_of(rule.at_case_manager, ctx, "the CASE_MANAGER"), "AtCaseManager"
    )
    participant = _or_pass(
        _any_of(
            rule.at_participant,
            ctx,
            "a participant other than the CASE_MANAGER",
        ),
        "AtParticipant",
    )
    return py_trees.composites.Sequence(
        name="SenderRuleGuard",
        memory=False,
        children=[
            py_trees.composites.Selector(
                name="AtCaseManager",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="NotAtCaseManager",
                        child=CheckIsCaseManagerNode(
                            case_id=ctx.case_id, case_may_be_absent=True
                        ),
                    ),
                    manager,
                ],
            ),
            py_trees.composites.Selector(
                name="AtParticipant",
                memory=False,
                children=[
                    CheckIsCaseManagerNode(
                        case_id=ctx.case_id, case_may_be_absent=True
                    ),
                    participant,
                ],
            ),
        ],
    )
