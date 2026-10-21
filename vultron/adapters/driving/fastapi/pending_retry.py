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

"""Startup retry runner for owed creation-time revision relays.

:func:`retry_pending_creation_time_revision_relays` finds every
``PendingCreationTimeRevisionRelay`` marker, the revision a contested case
creation registered but whose ``Invite(EmbargoEvent)`` relay failed
(EP-04-011), and re-runs ``RelayCreationTimeRevisionNode`` for its case.
Creation-time initialization runs once per case (EP-04-012), so without the
marker and this runner a failed relay would never be retried unless the
proposal happened to be redelivered (#4121).

It runs once inside the FastAPI application lifespan, before the server
accepts requests: a persisted marker is an obligation from a *previous*
process run, so the start of each new run is the natural recovery point.

The case-creation ``Create(VulnerabilityCase)`` needs no runner of its own:
it is queued in the same transaction as the case (ADR-0146), so once that
transaction commits the durable outbox holds it and retries its delivery
(OX-13, CP-05-005).
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
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CREATE_CASE_SEMANTIC_TYPE,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.models.pending_creation_time_revision_relay import (
    PendingCreationTimeRevisionRelay,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.sync_helpers import recorded_entries_for_case

logger = logging.getLogger(__name__)


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


def _hosted_datalayers() -> dict[str, DataLayer]:
    """Every store this node holds: the actor cache plus each hosted actor.

    The marker always sits in the store of the CASE_MANAGER that owes it (the
    store its writer executed against), so the hosted stores are the whole
    search space (ADR-0073).
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
        e.semantic_type == CREATE_CASE_SEMANTIC_TYPE
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
    "retry_pending_creation_time_revision_relays",
]
