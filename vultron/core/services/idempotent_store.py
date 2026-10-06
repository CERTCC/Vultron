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


"""Idempotently store a received domain object (CLP-10-019, CS-22-001).

The one implementation of "store what arrived unless it is already held".  It
lives in ``services/`` because both the receive-side store node
(:class:`~vultron.core.behaviors.case.nodes.store_received_object.StoreReceivedObjectNode`)
and the handlers that have not yet moved onto a tree share it, and the
``execute()`` mutation ratchet follows calls into this package.
"""

import logging
from typing import Any

from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


def idempotent_store(
    dl: CasePersistence,
    type_key: str | None,
    id_key: str | None,
    obj: Any,
    label: str,
    activity_id: str | None = None,
) -> HandlerResult:
    """Guard against duplicate object creation.

    Checks whether *id_key* is already present in the DataLayer.  If so, logs
    and returns without storing.  Otherwise stores *obj* (if not ``None``) via
    ``dl.create``.

    An object carrying an id but **no ``type_``** is a *reference*, not something
    that can be stored: ``type_`` is what selects the storage table, so
    ``Record.from_obj`` refuses it outright.  The extractor produces exactly such
    a stub — ``CoreObject(id_=…, type_=None)`` — when an inbound activity names
    its object by bare URI, or by an object with no type.  That stub is load
    bearing: ``event.object_id`` is *derived* from ``object_``, so it is how the id
    survives at all; it simply is not a storable record.

    Storing it was attempted anyway, which aborted the enclosing BT
    (``CreateReportReceivedBT`` among them).  Such a reference is skipped here with
    a warning naming it as one, because there is nothing to store — this is the
    "Bare Object URI" case the Actor Knowledge Model describes, where the sender
    should have inlined the object and the recipient legitimately has no copy.

    Args:
        dl: The DataLayer to read/write.
        type_key: Object type used as the DataLayer collection key.
        id_key: Object ID to check for existence.
        obj: The domain object to persist when not already present.
        label: Human-readable label used in log messages (e.g. ``"Note"``).
        activity_id: Activity ID used in warning log when *obj* is ``None``.

    Returns:
        What this helper did, as a ``HandlerResult`` a handler can return
        directly: ``APPLIED`` when *obj* was stored, and ``SKIPPED`` (with a
        reason) on every exit that stored nothing.  ``SKIPPED`` describes the
        helper's own act; whether a caller should report a missing or
        bare-reference object as ``REFUSED`` instead is the caller's verdict
        (#2255), not this helper's.  Callers that ignore the value are
        unaffected.
    """
    if not type_key or not id_key:
        return HandlerResult.skipped(f"no {label} type or id to store under")
    if dl.read(id_key) is not None:
        # Routine idempotency skip — infrastructure, not protocol story
        # (SL-04-007).  Fires on essentially every received-side activity.
        logger.debug("'%s' already stored — skipping (idempotent)", id_key)
        return HandlerResult.skipped(f"{label} '{id_key}' already stored")
    if obj is None:
        logger.warning("no %s object for event '%s'", label, activity_id)
        return HandlerResult.skipped(f"no {label} object to store")
    if getattr(obj, "type_", None) is None:
        logger.warning(
            "%s '%s' arrived as a bare reference with no type (activity '%s'):"
            " the sender named it by URI instead of inlining it, so there is no"
            " object to store — recording nothing (Actor Knowledge Model)",
            label,
            id_key,
            activity_id,
        )
        return HandlerResult.skipped(
            f"{label} '{id_key}' arrived as a bare reference"
        )
    dl.create(obj)
    logger.info("Stored %s '%s'", label, id_key)
    return HandlerResult.applied()
