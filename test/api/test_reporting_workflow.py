#!/usr/bin/env python
"""
Test the reporting workflow
"""

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
)
from vultron.api.v2.backend.handlers.create import (
    rm_create_report,
    create_case,
)
from vultron.api.v2.backend.handlers.offer import rm_submit_report
from vultron.api.v2.backend.handlers.read import rm_read_report
from vultron.api.v2.backend.handlers.reject import (
    reject_offer,
    tentative_reject_offer,
)
from vultron.api.v2.data import get_datalayer
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Create,
    as_Offer,
    as_Read,
    as_TentativeReject,
    as_Reject,
    as_Accept,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


# Fixtures
@pytest.fixture
def reporter():
    return as_Actor(name="Test Reporter")


@pytest.fixture
def report(reporter):
    return VulnerabilityReport(
        name="Test Vulnerability Report",
        summary="This is a test vulnerability report.",
        attributed_to=reporter,
    )


@pytest.fixture
def coordinator():
    return as_Actor(name="Test Coordinator")


@pytest.fixture
def case(report):
    return VulnerabilityCase(
        name="Test Vulnerability Case",
        vulnerability_reports=[report],
    )


@pytest.fixture
def dl():
    dl = get_datalayer()
    assert not dl.all()
    yield dl
    dl.clear()


# Helper to call handlers and assert no exceptions and expected return
def _call_handler(activity, handler, actor):
    try:
        result = handler(actor_id=actor.as_id, activity=activity)
    except Exception as e:
        pytest.fail(f"Handler raised an exception: {e}")
    assert result is None


# Tests
def test_create_report(reporter, report):
    activity = as_Create(actor=reporter, object=report)
    _call_handler(activity, rm_create_report, reporter)


def test_offer_report(reporter, report, dl):
    activity = as_Offer(actor=reporter, object=report)
    _call_handler(activity, rm_submit_report, reporter)

    # check side effects
    assert activity.as_id in dl
    assert report.as_id in dl


def test_read_report(reporter, report):
    activity = as_Read(actor=reporter, object=report)
    _call_handler(activity, rm_read_report, reporter)  # No read handler yet


def test_validate_report(monkeypatch, reporter, report):
    mock_validate = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.accept.rm_validate_report",
        mock_validate,
    )

    offer = as_Offer(actor=reporter, object=report)
    activity = as_Accept(actor=reporter, object=offer)
    _call_handler(activity, accept_offer_handler, reporter)

    mock_validate.assert_called_once_with(activity)


def test_invalidate_report(monkeypatch, reporter, report):
    mock_invalidate = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.reject.rm_invalidate_report",
        mock_invalidate,
    )

    offer = as_Offer(actor=reporter, object=report)
    activity = as_TentativeReject(actor=reporter, object=offer)
    _call_handler(activity, tentative_reject_offer, reporter)

    mock_invalidate.assert_called_once_with(activity)


def test_create_case(coordinator, case):
    activity = as_Create(actor=coordinator, object=case)
    _call_handler(activity, create_case, coordinator)


def test_reject_offer(monkeypatch, reporter, report):
    mock_rm_close = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend.handlers.reject.rm_close_report", mock_rm_close
    )

    offer = as_Offer(actor=reporter, object=report)
    activity = as_Reject(actor=reporter, object=offer)
    _call_handler(activity, reject_offer, reporter)

    mock_rm_close.assert_called_once_with(activity)
