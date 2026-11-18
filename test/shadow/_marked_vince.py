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

"""A VINCE case reader over a synthetic case whose content holds a marker.

The committed fixture ``999901-active-embargoed`` is served by a fake VINCE
API (``httpx.MockTransport``), with :data:`CONTENT_MARKER` written into the
case's title and summary, each post's content and author, the report's vul
description and contact, each vul's description and each vendor's statement
(VSD-01-003).  No request reaches a network.
"""

from __future__ import annotations

from typing import Any

import httpx2 as httpx

from test.adapters.connectors.vince._support import (
    ACTIVE,
    AS_OF,
    COMM_URL,
    reads,
)
from test.support.case_reader import CONTENT_MARKER
from vultron.adapters.connectors.vince import VinceCaseReader
from vultron.config.vince import VinceConfig

_TOKEN = "synthetic-token-5959"  # noqa: S105 - a made-up test value

#: The VINCE case the reader serves, as the analyst enters it.
VINCE_CASE = reads(ACTIVE)["case"]["vuid"]


def _mark(text: str, marker: str) -> str:
    return f"{text} {marker}"


def marked_reads(marker: str = CONTENT_MARKER) -> dict[str, Any]:
    """The fixture's reads, with *marker* in the case's content."""
    case_reads = reads(ACTIVE)
    case = case_reads["case"]
    for key in ("title", "summary"):
        case[key] = _mark(case[key], marker)
    for post in case_reads["posts"]:
        post["content"] = _mark(post["content"], marker)
        post["author"]["name"] = _mark(post["author"]["name"], marker)
    report = case_reads["report"]
    for key in ("vul_description", "contact_name"):
        report[key] = _mark(report[key], marker)
    for vul in case_reads["vuls"]:
        vul["description"] = _mark(vul["description"], marker)
    for vendor in case_reads["vendors"]:
        vendor["statement"] = _mark(vendor["statement"], marker)
    return case_reads


def marked_vince_reader(marker: str = CONTENT_MARKER) -> VinceCaseReader:
    """A :class:`VinceCaseReader` over :func:`marked_reads`."""
    case_reads = marked_reads(marker)
    prefix = f"/vince/comm/api/case/{VINCE_CASE}/"

    def handle(request: httpx.Request) -> httpx.Response:
        read = request.url.path.removeprefix(prefix).removesuffix("/")
        body = case_reads.get(read or "case")
        if body is None:
            return httpx.Response(404, json={"detail": "Not found."})
        return httpx.Response(200, json=body)

    config = VinceConfig.model_validate(
        {"base_url": f"{COMM_URL}/api", "api_token": _TOKEN}
    )
    return VinceCaseReader(
        config,
        transport=httpx.MockTransport(handle),
        clock=lambda: AS_OF[ACTIVE],
    )


__all__ = ["VINCE_CASE", "marked_reads", "marked_vince_reader"]
