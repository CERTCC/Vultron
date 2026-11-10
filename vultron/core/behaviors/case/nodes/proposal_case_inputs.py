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

"""The inputs of a case created from a proposal, filled from its CSAF report.

A ``Create(CaseProposal)`` carries the initial ``Offer(VulnerabilityReport)``
inline (CP-01-008).  The proposer and the CASE_MANAGER are two roles of the
one coordinating function that received the report, so the CSAF document on
that Offer's report is the initial report reaching it, not a document on
another activity (ADR-0184, CSAF-02-001, CSAF-02-002).  When the proposal
creates a new case, the CASE_MANAGER fills the case's name, summary, P/X/A
and proposed embargo end from it, by the one mapping
:func:`~vultron.core.services.report_case_inputs.case_inputs_from_claims`,
measured against its own receipt of the proposal: the receiver's receipt
time travels on no message.

:class:`ResolveReportCaseInputsNode` runs that mapping ahead of
``CreateCaseFromProposalNode``, which builds the case from its result;
:class:`StoreCaseInputClaimsRecordsNode` records, after the case exists, what
became of each claimed value (CSAF-04-004).  Only this creating side marks a
value ``applied`` or ``overridden``; the receiver's own record keeps every
value display only, so no stored record says a value shaped a case it did not
shape.  Both run only on the new-case arm, so a proposal that resolves to an
existing case changes nothing from the document (CSAF-02-002, EP-04-029).
"""

from collections.abc import Sequence
from datetime import datetime

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.activity_ids import derived_object_id
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.report_claims import (
    ClaimsReading,
    ReportClaimsRecord,
)
from vultron.core.services.report_case_inputs import (
    ReportCaseInputs,
    StatedReportFields,
    case_inputs_from_claims,
    fills_case_inputs,
)
from vultron.errors import VultronAlreadyExistsError

#: Blackboard key for the resolved :class:`ReportCaseInputs`.
REPORT_CASE_INPUTS_KEY = "report_case_inputs"


def filling_reading(
    readings: Sequence[ClaimsReading],
) -> ClaimsReading | None:
    """The one reading that fills case inputs: the first of the right category.

    A report may carry several CSAF documents.  Only the first of category
    ``csaf_vulnerability_report`` speaks for the case; every other value stays
    display only, so two documents never compete for one input.
    """
    return next((r for r in readings if fills_case_inputs(r.claims)), None)


def csaf_proposed_embargo_id(proposal_id: str) -> str:
    """The id of the embargo a proposal's CSAF disclosure date proposes.

    Derived from the proposal, so a redelivery names the same event
    (EP-04-012).
    """
    return derived_object_id(f"{proposal_id}#csaf-proposed-embargo")


