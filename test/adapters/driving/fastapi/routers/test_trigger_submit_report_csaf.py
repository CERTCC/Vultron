#!/usr/bin/env python

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
"""The submit-report trigger with a CSAF document (CSAF-01, CSAF-02, CSAF-04).

The Reporter's side of ADR-0184: a valid ``csaf_vulnerability_report`` is
attached to the offered report as a ``Document``, an invalid one or one of
another category is refused with a 422 naming each fault and nothing is sent,
and a name, summary or proposed embargo end the request leaves out is filled
from the document.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from test.wire.csaf._documents import (
    minimal_csaf_document,
    section,
    vulnerability_report_document,
)
from vultron.adapters.driving.fastapi.deps import get_trigger_dl
from vultron.adapters.driving.fastapi.routers import (
    trigger_report as trigger_report_router,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.report import VulnerabilityReport

_FLUSH = "vultron.adapters.driving.fastapi.trigger_runner.outbox_handler"
_RECIPIENT = "https://example.org/actors/vendor"
_TEXT = "An overflow in the Example Widget's parser."
_TITLE = "Buffer overflow in Example Widget"
_SUMMARY = "A short summary."


@pytest.fixture(autouse=True)
def _no_outbox_delivery():
    """No delivery: the queued flush is asserted in the routes contract."""
    with patch(_FLUSH, new_callable=AsyncMock):
        yield


@pytest.fixture
def client(dl):
    app = FastAPI()
    app.include_router(trigger_report_router.router)
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    yield TestClient(app)
    app.dependency_overrides = {}


def _report_document(*, days_to_disclosure: int = 30) -> dict[str, Any]:
    """A schema-valid vulnerability report that sets no P, X or A.

    Its one vulnerability is disclosed *days_to_disclosure* days from now,
    so the earliest future disclosure date proposes the embargo end.
    """
    data = vulnerability_report_document()
    vul = data["vulnerabilities"][0]
    del vul["metrics"]
    del vul["first_known_exploitation_dates"]
    vul["disclosure_date"] = (
        days_from_now_utc(days_to_disclosure)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return data


def _submit(client, actor, **body: Any):
    return client.post(
        f"/actors/{actor.id_}/trigger/submit-report",
        json={"report_content": _TEXT, "recipient_id": _RECIPIENT, **body},
    )


def _offered_report(resp) -> dict[str, Any]:
    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
    report: dict[str, Any] = resp.json()["offer"]["object"]
    return report


# ---------------------------------------------------------------------------
# AC-1: the document travels as an attached Document
# ---------------------------------------------------------------------------


@pytest.mark.spec("CSAF-01-001")
@pytest.mark.spec("CSAF-01-002")
def test_a_valid_csaf_document_is_sent_as_an_attached_json_document(
    client, actor
):
    data = _report_document()

    report = _offered_report(
        _submit(client, actor, report_name="Widget", csaf_document=data)
    )

    (attachment,) = report["attachment"]
    assert attachment["type"] == "Document"
    assert attachment["mediaType"] == "application/json"
    assert json.loads(attachment["content"]) == data
    assert report["content"] == _TEXT


@pytest.mark.spec("CSAF-01-001")
def test_the_stored_report_keeps_the_attachment(client, actor, dl):
    data = _report_document()

    report = _offered_report(
        _submit(client, actor, report_name="Widget", csaf_document=data)
    )

    assert [r.id_ for r in dl.list_objects("VulnerabilityReport")] == [
        report["id"]
    ]
    stored = dl.read(report["id"])
    assert isinstance(stored, VulnerabilityReport)
    assert stored.attachment is not None
    (attachment,) = stored.attachment
    assert isinstance(attachment, AttachedDocument)
    assert attachment.content is not None
    assert json.loads(attachment.content) == data
    assert stored.content == _TEXT


def test_without_a_document_the_report_attaches_nothing(client, actor):
    report = _offered_report(_submit(client, actor, report_name="Widget"))

    assert "attachment" not in report


# ---------------------------------------------------------------------------
# AC-2: strict sender
# ---------------------------------------------------------------------------


def _schema_invalid_document() -> dict[str, Any]:
    """A vulnerability report missing its title, with a malformed date."""
    data = _report_document()
    document = section(data, "document")
    del document["title"]
    section(data, "document", "tracking")["current_release_date"] = "soon"
    return data


def _refusal(resp) -> tuple[str, list[str]]:
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, resp.text
    detail = resp.json()["detail"]
    return detail["message"], [d["message"] for d in detail["details"]]


@pytest.mark.spec("CSAF-04-009")
@pytest.mark.spec("CSAF-02-007")
def test_a_schema_invalid_document_is_refused_naming_each_fault(
    client, actor, dl
):
    outbox_before = set(dl.outbox_list())

    _, faults = _refusal(
        _submit(
            client,
            actor,
            report_name="Widget",
            csaf_document=_schema_invalid_document(),
        )
    )

    assert any(f.startswith("$.document.title:") for f in faults), faults
    assert any(
        f.startswith("$.document.tracking.current_release_date:")
        for f in faults
    ), faults
    assert set(dl.outbox_list()) == outbox_before
    assert dl.list_objects("VulnerabilityReport") == []


@pytest.mark.spec("CSAF-04-009")
def test_a_document_of_another_category_is_refused(client, actor, dl):
    outbox_before = set(dl.outbox_list())

    _, faults = _refusal(
        _submit(
            client,
            actor,
            report_name="Widget",
            csaf_document=minimal_csaf_document(),
        )
    )

    assert faults == [
        "the document has document.category 'csaf_base'; submit-report"
        " attaches only a 'csaf_vulnerability_report' (CSAF-04-009)"
    ]
    assert set(dl.outbox_list()) == outbox_before
    assert dl.list_objects("VulnerabilityReport") == []


@pytest.mark.spec("CSAF-04-009")
def test_every_fault_is_named_not_only_the_first(client, actor):
    data = _schema_invalid_document()
    section(data, "document")["category"] = "csaf_security_advisory"

    message, faults = _refusal(
        _submit(client, actor, report_name="Widget", csaf_document=data)
    )

    assert len(faults) >= 3, faults
    assert any("csaf_security_advisory" in f for f in faults)
    for fault in faults:
        assert fault in message


@pytest.mark.spec("CSAF-04-009")
def test_a_json_object_that_is_not_csaf_is_refused(client, actor, dl):
    _, faults = _refusal(
        _submit(
            client,
            actor,
            report_name="Widget",
            csaf_document={"title": "not CSAF"},
        )
    )

    assert any(f.startswith("$.$schema:") for f in faults), faults
    assert any("states no document.category" in f for f in faults)
    assert dl.list_objects("VulnerabilityReport") == []


def test_a_csaf_document_that_is_not_an_object_is_422(client, actor):
    resp = _submit(
        client, actor, report_name="Widget", csaf_document=["not", "CSAF"]
    )

    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_a_report_with_neither_name_nor_document_is_422(client, actor):
    resp = _submit(client, actor)

    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "report_name is required" in resp.text


# ---------------------------------------------------------------------------
# AC-3: the document fills what the request leaves out
# ---------------------------------------------------------------------------


@pytest.mark.spec("CSAF-04-010")
@pytest.mark.spec("CSAF-02-004")
def test_a_missing_name_summary_and_embargo_end_come_from_the_document(
    client, actor
):
    data = _report_document(days_to_disclosure=30)
    disclosure = data["vulnerabilities"][0]["disclosure_date"]

    resp = _submit(client, actor, csaf_document=data)

    report = _offered_report(resp)
    assert report["name"] == _TITLE
    assert report["summary"] == _SUMMARY
    proposed = resp.json()["offer"]["proposedEmbargo"]
    assert proposed["context"] == report["id"]
    assert proposed["endTime"].startswith(disclosure.removesuffix("Z"))


@pytest.mark.spec("CSAF-04-010")
def test_a_stated_name_summary_and_embargo_end_are_kept(client, actor):
    end = days_from_now_utc(60).replace(microsecond=0)

    resp = _submit(
        client,
        actor,
        report_name="Widget",
        report_summary="The Reporter's own summary.",
        proposed_embargo_end_time=end.isoformat(),
        csaf_document=_report_document(days_to_disclosure=30),
    )

    report = _offered_report(resp)
    assert report["name"] == "Widget"
    assert report["summary"] == "The Reporter's own summary."
    assert resp.json()["offer"]["proposedEmbargo"]["endTime"].startswith(
        end.strftime("%Y-%m-%dT%H:%M:%S")
    )


@pytest.mark.spec("CSAF-04-010")
def test_a_document_that_sets_exploitation_proposes_no_embargo_end(
    client, actor
):
    # The fixture's vulnerability states SSVC Exploitation PoC, which sets X,
    # so the case would start with no embargo (EP-04-020).
    resp = _submit(
        client, actor, csaf_document=vulnerability_report_document()
    )

    assert _offered_report(resp)["name"] == _TITLE
    assert "proposedEmbargo" not in resp.json()["offer"]


@pytest.mark.spec("CSAF-04-010")
def test_a_stated_embargo_end_is_kept_when_the_document_sets_exploitation(
    client, actor
):
    end = days_from_now_utc(20).replace(microsecond=0)

    resp = _submit(
        client,
        actor,
        proposed_embargo_end_time=end.isoformat(),
        csaf_document=vulnerability_report_document(),
    )

    assert resp.json()["offer"]["proposedEmbargo"]["endTime"].startswith(
        end.strftime("%Y-%m-%dT%H:%M:%S")
    )


def test_a_past_disclosure_date_proposes_no_embargo_end(client, actor):
    data = _report_document()
    data["vulnerabilities"][0]["disclosure_date"] = "2020-01-01T00:00:00Z"

    resp = _submit(client, actor, csaf_document=data)

    assert _offered_report(resp)["name"] == _TITLE
    assert "proposedEmbargo" not in resp.json()["offer"]
