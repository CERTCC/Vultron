#!/usr/bin/env python
"""Core BT inbox orchestration module.

Provides :func:`process_payload` as the sole caller-facing entry point
for inbox processing.  Callers supply adapter implementations for
ingress parsing, dispatch, and pending-queue management; the BT Sequence
enforces fixed pipeline ordering and returns a typed
:class:`InboxOutcome`.

Per specs/inbox-orchestration.yaml IO-02-001 through IO-02-003.
"""

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

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.inbox.inbox_tree import create_inbox_bt
from vultron.core.behaviors.inbox.models import (
    DispatchAdapter,
    InboxOutcome,
    IngressPayloadAdapter,
    PendingCaseQueuePort,
)
from vultron.core.behaviors.inbox.nodes import (
    ALL_INBOX_KEYS,
    KEY_CONTEXT_ID,
    KEY_DISPATCH,
    KEY_FAILURE_REASON,
    KEY_INGRESS,
    KEY_OUTCOME_STATUS,
    KEY_PAYLOAD,
    KEY_QUEUE,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Maximum BT ticks before giving up (safety limit — all pipeline nodes
# return SUCCESS/FAILURE synchronously, so one tick should suffice).
_MAX_TICKS = 10


def _save_inbox_keys(
    storage: dict[str, Any],
) -> dict[str, tuple[bool, Any]]:
    """Snapshot the current values of all inbox blackboard keys."""
    saved: dict[str, tuple[bool, Any]] = {}
    for key in ALL_INBOX_KEYS:
        for variant in (key, f"/{key}"):
            saved[variant] = (variant in storage, storage.get(variant))
    return saved


def _write_inbox_inputs(
    payload: Any,
    ingress_adapter: IngressPayloadAdapter,
    dispatch_adapter: DispatchAdapter,
    queue_port: PendingCaseQueuePort | None,
) -> None:
    """Write pipeline inputs to the BT blackboard."""
    setup_bb = py_trees.blackboard.Client(name="InboxOrchestrator-setup")
    setup_bb.register_key(KEY_PAYLOAD, access=py_trees.common.Access.WRITE)
    setup_bb.register_key(KEY_INGRESS, access=py_trees.common.Access.WRITE)
    setup_bb.register_key(KEY_DISPATCH, access=py_trees.common.Access.WRITE)
    setup_bb.register_key(KEY_QUEUE, access=py_trees.common.Access.WRITE)
    setup_bb.inbox_payload = payload
    setup_bb.inbox_ingress = ingress_adapter
    setup_bb.inbox_dispatch = dispatch_adapter
    setup_bb.inbox_queue = queue_port


def _run_bt_pipeline() -> Status:
    """Instantiate the inbox BT, tick to completion, and return the status."""
    tree = create_inbox_bt()
    bt = py_trees.trees.BehaviourTree(root=tree)
    bt.setup()

    tick_count = 0
    final_status = Status.INVALID
    try:
        while tick_count < _MAX_TICKS:
            tick_count += 1
            bt.tick()
            final_status = bt.root.status
            if final_status in (Status.SUCCESS, Status.FAILURE):
                break
    except Exception as exc:
        logger.exception("process_payload: BT tick raised exception: %s", exc)
        final_status = Status.FAILURE
    finally:
        bt.shutdown()

    logger.debug(
        "process_payload: BT completed status=%s ticks=%d",
        final_status,
        tick_count,
    )
    return final_status


def _read_inbox_outcome() -> InboxOutcome:
    """Read the outcome fields written by BT nodes and build an InboxOutcome."""
    result_bb = py_trees.blackboard.Client(name="InboxOrchestrator-result")
    result_bb.register_key(
        KEY_OUTCOME_STATUS, access=py_trees.common.Access.READ
    )
    result_bb.register_key(KEY_CONTEXT_ID, access=py_trees.common.Access.READ)
    result_bb.register_key(
        KEY_FAILURE_REASON, access=py_trees.common.Access.READ
    )

    try:
        status_str: str = result_bb.inbox_outcome_status
    except KeyError:
        status_str = "rejected"

    try:
        context_id: str | None = result_bb.inbox_context_id
    except KeyError:
        context_id = None

    try:
        failure_reason: str | None = result_bb.inbox_failure_reason
    except KeyError:
        failure_reason = None

    return InboxOutcome(
        status=status_str,  # type: ignore[arg-type]
        context_id=context_id,
        failure_reason=failure_reason,
    )


def _restore_inbox_keys(
    storage: dict[str, Any],
    saved: dict[str, tuple[bool, Any]],
) -> None:
    """Restore inbox blackboard keys to their pre-execution state."""
    for key, (had_value, value) in saved.items():
        if had_value:
            storage[key] = value
        else:
            storage.pop(key, None)


def process_payload(
    payload: dict[str, Any] | bytes | str | Any,
    ingress_adapter: IngressPayloadAdapter,
    dispatch_adapter: DispatchAdapter,
    queue_port: PendingCaseQueuePort | None = None,
) -> InboxOutcome:
    """Process one inbox payload through the BT pipeline.

    Always returns an :class:`InboxOutcome`; never raises for
    protocol-invalid payloads (IO-04-001).

    Args:
        payload: Raw inbox payload.  For the FastAPI driving adapter this
            is the JSON request body dict (or an already-parsed
            ``as_Activity``).  For replay paths it is a stored
            activity-ID string.
        ingress_adapter: Translates *payload* into a rehydrated
            ``as_Activity``.  Owns parse and rehydrate (IO-03-001).
        dispatch_adapter: Executes the use-case path for a
            ``VultronEvent`` (IO-03-001).
        queue_port: Optional pending-case queue port.  When provided,
            activities whose case context is not yet locally available
            are queued for later replay instead of being rejected
            (IO-03-002).

    Returns:
        :class:`InboxOutcome` with ``status`` set to one of
        ``"processed"``, ``"deferred"``, or ``"rejected"``.
    """
    # Import the shared BT global lock to serialise BT blackboard access
    # across concurrent FastAPI BackgroundTasks.  The RLock supports
    # re-entrant acquisition so replay paths calling process_payload
    # recursively do not deadlock.
    from vultron.core.behaviors.bridge import _BT_GLOBAL_LOCK

    with _BT_GLOBAL_LOCK:
        storage = py_trees.blackboard.Blackboard.storage
        saved = _save_inbox_keys(storage)

        try:
            _write_inbox_inputs(
                payload, ingress_adapter, dispatch_adapter, queue_port
            )
            _run_bt_pipeline()
            outcome = _read_inbox_outcome()
        finally:
            _restore_inbox_keys(storage, saved)

    logger.info(
        "process_payload: outcome status=%s context_id=%s",
        outcome.status,
        outcome.context_id,
    )
    return outcome
