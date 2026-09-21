"""BT tree for the CreateCaseProposal received-side use case.

Case-actor side: handles an inbound ``Create(as_CaseProposal)`` and emits
two outbound activities in sequence:

  1. ``Accept(as_CaseProposal)`` — acknowledgement to the vendor
  2. ``Create(VulnerabilityCase)`` — case announcement to the vendor

A durable ``PendingCreateCaseActivity`` marker is written to the DataLayer
after step 1 and cleared on successful completion of step 2 so that a retry
runner (#1139) can recover the obligation if delivery of step 2 fails.

The normal-path Sequence performs CaseActor-native initialization per
ADR-0041 before emitting outbound activities:

  1. Resolve (or create) the VulnerabilityCase
  2. Add the proposing actor (report receiver) as CASE_OWNER participant at
     RM.RECEIVED, with any additional roles from
     ``ActorConfig.default_case_roles`` (AC-1)
  3. Add reporter as participant at RM.ACCEPTED (AC-2)
  4. Initialize the default embargo (AC-3)
  5. Seed vendor (CASE_OWNER) as embargo SIGNATORY (CM-13)
  6. Seed reporter as embargo SIGNATORY (CM-14-005)
  7. Commit canonical ledger entries natively (AC-4)
  8. Emit ``Accept(as_CaseProposal)``
  9. Write durable retry marker (CP-05-005)
  10. Emit ``Create(VulnerabilityCase)`` with inline participants (AC-5)
  11. Clear retry marker on success

Admission (CP-05-002) and idempotency (CP-05-006):

The top-level tree is a Selector with four branches, tried in order:

* **Accept in flight** — ``CheckMarkerExistsNode``: if a
  ``PendingCreateCaseActivity`` marker already exists for this proposal_id,
  Accept was already sent and Create delivery is still pending; the retry
  runner owns recovery, so return SUCCESS immediately (no re-send).

* **Already declined** — ``AlreadyDeclinedArm``: a ``CaseProposalDeclineRecord``
  exists, so the decision stands and is not re-made.  The arm still ensures the
  ``Reject`` was queued, because the record is written *before* the emit, and it
  reads that from ``reject_activity_id`` on the record rather than from the
  outbox — a delivered ``Reject`` has already left the outbox.

* **Decline** — ``DeclineProposalArm``: the ``EvaluateCaseProposal`` call-out
  point refused, so record the decline and emit ``Reject(as_CaseProposal)``.
  Its guards are proposal-keyed: ``report_id`` is supplied by the sender, so a
  report-keyed guard is one the sender can satisfy in order to skip the gate.

* **Accept** — ``AcceptProposalArm``: ``CheckNoDeclineRecordNode`` then the
  normal / duplicate flow, a Sequence that first writes the proposal-keyed
  ``CaseProposalAdmissionRecord`` (so a later delivery can tell that *this*
  proposal began the accept path) and then resolves the case via a Selector
  between ``LoadExistingCaseNode`` (AC-1/AC-2: finds and reuses an existing
  ``VulnerabilityCase`` for the same report) and ``CreateCaseFromProposalNode``
  (normal path: creates a new case).

Why the accept arm carries a guard
----------------------------------
A Selector falls through on FAILURE, and ``_EmitSingleActivityBase.update()``
converts *any* exception into FAILURE.  Without the guard, a decline whose
``Reject`` could not be built — no wire proposal, no injected
``TriggerActivityPort``, a store error — would fall through to the accept flow
and create the case, commit ledger entries, and send ``Accept`` + ``Create``,
reporting SUCCESS.  A refusal gate whose failure direction is "admit" is worse
than no gate, so the decline record is persisted first and the accept arm is
gated on its absence: the tree fails instead of admitting.

Spec: ``specs/case-proposal.yaml`` CP-05-001 through CP-05-006.
Per: ``docs/adr/0041-caseactor-authoritative-case-initialization.md``,
``docs/adr/0025-call-out-point-abstraction-layer.md``.
"""

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

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.proposal_admission_actions import (
    EmitRejectCaseProposalNode,
    RecordProposalAdmissionNode,
    RecordProposalDeclineNode,
)
from vultron.core.behaviors.case.nodes.proposal_admission_conditions import (
    CheckDeclineRecordExistsNode,
    CheckNoDeclineRecordNode,
    CheckProposalAlreadyAnsweredNode,
    CheckRejectAlreadyAnsweredNode,
)
from vultron.core.behaviors.case.nodes.proposal_case_resolution import (
    CreateCaseFromProposalNode,
    LoadExistingCaseNode,
    StoreProposalReportNode,
)
from vultron.core.behaviors.case.nodes.proposal_consent import (
    SeedReporterSignatoryNode,
    SeedVendorOwnerSignatoryNode,
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
    AddVendorOwnerParticipantNode,
)
from vultron.core.behaviors.case.nodes.proposal_reporter import (
    AddReporterParticipantNode,
)
from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
    CheckMarkerExistsNode,
    ClearCreateCaseMarkerNode,
    WriteCreateCaseMarkerNode,
)
from vultron.core.models.report import VulnerabilityReport

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.case_proposal import (
        CaseProposalCallOutBundle,
    )

