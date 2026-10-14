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
  An any-of selector ends with :class:`SenderHoldsNoneOfNode`, so a refused
  sender's reason names every kind the side accepts.
- Otherwise the guard dispatches on the receiver's side::

      SenderRuleGuard (Sequence)
      ├── AtCaseManager (Selector): Inverter(CheckIsCaseManager), <manager kinds>
      └── AtParticipant (Selector): CheckIsCaseManager, <participant kinds>

  Each arm passes on the other side, and on its own side fails on its own
  kinds' failure, so the refusal reason is the failing kind's (BT-13-001).

Each kind's node reads the records the context names.  ``NAMED_ACTOR`` is
one kind whatever the request (HP-01-009): the context's ``request`` names the
record holding it, and the factory picks the small check for that record, all
on one addressee base (``SenderIsRequestAddresseeNode``).  ``AUTHOR`` reads
the changed object the context names.

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
    SenderHoldsNoneOfNode,
    SenderIsActiveParticipantNode,
    SenderIsCaseManagerNode,
    SenderIsCaseOwnerNode,
    SenderIsInviteeNode,
    SenderIsNoteAuthorNode,
    SenderIsOfferAddresseeNode,
    SenderIsOwnershipOffererNode,
    SenderIsOwnershipTransfereeNode,
    SenderIsProposalAddresseeNode,
    SenderIsRequestAddresseeNode,
    SenderRule,
    in_declaration_order,
)
from vultron.errors import VultronWiringError

__all__ = [
    "AddresseeRequest",
    "CaseProposalRequest",
    "OwnershipOfferRequest",
    "ReportOfferRequest",
    "SenderCheckContext",
    "compose_sender_guard",
]


@dataclass(frozen=True)
class CaseProposalRequest:
    """The request is a CaseProposal, recorded on the report case link.

    Attributes:
        report_id: The report the proposal was for (CP-06-005).
    """

    report_id: str


@dataclass(frozen=True)
class ReportOfferRequest:
    """The request is an ``Offer(VulnerabilityReport)``, recorded on this
    store's offer record.

    Attributes:
        offer_id: The Offer the reply names; ``None`` when it names none,
            which refuses (RMB-08-004).
    """

    offer_id: str | None


@dataclass(frozen=True)
class OwnershipOfferRequest:
    """The request is an ownership-transfer Offer, recorded in the case
    ledger by the CASE_MANAGER of :attr:`SenderCheckContext.case_id`.

    A ``NAMED_ACTOR`` sender must be its transferee (CM-21-011); a
    ``CASE_OWNER`` sender must be the Case Owner that made it (CM-21-015).

    Attributes:
        offer_id: The Offer the reply names; ``None`` when it names none,
            which refuses.
    """

    offer_id: str | None


