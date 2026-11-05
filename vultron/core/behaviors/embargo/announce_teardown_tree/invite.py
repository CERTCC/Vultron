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

"""Received-side ``Invite(EmbargoEvent)`` tree (protocol EP / EV).

The type declares the manager and the participant-replica path, and the
factory branches each arm on the one answer the path stage gave (HP-01-038,
ADR-0153).  A receiver that holds no replica of the case takes neither arm:
the path stage refuses it there, with the reason it composes (HP-01-039).

The CASE_MANAGER adjudicates the proposal (``ProposeEmbargoLifecycleNode``)
and relays it to every participant except the proposer
(``RelayEmbargoInviteToEachNode``, ``nodes/relay.py``); the addressee's store
answers the Invite to the CASE_MANAGER and writes no state (ADR-0113,
EP-09-003).
"""

import logging

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.path_branch import OnPaths
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.embargo_clock_decisions import (
    embargo_clock_decisions,
)
from vultron.core.behaviors.embargo.nodes import (
    CanAnswerEmbargoInviteNode,
    CollectEmbargoInviteRecipientsNode,
    EmbargoProposalNotYetRecordedNode,
    IndexReceivedEmbargoProposalNode,
    OwnerMayAutoAcceptEmbargoNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    RelayEmbargoInviteToEachNode,
    SendEmbargoInviteAnswerNode,
    SendOwnerEmbargoDecisionNode,
    case_manager_admits_proposal_guard,
    invitee_not_yet_answered_guard,
)
from vultron.core.behaviors.embargo.nodes.manager_consent import (
    record_manager_embargo_consent_tree,
)
from vultron.core.behaviors.embargo.refusal_tree import pxa_invite_refusal
from vultron.core.behaviors.embargo.response_decision_tree import (
    create_embargo_response_decision_tree,
)
from vultron.core.behaviors.role_condition import ActorHoldsRoleInCaseNode
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import embargo_sender_context
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def _index_received_proposal(
    case_id: str, embargo_id: str, invite_id: str
) -> IndexReceivedEmbargoProposalNode:
    """The DL-06 proposal index, last in whichever Invite arm runs.

    The two declared path branches of ``invite_to_embargo_on_case_tree`` are
    mutually exclusive and between them cover every receiver the tree admits,
    so each ends with its own index node: the index is written only once the
    Invite has been applied, as the accept/reject triggers and the
    idempotency guard expect.
    """
    return IndexReceivedEmbargoProposalNode(
        case_id=case_id, embargo_id=embargo_id, invite_id=invite_id
    )