logger = logging.getLogger(__name__)


def _offer_provenance_from_proposal(
    proposal_dict: dict | None,
) -> tuple[str | None, str | None]:
    """Return ``(offer_id, offer_actor_id)`` carried on the proposal (CP-01-007).

    Both spellings are accepted for the same reason
    ``StoreProposalReportNode._report_from_proposal_dict`` accepts both: which
    one a caller has depends on whether its dump used ``by_alias``.
    """

    def _pick(alias: str, field: str) -> str | None:
        raw = (proposal_dict or {}).get(alias)
        if not isinstance(raw, str):
            raw = (proposal_dict or {}).get(field)
        return raw if isinstance(raw, str) and raw else None

    return _pick("offerId", "offer_id"), _pick(
        "offerActorId", "offer_actor_id"
    )


def create_case_proposal_received_tree(
    report_id: str | None,
    proposal_id: str,
    vendor_uri: str,
    proposal_dict: dict | None = None,
    actor_config: ActorConfig | None = None,
    inline_report: VulnerabilityReport | None = None,
    call_out: "CaseProposalCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Return the received-side BT for processing a ``Create(as_CaseProposal)``.

    The tree is a four-branch Selector: the CP-05-005 in-flight guard, the
    CP-05-006 already-declined answer, the CP-05-002 admission decision, and the
    accept flow.

    **Branch 1 — AC-3 guard** (``CheckMarkerExistsNode``):
      If a ``PendingCreateCaseActivity`` marker already exists for this
      proposal_id, ``Accept(CaseProposal)`` was already sent and
      ``Create(VulnerabilityCase)`` delivery is still pending.  Return SUCCESS
      immediately — the retry runner owns recovery; do not re-send Accept.

    **Branch 2 — already declined** (``AlreadyDeclinedArm``):
      A ``CaseProposalDeclineRecord`` exists, so the decision stands and the
      call-out point is not consulted again — a retrying proposer is not sent a
      fresh ``Reject`` per delivery, and a stateful or stochastic backend cannot
      accept what it previously refused.  The arm's inner Selector re-emits the
      ``Reject`` only when the record shows none was ever queued, which recovers
      the "declined but the emit failed" state the record exists to make visible.
      It asks the record rather than the outbox because ``outbox_pop`` removes a
      ``Reject`` on delivery, so an outbox-keyed answer would re-emit forever
      after the refusal was successfully delivered.

    **Branch 3 — decline** (``DeclineProposalArm``, CP-05-002, CP-05-004):
      Runs the ``EvaluateCaseProposal`` admission call-out point and, when it
      refuses, records the decline and emits ``Reject(as_CaseProposal)``.  Four
      properties are load-bearing:

      * It sits **before** ``ResolveCaseIdSelector``, so a refusal happens ahead
        of every write.  A Reject emitted after the accept flow's effects would
        report "declined" while this store held a half-built case with committed
        ledger entries (CLP-10-009).  ``CheckProposalAlreadyAnsweredNode``
        extends that to *later* deliveries via the proposal-keyed
        ``CaseProposalAdmissionRecord`` that ``main_flow`` writes first —
        ``main_flow`` creates the case before it emits, so neither an Accept-only
        guard nor the case itself can identify a half-built one as *this*
        proposal's.
      * Its guards are keyed on the **proposal**, never the report.  ``report_id``
        comes from the report the sender embedded, so a report-keyed guard is one
        a sender can satisfy on purpose and thereby skip the gate entirely.
      * The decline record is written **before** the emit, so branch 4's guard
        can stop a failed emit from becoming an accept.
      * Everything in this arm ahead of the record **raises** instead of
        returning FAILURE when it cannot do its job.  A Selector falls through
        on FAILURE, so for a node in a refusal arm "I could not tell" and "no"
        both mean *admit*; only ``BTBridge`` failing the whole tree is safe.

    **Branch 4 — accept** (``AcceptProposalArm``): ``CheckNoDeclineRecordNode``
    followed by the normal / duplicate flow (Sequence):
      First ``RecordProposalAdmissionNode`` stamps the proposal-keyed admission
      record, before any case exists.  Then a sub-Selector resolves which
      ``VulnerabilityCase`` to use:

      * ``LoadExistingCaseNode`` (AC-1/AC-2): if a case already exists for
        *report_id*, write its ID to the blackboard and succeed.
      * ``CreateCaseFromProposalNode`` (normal path): create a new case.

      Then CaseActor-native initialization steps (ADR-0041):

      3. ``AddCaseActorParticipantNode`` — CaseActor registered as
         COORDINATOR + CASE_MANAGER (ADR-0041)
      4. ``AddVendorOwnerParticipantNode`` — proposing actor added as
         CASE_OWNER (plus ``actor_config.default_case_roles``) at RM.RECEIVED
         (ADR-0041 AC-1)
      5. ``AddReporterParticipantNode`` — reporter added at RM.ACCEPTED
         (ADR-0041 AC-2)
      6. ``InitializeDefaultEmbargoNode`` — default embargo initialized
         (ADR-0041 AC-3)
      7. ``SeedVendorOwnerSignatoryNode`` — vendor (CASE_OWNER) seeded as
         embargo SIGNATORY (CM-13)
      8. ``SeedReporterSignatoryNode`` — reporter seeded as embargo
         SIGNATORY (CM-14-005); implicit consent per ADR-0048
      9. ``CommitNativeLedgerEntriesNode`` — canonical ledger entries
         committed (ADR-0041 AC-4)

      Then the outbound messaging steps:

      10. ``EmitAcceptCaseProposalNode`` — emits Accept(as_CaseProposal)
      11. ``WriteCreateCaseMarkerNode`` — writes durable retry marker with
         inline case object (CP-05-005, ADR-0041 AC-5)
      12. ``EmitCreateVulnerabilityCaseNode`` — emits
         Create(VulnerabilityCase) with inline participants
      13. ``ClearCreateCaseMarkerNode`` — removes marker on success
         (CP-05-005)

    If node 11 fails, the marker written in node 10 remains in the DataLayer so
    that a retry runner (#1139) can complete the ``Create(VulnerabilityCase)``
    delivery independently.

    Spec: CP-05-001 through CP-05-006.
    Per: ``docs/adr/0041-caseactor-authoritative-case-initialization.md``.

    Args:
        report_id: URI of the VulnerabilityReport embedded in the proposal
            (CP-01-004). Pass ``None`` if the report URI could not be
            extracted — the case will be created without a report link.
        proposal_id: URI of the ``as_CaseProposal`` object.
        vendor_uri: URI of the vendor actor to whom the responses are sent.
        proposal_dict: Wire-serialised proposal dict (``model_dump(by_alias=True)``).
            When supplied, the Accept's ``object_`` carries the full inline proposal,
            satisfying CP-05-003 and the AKM-03-001 outbox requirement. Falls back
            to bare URI when ``None``. It is also where the report's offer
            provenance arrives (``offerId``/``offerActorId``, CP-01-007), which
            the ``add_report_to_case`` ledger entry needs and this CaseActor
            cannot look up for itself.
        actor_config: Optional local actor configuration.  Its
            ``default_case_roles`` determine the CVD roles the proposing
            (report-receiving) actor is given alongside ``CVDRole.CASE_OWNER``
            (CFG-07-002, CFG-07-004).  When ``None`` the receiver gets
            ``CVDRole.CASE_OWNER`` only.
        call_out: Bundle supplying the ``EvaluateCaseProposal`` admission
            call-out point.  Defaults to ``CASE_PROPOSAL_DETERMINISTIC``, whose
            backend always succeeds, so an unconfigured deployment admits every
            well-formed proposal exactly as it did before this seam existed
            (BT-23-001, BT-23-011).

    Returns:
        A py_trees Selector behaviour ready for ``BTBridge.execute_with_setup``.
    """
    from vultron.core.behaviors.call_out.bundles.case_proposal import (
        CASE_PROPOSAL_DETERMINISTIC,
    )
    from vultron.core.behaviors.case.embargo_tree import (
        InitializeDefaultEmbargoNode,
    )

    bundle = call_out if call_out is not None else CASE_PROPOSAL_DETERMINISTIC

    offer_id, offer_actor_id = _offer_provenance_from_proposal(proposal_dict)

    # Sub-Selector: reuse existing case (duplicate) OR create new (normal path)
    case_resolution = py_trees.composites.Selector(
        name="ResolveCaseIdSelector",
        memory=False,
        children=[
            LoadExistingCaseNode(report_id=report_id),
            CreateCaseFromProposalNode(report_id=report_id),
        ],
    )

    # Main flow: record admission → resolve case → native init → emit Accept →
    # write marker → emit Create → clear marker
    main_flow = py_trees.composites.Sequence(
        name="CreateCaseProposalReceivedBT",
        memory=False,
        children=[
            # Ahead of case_resolution deliberately.  This is the proposal-keyed
            # evidence that the accept path began; without it the only marker of
            # an in-progress accept is the case itself, which is keyed on a
            # report the *sender* chose.  See RecordProposalAdmissionNode.
            RecordProposalAdmissionNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
            ),
            case_resolution,
            # Store the inline report first: the reporter participant, its ledger
            # entry and the SIGNATORY seed are all derived from it, and each of
            # those nodes skips "best-effort" when it is missing.
            StoreProposalReportNode(
                report_id=report_id,
                proposal_dict=proposal_dict,
                inline_report=inline_report,
            ),
            # ADR-0041: register CaseActor as COORDINATOR + CASE_MANAGER
            AddCaseActorParticipantNode(),
            # ADR-0041 AC-1: add vendor as CASE_OWNER at RM.RECEIVED
            AddVendorOwnerParticipantNode(
                vendor_uri=vendor_uri,
                report_id=report_id,
                actor_config=actor_config,
            ),
            # ADR-0041 AC-2: add reporter at RM.ACCEPTED
            AddReporterParticipantNode(report_id=report_id),
            # ADR-0041 AC-3: initialize default embargo
            InitializeDefaultEmbargoNode(),
            # CM-13: seed the vendor (CASE_OWNER) as embargo SIGNATORY.
            # InitializeDefaultEmbargoNode's SeedOwnerAsSignatoryNode keys on
            # actor_id (the CaseActor), which is not a participant here, so it
            # no-ops; this node seeds the vendor explicitly.
            SeedVendorOwnerSignatoryNode(vendor_uri=vendor_uri),
            # CM-14-005: seed the reporter as embargo SIGNATORY.
            # Reporter consent is implicit in submitting the report (ADR-0048);
            # no invitation round-trip is needed or appropriate.
            SeedReporterSignatoryNode(report_id=report_id),
            # ADR-0041 AC-4: commit canonical ledger entries natively
            CommitNativeLedgerEntriesNode(
                vendor_uri=vendor_uri,
                report_id=report_id,
                offer_id=offer_id,
                offer_actor_id=offer_actor_id,
            ),
            # Outbound messaging
            EmitAcceptCaseProposalNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
                proposal_dict=proposal_dict,
            ),
            WriteCreateCaseMarkerNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
            ),
            EmitCreateVulnerabilityCaseNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
            ),
            ClearCreateCaseMarkerNode(proposal_id=proposal_id),
        ],
    )

    # A proposal already declined is not re-adjudicated.  The arm still ensures
    # the Reject went out, because the decline record is written *before* the
    # emit, so "declined with nothing queued" is a reachable and recoverable
    # state (the same ordering CP-05-005 uses for the accept side's Create).
    resend_decline_arm = py_trees.composites.Sequence(
        name="AlreadyDeclinedArm",
        memory=False,
        children=[
            CheckDeclineRecordExistsNode(proposal_id=proposal_id),
            py_trees.composites.Selector(
                name="EnsureRejectQueued",
                memory=False,
                children=[
                    CheckRejectAlreadyAnsweredNode(proposal_id=proposal_id),
                    EmitRejectCaseProposalNode(
                        proposal_id=proposal_id,
                        vendor_uri=vendor_uri,
                        proposal_dict=proposal_dict,
                    ),
                ],
            ),
        ],
    )

    # CP-05-002 / CP-05-004 admission decision.  `Inverter` converts the
    # call-out point's "declined" FAILURE into the SUCCESS this arm needs to
    # proceed, so the Evaluator keeps the BT-18-007 contract (a refusal is a
    # FAILURE return, never a "rejected" value written alongside SUCCESS).
    decline_arm = py_trees.composites.Sequence(
        name="DeclineProposalArm",
        memory=False,
        children=[
            # A decision already on record is never re-adjudicated here.  The
            # resend arm above normally answers that case, but it returns FAILURE
            # when its own emit fails, and the Selector would then run this arm
            # and tick the call-out point a second time on the same delivery —
            # billing a metered policy backend twice for one proposal.  The tree
            # still fails closed either way (an admitting verdict lands on
            # CheckNoDeclineRecordNode), so this guard buys the contract the
            # docstring claims, not the safety.
            CheckNoDeclineRecordNode(proposal_id=proposal_id),
            # Keyed on the proposal, not the report: `report_id` is chosen by the
            # sender, so a report-scoped guard can be skipped by naming a report
            # this service has already seen.
            py_trees.decorators.Inverter(
                name="ProposalNotYetAnswered",
                child=CheckProposalAlreadyAnsweredNode(
                    proposal_id=proposal_id, report_id=report_id
                ),
            ),
            py_trees.decorators.Inverter(
                name="ProposalDeclined",
                child=bundle.evaluate_proposal_factory("EvaluateCaseProposal"),
            ),
            # Before the emit, deliberately — see RecordProposalDeclineNode.
            RecordProposalDeclineNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
            ),
            EmitRejectCaseProposalNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
                proposal_dict=proposal_dict,
            ),
        ],
    )

    # The decline record is the accept path's precondition, which is what makes
    # a refusal terminal: if the emit above failed, this Selector tries the
    # accept arm next and the guard refuses it, so the tree fails instead of
    # creating the case and sending an Accept the service decided against.
    accept_arm = py_trees.composites.Sequence(
        name="AcceptProposalArm",
        memory=False,
        children=[
            CheckNoDeclineRecordNode(proposal_id=proposal_id),
            main_flow,
        ],
    )

    return py_trees.composites.Selector(
        name="CreateCaseProposalIdempotencySelector",
        memory=False,
        children=[
            CheckMarkerExistsNode(proposal_id=proposal_id),
            resend_decline_arm,
            decline_arm,
            accept_arm,
        ],
    )
