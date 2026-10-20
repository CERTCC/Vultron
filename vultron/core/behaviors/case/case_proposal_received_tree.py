"""BT tree for the CreateCaseProposal received-side use case.

Case-actor side: handles an inbound ``Create(as_CaseProposal)`` and emits
two outbound activities in sequence:

  1. ``Accept(as_CaseProposal)`` — acknowledgement to the report receiver
  2. ``Create(VulnerabilityCase)`` — case announcement to the report receiver

A durable ``PendingCreateCaseActivity`` marker is written to the DataLayer
after step 1 and cleared on successful completion of step 2 so that a retry
runner (#1139) can recover the obligation if delivery of step 2 fails.

The normal-path Sequence performs CaseActor-native initialization per
ADR-0041, emits the outbound activities, and commits the canonical ledger
entries last (CP-09-009):

  1. Resolve (or create) the case, attributed to the proposer (CP-09-001)
  2. Add the proposer as CASE_OWNER at RM.RECEIVED, plus the roles it
     stated on the proposal (AC-1, CP-09-007, ADR-0133)
  3. Add reporter as participant at RM.ACCEPTED (AC-2)
  4. Initialize the default embargo, seeding the CASE_OWNER as a signatory
     (AC-3, CM-14-003); record any pending revision as owed (EP-04-011)
  5. Seed reporter as an embargo signatory (CM-14-005)
  6. Emit ``Accept(as_CaseProposal)``
  7. Write durable retry marker (CP-05-005)
  8. Emit ``Create(VulnerabilityCase)`` with inline participants (AC-5)
  9. Clear retry marker on success
  10. Commit canonical ledger entries (AC-4) — after the emits, so every
      participant holds the case before its first ``Announce(CaseLedgerEntry)``
      (CM-14-011, CP-09-009)
  11. Relay a contested creation's pending revision to the party whose terms
      won (EP-04-011) — after initialization is complete (CM-14-007)

Steps 1-10, with the admission record ahead of them, are one act: they run
in one ``ActTransaction`` (ADR-0146), so a failed step rolls back the case,
its records, the queued ``Accept`` and ``Create``, the retry marker and every
creation entry already committed (CLP-07-013, #4442).  Step 11 keeps its own
retry marker (#4121) and runs after the act commits.

Admission (CP-05-002) and idempotency (CP-05-006):

Ahead of the branches, the receive-tree factory composes the sender guard from
the use case's ``AUTHOR`` declaration: the proposal id is chosen by the sender,
so one this store recorded for another proposer is refused before any branch
reads or writes a proposal-keyed record (CP-05-010, HP-01-008, #4719).

The top-level tree is a Selector with five branches, tried in order:

* **Accept in flight** — ``CheckMarkerExistsNode``: if a
  ``PendingCreateCaseActivity`` marker already exists for this proposal_id,
  Accept was already sent and Create delivery is still pending; the retry
  runner owns recovery, so return SUCCESS immediately (no re-send).

* **Already declined** — ``AlreadyDeclinedArm``: a ``CaseProposalDeclineRecord``
  exists, so the decision stands and is not re-made.  The arm still ensures the
  ``Reject`` was queued, because the record is written *before* the emit, and it
  reads that from ``reject_activity_id`` on the record rather than from the
  outbox — a delivered ``Reject`` has already left the outbox.

* **Closed case** — ``DeclineClosedCaseProposalArm``: the proposal resolves to
  a fully closed case (the owner's own case for the report, or the case this
  proposal's stored ``Accept`` names), so record the decline and emit
  ``Reject(as_CaseProposal)``.  Nothing is written for the case (CP-05-006,
  CP-05-008, CM-23-013).  The factory's post-close guard cannot do this: the
  proposal names a report, not a case.

* **Decline** — ``DeclineProposalArm``: the ``EvaluateCaseProposal`` call-out
  point refused, so record the decline and emit ``Reject(as_CaseProposal)``.
  Its guards are proposal-keyed: ``report_id`` is supplied by the sender, so a
  report-keyed guard is one the sender can satisfy in order to skip the gate.

* **Accept** — ``AcceptProposalArm``: ``CheckNoDeclineRecordNode`` then the
  normal / duplicate flow, a Sequence that first writes the proposal-keyed
  ``CaseProposalAdmissionRecord`` (so a later delivery can tell that *this*
  proposal began the accept path) and then resolves the case via a Selector
  between ``LoadExistingCaseNode`` (AC-1/AC-2: finds and reuses the existing
  ``VulnerabilityCase`` the proposal resolves to — the proposer's own case for
  the report, or the case the proposal's stored ``Accept`` names) and
  ``CreateCaseFromProposalNode`` (normal path: creates a new case).

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

Spec: ``specs/case-proposal.yaml`` CP-05-001 through CP-05-006, CP-05-008.
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
from collections.abc import Sequence
from typing import TYPE_CHECKING

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.act_transaction import ActTransaction
from vultron.core.behaviors.call_out.bundles.case_proposal import (
    CASE_PROPOSAL_DETERMINISTIC,
)
from vultron.core.behaviors.case.embargo_tree import (
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
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
    CheckDeclineRecordExistsNode,
    CheckNoDeclineRecordNode,
    CheckProposalAlreadyAnsweredNode,
    CheckProposalCaseFullyClosedNode,
    CheckRejectAlreadyAnsweredNode,
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
from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
    CheckCaseAlreadyAnnouncedNode,
    CheckMarkerExistsNode,
    ClearCreateCaseMarkerNode,
    WriteCreateCaseMarkerNode,
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

logger = logging.getLogger(__name__)

CLOSED_CASE_DECLINE_REASON = (
    "The case for this proposal is fully closed; nothing more will be done"
    " for this proposal."
)
"""The ``Reject`` summary for a proposal whose case is fully closed.

