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

An empty side composes :class:`NoSenderAdmittedNode`, so an activity that
names no case is refused under a rule with no ``outside_case`` side; ``ANY_ACTOR`` composes
no node, so a rule that admits any actor composes no guard at all.

The context records live in :mod:`vultron.core.behaviors.sender_check_context`
and are re-exported here.  Beside the composer sit the two pre-flight builders
(:func:`closed_sender_guard`, :func:`case_owner_guard`) and
:func:`sender_guard_refused`, which tells a handler its run ended at the
composed guard.
"""

import py_trees

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.sender_check_context import (
    AddresseeRequest,
    AuthoredCaseProposal,
    AuthoredNote,
    AuthoredObject,
    CaseBootstrapRequest,
    CaseProposalRequest,
    OwnershipOfferRequest,
    ReportOfferRequest,
    SenderCheckContext,
    embargo_sender_context,
)
from vultron.core.behaviors.sender_entitlement import (
    NoSenderAdmittedNode,
    SenderClosureNotRecordedNode,
    SenderEntitlementKind,
    SenderHoldsNoneOfNode,
    SenderIsActiveLedgerParticipantNode,
    SenderIsActiveParticipantNode,
    SenderIsCaseManagerNode,
    SenderIsCaseOwnerNode,
    SenderIsExpectedCaseCreatorNode,
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
    "CaseBootstrapRequest",
    "case_owner_guard",
    "CaseProposalRequest",
    "OwnershipOfferRequest",
    "ReportOfferRequest",
    "SenderCheckContext",
    "closed_sender_guard",
    "compose_sender_guard",
    "embargo_sender_context",
    "sender_guard_refused",
]


def closed_sender_guard(
    case_id: str, sender_id: str
) -> SenderClosureNotRecordedNode:
    """The CM-23-018 check that the case does not record the sender's closure.

    Built here, beside the kinds' guards, so the closed-sender pre-flight
    (``vultron.core.use_cases.received._sender_preflight``) never names a
    sender node itself (HP-01-007).  It is not a kind: it tells a repeated
    closing act (``SKIPPED``) from any other act of a closed sender
    (``REFUSED``) before a handler's received tree runs.
    """
    return SenderClosureNotRecordedNode(
        case_id=case_id, sender_actor_id=sender_id
    )


#: The names :func:`compose_sender_guard` gives the composites it builds.
_RULE_GUARD = "SenderRuleGuard"
_ANY_OF = "AnyOfSenderKinds"

#: The attribute :func:`compose_sender_guard` sets on the guard it returns,
#: so :func:`sender_guard_refused` knows that node by its origin, never by
#: its name or type: another sender node at the root is not the guard.
_COMPOSED_GUARD_MARK = "_vultron_composed_sender_guard"


def _is_composed_guard(node: py_trees.behaviour.Behaviour) -> bool:
    """*node* is the guard :func:`compose_sender_guard` returned."""
    return getattr(node, _COMPOSED_GUARD_MARK, False) is True


def sender_guard_refused(root: py_trees.behaviour.Behaviour) -> bool:
    """True when a received tree's run ended at its composed sender guard.

    The factory places the guard as one child of the tree's root Sequence
    (HP-01-008); the run ended there when the first child that failed is
    that guard.  A sender node deeper in the tree, which picks an effect
    after admission, is not it.  A handler that answers a refused assertion
    (a processing fault, say) asks this first: a sender with no standing is
    owed no answer about its content (HP-01-006).
    """
    for child in root.children:
        if child.status is py_trees.common.Status.FAILURE:
            return _is_composed_guard(child)
    return False


def case_owner_guard(
    case_id: str, sender_id: str
) -> py_trees.behaviour.Behaviour:
    """The ``CASE_OWNER`` check, for a pre-flight that picks a verdict.

    Built here, beside the kinds' guards, so a pre-flight never names a
    sender node itself (HP-01-007).  It admits no one: the closed-sender
    pre-flight asks it to tell a Case Owner's redelivered ``Leave``, whose
    case closure may still be incomplete, from a repeat that changes
    nothing (CM-23-002, CM-23-018).
    """
    return SenderIsCaseOwnerNode(sender_actor_id=sender_id, case_id=case_id)


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
    if isinstance(request, CaseBootstrapRequest):
        return SenderIsExpectedCaseCreatorNode(
            case_id=request.case_id, sender_actor_id=ctx.sender_id
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
        name=_ANY_OF,
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
            ``authored_object``, or a case-scoped check without
            ``case_id``.
    """
    guard = _compose(rule, ctx)
    if guard is not None:
        setattr(guard, _COMPOSED_GUARD_MARK, True)
    return guard


def _compose(
    rule: SenderRule, ctx: SenderCheckContext
) -> py_trees.behaviour.Behaviour | None:
    """The guard :func:`compose_sender_guard` returns, before it is marked."""
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
        name=_RULE_GUARD,
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
