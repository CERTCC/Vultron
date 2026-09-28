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
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)
from vultron.core.models.events import MessageSemantics
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.report import (
    CreateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
    ValidateReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    AckReportReceivedUseCase,
    CloseReportReceivedUseCase,
)
from vultron.core.use_cases.received.case import CreateCaseReceivedUseCase


# Fixtures
@pytest.fixture
def reporter():
    return as_Actor(name="Test Reporter")


@pytest.fixture
def report(reporter):
    return as_VulnerabilityReport(
        name="Test Vulnerability Report",
        summary="This is a test vulnerability report.",
        attributed_to=reporter.id_,
    )


@pytest.fixture
def coordinator():
    return as_Actor(name="Test Coordinator")


@pytest.fixture
def case(report):
    return as_VulnerabilityCase(
        name="Test Vulnerability Case",
        vulnerability_reports=[report],
    )


@pytest.fixture
def dl():
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )
    yield dl
    dl.clear_all()


def _call_use_case(
    activity: as_Activity,
    use_case_class,
    dl=None,
    expected: HandlerDisposition = HandlerDisposition.APPLIED,
):
    from vultron.semantic_registry import extract_event

    event = extract_event(activity)

    assert event.semantic_type != MessageSemantics.UNKNOWN
    assert event.semantic_type in MessageSemantics

    try:
        result = use_case_class(dl, event).execute()
    except Exception as e:
        pytest.fail(f"Use case raised an exception: {e}")
    # A handler reports what it did with the message (HP-01-003, #2255).
    assert result.disposition is expected, result.reason


# TODO shouldn't we be testing the dispatcher routing to the right handler?


# Tests
def test_create_report_handler_returns_applied(reporter, report, dl):
    activity = as_Create(actor=reporter, object_=report)
    _call_use_case(activity, CreateReportReceivedUseCase, dl=dl)


def test_submit_report_persists_activity_and_report(reporter, report, dl):
    activity = as_Offer(actor=reporter, object_=report)
    # Addressed to no one, so the receiver refuses it (HP-01-005): the Offer
    # names no party entitled to propose a case.  The report is still stored
    # for a later explicit decision (CM-15-001).
    _call_use_case(
        activity,
        SubmitReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )

    # check side effects
    assert dl.read(activity.id_) is not None
    assert dl.read(report.id_) is not None


def test_read_activity_handler_noop_returns_applied(reporter, report, dl):
    activity = as_Read(
        actor=reporter, object_=as_Offer(actor=reporter, object_=report)
    )
    _call_use_case(activity, AckReportReceivedUseCase, dl=dl)


def test_accept_offer(reporter, report, dl):
    offer = as_Offer(actor=reporter, object_=report)
    activity = as_Accept(actor=reporter, object_=offer)
    # No local case for the report, so there is no RM state to move (#2255).
    _call_use_case(
        activity,
        ValidateReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )


def test_tentative_reject_triggers_invalidation(reporter, report, dl):
    offer = as_Offer(actor=reporter, object_=report)
    activity = as_TentativeReject(actor=reporter, object_=offer)
    # No local case for the report, so there is no RM state to move (#2255).
    _call_use_case(
        activity,
        InvalidateReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )

    # check side effects
    assert dl.read(activity.id_) is not None


def test_create_case_from_untrusted_sender_is_refused(coordinator, case, dl):
    # No pending link and no CASE_MANAGER in the snapshot, so nothing makes
    # the sender a trusted creator of this replica (#2255).
    activity = as_Create(actor=coordinator, object_=case)
    _call_use_case(
        activity,
        CreateCaseReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )


def test_reject_offer_triggers_close_report(reporter, report, dl):
    offer = as_Offer(actor=reporter, object_=report)
    activity = as_Reject(actor=reporter, object_=offer)
    # No local case for the report, so there is no RM state to move (#2255).
    _call_use_case(
        activity,
        CloseReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )

    # check side effects
    assert dl.read(activity.id_) is not None