class ResolveReportCaseInputsNode(DataLayerActionWithPorts):
    """Fill a new case's inputs from the proposal's carried CSAF report.

    Writes the :class:`ReportCaseInputs` to ``report_case_inputs`` for
    ``CreateCaseFromProposalNode``.  When the carried Offer has no
    ``proposedEmbargo`` and the document gives a proposed end, that end
    becomes the sender's proposal the embargo resolution reads
    (``sender_proposed_embargo_duration`` and ``sender_proposed_embargo``),
    so it competes with the owner's actor default like any sender proposal
    (CSAF-03-001, EP-04-003).

    With no document to read, it writes the report's own name and summary
    and reads no clock.  It writes nothing to the store.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        REPORT_CASE_INPUTS_KEY: PortInformation(
            data_type=ReportCaseInputs, required=True
        ),
        "sender_proposed_embargo_duration": PortInformation(
            data_type=object, required=False
        ),
        "sender_proposed_embargo": PortInformation(
            data_type=object, required=False
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            key: f"/{key}"
            for key in (
                REPORT_CASE_INPUTS_KEY,
                "sender_proposed_embargo_duration",
                "sender_proposed_embargo",
            )
        }

    def __init__(
        self,
        *,
        report_id: str | None,
        proposal_id: str,
        readings: Sequence[ClaimsReading],
        stated: StatedReportFields,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._proposal_id = proposal_id
        self._reading = filling_reading(readings)
        self._stated = stated

    def update(self) -> Status:
        if self._reading is None:
            self._set_output(
                REPORT_CASE_INPUTS_KEY,
                ReportCaseInputs(
                    name=self._stated.name,
                    summary=self._stated.summary,
                    proposed_embargo_end=self._stated.proposed_embargo_end,
                ),
            )
            return Status.SUCCESS
        received_at = self._require_act_instant()
        inputs = case_inputs_from_claims(
            self._reading.claims,
            reference_time=received_at,
            stated=self._stated,
        )
        self._set_output(REPORT_CASE_INPUTS_KEY, inputs)
        self._propose_csaf_embargo(inputs, received_at)
        self.logger.info(
            "%s: proposal '%s' fills its new case from %s document '%s':"
            " name %s, summary %s, P/X/A %s/%s/%s, proposed embargo end %s"
            " (CSAF-02-001, CSAF-03)",
            self.name,
            self._proposal_id,
            self._reading.document_format,
            self._reading.document_id,
            "set" if inputs.name else "unset",
            "set" if inputs.summary else "unset",
            inputs.public,
            inputs.exploit_public,
            inputs.attacks_observed,
            (
                inputs.proposed_embargo_end.isoformat()
                if inputs.proposed_embargo_end
                else None
            ),
        )
        return Status.SUCCESS

    def _propose_csaf_embargo(
        self, inputs: ReportCaseInputs, received_at: datetime
    ) -> None:
        """Seed the document's embargo end as the sender's proposal.

        Only when the Offer proposed none (CSAF-03-001) and the case may
        start under an embargo (EP-04-020).  Its subject is the report until
        the case exists (EP-04-009).
        """
        end = inputs.proposed_embargo_end
        if (
            self._stated.proposed_embargo_end is not None
            or end is None
            or not inputs.embargo_eligible
            or self._report_id is None
        ):
            return
        self._set_output("sender_proposed_embargo_duration", end - received_at)
        self._set_output(
            "sender_proposed_embargo",
            EmbargoEvent(
                id_=csaf_proposed_embargo_id(self._proposal_id),
                start_time=received_at,
                end_time=end,
                context=self._report_id,
            ),
        )


class StoreCaseInputClaimsRecordsNode(DataLayerActionWithPorts):
    """Record what became of each value the carried CSAF document claimed.

    One :class:`ReportClaimsRecord` per reading, in the CASE_MANAGER's own
    store.  The reading that filled the case carries the ``applied`` and
    ``overridden`` outcomes of ``report_case_inputs``; every other value
    stays display only (CSAF-04-004).  The record is never sent
    (CSAF-04-005).  Idempotent: a record already held is kept.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        REPORT_CASE_INPUTS_KEY: PortInformation(
            data_type=ReportCaseInputs, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {REPORT_CASE_INPUTS_KEY: f"/{REPORT_CASE_INPUTS_KEY}"}

    def __init__(
        self,
        *,
        report_id: str | None,
        activity_id: str,
        readings: Sequence[ClaimsReading],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._activity_id = activity_id
        self._readings = list(readings)
        self._filling = filling_reading(readings)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if not self._readings or self._report_id is None:
            return Status.SUCCESS
        inputs = self._try_get_input(REPORT_CASE_INPUTS_KEY)
        received_at = self._require_act_instant()
        for reading in self._readings:
            record = ReportClaimsRecord(
                report_id=self._report_id,
                activity_id=self._activity_id,
                received_at=received_at,
                reading=reading,
            )
            if reading is self._filling and isinstance(
                inputs, ReportCaseInputs
            ):
                record = record.with_outcomes(inputs.outcomes)
            try:
                self.datalayer.create(record)
            except VultronAlreadyExistsError:
                self.logger.debug(
                    "%s: claims record for document '%s' of report '%s'"
                    " already held",
                    self.name,
                    reading.document_id,
                    self._report_id,
                )
                continue
            self.logger.info(
                "%s: recorded what became of the claims of document '%s' on"
                " report '%s' from activity '%s' (CSAF-04-004)",
                self.name,
                reading.document_id,
                self._report_id,
                self._activity_id,
            )
        return Status.SUCCESS


__all__ = [
    "REPORT_CASE_INPUTS_KEY",
    "ResolveReportCaseInputsNode",
    "StoreCaseInputClaimsRecordsNode",
    "csaf_proposed_embargo_id",
    "filling_reading",
]
