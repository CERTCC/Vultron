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

from test.support.act_runner import run_in_act
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from vultron.core.models.events import MessageSemantics
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.case import CreateCaseReceivedUseCase
from vultron.core.use_cases.received.report import (
    AckReportReceivedUseCase,
    CloseReportReceivedUseCase,
    CreateReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Offer,
    as_Read,
    as_Reject,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)


# Fixtures
@pytest.fixture
def reporter():
    return make(as_Actor, name="Test Reporter")


@pytest.fixture
def report(reporter):
    return make(
        as_VulnerabilityReport,
        name="Test Vulnerability Report",
        summary="This is a test vulnerability report.",
        attributed_to=reporter.id_,
    )


@pytest.fixture
def coordinator():
    return make(as_Actor, name="Test Coordinator")


@pytest.fixture
def case(report):
    return make(
        as_VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
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
    from test.support.received import received_event

    event = received_event(activity, at=dl)

    assert event.semantic_type != MessageSemantics.UNKNOWN
    assert event.semantic_type in MessageSemantics

    try:
        result = run_in_act(use_case_class(dl, event))
    except Exception as e:  # noqa: BLE001  # ruff-baseline #3989
        pytest.fail(f"Use case raised an exception: {e}")
    # A handler reports what it did with the message (HP-01-003, #2255).
    assert result.disposition is expected, result.reason


# TODO shouldn't we be testing the dispatcher routing to the right handler?


# Tests
def test_create_report_handler_returns_applied(reporter, report, dl):
    activity = make(
        as_Create, actor=reporter, object_=report, to=[dl.actor_id]
    )
    _call_use_case(activity, CreateReportReceivedUseCase, dl=dl)


def test_unaddressed_submit_report_is_refused_and_stores_nothing(
    reporter, report, dl
):
    activity = make(as_Offer, actor=reporter, object_=report)
    # Addressed to no one, so the addressee door refuses it before anything
    # is stored (HP-01-005, ADR-0154): no report, and no received record,
    # because intake never ran; the inbox's outcome stage writes the receipt
    # stub from the delivery itself (CLP-10-018).
    _call_use_case(
        activity,
        SubmitReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )

    assert dl.read(ReceivedActivityRecord.build_id(activity.id_)) is None
    assert dl.read(report.id_) is None


def test_read_activity_from_a_non_addressee_is_refused(reporter, report, dl):
    activity = make(
        as_Read,
        actor=reporter,
        object_=make(as_Offer, actor=reporter, object_=report),
    )
    # The receiver holds no record of the Offer naming the sender as its
    # addressee, so the sender is not entitled to acknowledge it (RMB-08-004).
    _call_use_case(
        activity,
        AckReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )


def test_accept_offer(reporter, report, dl):
    offer = make(as_Offer, actor=reporter, object_=report)
    activity = make(as_Accept, actor=reporter, object_=offer)
    # No local case for the report, so there is no RM state to move (#2255).
    _call_use_case(
        activity,
        ValidateReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )


def test_tentative_reject_triggers_invalidation(reporter, report, dl):
    offer = make(as_Offer, actor=reporter, object_=report)
    activity = make(as_TentativeReject, actor=reporter, object_=offer)
    # No local case for the report, so there is no RM state to move (#2255).
    _call_use_case(
        activity,
        InvalidateReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )

    # A door refused it, so intake recorded nothing: the outcome stage
    # leaves its receipt stub from the delivery's own body (CLP-10-018).
    assert dl.read(ReceivedActivityRecord.build_id(activity.id_)) is None


def test_create_case_from_untrusted_sender_is_refused(coordinator, case, dl):
    # No anchor this actor wrote names the sender, so nothing makes it a
    # trusted creator of this replica (#2255, CBT-01-011).
    activity = make(as_Create, actor=coordinator, object_=case)
    _call_use_case(
        activity,
        CreateCaseReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )


def test_reject_offer_triggers_close_report(reporter, report, dl):
    offer = make(as_Offer, actor=reporter, object_=report)
    activity = make(as_Reject, actor=reporter, object_=offer)
    # No local case for the report, so there is no RM state to move (#2255).
    _call_use_case(
        activity,
        CloseReportReceivedUseCase,
        dl=dl,
        expected=HandlerDisposition.REFUSED,
    )

    # A door refused it, so intake recorded nothing: the outcome stage
    # leaves its receipt stub from the delivery's own body (CLP-10-018).
    assert dl.read(ReceivedActivityRecord.build_id(activity.id_)) is None
