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


"""Embargo-consent seeding leaf nodes for the CaseProposal received tree.

Seed the vendor (CASE_OWNER, CM-13) and the reporter (CM-14-005) as embargo
SIGNATORY on the case's default active embargo. Composed by
``create_case_proposal_received_tree`` (BTND-07-003).
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger

logger = logging.getLogger(__name__)


def _seed_participant_as_signatory(
    datalayer: CasePersistence,
    stored_case: VulnerabilityCase,
    participant: CaseParticipant,
    log_label: str,
    spec_ref: str,
) -> None:
    """Seed *participant* as embargo SIGNATORY on *stored_case*'s active embargo.

    Shared by ``SeedVendorOwnerSignatoryNode`` (CM-13) and
    ``SeedReporterSignatoryNode`` (CM-14-005). Uses
    ``apply_pec_transition(PEC_Trigger.ACCEPT)`` — the authoritative
    consent-write path (CM-18-005, ADR-0048) — to update both the PEC state
    machine and ``ParticipantStatus.consent`` atomically. The idempotency
    guard (``!= PEC.SIGNATORY``) prevents double-transitions on retries.
    """
    # `active_embargo_id`, not the field: it may hold the whole EmbargoEvent
    # when a received case carried one (AKM-03-001), and this list holds ids.
    embargo_id = stored_case.active_embargo_id
    if participant.embargo_consent_state not in (PEC.SIGNATORY, PEC.DECLINED):
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


class SeedVendorOwnerSignatoryNode(DataLayerActionWithPorts):
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

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

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

        # Regime 2 / best-effort seed (ADR-0087): seeding the vendor SIGNATORY
        # marker is optional enrichment on the receiving side; an absent or
        # still-forming case is skipped as SUCCESS rather than failing the
        # proposal-processing tree (conformance allowlist).
        stored_case = self.datalayer.read_case(case_id, raise_on_missing=False)
        if stored_case is None:
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


class SeedReporterSignatoryNode(DataLayerActionWithPorts):
    """Seed the reporter participant as embargo SIGNATORY (CM-14-005).

    CM-14-005 requires: "When the reporter is added as a participant during
    case initialization, they MUST be seeded as SIGNATORY on any active
    embargo."  The reporter's consent is *implicit* in submitting the report
    (ADR-0048) — no invitation round-trip is needed.

    This node runs after ``InitializeDefaultEmbargoNode`` (so the embargo is
    already ACTIVE) and after ``AddReporterParticipantNode`` (so the
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

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

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
                " StoreProposalReportNode from the copy the proposal carries"
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
        # Regime 2 / best-effort seed (ADR-0087): reporter SIGNATORY seeding is
        # optional enrichment; an absent/forming case is skipped, not failed
        # (conformance allowlist).
        stored_case = self.datalayer.read_case(case_id, raise_on_missing=False)
        if stored_case is None:
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
