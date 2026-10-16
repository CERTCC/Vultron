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
on one addressee base (``SenderIsRequestAddresseeNode``).  ``AUTHOR`` is one
kind whatever the object: the context's ``authored_object`` names it, and the
factory picks the note-author or proposal-author check for it.

An activity that carries a ``CaseLedgerEntry`` has no case at build time: the
entry names it.  Its tree passes a :class:`LedgerActivityContext`, and the
kinds' nodes read the sender and the case from the activity on the blackboard
at run time (SYNC-03-005, SYNC-13-006).  Only the kinds whose nodes can do
that may be declared for it: ``CASE_MANAGER`` and ``LEDGER_PEER``.

An empty side composes :class:`NoSenderAdmittedNode`, so an activity that
names no case is refused under a rule with no ``outside_case`` side; ``ANY_ACTOR`` composes
no node, so a rule that admits any actor composes no guard at all.
"""

from collections.abc import Callable
from dataclasses import dataclass

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.sender_entitlement import (
    NoSenderAdmittedNode,
    SenderClosureNotRecordedNode,
    SenderEntitlementConditionNode,
    SenderEntitlementKind,
    SenderHoldsNoneOfNode,
    SenderIsActiveLedgerParticipantNode,
    SenderIsActiveParticipantNode,
    SenderIsCaseManagerNode,
    SenderIsCaseOwnerNode,
    SenderIsInviteeNode,
    SenderIsNoteAuthorNode,
    SenderIsOfferAddresseeNode,
    SenderIsOfferingCaseOwnerNode,
    SenderIsOwnershipOffererNode,
    SenderIsOwnershipTransfereeNode,
    SenderIsParticipantNode,
    SenderIsProposalAddresseeNode,
    SenderIsProposalAuthorNode,
    SenderIsRequestAddresseeNode,
    SenderRule,
    in_declaration_order,
)
from vultron.errors import VultronWiringError

__all__ = [
    "AddresseeRequest",
    "AuthoredCaseProposal",
    "AuthoredNote",
    "AuthoredObject",
    "CaseProposalRequest",
    "LedgerActivityContext",
    "OwnershipOfferRequest",
    "ReportOfferRequest",
    "SenderCheckContext",
    "SenderContext",
    "closed_sender_guard",
    "compose_sender_guard",
    "embargo_sender_context",
    "sender_guard_refused",
]

#: The composites :func:`compose_sender_guard` builds around the kinds' nodes.
_ANY_OF_NAME = "AnyOfSenderKinds"
_RULE_GUARD_NAME = "SenderRuleGuard"


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
        reply_id: The reply's own id, so the offerer check recognises a
            redelivery of the withdrawal that closed the Offer (HP-01-003).
    """

    offer_id: str | None
    reply_id: str


#: The record that holds the request a ``NAMED_ACTOR`` sender answers.
AddresseeRequest = (
    CaseProposalRequest | ReportOfferRequest | OwnershipOfferRequest
)


@dataclass(frozen=True)
class AuthoredNote:
    """An ``AUTHOR`` sender must have written this note, and still be an
    active participant of the case (CM-30-001).

    Attributes:
        note_id: The note being removed.
    """

    note_id: str


@dataclass(frozen=True)
class AuthoredCaseProposal:
    """An ``AUTHOR`` sender must be this proposal's proposer, as the
    CASE_MANAGER recorded it for the proposal id (CP-05-010).

    Attributes:
        proposal_id: The proposal the ``Create(CaseProposal)`` carries.
    """

    proposal_id: str


