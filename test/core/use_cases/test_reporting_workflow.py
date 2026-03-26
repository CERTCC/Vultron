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

import pytest

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Offer,
    as_Read,
    as_Reject,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.core.models.events import MessageSemantics
from vultron.core.use_cases.report import (
    CreateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
    ValidateReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    AckReportReceivedUseCase,
    CloseReportReceivedUseCase,
)
from vultron.core.use_cases.case import CreateCaseReceivedUseCase


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
    from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer

    dl = TinyDbDataLayer(db_path=None)
    yield dl
    dl.clear_all()


def _call_use_case(activity: as_Activity, use_case_class, dl=None):
    from vultron.wire.as2.extractor import extract_intent

    event = extract_intent(activity)

    assert event.semantic_type != MessageSemantics.UNKNOWN
    assert event.semantic_type in MessageSemantics

    try:
        result = use_case_class(dl, event).execute()
    except Exception as e:
        pytest.fail(f"Use case raised an exception: {e}")
    assert result is None


# TODO shouldn't we be testing the dispatcher routing to the right handler?


# Tests
def test_create_report_handler_returns_none(reporter, report, dl):
    activity = as_Create(actor=reporter, as_object=report)
    _call_use_case(activity, CreateReportReceivedUseCase, dl=dl)


def test_submit_report_persists_activity_and_report(reporter, report, dl):
    activity = as_Offer(actor=reporter, as_object=report)
    _call_use_case(activity, SubmitReportReceivedUseCase, dl=dl)

    # check side effects
    assert dl.read(activity.as_id) is not None
    assert dl.read(report.as_id) is not None


def test_read_activity_handler_noop_returns_none(reporter, report, dl):
    activity = as_Read(
        actor=reporter, as_object=as_Offer(actor=reporter, as_object=report)
    )
    _call_use_case(activity, AckReportReceivedUseCase, dl=dl)


def test_accept_offer(reporter, report, dl):
    offer = as_Offer(actor=reporter, as_object=report)
    activity = as_Accept(actor=reporter, as_object=offer)
    _call_use_case(activity, ValidateReportReceivedUseCase, dl=dl)


def test_tentative_reject_triggers_invalidation(reporter, report, dl):
    offer = as_Offer(actor=reporter, as_object=report)
    activity = as_TentativeReject(actor=reporter, as_object=offer)
    _call_use_case(activity, InvalidateReportReceivedUseCase, dl=dl)

    # check side effects
    assert dl.read(activity.as_id) is not None


def test_create_case_handler_returns_none(coordinator, case, dl):
    activity = as_Create(actor=coordinator, as_object=case)
    _call_use_case(activity, CreateCaseReceivedUseCase, dl=dl)


def test_reject_offer_triggers_close_report(reporter, report, dl):
    offer = as_Offer(actor=reporter, as_object=report)
    activity = as_Reject(actor=reporter, as_object=offer)
    _call_use_case(activity, CloseReportReceivedUseCase, dl=dl)

    # check side effects
    assert dl.read(activity.as_id) is not None
