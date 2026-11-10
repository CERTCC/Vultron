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
"""A report's CSAF document raises receiver-local signals that never act.

Receive-path tests for CSAF-04-006 to CSAF-04-008.
"""

import copy
from typing import Any

import pytest

from test.core.use_cases.received._csaf_receipt import Receipt, csaf
from test.wire.csaf._documents import section, vulnerability_report_document
from vultron.core.models.report_claims import CaseSplitDifference

pytestmark = pytest.mark.usefixtures("case_actor_service_url")

_RECEIVER_NAME = "Example Vendor"


def _two_vulnerabilities(**second: Any) -> dict[str, Any]:
    data = vulnerability_report_document()
    first = data["vulnerabilities"][0]
    other = copy.deepcopy(first)
    other["cve"] = "CVE-2026-0002"
    other.update(second)
    data["vulnerabilities"].append(other)
    return data


def _with_second_vendor() -> dict[str, Any]:
    data = vulnerability_report_document()
    branches = section(data, "product_tree")["branches"]
    assert isinstance(branches, list)
    branches.append(
        {
            "category": "vendor",
            "name": "Other Vendor",
            "branches": [
                {
                    "category": "product_name",
                    "name": "Gadget",
                    "product": {
                        "name": "Other Vendor Gadget",
                        "product_id": "GADGET-1",
                    },
                }
            ],
        }
    )
    status = data["vulnerabilities"][0]["product_status"]
    status["known_affected"].append("GADGET-1")
    return data


def _sent_types(receipt: Receipt) -> list[tuple[str, str | None]]:
    """The type of each sent activity and of its object."""
    sent = []
    for body in receipt.sent_bodies():
        obj = body.get("object")
        sent.append(
            (body["type"], obj.get("type") if isinstance(obj, dict) else None)
        )
    return sent


def _assert_only_the_case_proposal_is_sent(receipt: Receipt) -> None:
    """Nothing splits, suggests or invites because of a signal (CSAF-04-008)."""
    assert _sent_types(receipt) == [("Create", "CaseProposal")]


@pytest.mark.spec("CSAF-04-006", "CSAF-04-008")
def test_vulnerabilities_that_differ_in_exploitation_raise_a_split_signal() -> (
    None
):
    data = _two_vulnerabilities(metrics=[], first_known_exploitation_dates=[])
    receipt = Receipt(csaf(data), receiver_name=_RECEIVER_NAME)

    receipt.handle()

    signal = receipt.record().case_split_signal
    assert signal is not None
    assert signal.differs_in == [
        CaseSplitDifference.EXPLOIT_PUBLIC,
        CaseSplitDifference.ATTACKS_OBSERVED,
    ]
    _assert_only_the_case_proposal_is_sent(receipt)


@pytest.mark.spec("CSAF-04-006")
def test_vulnerabilities_that_differ_in_public_status_raise_a_split_signal() -> (
    None
):
    data = _two_vulnerabilities(disclosure_date="2026-10-01T00:00:00Z")
    receipt = Receipt(csaf(data), receiver_name=_RECEIVER_NAME)

    receipt.handle()

    signal = receipt.record().case_split_signal
    assert signal is not None
    assert signal.differs_in == [
        CaseSplitDifference.PUBLIC_STATUS,
        CaseSplitDifference.FUTURE_DISCLOSURE_DATE,
    ]


@pytest.mark.spec("CSAF-04-006")
def test_agreeing_vulnerabilities_raise_no_split_signal() -> None:
    receipt = Receipt(
        csaf(_two_vulnerabilities()), receiver_name=_RECEIVER_NAME
    )

    receipt.handle()

    assert receipt.record().case_split_signal is None


@pytest.mark.spec("CSAF-04-007", "CSAF-04-008")
def test_two_affected_vendors_raise_a_candidate_parties_signal() -> None:
    receipt = Receipt(
        csaf(_with_second_vendor()), receiver_name=_RECEIVER_NAME
    )

    receipt.handle()

    signal = receipt.record().candidate_parties_signal
    assert signal is not None
    assert signal.vendors == ["Other Vendor"]
    _assert_only_the_case_proposal_is_sent(receipt)


@pytest.mark.spec("CSAF-04-007")
def test_one_affected_vendor_other_than_the_receiver_is_a_candidate() -> None:
    receipt = Receipt(
        csaf(vulnerability_report_document()), receiver_name="A Coordinator"
    )

    receipt.handle()

    signal = receipt.record().candidate_parties_signal
    assert signal is not None
    assert signal.vendors == ["Example Vendor"]


@pytest.mark.spec("CSAF-04-007")
def test_the_receiver_as_the_only_affected_vendor_raises_no_signal() -> None:
    receipt = Receipt(
        csaf(vulnerability_report_document()), receiver_name=_RECEIVER_NAME
    )

    receipt.handle()

    assert receipt.record().candidate_parties_signal is None


def test_a_document_of_another_category_raises_no_signal() -> None:
    data = _with_second_vendor()
    section(data, "document")["category"] = "csaf_base"
    receipt = Receipt(csaf(data), receiver_name=_RECEIVER_NAME)

    receipt.handle()

    record = receipt.record()
    assert record.candidate_parties_signal is None
    assert record.case_split_signal is None