#: The object an ``AUTHOR`` sender must have written.
AuthoredObject = AuthoredNote | AuthoredCaseProposal


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
        authored_object: The object an ``AUTHOR`` sender must have written;
            it picks the author check (HP-01-009).
        offered_ownership_id: A new ownership-transfer Offer's own id: a
            ``CASE_OWNER`` sender must hold the role, unless it redelivers
            an Offer the CASE_MANAGER recorded from it (CM-21-019,
            HP-01-003).
    """

    sender_id: str
    case_id: str | None = None
    invite_id: str | None = None
    invite_is_case_join: bool = False
    case_manager_anchored: bool = False
    case_manager_required: bool = False
    request: AddresseeRequest | None = None
    authored_object: AuthoredObject | None = None
    offered_ownership_id: str | None = None


@dataclass(frozen=True)
class LedgerActivityContext:
    """The received activity carries a ``CaseLedgerEntry``, which names the case.

    A ledger activity's tree has no case at build time, so the guard's nodes
    read the sender and the case from the activity on the blackboard when the
    tree runs: ``CASE_MANAGER`` from the announced entry (SYNC-13-006), and
    ``LEDGER_PEER`` from the rejected entry (SYNC-03-005).  The guard is
    composed for the activity's case, never for the rule's ``outside_case``
    side, and the rule must state the same kinds at the CASE_MANAGER and at a
    participant: telling the receiver's side apart needs the case at build
    time.
    """


#: Either kind of context :func:`compose_sender_guard` composes a guard for.
SenderContext = SenderCheckContext | LedgerActivityContext


def embargo_sender_context(
    sender_id: str, case_id: str | None
) -> SenderCheckContext:
    """The context an embargo activity's sender is checked in.

    Embargo state is the case's, so the sender's standing is established
    against the case this store holds: a case it does not hold, or one that
    names no CASE_MANAGER, refuses the sender rather than passing it through
    (Regime 1, ADR-0087).  ``Invite``, ``Remove`` and ``Announce`` of an
    ``EmbargoEvent`` share it (EP-09-003, PCR-03-001, PCR-08).
    """
    return SenderCheckContext(
        sender_id=sender_id, case_id=case_id, case_manager_required=True
    )


def closed_sender_guard(
    case_id: str, sender_id: str
) -> SenderClosureNotRecordedNode:
    """The CM-23-018 check that the case does not record the sender's closure.

    Built here, beside the kinds' guards, so the receive-tree factory never
    names a sender node itself (HP-01-007).  It is not a kind: the factory
    places it just before the sender guard of a tree whose act would close
    its sender (``closing_act``), so a repeat of that act is ``SKIPPED``
    rather than refused by the guard (ID-05-003).
    """
    return SenderClosureNotRecordedNode(
        case_id=case_id, sender_actor_id=sender_id
    )


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


def _author_node(
    ctx: SenderCheckContext,
) -> SenderIsNoteAuthorNode | SenderIsProposalAuthorNode:
    """The ``AUTHOR`` check for the object *ctx* names (HP-01-009)."""
    authored = ctx.authored_object
    if isinstance(authored, AuthoredNote):
        return SenderIsNoteAuthorNode(
            note_id=authored.note_id,
            sender_actor_id=ctx.sender_id,
            case_id=_case_of(ctx, "the author of a note"),
        )
    if isinstance(authored, AuthoredCaseProposal):
        return SenderIsProposalAuthorNode(
            proposal_id=authored.proposal_id, sender_actor_id=ctx.sender_id
        )
    raise VultronWiringError(
        "compose_sender_guard: an AUTHOR kind needs the object its sender"
        " must have written in SenderCheckContext.authored_object"
        " (HP-01-009)"
    )


def _case_of(ctx: SenderCheckContext, what: str) -> str:
    """The context's case, which a check against *what* needs."""
    if ctx.case_id is None:
        raise VultronWiringError(
            f"compose_sender_guard: checking a sender against {what} needs"
            " SenderCheckContext.case_id (HP-01-008)"
        )
    return ctx.case_id


#: The two participant-record kinds: any record on the case, or an active one
#: (CM-10-004).  Each reads only the sender and the case.
_MEMBERSHIP_NODES: dict[
    SenderEntitlementKind,
    type[SenderIsParticipantNode] | type[SenderIsActiveParticipantNode],
] = {
    SenderEntitlementKind.PARTICIPANT: SenderIsParticipantNode,
    SenderEntitlementKind.ACTIVE_PARTICIPANT: SenderIsActiveParticipantNode,
}


def _case_owner_node(ctx: SenderCheckContext) -> py_trees.behaviour.Behaviour:
    """The ``CASE_OWNER`` check for the activity in *ctx*.

    The withdrawal of a recorded ownership-transfer Offer checks the Owner
    that made it (CM-21-015); a new Offer checks the Owner making it
    (CM-21-019); anything else checks the role alone.
    """
    if isinstance(ctx.request, OwnershipOfferRequest):
        return SenderIsOwnershipOffererNode(
            case_id=_case_of(ctx, "an ownership-transfer Offer"),
            offer_id=ctx.request.offer_id,
            sender_actor_id=ctx.sender_id,
            reply_id=ctx.request.reply_id,
        )
    if ctx.offered_ownership_id is not None:
        return SenderIsOfferingCaseOwnerNode(
            case_id=_case_of(ctx, "an ownership-transfer Offer"),
            offer_id=ctx.offered_ownership_id,
            sender_actor_id=ctx.sender_id,
        )
    return SenderIsCaseOwnerNode(
        sender_actor_id=ctx.sender_id, case_id=ctx.case_id
    )


def _kind_node(
    kind: SenderEntitlementKind, ctx: SenderCheckContext
) -> py_trees.behaviour.Behaviour:
    """The condition node that checks *kind* for the activity in *ctx*."""
    if (membership := _MEMBERSHIP_NODES.get(kind)) is not None:
        return membership(sender_actor_id=ctx.sender_id, case_id=ctx.case_id)
    if kind is SenderEntitlementKind.LEDGER_PEER:
        # Reads the sender and the case from the ledger activity on the
        # blackboard (SYNC-03-005).
        return SenderIsActiveLedgerParticipantNode(
            name="SenderIsActiveLedgerParticipant"
        )
    if kind is SenderEntitlementKind.CASE_MANAGER:
        return SenderIsCaseManagerNode(
            case_id=ctx.case_id,
            anchored=ctx.case_manager_anchored,
            required=ctx.case_manager_required,
            sender_actor_id=ctx.sender_id,
        )
    if kind is SenderEntitlementKind.CASE_OWNER:
        return _case_owner_node(ctx)
    if kind is SenderEntitlementKind.NAMED_ACTOR:
        return _addressee_node(ctx)
    if kind is SenderEntitlementKind.AUTHOR:
        return _author_node(ctx)
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
            closure_case_id=ctx.case_id,
        )
    # ANY_ACTOR composes no node (see _any_of), so no kind reaches here.
    raise VultronWiringError(
        f"compose_sender_guard: {kind.name} has no condition node"
    )


