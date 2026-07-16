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
#  U.S. Patent and Trademark Office by Carnegie Mellon file).

"""Background retry runner for pending ``Create(VulnerabilityCase)`` activities.

After the case-actor service sends ``Accept(CaseProposal)``, it writes a
``PendingCreateCaseActivity`` marker to the DataLayer and then attempts to
deliver ``Create(VulnerabilityCase)``.  If that delivery fails (or the
process crashes), the marker persists.

This module provides :func:`retry_pending_create_case_activities`, which:

1. Scans every registered actor-scoped DataLayer for
   ``PendingCreateCaseActivity`` markers.
2. Reconstructs the pre-built ``Create(VulnerabilityCase)`` payload from
   the marker (never re-constructs the activity from scratch, to preserve
   the original ``id_``).
3. Writes the activity to the DataLayer if not already present (idempotency
   guard).
4. Re-enqueues the activity to the actor's outbox so the
   :class:`~vultron.adapters.driving.fastapi.outbox_monitor.OutboxMonitor`
   can deliver it.
5. Deletes the marker so the retry runner does not re-deliver an already-
   queued activity on future startups.

**Design decision (AC-2):** The runner uses *option (a): on-startup scan*.
It is called once inside the FastAPI application lifespan immediately before
the server starts accepting requests.  This is the simplest approach and
directly covers the primary failure mode — a process crash after ``Accept``
was sent but before ``Create(VulnerabilityCase)`` was delivered.  The
:class:`OutboxMonitor` then drains and delivers the re-queued activities
asynchronously during normal operation.

Alternatives considered:

- (b) *Triggered re-scan on each inbox receipt* — adds per-request overhead
  and does not cover the crash-before-any-request scenario.
- (c) *Dedicated polling task via a scheduler* — heavier mechanism than
  needed for a low-frequency event.

Option (a) is sufficient because a persisted marker represents an obligation
from a *previous* process run; a re-scan at the start of each new run is
the natural recovery point.

Spec: ``specs/case-proposal.yaml`` CP-05-005.
Issue: #1139.
"""

import logging
from collections.abc import Callable
from typing import cast

from vultron.core.models.activity import VultronCreateCaseActivity
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


def _discover_actor_ids_from_shared_dl(shared_dl: DataLayer) -> list[str]:
    """Scan the shared DataLayer for ``case_actor_id`` values in persisted markers.

    Used by the startup scan to find actors that have pending
    ``PendingCreateCaseActivity`` markers even when the process-level actor
    cache is empty (e.g., after a crash/restart). The shared (unscoped)
    DataLayer returns rows across all actors.

    Args:
        shared_dl: An unscoped DataLayer that can see all actors' records.

    Returns:
        List of unique ``case_actor_id`` values found in persisted markers.
    """
    actor_ids: set[str] = set()
    for raw in shared_dl.list_objects("PendingCreateCaseActivity"):
        if isinstance(raw, PendingCreateCaseActivity):
            actor_ids.add(raw.case_actor_id)
    return list(actor_ids)


def _reconstruct_activity(
    marker: PendingCreateCaseActivity,
) -> VultronCreateCaseActivity | None:
    """Reconstruct Create(VulnerabilityCase) from a marker's stored payload.

    Returns the reconstructed activity, or ``None`` if the payload is
    missing or invalid (errors are logged at ERROR level).
    """
    if not marker.create_activity_payload:
        logger.warning(
            "retry_pending: marker '%s' has no create_activity_payload;"
            " skipping.",
            marker.id_,
        )
        return None

    try:
        return VultronCreateCaseActivity.model_validate(
            marker.create_activity_payload
        )
    except Exception as exc:
        logger.error(
            "retry_pending: could not reconstruct Create(VulnerabilityCase)"
            " from marker '%s': %s",
            marker.id_,
            exc,
        )
        return None


def _ensure_activity_persisted(
    dl: DataLayer,
    activity: VultronCreateCaseActivity,
) -> bool:
    """Write *activity* to *dl* if not already present.

    Returns ``True`` on success (including when the activity already exists),
    ``False`` if the DataLayer create call raises.
    """
    if dl.read(activity.id_) is not None:
        return True
    try:
        dl.create(activity)
        return True
    except ValueError as exc:
        logger.error(
            "retry_pending: could not persist Create(VulnerabilityCase)"
            " '%s': %s",
            activity.id_,
            exc,
        )
        return False


def _enqueue_and_clear(
    dl: DataLayer,
    marker: PendingCreateCaseActivity,
    activity: VultronCreateCaseActivity,
) -> bool:
    """Enqueue *activity* to the outbox and delete *marker*.

    Returns ``True`` when the activity is in the outbox (whether it was
    already there or was just added). Marker cleanup failures are logged
    as warnings but do not affect the return value — the obligation is
    considered satisfied once the activity is in the outbox.

    The enqueue step is idempotent: if *activity* is already in the
    outbox (e.g. from a previous partial run where the marker deletion
    failed), no duplicate entry is inserted (AC-4).
    """
    enqueue_actor_id = marker.case_actor_id

    # Idempotency guard: skip the insert if this activity is already
    # queued. record_outbox_item does not enforce uniqueness; calling it
    # twice would create two outbox entries and cause double delivery.
    try:
        existing_outbox = cast(
            CaseOutboxPersistence, dl
        ).outbox_list_for_actor(enqueue_actor_id)
    except Exception as exc:
        logger.error(
            "retry_pending: could not read outbox for actor '%s': %s",
            enqueue_actor_id,
            exc,
        )
        return False

    if activity.id_ not in existing_outbox:
        try:
            cast(CaseOutboxPersistence, dl).record_outbox_item(
                enqueue_actor_id, activity.id_
            )
        except Exception as exc:
            logger.error(
                "retry_pending: could not enqueue Create(VulnerabilityCase)"
                " '%s' to outbox for actor '%s': %s",
                activity.id_,
                enqueue_actor_id,
                exc,
            )
            return False
    else:
        logger.debug(
            "retry_pending: Create(VulnerabilityCase) '%s' already in"
            " outbox for actor '%s'; skipping duplicate enqueue.",
            activity.id_,
            enqueue_actor_id,
        )

    deleted = dl.delete("PendingCreateCaseActivity", marker.id_)
    if not deleted:
        logger.warning(
            "retry_pending: marker '%s' could not be deleted after"
            " successful re-queue for actor '%s'. On the next startup"
            " scan the activity will be found in the outbox and skipped.",
            marker.id_,
            enqueue_actor_id,
        )

    logger.info(
        "retry_pending: re-queued Create(VulnerabilityCase) '%s'"
        " for actor '%s' (marker '%s').",
        activity.id_,
        enqueue_actor_id,
        marker.id_,
    )
    return True


