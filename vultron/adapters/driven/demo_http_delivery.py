"""Backward-compatibility shim — import from ``http_delivery`` instead.

``DemoHttpDeliveryAdapter`` has been renamed to ``HttpDeliveryAdapter`` and
moved to ``vultron.adapters.driven.http_delivery`` (ADR-0042, OX-12-001).
This module re-exports the new names under the old identifiers so that
existing import sites continue to work until they are migrated.

.. deprecated::
    Import ``HttpDeliveryAdapter`` from
    ``vultron.adapters.driven.http_delivery`` directly.
"""

from vultron.adapters.driven.http_delivery import (  # noqa: F401
    DEFAULT_BACKOFF_MULTIPLIER,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_MAX_RETRIES,
    DeliveryError,
    HttpDeliveryAdapter as DemoHttpDeliveryAdapter,
)
