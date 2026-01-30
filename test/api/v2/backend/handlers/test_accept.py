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
from vultron.api.v2.data.enums import OfferStatusEnum
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Accept,
)
from vultron.bt.report_management.states import RM


# Activity-specific fixture (use finder, vendor, offer, report, dl from conftest.py)
@pytest.fixture
def accept(finder, vendor, offer):
    return as_Accept(to=finder.as_id, actor=vendor.as_id, object=offer)


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


def test_rm_validate_report_calls_set_status(
    monkeypatch, dl, accept: as_Accept
):
    mock_set_status = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.accept.set_status", mock_set_status
    )

    dl.create(object_to_record(accept))
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

    dl.create(object_to_record(accept))
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
