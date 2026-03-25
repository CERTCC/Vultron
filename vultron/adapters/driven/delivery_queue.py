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

"""Delivery queue driven adapter — OX-1.1 implementation.

Implements the ``ActivityEmitter`` port (``core/ports/emitter.py``) by
delivering outbound ActivityStreams activities to recipient actor inboxes
via HTTP POST (ActivityPub convention).

Responsibilities:

- Derives each recipient's inbox URL as ``{actor_uri}/inbox/``
  (ActivityPub convention, OX-05-001).
- POSTs the serialised activity payload to each recipient inbox URL
  using synchronous ``httpx`` (prototype simplicity).
- Delivery failures are isolated per-recipient: a failed POST is logged
  at ERROR level but does not abort delivery to other recipients.
- Idempotency (OX-06-001) is enforced at the receiving inbox endpoint
  (``POST /actors/{id}/inbox/``), not here, because each actor runs as an
  isolated process with no direct DataLayer access to other actors.

Port: ``vultron.core.ports.emitter.ActivityEmitter``
"""

import logging

import httpx

from vultron.core.models.activity import VultronActivity
from vultron.core.ports.emitter import (  # noqa: F401 — port reference
    ActivityEmitter,
)

logger = logging.getLogger(__name__)


class DeliveryQueueAdapter:
    """``ActivityEmitter`` driven-port implementation.

    Delivers outbound activities to recipient actor inboxes via HTTP POST
    (OX-1.1).  Delivery failures for individual recipients are logged at
    ERROR level but do not raise, so one failed recipient never blocks
    delivery to others.
    """

    def emit(
        self,
        activity: VultronActivity,
        recipients: list[str],
    ) -> None:
        """Deliver *activity* to each recipient's inbox via HTTP POST.

        Derives each inbox URL as ``{actor_uri}/inbox/`` and POSTs the
        JSON-serialised activity payload.  Per-recipient failures are logged
        and swallowed so that one unreachable actor does not prevent delivery
        to the rest.

        Args:
            activity: The domain activity to deliver.  Must expose either
                ``model_dump(by_alias=True)`` (Pydantic) or be convertible
                via ``dict()``.
            recipients: List of recipient actor ID strings (full URIs).
        """
        activity_id = getattr(activity, "as_id", None) or getattr(
            activity, "id", None
        )
        if hasattr(activity, "model_dump"):
            payload = activity.model_dump(by_alias=True, exclude_none=True)
        else:
            payload = dict(activity)

        for recipient_id in recipients:
            inbox_url = recipient_id.rstrip("/") + "/inbox/"
            try:
                response = httpx.post(inbox_url, json=payload, timeout=5.0)
                response.raise_for_status()
                logger.info(
                    "Delivered activity %s to %s (HTTP %s)",
                    activity_id,
                    inbox_url,
                    response.status_code,
                )
            except Exception as exc:
                logger.error(
                    "Failed to deliver activity %s to %s: %s",
                    activity_id,
                    inbox_url,
                    exc,
                )