def _ledger_kind_node(
    kind: SenderEntitlementKind,
) -> py_trees.behaviour.Behaviour:
    """The condition node that checks *kind* for a ledger activity.

    Each node reads the sender and the case from the activity on the
    blackboard (:class:`LedgerActivityContext`).
    """
    if kind is SenderEntitlementKind.LEDGER_PEER:
        return SenderIsActiveLedgerParticipantNode(
            name="SenderIsActiveLedgerParticipant"
        )
    if kind is SenderEntitlementKind.CASE_MANAGER:
        return SenderIsCaseManagerNode()
    raise VultronWiringError(
        f"compose_sender_guard: {kind.name} cannot be checked against a case"
        " read from a ledger activity at run time; only CASE_MANAGER and"
        " LEDGER_PEER can (HP-01-008)"
    )


def _any_of(
    kinds: frozenset[SenderEntitlementKind],
    node_for: Callable[[SenderEntitlementKind], py_trees.behaviour.Behaviour],
    side: str,
) -> py_trees.behaviour.Behaviour | None:
    """The guard for one side: ``None`` when it admits any actor."""
    if not kinds:
        return NoSenderAdmittedNode(side=side)
    if SenderEntitlementKind.ANY_ACTOR in kinds:
        return None
    nodes = [node_for(kind) for kind in in_declaration_order(kinds)]
    if len(nodes) == 1:
        return nodes[0]
    # The last arm fails naming every kind, so the refusal reason is the
    # side's whole rule rather than the last kind tried (BT-13-001).
    return py_trees.composites.Selector(
        name=_ANY_OF_NAME,
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


def _ledger_guard(rule: SenderRule) -> py_trees.behaviour.Behaviour | None:
    """The guard *rule* requires for a ledger activity's case."""
    if rule.at_case_manager != rule.at_participant:
        raise VultronWiringError(
            "compose_sender_guard: a ledger activity's case is read at run"
            " time, so its rule must state the same kinds at the CASE_MANAGER"
            " and at a participant (HP-01-008)"
        )
    return _any_of(rule.at_case_manager, _ledger_kind_node, "a case actor")


def compose_sender_guard(
    rule: SenderRule, ctx: SenderContext
) -> py_trees.behaviour.Behaviour | None:
    """Compose the guard *rule* requires for the activity *ctx* describes.

    Args:
        rule: The use case's declared sender rule.
        ctx: The sender and the records its kinds are checked against, or a
            :class:`LedgerActivityContext` for an activity whose case the
            ledger entry it carries names.

    Returns:
        The guard, or ``None`` when the receiver's side admits any actor.

    Raises:
        VultronWiringError: The context lacks a record a kind needs: an
            ``INVITEE`` kind without ``invite_id``, a ``NAMED_ACTOR`` kind
            without ``request``, an ``AUTHOR`` kind without
            ``authored_object``, or a case-scoped check without
            ``case_id``; or a ledger activity's rule declares a kind that
            cannot read the case at run time, or differs by side.
    """
    if isinstance(ctx, LedgerActivityContext):
        return _ledger_guard(rule)

    def node_for(kind: SenderEntitlementKind) -> py_trees.behaviour.Behaviour:
        return _kind_node(kind, ctx)

    if ctx.case_id is None:
        return _any_of(
            rule.outside_case,
            node_for,
            "a receiver that holds no case for it (the activity names no"
            " case this store holds)",
        )
    if rule.at_case_manager == rule.at_participant:
        return _any_of(rule.at_case_manager, node_for, "a case actor")
    manager = _or_pass(
        _any_of(rule.at_case_manager, node_for, "the CASE_MANAGER"),
        "AtCaseManager",
    )
    participant = _or_pass(
        _any_of(
            rule.at_participant,
            node_for,
            "a participant other than the CASE_MANAGER",
        ),
        "AtParticipant",
    )
    return py_trees.composites.Sequence(
        name=_RULE_GUARD_NAME,
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


def _is_composed_guard(node: py_trees.behaviour.Behaviour) -> bool:
    """Whether *node* is the root of a guard :func:`compose_sender_guard`
    builds: a kind's node, an empty side's refusal, or a composite."""
    return isinstance(
        node, (SenderEntitlementConditionNode, SenderIsParticipantNode)
    ) or node.name in {_ANY_OF_NAME, _RULE_GUARD_NAME}


def sender_guard_refused(root: py_trees.behaviour.Behaviour) -> bool:
    """Whether the sender guard the factory placed in *root* refused.

    ``create_receive_activity_tree`` places the composed guard as a direct
    child of the tree's root, so a handler can tell a sender refusal from a
    failure elsewhere without naming a sender node itself (HP-01-007).
    """
    return any(
        _is_composed_guard(child) and child.status is Status.FAILURE
        for child in root.children
    )
