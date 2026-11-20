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

"""The condition node each declared kind composes for one activity
(HP-01-009, HP-01-025).
"""

from collections.abc import Mapping

import py_trees

from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import (
    CASE_ID,
    INVITE_ID,
    NOTE_ID,
    OFFER_ID,
    PARTICIPANT_ID,
    PROPOSAL_ID,
    REPORT_ID,
    SENDER_ID,
    ActKey,
)
from vultron.core.behaviors.sender_check_context import (
    AuthoredCaseProposal,
    AuthoredNote,
    AuthoredParticipantRecord,
    CaseBootstrapRequest,
    CaseProposalRequest,
    OwnershipOfferRequest,
    ReportOfferRequest,
    RoleOfferRequest,
    SenderCheckContext,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
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
    SenderIsParticipantRecordSubjectNode,
    SenderIsProposalAddresseeNode,
    SenderIsProposalAuthorNode,
    SenderIsRoleOfferTargetNode,
)
from vultron.core.behaviors.sender_guard.doors import (
    closed_sender_guard,
)
from vultron.errors import VultronWiringError


def _sender_seeded(
    node: py_trees.behaviour.Behaviour,
    ctx: SenderCheckContext,
    seeds: Mapping[ActKey, str | None] | None = None,
) -> py_trees.behaviour.Behaviour:
    """*node* with ``/sender_id`` and each key of *seeds* seeded.

    The kind nodes read every per-act value from its key (BTND-01-008); a
    seed of ``None`` is left unseeded, which the node reads as absent.
    """
    return with_act_keys(node, {SENDER_ID: ctx.sender_id, **(seeds or {})})


def _addressee_node(
    ctx: SenderCheckContext,
) -> py_trees.behaviour.Behaviour:
    """The ``NAMED_ACTOR`` check for the record *ctx* names (HP-01-009)."""
    request = ctx.request
    if isinstance(request, CaseProposalRequest):
        return _sender_seeded(
            SenderIsProposalAddresseeNode(),
            ctx,
            {REPORT_ID: request.report_id},
        )
    if isinstance(request, ReportOfferRequest):
        return _sender_seeded(
            SenderIsOfferAddresseeNode(), ctx, {OFFER_ID: request.offer_id}
        )
    if isinstance(request, CaseBootstrapRequest):
        return _sender_seeded(
            SenderIsExpectedCaseCreatorNode(), ctx, {CASE_ID: request.case_id}
        )
    if isinstance(request, OwnershipOfferRequest):
        return SenderIsOwnershipTransfereeNode(
            case_id=_case_of(ctx, "an ownership-transfer Offer"),
            offer_id=request.offer_id,
            sender_actor_id=ctx.sender_id,
        )
    if isinstance(request, RoleOfferRequest):
        return _sender_seeded(
            SenderIsRoleOfferTargetNode(),
            ctx,
            {
                CASE_ID: _case_of(ctx, "a role Offer"),
                OFFER_ID: request.offer_id,
            },
        )
    raise VultronWiringError(
        "compose_sender_guard: a NAMED_ACTOR kind needs the record holding"
        " its request in SenderCheckContext.request (HP-01-009)"
    )


def _author_node(
    ctx: SenderCheckContext,
) -> py_trees.behaviour.Behaviour:
    """The ``AUTHOR`` check for the object *ctx* names (HP-01-009)."""
    authored = ctx.authored_object
    if isinstance(authored, AuthoredParticipantRecord):
        # The record names its own case (HP-08-008), so the check reads it
        # from there when the context names none.
        return _sender_seeded(
            SenderIsParticipantRecordSubjectNode(),
            ctx,
            {PARTICIPANT_ID: authored.participant_id, CASE_ID: ctx.case_id},
        )
    if isinstance(authored, AuthoredNote):
        return _sender_seeded(
            SenderIsNoteAuthorNode(),
            ctx,
            {
                NOTE_ID: authored.note_id,
                CASE_ID: _case_of(ctx, "the author of a note"),
            },
        )
    if isinstance(authored, AuthoredCaseProposal):
        return _sender_seeded(
            SenderIsProposalAuthorNode(),
            ctx,
            {PROPOSAL_ID: authored.proposal_id},
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
            " SenderCheckContext.case_id (HP-01-025)"
        )
    return ctx.case_id


