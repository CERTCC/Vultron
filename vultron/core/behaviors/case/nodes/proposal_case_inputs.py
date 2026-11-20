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

"""The inputs of a case created from a proposal.

A ``Create(CaseProposal)`` carries the initial ``Offer(VulnerabilityReport)``
inline (CP-01-008).  The proposer and the CASE_MANAGER are two roles of the
one coordinating function that received the report, so the CSAF document on
that Offer's report is the initial report reaching it, not a document on
another activity (ADR-0184, CSAF-02-001, CSAF-02-002).

A new case's inputs have two sources, and a proposal picks one whole:

- the proposal's ``caseInputs``, when it carries them: the proposer has
  spoken for every input, so the CASE_MANAGER reads no CSAF document and
  refills nothing from one (CP-01-024);
- else the CSAF document on the carried Offer's report, by the one mapping
  :func:`~vultron.core.services.report_case_inputs.case_inputs_from_claims`
  (CP-01-025).

Both pass through one date step,
:func:`~vultron.core.services.report_case_inputs.case_inputs_from_proposal`,
measured against the act's instant: the CASE_MANAGER judges every date when
it builds the case, and the receiver's receipt time travels on no message
(CP-01-023, CSAF-03-001).

:class:`ResolveReportCaseInputsNode` resolves the inputs ahead of
``CreateCaseFromProposalNode``, which builds the case from its result;
:class:`StoreCaseInputClaimsRecordsNode` records, after the case exists, what
became of each claimed value of a document it read (CSAF-04-004).  Only the
side that read the document marks a value ``applied`` or ``overridden``: the
receiver, for the ``caseInputs`` it converted
(:class:`~vultron.core.behaviors.case.nodes.proposal.ConvertReportToCaseProposalNode`),
or this CASE_MANAGER, for a document it read itself.  Both run only on the
new-case arm, so a proposal that resolves to an existing case changes nothing
from its inputs (CSAF-02-002, EP-04-029).
"""

from collections.abc import Sequence
from datetime import datetime

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import embargo_authored_times
from vultron.core.models.activity_ids import derived_object_id
from vultron.core.models.case_proposal import ProposedCaseInputs
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.report_claims import (
    ClaimsReading,
    ReportClaimsRecord,
)
from vultron.core.services.report_case_inputs import (
    ReportCaseInputs,
    StatedReportFields,
    case_inputs_from_claims,
    case_inputs_from_proposal,
    filling_reading,
)

#: Blackboard key for the resolved :class:`ReportCaseInputs`.
REPORT_CASE_INPUTS_KEY = "report_case_inputs"


def csaf_proposed_embargo_id(proposal_id: str) -> str:
    """The id of the embargo a proposal's CSAF disclosure date proposes.

    Derived from the proposal, so a redelivery names the same event
    (EP-04-012).
    """
    return derived_object_id(f"{proposal_id}#csaf-proposed-embargo")


class ResolveReportCaseInputsNode(DataLayerActionWithPorts):
    """Resolve a new case's inputs: the proposal's, else its CSAF report's.

    Writes the :class:`ReportCaseInputs` to ``report_case_inputs`` for
    ``CreateCaseFromProposalNode``.  *proposed*, the proposal's
    ``caseInputs``, is taken whole when given, and no document is read
    (CP-01-024); otherwise the first ``csaf_vulnerability_report`` reading
    fills them (CP-01-025).  Either way the disclosure date is judged at the
    act's instant (CP-01-023).  When the carried Offer has no
    ``proposedEmbargo`` and the inputs give a proposed end, that end becomes
    the sender's proposal the embargo resolution reads
    (``sender_proposed_embargo_duration`` and ``sender_proposed_embargo``),
    so it competes with the owner's actor default like any sender proposal
    (CSAF-03-001, EP-04-003).

    With neither, it writes the report's own name and summary and reads no
    clock.  It writes nothing to the store.
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
        proposed: ProposedCaseInputs | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._proposal_id = proposal_id
        self._reading = filling_reading(readings)
        self._stated = stated
        self._proposed = proposed

    def update(self) -> Status:
        # The caller passes no readings with *proposed* (CP-01-024); given
        # both, the stated inputs win and the reading is ignored.
        if self._proposed is None and self._reading is None:
            self._set_output(
                REPORT_CASE_INPUTS_KEY,
                ReportCaseInputs.from_stated(self._stated),
            )
            return Status.SUCCESS
        received_at = self._require_act_instant()
        if self._proposed is not None:
            inputs = case_inputs_from_proposal(
                self._proposed,
                reference_time=received_at,
                proposed_embargo_end=self._stated.proposed_embargo_end,
            )
            source = "the proposal's caseInputs (CP-01-024)"
        else:
            assert self._reading is not None
            inputs = case_inputs_from_claims(
                self._reading.claims,
                reference_time=received_at,
                stated=self._stated,
            )
            source = (
                f"{self._reading.document_format} document"
                f" '{self._reading.document_id}' (CSAF-02-001, CP-01-025)"
            )
        self._set_output(REPORT_CASE_INPUTS_KEY, inputs)
        self._propose_csaf_embargo(inputs, received_at)
        self.logger.info(
            "%s: proposal '%s' fills its new case from %s:"
            " name %s, summary %s, P/X/A %s/%s/%s, %d item(s),"
            " %d reference(s), proposed embargo end %s",
            self.name,
            self._proposal_id,
            source,
            "set" if inputs.name else "unset",
            "set" if inputs.summary else "unset",
            inputs.public,
            inputs.exploit_public,
            inputs.attacks_observed,
            len(inputs.proposed_items),
            len(inputs.reference_links),
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
        """Seed the disclosure date's embargo end as the sender's proposal.

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
                end_time=end,
                context=self._report_id,
                **embargo_authored_times(received_at),
            ),
        )


class StoreCaseInputClaimsRecordsNode(DataLayerActionWithPorts):
    """Record what became of each value the carried CSAF document claimed.

    One :class:`ReportClaimsRecord` per reading, in the CASE_MANAGER's own
    store, keyed on the case it filled (``case_id``), so a second proposer's
    case for the same report keeps its own record (CBT-06-002).  The reading
    that filled the case carries the ``applied`` and ``overridden`` outcomes
    of ``report_case_inputs``; every other value stays display only
    (CSAF-04-004).  The record is never sent (CSAF-04-005).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        REPORT_CASE_INPUTS_KEY: PortInformation(
            data_type=ReportCaseInputs, required=True
        ),
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            REPORT_CASE_INPUTS_KEY: f"/{REPORT_CASE_INPUTS_KEY}",
            "case_id": "/case_id",
        }

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
        inputs: ReportCaseInputs = self.get_input(REPORT_CASE_INPUTS_KEY)
        case_id: str = self.get_input("case_id")
        received_at = self._require_act_instant()
        for reading in self._readings:
            record = ReportClaimsRecord(
                report_id=self._report_id,
                activity_id=self._activity_id,
                received_at=received_at,
                case_id=case_id,
                reading=reading,
            )
            if reading is self._filling:
                record = record.with_outcomes(inputs.outcomes)
            # Keyed on the case it filled, and written in the creation act, so
            # a failed creation leaves none and two cases from one report keep
            # a record each; a held one is this case's own.
            self.datalayer.save(record)
            self.logger.info(
                "%s: recorded what became of the claims of document '%s' on"
                " report '%s' for case '%s' from activity '%s' (CSAF-04-004)",
                self.name,
                reading.document_id,
                self._report_id,
                case_id,
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
