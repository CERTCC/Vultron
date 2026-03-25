"""Shared helper utilities for use-case implementations.

Module-level helpers used across multiple use-case modules.
All helpers are private to the use-cases package (prefix ``_``).
"""

import logging
import uuid
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
    as_id = getattr(obj, "as_id", None)
    if isinstance(as_id, str):
        return as_id
    return str(obj)


def _idempotent_create(
    dl: DataLayer,
    type_key: str | None,
    id_key: str | None,
    obj: Any,
    label: str,
    activity_id: str | None = None,
) -> None:
    """Guard against duplicate object creation.

    Checks whether *id_key* is already present in the DataLayer.  If so, logs
    and returns without storing.  Otherwise stores *obj* (if not ``None``) via
    ``dl.create``.

    Args:
        dl: The DataLayer to read/write.
        type_key: Object type used as the DataLayer collection key.
        id_key: Object ID to check for existence.
        obj: The domain object to persist when not already present.
        label: Human-readable label used in log messages (e.g. ``"Note"``).
        activity_id: Activity ID used in warning log when *obj* is ``None``.
    """
    if not type_key or not id_key:
        return
    if dl.get(type_key, id_key) is not None:
        logger.info("'%s' already stored — skipping (idempotent)", id_key)
        return
    if obj is not None:
        dl.create(obj)
        logger.info("Stored %s '%s'", label, id_key)
    else:
        logger.warning("no %s object for event '%s'", label, activity_id)


def _report_phase_status_id(
    actor_id: str, report_id: str, rm_state: str
) -> str:
    """Return a deterministic URN for a report-phase participant status record.

    Uses UUID v5 (name-based) so the same (actor, report, rm_state) triple
    always produces the same ID, enabling idempotent DataLayer creation.
    """
    name = f"{actor_id}|{report_id}|{rm_state}"
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"
