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
from datetime import datetime
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.blackboard_scope import (
    KeyState,
    key_aliases,
    restore_keys,
    snapshot_keys,
)
from vultron.core.behaviors.bridge.act_instant import (
    act_instant_in_tree_run,
    open_received_act,
)
from vultron.core.behaviors.inbox.inbox_tree import create_inbox_bt
from vultron.core.behaviors.inbox.models import (
    DispatchAdapter,
    InboxOutcome,
    InboxOutcomeStatus,
    IngressPayloadAdapter,
    PendingCaseQueuePort,
    ReceivedOutcomePort,
)
from vultron.core.behaviors.inbox.nodes import (
    ALL_INBOX_KEYS,
    KEY_CONTEXT_ID,
    KEY_DEREFERENCE,
    KEY_DISPATCH,
    KEY_DISPOSITION,
    KEY_EVENT,
    KEY_FAILURE_REASON,
    KEY_INGRESS,
    KEY_OUTCOME,
    KEY_OUTCOME_STATUS,
    KEY_PAYLOAD,
    KEY_QUEUE,
    KEY_UNHANDLED,
)
from vultron.core.ports.object_dereference import ObjectDereferencePort

logger = logging.getLogger(__name__)

# Maximum BT ticks before giving up (safety limit — all pipeline nodes
# return SUCCESS/FAILURE synchronously, so one tick should suffice).
_MAX_TICKS = 10


def _save_inbox_keys(
    storage: dict[str, Any],
) -> dict[str, KeyState]:
    """Snapshot the current values of all inbox blackboard keys.

    Delegates to the shared implementation rather than carrying its own copy:
    ``BTBridge.execute_with_setup`` needs the identical guarantee, and keeping
    two copies meant a fix to one never reached the other (#3534, CS-22-001).
    """
    return snapshot_keys(storage, ALL_INBOX_KEYS)


def _write_inbox_inputs(
    payload: Any,
    ingress_adapter: IngressPayloadAdapter,
    dispatch_adapter: DispatchAdapter,
    queue_port: PendingCaseQueuePort | None,
    dereference_port: ObjectDereferencePort | None = None,
    received_outcome_port: ReceivedOutcomePort | None = None,
) -> None:
    """Write pipeline inputs to the BT blackboard."""
    setup_bb = py_trees.blackboard.Client(name="InboxOrchestrator-setup")
    setup_bb.register_key(KEY_PAYLOAD, access=py_trees.common.Access.WRITE)
    setup_bb.register_key(KEY_INGRESS, access=py_trees.common.Access.WRITE)
    setup_bb.register_key(KEY_DISPATCH, access=py_trees.common.Access.WRITE)
    setup_bb.register_key(KEY_QUEUE, access=py_trees.common.Access.WRITE)
    setup_bb.register_key(KEY_DEREFERENCE, access=py_trees.common.Access.WRITE)
    setup_bb.register_key(KEY_OUTCOME, access=py_trees.common.Access.WRITE)
    setup_bb.inbox_payload = payload
    setup_bb.inbox_ingress = ingress_adapter
    setup_bb.inbox_dispatch = dispatch_adapter
    setup_bb.inbox_queue = queue_port
    setup_bb.inbox_dereference = dereference_port
    setup_bb.inbox_received_outcome = received_outcome_port


def _run_bt_pipeline(actor_config: ActorConfig | None = None) -> Status:
    """Instantiate the inbox BT, tick to completion, and return the status."""
    tree = create_inbox_bt(actor_config=actor_config)
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
    except Exception:
        logger.exception("process_payload: BT tick raised exception")
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
    result_bb.register_key(KEY_EVENT, access=py_trees.common.Access.READ)
    result_bb.register_key(KEY_UNHANDLED, access=py_trees.common.Access.READ)

    # No node wrote a status: the BT failed somewhere that records nothing,
    # so the payload was not processed (fail closed).
    try:
        status = InboxOutcomeStatus(result_bb.inbox_outcome_status)
    except KeyError:
        status = InboxOutcomeStatus.REJECTED

    try:
        context_id: str | None = result_bb.inbox_context_id
    except KeyError:
        context_id = None

    try:
        failure_reason: str | None = result_bb.inbox_failure_reason
    except KeyError:
        failure_reason = None

    try:
        unhandled = bool(result_bb.inbox_unhandled)
    except KeyError:
        unhandled = False

    try:
        activity_id: str | None = result_bb.inbox_event.activity_id
    except KeyError:
        # Rejected before extraction: there is no event to name.
        activity_id = None

    return InboxOutcome(
        status=status,
        context_id=context_id,
        activity_id=activity_id,
        failure_reason=failure_reason,
        unhandled=unhandled,
    )


