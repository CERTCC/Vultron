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

"""
Embargo lifecycle behavior tree compositions.

Provides factory functions for the received-side embargo BTs:

``invite_to_embargo_on_case_tree`` — handles receipt of an ``Invite(EmbargoEvent)``
activity (protocol EP / EV message).  Two role-gated arms behind the shared
intake and guarded commit (ADR-0113, EP-09): the CASE_MANAGER adjudicates the
proposal (``ProposeEmbargoLifecycleNode``) and relays it to every participant
except the proposer (``RelayEmbargoInviteToEachNode``, ``nodes/relay.py``); the
addressee's store answers the Invite to the CASE_MANAGER and writes no state
(EP-09-003).  The tree's docstring draws it.

``remove_embargo_from_case_tree`` — handles receipt of a ``Remove(EmbargoEvent)``
activity (protocol ET message).  Sequence:

    RemoveEmbargoFromCaseBT (Sequence)
    ├─ ValidateCaseExistsNode             # case must exist as VulnerabilityCase
    ├─ GuardedCommitCaseLedgerEntryBT     # record receipt before effects (CLP-10-006)
    └─ TeardownIfActive (Selector)        # skip when there is nothing to tear down
       ├─ EmbargoWasNotActive (Inverter)  # not the active embargo (only proposed)
       │  └─ IsActiveEmbargoNode
       ├─ EmbargoAlreadyExited (Inverter) # EM state already EXITED
       │  └─ HasEmbargoActiveNode
       └─ ActiveTeardown (Sequence)       # its FAILURE is the tree's FAILURE
          ├─ ClearActiveEmbargoNode       # TERMINATE + CANCEL every proposal → EXITED
          ├─ SendAnnounceEmbargoEventNode # emit Announce(EmbargoEvent) to CaseActor
          └─ EmbargoAdmissionBackfill     # CASE_MANAGER: backfill paused peers (CM-10-006)

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

import logging

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.invite_actor_emit import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)

# The standalone admission backfill lives in ``admission_backfill_tree``
# (BT-17-008: a received-tree module takes its gate from the factory); the
# Remove(EmbargoEvent) teardown nests it in its active-only branch.
from vultron.core.behaviors.embargo.admission_backfill_tree import (
    embargo_admission_backfill_tree,
)

# The Accept/Reject(Invite(EmbargoEvent)) trees live in ``answer_trees``
# (CS-18-001); re-exported for existing importers.
from vultron.core.behaviors.embargo.answer_trees import (  # noqa: F401
    accept_invite_to_embargo_tree,
    reject_invite_to_embargo_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    CanAnswerEmbargoInviteNode,
    ClearActiveEmbargoNode,
    CollectEmbargoInviteRecipientsNode,
    CreateAndStoreInviteNode,
    EmbargoProposalNotYetRecordedNode,
    HasEmbargoActiveNode,
    IndexReceivedEmbargoProposalNode,
    IsActiveEmbargoNode,
    OwnerMayAutoAcceptEmbargoNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    RelayEmbargoInviteToEachNode,
    SendAnnounceEmbargoEventNode,
    SendEmbargoInviteAnswerNode,
    SetEmbargoActiveNode,
    ValidateCaseExistsNode,
    case_manager_admits_proposal_guard,
)
from vultron.core.behaviors.embargo.nodes.manager_consent import (
    record_manager_embargo_consent_tree,
)
from vultron.core.behaviors.embargo.response_decision_tree import (
    create_embargo_response_decision_tree,
)
from vultron.core.behaviors.replica_emit_exemptions import (
    EMBARGO_INVITE_ANSWER,
    EMBARGO_TEARDOWN_ANNOUNCE,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderIsCaseOwnerNode,
    SenderMayAssertEmbargoNode,
)
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.services.embargo_lifecycle import TransitionMode

logger = logging.getLogger(__name__)


def remove_embargo_from_case_tree(
    case_id: str,
    embargo_id: str,
    sender_actor_id: str,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiver-side embargo removal (protocol ET).

    Handles receipt of a ``Remove(EmbargoEvent)`` activity.  If the embargo
    is the active one, its register entry is terminated and every open
    proposal cancelled in one step, so EM derives ``EXITED`` (ADR-0122); no
    participant consent is written, since with no embargo in force nobody is
    bound (ADR-0118).  A ``Remove`` naming an embargo that is not in force
    changes nothing: the register cancels a proposal only with a
    termination or on a threat signal.
    Always commits a canonical ledger entry when the executing actor holds
    the ``CASE_MANAGER`` role (via the guarded commit subtree).

    The inner ``TeardownIfActive`` Selector skips the teardown when there is
    nothing to tear down: the embargo is not the active one, or the EM state
    is already EXITED.  Only those two
    guards fall back.  A teardown step that fails fails the tree, so the
    handler can report it instead of mistaking it for "was not active"
    (#2255).

    BT returns SUCCESS when the outer Sequence completes (including when no
    teardown was needed).  BT returns FAILURE when the case is not found or a
    teardown step fails.

    Args:
        case_id: ID of the VulnerabilityCase to update.
        embargo_id: ID of the EmbargoEvent being removed.
        sender_actor_id: Sender of the ``Remove``; the Case Owner (or the
            CASE_MANAGER) at the CASE_MANAGER, the CASE_MANAGER elsewhere
            (ADR-0115, EP-09-005, PCR-03-001).
        actor_config: The CASE_MANAGER's configuration; its RSVP windows set
            the deadline of a re-issued stub Invite.  ``None`` applies the
            ``ActorConfig`` defaults.

    Returns:
        Root node of the ``RemoveEmbargoFromCaseBT`` Sequence.
    """
    teardown_if_active = py_trees.composites.Selector(
        name="TeardownIfActive",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="EmbargoWasNotActive",
                child=IsActiveEmbargoNode(
                    case_id=case_id, embargo_id=embargo_id
                ),
            ),
            py_trees.decorators.Inverter(
                name="EmbargoAlreadyExited",
                child=HasEmbargoActiveNode(case_id=case_id),
            ),
            py_trees.composites.Sequence(
                name="ActiveTeardown",
                memory=False,
                children=[
                    ClearActiveEmbargoNode(case_id=case_id),
                    SendAnnounceEmbargoEventNode(
                        case_id=case_id, embargo_id=embargo_id
                    ),
                    embargo_admission_backfill_tree(case_id, actor_config),
                ],
            ),
        ],
    )
    root = create_receive_activity_tree(
        name="RemoveEmbargoFromCaseBT",
        case_id=case_id,
        sender_guard=SenderMayAssertEmbargoNode(
            case_id=case_id,
            sender_actor_id=sender_actor_id,
            manager_arm=SenderEntitlementKind.CASE_OWNER,
        ),
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        replica_effects=[teardown_if_active],
        replica_emit_exemption=EMBARGO_TEARDOWN_ANNOUNCE,
    )
    logger.info(
        "Created RemoveEmbargoFromCaseBT for case=%s embargo=%s",
        case_id,
        embargo_id,
    )
    return root


