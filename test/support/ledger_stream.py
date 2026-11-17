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

"""Node ledgers for the live case reader's tests, read once or followed.

:func:`ledger_entry_row` and :func:`recording_rows` give ledger rows as a
node serves them.

:class:`ScriptedStream` is an HTTP transport that answers each request with
the next scripted answer: an event-stream body, one that loses its
connection (:class:`Dropping`) or goes quiet past the read timeout
(:class:`Quiet`), a status and body, or an exception.  Once the script is
spent, every request is refused as by a node that is down.  It records each
request, so a test can assert what the reader sent.  A dashboard test's
script can build a reader on it, since the transport runs in-process.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2 as httpx

from test.support.act_clock import ACT_AT
from test.support.objects import make
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.shadow.readers import VultronNodeCaseReader
from vultron.shadow.readers.vultron_node import DEFAULT_RECONNECTS

#: The node and the CASE_MANAGER a scripted reader reads.
NODE = "http://node.test/api/v2"
ACTOR = "case-actor"


def recording_rows(path: Path) -> list[dict[str, Any]]:
    """The rows of the case-ledger recording at *path*, as JSON objects."""
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def ledger_entry_row(case_id: str, log_index: int) -> dict[str, Any]:
    """A bare ledger entry of *case_id* at *log_index*, as a node sends it."""
    entry = make(
        CaseLedgerEntry,
        case_id=case_id,
        log_index=log_index,
        log_object_id=f"{case_id}/objects/{log_index}",
        semantic_type=f"test_event_{log_index}",
        received_at=ACT_AT,
        published=ACT_AT,
    )
    return entry.model_dump(mode="json", by_alias=True, exclude_none=True)


#: The event a node sends as it shuts down.
CLOSE = "event: close\ndata: \n\n"


def sse_event(row: dict[str, Any] | str, event_id: int | None = None) -> str:
    """One event carrying *row*, as JSON unless it is text already."""
    data = row if isinstance(row, str) else json.dumps(row)
    head = "" if event_id is None else f"id: {event_id}\n"
    return f"{head}data: {data}\n\n"


def sse_rows(rows: list[dict[str, Any]]) -> str:
    """One event per ledger row, each's id its log index."""
    return "".join(sse_event(row, row["logIndex"]) for row in rows)


class Dropping(httpx.SyncByteStream):
    """A response body that sends *text*, then loses the connection."""

    def __init__(self, text: str) -> None:
        self._text = text

    def __iter__(self) -> Iterator[bytes]:
        yield self._text.encode()
        raise httpx.RemoteProtocolError("connection lost")


class Quiet(httpx.SyncByteStream):
    """A response body that sends *text*, then goes quiet past the timeout."""

    def __init__(self, text: str) -> None:
        self._text = text

    def __iter__(self) -> Iterator[bytes]:
        yield self._text.encode()
        raise httpx.ReadTimeout("quiet")


#: One scripted answer: a body, a body that drops or goes quiet, a status
#: and body, or an exception the transport raises.
Answer = str | httpx.SyncByteStream | tuple[int, str] | Exception


class ScriptedStream:
    """A transport answering each request with the next scripted answer."""

    def __init__(self, *answers: Answer) -> None:
        self.requests: list[httpx.Request] = []
        self._answers = list(answers)

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self._answers:
            raise httpx.ConnectError("refused", request=request)
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, tuple):
            status, body = answer
            return httpx.Response(status, text=body)
        headers = {"Content-Type": "text/event-stream"}
        if isinstance(answer, httpx.SyncByteStream):
            return httpx.Response(200, headers=headers, stream=answer)
        return httpx.Response(200, headers=headers, text=answer)

    def reader(
        self, *, reconnects: int = DEFAULT_RECONNECTS
    ) -> VultronNodeCaseReader:
        """A live reader whose requests this script answers, with no delay."""
        return VultronNodeCaseReader(
            NODE,
            ACTOR,
            transport=httpx.MockTransport(self._answer),
            reconnects=reconnects,
            retry_delay=0,
        )
