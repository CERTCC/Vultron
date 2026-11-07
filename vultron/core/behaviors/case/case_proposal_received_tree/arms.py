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

"""The arms of the ``Create(CaseProposal)`` received tree (CP-05).

Built by :func:`~vultron.core.behaviors.case.case_proposal_received_tree.factory.create_case_proposal_received_tree`,
in the order its idempotency Selector tries them after the already-declined
check: the closed-case decline, the admission decline and the accept act.
Each decline records its decision and emits its ``Reject`` in one
``RefusalActTransaction``, so a failed decline fails the tree rather than
falling through to the accept arm.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.act_transaction import (
    ActTransaction,
    RefusalActTransaction,
)
from vultron.core.behaviors.case.embargo_tree import (
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.nodes.embargo_revision_relay import (
    RelayCreationTimeRevisionNode,
)
from vultron.core.behaviors.case.nodes.proposal_admission_actions import (
    EmitRejectCaseProposalNode,
    RecordProposalAdmissionNode,
    RecordProposalDeclineNode,
)
from vultron.core.behaviors.case.nodes.proposal_admission_conditions import (
    CheckProposalAlreadyAnsweredNode,
    CheckProposalCaseFullyClosedNode,
)
from vultron.core.behaviors.case.nodes.proposal_announcement import (
    CheckCaseAlreadyAnnouncedNode,
)
from vultron.core.behaviors.case.nodes.proposal_case_resolution import (
    CreateCaseFromProposalNode,
    LoadExistingCaseNode,
    StoreProposalReportNode,
)
from vultron.core.behaviors.case.nodes.proposal_consent import (
    SeedReporterSignatoryNode,
)
from vultron.core.behaviors.case.nodes.proposal_emits import (
    EmitAcceptCaseProposalNode,
    EmitCreateVulnerabilityCaseNode,
)
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CommitNativeLedgerEntriesNode,
)
from vultron.core.behaviors.case.nodes.proposal_participants import (
    AddCaseActorParticipantNode,
    AddOwnerParticipantNode,
)
from vultron.core.behaviors.case.nodes.proposal_reporter import (
    AddReporterParticipantNode,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.enums.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.case_proposal import (
        CaseProposalCallOutBundle,
    )


CLOSED_CASE_DECLINE_REASON = (
    "The case for this proposal is fully closed; nothing more will be done"
    " for this proposal."
)
"""The ``Reject`` summary for a proposal whose case is fully closed.