It declines the delivery only: an ``Accept`` already sent for the proposal
stands (CP-05-005, CP-05-006).
"""


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
    """Return the received-side BT for processing a ``Create(as_CaseProposal)``.

    The tree is a Sequence of intake (CLP-10-017), the sender guard the
    factory composes from *sender_rule*, and a five-branch Selector:
    the CP-05-005 in-flight guard, the
    CP-05-006 already-declined answer, the closed-case decline, the CP-05-002
    admission decision, and the accept flow.

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

    **Branch 3 — closed case** (``DeclineClosedCaseProposalArm``, CP-05-006,
    CP-05-008, CM-23-013):
      ``CheckProposalCaseFullyClosedNode`` finds that the proposal resolves to
      a fully closed case: the proposer's own case for *report_id* (a new
      proposal id from the owner), or the case the proposal's stored
      ``Accept`` names (a redelivery of the original proposal).  The arm
      records the decline, with ``CLOSED_CASE_DECLINE_REASON``, and emits
      ``Reject(as_CaseProposal)``.  It writes nothing for the case: no
      ``CaseLedgerEntry`` and no case or participant change.  The decline
      record is keyed on the proposal, so CM-23-013 does not bar it.  The
      ``Reject`` declines only this delivery and does not revoke a stored
      ``Accept`` (CP-05-005).  It follows the decline arm's refusal rules: the
      closure check raises on a store error, and the record is written before
      the emit, so a failed ``Reject`` cannot fall through into an accept
      that reuses the closed case.  The admission call-out point is not
      consulted.

    **Branch 4 — decline** (``DeclineProposalArm``, CP-05-002, CP-05-004):
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
      * The decline record is written **before** the emit, so branch 5's guard
        can stop a failed emit from becoming an accept.
      * Everything in this arm ahead of the record **raises** instead of
        returning FAILURE when it cannot do its job.  A Selector falls through
        on FAILURE, so for a node in a refusal arm "I could not tell" and "no"
        both mean *admit*; only ``BTBridge`` failing the whole tree is safe.

    **Branch 5 — accept** (``AcceptProposalArm``): ``CheckNoDeclineRecordNode``
    followed by the normal / duplicate flow (Sequence):
      First ``RecordProposalAdmissionNode`` stamps the proposal-keyed admission
      record, before any case exists.  Then a sub-Selector resolves which
      ``VulnerabilityCase`` to use:

      * ``LoadExistingCaseNode`` (AC-1/AC-2): if *proposer_uri* already owns a
        case for *report_id* (CP-05-008), or the proposal's stored ``Accept``
        names a case (a redelivery, CP-05-006, also from a former owner after
        an ownership transfer, #4650), write its ID to the blackboard and
        succeed; another proposer's case for the report is not reused.  It
        resolves the case with ``proposal_case_ids``, as branch 3 does, and a
        fully closed case never reaches it: branch 3 declines it.
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
         (CM-14-003); a revision it registers is first recorded as an owed
         relay (EP-04-011, #4121)
      7. ``SeedReporterSignatoryNode`` — reporter seeded as embargo
         signatory (CM-14-005); implicit consent per ADR-0048
      Then the outbound messaging steps:

      8. ``EmitAcceptCaseProposalNode`` — emits Accept(as_CaseProposal)
      9. ``WriteCreateCaseMarkerNode`` — writes durable retry marker with
         inline case object (CP-05-005, ADR-0041 AC-5)
      10. ``EmitCreateVulnerabilityCaseNode`` — emits
         Create(VulnerabilityCase) with inline participants
      11. ``ClearCreateCaseMarkerNode`` — removes marker on success
         (CP-05-005)

      Then, last of all:

      12. ``CommitNativeLedgerEntriesNode`` — canonical ledger entries
         committed (ADR-0041 AC-4).  Each commit fans out through the FIFO
         outbox, so it runs after the Create: every recipient must hold the
         case object before its first ``Announce(CaseLedgerEntry)`` arrives
         (CM-14-011, CP-09-009), or it enters the SYNC-15 pre-genesis
         reject/replay path on the normal case-creation route (#3033, #2898).
      13. ``RelayCreationTimeRevisionNode`` — relays the revision step 6
         recorded, if any, as ``Invite(EmbargoEvent)`` to the party
         whose terms won (EP-04-011), then indexes the sent Invite
         (EP-08-002) and deletes the marker, which a failure keeps for a
         retry (#4121); no modification precedes step 12 (CM-14-007).

    Nodes from the admission record through node 12 run in one
    ``ActTransaction`` (ADR-0146): if any of them fails, nothing they wrote is
    kept, the ``Accept`` and the marker of node 9 included, and delivery is
    told of neither activity (DL-02-004).  The marker therefore only matters
    for a delivery failure after the commit (CP-05-005).

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
            when no actor default applies (EP-04-005); ``None`` uses the
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

    # Main flow: record admission → resolve case → native init → emit Accept →
    # write marker → emit Create → clear marker
    # The creation is one act (ADR-0146): everything from the admission
    # record to the last creation entry is written in one ActTransaction, so
    # a creation entry that fails, or an emit that fails, rolls back the case,
    # its records, the queued Accept and Create and every entry already
    # committed (CLP-07-013, #4442).  Delivery is told of the queued
    # activities only once the block commits (DL-02-004), so nothing about a
    # rolled-back case is ever sent, and a redelivery starts from the
    # beginning.
    creation_act = ActTransaction(
        name="CreateCaseFromProposalAct",
        children=[
            # Ahead of case_resolution deliberately.  This is the proposal-keyed
            # evidence that the accept path began; without it the only marker of
            # an in-progress accept is the case itself, which is keyed on a
            # report the *sender* chose.  See RecordProposalAdmissionNode.
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
            # records its revision's relay as owed in the same commit that
            # registers the revision (EP-04-011, #4121, #4156).
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
            # A case the proposer already holds (CP-05-008) is not announced
            # a second time; the Accept above is this proposal's whole answer.
            py_trees.composites.Selector(
                name="AnnounceCaseOnce",
                memory=False,
                children=[
                    CheckCaseAlreadyAnnouncedNode(),
                    py_trees.composites.Sequence(
                        name="AnnounceCase",
                        memory=False,
                        children=[
                            WriteCreateCaseMarkerNode(
                                proposal_id=proposal_id,
                                owner_uri=proposer_uri,
                            ),
                            EmitCreateVulnerabilityCaseNode(
                                proposal_id=proposal_id,
                            ),
                            ClearCreateCaseMarkerNode(proposal_id=proposal_id),
                        ],
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
                owner_uri=proposer_uri,
                report_id=report_id,
                offer_id=offer_id,
                offer_actor_id=offer_actor_id,
            ),
        ],
    )

    main_flow = py_trees.composites.Sequence(
        name="AcceptProposalFlow",
        memory=False,
        children=[
            creation_act,
            # EP-04-011: relay the shortest-wins loser that step 6 recorded,
            # only now that initialization is complete (CM-14-007).  Outside
            # the creation act: the relay keeps its own retry marker (#4121),
            # so a failed relay does not undo a committed creation.
            RelayCreationTimeRevisionNode(actor_config=actor_config),
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
                        proposer_uri=proposer_uri,
                        proposal_dict=proposal_dict,
                    ),
                ],
            ),
        ],
    )

    # CP-05-006 / CP-05-008 / CM-23-013: a proposal that resolves to a fully
    # closed case — the owner's new proposal, or a redelivery of the original
    # one — is declined, and nothing is written for the case.  Ahead of the
    # admission decision: closure decides, so the call-out point is not
    # consulted, and ahead of the accept arm, which would reuse the closed
    # case.  It is the same refusal shape as the decline arm below: the
    # proposal-keyed decline record is written before the emit, so a failed
    # Reject stops at the accept arm's CheckNoDeclineRecordNode, and a later
    # delivery is answered from the record by the resend arm above.
    closed_case_arm = py_trees.composites.Sequence(
        name="DeclineClosedCaseProposalArm",
        memory=False,
        children=[
            CheckNoDeclineRecordNode(proposal_id=proposal_id),
            CheckProposalCaseFullyClosedNode(
                proposal_id=proposal_id,
                proposer_uri=proposer_uri,
                report_id=report_id,
            ),
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
                proposer_uri=proposer_uri,
            ),
            EmitRejectCaseProposalNode(
                proposal_id=proposal_id,
                proposer_uri=proposer_uri,
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

    # Intake runs ahead of the whole Selector, so every arm — including a
    # decline and the in-flight guard — leaves the archived Create(CaseProposal)
    # (CLP-10-017, CLP-10-018).  No commit stage (``case_id=None``): the case
    # does not exist yet, and the accept arm's CommitNativeLedgerEntriesNode
    # ledgers the facts it creates (ADR-0041 AC-4).
    return create_receive_activity_tree(
        name="CreateCaseProposalReceivedBT",
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
                    CheckMarkerExistsNode(proposal_id=proposal_id),
                    resend_decline_arm,
                    closed_case_arm,
                    decline_arm,
                    accept_arm,
                ],
            )
        ],
    )
