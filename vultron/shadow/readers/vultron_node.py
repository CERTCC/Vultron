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

"""The live Vultron case reader: a running node's case ledger (#6530, #6531).

A Vultron case needs no translation, wherever its ledger is read from
(ADR-0191).  This reader reads it from a running node in prototype run mode,
as the CASE_MANAGER named by its configuration, through one of the node's
two demo case-ledger endpoints:

* :meth:`~VultronNodeCaseReader.read_case` reads the case once, through the
  list endpoint,
  ``GET {node}/actors/{actor}/demo/cases/{case}/log?format=ndjson``.
* :meth:`~VultronNodeCaseReader.follow_case` follows the case as its ledger
  grows, through the event-stream endpoint,
  ``GET {node}/actors/{actor}/demo/cases/{case}/log/stream``.  The node
  replays the stored entries, then pushes each new one; each entry received
  yields the case's whole reading again, built from every entry so far.  A
  dropped connection is resumed with ``Last-Event-ID``, so the node sends
  only the entries after the last one received, and the follow ends when
  the node sends ``event: close``.

Either way it returns the entries untranslated, in log-index order, each
citing itself by its ledger id, exactly as the file reader does: both build
their reading through
:func:`~vultron.shadow.readers.ledger_reading.ledger_reading`.

It sends nothing but a ``GET`` of one of those endpoints (SHD-04-001).  It
uses a plain HTTP client, never the outbox, an activity emitter or an HTTP
delivery adapter (SHD-01-001); it follows no redirect and takes no proxy
from the environment, so every request goes to the configured node and
nowhere else.  A followed case is held in memory while it is followed, and
nothing of it is written anywhere (SHD-01-003).

Every way the read can fail, an unreachable node, a node that does not serve
the endpoint (one not in prototype run mode), a node with no such case, or a
row that is not a valid ledger entry, is a
:class:`~vultron.errors.VultronNodeCaseReadError` naming the node and the
case (SHD-04-002, SHD-04-004): ``read_case`` raises it, and ``follow_case``
yields it in place of the reading it refuses.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from urllib.parse import quote, urlsplit

import httpx2 as httpx

from vultron.core.models.case_reading import CaseReading, UnobservableFact
from vultron.errors import VultronNodeCaseReadError
from vultron.measure.ledger import (
    LedgerFile,
    LedgerRow,
    UnusableRow,
    ledger_from_rows,
    parse_ledger_row,
    parse_ledger_text,
)
from vultron.shadow.readers.event_stream import MESSAGE, server_sent_events
from vultron.shadow.readers.following import FollowedReading
from vultron.shadow.readers.ledger_reading import ledger_reading

logger = logging.getLogger(__name__)

#: Seconds each network step of a read may take.  A followed stream that
#: sends nothing this long, not even the node's keepalive comment, is
#: reconnected.
DEFAULT_READ_TIMEOUT: Final = 10.0

#: How many times in a row a follow tries to reconnect to a node it has
#: lost before it ends.
DEFAULT_RECONNECTS: Final = 3

#: Seconds a follow waits before it reconnects to a node it has lost.
DEFAULT_RETRY_DELAY: Final = 1.0

#: The event a node sends as it shuts down, ending the stream.
CLOSE_EVENT: Final = "close"

#: The ``detail`` the node's ledger endpoint answers a 404 with when it holds
#: no such case.  Any other 404 means the route itself is absent: the node
#: is not in prototype run mode, or the URL does not name a node's API root.
_CASE_NOT_FOUND_DETAIL: Final = "Case not found."

_URN_UUID: Final = "urn:uuid:"


def path_segment(identifier: str) -> str:
    """The one URL path segment that names *identifier* on its node.

    A node routes an actor or a case by the last segment of its id (a
    ``urn:uuid:`` id by its UUID), so a full id and a short one name the
    same thing.  The segment is percent-encoded whole, so no character of
    an id can add a path segment, a query or a fragment to the request.

    Raises:
        ValueError: *identifier* has no segment, its segment is ``.`` or
            ``..``, which a URL resolves to another path, or it carries a
            query or a fragment, which would be dropped and so read another
            case or actor than the one named.
    """
    text = identifier.strip()
    if text.startswith(_URN_UUID):
        segment = text[len(_URN_UUID) :]
    else:
        parts = urlsplit(text)
        if parts.query or parts.fragment or "?" in text or "#" in text:
            raise ValueError(
                f"{identifier!r} names no case or actor: it carries a query"
                " or a fragment"
            )
        segment = parts.path.rstrip("/").rpartition("/")[2]
    if segment in ("", ".", ".."):
        raise ValueError(f"{identifier!r} names no case or actor")
    return quote(segment, safe="")


def _names(requested: str, served: str) -> bool:
    """Whether *served*, a case id the node answered with, is *requested*.

    A full id must match whole, apart from a trailing slash, so a case of
    another node with the same last segment is not read as this one; a
    short id matches the served id's last segment, and a served id that
    names no case matches nothing.
    """
    asked = requested.strip().rstrip("/")
    if asked.startswith(_URN_UUID) or urlsplit(asked).scheme:
        return served.rstrip("/") == asked
    try:
        served_segment = path_segment(served)
    except ValueError:
        # A served id with no segment, or with a query or a fragment, names
        # no case, so it cannot be the one asked for.
        return False
    return served_segment == path_segment(asked)


def _not_found(response: httpx.Response) -> str:
    """Why the node answered 404: no such case, or no such endpoint."""
    try:
        detail = response.json().get("detail")
    except ValueError, AttributeError:
        detail = None
    if detail == _CASE_NOT_FOUND_DETAIL:
        return "the node holds no such case (HTTP 404)"
    return (
        "the node does not serve the case ledger endpoint (HTTP 404); it"
        " serves it only in prototype run mode"
    )


def _answer_problem(response: httpx.Response) -> str:
    """Why the node's answer, any but an HTTP 200, is no ledger."""
    if response.status_code == 404:
        return _not_found(response)
    return f"the node answered HTTP {response.status_code}"