def invite_to_embargo_on_case_tree(
    case_id: str,
    invitee_id: str,
    invite_id: str,
    *,
    embargo_id: str,
    proposer_id: str,
    sender_actor_id: str,
    sender_rule: SenderRule,
    embargo: EmbargoEvent | None = None,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiving an embargo proposal or invitation (EP / EV).

    Handles receipt of an ``Invite(EmbargoEvent)`` activity.  The tree has
    two mutually exclusive declared path branches behind the shared intake
    and guarded commit, because the same wire message means two different
    things depending on who receives it (ADR-0113, HP-01-038):

    **The CASE_MANAGER adjudicates** (EP-09-001, EP-09-002).  A participant
    addresses its proposal to the CASE_MANAGER alone (PCR-08-001), so the
    "Participant receiving EP/EV" of EMB-01 and EMB-03 is the manager.  Under
    its role gate (BT-17-001) it persists the proposed ``EmbargoEvent`` from
    the copy the message carries (CLP-10-017), resolves the relay recipients
    before anything moves (BT-19-001), moves the canonical case through
    ``EmbargoLifecycle.propose_embargo`` in STRICT mode — ``NONE → PROPOSED``
    for a first proposal, ``ACTIVE → REVISE`` for a revision, no transition
    for a counter-proposal at ``PROPOSED`` or ``REVISE`` — recording the
    *proposer's* consent to its own terms (ADR-0093), then relays one
    ``Invite(EmbargoEvent)`` to every participant except the proposer as
    ``actor`` with the proposer in ``attributedTo`` (CM-24), committing each
    emission and applying the invitee's PEC ``INVITE`` where CM-18-003 allows
    it (EP-09-004).  A case whose EM state admits no proposal (``EXITED``) is
    refused by a read-only guard ahead of the commit (CLP-10-009).

    **The door guards and the P/X/A refusal precede both arms**: a copy not
    addressed to this receiver is refused (HP-01-005), then a sender without
    standing (HP-01-006).  Once P/X/A is set, the Invite is refused with a
    ``Reject`` of it (EMB-01-002, EMB-03-004) by a diversion of the tree
    (:func:`~vultron.core.behaviors.embargo.refusal_tree.pxa_invite_refusal`,
    CLP-10-026): its invitee answers the CASE_MANAGER, the CASE_MANAGER the
    proposer, and neither arm runs.
    The CM-24 authorship pair comes from the shared ``delegated_authorship``
    helper (CM-24-005): the relay runs only in the manager branch, so
    ``actor`` is the role holder, and ``attributedTo`` is the proposer.

    **Either arm is preceded by an idempotency guard**: the same Invite
    delivered again while its proposal is open
    (``pending_embargo_proposal_index`` already maps the embargo to this
    Invite's id) commits nothing and the handler reports it as a repeat
    (CLP-13-001, HP-01-003).  The index holds no decided proposal
    (EP-08-003), so on the participant path a second guard,
    :class:`~vultron.core.behaviors.embargo.nodes.relay_guards.EmbargoInviteNotYetAnsweredNode`,
    skips an Invite the invitee has already answered, however its proposal
    has moved since (ID-04-004, SYNC-19-001).  At the CASE_MANAGER a proposal of
    terms the case already holds — the end time of a pending proposal, or,
    with no revision pending, of the embargo in force — is a repeat too,
    whatever its ids and sender (EP-09-032).  Each arm ends by writing that
    index (DL-06), so it is written only once the Invite has been applied in
    whichever arm ran.  The participant-replica arm is the ``PathBranch`` the
    factory builds from an ``OnPaths.off_case_manager`` declaration among
    ``replica_effects``, and so runs
    before the factory's CASE_MANAGER gate; the two arms are mutually
    exclusive on the one answer the path stage gave, so their order does not
    matter (HP-01-037, HP-01-038).

    **A participant replica stores and answers** the Invite addressed to it
    and writes nothing else (EP-09-003).  The intake archives the Invite
    under the receiver's key (CLP-10-017, DL-06-006); when
    the executing actor is its addressee, the EMB-15 response decision
    (``create_embargo_response_decision_tree``) queues an ``Accept`` or
    ``Reject`` of it to the CASE_MANAGER (``SendEmbargoInviteAnswerNode``).
    When the addressee is the case owner its answer is its decision for the
    case, so it is queued as ``Accept`` or ``Reject`` of the embargo itself
    (``SendOwnerEmbargoDecisionNode``, ADR-0122) — and only inside the
    prototype's auto-accept bound; otherwise the owner holds its answer.
    No EM state and no consent state moves here: the replica learns the
    proposal, the relayed Invite and every answer from the CASE_MANAGER's
    committed entries, which ``create_announce_log_entry_tree`` replays
    (EP-09-007, RSH-08-004).  An Invite that reached a store other than its
    addressee's is archived and left unanswered.

    Args:
        case_id: ID of the VulnerabilityCase.
        invitee_id: Actor ID of the invitee (the Invite's sole ``to``).
        invite_id: ID of the received Invite activity.
        embargo_id: ID of the proposed ``EmbargoEvent`` (the Invite's object).
        proposer_id: Actor whose terms these are — the Invite's ``actor``, or
            its ``attributedTo`` when the proposal was itself relayed.
        sender_actor_id: The Invite's ``actor``: an active participant at the
            CASE_MANAGER (CM-10-004), the CASE_MANAGER at a participant
            replica (EP-09-003, PCR-08; ADR-0115).  Not ``proposer_id``, which
            a relay's ``attributedTo`` may name.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).
        embargo: The inline ``EmbargoEvent`` the message carries, persisted
            by an effect in whichever store receives the Invite (CLP-10-017);
            ``None`` when the message named its object by bare URI.
        actor_config: The executing CASE_MANAGER's configuration; its RSVP
            windows set each relayed Invite's ``endTime`` (CM-28-012).
            ``None`` applies the ``ActorConfig`` defaults.

    Returns:
        Root node of the ``InviteToEmbargoOnCaseBT`` Sequence.
    """
    # Every store keeps the embargo the Invite carries, the core record its
    # adjudication and answer read.  The Invite itself is read as intake
    # archived it, never stored under the id its sender chose (CLP-10-017,
    # DL-06-006).  Storing the embargo moves no EM or consent state
    # (EP-09-003).
    intake: list[py_trees.behaviour.Behaviour] = []
    if embargo is not None:
        intake.append(PersistEmbargoEventNode(embargo=embargo))
    adjudication: list[py_trees.behaviour.Behaviour] = [
        CollectEmbargoInviteRecipientsNode(
            case_id=case_id, proposer_id=proposer_id
        ),
        # The guarded commit committed the proposal, whose entry is the
        # PROPOSE step, in this act's transaction;
        # the decision's new consent rows follow as the CASE_MANAGER's own
        # Create(EmbargoConsent) entries, and all are applied by copying
        # (ADR-0124, CLP-07-013).
        ProposeEmbargoLifecycleNode(
            case_id=case_id,
            embargo_id=embargo_id,
            result_out={},
            proposer_id=proposer_id,
            embargo=embargo,
        ).applying_after(cause_id=invite_id),
        RelayEmbargoInviteToEachNode(
            case_id=case_id,
            embargo_id=embargo_id,
            proposer_id=proposer_id,
            actor_config=actor_config,
            # Each relayed Invite's id derives from the proposal it
            # answers (ID-04-004).
            answers=invite_id,
        ),
        # EP-09-024: the relay skips the manager, so it writes its own row.
        record_manager_embargo_consent_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            proposer_id=proposer_id,
            cause_id=invite_id,
        ),
    ]
    root = create_receive_activity_tree(
        name="InviteToEmbargoOnCaseBT",
        case_id=case_id,
        # The same wire message means two different things depending on who
        # receives it, so the type declares a branch for each path
        # (HP-01-038, ADR-0153, ADR-0113): the CASE_MANAGER adjudicates and
        # relays, the addressee's replica answers.  A store that holds no
        # replica of the case is refused at the path stage.
        paths={ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
        sender_rule=sender_rule,
        sender_context=embargo_sender_context(sender_actor_id, case_id),
        # Every overdue invitation expires first (CM-28-028).
        clock_decisions=embargo_clock_decisions(case_id),
        precondition_guards=[
            EmbargoProposalNotYetRecordedNode(
                case_id=case_id, embargo_id=embargo_id, invite_id=invite_id
            ),
            # EMB-01-002: with P/X/A set the Invite is answered with a Reject and
            # moves nothing, at the CASE_MANAGER and at a participant alike.
            pxa_invite_refusal(
                case_id=case_id,
                invite_id=invite_id,
                invitee_id=invitee_id,
                sender_id=sender_actor_id,
                embargo=embargo,
            ),
            # The invitee answers one Invite once, decided or not (ID-04-004).
            # After the P/X/A refusal, whose own guard re-queues a sealed
            # Reject (ID-04-005).
            invitee_not_yet_answered_guard(
                invitee_id=invitee_id, invite_id=invite_id
            ),
            # EM admits the proposal, and its terms are new: a proposal of
            # terms the case already holds, under whatever ids and from
            # whichever sender, is a repeat (EP-09-032).
            case_manager_admits_proposal_guard(
                case_id=case_id, embargo_id=embargo_id, embargo=embargo
            ),
        ],
        replica_effects=[
            *intake,
            OnPaths.off_case_manager(
                "AnswerInviteOnReplica",
                py_trees.composites.Selector(
                    name="AnswerIfAddressee",
                    memory=False,
                    children=[
                        py_trees.decorators.Inverter(
                            name="SkipUnlessAnswerable",
                            child=CanAnswerEmbargoInviteNode(
                                case_id=case_id,
                                invitee_id=invitee_id,
                                embargo_id=embargo_id,
                            ),
                        ),
                        # EP-09-005/006: the owner's answer is its own
                        # to give; it auto-accepts only inside the
                        # prototype's bound, otherwise it holds.
                        py_trees.composites.Sequence(
                            name="OwnerHoldsAnswer",
                            memory=False,
                            children=[
                                ActorHoldsRoleInCaseNode(
                                    actor_id=invitee_id,
                                    role=CVDRole.CASE_OWNER,
                                    case_id=case_id,
                                    name="InviteeIsCaseOwner",
                                ),
                                py_trees.decorators.Inverter(
                                    name="AutoAcceptNotAllowed",
                                    child=OwnerMayAutoAcceptEmbargoNode(
                                        case_id=case_id,
                                        embargo_id=embargo_id,
                                    ),
                                ),
                            ],
                        ),
                        # The owner's answer is its decision for the
                        # case, sent as Accept/Reject of the embargo
                        # itself (ADR-0122).
                        py_trees.composites.Sequence(
                            name="OwnerDecides",
                            memory=False,
                            children=[
                                ActorHoldsRoleInCaseNode(
                                    actor_id=invitee_id,
                                    role=CVDRole.CASE_OWNER,
                                    case_id=case_id,
                                    name="InviteeIsOwner",
                                ),
                                create_embargo_response_decision_tree(
                                    case_id=case_id,
                                    deciding_actor_id=invitee_id,
                                    accept_bt=SendOwnerEmbargoDecisionNode(
                                        case_id=case_id,
                                        embargo_id=embargo_id,
                                        accept=True,
                                        name="SendActivateEmbargo",
                                    ),
                                    reject_bt=SendOwnerEmbargoDecisionNode(
                                        case_id=case_id,
                                        embargo_id=embargo_id,
                                        accept=False,
                                        name="SendRejectEmbargoProposal",
                                    ),
                                ),
                            ],
                        ),
                        create_embargo_response_decision_tree(
                            case_id=case_id,
                            deciding_actor_id=invitee_id,
                            accept_bt=SendEmbargoInviteAnswerNode(
                                case_id=case_id,
                                invite_id=invite_id,
                                accept=True,
                                name="SendAcceptEmbargoInvite",
                            ),
                            reject_bt=SendEmbargoInviteAnswerNode(
                                case_id=case_id,
                                invite_id=invite_id,
                                accept=False,
                                name="SendRejectEmbargoInvite",
                            ),
                        ),
                    ],
                ),
                _index_received_proposal(case_id, embargo_id, invite_id),
                body_name="AnswerInviteOnReplicaBody",
            ),
        ],
        manager_effects=[
            *adjudication,
            _index_received_proposal(case_id, embargo_id, invite_id),
        ],
        manager_case_id=case_id,
        manager_gate_name="AdjudicateEmbargoProposal",
    )
    logger.info(
        "Created InviteToEmbargoOnCaseBT for case=%s invitee=%s invite=%s"
        " embargo=%s proposer=%s",
        case_id,
        invitee_id,
        invite_id,
        embargo_id,
        proposer_id,
    )
    return root
