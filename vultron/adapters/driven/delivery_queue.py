"""Delivery queue driven adapter — OX-1.1 implementation.

Implements the ``ActivityEmitter`` port (``core/ports/emitter.py``) by
delivering outbound ActivityStreams activities to recipient actor inboxes
via HTTP POST (ActivityPub convention).

Responsibilities:

- Derives each recipient's inbox URL as ``{actor_uri}/inbox/``
  (ActivityPub convention, OX-05-001).
- POSTs the serialised activity payload to each recipient inbox URL
  using ``httpx.AsyncClient`` so the delivery loop is non-blocking.
- Retries with exponential backoff on delivery failure (SYNC-05-001).
- Retry/backoff parameters are configurable; defaults are documented
  as module-level constants (SYNC-05-002).
- Delivery failures are isolated per-recipient: exhausting retries for
  one recipient is logged at ERROR level but does not abort delivery to
  other recipients.
- Idempotency (OX-06-001) is enforced at the receiving inbox endpoint
  (``POST /actors/{id}/inbox/``), not here, because each actor runs as an
  isolated process with no direct DataLayer access to other actors.

Port: ``vultron.core.ports.emitter.ActivityEmitter``
"""

import asyncio
import json
import logging

import httpx

from vultron.core.models.activity import VultronActivity
from vultron.core.ports.emitter import (  # noqa: F401 — port reference
    ActivityEmitter,
)

logger = logging.getLogger(__name__)

#: Default maximum delivery retry attempts per recipient.
#: Set to 0 to disable retries (deliver once only).
#: Spec: SYNC-05-002.
DEFAULT_MAX_RETRIES: int = 3

#: Default initial retry delay in seconds before the first retry.
#: Spec: SYNC-05-002.
DEFAULT_INITIAL_DELAY: float = 0.5

#: Default exponential backoff multiplier applied after each failed attempt.
#: The delay doubles on each retry when the default multiplier of 2.0 is used.
#: Spec: SYNC-05-002.
DEFAULT_BACKOFF_MULTIPLIER: float = 2.0

#: Default upper bound on retry delay in seconds.
#: Prevents unbounded growth of the retry interval.
#: Spec: SYNC-05-002.
DEFAULT_MAX_DELAY: float = 30.0


class DeliveryQueueAdapter:
    """``ActivityEmitter`` driven-port implementation.

    Delivers outbound activities to recipient actor inboxes via HTTP POST
    (OX-1.1).  Each recipient is attempted up to ``max_retries + 1`` times
    with exponential backoff (SYNC-05-001, SYNC-05-002).  Delivery failures
    for individual recipients after all retries are exhausted are logged at
    ERROR level but do not raise, so one failed recipient never blocks
    delivery to others.

    Args:
        max_retries: Maximum number of retry attempts after the initial
            delivery failure.  Defaults to :data:`DEFAULT_MAX_RETRIES`.
        initial_delay: Seconds to wait before the first retry.
            Defaults to :data:`DEFAULT_INITIAL_DELAY`.
        backoff_multiplier: Multiplier applied to the delay after each
            failed attempt.  Defaults to :data:`DEFAULT_BACKOFF_MULTIPLIER`.
        max_delay: Upper bound on retry delay in seconds.
            Defaults to :data:`DEFAULT_MAX_DELAY`.
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_delay: float = DEFAULT_INITIAL_DELAY,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        max_delay: float = DEFAULT_MAX_DELAY,
    ) -> None:
        self._max_retries = max_retries
        self._initial_delay = initial_delay
        self._backoff_multiplier = backoff_multiplier
        self._max_delay = max_delay

    async def emit(
        self,
        activity: VultronActivity,
        recipients: list[str],
    ) -> None:
        """Deliver *activity* to each recipient's inbox via HTTP POST.

        Derives each inbox URL as ``{actor_uri}/inbox/`` and POSTs the
        JSON-serialised activity payload using an async HTTP client.
        Per-recipient failures are retried with exponential backoff; after
        all retries are exhausted the failure is logged at ERROR level and
        delivery continues to the next recipient.

        Args:
            activity: The domain activity to deliver.  Must expose either
                ``model_dump_json(by_alias=True)`` (Pydantic) or be convertible
                via ``dict()``.
            recipients: List of recipient actor ID strings (full URIs).
        """
        activity_id = getattr(activity, "id_", None) or getattr(
            activity, "id", None
        )
        # Use model_dump_json() so Pydantic's encoder handles datetime, UUID,
        # and enum values correctly.  Passing model_dump() output to httpx's
        # json= parameter fails for any activity whose nested objects contain
        # datetime fields (e.g. VulnerabilityCase.events[].received_at).
        if hasattr(activity, "model_dump_json"):
            json_body: str = activity.model_dump_json(
                by_alias=True, exclude_none=True
            )
        else:
            json_body = json.dumps(dict(activity), default=str)

        async with httpx.AsyncClient() as client:
            for recipient_id in recipients:
                await self._deliver_with_retry(
                    client=client,
                    json_body=json_body,
                    recipient_id=recipient_id,
                    activity_id=activity_id,
                )

    async def _deliver_with_retry(
        self,
        client: httpx.AsyncClient,
        json_body: str,
        recipient_id: str,
        activity_id: str | None,
    ) -> None:
        """Deliver a single JSON payload to *recipient_id* with retry/backoff.

        Attempts delivery up to ``max_retries + 1`` times.  On each failure
        (except the last), waits *delay* seconds before retrying.  The delay
        grows by *backoff_multiplier* on each failure, capped at *max_delay*.

        Spec: SYNC-05-001, SYNC-05-002.
        """
        inbox_url = recipient_id.rstrip("/") + "/inbox/"
        delay = self._initial_delay

        for attempt in range(self._max_retries + 1):
            try:
                response = await client.post(
                    inbox_url,
                    content=json_body,
                    headers={"Content-Type": "application/json"},
                    timeout=5.0,
                )
                response.raise_for_status()
                logger.info(
                    "Delivered activity %s to %s (HTTP %s)",
                    activity_id,
                    inbox_url,
                    response.status_code,
                )
                return
            except Exception as exc:
                if attempt < self._max_retries:
                    logger.warning(
                        "Delivery attempt %d/%d failed for activity %s "
                        "to %s: %s — retrying in %.1fs",
                        attempt + 1,
                        self._max_retries + 1,
                        activity_id,
                        inbox_url,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(
                        delay * self._backoff_multiplier, self._max_delay
                    )
                else:
                    logger.error(
                        "Failed to deliver activity %s to %s after %d "
                        "attempt(s): %s",
                        activity_id,
                        inbox_url,
                        self._max_retries + 1,
                        exc,
                    )
