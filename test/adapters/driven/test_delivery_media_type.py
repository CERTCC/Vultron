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

#: The two media types a Vultron inbox accepts (HTTP-01-001, HTTP-01-002).
ACTIVITYSTREAMS_MEDIA_TYPES = {
    "application/activity+json",
    'application/ld+json; profile="https://www.w3.org/ns/activitystreams"',
}


@pytest.mark.spec("HTTP-01-004")
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "HTTP-01-004: the delivery adapter posts with Content-Type "
        "application/json, not an ActivityStreams media type. "
        "Tracked by #3660."
    ),
)
def test_delivery_posts_an_activitystreams_media_type() -> None:
    """A delivery POST names one of the two ActivityStreams media types."""
    adapter = HttpDeliveryAdapter(max_retries=0, initial_delay=0.0)
    response = MagicMock()
    response.status_code = 202
    response.raise_for_status = MagicMock()

    with patch("httpx2.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        asyncio.run(adapter.emit(ACTIVITY_ID, BODY, [RECIPIENT_URI]))

    post.assert_called_once()
    content_type = post.call_args.kwargs["headers"]["Content-Type"]
    assert content_type in ACTIVITYSTREAMS_MEDIA_TYPES
