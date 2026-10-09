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
3. Persists the activity, if not already present, and seals its body through
   the trigger adapter (idempotency guard; VM-08-003).
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

The same startup scan recovers a second obligation of the case-creation
tree: :func:`retry_pending_creation_time_revision_relays` finds every
``PendingCreationTimeRevisionRelay`` marker, the revision a contested case
creation registered but whose ``Invite(EmbargoEvent)`` relay failed
(EP-04-011), and re-runs ``RelayCreationTimeRevisionNode`` for its case.
Creation-time initialization runs once per case (EP-04-012), so without the
marker and this runner a failed relay would never be retried unless the
proposal happened to be redelivered (#4121).
"""

import logging
from collections.abc import Callable, Mapping
from typing import cast

import py_trees
from py_trees.common import Status

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.datalayer import (
    get_all_actor_datalayers,
    get_datalayer,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.embargo_revision_relay import (
    RelayCreationTimeRevisionNode,
)
from vultron.core.behaviors.case.nodes.proposal import (
    RequeuePendingCreateCaseActivityNode,
)
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CREATE_CASE_EVENT_TYPE,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.pending_creation_time_revision_relay import (
    PendingCreationTimeRevisionRelay,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


def _discover_actor_ids_from_stores() -> list[str]:
    """Find ``case_actor_id`` values in persisted markers across hosted actors.

    Used by the startup scan to find actors with pending
    ``PendingCreateCaseActivity`` markers when the process-level actor cache is
    empty (e.g. after a crash/restart).

    Before ADR-0073 this read one unscoped DataLayer that could see every
    actor's rows.  There is no such view now, so it enumerates the actors this
    node hosts and scans each one's own store.  The marker names the CaseActor
    that owes the work (``case_actor_id``), which is not necessarily the actor
    whose store holds the marker — so the two are kept distinct here.

    Returns:
        Unique ``case_actor_id`` values found in any hosted actor's store.
    """
    actor_ids: set[str] = set()
    for host_id in actor_hosts.hosted_actor_ids():
        host_dl = get_datalayer(host_id)
        for raw in host_dl.list_objects("PendingCreateCaseActivity"):
            if isinstance(raw, PendingCreateCaseActivity):
                actor_ids.add(raw.case_actor_id)
    return list(actor_ids)


def _persist_prepared_activity(
    dl: DataLayer,
    marker: PendingCreateCaseActivity,
) -> str | None:
    """Persist and seal the marker's Create(VulnerabilityCase); return its id.

    Goes through the same adapter method the emitting node uses, so a
    recovered activity is persisted under the marker's id and its delivered
    body is the sealed one (CP-05-005, VM-08-003).  Returns ``None`` if the
    payload is missing or invalid (errors are logged at ERROR level).
    """
    if not marker.create_activity_payload:
        logger.warning(
            "retry_pending: marker '%s' has no create_activity_payload;"
            " skipping.",
            marker.id_,
        )
        return None

    try:
        activity_id, _body = TriggerActivityAdapter(
            cast(CaseOutboxPersistence, dl)
        ).emit_prepared_create_case(marker.create_activity_payload)
    except VultronError as exc:
        logger.error(  # noqa: TRY400  # ruff-baseline #3353
            "retry_pending: could not persist Create(VulnerabilityCase)"
            " from marker '%s': %s",
            marker.id_,
            exc,
        )
        return None
    return activity_id


def _run_recovery_tree(
    bridge: BTBridge,
    tree: py_trees.behaviour.Behaviour,
    actor_id: str,
    what: str,
) -> bool:
    """Run a recovery *tree* as *actor_id*; log and return ``False`` on failure.

    Recovery work is protocol-significant, so it runs as a BT through the
    bridge (BT-15-001), and a failure is diagnosed through
    ``BTBridge.get_failure_reason`` (BT-13-001).  *what* names the work in
    the log line.
    """
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)
    if result.status != Status.SUCCESS:
        logger.error(
            "retry_pending: %s did not succeed for actor '%s': %s",
            what,
            actor_id,
            BTBridge.get_failure_reason(tree),
        )
        return False
    return True


def _enqueue_and_clear(
    dl: DataLayer,
    marker: PendingCreateCaseActivity,
    activity_id: str,
) -> bool:
    """Re-queue *activity* and clear *marker*, via the BT.

    Returns ``True`` when the activity is in the outbox (whether it was already
    there or was just added).  Marker cleanup failures are logged as warnings
    but do not affect the return value — the obligation is discharged once the
    activity is queued.

    Enqueueing an outbound activity is protocol-significant behaviour, so the
    work lives in ``RequeuePendingCreateCaseActivityNode`` rather than here
    (BT-15-001).  This adapter function only schedules it: the BT bridge gives
    the operation the same audit trail as every other protocol effect, which is
    exactly what a crash-recovery path should have.
    """
    tree = RequeuePendingCreateCaseActivityNode(
        marker=marker, activity_id=activity_id
    )
    # `dl` is typed as the narrow `DataLayer` port; the BT needs case-aware
    # reads.  `SqliteDataLayer` satisfies both protocols structurally, but a bare
    # `DataLayer` does not, because `CasePersistence.clone_for_actor` is declared
    # to return a `CasePersistence`.
    return _run_recovery_tree(
        BTBridge(datalayer=cast(CasePersistence, dl)),
        tree,
        marker.case_actor_id,
        f"re-queue of marker '{marker.id_}'",
    )


def retry_pending_create_case_activities(
    actor_datalayers_factory: Callable[[], dict[str, DataLayer]] | None = None,
    marker_scan_factory: Callable[[], list[str]] | None = None,
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
    supplements the cache by scanning each hosted actor's own store for
    persisted markers and opening DataLayers for any ``case_actor_id`` values
    discovered there.  The scan runs automatically when
    ``actor_datalayers_factory`` is ``None`` (the default production path), and
    also when ``marker_scan_factory`` is explicitly provided (useful for
    testing the startup-recovery path without touching the module-level cache).

    Args:
        actor_datalayers_factory: Callable returning the current
            ``{actor_id: DataLayer}`` mapping.  Defaults to
            :func:`~vultron.adapters.driven.datalayer.get_all_actor_datalayers`.
            Inject a test double to avoid touching the module-level cache.
        marker_scan_factory: Callable returning the ``case_actor_id`` values
            that have persisted markers.  Defaults to
            :func:`_discover_actor_ids_from_stores`, which scans every hosted
            actor's own store.  Inject a test double to exercise the
            startup-recovery path in isolation.  Replaces the pre-ADR-0073
            ``shared_datalayer_factory``, which handed in one unscoped
            DataLayer that could see all actors' rows.

    Returns:
        The number of ``Create(VulnerabilityCase)`` activities successfully
        re-queued during this run.
    """
    if actor_datalayers_factory is not None:
        actor_dls: dict[str, DataLayer] = dict(actor_datalayers_factory())
    else:
        actor_dls = dict(get_all_actor_datalayers())  # type: ignore[assignment]

    # Supplement the map with actors discovered from persisted markers.  On
    # crash/restart the process cache is empty, so without this scan the runner
    # would skip all persisted obligations.  The scan runs unconditionally on
    # the default production path (actor_datalayers_factory is None) and when a
    # marker_scan_factory is explicitly injected (test coverage of the
    # startup-recovery path).
    _run_marker_scan = (actor_datalayers_factory is None) or (
        marker_scan_factory is not None
    )
    if _run_marker_scan:
        discovered = (
            marker_scan_factory()
            if marker_scan_factory is not None
            else _discover_actor_ids_from_stores()
        )
        for actor_id in discovered:
            if actor_id not in actor_dls:
                actor_dls[actor_id] = get_datalayer(actor_id)
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

        activity_id = _persist_prepared_activity(dl, raw_marker)
        if activity_id is None:
            continue

        if _enqueue_and_clear(dl, raw_marker, activity_id):
            retried += 1

    return retried


def _hosted_datalayers() -> dict[str, DataLayer]:
    """Every store this node holds: the actor cache plus each hosted actor.

    Unlike the ``Create`` runner, which opens a store for each
    ``case_actor_id`` its markers name, this marker always sits in the store
    of the CASE_MANAGER that owes it (the store its writer executed against),
    so the hosted stores are the whole search space (ADR-0073).
    """
    dls: dict[str, DataLayer] = {**get_all_actor_datalayers()}
    for host_id in actor_hosts.hosted_actor_ids():
        if host_id not in dls:
            dls[host_id] = get_datalayer(host_id)
    return dls


def _relay_pending_revision(
    dl: DataLayer, marker: PendingCreationTimeRevisionRelay
) -> bool:
    """Re-run the creation-time revision relay for *marker*'s case, via the BT.

    Sending the Invite is protocol-significant, so the work is the case tree's
    own ``RelayCreationTimeRevisionNode`` run through ``BTBridge`` (BT-15-001),
    behind the CASE_MANAGER gate (BT-17-001) so only the current role holder
    relays, as the actor the marker names, with the ports the received tree
    gives it.  The node deletes the marker once the relay is discharged and
    keeps it on any failure, while the case's creation entries are still
    uncommitted, or when the gate turns the actor away, so a later run can
    retry.  Returns ``True`` only when the marker was discharged.
    """
    cop = cast(CaseOutboxPersistence, dl)
    tree = create_case_manager_gated_tree(
        name="RetryCreationTimeRevisionRelay",
        case_id=marker.case_id,
        children=[RelayCreationTimeRevisionNode(case_id=marker.case_id)],
    )
    bridge = BTBridge(
        datalayer=cast(CasePersistence, dl),
        trigger_activity=TriggerActivityAdapter(cop),
        sync_port=SyncActivityAdapter(cop),
        wire_render_port=As2WireRenderAdapter(),
    )
    if not _run_recovery_tree(
        bridge,
        tree,
        marker.case_actor_id,
        f"relay of creation-time revision '{marker.embargo_id}'"
        f" on case '{marker.case_id}'",
    ):
        return False
    if dl.read(marker.id_) is None:
        return True
    if not any(
        e.event_type == CREATE_CASE_EVENT_TYPE
        for e in recorded_entries_for_case(case_id=marker.case_id, dl=cop)
    ):
        # Nothing at startup commits a case's creation entries: only a
        # redelivered proposal re-runs the case tree that does, so without one
        # this relay waits at every boot (CM-14-007, CM-14-011).
        logger.warning(
            "retry_pending: relay of creation-time revision '%s' on case '%s'"
            " waits for the case's creation entries, which only a redelivered"
            " proposal commits; kept for a later run",
            marker.embargo_id,
            marker.case_id,
        )
    else:
        logger.info(
            "retry_pending: relay of creation-time revision '%s' on case '%s'"
            " is still owed by '%s', which no longer holds CASE_MANAGER;"
            " kept for a later run",
            marker.embargo_id,
            marker.case_id,
            marker.case_actor_id,
        )
    return False


def retry_pending_creation_time_revision_relays(
    datalayers_factory: Callable[[], Mapping[str, DataLayer]] | None = None,
) -> int:
    """Complete every creation-time revision relay still owed (EP-04-011).

    Scans each store for ``PendingCreationTimeRevisionRelay`` markers and
    re-runs the relay for each one's case.  Idempotent: the relay sends the
    Invite under the id the marker carries, and an Invite already in the
    ledger is indexed rather than sent again.  A failure is logged and leaves
    the marker for the next run; it never stops the server from starting.

    Args:
        datalayers_factory: Callable returning the ``{actor_id: DataLayer}``
            stores to scan.  Defaults to the actor cache plus every hosted
            actor's own store.  Inject a test double to avoid touching the
            module-level cache.

    Returns:
        The number of markers whose relay was discharged during this run.

    Spec: EP-04-011.  Issue: #4121.
    """
    stores = (
        datalayers_factory()
        if datalayers_factory is not None
        else _hosted_datalayers()
    )
    relayed = 0
    for actor_id, dl in stores.items():
        try:
            markers = dl.list_objects("PendingCreationTimeRevisionRelay")
        except Exception as exc:  # noqa: BLE001 - recovery must not crash boot
            logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "retry_pending: could not scan actor '%s' for pending"
                " revision relays: %s",
                actor_id,
                exc,
            )
            continue
        for marker in markers:
            if not isinstance(marker, PendingCreationTimeRevisionRelay):
                continue
            if marker.case_actor_id != actor_id:
                # A tree runs against the store of the actor it executes as
                # (BT-05-005, DL-07-004); a marker naming another actor was not
                # written by this store's owner, so relaying it here would
                # read one actor's case as another's.
                logger.warning(
                    "retry_pending: store '%s' holds a revision relay owed by"
                    " '%s' for case '%s'; skipped",
                    actor_id,
                    marker.case_actor_id,
                    marker.case_id,
                )
                continue
            if _relay_pending_revision(dl, marker):
                relayed += 1
    if relayed:
        logger.info(
            "retry_pending: %d pending creation-time revision relay(s)"
            " completed.",
            relayed,
        )
    return relayed


__all__ = [
    "retry_pending_create_case_activities",
    "retry_pending_creation_time_revision_relays",
]