def add_embargo_to_case_tree(
    case_id: str,
    embargo_id: str,
    sender_actor_id: str,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiver-side embargo activation (protocol EA).

    Handles receipt of an ``Add(EmbargoEvent)`` activity.  Sets the embargo
    as active on the case, transitions EM → ACTIVE, and commits a canonical
    ledger entry. As the CASE_MANAGER it then backfills any participant the
    newly active embargo admits (CM-10-006).

    BT returns SUCCESS when the embargo is activated.
    Always commits the ledger entry regardless of BT result.

    Args:
        case_id: ID of the VulnerabilityCase to update.
        embargo_id: ID of the EmbargoEvent being activated.
        sender_actor_id: Sender of the ``Add``; the Case Owner (or the
            CASE_MANAGER) at the CASE_MANAGER, the CASE_MANAGER elsewhere
            (ADR-0115, EP-09-005, PCR-03-001).
        actor_config: The CASE_MANAGER's configuration; its RSVP windows set
            the deadline of a re-issued stub Invite.  ``None`` applies the
            ``ActorConfig`` defaults.

    Returns:
        Root node of the ``AddEmbargoToCaseBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="AddEmbargoToCaseBT",
        case_id=case_id,
        sender_guard=SenderMayAssertEmbargoNode(
            case_id=case_id,
            sender_actor_id=sender_actor_id,
            manager_arm=SenderEntitlementKind.CASE_OWNER,
        ),
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        replica_effects=[
            SetEmbargoActiveNode(
                case_id=case_id,
                embargo_id=embargo_id,
                transition_mode=TransitionMode.OBSERVED,
            ),
        ],
        # Activating a revision can admit a participant that had already
        # accepted it, after the Add entry was fanned out (CM-10-006).
        manager_effects=[
            BackfillAdmittedParticipantsNode(case_id=case_id),
            # The activation can change the terms of a stub Invite still
            # outstanding (CM-11-016).
            ReissueStubInvitesNode(case_id=case_id, actor_config=actor_config),
        ],
        manager_case_id=case_id,
        manager_gate_name="EmbargoAdmissionBackfill",
    )
    logger.info(
        "Created AddEmbargoToCaseBT for case=%s embargo=%s",
        case_id,
        embargo_id,
    )
    return root


