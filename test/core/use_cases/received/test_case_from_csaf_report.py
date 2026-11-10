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
"""A case created from an initial CSAF report starts from what the report says.

Receive-path tests for CSAF-02-001 to CSAF-02-003 and CSAF-03-001 to
CSAF-03-007.  The Vendor receives the Finder's ``Offer(VulnerabilityReport)``
and sends ``Create(CaseProposal)``; a separate CASE_MANAGER, in its own store,
receives that sealed proposal and creates the case from the CSAF document on
the Offer the proposal carries.
"""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from test.core.use_cases.received._csaf_receipt import (
    REPORT_ID,
    CaseManager,
    Receipt,
    csaf,
    document,
)
from test.wire.csaf._documents import section, vulnerability_report_document
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.report_claims import ClaimOutcome
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs.states import CS_pxa
from vultron.core.states.em import EM

pytestmark = pytest.mark.usefixtures("case_actor_service_url")

_TITLE = "Buffer overflow in Example Widget"
_SUMMARY_NOTE = "A short summary."
_SOONER = "2027-01-15T00:00:00Z"
_LATER = "2027-03-01T00:00:00Z"
_PAST = "2026-10-01T00:00:00Z"


def _quiet_document(**vul: Any) -> dict[str, Any]:
    """A report document whose one vulnerability states only *vul*."""
    data = vulnerability_report_document()
    entry = data["vulnerabilities"][0]
    for key in (
        "disclosure_date",
        "metrics",
        "first_known_exploitation_dates",
    ):
        entry.pop(key)
    entry.update(vul)
    return data


def _ssvc(key: str) -> list[dict[str, Any]]:
    return [
        {
            "content": {
                "ssvc_v2": {
                    "schemaVersion": "2.0.0",
                    "timestamp": "2026-10-01T00:00:00Z",
                    "selections": [
                        {
                            "namespace": "ssvc",
                            "key": "E",
                            "version": "1.1.0",
                            "values": [{"key": key}],
                        }
                    ],
                }
            },
            "products": ["WIDGET-1"],
        }
    ]


def _created(receipt: Receipt) -> tuple[CaseManager, VulnerabilityCase]:
    """Deliver *receipt*'s proposal to a separate CASE_MANAGER."""
    receipt.handle()
    manager = CaseManager()
    result = manager.receive(receipt.proposal_body())
    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    return manager, manager.case()


def _embargo_end(manager: CaseManager, case: VulnerabilityCase) -> datetime:
    assert case.em_state is EM.ACTIVE
    embargo = manager.dl.read(str(case.active_embargo_id))
    assert isinstance(embargo, EmbargoEvent)
    return embargo.end_time


def _when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp).astimezone(UTC)


@pytest.mark.spec("CSAF-02-001", "CSAF-03-007")
def test_a_missing_name_and_summary_come_from_the_csaf_document() -> None:
    receipt = Receipt(csaf(_quiet_document()), report_name=None)

    manager, case = _created(receipt)

    assert (case.name, case.summary) == (_TITLE, _SUMMARY_NOTE)
    [record] = manager.records()
    assert record.outcomes["name"] is ClaimOutcome.APPLIED
    assert record.outcomes["summary"] is ClaimOutcome.APPLIED


@pytest.mark.spec("CSAF-03-007")
def test_the_description_note_is_the_summary_when_there_is_no_summary_note() -> (
    None
):
    data = _quiet_document()
    section(data, "document")["notes"] = [
        {"category": "description", "text": "A longer description."}
    ]
    receipt = Receipt(csaf(data), report_name=None)

    _, case = _created(receipt)

    assert case.summary == "A longer description."


@pytest.mark.spec("CSAF-03-006")
def test_a_case_starts_with_its_reports_name_and_summary() -> None:
    receipt = Receipt(
        report_name="Widget overflow", report_summary="It overflows."
    )

    _, case = _created(receipt)

    assert (case.name, case.summary) == ("Widget overflow", "It overflows.")


@pytest.mark.spec("CSAF-02-003")
def test_a_vultron_field_beats_the_csaf_value() -> None:
    proposed_end = _when(_LATER)
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=_SOONER)),
        report_name="Widget overflow",
        proposed_embargo_end=proposed_end,
    )

    manager, case = _created(receipt)

    assert case.name == "Widget overflow"
    assert case.summary == _SUMMARY_NOTE
    assert _embargo_end(manager, case) == proposed_end
    [record] = manager.records()
    assert record.outcomes["name"] is ClaimOutcome.OVERRIDDEN
    assert (
        record.outcomes["vulnerabilities[0].disclosure_date"]
        is ClaimOutcome.OVERRIDDEN
    )


@pytest.mark.spec("CSAF-03-001")
def test_a_future_disclosure_date_proposes_the_embargo_end() -> None:
    receipt = Receipt(csaf(_quiet_document(disclosure_date=_SOONER)))

    manager, case = _created(receipt)

    assert _embargo_end(manager, case) == _when(_SOONER)
    [record] = manager.records()
    assert (
        record.outcomes["vulnerabilities[0].disclosure_date"]
        is ClaimOutcome.APPLIED
    )


