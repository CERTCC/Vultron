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
"""Dispositions of AddReportToCaseReceivedUseCase (HP-01-003, #2255)."""

from types import SimpleNamespace
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.events.case import AddReportToCaseReceivedEvent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.case.lifecycle import (
    AddReportToCaseReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/lifecycle-001"
_REPORT_ID = "https://example.org/reports/lifecycle-001"


@pytest.fixture()
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/actors/cm"
    )


def _request(
    report_id: str | None = _REPORT_ID, case_id: str | None = _CASE_ID
) -> AddReportToCaseReceivedEvent:
    return cast(
        AddReportToCaseReceivedEvent,
        SimpleNamespace(report_id=report_id, case_id=case_id),
    )


@pytest.mark.spec("HP-01-003")
def test_adding_new_report_is_applied(dl):
    dl.create(as_VulnerabilityCase(id_=_CASE_ID, name="Lifecycle"))

    result = AddReportToCaseReceivedUseCase(dl, _request()).execute()

    assert result.disposition == HandlerDisposition.APPLIED


@pytest.mark.spec("HP-01-003")
def test_report_already_in_case_is_skipped(dl):
    case = as_VulnerabilityCase(id_=_CASE_ID, name="Lifecycle")
    case.vulnerability_reports.append(_REPORT_ID)
    dl.create(case)

    result = AddReportToCaseReceivedUseCase(dl, _request()).execute()

    assert result.disposition == HandlerDisposition.SKIPPED


@pytest.mark.spec("HP-01-003")
def test_unknown_case_is_refused(dl):
    result = AddReportToCaseReceivedUseCase(dl, _request()).execute()

    assert result.disposition == HandlerDisposition.REFUSED
    assert result.reason is not None and _CASE_ID in result.reason


@pytest.mark.spec("HP-01-003")
@pytest.mark.parametrize(
    "request_", [_request(report_id=None), _request(case_id=None)]
)
def test_missing_id_is_refused(dl, request_):
    result = AddReportToCaseReceivedUseCase(dl, request_).execute()

    assert result.disposition == HandlerDisposition.REFUSED
