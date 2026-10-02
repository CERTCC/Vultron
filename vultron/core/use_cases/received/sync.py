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
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Received use cases for LedgerFanout/LedgerReconciliation: accept or reject inbound log-entry
announcements, and handle hash-chain rejection replies.

Spec: SYNC-02-003, SYNC-03-001 through SYNC-03-003, SYNC-04-001, SYNC-04-002.
"""

import logging

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes import (
    BufferOutOfOrderEntryNode,
    BufferPreGenesisEntryNode,
    CheckHashMatchesNode,
    CheckLedgerEntryAlreadyStoredNode,
    ReconstructChainTailNode,
    SendRejectLogEntryNode,
    VerifySenderIsCaseActorNode,
    VerifySenderIsOwnIdNode,
)
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.sync import (
    AnnounceLogEntryReceivedEvent,
    RejectLogEntryReceivedEvent,
)
from vultron.core.models.ledger_gap_buffer import (
    LedgerGapBuffer,
    get_ledger_gap_buffer,
)
from vultron.core.models.pending_assertion import (
    PendingAssertionStore,
    get_pending_assertion_store,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.sync_helpers import _reconstruct_tail_hash
from vultron.core.use_cases._helpers import (
    _find_case_actor_id,
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    node_failed,
    node_succeeded,
    verdict_from_bt,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


def _run_announce_bt(
    dl: CaseOutboxPersistence,
    request: AnnounceLogEntryReceivedEvent,
    receiving_actor_id: str,
    gap_buffer: LedgerGapBuffer | None,
    sync_port: SyncActivityPort | None,
    wire_render_port: WireRenderPort | None = None,
) -> tuple[py_trees.behaviour.Behaviour, BTExecutionResult]:
    """Run the announce receive BT for *request* with the gap buffer wired.

    Returns the tree along with the result so the caller can tell which
    branch decided the outcome (#2255).
    """
    tree = create_announce_log_entry_tree()
    result = BTBridge(
        datalayer=dl,
        wire_render_port=wire_render_port,
        sync_port=sync_port,
    ).execute_with_setup(
        tree=tree,
        actor_id=receiving_actor_id,
        activity=request,
        gap_buffer=gap_buffer,
    )
    return tree, result


def _announce_verdict(
    tree: py_trees.behaviour.Behaviour,
    result: BTExecutionResult,
    request: AnnounceLogEntryReceivedEvent,
    entry: CaseLedgerEntry,
) -> HandlerResult:
    """Classify a finished ``AnnounceLogEntryReceivedBT`` run (HP-01-003).

    ``SendRejectLogEntryNode`` always returns ``FAILURE`` after it sends, so a
    completed reject marks an entry this replica answered with ``Reject``.
    """
    verdict = verdict_from_bt(tree, result, label="AnnounceLogEntryReceivedBT")
    if verdict.disposition is HandlerDisposition.APPLIED:
        if node_succeeded(tree, VerifySenderIsOwnIdNode):
            return HandlerResult.skipped(
                f"own announcement of ledger entry '{entry.id_}' echoed back;"
                " delivery confirmed"
            )
        if node_succeeded(tree, CheckLedgerEntryAlreadyStoredNode):
            return HandlerResult.skipped(
                f"ledger entry '{entry.id_}' already stored"
            )
        return verdict
    if verdict.disposition is not HandlerDisposition.REFUSED:
        return verdict
    return _refused_announce_verdict(tree, request, entry) or verdict


def _refused_announce_verdict(
    tree: py_trees.behaviour.Behaviour,
    request: AnnounceLogEntryReceivedEvent,
    entry: CaseLedgerEntry,
) -> HandlerResult | None:
    """Name why a failed announce run failed, or ``None`` for the default."""
    if node_succeeded(tree, BufferOutOfOrderEntryNode):
        return HandlerResult.deferred(
            f"ledger entry '{entry.id_}' (log_index={entry.log_index})"
            " buffered until its predecessor arrives (SYNC-14-001)"
        )
    if node_succeeded(tree, BufferPreGenesisEntryNode):
        return HandlerResult.deferred(
            f"ledger entry '{entry.id_}' buffered until case"
            f" '{entry.case_id}' is seeded (SYNC-15-004)"
        )
    if node_failed(tree, VerifySenderIsOwnIdNode):
        return HandlerResult.refused(
            f"CASE_MANAGER does not accept an announcement of ledger entry"
            f" '{entry.id_}' from '{request.actor_id}'"
        )
    if node_failed(tree, VerifySenderIsCaseActorNode):
        return HandlerResult.refused(
            f"sender '{request.actor_id}' is not the CaseActor for case"
            f" '{entry.case_id}' (SYNC-13-006)"
        )
    if node_failed(tree, SendRejectLogEntryNode):
        if node_failed(tree, ReconstructChainTailNode):
            return HandlerResult.refused(
                f"case '{entry.case_id}' is not seeded here; Reject sent for"
                " replay from genesis (SYNC-15-001)"
            )
        if node_failed(tree, CheckHashMatchesNode):
            return HandlerResult.refused(
                f"ledger entry '{entry.id_}' does not extend the local chain"
                " tail; Reject sent (SYNC-03-001)"
            )
    return None


def drain_gap_buffer(
    dl: CaseOutboxPersistence,
    case_id: str,
    receiving_actor_id: str,
    gap_buffer: LedgerGapBuffer,
    sync_port: SyncActivityPort | None = None,
    wire_render_port: WireRenderPort | None = None,
) -> None:
    """Apply buffered entries that now extend the local chain, in order.

    After each committed entry, look up the buffered successor keyed by the new
    tail hash and run the announce BT on it — reusing the exact
    effects-before-persist path (SYNC-12-001).  Cascades until no buffered entry
    extends the current tail.  A drained entry that fails to apply is re-buffered
    so a later retry (or CaseActor replay) can pick it up.

    This is the shared drain used both by the ``Announce(CaseLedgerEntry)``
    receive path (draining forward gaps once a predecessor lands, SYNC-10-004)
    and by the ``VulnerabilityCase`` seed path (draining *pre-genesis* entries
    once the case — and therefore the deterministic per-case genesis hash — is
    present, SYNC-15-005 / #2186).  In the pre-genesis case the first
    reconstructed tail is ``(genesis_hash, -1)``, so a buffered genesis entry
    (``prev_log_hash == genesis_hash``) drains first and the rest cascade.

    A synthetic :class:`AnnounceLogEntryReceivedEvent` is constructed per drained
    entry so this function has no dependency on an inbound request being in
    flight; ``actor_id`` is resolved to the CaseActor when known, falling back to
    ``case_id``.
    """
    actor_id = _find_case_actor_id(dl, case_id) or case_id
    while True:
        try:
            tail_hash, _ = _reconstruct_tail_hash(case_id, dl)
        except VultronValidationError:
            # No genesis anchor yet — nothing can be drained.
            return
        successor = gap_buffer.take_next(case_id, tail_hash)
        if successor is None:
            return

        logger.info(
            "sync: draining buffered entry '%s' (log_index=%d) for case "
            "'%s' now that its predecessor has arrived",
            successor.id_,
            successor.log_index,
            case_id,
        )
        drain_event = AnnounceLogEntryReceivedEvent(
            activity_id=f"urn:vultron:sync:drain:{successor.id_}",
            actor_id=actor_id,
            receiving_actor_id=receiving_actor_id,
            object_=successor,
        )
        # _run_announce_bt delegates to BTBridge.execute_with_setup, which
        # classifies any node error into a FAILURE result rather than raising
        # (CONCERN-3019), so the FAILURE branch below owns re-buffering.  A raise
        # here would be an unclassified bridge-contract violation and must
        # surface loudly rather than be absorbed (CS-23-001).
        _, result = _run_announce_bt(
            dl,
            drain_event,
            receiving_actor_id,
            gap_buffer,
            sync_port,
            wire_render_port,
        )
        if result.status == Status.FAILURE and dl.read(successor.id_) is None:
            # Application failed and the entry was not persisted; hold it again
            # so a future arrival or CaseActor replay can retry.
            gap_buffer.buffer(successor)
            logger.warning(
                "sync: buffered entry '%s' failed to apply on drain — "
                "re-buffered pending retry",
                successor.id_,
            )
            return


class AnnounceLedgerEntryReceivedUseCase:
    """Process a received ``Announce(CaseLedgerEntry)`` activity.

    Validates the incoming entry against the local hash-chain tail and
    persists it if the chain is consistent.  On mismatch, sends a
    ``Reject(CaseLedgerEntry)`` back to the CaseActor carrying the local
    tail hash (SYNC-03-001).

    When *pending_assertions* is provided (or resolved from the per-actor
    registry), clears the matching pending assertion on receipt so that
    future emits for the same ``(case_id, event_type, log_object_id)``
    triple are no longer suppressed (SYNC-11-003).

    Out-of-order delivery is tolerated: a received entry whose predecessor has
    not yet arrived is held in an actor-local
    :class:`~vultron.core.models.ledger_gap_buffer.LedgerGapBuffer` rather than
    dropped, and buffered successors are drained in hash-chain order as soon as
    the entry that closes the gap is committed.  This makes convergence
    independent of ``Announce`` delivery order (issue #1556, SYNC-10-004).

    Spec: SYNC-02-003, SYNC-03-001 through SYNC-03-003, SYNC-10-004,
    SYNC-11-003, SYNC-12-001.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AnnounceLogEntryReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        pending_assertions: PendingAssertionStore | None = None,
        gap_buffer: LedgerGapBuffer | None = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request = request
        self._sync_port = sync_port
        self._pending_assertions = pending_assertions
        self._gap_buffer = gap_buffer

    def execute(self) -> HandlerResult:
        request = self._request
        entry = request.log_entry
        if entry is None:
            logger.warning(
                "sync: received ANNOUNCE_CASE_LEDGER_ENTRY activity '%s' "
                "with no log entry object — refusing",
                request.activity_id,
            )
            return HandlerResult.refused(
                "Announce(CaseLedgerEntry) carries no log entry"
            )

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        gap_buffer = self._gap_buffer
        if gap_buffer is None and request.receiving_actor_id:
            gap_buffer = get_ledger_gap_buffer(request.receiving_actor_id)

        logger.info(
            "sync: received log-entry announcement '%s' for case '%s' "
            "from actor '%s' (log_index=%d)",
            request.activity_id,
            entry.case_id,
            request.actor_id,
            entry.log_index,
        )
        tree, result = _run_announce_bt(
            self._dl,
            request,
            receiving_actor_id,
            gap_buffer,
            self._sync_port,
            self._wire_render_port,
        )

        # Whenever an entry is committed, its successor may already be waiting
        # in the gap buffer; drain the contiguous run keyed on the new tail
        # (SYNC-10-004).  Draining also runs after a mismatch, in case an
        # earlier-arrived predecessor is somehow already present.
        if gap_buffer is not None:
            drain_gap_buffer(
                self._dl,
                entry.case_id,
                receiving_actor_id,
                gap_buffer,
                self._sync_port,
                self._wire_render_port,
            )

        verdict = _announce_verdict(tree, result, request, entry)
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "sync: refused log-entry announcement '%s': %s",
                request.activity_id,
                verdict.reason,
            )
        elif verdict.disposition is HandlerDisposition.DEFERRED:
            logger.info(
                "sync: deferred log-entry announcement '%s': %s",
                request.activity_id,
                verdict.reason,
            )

        # Clear pending assertion for this entry regardless of BT outcome
        # (SYNC-11-003): a canonical ledger entry confirms the assertion has
        # been processed by the log authority.
        store = self._pending_assertions
        if store is None and request.receiving_actor_id:
            store = get_pending_assertion_store(request.receiving_actor_id)
        if store is not None:
            store.clear(
                entry.case_id,
                entry.event_type,
                entry.log_object_id,
            )
        return verdict


class RejectLedgerEntryReceivedUseCase:
    """CaseActor handles a participant's rejection of a log entry announcement.

    When a participant rejects an ``Announce(CaseLedgerEntry)`` because the
    ``prev_log_hash`` does not match their local tail, the CaseActor runs the
    reject tree (``create_reject_log_entry_tree``), whose nodes:

    1. Record the rejecting peer's last-acknowledged hash in its
       per-peer replication state — ``UpdateReplicationStateNode``
       (SYNC-04-001, SYNC-04-002).
    2. Replay all missing entries from after the last-accepted hash to the
       peer — ``SendMissingEntriesNode`` (SYNC-03-002).

    Spec: SYNC-03-001, SYNC-03-002, SYNC-04-001, SYNC-04-002.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectLogEntryReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        rejected_entry = request.rejected_entry
        if rejected_entry is None:
            logger.warning(
                "sync: received REJECT_CASE_LEDGER_ENTRY from '%s' "
                "with no log entry object — refusing",
                request.actor_id,
            )
            return HandlerResult.refused(
                "Reject(CaseLedgerEntry) carries no log entry"
            )

        logger.info(
            "sync: received Reject(CaseLedgerEntry) from peer '%s' "
            "for case '%s', last_accepted_hash=%.16s…",
            request.actor_id,
            rejected_entry.case_id,
            request.last_accepted_hash,
        )
        tree = create_reject_log_entry_tree()
        result = BTBridge(
            datalayer=self._dl,
            sync_port=self._sync_port,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="RejectLogEntryReceivedBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "sync: could not act on Reject(CaseLedgerEntry) '%s': %s",
                request.activity_id,
                verdict.reason,
            )
        return verdict