It declines the delivery only: an ``Accept`` already sent for the proposal
stands (CP-05-012, CP-05-014).
"""


def create_case_from_proposal_act(
    *,
    report_id: str | None,
    proposal_id: str,
    proposer_uri: str,
    proposal_dict: dict | None,
    actor_config: ActorConfig | None,
    inline_report: VulnerabilityReport | None,
    proposer_case_roles: Sequence[CVDRole],
    offer_id: str | None,
    offer_actor_id: str | None,
) -> ActTransaction:
    """Build ``CreateCaseFromProposalAct``, the accept arm, as one act (ADR-0146)."""
    # Sub-Selector: reuse existing case (duplicate) OR create new (normal path)
    case_resolution = py_trees.composites.Selector(
        name="ResolveCaseIdSelector",
        memory=False,
        children=[
            LoadExistingCaseNode(
                report_id=report_id,
                owner_id=proposer_uri,
                proposal_id=proposal_id,
            ),
            CreateCaseFromProposalNode(
                report_id=report_id, owner_id=proposer_uri
            ),
        ],
    )

    # The creation is one act (ADR-0146, CLP-07-015): everything from the
    # admission record to the creation-time revision relay is written in one
    # ActTransaction, so any failure rolls back the case, its records, the
    # queued Accept, Create and Invite and every entry already committed
    # (CLP-07-013, #4442).  Delivery is told of the queued activities only
    # once the block commits (DL-02-004), so nothing about a rolled-back case
    # is ever sent, and a redelivery starts from the beginning.
    return ActTransaction(
        name="CreateCaseFromProposalAct",
        children=[
            # Ahead of case_resolution deliberately: LoadExistingCaseNode reads
            # whether the record was already stored.  The record is the
            # proposal-keyed evidence that this proposal was accepted; the case
            # itself is keyed on a report the *sender* chose.  See
            # RecordProposalAdmissionNode.
            RecordProposalAdmissionNode(
                proposal_id=proposal_id,
                proposer_uri=proposer_uri,
            ),
            case_resolution,
            # Store the inline report first: the reporter participant, its ledger
            # entry and the signatory seed are all derived from it, and each of
            # those nodes skips "best-effort" when it is missing.
            StoreProposalReportNode(
                report_id=report_id,
                proposal_dict=proposal_dict,
                inline_report=inline_report,
            ),
            # ADR-0041: register CaseActor as COORDINATOR + CASE_MANAGER
            AddCaseActorParticipantNode(),
            # ADR-0041 AC-1: add the report receiver as CASE_OWNER at RM.RECEIVED
            AddOwnerParticipantNode(
                owner_uri=proposer_uri,
                report_id=report_id,
                case_roles=proposer_case_roles,
            ),
            # ADR-0041 AC-2: add reporter at RM.ACCEPTED
            AddReporterParticipantNode(report_id=report_id),
            # ADR-0041 AC-3: initialize default embargo.  Its
            # InitializeCreationEmbargoNode seeds the case owner — the
            # CASE_OWNER this case is attributed to — as a signatory
            # (CM-14-003), the one owner-seeding path.  A contested creation
            # registers its losing terms as a revision in the same commit
            # (EP-04-016, #4142).
            InitializeDefaultEmbargoNode(
                actor_config=actor_config, report_id=report_id
            ),
            # CM-14-005: seed the reporter as an embargo signatory.
            # Reporter consent is implicit in submitting the report (ADR-0048);
            # no invitation round-trip is needed or appropriate.
            SeedReporterSignatoryNode(report_id=report_id),
            # Outbound messaging.  The case object is fully initialised at this
            # point (participants, roles, embargo — CBT-01-009), so the
            # bootstrap Create is a faithful record of a completed
            # initialisation even though the canonical ledger entries that
            # describe it are committed below.
            EmitAcceptCaseProposalNode(
                proposal_id=proposal_id,
                proposer_uri=proposer_uri,
                proposal_dict=proposal_dict,
            ),
            # A case the proposer already holds (CP-05-008), or one this
            # proposal's committed act already announced (CP-05-006), is not
            # announced a second time; the Accept above is the whole answer.
            py_trees.composites.Selector(
                name="AnnounceCaseOnce",
                memory=False,
                children=[
                    CheckCaseAlreadyAnnouncedNode(),
                    EmitCreateVulnerabilityCaseNode(
                        proposal_id=proposal_id,
                        owner_uri=proposer_uri,
                    ),
                ],
            ),
            # ADR-0041 AC-4: commit canonical ledger entries natively — AFTER
            # the emits above, deliberately.  Each commit fans its entry out to
            # every participant, and the outbox is FIFO (OX-01-002), so a commit
            # placed ahead of Create(VulnerabilityCase) hands every recipient
            # ledger entries for a case it does not hold yet: each one takes
            # the SYNC-15 pre-genesis path (buffer, Reject, from-genesis
            # replay) while the Create waits behind the whole fan-out.  That
            # queue position is what timed out the replica gates in rv and
            # rcv-reject (#3033) and congested the CaseActor outbox in rcvcv
            # (#2898).  CM-14-011 states the rule and its rationale: the
            # receiver's system must hold the case object before any
            # Announce(CaseLedgerEntry) fan-out that references it.
            CommitNativeLedgerEntriesNode(
                report_id=report_id,
                offer_id=offer_id,
                offer_actor_id=offer_actor_id,
            ),
            # EP-04-011: relay the losing terms InitializeDefaultEmbargoNode
            # registered, only now that initialization is complete
            # (CM-14-014).  Inside the act: a failed relay rolls the creation
            # back, so a redelivery creates and relays it again.
            RelayCreationTimeRevisionNode(
                proposal_id=proposal_id,
                report_id=report_id,
                actor_config=actor_config,
            ),
        ],
    )


def decline_closed_case_proposal_arm(
    *,
    report_id: str | None,
    proposal_id: str,
    proposer_uri: str,
    proposal_dict: dict | None,
) -> py_trees.composites.Sequence:
    """Build ``DeclineClosedCaseProposalArm`` (CP-05-014, CP-05-018, CM-23-013)."""
    # CP-05-014 / CP-05-018 / CM-23-013: a proposal that resolves to a fully
    # closed case — the owner's new proposal, or a redelivery of the original
    # one — is declined, and nothing is written for the case.  Ahead of the
    # admission decision: closure decides, so the call-out point is not
    # consulted, and ahead of the accept arm, which would reuse the closed
    # case.  The decline record and its Reject commit together or not at all,
    # and a failure fails the tree rather than reaching the accept arm.
    return py_trees.composites.Sequence(
        name="DeclineClosedCaseProposalArm",
        memory=False,
        children=[
            CheckProposalCaseFullyClosedNode(
                proposal_id=proposal_id,
                proposer_uri=proposer_uri,
                report_id=report_id,
            ),
            RefusalActTransaction(
                name="DeclineClosedCaseProposalAct",
                children=[
                    RecordProposalDeclineNode(
                        proposal_id=proposal_id,
                        proposer_uri=proposer_uri,
                        reason=CLOSED_CASE_DECLINE_REASON,
                    ),
                    EmitRejectCaseProposalNode(
                        proposal_id=proposal_id,
                        proposer_uri=proposer_uri,
                        proposal_dict=proposal_dict,
                    ),
                ],
            ),
        ],
    )


def decline_proposal_arm(
    *,
    proposal_id: str,
    proposer_uri: str,
    proposal_dict: dict | None,
    bundle: "CaseProposalCallOutBundle",
) -> py_trees.composites.Sequence:
    """Build ``DeclineProposalArm``, the CP-05-002 admission decision."""
    # CP-05-002 / CP-05-004 admission decision.  `Inverter` converts the
    # call-out point's "declined" FAILURE into the SUCCESS this arm needs to
    # proceed, so the Evaluator keeps the BT-18-007 contract (a refusal is a
    # FAILURE return, never a "rejected" value written alongside SUCCESS).
    return py_trees.composites.Sequence(
        name="DeclineProposalArm",
        memory=False,
        children=[
            # Keyed on the proposal, not the report: `report_id` is chosen by the
            # sender, so a report-scoped guard can be skipped by naming a report
            # this service has already seen.
            py_trees.decorators.Inverter(
                name="ProposalNotYetAnswered",
                child=CheckProposalAlreadyAnsweredNode(
                    proposal_id=proposal_id
                ),
            ),
            py_trees.decorators.Inverter(
                name="ProposalDeclined",
                child=bundle.evaluate_proposal_factory("EvaluateCaseProposal"),
            ),
            # The decision and its Reject are one act; a failure fails the
            # tree, so the Selector never tries the accept arm with a decline
            # half made.
            RefusalActTransaction(
                name="DeclineProposalAct",
                children=[
                    RecordProposalDeclineNode(
                        proposal_id=proposal_id,
                        proposer_uri=proposer_uri,
                    ),
                    EmitRejectCaseProposalNode(
                        proposal_id=proposal_id,
                        proposer_uri=proposer_uri,
                        proposal_dict=proposal_dict,
                    ),
                ],
            ),
        ],
    )
