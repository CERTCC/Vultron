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

"""The ``Create(CaseProposal)`` received-tree factory (CP-05, ADR-0041)."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.call_out.bundles.case_proposal import (
    CASE_PROPOSAL_DETERMINISTIC,
)
from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.proposal_admission_conditions import (
    CheckDeclineRecordExistsNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.offer_provenance import (
    offer_provenance_from_proposal,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.replica_emit_exemptions import CASE_PROPOSAL
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    AuthoredCaseProposal,
    SenderCheckContext,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.predicates.addressing import normalise_actor_id
from vultron.enums.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.case_proposal import (
        CaseProposalCallOutBundle,
    )
from vultron.core.behaviors.case.case_proposal_received_tree.arms import (
    create_case_from_proposal_act,
    decline_closed_case_proposal_arm,
    decline_proposal_arm,
)


def create_case_proposal_received_tree(
    report_id: str | None,
    proposal_id: str | None,
    proposer_uri: str,
    proposal_dict: dict | None = None,
    actor_config: ActorConfig | None = None,
    inline_report: VulnerabilityReport | None = None,
    call_out: "CaseProposalCallOutBundle | None" = None,
    proposer_case_roles: Sequence[CVDRole] = (),
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Return the received-side BT for processing a ``Create(CaseProposal)``.

    The tree is a Sequence of intake (CLP-10-017), the sender guard the
    factory composes from *sender_rule*, and a four-branch Selector: the
    CP-05-006 already-declined answer, the closed-case decline, the CP-05-002
    admission decision, and the accept flow.

    **Branch 1 — already declined** (``CheckDeclineRecordExistsNode``):
      A ``CaseProposalDeclineRecord`` exists, so the decision stands and the
      call-out point is not consulted again — a retrying proposer is not sent a
      fresh ``Reject`` per delivery, and a stateful or stochastic backend cannot
      accept what it previously refused.  The record commits in the same
      transaction as the ``Reject`` it answers with, so "declined with nothing
      queued" is not a state the store can hold.

    **Branch 2 — closed case** (``DeclineClosedCaseProposalArm``, CP-05-014,
    CP-05-018, CM-23-013):
      ``CheckProposalCaseFullyClosedNode`` finds that the proposal resolves to
      a fully closed case: the proposer's own case for *report_id* (a new
      proposal id from the owner), or the case the proposal's stored
      ``Accept`` names (a redelivery of the original proposal).  The arm
      records the decline, with ``CLOSED_CASE_DECLINE_REASON``, and emits
      ``Reject(CaseProposal)``, both in one ``RefusalActTransaction``.  It
      writes nothing for the case: no ``CaseLedgerEntry`` and no case or
      participant change.  The decline record is keyed on the proposal, so
      CM-23-013 does not bar it.  The ``Reject`` declines only this delivery
      and does not revoke a stored ``Accept`` (CP-05-012).  The closure check
      raises on a store error, and a failed decline fails the tree, so
      neither can fall through into an accept that reuses the closed case.
      The admission call-out point is not consulted.

    **Branch 3 — decline** (``DeclineProposalArm``, CP-05-002, CP-05-004):
      Runs the ``EvaluateCaseProposal`` admission call-out point and, when it
      refuses, records the decline and emits ``Reject(CaseProposal)`` in one
      ``RefusalActTransaction``.  Three properties are load-bearing:

      * It sits **before** the accept flow, so a refusal happens ahead of every
        write.  A Reject emitted after the accept flow's effects would report
        "declined" while this store held a case with committed ledger entries
        (CLP-10-009).  ``CheckProposalAlreadyAnsweredNode`` extends that to
        *later* deliveries via the proposal-keyed ``CaseProposalAdmissionRecord``
        the accept flow writes first.
      * Its guards are keyed on the **proposal**, never the report.  ``report_id``
        comes from the report the sender embedded, so a report-keyed guard is one
        a sender can satisfy on purpose and thereby skip the gate entirely.
      * Everything in this arm **raises** instead of returning FAILURE when it
        cannot do its job: the guards ahead of the decision, and the decline
        itself, whose ``RefusalActTransaction`` rolls back and raises.  A
        Selector falls through on FAILURE, so for a node in a refusal arm "I
        could not tell" and "no" both mean *admit*; only ``BTBridge`` failing
        the whole tree is safe.

    **Branch 4 — accept** (``CreateCaseFromProposalAct``), one
    ``ActTransaction`` (ADR-0146):
      First ``RecordProposalAdmissionNode`` stamps the proposal-keyed admission
      record, before any case exists.  Then a sub-Selector resolves which
      ``VulnerabilityCase`` to use:

      * ``LoadExistingCaseNode`` (AC-1/AC-2): if *proposer_uri* already owns a
        case for *report_id* (CP-05-008), or the proposal's stored ``Accept``
        names a case (a redelivery, CP-05-006, also from a former owner after
        an ownership transfer, #4650), write its ID to the blackboard and
        succeed; another proposer's case for the report is not reused.  It
        resolves the case with ``proposal_case_ids``, as branch 2 does, and a
        fully closed case never reaches it: branch 2 declines it.
      * ``CreateCaseFromProposalNode`` (normal path): create a new case,
        attributed to *proposer_uri*, which becomes the CASE_OWNER
        (CP-09-001).

      Then CaseActor-native initialization steps (ADR-0041):

      3. ``AddCaseActorParticipantNode`` — CaseActor registered as
         COORDINATOR + CASE_MANAGER (ADR-0041)
      4. ``AddOwnerParticipantNode`` — proposing actor added as
         CASE_OWNER (plus *proposer_case_roles*) at RM.RECEIVED
         (ADR-0041 AC-1, CP-09-007); skipped for a proposer that no longer
         owns the case it resolved to, so a former owner's redelivery does
         not make it CASE_OWNER again (CM-21-001)
      5. ``AddReporterParticipantNode`` — reporter added at RM.ACCEPTED
         (ADR-0041 AC-2)
      6. ``InitializeDefaultEmbargoNode`` — default embargo initialized
         (ADR-0041 AC-3); its ``InitializeCreationEmbargoNode`` seeds the case
         owner (``attributed_to``, the CASE_OWNER) as an embargo signatory
         (CM-14-003) and registers a contested creation's losing terms as a
         revision (EP-04-016)
      7. ``SeedReporterSignatoryNode`` — reporter seeded as embargo
         signatory (CM-14-005); implicit consent per ADR-0048

      Then the outbound messaging steps:

      8. ``EmitAcceptCaseProposalNode`` — emits Accept(CaseProposal)
      9. ``EmitCreateVulnerabilityCaseNode`` — emits
         Create(VulnerabilityCase) with the case inline (ADR-0041 AC-5),
         under an id derived from the proposal (OX-06-002); skipped by
         ``CheckCaseAlreadyAnnouncedNode`` for a case already announced

      Then, last of all:

      10. ``CommitNativeLedgerEntriesNode`` — canonical ledger entries
         committed (ADR-0041 AC-4).  Each commit fans out through the FIFO
         outbox, so it runs after the Create: every recipient must hold the
         case object before its first ``Announce(CaseLedgerEntry)`` arrives
         (CM-14-011, CP-09-009), or it enters the SYNC-15 pre-genesis
         reject/replay path on the normal case-creation route (#3033, #2898).
      11. ``RelayCreationTimeRevisionNode`` — relays the revision step 6
         registered, if any, as ``Invite(EmbargoEvent)`` to the party
         whose terms won (EP-04-011), and indexes the sent Invite
         (EP-08-002); no modification precedes step 10 (CM-14-014).

    If any of them fails, nothing they wrote is kept: no case, participant,
    embargo, ledger entry, ``Accept``, ``Create`` or ``Invite``, and delivery
    is told of none of the activities (DL-02-004).  A redelivery of the
    proposal then processes it fresh.  Once the act commits, the durable
    outbox retries the delivery of each queued activity (OX-13, CP-05-011).

    Spec: CP-05-001 through CP-05-006, CP-05-008.
    Per: ``docs/adr/0041-caseactor-authoritative-case-initialization.md``.

    A proposal with no id is refused by the same tree's guard instead
    (``ActivityIncompleteNode``): every branch above is keyed on the
    proposal, so there is nothing to judge, yet the delivery still runs one
    tree and is archived (CLP-10-005, CLP-10-018).

    Args:
        report_id: URI of the VulnerabilityReport embedded in the proposal
            (CP-01-004). Pass ``None`` if the report URI could not be
            extracted — the case will be created without a report link.
        proposal_id: URI of the ``as_CaseProposal`` object; ``None`` when
            the proposal names none.
        proposer_uri: URI of the proposing actor — the report receiver — to
            whom the responses are sent.  It is normalised with
            ``normalise_actor_id``, so a trailing slash names the same
            proposer and nothing is stored under the slash spelling (#4772).
            If the proposal is admitted, it becomes the case's CASE_OWNER:
            the new case is attributed to it (CP-09-001) and it is the
            participant given ``CVDRole.CASE_OWNER``.  A declined proposer
            owns nothing, so the nodes that run before the case exists name
            it the proposer.
        proposal_dict: The proposal's AS2 rendering (from ``WireRenderPort``).
            When supplied, the Accept's ``object_`` carries the full inline proposal,
            satisfying CP-05-009 and the AKM-03-003 outbox requirement. Falls back
            to bare URI when ``None``. It is also where the report's offer
            provenance arrives (``offerId``/``offerActorId``, CP-01-007), which
            the ``add_report_to_case`` ledger entry needs and this CaseActor
            cannot look up for itself.
        actor_config: Optional configuration of the CaseActor itself.  Its
            ``protocol_default_embargo_duration`` is the fallback embargo
            when no actor default applies (EP-04-019); ``None`` uses the
            ``ActorConfig`` default.  It says nothing about the proposer, so
            its ``default_case_roles`` are not read (ADR-0133).
        call_out: Bundle supplying the ``EvaluateCaseProposal`` admission
            call-out point.  Defaults to ``CASE_PROPOSAL_DETERMINISTIC``, whose
            backend always succeeds, so an unconfigured deployment admits every
            well-formed proposal exactly as it did before this seam existed
            (BT-23-001, BT-23-011).
        proposer_case_roles: The CVD roles the proposer stated on the proposal
            (CP-01-011), given to it alongside ``CVDRole.CASE_OWNER``
            (CP-09-007).  Empty gives ``CVDRole.CASE_OWNER`` only.
        sender_rule: The use case's declared sender rule; the factory
            composes the guard from it, with the proposal as the object an
            ``AUTHOR`` sender must have written.  The proposal id is the
            sender's choice, so a proposal id this store recorded for another
            proposer is refused before any arm runs (CP-05-010, HP-01-008).

    Returns:
        The root ``Sequence`` (intake, then the idempotency Selector), ready
        for ``BTBridge.execute_with_setup``.
    """
    if proposal_id is None:
        return create_incomplete_activity_received_tree(
            "CreateCaseProposalReceivedBT",
            "Create(CaseProposal) carries no proposal id",
        )
    bundle = call_out if call_out is not None else CASE_PROPOSAL_DETERMINISTIC

    # The sender wrote this id; from here on it is the proposer's identity,
    # which the tree stores and looks up.  Every node below gets the canonical
    # spelling, so the sender guard's ``same_actor_id`` and the accept path's
    # lookups agree on who the proposer is (#4772).
    proposer_uri = normalise_actor_id(proposer_uri)

    offer_id, offer_actor_id = offer_provenance_from_proposal(proposal_dict)

    creation_act = create_case_from_proposal_act(
        report_id=report_id,
        proposal_id=proposal_id,
        proposer_uri=proposer_uri,
        proposal_dict=proposal_dict,
        actor_config=actor_config,
        inline_report=inline_report,
        proposer_case_roles=proposer_case_roles,
        offer_id=offer_id,
        offer_actor_id=offer_actor_id,
    )
    closed_case_arm = decline_closed_case_proposal_arm(
        report_id=report_id,
        proposal_id=proposal_id,
        proposer_uri=proposer_uri,
        proposal_dict=proposal_dict,
    )
    decline_arm = decline_proposal_arm(
        proposal_id=proposal_id,
        proposer_uri=proposer_uri,
        proposal_dict=proposal_dict,
        bundle=bundle,
    )

    # Intake runs ahead of the whole Selector, so every arm, a decline
    # included, leaves the archived Create(CaseProposal) (CLP-10-017,
    # CLP-10-018).  No commit stage (``case_id=None``): the case does not
    # exist yet, and the accept arm's CommitNativeLedgerEntriesNode ledgers
    # the facts it creates (ADR-0041 AC-4).
    return create_receive_activity_tree(
        name="CreateCaseProposalReceivedBT",
        # The proposal is what brings the case into being, so the first
        # delivery lands on the no-case path (HP-01-041, CP-09-001); a
        # redelivery lands at the CASE_MANAGER of the case this actor then
        # created, where the idempotency arms answer it afresh (HP-01-038).
        paths={ReceivedPath.NO_CASE, ReceivedPath.CASE_MANAGER},
        case_id=None,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=proposer_uri,
            authored_object=AuthoredCaseProposal(proposal_id=proposal_id),
        ),
        precondition_guards=[],
        replica_emit_exemption=CASE_PROPOSAL,
        replica_effects=[
            py_trees.composites.Selector(
                name="CreateCaseProposalIdempotencySelector",
                memory=False,
                children=[
                    CheckDeclineRecordExistsNode(proposal_id=proposal_id),
                    closed_case_arm,
                    decline_arm,
                    creation_act,
                ],
            )
        ],
    )
