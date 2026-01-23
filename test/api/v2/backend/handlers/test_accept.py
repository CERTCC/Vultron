#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from unittest.mock import Mock

import pytest

from vultron.api.v2.backend.handlers.accept import (
    accept_offer_handler,
    rm_validate_report,
)
from vultron.api.v2.data import get_datalayer
from vultron.api.v2.data.enums import OfferStatusEnum
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Offer,
    as_Accept,
)
from vultron.as_vocab.base.objects.actors import as_Person, as_Organization
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.bt.report_management.states import RM


# Fixtures
@pytest.fixture
def finder():
    return as_Person(name="Test Finder")


@pytest.fixture
def vendor():
    return as_Organization(name="Test Vendor")


@pytest.fixture
def report(finder):
    return VulnerabilityReport(
        content="Test vulnerability report content",
        attributed_to=finder,
    )


@pytest.fixture
def offer(finder, vendor, report):
    return as_Offer(to=vendor, actor=finder, object=report)


@pytest.fixture
def accept(finder, vendor, offer):
    return as_Accept(to=finder.as_id, actor=vendor.as_id, object=offer)


@pytest.fixture
def dl(finder, vendor, report, offer):
    dl = get_datalayer()
    dl.create(finder)
    dl.create(vendor)
    dl.create(report)
    dl.create(offer)
    yield dl
    dl.clear()


# Tests
def test_accept_offer_handler_calls_rm_validate_report(
    monkeypatch, dl, vendor, accept
):
    mock_rm_validate = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.accept.rm_validate_report",
        mock_rm_validate,
    )

    activity = accept
    accept_offer_handler(actor_id=vendor.as_id, activity=activity)

    mock_rm_validate.assert_called_once_with(activity)


@pytest.mark.skip(reason="TODO: implement routing behavior tests")
def test_accept_offer_handler_other_routing_cases_placeholder():
    pass


def test_rm_validate_report_calls_set_status(monkeypatch, dl, accept):
    mock_set_status = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.accept.set_status", mock_set_status
    )

    dl.create(accept)
    activity = accept

    rm_validate_report(activity)

    mock_set_status.assert_called()


def test_rm_validate_report_updates_offer_and_report_statuses(
    monkeypatch, dl, accept
):
    mock_set_status = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.accept.set_status", mock_set_status
    )

    dl.create(accept)
    activity = accept

    rm_validate_report(activity)

    matches = []
    for args in mock_set_status.call_args_list:
        obj = args[0][0]
        match obj.object_type:
            case "Offer":
                assert obj.status == OfferStatusEnum.ACCEPTED
                matches.append("Offer")
            case "VulnerabilityReport":
                assert obj.status == RM.VALID
                matches.append("VulnerabilityReport")

    assert "Offer" in matches
    assert "VulnerabilityReport" in matches