def retry_pending_create_case_activities(
    actor_datalayers_factory: Callable[[], dict[str, DataLayer]] | None = None,
    shared_datalayer_factory: Callable[[], DataLayer] | None = None,
) -> int:
    """Re-queue all persisted ``PendingCreateCaseActivity`` obligations.

    Iterates over every registered actor-scoped DataLayer, finds any
    ``PendingCreateCaseActivity`` markers, and re-enqueues the stored
    ``Create(VulnerabilityCase)`` payload to the case-actor's outbox for
    delivery by the :class:`OutboxMonitor`.

    Each marker is deleted after the payload is successfully enqueued, so
    running this function multiple times does not produce duplicate
    activities (AC-4).

    On crash/restart the process-level actor cache is empty.  This function
    supplements the cache by scanning the shared (unscoped) DataLayer for
    persisted markers and creating actor-scoped DataLayers for any
    ``case_actor_id`` values discovered there.  The shared-DL scan runs
    automatically when ``actor_datalayers_factory`` is ``None`` (the default
    production path), and also when ``shared_datalayer_factory`` is
    explicitly provided (useful for testing the startup-recovery path without
    touching the module-level cache).

    Args:
        actor_datalayers_factory: Callable returning the current
            ``{actor_id: DataLayer}`` mapping.  Defaults to
            :func:`~vultron.adapters.driven.datalayer.get_all_actor_datalayers`.
            Inject a test double to avoid touching the module-level cache.
        shared_datalayer_factory: Callable returning a shared (unscoped)
            DataLayer used to discover actor IDs from persisted markers on
            startup.  Defaults to
            :func:`~vultron.adapters.driven.datalayer.get_datalayer` (no
            actor scoping) when ``actor_datalayers_factory`` is ``None``.
            Inject a test double to exercise the startup-recovery path in
            isolation.

    Returns:
        The number of ``Create(VulnerabilityCase)`` activities successfully
        re-queued during this run.
    """
    if actor_datalayers_factory is not None:
        actor_dls: dict[str, DataLayer] = dict(actor_datalayers_factory())
    else:
        from vultron.adapters.driven.datalayer import get_all_actor_datalayers

        actor_dls = dict(get_all_actor_datalayers())  # type: ignore[assignment]

    # Supplement the map with actors discovered from persisted markers in the
    # shared DataLayer.  On crash/restart the process cache is empty, so without
    # this scan the runner would skip all persisted obligations.  The scan runs
    # unconditionally on the default production path (actor_datalayers_factory is
    # None) and when a shared_datalayer_factory is explicitly injected (test
    # coverage of the startup-recovery path).
    _run_shared_scan = (actor_datalayers_factory is None) or (
        shared_datalayer_factory is not None
    )
    if _run_shared_scan:
        if shared_datalayer_factory is not None:
            shared_dl: DataLayer = shared_datalayer_factory()
        else:
            from vultron.adapters.driven.datalayer import get_datalayer

            shared_dl = get_datalayer()  # type: ignore[assignment]

        for actor_id in _discover_actor_ids_from_shared_dl(shared_dl):
            if actor_id not in actor_dls:
                actor_dls[actor_id] = shared_dl.clone_for_actor(actor_id)
                logger.debug(
                    "retry_pending: discovered actor '%s' from persisted"
                    " markers — creating scoped DataLayer.",
                    actor_id,
                )

    if not actor_dls:
        logger.debug(
            "retry_pending: no actor DataLayers registered; skipping."
        )
        return 0

    retried = 0
    for actor_id, dl in actor_dls.items():
        retried += _retry_actor_dl(actor_id, dl)

    if retried:
        logger.info(
            "retry_pending: %d pending Create(VulnerabilityCase)"
            " activity/activities re-queued for delivery.",
            retried,
        )
    else:
        logger.debug(
            "retry_pending: no pending Create(VulnerabilityCase) found."
        )
    return retried


def _retry_actor_dl(actor_id: str, dl: DataLayer) -> int:
    """Process all PendingCreateCaseActivity markers in one actor DataLayer.

    Returns the count of successfully re-queued activities.
    """
    retried = 0
    for raw_marker in dl.list_objects("PendingCreateCaseActivity"):
        if not isinstance(raw_marker, PendingCreateCaseActivity):
            logger.warning(
                "retry_pending: unexpected object type %r in actor '%s'"
                " DataLayer; skipping.",
                type(raw_marker).__name__,
                actor_id,
            )
            continue

        activity = _reconstruct_activity(raw_marker)
        if activity is None:
            continue

        if not _ensure_activity_persisted(dl, activity):
            continue

        if _enqueue_and_clear(dl, raw_marker, activity):
            retried += 1

    return retried


__all__ = ["retry_pending_create_case_activities"]
