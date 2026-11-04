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

"""Trigger trees that answer or decide an embargo.

The accept, reject, withdraw, activate and proposal-rejection triggers share
the decision arms built here: the CASE_MANAGER decides on a staged store,
commits, applies and declares; any other participant asks the manager
(ADR-0124, EP-09-007).
"""

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_PROPOSAL_REJECTION_SEMANTIC_TYPE,
    AcceptEmbargoLifecycleNode,
    CommitAndApplyEmbargoActivationNode,
    CommitEmbargoDecisionNode,
    CommitOwnConsentDecisionNode,
    EmbargoActivityBuilder,
    RejectEmbargoLifecycleNode,
    RejectEmbargoProposalLifecycleNode,
    WithdrawEmbargoLifecycleNode,
    embargo_ending_notice_nodes,
)
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    _EmbargoLifecycleNode,
)
from vultron.core.behaviors.embargo.trigger_tree._arms import (
    _asserting,
    _by_role,
    _make_emit_node,
)
from vultron.core.behaviors.embargo.trigger_tree.termination import (
    end_embargo_outliving_disclosure_bt,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.models.events.base import MessageSemantics

_ACCEPT_SEMANTIC_TYPE = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
_WITHDRAW_SEMANTIC_TYPE = MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value


def _answer_arms(
    name: str,
    case_id: str,
    lifecycle_node: _EmbargoLifecycleNode,
    semantic_type: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
    actor_config: ActorConfig | None = None,
    *,
    ends_embargo_after_disclosure: bool = False,
) -> list[py_trees.behaviour.Behaviour]:
    """Manager: decide, commit, apply, declare; otherwise: ask the manager.

    The manager's Accept or Reject — of an Invite (the sender's consent), or
    as the case owner of the embargo itself (ADR-0122) — is addressed to
    nobody: every replica learns it from the committed entry (EP-09-007).  An
    Accept that activates a shorter revision is announced to the bound
    signatories the ledger no longer reaches (CM-31-009).

    The manager arm commits before it writes (ADR-0124, CLP-07-013): the
    lifecycle node only decides, on a staged store, and the commit node
    commits the act's entry (carrying any register step), then one
    CASE_MANAGER entry per consent row the decision changes, and applies them
    by copying.  *lifecycle_node* is built with *result_out*, where it leaves
    the decision.  *ends_embargo_after_disclosure* is passed to
    :func:`_decision_arms`.
    """
    return _decision_arms(
        name,
        case_id,
        [
            lifecycle_node.deciding(),
            CommitEmbargoDecisionNode(
                case_id=case_id,
                semantic_type=semantic_type,
                builder=activity_builder,
                decision_from=result_out,
            ),
        ],
        result_out,
        activity_builder,
        actor_config,
        ends_embargo_after_disclosure=ends_embargo_after_disclosure,
    )


def _decision_arms(
    name: str,
    case_id: str,
    decide_and_commit: list[py_trees.behaviour.Behaviour],
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
    actor_config: ActorConfig | None = None,
    *,
    ends_embargo_after_disclosure: bool = False,
) -> list[py_trees.behaviour.Behaviour]:
    """The two arms of an answer or decision, around *decide_and_commit*.

    As the manager: capture the signatories bound before the change, run
    *decide_and_commit*, declare the ``Add(CaseStatus)``, announce a shorter
    revision to the bound signatories the ledger no longer reaches
    (CM-31-009), and re-issue stale stub Invites (CM-11-016).  Otherwise:
    ask the manager.  Shared by :func:`_answer_arms` and the activation arm;
    each decides before it commits and commits before it writes (ADR-0124).

    With *ends_embargo_after_disclosure* (the owner's rejection), a decision
    that leaves the prior terms standing with P/X/A set is followed in the
    same act by the termination (:func:`end_embargo_outliving_disclosure_bt`,
    EMB-04-002), which declares, notifies and re-issues in place of the
    usual tail.
    """
    capture, notices = embargo_ending_notice_nodes(case_id)
    tail: list[py_trees.behaviour.Behaviour] = [
        _make_emit_node(case_id),
        notices,
        # The owner's accept of a revision changes the active embargo
        # under any outstanding stub Invite (CM-11-016).  The node compares
        # each stub's terms with the embargo in force and does nothing
        # while a proposal is open, so a reject or a participant's accept
        # re-issues nothing.
        ReissueStubInvitesNode(case_id=case_id, actor_config=actor_config),
    ]
    if ends_embargo_after_disclosure:
        tail = [
            end_embargo_outliving_disclosure_bt(
                case_id=case_id, otherwise=tail, actor_config=actor_config
            )
        ]
    return _by_role(
        name,
        case_id,
        as_case_manager=[capture, *decide_and_commit, *tail],
        otherwise=[
            sender_side_bt(
                case_id=case_id,
                activity_builder=_asserting(activity_builder, result_out),
            )
        ],
    )


def accept_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for accepting an embargo invite (EP-09-008).

    ``Accept(Invite(EmbargoEvent))``: the actor's own consent; it moves no
    register entry (ADR-0122).
    """
    return py_trees.composites.Sequence(
        name="AcceptEmbargoTriggerBT",
        memory=False,
        children=_answer_arms(
            "AcceptEmbargo",
            case_id,
            AcceptEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            _ACCEPT_SEMANTIC_TYPE,
            result_out,
            activity_builder,
        ),
    )


def reject_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
    own_consent_out: dict[str, object] | None = None,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for rejecting an embargo invite (EP-09-008).

    ``Reject(Invite(EmbargoEvent))``: the actor's own consent; it moves no
    register entry (ADR-0122).  Any participant other than the CASE_MANAGER
    sends it to the CASE_MANAGER.  The CASE_MANAGER, answering an embargo it
    has a stake in (EP-09-024), sends no ``Reject``: the CASE_MANAGER's
    ``Reject`` of a proposal is its abandonment of it (EMB-16-001,
    ADR-0152), so its own consent is committed as its ``Update(EmbargoConsent)``
    of the row (:class:`CommitOwnConsentDecisionNode`, MSM-07-017), whose
    snapshot it writes to ``own_consent_out["activity"]`` when given.
    """
    return py_trees.composites.Sequence(
        name="RejectEmbargoTriggerBT",
        memory=False,
        children=_decision_arms(
            "RejectEmbargo",
            case_id,
            [
                RejectEmbargoLifecycleNode(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    result_out=result_out,
                ).deciding(),
                CommitOwnConsentDecisionNode(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    decision_from=result_out,
                    captured=own_consent_out,
                ),
            ],
            result_out,
            activity_builder,
        ),
    )


def withdraw_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for withdrawing from the embargo in force (EP-09-013).

    ``Leave(EmbargoEvent)`` (MSM-07-010): the actor's own consent ends; it
    moves no register entry.  As the CASE_MANAGER the actor records its own
    withdrawal and commits the Leave; any other participant sends it to the
    CASE_MANAGER (PCR-08).  The use case refuses an actor that cannot
    withdraw before this tree is built.
    """
    return py_trees.composites.Sequence(
        name="WithdrawEmbargoTriggerBT",
        memory=False,
        children=_answer_arms(
            "WithdrawEmbargo",
            case_id,
            WithdrawEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            _WITHDRAW_SEMANTIC_TYPE,
            result_out,
            activity_builder,
        ),
    )


def activate_embargo_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for the case owner's activation (EP-09-008).

    ``Accept(EmbargoEvent)[target=VulnerabilityCase]`` (ADR-0122): as the CASE_MANAGER the
    owner decides the activation ``STRICT``, commits the ``Accept`` (the
    whole ``ACTIVATE`` step and its own agreement) and then one
    ``Update(EmbargoConsent)`` per ``CARRY_OVER`` row, and only then writes
    the case file (:class:`CommitAndApplyEmbargoActivationNode`, ADR-0124);
    any other owner asks the CASE_MANAGER.  The rest of both arms is
    :func:`_decision_arms`, shared with :func:`_answer_arms`; the ``Accept``
    is addressed to nobody.
    """
    return py_trees.composites.Sequence(
        name="ActivateEmbargoTriggerBT",
        memory=False,
        children=_decision_arms(
            "ActivateEmbargo",
            case_id,
            [
                CommitAndApplyEmbargoActivationNode(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    result_out=result_out,
                    builder=activity_builder,
                )
            ],
            result_out,
            activity_builder,
        ),
    )


def reject_embargo_proposal_trigger_bt(
    *,
    case_id: str,
    embargo_id: str,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for the case owner's rejection (EP-09-008).

    ``Reject(EmbargoEvent)[target=VulnerabilityCase]`` (ADR-0122): as the CASE_MANAGER the
    owner rejects the proposal ``STRICT`` and commits its decision; any other
    owner asks the CASE_MANAGER.  A rejection of the last revision after
    disclosure is followed, in the same act, by the CASE_MANAGER's
    termination (EMB-04-002, MSM-07-032), so a refused termination commits
    neither.
    """
    return py_trees.composites.Sequence(
        name="RejectEmbargoProposalTriggerBT",
        memory=False,
        children=_answer_arms(
            "RejectEmbargoProposal",
            case_id,
            RejectEmbargoProposalLifecycleNode(
                case_id=case_id,
                embargo_id=embargo_id,
                result_out=result_out,
            ),
            EMBARGO_PROPOSAL_REJECTION_SEMANTIC_TYPE,
            result_out,
            activity_builder,
            ends_embargo_after_disclosure=True,
        ),
    )