def _restore_inbox_keys(
    storage: dict[str, Any],
    saved: dict[str, KeyState],
) -> None:
    """Restore inbox blackboard keys to their pre-execution state (#3534)."""
    restore_keys(storage, saved)


def process_payload(
    payload: dict[str, Any] | bytes | str | Any,
    ingress_adapter: IngressPayloadAdapter,
    dispatch_adapter: DispatchAdapter,
    queue_port: PendingCaseQueuePort | None = None,
    actor_config: ActorConfig | None = None,
    dereference_port: ObjectDereferencePort | None = None,
    received_outcome_port: ReceivedOutcomePort | None = None,
    *,
    arrived_at: datetime,
) -> InboxOutcome:
    """Process one inbox payload through the BT pipeline.

    The processing of one delivery is one act (ADR-0176): it takes the tree
    lock, and its tree runs carry the message's arrival stamp *arrived_at* as
    ``/at`` until it returns.  No clock is read here: the inbox stamped the
    message when it arrived, before it queued for the lock, so a backlog
    does not move the instant the message is judged at.  A held activity
    replayed later is processed by a call of its own, at the arrival stamp
    its held record carries, even when that call is nested in the
    processing of the delivery that released it.

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
        actor_config: The receiving actor's configuration; its RSVP
            windows govern inbound embargo invites (EP-07-001, EP-07-002).
            ``None`` applies the protocol defaults.
        dereference_port: Optional fetch-and-defer port.  When provided,
            an activity naming an object the receiver must fetch first waits
            on the fetch instead of being processed without it (AKM-05-007).
        received_outcome_port: Optional port that moves the received record
            to its final outcome stage.  When provided, a refused delivery's
            body is given up for a receipt stub (CLP-10-018, ADR-0154); both
            production pipelines provide it, and without it a refused body is
            over-retained rather than lost.
        arrived_at: The message's arrival stamp, read once from the act
            clock when it arrived (``stamp_arrival``), or carried by the held
            record a replay is rebuilt from.  The act's instant.

    Returns:
        :class:`InboxOutcome` whose ``status`` is an
        :class:`InboxOutcomeStatus` member, derived from the handler's
        ``HandlerResult`` when dispatch ran (IO-01-006).
    """
    # The shared BT global lock serialises BT blackboard access
    # across concurrent FastAPI BackgroundTasks.  The RLock supports
    # re-entrant acquisition so replay paths calling process_payload
    # recursively do not deadlock.  The instant is the arrival stamp, read
    # before the message queued for the lock, so time spent queueing is
    # charged to the receiver, never to the sender (ADR-0176).
    with open_received_act(arrived_at) as at, act_instant_in_tree_run(at):
        storage = py_trees.blackboard.Blackboard.storage
        saved = _save_inbox_keys(storage)
        # Every run starts with no handler verdict.  A nested run (the replay
        # a case bootstrap triggers runs inside the outer dispatch, after it
        # published its verdict) would otherwise inherit the outer run's, and
        # a dispatch of its own that raised would be settled by another
        # delivery's verdict instead of leaving its record alone
        # (CLP-10-074).  The snapshot above restores it on the way out.
        for alias in key_aliases(KEY_DISPOSITION):
            storage.pop(alias, None)

        try:
            _write_inbox_inputs(
                payload,
                ingress_adapter,
                dispatch_adapter,
                queue_port,
                dereference_port,
                received_outcome_port,
            )
            _run_bt_pipeline(actor_config)
            outcome = _read_inbox_outcome()
        finally:
            _restore_inbox_keys(storage, saved)

    logger.debug(
        "process_payload: outcome status=%s context_id=%s",
        outcome.status,
        outcome.context_id,
    )
    return outcome