def _index_received_proposal(
    case_id: str, embargo_id: str, invite_id: str
) -> IndexReceivedEmbargoProposalNode:
    """The DL-06 proposal index, last in whichever Invite arm runs.

    The two arms of ``invite_to_embargo_on_case_tree`` are mutually exclusive
    and between them cover every receiver, so each ends with its own index
    node: the index is written only once the Invite has been applied, as the
    accept/reject triggers and the idempotency guard expect.
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
    embargo: EmbargoEvent | None = None,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiving an embargo proposal or invitation (EP / EV).

    Handles receipt of an ``Invite(EmbargoEvent)`` activity.  The tree has
    two mutually exclusive arms behind the shared intake and guarded commit,
    because the same wire message means two different things depending on
    who receives it (ADR-0113):

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
    refused by a read-only guard ahead of the commit (CLP-10-009); the P/X/A
    refusal with ER (EMB-01-002, EMB-03-003) is the use case's pre-flight.
    The CM-24 authorship pair comes from the shared ``delegated_authorship``
    helper (CM-24-005): the relay runs only under the role gate, so ``actor``
    is the role holder, and ``attributedTo`` is the proposer.

    **Either arm is preceded by an idempotency guard**: the same Invite
    delivered again (``pending_embargo_proposal_index`` already maps the
    embargo to this Invite's id) commits nothing and the handler reports it
    as a repeat (CLP-13-001, HP-01-003).  Each arm ends by writing that
    index (DL-06), so it is written only once the Invite has been applied in
    whichever arm ran.  The participant-replica arm sits in
    ``replica_effects`` and so runs before the factory's CASE_MANAGER gate;
    the two arms are mutually exclusive on the same role check, and neither
    changes who holds the role, so their order does not matter.

    **A participant replica stores and answers** the Invite addressed to it
    and writes nothing else (EP-09-003).  The intake stores the Invite; when
    the executing actor is its addressee, the EMB-15 response decision
    (``create_embargo_response_decision_tree``) queues an ``Accept`` or
    ``Reject`` of it to the CASE_MANAGER (``SendEmbargoInviteAnswerNode``).
    No EM state and no consent state moves here: the replica learns the
    proposal, the relayed Invite and every answer from the CASE_MANAGER's
    committed entries, which ``create_announce_log_entry_tree`` replays
    (EP-09-007, RSH-08-004).  An Invite that reached a store other than its
    addressee's is stored and left unanswered.

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
        embargo: The inline ``EmbargoEvent`` the message carries, persisted
            by the intake in whichever store receives the Invite (CLP-10-017);
            ``None`` when the message named its object by bare URI.
        actor_config: The executing CASE_MANAGER's configuration; its RSVP
            windows set each relayed Invite's ``endTime`` (CM-28-012).
            ``None`` applies the ``ActorConfig`` defaults.

    Returns:
        Root node of the ``InviteToEmbargoOnCaseBT`` Sequence.
    """
    # The intake stores the Invite and the embargo it carries, in every store:
    # the store keeps the Invite's object by reference, so without the
    # EmbargoEvent it could not read the Invite back whole to adjudicate or
    # answer it.  Storing the object moves no EM or consent state (EP-09-003).
    intake: list[py_trees.behaviour.Behaviour] = [CreateAndStoreInviteNode()]
    if embargo is not None:
        intake.append(PersistEmbargoEventNode(embargo=embargo))
    adjudication: list[py_trees.behaviour.Behaviour] = [
        CollectEmbargoInviteRecipientsNode(
            case_id=case_id, proposer_id=proposer_id
        ),
        ProposeEmbargoLifecycleNode(
            case_id=case_id,
            embargo_id=embargo_id,
            result_out={},
            proposer_id=proposer_id,
        ),
        RelayEmbargoInviteToEachNode(
            case_id=case_id,
            embargo_id=embargo_id,
            proposer_id=proposer_id,
            actor_config=actor_config,
        ),
        # EP-09-002: the relay skips the manager, so it writes its own row.
        record_manager_embargo_consent_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            proposer_id=proposer_id,
        ),
    ]
    root = create_receive_activity_tree(
        name="InviteToEmbargoOnCaseBT",
        case_id=case_id,
        sender_guard=SenderMayAssertEmbargoNode(
            case_id=case_id,
            sender_actor_id=sender_actor_id,
            manager_arm=SenderEntitlementKind.ACTIVE_PARTICIPANT,
        ),
        precondition_guards=[
            EmbargoProposalNotYetRecordedNode(
                case_id=case_id, embargo_id=embargo_id, invite_id=invite_id
            ),
            case_manager_admits_proposal_guard(case_id=case_id),
        ],
        replica_effects=[
            *intake,
            create_participant_replica_gated_tree(
                name="AnswerInviteOnReplica",
                case_id=case_id,
                children=[
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
                                    SenderIsCaseOwnerNode(
                                        sender_actor_id=invitee_id,
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
                ],
                body_name="AnswerInviteOnReplicaBody",
            ),
        ],
        replica_emit_exemption=EMBARGO_INVITE_ANSWER,
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