def _transport_problem(exc: httpx.HTTPError) -> str:
    """Why a request to the node got no answer."""
    if isinstance(exc, httpx.TimeoutException):
        return "the node did not answer in time"
    return f"the node cannot be reached ({type(exc).__name__})"


def _beating(lines: Iterator[str], beat: Callable[[], None]) -> Iterator[str]:
    """*lines*, calling *beat* at each comment, a quiet node's keepalive."""
    for line in lines:
        if line.startswith(":"):
            beat()
        yield line


@dataclass
class _Follow:
    """What one follow of a case has received, across its connections.

    Attributes:
        case_id: The case followed, as it was named.
        served_by: The stream endpoint's path, describing each bad entry.
        rows: Every entry received, parsed, in the order it arrived.
        last_event_id: The last event id received, sent back on reconnect.
        losses: Connections lost in a row since the node last sent an
            event or a keepalive.
    """

    case_id: str
    served_by: Path
    rows: list[LedgerRow | UnusableRow] = field(default_factory=list)
    last_event_id: str | None = None
    losses: int = 0


class VultronNodeCaseReader:
    """A ``CaseReader`` over a running Vultron node's case ledger.

    The case id it is given is the case's id on the node, full or short.
    Besides reading a case once, it can follow one as its ledger grows
    (:class:`~vultron.shadow.readers.following.CaseFollower`).

    Args:
        node_url: The node's API root, such as
            ``http://case-actor:7999/api/v2``.
        actor_id: The CASE_MANAGER on that node whose case ledger is read,
            by its full id or its short id, such as ``case-actor``.
        transport: The HTTP transport requests go through; by default the
            network.  A test passes one that records each request.
        timeout: Seconds each network step of a read may take.  A followed
            stream that sends nothing for this long is reconnected.
        reconnects: How many times in a row a follow tries to reconnect to
            a node it has lost before it ends.
        retry_delay: Seconds a follow waits before each such try.

    Raises:
        ValueError: *actor_id* names no actor, or *reconnects* or
            *retry_delay* is negative.
    """

    name = "vultron-node"
    #: A Vultron ledger records every act the protocol defines, so nothing
    #: is declared unobservable (CRD-02-004).
    unobservable: tuple[UnobservableFact, ...] = ()

    def __init__(
        self,
        node_url: str,
        actor_id: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_READ_TIMEOUT,
        reconnects: int = DEFAULT_RECONNECTS,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        if reconnects < 0 or retry_delay < 0:
            raise ValueError("reconnects and retry_delay must not be negative")
        self._node_url = node_url.rstrip("/")
        self._actor = path_segment(actor_id)
        self._transport = transport
        self._timeout = timeout
        self._reconnects = reconnects
        self._retry_delay = retry_delay

    @property
    def node_url(self) -> str:
        """The node's API root every request goes to."""
        return self._node_url

    def _log_path(self, case_id: str) -> str:
        """The ledger list endpoint of *case_id*, relative to the API root."""
        try:
            case = path_segment(case_id)
        except ValueError as exc:
            raise self._refused(case_id, [str(exc)]) from exc
        return f"/actors/{self._actor}/demo/cases/{case}/log"

    def _served_by(self, path: str) -> Path:
        """The endpoint path a bad row is described by, on the node."""
        return Path(urlsplit(self._node_url).path + path)

    def _refused(
        self, case_id: str, problems: list[str]
    ) -> VultronNodeCaseReadError:
        return VultronNodeCaseReadError(self._node_url, case_id, problems)

    def _client(self, accept: str) -> httpx.Client:
        """A client that sends only to the node, accepting *accept*."""
        return httpx.Client(
            base_url=self._node_url,
            transport=self._transport,
            timeout=self._timeout,
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": accept},
        )

    def _fetch(self, case_id: str, path: str) -> str:
        """Send the one ``GET`` of the ledger list and return its body."""
        try:
            with self._client("application/x-ndjson") as client:
                response = client.get(path, params={"format": "ndjson"})
        except httpx.HTTPError as exc:
            raise self._refused(case_id, [_transport_problem(exc)]) from exc
        logger.debug(
            "Vultron node %s: ledger of case %s answered %d",
            self._node_url,
            case_id,
            response.status_code,
        )
        if response.status_code != 200:
            raise self._refused(case_id, [_answer_problem(response)])
        return response.text

    def _accepted(self, case_id: str, ledger: LedgerFile) -> CaseReading:
        """The reading *ledger* makes for *case_id*, or the refusal.

        Raises:
            VultronNodeCaseReadError: A row is not a valid ledger entry,
                the entries are not one case's ledger in log-index order,
                there is none, or they are another case's ledger.
        """
        reading = ledger_reading(
            ledger,
            unobservable=self.unobservable,
            refuse=lambda problems: self._refused(case_id, problems),
        )
        served = reading.ledger[0].case_id
        if not _names(case_id, served):
            raise self._refused(
                case_id,
                [f"the node answered with the ledger of case {served}"],
            )
        return reading

    def read_case(self, case_id: str) -> CaseReading:
        """Read the case ledger of *case_id* from the node.

        Raises:
            VultronNodeCaseReadError: *case_id* names no case, the node
                cannot be reached, does not serve the ledger endpoint, holds
                no such case or no entry for it, sends a row that is not a
                valid ledger entry or entries that are not one case's ledger
                in log-index order, or answers with another case's ledger.
                The error names the node and the case and carries every
                problem found.
        """
        path = self._log_path(case_id)
        text = self._fetch(case_id, path)
        # Each bad row is described by the path of the endpoint that served
        # it, on the node the error names.
        reading = self._accepted(
            case_id, parse_ledger_text(text, self._served_by(path))
        )
        logger.info(
            "Read case %s: %d ledger entries from the Vultron node at %s",
            reading.ledger[0].case_id,
            len(reading.ledger),
            self._node_url,
        )
        return reading

    def follow_case(
        self,
        case_id: str,
        *,
        heartbeat: Callable[[], None] | None = None,
    ) -> Generator[FollowedReading]:
        """Follow the case ledger of *case_id* on the node as it grows.

        Sends a ``GET`` of the case's ledger event-stream endpoint and, for
        each entry the node sends, yields the case's whole reading built
        from every entry received so far, in log-index order (SHD-04-003).
        Once an entry is not a valid ledger entry, each reading after it is
        refused whole: the refusal is yielded in its place, naming the
        entry by its place in the stream, ``… /log/stream line N`` for the
        Nth entry (SHD-04-004).

        A quiet node sends a keepalive comment, so a quiet case keeps its
        connection.  A stream that drops, or that sends nothing at all for
        the reader's timeout, is reconnected with ``Last-Event-ID`` set to
        the last event id received, so the node sends only the entries
        after it (SHD-04-001).
        The follow ends when the node sends ``event: close``, when it
        answers anything but the stream (no such case, no such endpoint),
        or when it cannot be reached again after the reader's reconnect
        tries; the last two yield the refusal saying why, as the last item.

        Args:
            case_id: The case's id on the node, full or short.
            heartbeat: Called at each keepalive comment the node sends
                and before each reconnect, so a caller waiting on a quiet
                case can stop the follow.
        """
        try:
            path = self._log_path(case_id) + "/stream"
        except VultronNodeCaseReadError as exc:
            yield exc
            return
        follow = _Follow(case_id=case_id, served_by=self._served_by(path))
        logger.info(
            "Following case %s on the Vultron node at %s",
            case_id,
            self._node_url,
        )
        while True:
            lost = yield from self._stream(path, follow, heartbeat)
            if lost is None:
                return
            if lost:
                follow.losses += 1
                if follow.losses > self._reconnects:
                    logger.warning(
                        "Stopped following case %s: lost the Vultron node at"
                        " %s (%s)",
                        case_id,
                        self._node_url,
                        lost,
                    )
                    yield self._refused(case_id, [lost])
                    return
                logger.warning(
                    "Lost the stream of case %s on the Vultron node at %s"
                    " (%s); reconnecting, try %d of %d",
                    case_id,
                    self._node_url,
                    lost,
                    follow.losses,
                    self._reconnects,
                )
            else:
                logger.debug(
                    "The stream of case %s on the Vultron node at %s went"
                    " quiet; reconnecting",
                    case_id,
                    self._node_url,
                )
            if heartbeat is not None:
                heartbeat()
            if lost:
                time.sleep(self._retry_delay)

    def _stream(
        self,
        path: str,
        follow: _Follow,
        heartbeat: Callable[[], None] | None,
    ) -> Generator[FollowedReading, None, str | None]:
        """Read one connection to the event stream, yielding each reading.

        Returns:
            ``None`` when the follow is over: the node closed the stream,
            or answered with something other than a stream, whose refusal
            was yielded.  Otherwise why the connection was lost, or ``""``
            when a stream that answered went quiet for the timeout.
        """
        headers = (
            {"Last-Event-ID": follow.last_event_id}
            if follow.last_event_id
            else {}
        )
        answered = False
        try:
            with (
                self._client("text/event-stream") as client,
                client.stream("GET", path, headers=headers) as response,
            ):
                if response.status_code != 200:
                    response.read()
                    yield self._refused(
                        follow.case_id, [_answer_problem(response)]
                    )
                    return None
                answered = True

                def beat() -> None:
                    # A keepalive shows the node is still there.
                    follow.losses = 0
                    if heartbeat is not None:
                        heartbeat()

                lines = _beating(response.iter_lines(), beat)
                for event in server_sent_events(lines):
                    follow.losses = 0
                    # Each connection's parser starts with no id, so an
                    # event without one keeps the follow's resume point.
                    if event.last_event_id is not None:
                        follow.last_event_id = event.last_event_id
                    if event.type == CLOSE_EVENT:
                        logger.info(
                            "Stopped following case %s: the Vultron node at"
                            " %s closed the stream",
                            follow.case_id,
                            self._node_url,
                        )
                        return None
                    if event.type == MESSAGE:
                        yield self._followed(follow, event.data)
        except httpx.ReadTimeout as exc:
            # A stream that answered and then went quiet, from a node that
            # sends no keepalive, is a live case with no new entry: it is
            # reconnected, not counted lost.
            return "" if answered else _transport_problem(exc)
        except httpx.HTTPError as exc:
            return _transport_problem(exc)
        return "the node ended the stream without closing it"

    def _followed(self, follow: _Follow, data: str) -> FollowedReading:
        """Add the entry *data* carries; the reading every entry makes."""
        follow.rows.append(
            parse_ledger_row(data, follow.served_by, len(follow.rows) + 1)
        )
        try:
            reading = self._accepted(
                follow.case_id, ledger_from_rows(follow.served_by, follow.rows)
            )
        except VultronNodeCaseReadError as exc:
            logger.warning(
                "Refused the reading of case %s after %d streamed entries",
                follow.case_id,
                len(follow.rows),
            )
            return exc
        logger.debug(
            "Case %s: %d ledger entries streamed from the Vultron node at %s",
            follow.case_id,
            len(follow.rows),
            self._node_url,
        )
        return reading


__all__ = [
    "CLOSE_EVENT",
    "DEFAULT_READ_TIMEOUT",
    "DEFAULT_RECONNECTS",
    "DEFAULT_RETRY_DELAY",
    "VultronNodeCaseReader",
    "path_segment",
]
