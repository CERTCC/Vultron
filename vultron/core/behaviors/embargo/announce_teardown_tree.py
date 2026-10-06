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
    ├─ RemoveFromProposedEmbargoesNode    # idempotent proposed-list cleanup
    └─ TeardownIfActive (Selector)        # skip when there is nothing to tear down
       ├─ EmbargoWasNotActive (Inverter)  # not the active embargo (only proposed)
       │  └─ IsActiveEmbargoNode
       ├─ EmbargoAlreadyExited (Inverter) # EM state already EXITED
       │  └─ HasEmbargoActiveNode
       └─ ActiveTeardown (Sequence)       # its FAILURE is the tree's FAILURE
          ├─ ClearActiveEmbargoNode       # ACTIVE/REVISE→EXITED + clear active_embargo
          ├─ ExitParticipantConsentNode  # exit all participant PEC to UNBOUND_EXITED
          ├─ SendAnnounceEmbargoEventNode # emit Announce(EmbargoEvent) to CaseActor
          └─ EmbargoAdmissionBackfill     # CASE_MANAGER: backfill paused peers (CM-10-006)

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

import logging

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
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
    ExitParticipantConsentNode,
    HasEmbargoActiveNode,
    IsActiveEmbargoNode,
    OwnerMayAutoAcceptEmbargoNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    RelayEmbargoInviteToEachNode,
    RemoveFromProposedEmbargoesNode,
    SendAnnounceEmbargoEventNode,
    SendEmbargoInviteAnswerNode,
    SetEmbargoActiveNode,
    ValidateCaseExistsNode,
    case_manager_admits_proposal_guard,
)
from vultron.core.behaviors.embargo.response_decision_tree import (
    create_embargo_response_decision_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderIsCaseOwnerNode
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.services.embargo_lifecycle import TransitionMode

logger = logging.getLogger(__name__)


def embargo_admission_backfill_tree(
    case_id: str,
) -> py_trees.behaviour.Behaviour:
    """Backfill the participants an embargo effect just admitted (CM-10-006).

    The admitting entry was committed and fanned out before the effect ran, so
    the fan-out withheld it; this sends it, and everything else withheld, once
    the gate admits the participant. CASE_MANAGER only (BT-17-001): the pause
    records and the canonical ledger live in its store.
    """
    return create_case_manager_gated_tree(
        name="EmbargoAdmissionBackfill",
        case_id=case_id,
        children=[BackfillAdmittedParticipantsNode(case_id=case_id)],
    )


def remove_embargo_from_case_tree(
    case_id: str,
    embargo_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiver-side embargo removal (protocol ET).

    Handles receipt of a ``Remove(EmbargoEvent)`` activity.  Removes the
    embargo from ``proposed_embargoes`` (idempotent) and, if the embargo is
    the active one, applies the ACTIVE/REVISE → EXITED EM state transition,
    clears ``active_embargo``, and exits participant embargo consent to the
    terminal ``UNBOUND_EXITED`` (ADR-0118).
    Always commits a canonical ledger entry when the executing actor holds
    the ``CASE_MANAGER`` role (via the guarded commit subtree).

    The inner ``TeardownIfActive`` Selector skips the teardown when there is
    nothing to tear down: the embargo was only in ``proposed_embargoes`` (not
    the active embargo), or the EM state is already EXITED.  Only those two
    guards fall back.  A teardown step that fails fails the tree, so the
    handler can report it instead of mistaking it for "was not active"
    (#2255).

    BT returns SUCCESS when the outer Sequence completes (including when no
    teardown was needed).  BT returns FAILURE when the case is not found or a
    teardown step fails.

    Args:
        case_id: ID of the VulnerabilityCase to update.
        embargo_id: ID of the EmbargoEvent being removed.

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
                    ExitParticipantConsentNode(case_id=case_id),
                    SendAnnounceEmbargoEventNode(
                        case_id=case_id, embargo_id=embargo_id
                    ),
                    embargo_admission_backfill_tree(case_id),
                ],
            ),
        ],
    )
    root = create_receive_activity_tree(
        name="RemoveEmbargoFromCaseBT",
        case_id=case_id,
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        effect_nodes=[
            RemoveFromProposedEmbargoesNode(
                case_id=case_id, embargo_id=embargo_id
            ),
            teardown_if_active,
        ],
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

    Returns:
        Root node of the ``AddEmbargoToCaseBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="AddEmbargoToCaseBT",
        case_id=case_id,
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        effect_nodes=[
            SetEmbargoActiveNode(
                case_id=case_id,
                embargo_id=embargo_id,
                transition_mode=TransitionMode.OBSERVED,
            ),
            # Activating a revision can admit a participant that had already
            # accepted it, after the Add entry was fanned out (CM-10-006).
            embargo_admission_backfill_tree(case_id),
        ],
    )
    logger.info(
        "Created AddEmbargoToCaseBT for case=%s embargo=%s",
        case_id,
        embargo_id,
    )
    return root


def invite_to_embargo_on_case_tree(
    case_id: str,
    invitee_id: str,
    invite_id: str,
    *,
    embargo_id: str,
    proposer_id: str,
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
    as a repeat (CLP-13-001, HP-01-003).

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
    ]
    root = create_receive_activity_tree(
        name="InviteToEmbargoOnCaseBT",
        case_id=case_id,
        precondition_guards=[
            EmbargoProposalNotYetRecordedNode(
                case_id=case_id, embargo_id=embargo_id, invite_id=invite_id
            ),
            case_manager_admits_proposal_guard(case_id=case_id),
        ],
        effect_nodes=[
            *intake,
            create_case_manager_gated_tree(
                name="AdjudicateEmbargoProposal",
                case_id=case_id,
                children=adjudication,
            ),
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
                ],
            ),
        ],
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
