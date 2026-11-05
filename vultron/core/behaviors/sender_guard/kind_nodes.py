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

import py_trees

from vultron.core.behaviors.case_id_scope import with_case_id
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
    SenderIsRequestAddresseeNode,
    SenderIsRoleOfferTargetNode,
)
from vultron.core.behaviors.sender_guard.doors import (
    closed_sender_guard,
)
from vultron.errors import VultronWiringError


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
    if isinstance(request, RoleOfferRequest):
        return SenderIsRoleOfferTargetNode(
            case_id=_case_of(ctx, "a role Offer"),
            offer_id=request.offer_id,
            sender_actor_id=ctx.sender_id,
        )
    raise VultronWiringError(
        "compose_sender_guard: a NAMED_ACTOR kind needs the record holding"
        " its request in SenderCheckContext.request (HP-01-009)"
    )


def _author_node(
    ctx: SenderCheckContext,
) -> (
    SenderIsNoteAuthorNode
    | SenderIsProposalAuthorNode
    | SenderIsParticipantRecordSubjectNode
):
    """The ``AUTHOR`` check for the object *ctx* names (HP-01-009)."""
    authored = ctx.authored_object
    if isinstance(authored, AuthoredParticipantRecord):
        return SenderIsParticipantRecordSubjectNode(
            participant_id=authored.participant_id,
            sender_actor_id=ctx.sender_id,
            case_id=_case_of(ctx, "the participant a record names"),
        )
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
            " SenderCheckContext.case_id (HP-01-025)"
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

    The withdrawal of an ownership-transfer proposal checks the Owner that
    made the Offer the CASE_MANAGER recorded from it (CM-21-015); a new
    proposal checks the Owner making it (CM-21-019); anything else checks
    the role alone.

    On a case, an owner whose closure the case records is refused first:
    it has left and may act on nothing further (CM-23-018).  The check is
    composed here, beside the role check, rather than inside
    :class:`SenderIsCaseOwnerNode`, whose standing reads in the Leave,
    suggest-actor, status and embargo trees must keep asking the role alone.
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
    return with_case_id(
        SenderIsCaseOwnerNode(sender_actor_id=ctx.sender_id), ctx.case_id
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
                " Invite's id in SenderCheckContext.invite_id (HP-01-025)"
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
        " LEDGER_PEER can (HP-01-025)"
    )
