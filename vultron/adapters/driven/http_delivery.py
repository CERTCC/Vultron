"""HTTP delivery driven adapter — sole inter-actor delivery path (ADR-0042).

Implements the ``ActivityEmitter`` port (``core/ports/emitter.py``) by
delivering outbound ActivityStreams activities to recipient actor inboxes
via HTTP POST (ActivityPub convention, OX-12-001).

Every recipient — co-located or remote — is treated as if it were remote.
There is no in-process shortcut; CaseActor ``cc:``-to-self loopback copies
are delivered over HTTP loopback exactly like any other recipient.

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
- After all recipients have been attempted, if any failed,
  ``DeliveryError`` is raised so ``outbox_handler`` can requeue the
  activity for a future drain pass (OX-05-002).
- Idempotency (OX-06-001) is enforced at the receiving inbox endpoint
  (``POST /actors/{id}/inbox/``), not here, because each actor runs as an
  isolated process with no direct DataLayer access to other actors.

Port: ``vultron.core.ports.emitter.ActivityEmitter``
"""

import asyncio
import json
import logging
import random

import httpx2 as httpx

from vultron.core.models.activity import VultronActivity
from vultron.core.ports.emitter import (  # noqa: F401 — port reference
    ActivityEmitter,
)


class DeliveryError(RuntimeError):
    """Raised by ``HttpDeliveryAdapter.emit`` when one or more recipients
    could not be reached after all retry attempts.

    ``outbox_handler`` catches this and requeues the activity for a future
    drain pass (OX-05-002).
    """

    def __init__(self, failed: list[str], activity_id: str | None) -> None:
        self.failed_recipients = failed
        super().__init__(
            f"Delivery failed for activity {activity_id!r} "
            f"to {len(failed)} recipient(s): {failed}"
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

#: Default HTTP request timeout in seconds (SYNC-05-004).
DEFAULT_DELIVERY_TIMEOUT: float = 30.0


class HttpDeliveryAdapter:
    """``ActivityEmitter`` driven-port implementation (ADR-0042, OX-12-001).

    Delivers outbound activities to recipient actor inboxes via HTTP POST.
    Every recipient is treated as remote — there is no co-located shortcut.
    Each recipient is attempted up to ``max_retries + 1`` times with
    exponential backoff (SYNC-05-001, SYNC-05-002).  Delivery failures for
    individual recipients are isolated: one failing recipient never blocks
    delivery to others.  After all recipients are attempted, if any failed,
    :class:`DeliveryError` is raised so ``outbox_handler`` can requeue the
    activity for retry (OX-05-002).

    Args:
        max_retries: Maximum number of retry attempts after the initial
            delivery failure.  Defaults to :data:`DEFAULT_MAX_RETRIES`.
        initial_delay: Seconds to wait before the first retry.
            Defaults to :data:`DEFAULT_INITIAL_DELAY`.
        backoff_multiplier: Multiplier applied to the delay after each
            failed attempt.  Defaults to :data:`DEFAULT_BACKOFF_MULTIPLIER`.
        max_delay: Upper bound on retry delay in seconds.
            Defaults to :data:`DEFAULT_MAX_DELAY`.
        timeout: HTTP request timeout in seconds passed to
            ``httpx.AsyncClient.post``.
            Defaults to :data:`DEFAULT_DELIVERY_TIMEOUT`.
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_delay: float = DEFAULT_INITIAL_DELAY,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        max_delay: float = DEFAULT_MAX_DELAY,
        timeout: float = DEFAULT_DELIVERY_TIMEOUT,
    ) -> None:
        self._max_retries = max_retries
        self._initial_delay = initial_delay
        self._backoff_multiplier = backoff_multiplier
        self._max_delay = max_delay
        self._timeout = timeout

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
        delivery continues to the next recipient.  After all recipients have
        been attempted, :class:`DeliveryError` is raised if any failed so
        that ``outbox_handler`` can requeue the activity (OX-05-002).

        Args:
            activity: The domain activity to deliver.  Must expose either
                ``model_dump_json(by_alias=True)`` (Pydantic) or be convertible
                via ``dict()``.
            recipients: List of recipient actor ID strings (full URIs).

        Raises:
            DeliveryError: If any recipient could not be reached after all
                retry attempts (OX-12-001).
        """
        activity_id = getattr(activity, "id_", None) or getattr(
            activity, "id", None
        )
        # Use model_dump_json() so Pydantic's encoder handles datetime, UUID,
        # and enum values correctly.  Passing model_dump() output to httpx's
        # json= parameter fails for any activity whose nested objects contain
        # datetime fields (e.g. VulnerabilityCase.events[].received_at).
        if hasattr(activity, "model_dump_json"):
            # serialize_as_any=True preserves nested-object subtype fields on
            # the wire (e.g. inline CaseLedgerEntry fields) — SYNC-02-004,
            # SYNC-13-004.
            json_body: str = activity.model_dump_json(
                by_alias=True, exclude_none=True, serialize_as_any=True
            )
        else:
            json_body = json.dumps(dict(activity), default=str)

        failed: list[str] = []
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=5)
        async with httpx.AsyncClient(limits=limits) as client:
            for recipient_id in recipients:
                try:
                    await self._deliver_with_retry(
                        client=client,
                        json_body=json_body,
                        recipient_id=recipient_id,
                        activity_id=activity_id,
                    )
                except DeliveryError:
                    failed.append(recipient_id)

        if failed:
            raise DeliveryError(failed, activity_id)

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
            last_exc: Exception
            try:
                response = await client.post(
                    inbox_url,
                    content=json_body,
                    headers={"Content-Type": "application/json"},
                    timeout=self._timeout,
                )
                response.raise_for_status()
                logger.info(
                    "Delivered activity %s to %s (HTTP %s)",
                    activity_id,
                    inbox_url,
                    response.status_code,
                )
                return
            except httpx.HTTPStatusError as exc:
                if 400 <= exc.response.status_code < 500:
                    # 4xx is deterministic: the same payload will never succeed.
                    # Raise immediately without consuming retry slots (OX-13-005).
                    logger.error(
                        "Terminal delivery failure (HTTP %d) for activity %s"
                        " to %s — not retrying (OX-13-005).",
                        exc.response.status_code,
                        activity_id,
                        inbox_url,
                    )
                    raise DeliveryError([recipient_id], activity_id) from exc
                last_exc = exc
            except Exception as exc:
                last_exc = exc

            # Retryable failure (5xx or network error).
            if attempt < self._max_retries:
                logger.warning(
                    "Delivery attempt %d/%d failed for activity %s "
                    "to %s: %s — retrying in %.1fs",
                    attempt + 1,
                    self._max_retries + 1,
                    activity_id,
                    inbox_url,
                    last_exc,
                    delay,
                )
                await asyncio.sleep(delay + random.uniform(0, 0.5))
                delay = min(delay * self._backoff_multiplier, self._max_delay)
            else:
                logger.error(
                    "Failed to deliver activity %s to %s after %d "
                    "attempt(s): %s",
                    activity_id,
                    inbox_url,
                    self._max_retries + 1,
                    last_exc,
                )
                raise DeliveryError([recipient_id], activity_id) from last_exc
