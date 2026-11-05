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

"""Verdicts that read a repeat guard's ``FAILURE`` as a benign no-op.

A guard that fails because the delivery is a redelivery, a repeated answer
or a stale copy ends the run with nothing applied; the handler reports
``SKIPPED``, not the default ``REFUSED`` (HP-01-003).
"""

import py_trees

from vultron.core.behaviors.case.nodes.case_copy import CaseCopyNotStaleNode
from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
    NoOpenOwnershipOfferNode,
)
from vultron.core.behaviors.case.nodes.ownership_reply_guard import (
    OwnershipOfferOpenNode,
)
from vultron.core.behaviors.case.nodes.role_offer_guard import (
    RoleOfferAdmissibleNode,
    RoleOfferOpenNode,
)
from vultron.core.behaviors.embargo.nodes.answer_repeat import (
    EmbargoAnswerNotRecordedNode,
)
from vultron.core.behaviors.embargo.nodes.proposal_repeat import (
    EmbargoTermsNotHeldNode,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    EmbargoInviteNotYetRefusedNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    IsWithdrawableEmbargoNode,
)
from vultron.core.behaviors.note.nodes.storage import NoteIdNotTakenNode
from vultron.core.behaviors.report.nodes.conditions import (
    CheckParticipantRMState,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received._bt_verdict.tree_lookup import (
    _HasRoot,
    find_node,
    node_failed,
    node_succeeded,
    taken_diversion,
)


def _redelivery_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    guard_type: (
        type[OwnershipOfferOpenNode]
        | type[NoOpenOwnershipOfferNode]
        | type[IsWithdrawableEmbargoNode]
        | type[NoteIdNotTakenNode]
        | type[RoleOfferAdmissibleNode]
        | type[RoleOfferOpenNode]
    ),
    verdict: HandlerResult,
    fallback: str,
) -> HandlerResult:
    """``SKIPPED`` when *guard_type* failed the run as a redelivery."""
    guard = find_node(tree, guard_type)
    if guard is not None and guard.is_redelivery:
        return HandlerResult.skipped(guard.feedback_message or fallback)
    return verdict


def _flagged_repeat_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    guard_type: (
        type[EmbargoAnswerNotRecordedNode]
        | type[EmbargoTermsNotHeldNode]
        | type[CaseCopyNotStaleNode]
    ),
    verdict: HandlerResult,
    fallback: str,
) -> HandlerResult:
    """``SKIPPED`` when *guard_type* failed the run as a repeat.

    For a guard that reports its repeat through ``failed_as_repeat``
    (:class:`~vultron.core.behaviors.idempotency.FlaggedRepeatGuardMixin`).
    """
    guard = find_node(tree, guard_type)
    if guard is not None and guard.failed_as_repeat:
        return HandlerResult.skipped(guard.feedback_message or fallback)
    return verdict


def embargo_answer_repeat_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a repeated answer to an embargo Invite as ``SKIPPED``.

    :class:`~vultron.core.behaviors.embargo.nodes.answer_repeat.EmbargoAnswerNotRecordedNode`
    fails with ``is_repeat`` set when the sender's consent row already holds
    the answer, so nothing is committed or announced.  That is the benign
    no-op of a repeat, not a refusal (CM-13-005, HP-01-003).
    """
    return _flagged_repeat_verdict(
        tree, EmbargoAnswerNotRecordedNode, verdict, "embargo answer repeated"
    )


def embargo_terms_repeat_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a proposal of terms the case already holds as ``SKIPPED``.

    :class:`~vultron.core.behaviors.embargo.nodes.proposal_repeat.EmbargoTermsNotHeldNode`
    fails with ``is_repeat`` set when the proposal's end time equals that of a
    pending proposal or, with none pending, of the embargo in force, so
    nothing is committed or relayed.  That is the benign no-op of a repeat,
    not a refusal (EP-09-032, HP-01-003).
    """
    return _flagged_repeat_verdict(
        tree, EmbargoTermsNotHeldNode, verdict, "embargo terms repeated"
    )


def stale_case_copy_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a case copy the replica's chain is past as ``SKIPPED``.

    :class:`~vultron.core.behaviors.case.nodes.case_copy.CaseCopyNotStaleNode`
    fails with ``is_stale`` set when the replica already holds entries past
    the copy's ledger position, so the case is left unchanged.  That is the
    benign no-op of a late copy, not a refusal (SYNC-16-006, HP-01-003).
    """
    return _flagged_repeat_verdict(
        tree, CaseCopyNotStaleNode, verdict, "case copy is stale"
    )


def embargo_withdrawal_redelivery_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered ``Leave(EmbargoEvent)`` as ``SKIPPED``.

    :class:`~vultron.core.behaviors.embargo.nodes.withdrawal.IsWithdrawableEmbargoNode`
    fails with ``is_redelivery`` set when the case's ledger already records
    the Leave, so nothing is re-applied.  That is the benign no-op of a
    redelivery, not a refusal (HP-01-003, MSM-07-010).
    """
    return _redelivery_verdict(
        tree,
        IsWithdrawableEmbargoNode,
        verdict,
        "Leave(EmbargoEvent) redelivered",
    )