#: The record that holds the request a ``NAMED_ACTOR`` sender answers.
AddresseeRequest = (
    CaseProposalRequest | ReportOfferRequest | OwnershipOfferRequest
)


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
        case_manager_required: A ``CASE_MANAGER`` sender is refused, rather
            than passed through, when this store holds no case or the case
            names no CASE_MANAGER.
        request: The record holding the request a ``NAMED_ACTOR`` sender
            answers; it picks the addressee check (HP-01-009).  An
            :class:`OwnershipOfferRequest` also makes a ``CASE_OWNER`` sender
            the Case Owner that made the Offer.
        authored_object_id: The object an ``AUTHOR`` sender must have
            written: the note being removed (CM-30-001).
    """

    sender_id: str
    case_id: str | None = None
    invite_id: str | None = None
    invite_is_case_join: bool = False
    case_manager_anchored: bool = False
    case_manager_required: bool = False
    request: AddresseeRequest | None = None
    authored_object_id: str | None = None


def _addressee_node(
    ctx: SenderCheckContext,
) -> SenderIsRequestAddresseeNode:
    """The ``NAMED_ACTOR`` check for the record *ctx* names (HP-01-009)."""
    request = ctx.request
    if isinstance(request, CaseProposalRequest):
        return SenderIsProposalAddresseeNode(
            report_id=request.report_id, sender_actor_id=ctx.sender_id
        )
    if isinstance(request, ReportOfferRequest):
        return SenderIsOfferAddresseeNode(
            offer_id=request.offer_id, sender_actor_id=ctx.sender_id
        )
    if isinstance(request, OwnershipOfferRequest):
        return SenderIsOwnershipTransfereeNode(
            case_id=_case_of(ctx, "an ownership-transfer Offer"),
            offer_id=request.offer_id,
            sender_actor_id=ctx.sender_id,
        )
    raise VultronWiringError(
        "compose_sender_guard: a NAMED_ACTOR kind needs the record holding"
        " its request in SenderCheckContext.request (HP-01-009)"
    )


def _case_of(ctx: SenderCheckContext, what: str) -> str:
    """The context's case, which a check against *what* needs."""
    if ctx.case_id is None:
        raise VultronWiringError(
            f"compose_sender_guard: checking a sender against {what} needs"
            " SenderCheckContext.case_id (HP-01-008)"
        )
    return ctx.case_id


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
            case_id=ctx.case_id,
            anchored=ctx.case_manager_anchored,
            required=ctx.case_manager_required,
        )
    if kind is SenderEntitlementKind.CASE_OWNER:
        if isinstance(ctx.request, OwnershipOfferRequest):
            return SenderIsOwnershipOffererNode(
                case_id=_case_of(ctx, "an ownership-transfer Offer"),
                offer_id=ctx.request.offer_id,
                sender_actor_id=ctx.sender_id,
            )
        return SenderIsCaseOwnerNode(
            sender_actor_id=ctx.sender_id, case_id=ctx.case_id
        )
    if kind is SenderEntitlementKind.NAMED_ACTOR:
        return _addressee_node(ctx)
    if kind is SenderEntitlementKind.AUTHOR:
        if ctx.authored_object_id is None:
            raise VultronWiringError(
                "compose_sender_guard: an AUTHOR kind needs the changed"
                " object's id in SenderCheckContext.authored_object_id"
                " (HP-01-009)"
            )
        return SenderIsNoteAuthorNode(
            note_id=ctx.authored_object_id,
            sender_actor_id=ctx.sender_id,
            case_id=_case_of(ctx, "the author of an object"),
        )
    if kind is SenderEntitlementKind.INVITEE:
        if ctx.invite_id is None:
            raise VultronWiringError(
                "compose_sender_guard: an INVITEE kind needs the recorded"
                " Invite's id in SenderCheckContext.invite_id (HP-01-008)"
            )
        return SenderIsInviteeNode(
            invite_id=ctx.invite_id,
            sender_actor_id=ctx.sender_id,
            case_id=ctx.case_id if ctx.invite_is_case_join else None,
        )
    # ANY_ACTOR composes no node (see _any_of), so no kind reaches here.
    raise VultronWiringError(
        f"compose_sender_guard: {kind.name} has no condition node"
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
    nodes = [_kind_node(kind, ctx) for kind in in_declaration_order(kinds)]
    if len(nodes) == 1:
        return nodes[0]
    # The last arm fails naming every kind, so the refusal reason is the
    # side's whole rule rather than the last kind tried (BT-13-001).
    return py_trees.composites.Selector(
        name="AnyOfSenderKinds",
        memory=False,
        children=[*nodes, SenderHoldsNoneOfNode(kinds)],
    )


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
        VultronWiringError: The context lacks a record a kind needs: an
            ``INVITEE`` kind without ``invite_id``, a ``NAMED_ACTOR`` kind
            without ``request``, an ``AUTHOR`` kind without
            ``authored_object_id``, or a case-scoped check without
            ``case_id``.
    """
    if ctx.case_id is None:
        return _any_of(
            rule.outside_case,
            ctx,
            "a receiver that holds no case for it (the activity names no"
            " case this store holds)",
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