#: The two participant-record kinds: any record on the case, or an active one
#: (CM-10-004).  Each reads only the sender and the case.
_MEMBERSHIP_NODES: dict[
    SenderEntitlementKind,
    type[SenderIsParticipantNode | SenderIsActiveParticipantNode],
] = {
    SenderEntitlementKind.PARTICIPANT: SenderIsParticipantNode,
    SenderEntitlementKind.ACTIVE_PARTICIPANT: SenderIsActiveParticipantNode,
}


def _case_owner_node(ctx: SenderCheckContext) -> py_trees.behaviour.Behaviour:
    """The ``CASE_OWNER`` check for the activity in *ctx*.

    The withdrawal of an ownership-transfer proposal checks the Owner that
    made the Offer the CASE_MANAGER recorded from it (CM-21-015); a new
    proposal checks the Owner making it (CM-21-019); anything else checks
    the role alone.

    On a case, an owner whose closure the case records is refused first:
    it has left and may act on nothing further (CM-23-018).  The check is
    composed here, beside the role check, rather than inside
    :class:`SenderIsCaseOwnerNode`, so the check itself asks the role alone.
    The owner's own ``Leave`` is the exception (*closing_case_owner*): it
    closes a case that is not fully closed, so the role alone is asked and
    the tree's closed-sender door guard decides a repeat (CM-23-002).
    """
    owner = _case_owner_role_node(ctx)
    if ctx.case_id is None or ctx.closing_case_owner:
        return owner
    return py_trees.composites.Sequence(
        name="OpenCaseOwner",
        memory=False,
        children=[closed_sender_guard(ctx.case_id, ctx.sender_id), owner],
    )


def _case_owner_role_node(
    ctx: SenderCheckContext,
) -> py_trees.behaviour.Behaviour:
    """The ``CASE_OWNER`` role check for the activity in *ctx*."""
    if isinstance(ctx.request, OwnershipOfferRequest):
        return SenderIsOwnershipOffererNode(
            case_id=_case_of(ctx, "an ownership-transfer Offer"),
            offer_id=ctx.request.offer_id,
            sender_actor_id=ctx.sender_id,
            reply_id=ctx.request.reply_id,
        )
    if ctx.ownership_proposal_id is not None:
        return SenderIsOfferingCaseOwnerNode(
            case_id=_case_of(ctx, "an ownership-transfer Offer"),
            proposal_id=ctx.ownership_proposal_id,
            sender_actor_id=ctx.sender_id,
        )
    return _sender_seeded(SenderIsCaseOwnerNode(), ctx, {CASE_ID: ctx.case_id})


def _kind_node(
    kind: SenderEntitlementKind, ctx: SenderCheckContext
) -> py_trees.behaviour.Behaviour:
    """The condition node that checks *kind* for the activity in *ctx*."""
    if (membership := _MEMBERSHIP_NODES.get(kind)) is not None:
        # The node reads its case from ``/case_id``, seeded with the case the
        # context names (BTND-01-006), and the sender from ``/sender_id``.
        return _sender_seeded(membership(), ctx, {CASE_ID: ctx.case_id})
    if kind is SenderEntitlementKind.LEDGER_PEER:
        # Reads the sender and the case from the ledger activity on the
        # blackboard (SYNC-03-005).
        return SenderIsActiveLedgerParticipantNode(
            name="SenderIsActiveLedgerParticipant"
        )
    if kind is SenderEntitlementKind.CASE_MANAGER:
        return _sender_seeded(
            SenderIsCaseManagerNode(
                anchored=ctx.case_manager_anchored,
                required=ctx.case_manager_required,
            ),
            ctx,
            {CASE_ID: ctx.case_id},
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
                " Invite's id in SenderCheckContext.invite_id (HP-01-025)"
            )
        return _sender_seeded(
            SenderIsInviteeNode(case_join=ctx.invite_is_case_join),
            ctx,
            {INVITE_ID: ctx.invite_id, CASE_ID: ctx.case_id},
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
        " LEDGER_PEER can (HP-01-025)"
    )