def add_note_redelivery_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered ``Add(Note)`` as ``SKIPPED``.

    :class:`~vultron.core.behaviors.note.nodes.storage.NoteIdNotTakenNode`
    fails with ``is_redelivery`` set when the case's ledger already records
    the ``Add``, so nothing is re-applied.  That is the benign no-op of a
    redelivery, not a refusal (HP-01-003, HP-08-006).
    """
    return _redelivery_verdict(
        tree, NoteIdNotTakenNode, verdict, "Add(Note) redelivered"
    )


def ownership_answer_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered reply to an ownership-transfer Offer as ``SKIPPED``.

    The reply's open-Offer guard — an
    :class:`~vultron.core.behaviors.case.nodes.ownership_reply_guard.OwnershipOfferOpenNode`,
    run right after the sender check, for the transferee's Accept or Reject
    or the offerer's withdrawal — fails with ``is_redelivery`` set when the
    reply is the one already ledgered as closing its Offer, so nothing is
    re-applied.  That is the benign no-op of a redelivery, not a refusal
    (HP-01-003, CM-21-011, CM-21-015).
    """
    return _redelivery_verdict(
        tree,
        OwnershipOfferOpenNode,
        verdict,
        "ownership-transfer reply redelivered",
    )


def ownership_offer_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered ownership-transfer proposal as ``SKIPPED``.

    :class:`~vultron.core.behaviors.case.nodes.ownership_offer_guard.NoOpenOwnershipOfferNode`
    fails with ``is_redelivery`` set when the CASE_MANAGER's ledger already
    records the Offer it made from the proposal, so the proposal is neither
    judged against a newer open Offer nor committed or made into an Offer
    again (HP-01-003, CM-21-014).
    """
    return _redelivery_verdict(
        tree,
        NoOpenOwnershipOfferNode,
        verdict,
        "ownership-transfer proposal redelivered",
    )


def role_offer_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered role Offer as ``SKIPPED``.

    :class:`~vultron.core.behaviors.case.nodes.role_offer_guard.RoleOfferAdmissibleNode`
    sets ``is_redelivery`` and fails when the CASE_MANAGER's ledger already
    records the Offer, so nothing runs (HP-01-003).
    """
    return _redelivery_verdict(
        tree, RoleOfferAdmissibleNode, verdict, "role Offer redelivered"
    )


def role_offer_answer_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered answer to a role Offer as ``SKIPPED``.

    :class:`~vultron.core.behaviors.case.nodes.role_offer_guard.RoleOfferOpenNode`
    sets ``is_redelivery`` when the answer is the one already ledgered as
    closing its Offer, and fails, so nothing runs (HP-01-003, CM-33-018).
    """
    return _redelivery_verdict(
        tree, RoleOfferOpenNode, verdict, "role Offer answer redelivered"
    )


def rm_declaration_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
    label: str,
) -> HandlerResult:
    """Report a restated RM declaration as ``SKIPPED``, not ``APPLIED``.

    The idempotent exit of
    :func:`~vultron.core.behaviors.report.rm_declaration_tree.record_rm_declaration`
    (``CheckParticipantRMState``) succeeds when the sender's declared state is
    already recorded, so nothing changed locally: a correct no-op, not a
    refusal or a fault (RSH-08-002, ADR-0095).  A tree that hangs further
    effects on the move asks the same condition ahead of its write and skips
    those too — the engage tree's case broadcast does
    (``_engage_effects_unless_restated``), so this answer covers them (#5006).
    """
    if verdict.disposition is HandlerDisposition.APPLIED and node_succeeded(
        tree, CheckParticipantRMState
    ):
        return HandlerResult.skipped(
            f"{label}: the declared RM state is already recorded for the sender"
        )
    return verdict


def pxa_refusal_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    name: str,
    answered: str,
) -> HandlerResult | None:
    """The verdict of a delivery the P/X/A refusal *name* diverted, else ``None``.

    ``SKIPPED`` when the ``Reject`` of the Invite *answered* names was
    already sent, so the redelivery is not refused twice (HP-01-003);
    otherwise ``REFUSED`` for the condition's reason (EMB-01-002,
    EMB-02-004), whether or not the ``Reject`` could be sent.
    """
    stage = taken_diversion(tree, name)
    if stage is None:
        return None
    if node_failed(stage, EmbargoInviteNotYetRefusedNode):
        return HandlerResult.skipped(
            f"{answered} not refused again: the Reject was already sent"
            " (HP-01-003)"
        )
    return HandlerResult.refused(
        stage.condition.feedback_message or f"{name}: P/X/A set"
    )
