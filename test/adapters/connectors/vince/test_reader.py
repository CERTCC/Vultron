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

"""The VINCE case reader fetches a case and returns its translation (#5963).

A fake transport serves the committed synthetic fixtures
(``test/fixtures/vince/``) as the VINCE API would: each read's JSON with
200, and a ``null`` read as 404.  No test reaches a network.

Spec: CRD-01-002 to CRD-01-006, CRD-02-004, CRD-02-006, ARCH-05-004,
ARCH-05-005, VSD-01-003 to VSD-01-005.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx2 as httpx
import pytest
from pydantic import SecretStr

from test.adapters.connectors.vince._support import (
    ACTIVE,
    AS_OF,
    AT_DUE_DATE,
    CASES,
    COMM_URL,
    INACTIVE,
    UNKNOWN,
    actors_by_name,
    reads,
    translate,
)
from test.support.connector_ports import surplus_members
from vultron.adapters.connectors.base import ports_implemented_by
from vultron.adapters.connectors.vince import (
    READS,
    VINCE_UNOBSERVABLE,
    VinceCaseReader,
    translate_case,
)
from vultron.adapters.connectors.vince.reader import DEFAULT_READ_TIMEOUT
from vultron.config.app import config_override
from vultron.config.vince import VinceConfig
from vultron.core.models.case_reading import CaseReading
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import (
    VinceAuthError,
    VinceCaseNotFoundError,
    VinceRateLimitedError,
    VinceReadError,
    VinceUnavailableError,
    VultronConfigError,
    VultronMissingCredentialError,
    VultronValidationError,
)

API_URL = f"{COMM_URL}/api"
TOKEN = "synthetic-token-5963"  # noqa: S105 - a made-up test value

Respond = Callable[[httpx.Request, str], httpx.Response | None]


@dataclass
class FakeVince:
    """A fake VINCE Comm API serving one fixture case's reads.

    *respond*, when set, may answer a read in its own way; a ``None`` from
    it falls through to the fixture.  Every request is recorded.
    """

    case_reads: Mapping[str, Any]
    respond: Respond | None = None
    requests: list[httpx.Request] = field(default_factory=list)

    @property
    def vuid(self) -> str:
        vuid: str = self.case_reads["case"]["vuid"]
        return vuid

    def _read(self, request: httpx.Request) -> str:
        prefix = f"/vince/comm/api/case/{self.vuid}/"
        path = request.url.path
        assert path.startswith(prefix), path
        return path.removeprefix(prefix).removesuffix("/") or "case"

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        read = self._read(request)
        if self.respond is not None:
            answer = self.respond(request, read)
            if answer is not None:
                return answer
        body = self.case_reads.get(read)
        if body is None:
            return httpx.Response(404, json={"detail": "Not found."})
        return httpx.Response(200, json=body)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    @property
    def reads_requested(self) -> list[str]:
        return [self._read(r) for r in self.requests]


class Clock:
    """A fixed clock that counts how often it is read."""

    def __init__(self, at: datetime) -> None:
        self.at = at
        self.reads = 0

    def __call__(self) -> datetime:
        self.reads += 1
        return self.at


def _config(**overrides: Any) -> VinceConfig:
    values: dict[str, Any] = {"base_url": API_URL, "api_token": TOKEN}
    values.update(overrides)
    return VinceConfig.model_validate(values)


def _reader(
    vince: FakeVince, at: datetime, config: VinceConfig | None = None
) -> VinceCaseReader:
    return VinceCaseReader(
        config if config is not None else _config(),
        transport=vince.transport,
        clock=Clock(at),
    )


def _read(stem: str, **kwargs: Any) -> tuple[CaseReading, FakeVince]:
    vince = FakeVince(reads(stem), **kwargs)
    return _reader(vince, AS_OF[stem]).read_case(vince.vuid), vince


# --- AC-1: one VINCE case in, its translation out ----------------------


@pytest.mark.spec("CRD-01-003")
@pytest.mark.parametrize("stem", CASES)
def test_the_reader_returns_the_translation_of_the_fetched_reads(stem):
    reading, _ = _read(stem)

    assert reading == translate(stem)


@pytest.mark.parametrize("stem", CASES)
def test_the_reader_sends_one_get_per_read_with_the_credential(stem):
    _, vince = _read(stem)

    assert vince.reads_requested == list(READS)
    assert {r.method for r in vince.requests} == {"GET"}
    for request in vince.requests:
        assert request.headers["Authorization"] == f"Token {TOKEN}"
        assert request.headers["Accept"] == "application/json"
        assert request.url.path.endswith("/")


def test_a_vu_prefixed_case_id_reads_the_same_case():
    vince = FakeVince(reads(ACTIVE))

    reading = _reader(vince, AS_OF[ACTIVE]).read_case(f"VU#{vince.vuid}")

    assert reading == translate(ACTIVE)


def test_a_read_vince_answers_404_reaches_the_translation_as_absent():
    def no_note(_request: httpx.Request, read: str) -> httpx.Response | None:
        return httpx.Response(404) if read == "note" else None

    reading, _ = _read(INACTIVE, respond=no_note)

    without_note = {**reads(INACTIVE), "note": None}
    assert reading == translate_case(
        without_note, comm_url=COMM_URL, as_of=AS_OF[INACTIVE]
    )
    assert reading != translate(INACTIVE)


@pytest.mark.spec("CRD-02-006")
def test_the_clock_is_read_once_and_is_the_time_of_reading():
    """The embargo of 999901 ends at its due_date only when the reader's
    clock says the case is read at or after it (VINCE-EM-03)."""
    vince = FakeVince(reads(ACTIVE))
    clock = Clock(AT_DUE_DATE)
    reader = VinceCaseReader(_config(), transport=vince.transport, clock=clock)

    reading = reader.read_case(vince.vuid)

    assert clock.reads == 1
    assert reading == translate(ACTIVE, as_of=AT_DUE_DATE)
    assert reading != translate(ACTIVE)


def test_the_reader_keeps_nothing_between_requests():
    vince = FakeVince(reads(ACTIVE))
    reader = _reader(vince, AS_OF[ACTIVE])

    assert reader.read_case(vince.vuid) == reader.read_case(vince.vuid)
    assert len(vince.requests) == 2 * len(READS)


# --- AC-2: each entry cites its VINCE record and names who acted -------


@pytest.mark.spec("CRD-01-004")
@pytest.mark.spec("CRD-01-006")
@pytest.mark.parametrize("stem", CASES)
def test_every_entry_cites_a_vince_record_and_names_a_participant(stem):
    reading, vince = _read(stem)

    cited = {c.entry_id: c.source_record for c in reading.citations}
    assert set(cited) == {entry.id_ for entry in reading.ledger}
    records = {f"case/{vince.vuid}/"} | {
        f"case/{vince.vuid}/{read}/" for read in READS if read != "case"
    }
    assert all(source.split("[")[0] in records for source in cited.values()), (
        cited
    )
    participants = set(actors_by_name(reading).values())
    assert {e.payload_snapshot["actor"] for e in reading.ledger} <= (
        participants
    )


# --- AC-3: what cannot be translated comes back --------------------------


@pytest.mark.spec("CRD-01-005")
def test_an_untranslatable_fixture_record_is_returned_not_dropped():
    reading, _ = _read(UNKNOWN)

    assert reading.untranslated
    assert reading.untranslated == translate(UNKNOWN).untranslated


@pytest.mark.spec("CRD-02-004")
def test_every_reading_carries_the_vince_unobservable_declaration():
    reading, _ = _read(ACTIVE)

    assert VinceCaseReader().unobservable == VINCE_UNOBSERVABLE
    assert reading.unobservable == VINCE_UNOBSERVABLE


# --- AC-4: no write path -------------------------------------------------


@pytest.mark.spec("ARCH-05-004")
def test_the_reader_implements_the_case_reader_port_only():
    assert ports_implemented_by(VinceCaseReader()) == (CaseReader,)


@pytest.mark.spec("CRD-01-002")
@pytest.mark.spec("ARCH-05-005")
def test_the_reader_exposes_no_member_beyond_its_name_and_the_port():
    """A write method, even a raising stub, would be a surplus member."""
    assert surplus_members(VinceCaseReader()) == set()


@pytest.mark.parametrize(
    "case_id",
    [
        "999901/vendor/statement",
        "../vulreport",
        "999901?x=1",
        "VU#",
        "",
        "abc",
        "\u0661\u0662\u0663",
    ],
)
def test_a_case_id_that_is_not_a_vince_number_is_refused_unsent(case_id):
    """Only digits reach a URL, so no case id reaches a write endpoint."""
    vince = FakeVince(reads(ACTIVE))

    with pytest.raises(VultronValidationError, match="VINCE case id"):
        _reader(vince, AS_OF[ACTIVE]).read_case(case_id)

    assert vince.requests == []


# --- AC-6: failures are named and never retried -------------------------


def _failing_at(read: str, response: httpx.Response) -> Respond:
    def respond(_request: httpx.Request, at: str) -> httpx.Response | None:
        return response if at == read else None

    return respond


@pytest.mark.parametrize(
    ("read", "response", "error"),
    [
        ("case", httpx.Response(404), VinceCaseNotFoundError),
        ("case", httpx.Response(401), VinceAuthError),
        ("posts", httpx.Response(403), VinceAuthError),
        ("vuls", httpx.Response(429), VinceRateLimitedError),
        ("note", httpx.Response(500), VinceUnavailableError),
        ("vendors", httpx.Response(503), VinceUnavailableError),
        (
            "report",
            httpx.Response(
                302,
                headers={
                    "Location": f"{API_URL}/case/999901/vendor/statement/"
                },
            ),
            VinceReadError,
        ),
        ("report", httpx.Response(400), VinceReadError),
        ("vendors/vuls", httpx.Response(200, text="<html>"), VinceReadError),
    ],
)
def test_a_failed_read_raises_its_named_error_after_one_attempt(
    read, response, error
):
    vince = FakeVince(reads(ACTIVE), respond=_failing_at(read, response))

    with pytest.raises(error) as excinfo:
        _reader(vince, AS_OF[ACTIVE]).read_case(vince.vuid)

    # A redirect is not followed: its target is never requested.
    assert vince.reads_requested == list(READS[: READS.index(read) + 1])
    assert excinfo.value.vuid == vince.vuid
    assert excinfo.value.read == read
    assert excinfo.value.status == response.status_code


@pytest.mark.parametrize(
    ("headers", "retry_after"),
    [
        ({"Retry-After": "120"}, 120.0),
        ({"Retry-After": "0"}, 0.0),
        ({}, None),
        ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
        ({"Retry-After": "nan"}, None),
        ({"Retry-After": "inf"}, None),
        ({"Retry-After": "-5"}, None),
    ],
)
def test_a_rate_limit_carries_the_wait_vince_asked_for(headers, retry_after):
    response = httpx.Response(429, headers=headers)
    vince = FakeVince(reads(ACTIVE), respond=_failing_at("case", response))

    with pytest.raises(VinceRateLimitedError) as excinfo:
        _reader(vince, AS_OF[ACTIVE]).read_case(vince.vuid)

    assert excinfo.value.retry_after == retry_after
    assert len(vince.requests) == 1


@pytest.mark.parametrize("timeout", [None, 4.5])
def test_every_read_carries_the_readers_timeout(timeout):
    vince = FakeVince(reads(ACTIVE))
    kwargs = {} if timeout is None else {"timeout": timeout}
    reader = VinceCaseReader(
        _config(),
        transport=vince.transport,
        clock=Clock(AS_OF[ACTIVE]),
        **kwargs,
    )

    reader.read_case(vince.vuid)

    expected = DEFAULT_READ_TIMEOUT if timeout is None else timeout
    for request in vince.requests:
        assert request.extensions["timeout"] == dict.fromkeys(
            ("connect", "read", "write", "pool"), expected
        )


@pytest.mark.parametrize(
    ("raised", "reason"),
    [
        (
            httpx.ConnectError("refused"),
            r"could not reach VINCE \(ConnectError\)",
        ),
        (httpx.ReadTimeout("slow"), "timed out"),
    ],
)
def test_an_unreachable_vince_is_named_after_one_attempt(raised, reason):
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise raised

    reader = VinceCaseReader(
        _config(),
        transport=httpx.MockTransport(handle),
        clock=Clock(AS_OF[ACTIVE]),
    )

    with pytest.raises(VinceUnavailableError, match=reason) as excinfo:
        reader.read_case("999901")

    assert len(calls) == 1
    assert excinfo.value.status is None


# --- Configuration and the credential ------------------------------------


@pytest.mark.parametrize(
    ("config", "error", "names"),
    [
        (VinceConfig(api_token=SecretStr(TOKEN)), VultronConfigError, "URL"),
        (
            VinceConfig(base_url=COMM_URL, api_token=SecretStr(TOKEN)),
            VultronConfigError,
            "/api",
        ),
        (
            VinceConfig(base_url=API_URL),
            VultronMissingCredentialError,
            "VULTRON_VINCE__API_TOKEN",
        ),
    ],
)
def test_a_missing_or_unusable_setting_refuses_the_read_unsent(
    config, error, names
):
    vince = FakeVince(reads(ACTIVE))

    with pytest.raises(error, match=names):
        _reader(vince, AS_OF[ACTIVE], config).read_case(vince.vuid)

    assert vince.requests == []


@pytest.mark.spec("VSD-01-004")
def test_the_reader_reads_its_settings_when_a_case_is_requested():
    """Built with no arguments, as the loader builds it, the reader takes
    its endpoint and credential from the configuration at request time."""
    vince = FakeVince(reads(ACTIVE))
    reader = VinceCaseReader(
        transport=vince.transport, clock=Clock(AS_OF[ACTIVE])
    )

    with config_override(
        VULTRON_VINCE__BASE_URL=API_URL + "/",
        VULTRON_VINCE__API_TOKEN=TOKEN,
    ):
        reading = reader.read_case(vince.vuid)

    assert reading == translate(ACTIVE)
    assert vince.requests[0].headers["Authorization"] == f"Token {TOKEN}"


@pytest.mark.spec("VSD-01-003")
@pytest.mark.spec("VSD-01-005")
def test_no_log_error_or_repr_carries_the_credential_or_case_content(
    caplog: pytest.LogCaptureFixture,
):
    case = reads(ACTIVE)["case"]
    content = [case["title"], case["summary"]]
    vince = FakeVince(
        reads(ACTIVE), respond=_failing_at("note", httpx.Response(401))
    )
    reader = _reader(vince, AS_OF[ACTIVE])

    with caplog.at_level(logging.DEBUG):
        _read(ACTIVE)
        with pytest.raises(VinceAuthError) as excinfo:
            reader.read_case(vince.vuid)

    rendered = [r.getMessage() for r in caplog.records]
    rendered += [str(excinfo.value), repr(excinfo.value), repr(reader)]
    assert any("999901" in text for text in rendered)
    for secret in (TOKEN, *content):
        assert not [text for text in rendered if secret in text]
