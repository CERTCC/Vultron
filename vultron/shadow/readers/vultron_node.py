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

"""The live Vultron case reader: a running node's case ledger (#6530).

A Vultron case needs no translation, wherever its ledger is read from
(ADR-0191).  This reader reads it from a running node in prototype run mode,
through the node's demo case-ledger list endpoint,
``GET {node}/actors/{actor}/demo/cases/{case}/log?format=ndjson``, as the
CASE_MANAGER named by its configuration.  It returns the entries untranslated,
in log-index order, each citing itself by its ledger id, exactly as the
file reader does: both build their reading through
:func:`~vultron.shadow.readers.ledger_reading.ledger_reading`.

It sends nothing but that one ``GET`` (SHD-04-001).  It uses a plain HTTP
client, never the outbox, an activity emitter or an HTTP delivery adapter
(SHD-01-001); it follows no redirect and takes no proxy from the
environment, so every request goes to the configured node and nowhere else.
It keeps nothing between requests (SHD-01-003).

Every way the read can fail, an unreachable node, a node that does not serve
the endpoint (one not in prototype run mode), a node with no such case, or a
row that is not a valid ledger entry, raises
:class:`~vultron.errors.VultronNodeCaseReadError` naming the node and the
case (SHD-04-002, SHD-04-004).

Following a case as its ledger grows, over the event-stream endpoint, is
the dashboard's follow-up (#6531).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final
from urllib.parse import quote, urlsplit

import httpx2 as httpx

from vultron.core.models.case_reading import CaseReading, UnobservableFact
from vultron.errors import VultronNodeCaseReadError
from vultron.measure.ledger import parse_ledger_text
from vultron.shadow.readers.ledger_reading import ledger_reading

logger = logging.getLogger(__name__)

#: Seconds each network step of a read may take.
DEFAULT_READ_TIMEOUT: Final = 10.0

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
    short id matches the served id's last segment.
    """
    asked = requested.strip().rstrip("/")
    if asked.startswith(_URN_UUID) or urlsplit(asked).scheme:
        return served.rstrip("/") == asked
    return path_segment(served) == path_segment(asked)


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


class VultronNodeCaseReader:
    """A ``CaseReader`` over a running Vultron node's case ledger.

    The case id it is given is the case's id on the node, full or short.

    Args:
        node_url: The node's API root, such as
            ``http://case-actor:7999/api/v2``.
        actor_id: The CASE_MANAGER on that node whose case ledger is read,
            by its full id or its short id, such as ``case-actor``.
        transport: The HTTP transport requests go through; by default the
            network.  A test passes one that records each request.
        timeout: Seconds each network step of a read may take.

    Raises:
        ValueError: *actor_id* names no actor.
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
    ) -> None:
        self._node_url = node_url.rstrip("/")
        self._actor = path_segment(actor_id)
        self._transport = transport
        self._timeout = timeout

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

    def _refused(
        self, case_id: str, problems: list[str]
    ) -> VultronNodeCaseReadError:
        return VultronNodeCaseReadError(self._node_url, case_id, problems)

    def _fetch(self, case_id: str, path: str) -> str:
        """Send the one ``GET`` of the ledger list and return its body."""
        try:
            with httpx.Client(
                base_url=self._node_url,
                transport=self._transport,
                timeout=self._timeout,
                follow_redirects=False,
                trust_env=False,
                headers={"Accept": "application/x-ndjson"},
            ) as client:
                response = client.get(path, params={"format": "ndjson"})
        except httpx.TimeoutException as exc:
            raise self._refused(
                case_id, ["the node did not answer in time"]
            ) from exc
        except httpx.HTTPError as exc:
            raise self._refused(
                case_id, [f"the node cannot be reached ({type(exc).__name__})"]
            ) from exc
        logger.debug(
            "Vultron node %s: ledger of case %s answered %d",
            self._node_url,
            case_id,
            response.status_code,
        )
        if response.status_code == 404:
            raise self._refused(case_id, [_not_found(response)])
        if response.status_code != 200:
            raise self._refused(
                case_id,
                [f"the node answered HTTP {response.status_code}"],
            )
        return response.text

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
        served_by = Path(urlsplit(self._node_url).path + path)
        ledger = parse_ledger_text(text, served_by)
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
        logger.info(
            "Read case %s: %d ledger entries from the Vultron node at %s",
            reading.ledger[0].case_id,
            len(reading.ledger),
            self._node_url,
        )
        return reading


__all__ = ["DEFAULT_READ_TIMEOUT", "VultronNodeCaseReader", "path_segment"]
