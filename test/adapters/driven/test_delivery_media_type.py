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
"""The media type ``HttpDeliveryAdapter`` posts an activity with.

Spec: HTTP-01-004.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx2 as httpx
import pytest

from vultron.adapters.driven.http_delivery import HttpDeliveryAdapter

RECIPIENT_URI = "https://example.org/actors/alice"
ACTIVITY_ID = "https://example.org/activities/act1"
BODY = json.dumps(
    {
        "id": ACTIVITY_ID,
        "type": "Announce",
        "actor": "https://example.org/actors/case-actor",
        "object": {"id": "https://example.org/objects/obj1", "type": "Note"},
    }
)

#: The two media types a Vultron inbox accepts (HTTP-01-001, HTTP-01-002),
#: as (media type, ``profile`` parameter) pairs.
ACTIVITYSTREAMS_MEDIA_TYPES = {
    ("application/activity+json", None),
    ("application/ld+json", "https://www.w3.org/ns/activitystreams"),
}


def _media_type(content_type: str) -> tuple[str, str | None]:
    """The media type and its ``profile`` parameter, normalized.

    Case, spacing and quoting do not change a media type, so a correct header
    written another way still matches.
    """
    media_type, *params = (part.strip() for part in content_type.split(";"))
    profile = None
    for param in params:
        name, _, value = param.partition("=")
        if name.strip().lower() == "profile":
            profile = value.strip().strip('"')
    return media_type.lower(), profile


@pytest.mark.spec("HTTP-01-004")
def test_delivery_posts_an_activitystreams_media_type() -> None:
    """A delivery POST names one of the two ActivityStreams media types.

    The request is caught at ``send``, after the client merges its own default
    headers in, so a header set on the client counts as well as one set on
    the call.
    """
    adapter = HttpDeliveryAdapter(max_retries=0, initial_delay=0.0)
    response = MagicMock()
    response.status_code = 202
    response.raise_for_status = MagicMock()

    with patch("httpx2.AsyncClient.send", new_callable=AsyncMock) as send:
        send.return_value = response
        asyncio.run(adapter.emit(ACTIVITY_ID, BODY, [RECIPIENT_URI]))

    # The preconditions fail with pytest.fail, not AssertionError, so a
    # delivery that stops going through ``send`` errors instead of xfailing.
    if send.call_count != 1:
        pytest.fail(
            f"expected one AsyncClient.send call, got {send.call_count}"
        )
    request = send.call_args.args[0]
    if not isinstance(request, httpx.Request):
        pytest.fail(
            f"AsyncClient.send got {type(request).__name__}, not a Request"
        )
    content_type = request.headers.get("content-type", "")
    assert _media_type(content_type) in ACTIVITYSTREAMS_MEDIA_TYPES
