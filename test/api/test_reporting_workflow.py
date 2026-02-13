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

from vultron.api.v2.backend import handlers as h
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
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
from vultron.as_vocab.type_helpers import AsActivityType
from vultron.enums import MessageSemantics
from vultron.semantic_map import find_matching_semantics
from vultron.types import BehaviorHandler, DispatchActivity


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
    # Use in-memory storage for tests (db_path=None)
    dl = get_datalayer(db_path=None)
    dl.clear_all()  # Clear before use to ensure clean state
    yield dl
    dl.clear_all()


def _call_handler(
    activity: AsActivityType, handler: BehaviorHandler, actor=None
):

    semantics = find_matching_semantics(activity)

    assert semantics != MessageSemantics.UNKNOWN
    assert semantics in MessageSemantics

    dispatchable = DispatchActivity(
        semantic_type=semantics, activity_id=activity.as_id, payload=activity
    )

    try:
        result = handler(dispatchable=dispatchable)
    except Exception as e:
        pytest.fail(f"Handler raised an exception: {e}")
    assert result is None


# TODO shouldn't we be testing the dispatcher routing to the right handler?


# Tests
def test_create_report_handler_returns_none(reporter, report):
    activity = as_Create(actor=reporter, object=report)
    _call_handler(activity, h.create_report)


def test_submit_report_persists_activity_and_report(reporter, report, dl):
    activity = as_Offer(actor=reporter, object=report)
    _call_handler(activity, h.submit_report)

    # check side effects
    assert dl.read(activity.as_id) is not None
    assert dl.read(report.as_id) is not None


def test_read_activity_handler_noop_returns_none(reporter, report):
    activity = as_Read(
        actor=reporter, object=as_Offer(actor=reporter, object=report)
    )
    _call_handler(activity, h.ack_report)  # No read handler yet


def test_accept_offer(reporter, report):
    offer = as_Offer(actor=reporter, object=report)
    activity = as_Accept(actor=reporter, object=offer)
    _call_handler(activity, h.validate_report)


@pytest.mark.xfail(
    reason="Uses deprecated _old_handlers that have import issues"
)
def test_tentative_reject_triggers_invalidation(monkeypatch, reporter, report):
    mock_invalidate = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend._old_handlers.reject.rm_invalidate_report",
        mock_invalidate,
    )

    offer = as_Offer(actor=reporter, object=report)
    activity = as_TentativeReject(actor=reporter, object=offer)
    _call_handler(activity, tentative_reject_offer, reporter)

    mock_invalidate.assert_called_once_with(activity)


def test_create_case_handler_returns_none(coordinator, case):
    activity = as_Create(actor=coordinator, object=case)
    _call_handler(activity, h.create_case, coordinator)


@pytest.mark.xfail(
    reason="Uses deprecated _old_handlers that have import issues"
)
def test_reject_offer_triggers_close_report(monkeypatch, reporter, report):
    mock_rm_close = Mock()
    monkeypatch.setattr(
        "vultron.api.v2.backend._old_handlers.reject.rm_close_report",
        mock_rm_close,
    )

    offer = as_Offer(actor=reporter, object=report)
    activity = as_Reject(actor=reporter, object=offer)
    _call_handler(activity, reject_offer, reporter)

    mock_rm_close.assert_called_once_with(activity)
