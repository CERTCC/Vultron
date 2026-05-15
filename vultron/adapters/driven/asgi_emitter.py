"""Local ASGI delivery adapter — delivers to co-located actors in-process.

Attempts to deliver every recipient via the local ASGI application first.
If the ASGI app returns a non-success status (e.g. 404 when the actor is
not hosted locally), the recipient is retried via HTTP through the standard
``DeliveryQueueAdapter``.

This strategy is URL-scheme agnostic: it works whether actor IDs use the
production ``base_url`` or a test-client URL like ``http://testserver``.

A reentrancy guard (``_asgi_delivery_depth``) prevents recursive ASGI
transport calls.  When ``_try_deliver_local`` is invoked from within an
already-active delivery chain (same asyncio task), subsequent deliveries
fall through to the HTTP fallback instead of re-entering the ASGI app.
In production the fallback is ``DeliveryQueueAdapter`` (normal HTTP POST
handled by uvicorn as a new request/task); in tests it is typically a
``NullDeliveryAdapter`` that silently drops unreachable deliveries.

Port: ``vultron.core.ports.emitter.ActivityEmitter``
"""

import contextvars
import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from vultron.adapters.driven.delivery_queue import DeliveryQueueAdapter
from vultron.config import get_config
from vultron.core.models.activity import VultronActivity

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Tracks ASGI delivery depth within a single asyncio task to prevent
# recursive ASGITransport re-entry (#531).  Each new asyncio task (e.g.
# a fresh HTTP request in uvicorn) starts at depth 0, so production
# delivery chains across separate requests are unaffected.
_asgi_delivery_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "_asgi_delivery_depth", default=0
)


class ASGIEmitter:
    """``ActivityEmitter`` that tries local ASGI delivery first.

    For each recipient the emitter extracts the URL path from the
    recipient ID and POSTs to the ASGI app.  If the app returns a
    non-success status the recipient is delivered via HTTP as a
    fallback.

    Args:
        app: The ASGI application to deliver to locally.
        base_url: Base URL for constructing the ASGI client.  Defaults
            to the configured ``server.base_url``.
        mount_prefix: URL path prefix at which *app* is mounted in the
            outer application (e.g. ``"/api/v2"``).  Stripped from
            recipient URLs before routing into *app*.
    """

    def __init__(
        self,
        app: "ASGIApp",
        base_url: str | None = None,
        mount_prefix: str = "",
    ) -> None:
        self._app = app
        self._base_url = (base_url or get_config().server.base_url).rstrip("/")
        self._mount_prefix = mount_prefix.rstrip("/")
        self._http_fallback = DeliveryQueueAdapter()

    async def emit(
        self,
        activity: VultronActivity,
        recipients: list[str],
    ) -> None:
        """Deliver *activity* to each recipient.

        Tries local ASGI delivery first; falls back to HTTP for
        recipients that are not hosted on this server.
        """
        if hasattr(activity, "model_dump_json"):
            json_body: str = activity.model_dump_json(
                by_alias=True, exclude_none=True
            )
        else:
            json_body = json.dumps(dict(activity), default=str)

        activity_id = getattr(activity, "id_", None) or getattr(
            activity, "id", None
        )

        remote_fallback: list[str] = []
        for recipient_id in recipients:
            if not self._is_local_recipient(recipient_id):
                remote_fallback.append(recipient_id)
                continue
            delivered = await self._try_deliver_local(
                json_body, recipient_id, activity_id
            )
            if not delivered:
                remote_fallback.append(recipient_id)

        if remote_fallback:
            await self._http_fallback.emit(activity, remote_fallback)

    def _is_local_recipient(self, recipient_id: str) -> bool:
        """Return True if *recipient_id* is served by this ASGI app.

        Compares the scheme and netloc of the recipient URL against the
        configured ``base_url``.  Remote actors (different host/port) are
        routed directly to HTTP to avoid intercepting messages destined for
        other containers.
        """
        try:
            parsed = urlparse(recipient_id)
            local = urlparse(self._base_url)
            return (
                parsed.scheme == local.scheme and parsed.netloc == local.netloc
            )
        except Exception:
            return False

    async def _try_deliver_local(
        self,
        json_body: str,
        recipient_id: str,
        activity_id: str | None,
    ) -> bool:
        """Attempt ASGI delivery; return True on success, False otherwise.

        Skips nested delivery when already inside an ASGI delivery chain
        (same asyncio task) to prevent recursive ``ASGITransport``
        re-entry (#531).  Cascading deliveries fall through to the HTTP
        fallback adapter instead.
        """
        depth = _asgi_delivery_depth.get()
        if depth > 0:
            logger.debug(
                "Skipping recursive ASGI delivery for %s"
                " (depth=%d) — deferring to HTTP fallback",
                recipient_id,
                depth,
            )
            return False

        import httpx

        parsed = urlparse(recipient_id.rstrip("/") + "/inbox/")
        inbox_path = parsed.path

        # Strip mount prefix so the path is relative to the sub-app.
        if self._mount_prefix and inbox_path.startswith(self._mount_prefix):
            inbox_path = inbox_path[len(self._mount_prefix) :]

        token = _asgi_delivery_depth.set(depth + 1)
        try:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url=self._base_url,
            ) as client:
                response = await client.post(
                    inbox_path,
                    content=json_body,
                    headers={"Content-Type": "application/json"},
                    timeout=10.0,
                )
                if response.status_code == 404:
                    logger.debug(
                        "ASGI 404 for %s — will try HTTP fallback",
                        inbox_path,
                    )
                    return False
                response.raise_for_status()
                logger.info(
                    "Delivered activity %s to %s via ASGI (HTTP %s)",
                    activity_id,
                    inbox_path,
                    response.status_code,
                )
                return True
        except Exception as exc:
            logger.debug(
                "ASGI delivery failed for %s (%s) — will try HTTP",
                inbox_path,
                exc,
            )
            return False
        finally:
            _asgi_delivery_depth.reset(token)
