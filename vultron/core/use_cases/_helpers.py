"""Shared helper utilities for use-case implementations.

Module-level helpers used across multiple use-case modules.
All helpers are private to the use-cases package (prefix ``_``).
"""

import logging
from typing import Any

from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


def _as_id(obj: Any) -> str | None:
    """Return the ActivityStreams id of *obj* as a plain string.

    - If *obj* is ``None``, returns ``None``.
    - If *obj* has an ``as_id`` attribute, returns ``obj.as_id``.
    - Otherwise returns ``str(obj)``.

    This handles the mixed ``str | <wire-type>`` collections that arise when
    the DataLayer stores plain string IDs alongside rehydrated objects.
    """
    if obj is None:
        return None
    if hasattr(obj, "as_id"):
        return obj.as_id
    return str(obj)


def _idempotent_create(
    dl: DataLayer,
    type_key: str | None,
    id_key: str | None,
    obj: Any,
    label: str,
    activity_id: str | None = None,
) -> bool:
    """Guard against duplicate object creation.

    Returns ``True`` if *id_key* is already present in the DataLayer and the
    caller should return early.  Otherwise stores *obj* (if not ``None``) via
    ``dl.create`` and returns ``False``.

    Args:
        dl: The DataLayer to read/write.
        type_key: Object type used as the DataLayer collection key.
        id_key: Object ID to check for existence.
        obj: The domain object to persist when not already present.
        label: Human-readable label used in log messages (e.g. ``"Note"``).
        activity_id: Activity ID used in warning log when *obj* is ``None``.
    """
    if not type_key or not id_key:
        return False
    if dl.get(type_key, id_key) is not None:
        logger.info("'%s' already stored — skipping (idempotent)", id_key)
        return True
    if obj is not None:
        dl.create(obj)
        logger.info("Stored %s '%s'", label, id_key)
    else:
        logger.warning("no %s object for event '%s'", label, activity_id)
    return False
