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

Idempotency (CP-05-006):

The top-level tree is a Selector with two branches:

* **AC-3 guard** — ``_CheckMarkerExistsNode``: if a
  ``PendingCreateCaseActivity`` marker already exists for this proposal_id,
  Accept was already sent and Create delivery is still pending; the retry
  runner owns recovery, so return SUCCESS immediately (no re-send).

* **Normal / duplicate flow** — a Sequence whose first step is itself a
  Selector between ``_LoadExistingCaseNode`` (AC-1/AC-2: finds and reuses
  an existing ``VulnerabilityCase`` for the same report) and
  ``_CreateCaseFromProposalNode`` (normal path: creates a new case).  The
  remaining nodes proceed with native initialization and outbound messaging.

Spec: ``specs/case-proposal.yaml`` CP-05-001 through CP-05-006.
Per: ``docs/adr/0041-caseactor-authoritative-case-initialization.md``.
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
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.case_lookup import (
    RequireCaseForReport,
)
from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
    _get_or_create_accepted_status,
)
from vultron.core.behaviors.case.nodes.participant.owner import (
    _build_owner_initial_status,
    _effective_case_roles,
)
from vultron.core.behaviors.case.ledger_snapshots import (
    build_add_case_status_snapshot,
    build_add_participant_status_snapshot,
    build_add_report_to_case_snapshot,
    build_create_case_snapshot,
)
from vultron.core.behaviors.case.offer_provenance import find_offer_for_report
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.activity import (
    VultronAccept,
    VultronCreateCaseActivity,
)
from vultron.core.models.case import VulnerabilityCase, VultronCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import PecDimension, RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class _CheckMarkerExistsNode(DataLayerAction):
    """Return SUCCESS if a ``PendingCreateCaseActivity`` marker already exists.

    AC-3 guard (CP-05-006): if the marker is present, ``Accept(CaseProposal)``
    was already sent for this proposal and a ``Create(VulnerabilityCase)``
    delivery is still pending.  The retry runner (#1139) owns recovery; the
    current delivery should be a no-op to avoid duplicate Accepts on the
    vendor side.

    Returns FAILURE when no marker is found, allowing the outer Selector to
    proceed to the normal / duplicate flow.
    """

    def __init__(self, proposal_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        marker_id = PendingCreateCaseActivity.build_id(self._proposal_id)
        existing = self.datalayer.read(marker_id)
        if isinstance(existing, PendingCreateCaseActivity):
            logger.info(
                "%s: PendingCreateCaseActivity marker found for proposal '%s'"
                " — Accept already sent; skipping re-send (CP-05-006 AC-3)",
                self.name,
                self._proposal_id,
            )
            return Status.SUCCESS

        return Status.FAILURE


class _LoadExistingCaseNode(RequireCaseForReport):
    """Find an existing ``VulnerabilityCase`` for *report_id* and load it.

    AC-1 / AC-2 (CP-05-006): detects a duplicate ``Create(as_CaseProposal)``
    for a report that already has a case.  Writes the existing ``case_id`` to
    the blackboard so ``_EmitAcceptCaseProposalNode`` and
    ``_WriteCreateCaseMarkerNode`` can reference it, then returns SUCCESS.

    Returns FAILURE when no existing case is found, allowing the outer
    Selector to fall through to ``_CreateCaseFromProposalNode`` (normal path).

    Behaviour is inherited wholesale from
    :class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`
    — "resolve this store's case for a report, publish ``/case_id``, fail when
    absent" has exactly one implementation (ARCH-15-004).  The subclass exists
    only to keep the CP-05-006 node name in BT traces and to document what
    FAILURE means *here*: no duplicate, so create the case.
    """


class _CreateCaseFromProposalNode(DataLayerActionWithPorts):
    """Create a VulnerabilityCase from the proposal and write case_id to blackboard.

    The case-actor service is the ``attributed_to`` author of the new case,
    preserving AS2 "I created this" semantics (CP-05-003, ADR-0023).
    """

    def __init__(
        self,
        report_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"case_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case = VultronCase(attributed_to=self.actor_id)
        if self._report_id is not None:
            case.vulnerability_reports.append(self._report_id)

        try:
            self.datalayer.create(case)
        except ValueError as exc:
            self.feedback_message = f"Case creation failed: {exc}"
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self._set_output("case_id", case.id_)
        logger.info(
            "%s: Created VulnerabilityCase '%s' from proposal",
            self.name,
            case.id_,
        )
        return Status.SUCCESS


class _StoreProposalReportNode(DataLayerAction):
    """Persist the report the proposal carried inline, if not already stored.

    Nothing else in this tree did, and three downstream nodes need it:
    ``_AddReporterParticipantNode``, ``_CommitNativeLedgerEntriesNode`` and
    ``_SeedReporterSignatoryNode`` each ``read(report_id)`` and skip
    "best-effort" when it is absent. So one missing write degraded silently in
    three places, and the visible symptom was a participant who never appeared
    and a replica the reporter never received.

    A shared store hid it: the *vendor* had stored the report when it received
    the Offer, and that row was visible to everyone. With per-actor stores the
    CaseActor has its own, and the report only reaches it inline on the proposal
    (CP-01-004) — so it has to be written here.

    Prefers *inline_report*, a report already converted to the core shape by the
    caller. The fallback — validating the proposal's serialised ``object`` — can
    only be as good as that dict's spelling, and the dict the received-side use
    case has is a ``by_alias=True`` wire dump, because the ``Accept`` must carry
    the proposal inline on the wire (CP-05-003, AKM-03-001). In wire spelling the
    reporter is ``attributedTo``; this core model declares ``attributed_to`` and
    sets ``extra="ignore"``, so validating that dict quietly produced a report
    with no reporter, and the complaint surfaced three nodes later as "has no
    attributed_to" (#2482). Converting is the wire layer's job — it owns
    ``to_core()`` — and core MUST NOT import wire to do it itself (ARCH-03-001),
    so the caller converts and passes the result down.
    """

    def __init__(
        self,
        report_id: str | None,
        proposal_dict: dict | None,
        inline_report: VulnerabilityReport | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._proposal_dict = proposal_dict
        self._inline_report = inline_report

    def _report_from_proposal_dict(self) -> VulnerabilityReport | None:
        """Rebuild the report from the proposal's serialised inline object.

        Accepts either spelling of the key: ``object`` is the wire alias and
        ``object_`` the field name, and which one a caller has depends on
        whether its dump used ``by_alias``.
        """
        proposal = self._proposal_dict or {}
        raw = proposal.get("object")
        if not isinstance(raw, dict):
            raw = proposal.get("object_")
        if not isinstance(raw, dict):
            logger.warning(
                "%s: proposal carried no inline report for '%s' (got %s), so"
                " the reporter participant and its ledger entry cannot be"
                " derived; the proposal should inline it (CP-01-004)",
                self.name,
                self._report_id,
                type(raw).__name__,
            )
            return None
        try:
            return VulnerabilityReport.model_validate(raw)
        except Exception as exc:
            logger.warning(
                "%s: could not reconstruct the inline report '%s' from the"
                " proposal: %s",
                self.name,
                self._report_id,
                exc,
            )
            return None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if not self._report_id:
            return Status.SUCCESS
        if self.datalayer.read(self._report_id) is not None:
            return Status.SUCCESS

        report = self._inline_report or self._report_from_proposal_dict()
        if report is None:
            return Status.SUCCESS
        self._warn_if_unattributed(report)

        try:
            self.datalayer.create(report)
        except ValueError as exc:
            logger.debug(
                "%s: report '%s' already stored: %s",
                self.name,
                self._report_id,
                exc,
            )
            return Status.SUCCESS

        logger.info(
            "%s: stored report '%s' from the inline proposal",
            self.name,
            self._report_id,
        )
        return Status.SUCCESS

    def _warn_if_unattributed(self, report: VulnerabilityReport) -> None:
        """Say out loud that a storable report is useless for what follows.

        Three downstream nodes derive from ``attributed_to``; without it each
        reports the absence separately and much further from the cause.
        """
        if report.attributed_to:
            return
        logger.warning(
            "%s: the inline report '%s' has no attributed_to, so the"
            " reporter participant, its ledger entry and the SIGNATORY"
            " seed cannot be derived from it (CP-01-004 requires a report"
            " attributed to its reporter)",
            self.name,
            self._report_id,
        )


class _AddCaseActorParticipantNode(DataLayerActionWithPorts):
    """Register the CaseActor itself as COORDINATOR + CASE_MANAGER participant.

    Under ADR-0041 the CaseActor creates the VulnerabilityCase, so it must
    also register itself as the CASE_MANAGER so that ResolveCaseManagerNode
    can locate it later (e.g. add-note-to-case, send_tree).

    Per CM-23-005 and ADR-0051, the CaseActor MUST have a full RM lifecycle.
    Three bootstrap ParticipantStatus records are emitted at creation:
      - RM.RECEIVED  = CaseProposal received and being evaluated
      - RM.VALID     = CaseProposal validated; case creation begun
      - RM.ACCEPTED  = VulnerabilityCase successfully created and coordinated

    These statuses are later committed as CaseLedgerEntries by
    _CommitNativeLedgerEntriesNode (CM-23-007).

    Reads ``case_id`` from the blackboard.  No-ops if the CaseActor is
    already in ``actor_participant_index`` (idempotent on duplicate delivery).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _build_bootstrap_statuses(
        self, case_id: str
    ) -> list[ParticipantStatus]:
        """Return the three bootstrap ParticipantStatus records (CM-23-005/006)."""
        assert self.actor_id is not None
        return [
            ParticipantStatus(
                context=case_id,
                rm=RmDimension(state=RM.RECEIVED),
                attributed_to=self.actor_id,
                cvd_role=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
                consent=PecDimension(state=PEC.NO_EMBARGO),
            ),
            ParticipantStatus(
                context=case_id,
                rm=RmDimension(state=RM.VALID),
                attributed_to=self.actor_id,
                cvd_role=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
                consent=PecDimension(state=PEC.NO_EMBARGO),
            ),
            ParticipantStatus(
                context=case_id,
                rm=RmDimension(state=RM.ACCEPTED),
                attributed_to=self.actor_id,
                cvd_role=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
                consent=PecDimension(state=PEC.NO_EMBARGO),
            ),
        ]

    def _register_participant(self, case_id: str) -> Status:
        """Create the participant with bootstrap statuses and attach to case."""
        assert self.datalayer is not None
        assert self.actor_id is not None

        bootstrap_statuses = self._build_bootstrap_statuses(case_id)
        for status in bootstrap_statuses:
            try:
                self.datalayer.create(status)
            except ValueError as e:
                logger.debug(
                    "_register_participant: create status idempotent or"
                    " error for actor '%s': %s",
                    self.actor_id,
                    e,
                )

        participant = VultronParticipant(
            attributed_to=self.actor_id,
            context=case_id,
            name=f"CaseActor for {case_id}",
            case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
            participant_statuses=bootstrap_statuses,
        )

        updated_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id,
            self.actor_id,
            self.logger,
        )
        if updated_case is None:
            self.feedback_message = f"Case '{case_id}' not found in DataLayer"
            return Status.FAILURE

        self.datalayer.save(updated_case)
        logger.info(
            "%s: Registered CaseActor '%s' as CASE_MANAGER for case '%s'"
            " with bootstrap RM lifecycle (RM.RECEIVED → RM.VALID →"
            " RM.ACCEPTED) per CM-23-005/ADR-0051",
            self.name,
            self.actor_id,
            case_id,
        )
        return Status.SUCCESS

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        stored_case = self.datalayer.read(case_id)
        if isinstance(stored_case, VulnerabilityCase):
            if self.actor_id in stored_case.actor_participant_index:
                return Status.SUCCESS

        return self._register_participant(case_id)


class _AddVendorOwnerParticipantNode(DataLayerActionWithPorts):
    """Add the report receiver as CASE_OWNER participant at RM.RECEIVED.

    The actor that sent the proposal is the case owner (receiver of the
    original vulnerability report).  Per ADR-0041 AC-1, the CaseActor adds
    them as CASE_OWNER at RM.RECEIVED in its own DataLayer.

    The receiver's additional CVD roles come from
    ``ActorConfig.default_case_roles`` (CFG-07-002, CFG-07-004) — the same
    source the pre-ADR-0041 vendor-side ``CreateCaseOwnerParticipant`` used.
    They must not be hard-coded: a coordinator that receives a report is a
    CASE_OWNER but never a VENDOR, and giving it ``CVDRole.VENDOR`` makes
    downstream VFD fix-lifecycle guards demand a fix it will never produce.

    Reads ``case_id`` from the blackboard (written by ResolveCaseIdSelector).
    """

    def __init__(
        self,
        vendor_uri: str,
        report_id: str | None,
        actor_config: ActorConfig | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._vendor_uri = vendor_uri
        self._report_id = report_id
        self._actor_config = actor_config

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        # Skip if vendor already has a participant in this case.
        stored_case = self.datalayer.read(case_id)
        if isinstance(stored_case, VulnerabilityCase):
            if self._vendor_uri in stored_case.actor_participant_index:
                logger.debug(
                    "%s: vendor '%s' already in actor_participant_index"
                    " for case '%s' — skipping",
                    self.name,
                    self._vendor_uri,
                    case_id,
                )
                return Status.SUCCESS

        initial_status = _build_owner_initial_status(
            self.datalayer,
            self._vendor_uri,
            case_id,
            self._report_id,
            RM.RECEIVED,
        )

        # Roles come from the local ActorConfig (CFG-07-002, CFG-07-004) so
        # role guards (e.g. CheckVendorRoleNode) work for vendors without
        # mislabelling coordinators as vendors.  A future spec amendment
        # should carry role hints in the CaseProposal itself so the CaseActor
        # does not have to rely on co-located configuration.
        participant = VultronParticipant(
            attributed_to=self._vendor_uri,
            context=case_id,
            case_roles=_effective_case_roles(self._actor_config),
            participant_statuses=[initial_status],
        )

        updated_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id,
            self._vendor_uri,
            self.logger,
        )
        if updated_case is None:
            self.feedback_message = f"Case '{case_id}' not found in DataLayer"
            return Status.FAILURE

        self.datalayer.save(updated_case)
        logger.info(
            "%s: Added report receiver '%s' with roles %s at RM.RECEIVED"
            " in case '%s' (ADR-0041 AC-1)",
            self.name,
            self._vendor_uri,
            [r.value for r in participant.case_roles],
            case_id,
        )
        return Status.SUCCESS


class _AddReporterParticipantNode(DataLayerActionWithPorts):
    """Add the reporter as a participant at RM.ACCEPTED.

    Reads the reporter's actor URI from ``VulnerabilityReport.attributed_to``
    in the DataLayer.  Per ADR-0041 AC-2, the reporter is added at
    RM.ACCEPTED — they submitted the report, which is already accepted.

    No-ops gracefully when the report cannot be found (logs a warning, returns
    SUCCESS) so the overall flow is not blocked by a missing reporter.

    **Why degrading is right here, and where it went wrong.** The case is valid
    without this participant: a proposal names the vendor and the case actor
    directly, and refusing the whole case because one *derived* participant could
    not be built would lose more than it protects. So SUCCESS is correct.

    What was wrong was that this node, ``_CommitNativeLedgerEntriesNode`` and
    ``_SeedReporterSignatoryNode`` each independently discovered the same missing
    write and each logged its own symptom, so one lost report read as three
    unrelated shrugs and nothing named the cause (#2482 AC-4). The write belongs
    to ``_StoreProposalReportNode``, which now says so loudly and in one place;
    these three name it in their warnings so a reader lands on the cause rather
    than on the third symptom.

    Reads ``case_id`` from the blackboard.
    """

    def __init__(
        self,
        report_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _resolve_reporter_uri(self, report_id: str) -> str | None:
        assert self.datalayer is not None
        raw_report = self.datalayer.read(report_id)
        if not isinstance(raw_report, VulnerabilityReport):
            logger.warning(
                "%s: report '%s' not found, so the reporter cannot be"
                " identified — skipping reporter participant (best-effort)."
                " The report is written by _StoreProposalReportNode from the"
                " copy the proposal carries inline (CP-01-004); if that node"
                " logged nothing, the proposal arrived without one",
                self.name,
                report_id,
            )
            return None
        reporter_uri = getattr(raw_report, "attributed_to", None)
        if not isinstance(reporter_uri, str) or not reporter_uri:
            logger.warning(
                "%s: report '%s' has no attributed_to — skipping reporter"
                " participant (best-effort)",
                self.name,
                report_id,
            )
            return None
        return reporter_uri

    def _already_has_participant(self, case_id: str, actor_uri: str) -> bool:
        assert self.datalayer is not None
        stored_case = self.datalayer.read(case_id)
        if not isinstance(stored_case, VulnerabilityCase):
            return False
        if actor_uri in stored_case.actor_participant_index:
            logger.debug(
                "%s: '%s' already in actor_participant_index for case '%s'"
                " — skipping",
                self.name,
                actor_uri,
                case_id,
            )
            return True
        return False

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._report_id is None:
            logger.debug(
                "%s: no report_id — skipping reporter participant", self.name
            )
            return Status.SUCCESS

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        reporter_uri = self._resolve_reporter_uri(self._report_id)
        if reporter_uri is None:
            return Status.SUCCESS

        if self._already_has_participant(case_id, reporter_uri):
            return Status.SUCCESS

        accepted_status = _get_or_create_accepted_status(
            self.datalayer,
            reporter_uri,
            self._report_id,
            self.name,
            self.logger,
            cvd_role=[CVDRole.REPORTER],
            em_consent_state=PEC.NO_EMBARGO,
        )

        participant = VultronParticipant(
            attributed_to=reporter_uri,
            context=case_id,
            case_roles=[CVDRole.REPORTER],
            participant_statuses=(
                [accepted_status] if accepted_status is not None else []
            ),
        )

        updated_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id,
            reporter_uri,
            self.logger,
        )
        if updated_case is None:
            self.feedback_message = f"Case '{case_id}' not found in DataLayer"
            return Status.FAILURE

        self.datalayer.save(updated_case)
        logger.info(
            "%s: Added reporter '%s' as REPORTER at RM.ACCEPTED"
            " in case '%s' (ADR-0041 AC-2)",
            self.name,
            reporter_uri,
            case_id,
        )
        return Status.SUCCESS


class _CommitNativeLedgerEntriesNode(DataLayerActionWithPorts):
    """Commit canonical ledger entries natively for CaseActor initialization.

    Commits entries in causal order per ADR-0041 AC-4:

      1. ``create_case``                     actor=CaseActor
      2. ``add_report_to_case``              actor=CaseActor
      3. ``add_participant_status_to_participant`` × N  actor=CaseActor
      4. ``add_case_status_to_case``         actor=vendor (the vendor set the
         genesis case status; ``("Add","CaseStatus")`` is nonetheless in
         ``_CASE_AUTHORED_SIGNATURES`` per CLP-12-001, so a CaseActor-authored
         entry would also validate)

    Best-effort: a single failed entry logs a warning but does not abort
    the Sequence; initialization proceeds regardless (the ledger is an
    audit record, not a precondition for the Accept/Create emissions).

    Reads ``case_id`` from the blackboard.
    """

    def __init__(
        self,
        vendor_uri: str,
        report_id: str | None,
        offer_id: str | None = None,
        offer_actor_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._vendor_uri = vendor_uri
        self._report_id = report_id
        self._offer_id = offer_id
        self._offer_actor_id = offer_actor_id
        self._case_id_bb: str | None = None
        self.wire_render_port = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        ports["wire_render_port"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id", "wire_render_port": "/wire_render_port"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        self.wire_render_port = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass
        try:
            self.wire_render_port = self.get_input("wire_render_port")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _commit_one(
        self,
        case_id: str,
        object_id: str,
        event_type: str,
        snapshot: dict[str, Any],
    ) -> bool:
        """Commit one canonical ledger entry.

        Returns ``True`` on success, ``False`` on failure.  Downstream callers
        treat most entries as best-effort (log and continue), but the genesis
        ``create_case`` entry is load-bearing — the root of the CaseActor's
        hash chain — so its result must not be silently discarded.
        """
        assert self.datalayer is not None
        assert self.actor_id is not None
        tree = create_commit_log_entry_tree(
            case_id=case_id,
            object_id=object_id,
            event_type=event_type,
            payload_snapshot=snapshot,
            disposition="recorded",
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=tree, actor_id=self.actor_id)
        if result.status != Status.SUCCESS:
            logger.warning(
                "%s: could not commit '%s' entry for case '%s' (best-effort): %s",
                self.name,
                event_type,
                case_id,
                result.feedback_message,
            )
            return False
        return True

    def _find_offer_id_for_report(
        self, report_id: str
    ) -> tuple[str | None, str | None]:
        """Return ``(offer_id, offer_actor_id)`` for *report_id*.

        Its own store first, then what the proposal carried (CP-01-007). The
        store answers only when this CaseActor received the
        ``Offer(VulnerabilityReport)`` itself — which a co-located one does not,
        because the ``OfferRecord`` belongs to the sibling that did and there is
        no read across that line (ADR-0073, PCR-01-003).

        The fallback is not a nicety. Every invited actor rebuilds its
        ``VultronOfferRecord`` from this entry's ``offerId``
        (``ApplyOfferReportFromLedgerNode``, ADR-0035 DL-06-002), and that node
        is deliberately lenient — a snapshot without one is skipped
        "(non-fatal)". So the omission surfaced nowhere near here: the invitee's
        ``validate-report`` answered ``404 Offer not found`` (#2548).
        """
        assert self.datalayer is not None
        offer_id, offer_actor_id = find_offer_for_report(
            self.datalayer, report_id
        )
        if offer_id:
            return offer_id, offer_actor_id
        return self._offer_id, self._offer_actor_id

    def _commit_add_reports(
        self, case: VulnerabilityCase, case_id: str
    ) -> None:
        assert self.datalayer is not None
        assert self.actor_id is not None
        assert self.wire_render_port is not None
        for report_id in case.vulnerability_reports:
            raw_report = self.datalayer.read(report_id)
            if not isinstance(raw_report, VulnerabilityReport):
                logger.warning(
                    "%s: report '%s' not found — skipping"
                    " add_report_to_case (best-effort). The report is written"
                    " by _StoreProposalReportNode from the copy the proposal"
                    " carries inline (CP-01-004); if that node logged nothing,"
                    " the proposal arrived without one",
                    self.name,
                    report_id,
                )
                continue
            offer_id, offer_actor_id = self._find_offer_id_for_report(
                report_id
            )
            snapshot = build_add_report_to_case_snapshot(
                raw_report,
                case,
                self.actor_id,
                case_id,
                self.wire_render_port,
                offer_id=offer_id,
                offer_actor_id=offer_actor_id,
            )
            self._commit_one(
                case_id, report_id, "add_report_to_case", snapshot
            )

    def _commit_participant_statuses(
        self, case: VulnerabilityCase, case_id: str
    ) -> None:
        assert self.datalayer is not None
        assert self.actor_id is not None
        for participant_ref in case.case_participants:
            participant_id = (
                participant_ref
                if isinstance(participant_ref, str)
                else getattr(participant_ref, "id_", None)
            )
            if not participant_id:
                continue
            raw_participant = self.datalayer.read(participant_id)
            if not isinstance(raw_participant, CaseParticipant):
                logger.warning(
                    "%s: participant '%s' not found — skipping"
                    " participant_status entry (best-effort)",
                    self.name,
                    participant_id,
                )
                continue
            self._commit_one_participant_statuses(raw_participant, case_id)

    def _commit_one_participant_statuses(
        self, participant: CaseParticipant, case_id: str
    ) -> None:
        assert self.actor_id is not None
        assert self.wire_render_port is not None
        for status in participant.participant_statuses:
            if not isinstance(status, ParticipantStatus):
                continue
            status_id = getattr(status, "id_", None)
            if not status_id:
                continue
            snapshot = build_add_participant_status_snapshot(
                status,
                participant,
                self.actor_id,
                case_id,
                self.wire_render_port,
            )
            self._commit_one(
                case_id,
                status_id,
                "add_participant_status_to_participant",
                snapshot,
            )

    def _commit_case_statuses(
        self, case: VulnerabilityCase, case_id: str
    ) -> None:
        assert self.datalayer is not None
        assert self.wire_render_port is not None
        for status_ref in case.case_statuses:
            if isinstance(status_ref, CaseStatus):
                status = status_ref
            elif isinstance(status_ref, str):
                raw = self.datalayer.read(status_ref)
                if not isinstance(raw, CaseStatus):
                    continue
                status = raw
            else:
                continue
            status_id = getattr(status, "id_", None)
            if not status_id:
                continue
            snapshot = build_add_case_status_snapshot(
                status,
                case,
                self._vendor_uri,
                case_id,
                self.wire_render_port,
            )
            self._commit_one(
                case_id, status_id, "add_case_status_to_case", snapshot
            )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        raw_case = self.datalayer.read(case_id)
        if not isinstance(raw_case, VulnerabilityCase):
            logger.warning(
                "%s: case '%s' not found — skipping ledger entries"
                " (best-effort)",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        case = raw_case
        # 1. create_case  (actor = CaseActor, in _CASE_AUTHORED_SIGNATURES)
        #
        # The genesis create_case entry is the root of the CaseActor's
        # canonical hash chain.  Unlike the remaining best-effort entries, a
        # failure here must NOT be masked: if the genesis entry is missing,
        # the CaseActor's authoritative ledger has no root and every later
        # entry (and every replica seeded from it) is broken.  Fail fast so
        # the enclosing Sequence aborts before Accept/Create are emitted, and
        # the vendor is not told a case exists that has no canonical ledger.
        if self.wire_render_port is None:
            self.feedback_message = "wire_render_port not available"
            logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if not self._commit_one(
            case_id,
            case_id,
            "create_case",
            build_create_case_snapshot(
                case, self.actor_id, case_id, self.wire_render_port
            ),
        ):
            self.feedback_message = (
                f"genesis create_case ledger commit failed for case"
                f" '{case_id}' — aborting native initialization"
            )
            logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        # 2. add_report_to_case  (actor = CaseActor)
        self._commit_add_reports(case, case_id)
        # 3. add_participant_status × N  (actor = CaseActor)
        self._commit_participant_statuses(case, case_id)
        # 4. add_case_status  (actor = vendor_uri — provenance, not a guard
        #    constraint: ("Add","CaseStatus") IS in _CASE_AUTHORED_SIGNATURES
        #    per CLP-12-001, so a CaseActor-authored entry validates too)
        self._commit_case_statuses(case, case_id)

        logger.info(
            "%s: native ledger entries committed for case '%s' (ADR-0041 AC-4)",
            self.name,
            case_id,
        )
        return Status.SUCCESS


def _seed_participant_as_signatory(
    datalayer: CasePersistence,
    stored_case: VulnerabilityCase,
    participant: CaseParticipant,
    log_label: str,
    spec_ref: str,
) -> None:
    """Seed *participant* as embargo SIGNATORY on *stored_case*'s active embargo.

    Shared by ``_SeedVendorOwnerSignatoryNode`` (CM-13) and
    ``_SeedReporterSignatoryNode`` (CM-14-005). Uses
    ``apply_pec_transition(PEC_Trigger.ACCEPT)`` — the authoritative
    consent-write path (CM-18-005, ADR-0048) — to update both the PEC state
    machine and ``ParticipantStatus.consent`` atomically. The idempotency
    guard (``!= PEC.SIGNATORY``) prevents double-transitions on retries.
    """
    # `active_embargo_id`, not the field: it may hold the whole EmbargoEvent
    # when a received case carried one (AKM-03-001), and this list holds ids.
    embargo_id = stored_case.active_embargo_id
    if participant.embargo_consent_state != PEC.SIGNATORY:
        participant.apply_pec_transition(PEC_Trigger.ACCEPT)
    if embargo_id and embargo_id not in participant.accepted_embargo_ids:
        participant.accepted_embargo_ids.append(embargo_id)
    datalayer.save(participant)
    logger.info(
        "Seeded %s as embargo SIGNATORY in case '%s' (%s)",
        log_label,
        stored_case.id_,
        spec_ref,
    )


class _SeedVendorOwnerSignatoryNode(DataLayerActionWithPorts):
    """Seed the vendor (CASE_OWNER) participant as embargo SIGNATORY (CM-13).

    ``InitializeDefaultEmbargoNode`` ends in ``SeedOwnerAsSignatoryNode``,
    which seeds the participant found at
    ``actor_participant_index.get(self.actor_id)`` — i.e. the *acting* actor.
    In the original vendor tree the acting actor was the case owner, so that
    worked.  Here the acting actor is the **CaseActor**, which is NOT a
    participant in this case, so ``SeedOwnerAsSignatoryNode`` silently
    no-ops and no participant becomes a signatory.

    Per CM-13 / ``notes/embargo-default-semantics.md`` (BUG-26042204), when a
    case is created with an ACTIVE default embargo the case owner MUST be
    seeded as ``SIGNATORY`` — it makes no sense for the owner to be locked out
    of their own embargo.  This node seeds the vendor participant explicitly by
    ``vendor_uri`` (not by ``actor_id``), closing the gap left by the reused
    node.

    Best-effort: if the case or vendor participant cannot be resolved, logs a
    warning and returns SUCCESS so the enclosing Sequence is not blocked (the
    embargo itself is already ACTIVE; a missing consent seed is a warning, not
    a hard stop).

    Reads ``case_id`` from the blackboard.
    """

    def __init__(
        self,
        vendor_uri: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._vendor_uri = vendor_uri

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE
            return Status.FAILURE

        stored_case = self.datalayer.read(case_id, raise_on_missing=False)
        if not isinstance(stored_case, VulnerabilityCase):
            logger.warning(
                "%s: case '%s' not found — cannot seed vendor SIGNATORY"
                " (best-effort)",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        if stored_case.active_embargo is None:
            logger.debug(
                "%s: no active embargo on case '%s' — nothing to seed",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        participant_id = stored_case.actor_participant_index.get(
            self._vendor_uri
        )
        if not participant_id:
            logger.warning(
                "%s: vendor '%s' has no participant in case '%s' —"
                " cannot seed SIGNATORY (best-effort)",
                self.name,
                self._vendor_uri,
                case_id,
            )
            return Status.SUCCESS

        participant = self.datalayer.read(
            participant_id, raise_on_missing=False
        )
        if not isinstance(participant, CaseParticipant):
            logger.warning(
                "%s: vendor participant '%s' not found in case '%s' —"
                " cannot seed SIGNATORY (best-effort)",
                self.name,
                participant_id,
                case_id,
            )
            return Status.SUCCESS

        self._seed_signatory(stored_case, participant)
        return Status.SUCCESS

    def _seed_signatory(
        self,
        stored_case: VulnerabilityCase,
        participant: CaseParticipant,
    ) -> None:
        assert self.datalayer is not None
        _seed_participant_as_signatory(
            self.datalayer,
            stored_case,
            participant,
            log_label=f"vendor '{self._vendor_uri}'",
            spec_ref="CM-13",
        )


class _SeedReporterSignatoryNode(DataLayerActionWithPorts):
    """Seed the reporter participant as embargo SIGNATORY (CM-14-005).

    CM-14-005 requires: "When the reporter is added as a participant during
    case initialization, they MUST be seeded as SIGNATORY on any active
    embargo."  The reporter's consent is *implicit* in submitting the report
    (ADR-0048) — no invitation round-trip is needed.

    This node runs after ``InitializeDefaultEmbargoNode`` (so the embargo is
    already ACTIVE) and after ``_AddReporterParticipantNode`` (so the
    participant record exists).  It resolves the reporter URI from the report
    in the DataLayer, looks up the participant, and calls
    ``apply_pec_transition(PEC_Trigger.ACCEPT)`` via the shared helper so that
    both the PEC state machine and the ``ParticipantStatus.consent`` dimension
    are updated atomically (CM-18-005, CM-18-006, ADR-0048).

    Best-effort: if the report, reporter URI, or participant cannot be
    resolved, or if there is no active embargo, the node logs a warning and
    returns SUCCESS so the enclosing Sequence is not blocked.

    Reads ``case_id`` from the blackboard.
    """

    def __init__(
        self,
        report_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _resolve_reporter_uri(self, report_id: str) -> str | None:
        assert self.datalayer is not None
        raw_report = self.datalayer.read(report_id)
        if not isinstance(raw_report, VulnerabilityReport):
            logger.warning(
                "%s: report '%s' not found, so the reporter cannot be"
                " identified — skipping reporter SIGNATORY seed"
                " (best-effort). The report is written by"
                " _StoreProposalReportNode from the copy the proposal carries"
                " inline (CP-01-004); if that node logged nothing, the"
                " proposal arrived without one",
                self.name,
                report_id,
            )
            return None
        reporter_uri = getattr(raw_report, "attributed_to", None)
        if not isinstance(reporter_uri, str) or not reporter_uri:
            logger.warning(
                "%s: report '%s' has no attributed_to — skipping reporter"
                " SIGNATORY seed (best-effort)",
                self.name,
                report_id,
            )
            return None
        return reporter_uri

    def _resolve_participant(
        self, case_id: str, reporter_uri: str
    ) -> tuple[VulnerabilityCase | None, CaseParticipant | None]:
        """Return (case, participant) for *reporter_uri*, or (None, None) on miss."""
        assert self.datalayer is not None
        stored_case = self.datalayer.read(case_id, raise_on_missing=False)
        if not isinstance(stored_case, VulnerabilityCase):
            logger.warning(
                "%s: case '%s' not found — cannot seed reporter SIGNATORY"
                " (best-effort)",
                self.name,
                case_id,
            )
            return None, None
        if stored_case.active_embargo is None:
            logger.debug(
                "%s: no active embargo on case '%s' — nothing to seed for"
                " reporter",
                self.name,
                case_id,
            )
            return None, None
        participant_id = stored_case.actor_participant_index.get(reporter_uri)
        if not participant_id:
            logger.warning(
                "%s: reporter '%s' has no participant in case '%s' —"
                " cannot seed SIGNATORY (best-effort)",
                self.name,
                reporter_uri,
                case_id,
            )
            return None, None
        participant = self.datalayer.read(
            participant_id, raise_on_missing=False
        )
        if not isinstance(participant, CaseParticipant):
            logger.warning(
                "%s: reporter participant '%s' not found in case '%s' —"
                " cannot seed SIGNATORY (best-effort)",
                self.name,
                participant_id,
                case_id,
            )
            return None, None
        return stored_case, participant

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._report_id is None:
            logger.debug(
                "%s: no report_id — skipping reporter SIGNATORY seed",
                self.name,
            )
            return Status.SUCCESS

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        reporter_uri = self._resolve_reporter_uri(self._report_id)
        if reporter_uri is None:
            return Status.SUCCESS

        stored_case, participant = self._resolve_participant(
            case_id, reporter_uri
        )
        if stored_case is None or participant is None:
            return Status.SUCCESS

        self._seed_signatory(stored_case, participant)
        return Status.SUCCESS

    def _seed_signatory(
        self,
        stored_case: VulnerabilityCase,
        participant: CaseParticipant,
    ) -> None:
        assert self.datalayer is not None
        _seed_participant_as_signatory(
            self.datalayer,
            stored_case,
            participant,
            log_label="reporter",
            spec_ref="CM-14-005",
        )


class _EmitAcceptCaseProposalNode(DataLayerActionWithPorts):
    """Build Accept(CaseProposal), store it, and queue it to the outbox.

    Sets ``accept_activity_id`` on the blackboard so the downstream
    ``_WriteCreateCaseMarkerNode`` can set the causal ``in_reply_to``
    link on ``Create(VulnerabilityCase)`` (CP-05-003, ADR-0045).

    Reads ``case_id`` from the blackboard (written by either
    ``_LoadExistingCaseNode`` or ``_CreateCaseFromProposalNode``) and
    sets ``result`` on the ``Accept`` activity to that URI.  For a
    duplicate proposal, this carries the existing-case reference required
    by CP-05-006 AC-2.  For a first-time proposal, it ties the Accept to
    the newly-created case.

    Failure here returns FAILURE so the Sequence aborts before the
    Create(VulnerabilityCase) is sent — the vendor should not receive an
    unacknowledged case (BT-14-001).
    """

    def __init__(
        self,
        proposal_id: str,
        vendor_uri: str,
        proposal_dict: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._vendor_uri = vendor_uri
        # proposal_dict is the wire-serialised proposal (model_dump(by_alias=True)).
        # Storing it inline satisfies CP-05-003 and the outbox AKM-03-001 requirement.
        self._object = (
            proposal_dict if proposal_dict is not None else proposal_id
        )

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "accept_activity_id": PortInformation(data_type=str, required=True)
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "accept_activity_id": "/accept_activity_id",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._case_id_bb: str | None = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self._case_id_bb

        activity = VultronAccept(
            actor=self.actor_id,
            object_=self._object,
            to=[self._vendor_uri],
            result=case_id,
        )

        try:
            self.datalayer.create(activity)
        except ValueError as exc:
            self.feedback_message = (
                f"Accept(CaseProposal) activity creation failed: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # `outbox_append`, not `record_outbox_item`: the queue lives in the
        # owning actor's store, so it takes no actor argument (ADR-0073).
        cast(CaseOutboxPersistence, self.datalayer).outbox_append(activity.id_)
        self._set_output("accept_activity_id", activity.id_)
        logger.info(
            "%s: Queued Accept(CaseProposal) '%s' to outbox for vendor '%s'",
            self.name,
            activity.id_,
            self._vendor_uri,
        )
        return Status.SUCCESS


class _EmitCreateVulnerabilityCaseNode(DataLayerAction):
    """Reconstruct Create(VulnerabilityCase) from the stored marker and queue it.

    Reads the pre-constructed ``Create(VulnerabilityCase)`` payload from the
    ``PendingCreateCaseActivity`` marker written by
    ``_WriteCreateCaseMarkerNode``.  Using the stored payload (rather than
    building a new activity from blackboard fields) guarantees that the
    activity ``id_`` in the DataLayer and outbox is identical to the ``id_``
    recorded in the marker.  This is critical for CP-05-005 idempotency: the
    retry runner checks outbox membership by the marker's stored ``id_``, so
    a fresh ``id_`` here would cause a duplicate delivery after crash/restart.

    Failure returns FAILURE so the enclosing Sequence surfaces it; the Accept
    has already been sent at this point (CP-05-005 covers the retry case).
    """

    def __init__(
        self,
        proposal_id: str,
        vendor_uri: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._vendor_uri = vendor_uri

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        # Read the pre-built payload from the marker to guarantee id_ consistency
        # with CP-05-005 retry logic.
        marker_id = PendingCreateCaseActivity.build_id(self._proposal_id)
        raw_marker = self.datalayer.read(marker_id)
        if not isinstance(raw_marker, PendingCreateCaseActivity):
            self.feedback_message = (
                f"PendingCreateCaseActivity marker '{marker_id}' not found"
                " or wrong type; cannot emit Create(VulnerabilityCase)"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if not raw_marker.create_activity_payload:
            self.feedback_message = (
                f"Marker '{marker_id}' has no create_activity_payload"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            activity = VultronCreateCaseActivity.model_validate(
                raw_marker.create_activity_payload
            )
        except Exception as exc:
            self.feedback_message = (
                f"Could not reconstruct Create(VulnerabilityCase)"
                f" from marker '{marker_id}': {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            self.datalayer.create(activity)
        except ValueError as exc:
            self.feedback_message = (
                f"Create(VulnerabilityCase) activity creation failed: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity.id_
            )
        except Exception as exc:
            self.feedback_message = (
                f"Failed to enqueue Create(VulnerabilityCase) to outbox: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        logger.info(
            "%s: Queued Create(VulnerabilityCase) '%s' from proposal '%s'",
            self.name,
            activity.id_,
            self._proposal_id,
        )
        return Status.SUCCESS


class _WriteCreateCaseMarkerNode(DataLayerActionWithPorts):
    """Write a ``PendingCreateCaseActivity`` marker to the DataLayer.

    Called after ``Accept(CaseProposal)`` has been sent and before
    ``Create(VulnerabilityCase)`` is attempted.  The marker records the
    obligation so that a retry runner (#1139) can complete it if the
    subsequent ``Create(VulnerabilityCase)`` delivery fails (CP-05-005).

    Reads ``case_id`` and ``accept_activity_id`` from the blackboard to
    pre-construct the ``Create(VulnerabilityCase)`` payload stored in the
    marker.  Returns FAILURE if either blackboard key is missing or the
    DataLayer write fails, so the Sequence halts before attempting delivery.
    """

    def __init__(
        self,
        proposal_id: str,
        vendor_uri: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._vendor_uri = vendor_uri
        self.wire_render_port = None
        self._case_id_bb: str | None = None
        self._accept_activity_id_bb: str | None = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        ports["accept_activity_id"] = PortInformation(
            data_type=str, required=False
        )
        ports["wire_render_port"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "accept_activity_id": "/accept_activity_id",
            "wire_render_port": "/wire_render_port",
        }

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        self._accept_activity_id_bb = None
        self.wire_render_port = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = None
        try:
            self._accept_activity_id_bb = self.get_input("accept_activity_id")
        except (NoDataAvailable, NotImplementedError):
            self._accept_activity_id_bb = None
        try:
            self.wire_render_port = self.get_input("wire_render_port")
        except (NoDataAvailable, NotImplementedError):
            self.wire_render_port = None

    def _collect_reporter_uris(self, case_id: str) -> list[str]:
        """Return URIs of REPORTER/FINDER participants in *case_id*, excluding vendor.

        CaseActor bootstraps non-vendor participants (ADR-0041 AC-5) by including
        them as direct ``to`` recipients of ``Create(VulnerabilityCase)`` so their
        DataLayers can seed a case replica immediately via
        ``CreateCaseReceivedUseCase`` without waiting for the
        ``Offer(CaseManagerRole)`` round-trip (which ADR-0041 removes).
        """
        assert self.datalayer is not None
        raw_case = self.datalayer.read(case_id)
        if not isinstance(raw_case, VulnerabilityCase):
            return []
        uris: list[str] = []
        for p_id in raw_case.actor_participant_index.values():
            p = self.datalayer.read(p_id)
            if not isinstance(p, CaseParticipant):
                continue
            if (
                CVDRole.REPORTER not in p.roles
                and CVDRole.FINDER not in p.roles
            ):
                continue
            uri = getattr(p, "attributed_to", None)
            if isinstance(uri, str) and uri and uri != self._vendor_uri:
                uris.append(uri)
        return uris

    def _build_case_object(self, case_id: str) -> "dict[str, Any] | None":
        assert self.datalayer is not None
        raw_case = self.datalayer.read(case_id)
        if not isinstance(raw_case, VulnerabilityCase):
            return None
        # Materialise each participant ref so _store_embedded_participants
        # on the vendor side receives full objects, not bare ID strings (AC-5).
        materialized: list[Any] = []
        for ref in raw_case.case_participants:
            if isinstance(ref, str):
                p_obj = self.datalayer.read(ref)
                materialized.append(p_obj if p_obj is not None else ref)
            else:
                materialized.append(ref)
        case_copy = raw_case.model_copy(
            update={"case_participants": materialized}
        )
        if self.wire_render_port is None:
            logger.warning(
                "%s: wire_render_port not available; cannot render case object",
                self.name,
            )
            return None
        case_dict = self.wire_render_port.render(case_copy)
        case_dict.setdefault("type", "VulnerabilityCase")
        # Inline full VulnerabilityReport dicts after render so invited
        # actors' _store_embedded_reports stores them (CBT-01-007, ISSUE-2134).
        # Done post-render because VulnerabilityCase.vulnerability_reports is
        # typed list[str]; embedding objects directly triggers Pydantic warnings.
        inlined_reports: list[Any] = []
        for ref in raw_case.vulnerability_reports:
            if isinstance(ref, str):
                r_obj = self.datalayer.read(ref)
                if isinstance(r_obj, VulnerabilityReport):
                    r_dict = self.wire_render_port.render(r_obj)
                    r_dict.setdefault("type", "VulnerabilityReport")
                    inlined_reports.append(r_dict)
                else:
                    inlined_reports.append(ref)
            else:
                inlined_reports.append(ref)
        case_dict["vulnerability_reports"] = inlined_reports
        return case_dict

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        accept_activity_id = self._accept_activity_id_bb
        if not isinstance(accept_activity_id, str):
            self.feedback_message = (
                "accept_activity_id not found in blackboard"
            )
            return Status.FAILURE

        # Pre-construct the payload that will be (re-)sent as
        # Create(VulnerabilityCase).  Mirrors the logic in
        # _EmitCreateVulnerabilityCaseNode so the retry runner (#1139)
        # can reconstruct the exact same activity without re-running the BT.
        # AC-5 (ADR-0041): embed full inline case object with materialised
        # participants so _store_embedded_participants seeds the vendor replica.
        case_object = self._build_case_object(case_id)
        if case_object is None:
            self.feedback_message = (
                f"VulnerabilityCase {case_id!r} not found in DataLayer"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # ADR-0041 AC-5: bootstrap all known participants directly.
        # Include REPORTER/FINDER URIs so their DataLayers receive the case
        # replica immediately; CreateCaseReceivedUseCase handles them via the
        # non-vendor participant path (no ReportCaseLink required).
        # CP-05-003 / ADR-0045: context = case URI (deferral routing key);
        # in_reply_to = Accept URI (causal antecedent, AS2-correct field).
        reporter_uris = self._collect_reporter_uris(case_id)
        create_activity = VultronCreateCaseActivity(
            actor=self.actor_id,
            object_=case_object,
            context=case_id,
            in_reply_to=accept_activity_id,
            to=[self._vendor_uri] + reporter_uris,
        )
        payload = create_activity.model_dump(by_alias=True)

        marker = PendingCreateCaseActivity(
            proposal_id=self._proposal_id,
            case_actor_id=self.actor_id,
            vendor_uri=self._vendor_uri,
            create_activity_payload=payload,
        )

        try:
            self.datalayer.save(marker)
        except Exception as exc:
            self.feedback_message = f"Failed to write marker: {exc}"
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        logger.info(
            "%s: Wrote PendingCreateCaseActivity marker for proposal '%s'",
            self.name,
            self._proposal_id,
        )
        return Status.SUCCESS


class _ClearCreateCaseMarkerNode(DataLayerAction):
    """Remove the ``PendingCreateCaseActivity`` marker after successful delivery.

    Called after ``Create(VulnerabilityCase)`` has been queued to the
    outbox.  Deletes the marker so the retry runner (#1139) does not
    re-deliver an already-sent activity (CP-05-005, AC-3).

    Always returns SUCCESS: the ``Create(VulnerabilityCase)`` has already
    been delivered; a cleanup failure must not roll back the delivery or
    fail the Sequence.  A warning is logged if the delete fails so that
    stale markers can be detected during retry-runner inspection.
    """

    def __init__(
        self,
        proposal_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def update(self) -> Status:
        if self.datalayer is None:
            logger.warning(
                "%s: DataLayer not available — marker '%s' may be stale",
                self.name,
                self._proposal_id,
            )
            return Status.SUCCESS

        marker_id = PendingCreateCaseActivity.build_id(self._proposal_id)
        deleted = self.datalayer.delete("PendingCreateCaseActivity", marker_id)
        if deleted:
            logger.info(
                "%s: Cleared PendingCreateCaseActivity marker for proposal '%s'",
                self.name,
                self._proposal_id,
            )
        else:
            logger.warning(
                "%s: PendingCreateCaseActivity marker for proposal '%s'"
                " was not found during cleanup — may already be cleared",
                self.name,
                self._proposal_id,
            )
        return Status.SUCCESS


def _offer_provenance_from_proposal(
    proposal_dict: dict | None,
) -> tuple[str | None, str | None]:
    """Return ``(offer_id, offer_actor_id)`` carried on the proposal (CP-01-007).

    Both spellings are accepted for the same reason
    ``_StoreProposalReportNode._report_from_proposal_dict`` accepts both: which
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
) -> py_trees.behaviour.Behaviour:
    """Return the received-side BT for processing a ``Create(as_CaseProposal)``.

    The tree is a two-branch Selector implementing CP-05-006 idempotency:

    **Branch 1 — AC-3 guard** (``_CheckMarkerExistsNode``):
      If a ``PendingCreateCaseActivity`` marker already exists for this
      proposal_id, ``Accept(CaseProposal)`` was already sent and
      ``Create(VulnerabilityCase)`` delivery is still pending.  Return SUCCESS
      immediately — the retry runner owns recovery; do not re-send Accept.

    **Branch 2 — normal / duplicate flow** (Sequence):
      First, a sub-Selector resolves which ``VulnerabilityCase`` to use:

      * ``_LoadExistingCaseNode`` (AC-1/AC-2): if a case already exists for
        *report_id*, write its ID to the blackboard and succeed.
      * ``_CreateCaseFromProposalNode`` (normal path): create a new case.

      Then CaseActor-native initialization steps (ADR-0041):

      3. ``_AddCaseActorParticipantNode`` — CaseActor registered as
         COORDINATOR + CASE_MANAGER (ADR-0041)
      4. ``_AddVendorOwnerParticipantNode`` — proposing actor added as
         CASE_OWNER (plus ``actor_config.default_case_roles``) at RM.RECEIVED
         (ADR-0041 AC-1)
      5. ``_AddReporterParticipantNode`` — reporter added at RM.ACCEPTED
         (ADR-0041 AC-2)
      6. ``InitializeDefaultEmbargoNode`` — default embargo initialized
         (ADR-0041 AC-3)
      7. ``_SeedVendorOwnerSignatoryNode`` — vendor (CASE_OWNER) seeded as
         embargo SIGNATORY (CM-13)
      8. ``_SeedReporterSignatoryNode`` — reporter seeded as embargo
         SIGNATORY (CM-14-005); implicit consent per ADR-0048
      9. ``_CommitNativeLedgerEntriesNode`` — canonical ledger entries
         committed (ADR-0041 AC-4)

      Then the outbound messaging steps:

      10. ``_EmitAcceptCaseProposalNode`` — emits Accept(as_CaseProposal)
      11. ``_WriteCreateCaseMarkerNode`` — writes durable retry marker with
         inline case object (CP-05-005, ADR-0041 AC-5)
      12. ``_EmitCreateVulnerabilityCaseNode`` — emits
         Create(VulnerabilityCase) with inline participants
      13. ``_ClearCreateCaseMarkerNode`` — removes marker on success
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

    Returns:
        A py_trees Selector behaviour ready for ``BTBridge.execute_with_setup``.
    """
    from vultron.core.behaviors.case.embargo_tree import (
        InitializeDefaultEmbargoNode,
    )

    offer_id, offer_actor_id = _offer_provenance_from_proposal(proposal_dict)

    # Sub-Selector: reuse existing case (duplicate) OR create new (normal path)
    case_resolution = py_trees.composites.Selector(
        name="ResolveCaseIdSelector",
        memory=False,
        children=[
            _LoadExistingCaseNode(report_id=report_id),
            _CreateCaseFromProposalNode(report_id=report_id),
        ],
    )

    # Main flow: resolve case → native init → emit Accept → write marker →
    # emit Create → clear marker
    main_flow = py_trees.composites.Sequence(
        name="CreateCaseProposalReceivedBT",
        memory=False,
        children=[
            case_resolution,
            # Store the inline report first: the reporter participant, its ledger
            # entry and the SIGNATORY seed are all derived from it, and each of
            # those nodes skips "best-effort" when it is missing.
            _StoreProposalReportNode(
                report_id=report_id,
                proposal_dict=proposal_dict,
                inline_report=inline_report,
            ),
            # ADR-0041: register CaseActor as COORDINATOR + CASE_MANAGER
            _AddCaseActorParticipantNode(),
            # ADR-0041 AC-1: add vendor as CASE_OWNER at RM.RECEIVED
            _AddVendorOwnerParticipantNode(
                vendor_uri=vendor_uri,
                report_id=report_id,
                actor_config=actor_config,
            ),
            # ADR-0041 AC-2: add reporter at RM.ACCEPTED
            _AddReporterParticipantNode(report_id=report_id),
            # ADR-0041 AC-3: initialize default embargo
            InitializeDefaultEmbargoNode(),
            # CM-13: seed the vendor (CASE_OWNER) as embargo SIGNATORY.
            # InitializeDefaultEmbargoNode's SeedOwnerAsSignatoryNode keys on
            # actor_id (the CaseActor), which is not a participant here, so it
            # no-ops; this node seeds the vendor explicitly.
            _SeedVendorOwnerSignatoryNode(vendor_uri=vendor_uri),
            # CM-14-005: seed the reporter as embargo SIGNATORY.
            # Reporter consent is implicit in submitting the report (ADR-0048);
            # no invitation round-trip is needed or appropriate.
            _SeedReporterSignatoryNode(report_id=report_id),
            # ADR-0041 AC-4: commit canonical ledger entries natively
            _CommitNativeLedgerEntriesNode(
                vendor_uri=vendor_uri,
                report_id=report_id,
                offer_id=offer_id,
                offer_actor_id=offer_actor_id,
            ),
            # Outbound messaging
            _EmitAcceptCaseProposalNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
                proposal_dict=proposal_dict,
            ),
            _WriteCreateCaseMarkerNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
            ),
            _EmitCreateVulnerabilityCaseNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
            ),
            _ClearCreateCaseMarkerNode(proposal_id=proposal_id),
        ],
    )

    return py_trees.composites.Selector(
        name="CreateCaseProposalIdempotencySelector",
        memory=False,
        children=[
            _CheckMarkerExistsNode(proposal_id=proposal_id),
            main_flow,
        ],
    )
