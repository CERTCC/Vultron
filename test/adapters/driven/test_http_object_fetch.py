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
import json
import subprocess
import sys
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import httpx2 as httpx
import pytest

from vultron.adapters.driven import http_object_fetch
from vultron.adapters.driven.http_object_fetch import (
    REQUESTER_HEADER,
    HttpObjectFetcher,
    default_object_fetcher,
    fetch_url,
    parse_fetched_object,
)
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchUse,
    ObjectReference,
)
from vultron.errors import VultronValidationError

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


def _response(
    status: int, body: Any = None, content: bytes | None = None
) -> MagicMock:
    """A streamed response: the async context ``client.stream`` opens."""
    response = MagicMock()
    response.__aenter__.return_value = response
    response.status_code = status
    raw = json.dumps(body).encode() if content is None else content

    async def _chunks() -> AsyncIterator[bytes]:
        for start in range(0, len(raw), 4):
            yield raw[start : start + 4]

    response.aiter_bytes = _chunks
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
) -> tuple[Any, MagicMock]:
    with (
        patch("httpx2.AsyncClient.stream") as get,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        get.side_effect = answers
        result = asyncio.run(fetcher.fetch(_CASE_REF, _REQUESTER))
    return result, get


class TestFetchUrl:
    def test_a_case_object_is_read_from_the_case_hosts_objects_route(
        self,
    ):
        """The case goes in the path by its surrogate key and the object as a
        query parameter, since either id may carry slashes."""
        url = urlsplit(fetch_url(_CASE_REF))

        assert (
            f"{url.scheme}://{url.netloc}{url.path}"
            == f"{_HOST}/cases/c-1/objects"
        )
        assert parse_qs(url.query) == {"object_id": [_OBJECT]}

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

    @pytest.mark.spec("AKM-05-013")
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
        response = _response(200, content=b"not json")

        result, get = _fetch(HttpObjectFetcher(max_attempts=3), [response])

        assert result.body is None
        assert result.failure is not None
        assert "no JSON" in result.failure
        get.assert_called_once()

    def test_a_body_over_the_byte_limit_ends_the_fetch_at_once(self):
        body = {"type": "EmbargoEvent", "id": _OBJECT, "name": "x" * 100}

        result, get = _fetch(
            HttpObjectFetcher(max_attempts=3, max_body_bytes=64),
            [_response(200, body)],
        )

        assert result.body is None
        assert result.failure is not None
        assert "over 64 bytes" in result.failure
        get.assert_called_once()

    def test_a_body_within_the_byte_limit_is_read(self):
        body = {"type": "EmbargoEvent", "id": _OBJECT}

        result, _ = _fetch(
            HttpObjectFetcher(max_body_bytes=1024), [_response(200, body)]
        )

        assert result.body == body

    def test_the_timeout_bounds_the_whole_attempt(self):
        """A peer that sends its body slowly still ends the attempt."""
        response = _response(200, {"type": "EmbargoEvent"})

        async def _slow() -> AsyncIterator[bytes]:
            yield b"{"
            await asyncio.Event().wait()  # never set: a peer gone quiet
            yield b"}"  # pragma: no cover

        response.aiter_bytes = _slow
        fetcher = HttpObjectFetcher(max_attempts=1, timeout=0.05)

        with patch("httpx2.AsyncClient.stream", side_effect=[response]):
            result = asyncio.run(fetcher.fetch(_CASE_REF, _REQUESTER))

        assert result.body is None
        assert result.failure is not None
        assert "TimeoutError" in result.failure

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


class TestTheDefaultFetcher:
    def test_it_takes_its_limits_from_the_config(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            http_object_fetch,
            "get_config",
            lambda: SimpleNamespace(
                max_object_fetch_attempts=7, object_fetch_timeout_seconds=1.5
            ),
        )

        fetcher = default_object_fetcher()

        assert fetcher._max_attempts == 7
        assert fetcher._timeout == 1.5


class TestParseFetchedObject:
    @pytest.mark.parametrize(
        "body, match",
        [
            ({"id": "urn:uuid:x"}, "names no type"),
            ({"type": "NoSuchType", "id": "urn:uuid:x"}, "not a valid"),
        ],
        ids=["untyped", "unknown-type"],
    )
    def test_a_body_the_vocabulary_cannot_type_is_refused(
        self, body: dict[str, Any], match: str
    ):
        with pytest.raises(VultronValidationError, match=match):
            parse_fetched_object(body, "urn:uuid:x")

    def test_it_types_an_actor_profile_with_nothing_else_imported(self):
        """The module loads the vocabulary it types by, whoever imports it.

        Run in a fresh interpreter: in this process other imports have
        already filled the registry.
        """
        script = (
            "from vultron.adapters.driven.http_object_fetch import"
            " parse_fetched_object\n"
            "actor = 'https://example.org/actors/vendor'\n"
            "parsed = parse_fetched_object("
            "{'type': 'Person', 'id': actor}, actor)\n"
            "print(type(parsed).__name__)\n"
        )

        run = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "VultronPerson"
