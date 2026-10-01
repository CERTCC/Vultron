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
except the proposer (``RelayEmbargoInviteToEachNode``, ``nodes/relay.py``); any
other store records the Invite on its replica.  The tree's docstring draws it.

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
          ├─ ResetParticipantConsentNode  # reset all participant PEC to UNBOUND
          └─ SendAnnounceEmbargoEventNode # emit Announce(EmbargoEvent) to CaseActor

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    ClearActiveEmbargoNode,
    CollectEmbargoInviteRecipientsNode,
    CreateAndStoreInviteNode,
    EmbargoProposalNotYetRecordedNode,
    HasEmbargoActiveNode,
    IsActiveEmbargoNode,
    OptionalLookupParticipantNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
    RelayEmbargoInviteToEachNode,
    RemoveFromProposedEmbargoesNode,
    ResetParticipantConsentNode,
    SendAnnounceEmbargoEventNode,
    SetEmbargoActiveNode,
    UpdateParticipantEmbargoPecNode,
    ValidateCaseExistsNode,
    case_manager_admits_proposal_guard,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.services.embargo_lifecycle import TransitionMode
from vultron.core.states.participant_embargo_consent import PEC_Trigger

logger = logging.getLogger(__name__)


def remove_embargo_from_case_tree(
    case_id: str,
    embargo_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiver-side embargo removal (protocol ET).

    Handles receipt of a ``Remove(EmbargoEvent)`` activity.  Removes the
    embargo from ``proposed_embargoes`` (idempotent) and, if the embargo is
    the active one, applies the ACTIVE/REVISE → EXITED EM state transition,
    clears ``active_embargo``, and resets participant embargo consent states.
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
                    ResetParticipantConsentNode(case_id=case_id),
                    SendAnnounceEmbargoEventNode(
                        case_id=case_id, embargo_id=embargo_id
                    ),
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
    ledger entry.

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
    pec_result_out: dict[str, object] | None = None,
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
    The CM-24 authorship invariants hold structurally — the relay runs only
    under the role gate, so ``actor`` is the role holder — rather than through
    the trigger-side ``_prepare_delegated_context()`` helper, which a BT node
    may not import (BTND-04-003) and whose fallback arm ADR-0113 retires.

    **Either arm is preceded by an idempotency guard**: the same Invite
    delivered again (``pending_embargo_proposal_index`` already maps the
    embargo to this Invite's id) commits nothing and the handler reports it
    as a repeat (CLP-13-001, HP-01-003).

    **A participant replica records** the Invite addressed to it: the
    invitee's participant record is looked up leniently and PEC ``INVITE``
    applied where legal — a ``SIGNATORY`` asked about a revision keeps its
    state and the tree succeeds (EP-09-004).  This on-receipt write is the
    pre-relay behaviour retained until the replica apply node for the
    manager's Invite commit lands (RSH-08-004, #3915); EP-09-003 then gates
    it off.

    Args:
        case_id: ID of the VulnerabilityCase.
        invitee_id: Actor ID of the invitee (the Invite's sole ``to``).
        invite_id: ID of the received Invite activity.
        embargo_id: ID of the proposed ``EmbargoEvent`` (the Invite's object).
        proposer_id: Actor whose terms these are — the Invite's ``actor``, or
            its ``attributedTo`` when the proposal was itself relayed.
        embargo: The inline ``EmbargoEvent`` the message carries, persisted
            in the manager's store before adjudication; ``None`` when the
            message named its object by bare URI.
        pec_result_out: Receives the replica arm's ``pec_before`` /
            ``pec_changed`` so the handler can report a repeat as SKIPPED.

    Returns:
        Root node of the ``InviteToEmbargoOnCaseBT`` Sequence.
    """
    adjudication: list[py_trees.behaviour.Behaviour] = []
    if embargo is not None:
        adjudication.append(PersistEmbargoEventNode(embargo=embargo))
    adjudication.extend(
        [
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
            ),
        ]
    )
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
            CreateAndStoreInviteNode(),
            create_case_manager_gated_tree(
                name="AdjudicateEmbargoProposal",
                case_id=case_id,
                children=adjudication,
            ),
            create_participant_replica_gated_tree(
                name="RecordInviteOnReplica",
                case_id=case_id,
                children=[
                    OptionalLookupParticipantNode(
                        case_id=case_id, target_actor_id=invitee_id
                    ),
                    UpdateParticipantEmbargoPecNode(
                        pec_trigger=PEC_Trigger.INVITE,
                        where_legal=True,
                        result_out=pec_result_out,
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


def accept_invite_to_embargo_tree(
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    invite_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for accepting embargo invitation (protocol EA).

    Handles receipt of an ``Accept(InviteToEmbargoOnCase)`` activity.
    Records the acceptance via EmbargoLifecycle and commits a canonical
    ledger entry.

    BT returns SUCCESS when acceptance is recorded.
    Always commits the ledger entry regardless of BT result.

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the EmbargoEvent being accepted.
        accepting_actor_id: Actor ID of the participant accepting.
        invite_id: ID of the InviteToEmbargoOnCase activity.

    Returns:
        Root node of the ``AcceptInviteToEmbargoBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="AcceptInviteToEmbargoBT",
        case_id=case_id,
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        effect_nodes=[
            RecordParticipantAcceptanceNode(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
            ),
        ],
    )
    logger.info(
        "Created AcceptInviteToEmbargoBT for case=%s embargo=%s"
        " accepting_actor=%s",
        case_id,
        embargo_id,
        accepting_actor_id,
    )
    return root


def reject_invite_to_embargo_tree(
    case_id: str,
    rejecting_actor_id: str,
    invite_id: str,
    embargo_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for rejecting embargo invitation (protocol ER / EJ).

    Handles receipt of a ``Reject(InviteToEmbargoOnCase)`` activity.  Records
    the rejecting participant's consent through
    :class:`RecordParticipantRejectionNode`, which applies the same
    MSM-07-004 rule as ``EmbargoLifecycle.reject_embargo_invite`` (ADR-0093):
    a Reject naming the case's *active* embargo is consent withdrawal
    (``DECLINE`` from any state, ``SIGNATORY`` included); one naming a
    *proposed* embargo drops the id from ``accepted_embargo_ids`` and
    declines only a participant not yet ``SIGNATORY``; the owner's EJ changes
    nobody's record.  When the rejecting actor is the case owner the Reject
    *decides* the proposal, so this replica also forgets it as an open
    proposal (EP-08-003) — the received Accept path prunes through
    ``accept_embargo_invite`` and the Reject path must not lag it, or a later
    default selection here would still see the rejected terms.

    Commits the ledger entry before the effects (CLP-10-006); a Reject naming
    an embargo the case knows nothing about fails the effect, so the handler
    reports a refusal.

    Args:
        case_id: ID of the VulnerabilityCase.
        rejecting_actor_id: Actor ID of the participant rejecting.
        invite_id: ID of the InviteToEmbargoOnCase activity.
        embargo_id: ID of the EmbargoEvent the Reject names (required: which
            terms are refused decides the consent effect, MSM-07-004).

    Returns:
        Root node of the ``RejectInviteToEmbargoBT`` Sequence.
    """
    effect_nodes: list[py_trees.behaviour.Behaviour] = [
        # The consent belongs to the actor who rejected, not to whoever's
        # replica this is: a Reject routes through the CASE_MANAGER (PCR-08),
        # so recording against the BT execution actor would decline the
        # manager's own consent instead.
        RecordParticipantRejectionNode(
            case_id=case_id,
            embargo_id=embargo_id,
            rejecting_actor_id=rejecting_actor_id,
        ),
        # The owner's Reject decides the proposal; a participant's is consent
        # and prunes nothing (EP-08-003, #3470).
        RemoveFromProposedEmbargoesNode(
            case_id=case_id,
            embargo_id=embargo_id,
            decided_by=rejecting_actor_id,
        ),
    ]
    root = create_receive_activity_tree(
        name="RejectInviteToEmbargoBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=effect_nodes,
    )
    logger.info(
        "Created RejectInviteToEmbargoBT for case=%s rejecting_actor=%s"
        " invite=%s",
        case_id,
        rejecting_actor_id,
        invite_id,
    )
    return root
