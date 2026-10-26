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
"""The HTTP object fetcher: URLs, retries and terminal answers (AKM-05-008)."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import httpx2 as httpx
import pytest

from vultron.adapters.driven.http_object_fetch import (
    REQUESTER_HEADER,
    HttpObjectFetcher,
    fetch_url,
)
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchUse,
    ObjectReference,
)

_HOST = "https://example.org/api/v2/actors/case-actor"
_CASE = "https://example.org/cases/c-1"
_OBJECT = "urn:uuid:embargo-1"
_REQUESTER = "https://example.org/actors/vendor"

_CASE_REF = ObjectReference(
    object_id=_OBJECT,
    source=ObjectFetchSource.CASE_HOST,
    host_actor_id=_HOST,
    case_id=_CASE,
    use=ObjectFetchUse.STORE,
)


def _response(status: int, body: Any = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json = MagicMock(return_value=body)
    if status >= 400:
        request = httpx.Request("GET", _HOST)
        error = httpx.HTTPStatusError(
            "error", request=request, response=httpx.Response(status)
        )
        response.raise_for_status = MagicMock(side_effect=error)
    else:
        response.raise_for_status = MagicMock()
    return response


def _fetch(
    fetcher: HttpObjectFetcher, answers: list[Any]
) -> tuple[Any, AsyncMock]:
    with (
        patch("httpx2.AsyncClient.get", new_callable=AsyncMock) as get,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        get.side_effect = answers
        result = asyncio.run(fetcher.fetch(_CASE_REF, _REQUESTER))
    return result, get


class TestFetchUrl:
    def test_a_case_object_is_read_from_the_case_hosts_case_object_route(
        self,
    ):
        url = urlsplit(fetch_url(_CASE_REF))

        assert (
            f"{url.scheme}://{url.netloc}{url.path}" == f"{_HOST}/case-object"
        )
        assert parse_qs(url.query) == {
            "case_id": [_CASE],
            "object_id": [_OBJECT],
        }

    def test_a_profile_is_read_from_the_actors_profile_route(self):
        reference = ObjectReference(
            object_id=_REQUESTER,
            source=ObjectFetchSource.ACTOR_PROFILE,
            host_actor_id=f"{_REQUESTER}/",
            use=ObjectFetchUse.HAND_OFF,
        )

        assert fetch_url(reference) == f"{_REQUESTER}/profile"


class TestHttpObjectFetcher:
    @pytest.mark.spec("AKM-05-003")
    @pytest.mark.spec("AKM-05-004")
    def test_a_fetch_answers_with_the_object_and_names_its_requester(self):
        body = {"type": "EmbargoEvent", "id": _OBJECT}

        result, get = _fetch(HttpObjectFetcher(), [_response(200, body)])

        assert result.body == body
        assert result.failure is None
        assert result.attempts == 1
        assert get.call_args.kwargs["headers"][REQUESTER_HEADER] == _REQUESTER

    @pytest.mark.spec("AKM-05-008")
    def test_a_4xx_ends_the_fetch_at_once(self):
        result, get = _fetch(
            HttpObjectFetcher(max_attempts=3), [_response(403)]
        )

        assert result.body is None
        assert result.failure is not None
        assert "403" in result.failure
        assert result.attempts == 1
        get.assert_called_once()

    @pytest.mark.spec("AKM-05-008")
    def test_a_5xx_is_retried_up_to_the_cap(self):
        result, get = _fetch(
            HttpObjectFetcher(max_attempts=3), [_response(503)] * 3
        )

        assert result.body is None
        assert result.failure is not None
        assert "503" in result.failure
        assert result.attempts == 3
        assert get.call_count == 3

    @pytest.mark.spec("AKM-05-008")
    def test_a_network_error_is_retried_and_may_then_succeed(self):
        body = {"type": "EmbargoEvent", "id": _OBJECT}
        refused = httpx.ConnectError("connection refused")

        result, get = _fetch(
            HttpObjectFetcher(max_attempts=3), [refused, _response(200, body)]
        )

        assert result.body == body
        assert result.attempts == 2
        assert get.call_count == 2

    @pytest.mark.spec("AKM-05-008")
    def test_a_body_that_is_not_a_json_object_fails_the_fetch(self):
        result, get = _fetch(HttpObjectFetcher(), [_response(200, ["x"])])

        assert result.body is None
        assert result.failure is not None
        assert "not an object" in result.failure
        get.assert_called_once()

    @pytest.mark.spec("AKM-05-008")
    def test_a_body_that_is_not_json_fails_the_fetch_at_once(self):
        response = _response(200)
        response.json.side_effect = ValueError("Expecting value")

        result, get = _fetch(HttpObjectFetcher(max_attempts=3), [response])

        assert result.body is None
        assert result.failure is not None
        assert "no JSON" in result.failure
        get.assert_called_once()

    def test_at_least_one_attempt_is_required(self):
        with pytest.raises(ValueError, match="at least 1"):
            HttpObjectFetcher(max_attempts=0)


class TestAnyFailureIsAResult:
    @pytest.mark.spec("AKM-05-008")
    def test_a_url_the_client_refuses_is_retried_then_a_failed_result(self):
        """Not only HTTP errors: whatever an attempt raises ends in a result."""
        refused = httpx.InvalidURL("Invalid port: '99999'")

        result, get = _fetch(HttpObjectFetcher(max_attempts=2), [refused] * 2)

        assert result.body is None
        assert result.failure is not None
        assert "Invalid port" in result.failure
        assert result.attempts == 2
        assert get.call_count == 2
