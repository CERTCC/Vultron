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
CaseProposal action nodes for the slimmed receive-report tree.

The report receiver proposes a case in two steps, so it may change the
proposal between them (CP-01-026):

- :class:`ConvertReportToCaseProposalNode` converts the received report into
  the core ``CaseProposal``
  (:func:`~vultron.core.services.report_case_proposal.case_proposal_from_report`),
  its ``caseInputs`` filled from the first ``csaf_vulnerability_report``
  reading, and marks on the receiver's own claims record each value the
  conversion used (CSAF-04-004);
- :class:`ProposeReportCaseToActorNode` hands that proposal to the adapter,
  which renders and sends it as ``Create(CaseProposal)`` (ADR-0041).

Both run from a ``report_id`` without a ``VulnerabilityCase`` in the
DataLayer.  The CaseActor's identity comes from
:func:`~vultron.core.behaviors.case.case_actor_identity.case_actor_identity`:
the container's identity, not a per-case one derived from the report
(#1872).
"""

from collections.abc import Sequence

from py_trees.common import Status

from vultron.config import get_config
from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
)
from vultron.core.behaviors.act_keys import REPORT_ID
from vultron.core.behaviors.case.case_actor_identity import (
    case_actor_identity,
)
from vultron.core.behaviors.case.offer_provenance import find_offer_for_report
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.helpers.emit import _EmitSingleActivityBase
from vultron.core.behaviors.node_logger import fail_with_fault
from vultron.core.models.case_proposal import CaseProposal
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_claims import (
    ClaimsReading,
    ReportClaimsRecord,
)
from vultron.core.services.report_case_proposal import (
    ConvertedCaseProposal,
    case_proposal_from_report,
)

#: Blackboard key for the receiver's core ``CaseProposal``, written by
#: :class:`ConvertReportToCaseProposalNode` and sent by
#: :class:`ProposeReportCaseToActorNode`.  A node between them may replace
#: it with a changed copy (CP-01-026).
CASE_PROPOSAL_KEY = "case_proposal"


class ConvertReportToCaseProposalNode(DataLayerActionWithPorts):
    """Convert the received report into the receiver's ``CaseProposal``.

    Reads the report the act names (``report_id``) from this store, and the
    Offer that brought it from this store's offer record (CP-01-007).  The
    proposal is addressed to the container's CaseActor,
    ``{ActorConfig.case_actor_service_url}/actors/case-actor`` (CP-04-003,
    CP-04-005), and states this actor's ``default_case_roles`` (CFG-07-002),
    which the CASE_MANAGER seats it with alongside ``CASE_OWNER`` (CP-01-011,
    CP-01-013, CP-09-007, ADR-0133).

    When the first ``csaf_vulnerability_report`` of *readings* fills case
    inputs, the proposal carries them as ``caseInputs`` (CP-01-026), and the
    receiver's claims record of that reading marks each value the
    conversion used ``applied`` or ``overridden`` (CSAF-04-004).  The record
    stays this actor's own (CSAF-04-005).

    Writes the proposal to ``case_proposal``.  Returns ``FAILURE`` when the
    DataLayer or ``actor_id`` is unavailable, ``case_actor_service_url`` is
    not configured, the report is not in this store, or the claims record
    of the filling reading is not held.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        **act_key_ports(REPORT_ID),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        CASE_PROPOSAL_KEY: PortInformation(
            data_type=CaseProposal, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            CASE_PROPOSAL_KEY: f"/{CASE_PROPOSAL_KEY}",
            **act_key_remappings(REPORT_ID),
        }

    def __init__(
        self,
        readings: Sequence[ClaimsReading] = (),
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._readings = list(readings)

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        report_id = act_value(self, REPORT_ID, str)
        case_actor_id = case_actor_identity()
        if case_actor_id is None:
            return fail_with_fault(
                self,
                "case_actor_service_url is not configured"
                " (set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL)",
            )
        report = self.datalayer.read(report_id)
        if not isinstance(report, VulnerabilityReport):
            return fail_with_fault(
                self,
                f"report '{report_id}' is not held as a VulnerabilityReport"
                " in this store, so no proposal can carry it (CP-01-004)",
            )
        converted = case_proposal_from_report(
            report,
            proposer_id=self.actor_id,
            case_actor_id=case_actor_id,
            readings=self._readings,
            # CP-01-007: this store has the OfferRecord because this actor
            # received the Offer; the CaseActor's own store never will.
            offer_id=find_offer_for_report(self.datalayer, report_id),
            # CP-01-013, ADR-0133: this actor's own roles, which the
            # CASE_MANAGER cannot read from its own configuration.
            proposer_case_roles=get_config().actor.default_case_roles,
            at=self._require_act_instant(),
        )
        if (f := self._mark_used_claims(report_id, converted)) is not None:
            return f
        self._set_output(CASE_PROPOSAL_KEY, converted.proposal)
        self.logger.info(
            "%s: converted report '%s' into proposal '%s' for case-actor"
            " '%s', %s",
            self.name,
            report_id,
            converted.proposal.id_,
            case_actor_id,
            (
                f"caseInputs from document '{converted.reading.document_id}'"
                " (CP-01-026)"
                if converted.reading is not None
                else "with no caseInputs"
            ),
        )
        return Status.SUCCESS

    def _mark_used_claims(
        self, report_id: str, converted: ConvertedCaseProposal
    ) -> Status | None:
        """Mark the values the conversion used on the receiver's record.

        ``None`` when done, or when no reading filled the proposal;
        ``FAILURE`` when the record of the filling reading is not held,
        since the effects that keep the report write it first.
        """
        reading = converted.reading
        if reading is None:
            return None
        assert self.datalayer is not None
        record_id = ReportClaimsRecord.build_id(
            report_id, reading.document_digest
        )
        record = self.datalayer.read(record_id)
        if not isinstance(record, ReportClaimsRecord):
            return fail_with_fault(
                self,
                f"the claims record '{record_id}' of document"
                f" '{reading.document_id}' on report '{report_id}' is not"
                " held, so the values the proposal takes cannot be marked"
                " (CSAF-04-004)",
            )
        self.datalayer.save(record.with_outcomes(converted.outcomes))
        self.logger.info(
            "%s: marked %d value(s) of document '%s' on report '%s' as"
            " used by the proposal (CSAF-04-004)",
            self.name,
            len(converted.outcomes),
            reading.document_id,
            report_id,
        )
        return None


class ProposeReportCaseToActorNode(_EmitSingleActivityBase):
    """Send the receiver's ``CaseProposal`` as ``Create(CaseProposal)``.

    Used by the slimmed ``receive_report_case_tree`` (ADR-0041): it needs no
    ``VulnerabilityCase``.  It sends the proposal on ``case_proposal``, as
    :class:`ConvertReportToCaseProposalNode` built it or as a node between
    them changed it, to the CaseActor the proposal names as its ``target``
    (CP-04-001, CP-04-002).  The adapter renders it, carrying the Offer
    whole when its store holds it (CP-01-008).

    Returns ``FAILURE`` when:

    - DataLayer, ``actor_id``, or ``trigger_activity_factory`` is unavailable.
    - ``trigger_activity_factory.create_case_proposal()`` raises an exception.

    Per specs/case-proposal.yaml CP-04-001, CP-04-002 and ADR-0041.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **_EmitSingleActivityBase.INPUT_PORTS,
        CASE_PROPOSAL_KEY: PortInformation(
            data_type=CaseProposal, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {CASE_PROPOSAL_KEY: f"/{CASE_PROPOSAL_KEY}"}

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f

        assert self.trigger_activity_factory is not None
        proposal: CaseProposal = self.get_input(CASE_PROPOSAL_KEY)
        try:
            activity_id, _ = (
                self.trigger_activity_factory.create_case_proposal(
                    proposal, at=self._require_act_instant()
                )
            )
            # Route through the shared emit seam (OX-14-001, ASK-04-008).
            self._emit_through_seam(activity_id, "")
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = f"create_case_proposal failed: {exc}"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.info(
            "%s: queued Create(CaseProposal) '%s' to outbox"
            " for case-actor '%s' (report '%s')",
            self.name,
            activity_id,
            proposal.target,
            getattr(proposal.object_, "id_", proposal.object_),
        )
        return Status.SUCCESS