@pytest.mark.spec("CSAF-03-002")
def test_the_earliest_future_disclosure_date_wins() -> None:
    data = _quiet_document(disclosure_date=_LATER)
    second = dict(data["vulnerabilities"][0])
    second["cve"] = "CVE-2026-0002"
    second["disclosure_date"] = _SOONER
    data["vulnerabilities"].append(second)
    receipt = Receipt(csaf(data))

    manager, case = _created(receipt)

    assert _embargo_end(manager, case) == _when(_SOONER)


@pytest.mark.spec("CSAF-03-003")
def test_a_past_disclosure_date_states_the_vul_is_public() -> None:
    receipt = Receipt(csaf(_quiet_document(disclosure_date=_PAST)))

    _, case = _created(receipt)

    assert case.current_status.pxa.state is CS_pxa.Pxa
    assert case.em_state is EM.NONE
    assert case.active_embargo_id is None


@pytest.mark.spec("CSAF-03-004")
@pytest.mark.parametrize(
    ("key", "pxa"),
    [("P", CS_pxa.PXa), ("A", CS_pxa.pxA), ("N", CS_pxa.pxa)],
    ids=["poc", "active", "none"],
)
def test_ssvc_exploitation_poc_sets_x_and_active_sets_a(
    key: str, pxa: CS_pxa
) -> None:
    receipt = Receipt(csaf(_quiet_document(metrics=_ssvc(key))))

    _, case = _created(receipt)

    # An exploit made public makes the public aware (pX to PX).
    assert case.current_status.pxa.state is pxa
    assert (case.em_state is EM.NONE) is (key != "N")


@pytest.mark.spec("CSAF-03-005")
def test_a_first_known_exploitation_date_sets_a() -> None:
    entry = {
        "date": "2026-10-02T00:00:00Z",
        "exploitation_date": "2026-09-30T00:00:00Z",
    }
    receipt = Receipt(
        csaf(_quiet_document(first_known_exploitation_dates=[entry]))
    )

    _, case = _created(receipt)

    assert case.current_status.pxa.state is CS_pxa.pxA
    assert case.em_state is EM.NONE


@pytest.mark.spec("CSAF-02-001")
def test_only_the_creating_side_marks_what_shaped_the_case() -> None:
    """The receiver's record stays display only; the CASE_MANAGER's says what
    the case took, so no record claims a value the case did not take."""
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=_SOONER)), report_name=None
    )

    manager, _ = _created(receipt)

    assert set(receipt.record().outcomes.values()) == {
        ClaimOutcome.DISPLAY_ONLY
    }
    [record] = manager.records()
    assert record.reading == receipt.record().reading
    assert record.received_at == receipt.record().received_at


@pytest.mark.spec("CSAF-02-002")
def test_a_document_of_another_category_changes_no_case_data() -> None:
    data = _quiet_document(disclosure_date=_PAST, metrics=_ssvc("A"))
    section(data, "document")["category"] = "csaf_security_advisory"
    receipt = Receipt(csaf(data), report_name=None)

    manager, case = _created(receipt)

    assert case.name is None
    assert case.current_status.pxa.state is CS_pxa.pxa
    assert case.em_state is EM.ACTIVE
    [record] = manager.records()
    assert set(record.outcomes.values()) == {ClaimOutcome.DISPLAY_ONLY}


@pytest.mark.spec("CSAF-02-002")
def test_csaf_on_a_report_that_already_has_a_case_changes_no_case_data() -> (
    None
):
    first = Receipt(report_name="Widget overflow")
    manager, case = _created(first)
    later = Receipt(
        csaf(_quiet_document(disclosure_date=_PAST, metrics=_ssvc("A"))),
        report_name=None,
    )
    later.handle()

    result = manager.receive(later.proposal_body())

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    unchanged = manager.case()
    assert unchanged.id_ == case.id_
    assert unchanged.name == "Widget overflow"
    assert unchanged.current_status.pxa.state is CS_pxa.pxa
    assert unchanged.em_state is case.em_state
    assert manager.records() == []


def test_the_first_vulnerability_report_document_fills_the_case() -> None:
    other = _quiet_document(disclosure_date=_PAST)
    section(other, "document")["title"] = "A second account"
    receipt = Receipt(
        csaf(_quiet_document()),
        document(json.dumps(other), f"{REPORT_ID}/csaf-2"),
        report_name=None,
    )

    manager, case = _created(receipt)

    assert case.name == _TITLE
    assert case.current_status.pxa.state is CS_pxa.pxa
    second = next(
        r for r in manager.records() if r.reading.claims.name != _TITLE
    )
    assert set(second.outcomes.values()) == {ClaimOutcome.DISPLAY_ONLY}
