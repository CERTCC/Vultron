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

"""The report receiver's case proposal, converted from what it received.

A report receiver asks a CASE_MANAGER to create a case by sending it a
``CaseProposal`` (CP-01).  :func:`case_proposal_from_report` is the one
conversion that builds it: from the stored report, the Offer that brought it
and the readings of the CSAF documents on the report.  When the first
``csaf_vulnerability_report`` reading fills case inputs, the proposal states
them as ``caseInputs`` (CP-01-022, CP-01-026), by
:func:`~vultron.core.services.report_case_inputs.proposed_case_inputs_from_claims`:
the earliest disclosure date as the document states it, and no P
(CP-01-023, CP-01-027).  The CASE_MANAGER judges the date when it builds the
case, which may be well after this receipt.

The result is a core object (ARCH-01-001): the receiver may change it before
its adapter renders and sends it, and nothing here reads a clock or the
store (ADR-0176).  :func:`used_claims` names the claimed values the
conversion used, for the receiver's own record (CSAF-04-004).
"""

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from vultron.core.models._helpers import authored_times
from vultron.core.models.case_proposal import CaseProposal
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_claims import ClaimOutcome, ClaimsReading
from vultron.core.services.report_case_inputs import (
    StatedReportFields,
    filling_reading,
    proposed_case_inputs_from_claims,
    proposed_claim_outcomes,
)
from vultron.enums.roles import CVDRole


class ConvertedCaseProposal(BaseModel):
    """A receiver's proposal and what its conversion used.

    Fields:
        proposal: The ``CaseProposal`` to send, ``caseInputs`` filled when a
            reading fills them.
        reading: The reading that filled ``caseInputs``; ``None`` when none
            did.
    """

    model_config = ConfigDict(frozen=True)

    proposal: CaseProposal
    reading: ClaimsReading | None = None


def case_proposal_from_report(
    report: VulnerabilityReport,
    *,
    proposer_id: str,
    case_actor_id: str,
    readings: Sequence[ClaimsReading] = (),
    offer_id: str | None = None,
    proposer_case_roles: Sequence[CVDRole] = (),
    at: datetime,
) -> ConvertedCaseProposal:
    """Convert a received *report* into the proposal its receiver sends.

    Args:
        report: The report the case is to be created around, carried inline
            (CP-01-004).
        proposer_id: The report receiver, the proposal's ``attributedTo``
            (CP-01-003).
        case_actor_id: The CASE_MANAGER the proposal is addressed to
            (CP-01-005, CP-04-003).
        readings: The readings of the CSAF documents attached to *report*;
            only the first ``csaf_vulnerability_report`` one fills
            ``caseInputs`` (CSAF-02-001).
        offer_id: The ``Offer(VulnerabilityReport)`` that brought *report*,
            named in ``inReplyTo`` (CP-01-007); the adapter carries it whole
            when its store holds it (CP-01-008).
        proposer_case_roles: The receiver's own ``default_case_roles``
            (CP-01-013).
        at: The act's instant, the proposal's author time (ADR-0176).

    The report's own name and summary beat the document's (CSAF-02-003);
    with no reading that fills case inputs the proposal states none, and the
    CASE_MANAGER starts the case from the report (CP-01-026).
    """
    reading = filling_reading(readings)
    proposal = CaseProposal(
        attributed_to=proposer_id,
        object_=report,
        target=case_actor_id,
        in_reply_to=offer_id,
        proposer_case_roles=list(proposer_case_roles),
        case_inputs=(
            proposed_case_inputs_from_claims(
                reading.claims, stated=_stated(report)
            )
            if reading is not None
            else None
        ),
        **authored_times(at),
    )
    return ConvertedCaseProposal(proposal=proposal, reading=reading)


def _stated(report: VulnerabilityReport) -> StatedReportFields:
    """What *report* states for the values a document can fill."""
    return StatedReportFields(name=report.name, summary=report.summary)


def used_claims(
    report: VulnerabilityReport, readings: Sequence[ClaimsReading]
) -> tuple[ClaimsReading | None, dict[str, ClaimOutcome]]:
    """The reading the conversion fills ``caseInputs`` from, and its outcomes.

    The outcomes of the values :func:`case_proposal_from_report` takes
    from that reading (CSAF-04-004); ``(None, {})`` when no reading fills
    case inputs.  Pure, so the receiver can mark its record after the
    proposal is sent without carrying them across the send.
    """
    reading = filling_reading(readings)
    if reading is None:
        return None, {}
    return reading, proposed_claim_outcomes(
        reading.claims, stated=_stated(report)
    )


__all__ = [
    "ConvertedCaseProposal",
    "case_proposal_from_report",
    "used_claims",
]
