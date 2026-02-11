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

from vultron.api.v2.backend.handlers.reject import (
    reject_offer,
    rm_close_report,
    tentative_reject_offer,
    rm_invalidate_report,
)
from vultron.enums import OfferStatusEnum
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Reject,
    as_TentativeReject,
)
from vultron.bt.report_management.states import RM


# Activity-specific fixtures (use finder, vendor, offer, report, dl from conftest.py)
@pytest.fixture
def reject(vendor, offer):
    return as_Reject(actor=vendor.as_id, object=offer)


@pytest.fixture
def tentative_reject(vendor, offer):
    return as_TentativeReject(actor=vendor.as_id, object=offer)


# Tests
def test_activity_structure_is_nested_correctly(reject):
    assert reject.as_type == "Reject"
    assert reject.as_object.as_type == "Offer"
    assert reject.as_object.as_object.as_type == "VulnerabilityReport"


def test_reject_offer_calls_datalayer_create(monkeypatch, dl, vendor, reject):
    mock_create = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.datalayer.tinydb_backend.TinyDbDataLayer.create",
        mock_create,
    )

    activity = reject
    assert activity.as_id not in dl

    reject_offer(actor_id=vendor.as_id, activity=activity)

    mock_create.assert_called_once_with(activity)
    # because create was mocked, activity still not persisted
    assert activity.as_id not in dl


def test_reject_offer_calls_rm_close_report(monkeypatch, dl, vendor, reject):
    mock_rm_close = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.reject.rm_close_report", mock_rm_close
    )

    activity = reject
    reject_offer(actor_id=vendor.as_id, activity=activity)

    mock_rm_close.assert_called_once_with(activity)


def test_rm_close_report_calls_set_status(monkeypatch, dl, reject):
    mock_set_status = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.reject.set_status", mock_set_status
    )

    dl.create(reject)
    activity = reject

    rm_close_report(activity)

    mock_set_status.assert_called()


def test_rm_close_report_updates_offer_and_report_statuses(
    monkeypatch, dl, reject
):
    mock_set_status = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.reject.set_status", mock_set_status
    )

    dl.create(reject)
    activity = reject

    rm_close_report(activity)

    matches = []
    for args in mock_set_status.call_args_list:
        obj = args[0][0]
        match obj.object_type:
            case "Offer":
                assert obj.status == OfferStatusEnum.REJECTED
                matches.append("Offer")
            case "VulnerabilityReport":
                assert obj.status == RM.CLOSED
                matches.append("VulnerabilityReport")

    assert "Offer" in matches
    assert "VulnerabilityReport" in matches


def test_tentative_reject_offer_calls_datalayer_create(
    monkeypatch, dl, vendor, tentative_reject
):
    mock_create = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.datalayer.tinydb_backend.TinyDbDataLayer.create",
        mock_create,
    )

    activity = tentative_reject
    assert activity.as_id not in dl

    tentative_reject_offer(actor_id=vendor.as_id, activity=activity)

    mock_create.assert_called_once_with(activity)
    assert activity.as_id not in dl


def test_tentative_reject_offer_calls_rm_invalidate_report(
    monkeypatch, dl, vendor, tentative_reject
):
    mock_rm_invalidate = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.reject.rm_invalidate_report",
        mock_rm_invalidate,
    )

    activity = tentative_reject
    tentative_reject_offer(actor_id=vendor.as_id, activity=activity)

    mock_rm_invalidate.assert_called_once_with(activity)


def test_rm_invalidate_report_calls_set_status(
    monkeypatch, dl, tentative_reject
):
    mock_set_status = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.reject.set_status", mock_set_status
    )

    dl.create(object_to_record(tentative_reject))
    activity = tentative_reject

    rm_invalidate_report(activity)

    mock_set_status.assert_called()


def test_rm_invalidate_report_updates_offer_and_report_statuses(
    monkeypatch, dl, tentative_reject
):
    mock_set_status = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.reject.set_status", mock_set_status
    )

    dl.create(object_to_record(tentative_reject))
    activity = tentative_reject

    rm_invalidate_report(activity)

    matches = []
    for args in mock_set_status.call_args_list:
        obj = args[0][0]
        match obj.object_type:
            case "Offer":
                assert obj.status == OfferStatusEnum.TENTATIVELY_REJECTED
                matches.append("Offer")
            case "VulnerabilityReport":
                assert obj.status == RM.INVALID
                matches.append("VulnerabilityReport")

    assert "Offer" in matches
    assert "VulnerabilityReport" in matches
