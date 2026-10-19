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
from typing import ClassVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import sender_guard_refused
from vultron.core.behaviors.sync.announce_tree import (
    AT_CASE_MANAGER,
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes import (
    BufferOutOfOrderEntryNode,
    BufferPreGenesisEntryNode,
    CheckHashMatchesNode,
    CheckLedgerEntryAlreadyStoredNode,
    ReconstructChainTailNode,
    SendRejectLogEntryNode,
)
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoChangeFromLedgerNode,
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
    resolve_ledger_gap_buffer,
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
from vultron.core.ports.inbox_hand_back import InboxHandBackPort
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    door_refusal,
    named_node_status,
    node_failed,
    node_succeeded,
    not_case_manager_refusal,
    verdict_from_bt,
)

logger = logging.getLogger(__name__)


def _run_announce_bt(
    dl: CaseOutboxPersistence,
    request: AnnounceLogEntryReceivedEvent,
    receiving_actor_id: str,
    gap_buffer: LedgerGapBuffer | None,
    sync_port: SyncActivityPort | None,
    wire_render_port: WireRenderPort | None,
    inbox_hand_back: InboxHandBackPort | None,
) -> tuple[py_trees.behaviour.Behaviour, BTExecutionResult]:
    """Run the announce receive BT for *request* with the gap buffer wired.

    The tree hands a buffered successor back to the inbox through
    *inbox_hand_back* rather than running it here (SYNC-14-009).  Returns the
    tree along with the result so the caller can tell which branch decided
    the outcome (#2255).
    """
    tree = create_announce_log_entry_tree(
        sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
    )
    result = BTBridge(
        datalayer=dl,
        wire_render_port=wire_render_port,
        sync_port=sync_port,
    ).execute_with_setup(
        tree=tree,
        actor_id=receiving_actor_id,
        activity=request,
        gap_buffer=gap_buffer,
        inbox_hand_back=inbox_hand_back,
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
        # Past the sender guard, an announcement the CASE_MANAGER admits is
        # its own (SYNC-13-006).
        if named_node_status(tree, AT_CASE_MANAGER) is Status.SUCCESS:
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
    if any(
        isinstance(node, ApplyEmbargoChangeFromLedgerNode)
        and node.refused_into_gap
        for node in tree.iterate()
    ):
        return HandlerResult.deferred(
            f"ledger entry '{entry.id_}' does not apply to this replica's"
            f" case '{entry.case_id}'; held in the gap buffer, never patched"
            " over (ADR-0124)"
        )
    if node_succeeded(tree, BufferPreGenesisEntryNode):
        return HandlerResult.deferred(
            f"ledger entry '{entry.id_}' buffered until case"
            f" '{entry.case_id}' is seeded (SYNC-15-004)"
        )
    if sender_guard_refused(tree):
        return HandlerResult.refused(
            f"sender '{request.actor_id}' is not the CASE_MANAGER of case"
            f" '{entry.case_id}', so its announcement of ledger entry"
            f" '{entry.id_}' is not accepted (SYNC-13-006, HP-01-006)"
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


class AnnounceLedgerEntryReceivedUseCase:
    """Process a received ``Announce(CaseLedgerEntry)`` activity.

    Validates the incoming entry against the local hash-chain tail and
    persists it if the chain is consistent.  On mismatch, sends a
    ``Reject(CaseLedgerEntry)`` back to the CaseActor carrying the local
    tail hash (SYNC-03-001).

    When *pending_assertions* is provided (or resolved from the per-actor
    registry), clears the matching pending assertion on receipt so that
    future emits for the same ``(case_id, semantic_type, log_object_id)``
    triple are no longer suppressed (SYNC-11-003).

    Out-of-order delivery is tolerated: a received entry whose predecessor has
    not yet arrived is held in an actor-local
    :class:`~vultron.core.models.ledger_gap_buffer.LedgerGapBuffer` rather than
    dropped.  Once the entry that closes the gap is committed, the tree hands
    the buffered successor back to this actor's inbox through the injected
    :class:`~vultron.core.ports.inbox_hand_back.InboxHandBackPort`, as an
    ``Announce(CaseLedgerEntry)`` from the case's CASE_MANAGER and a delivery
    of its own; that delivery's tree hands back the next one.  This makes
    convergence independent of ``Announce`` delivery order (issue #1556,
    SYNC-10-004) while each delivery still runs exactly one tree
    (SYNC-14-009, CLP-10-005).

    Spec: SYNC-02-003, SYNC-03-001 through SYNC-03-003, SYNC-10-004,
    SYNC-11-003, SYNC-12-001, SYNC-14-009.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.CASE_MANAGER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AnnounceLogEntryReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        pending_assertions: PendingAssertionStore | None = None,
        gap_buffer: LedgerGapBuffer | None = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        inbox_hand_back: InboxHandBackPort | None = None,
    ) -> None:
        self._dl = dl
        self._inbox_hand_back = inbox_hand_back
        # The received baseline supplies the trigger port to every use case;
        # this one runs no tree that builds an activity, so it is unused.
        del trigger_activity
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
        gap_buffer = resolve_ledger_gap_buffer(
            self._gap_buffer, request.receiving_actor_id
        )

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
            self._inbox_hand_back,
        )

        # A copy the door guards refused (an unaddressed one, HP-01-005, or a
        # closed case, CM-23-013) acts on nothing: the pending assertion it
        # does not confirm stays pending.
        if (refusal := door_refusal(tree)) is not None:
            logger.warning(
                "sync: refused log-entry announcement '%s': %s",
                request.activity_id,
                refusal.reason,
            )
            return refusal

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

        # Clear pending assertion for this entry whatever the tree decided
        # past its door guards (SYNC-11-003): a canonical ledger entry
        # confirms the assertion has been processed by the log authority.
        store = self._pending_assertions
        if store is None and request.receiving_actor_id:
            store = get_pending_assertion_store(request.receiving_actor_id)
        if store is not None:
            store.clear(
                entry.case_id,
                entry.semantic_type,
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

    Only an active participant's rejection is acted on, and only at the
    case's CASE_MANAGER: any other receiver reports ``REFUSED`` and sends
    nothing (SYNC-03-005, HP-01-005).  A participant at RM ``CLOSED`` keeps
    this one act, so the use case declares the ``LEDGER_PEER`` standing, not
    ``ACTIVE_PARTICIPANT``: its rejection is answered with a replay that
    stops at the entries recording its own closure (CM-23-004, CM-23-018).

    Spec: SYNC-03-001, SYNC-03-002, SYNC-03-005, SYNC-04-001, SYNC-04-002,
    CM-23-018.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.LEDGER_PEER
    )

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
        tree = create_reject_log_entry_tree(
            rejected_entry.case_id, sender_rule=self.sender_entitlement
        )
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
        if verdict.disposition is HandlerDisposition.APPLIED:
            # Only the CASE_MANAGER answers a rejection; a replica that
            # receives one was misaddressed (SYNC-03-005, HP-01-005).
            refusal = not_case_manager_refusal(
                tree, self._dl, rejected_entry.case_id
            )
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "sync: could not act on Reject(CaseLedgerEntry) '%s': %s",
                request.activity_id,
                verdict.reason,
            )
        return verdict
