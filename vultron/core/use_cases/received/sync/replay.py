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

"""Received use cases for a peer's request to replay ledger entries.

The ``Reject`` (hash-chain rejection reply) and ``Read`` of a
``CaseLedgerEntry`` both ask the CASE_MANAGER for the entries the peer lacks
(LedgerReconciliation; SYNC-04-001, SYNC-04-002, SYNC-17-002 through
SYNC-17-006).
"""

import logging
from typing import ClassVar

import py_trees

from vultron.core.behaviors.case.received_run import (
    OutcomeReader,
    ReceivedOutcome,
    find_node,
    node_failed,
    run_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sync.nodes.ledger_position import (
    PeerActiveParticipantNode,
)
from vultron.core.behaviors.sync.nodes.position_statement import (
    CheckStatedPositionInLedgerNode,
)
from vultron.core.behaviors.sync.read_tree import create_read_log_entry_tree
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)
from vultron.core.models.events.sync import (
    ReadLogEntryReceivedEvent,
    RejectLogEntryReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases.received._bt_verdict import (
    case_manager_verdict,
)

logger = logging.getLogger(__name__)


class _LedgerReplayRequestUseCase:
    """What the ``Reject`` and ``Read`` of a ``CaseLedgerEntry`` share.

    Both ask the CASE_MANAGER, in their own words, for the entries a peer
    lacks, and both are answered by one tree run against the receiver's own
    store (CLP-10-005); this holds the ports and the run, whose verdict
    only the CASE_MANAGER may act on.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        sync_port: SyncActivityPort | None,
        trigger_activity: TriggerActivityPort | None,
        wire_render_port: WireRenderPort | None,
    ) -> None:
        self._dl = dl
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port

    def _run(
        self,
        tree: py_trees.behaviour.Behaviour,
        request: RejectLogEntryReceivedEvent | ReadLogEntryReceivedEvent,
        case_id: str,
        *,
        label: str,
        reader: OutcomeReader | None = None,
    ) -> HandlerResult:
        """Run *tree* once for *request* and read its verdict.

        Only the CASE_MANAGER answers a replay request; a replica that
        receives one was misaddressed (SYNC-03-005, HP-01-005).
        """
        verdict = run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label=label,
            sync_port=self._sync_port,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            reader=reader,
        )
        return case_manager_verdict(tree, verdict, self._dl, case_id)


class RejectLedgerEntryReceivedUseCase(_LedgerReplayRequestUseCase):
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
    stops at the entries recording its own closure (CM-23-031, CM-23-048).

    Spec: SYNC-03-001, SYNC-03-002, SYNC-03-005, SYNC-04-001, SYNC-04-002,
    CM-23-018, CM-23-020, CM-23-048, CM-23-055.
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
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        super().__init__(dl, sync_port, trigger_activity, wire_render_port)
        self._request = request

    def execute(self) -> HandlerResult:
        request = self._request
        # The rejected entry's case, or, for the Reject that names no entry
        # because the peer holds none, the case it names as its target; the
        # parser admits that form only with a position naming no entry, so
        # it asks for a replay from genesis (SYNC-16-027).
        case_id = request.rejected_case_id
        if case_id is None:
            logger.warning(
                "sync: received REJECT_CASE_LEDGER_ENTRY from '%s' "
                "naming neither a log entry nor a case — refusing",
                request.actor_id,
            )
            return HandlerResult.refused(
                "Reject(CaseLedgerEntry) names neither a log entry nor a case"
            )

        logger.info(
            "sync: received Reject(CaseLedgerEntry) from peer '%s' "
            "for case '%s', last_accepted_hash=%.16s…",
            request.actor_id,
            case_id,
            request.last_accepted_hash,
        )
        tree = create_reject_log_entry_tree(
            case_id, sender_rule=self.sender_entitlement
        )
        return self._run(
            tree, request, case_id, label="RejectLogEntryReceivedBT"
        )


class ReadLedgerEntryReceivedUseCase(_LedgerReplayRequestUseCase):
    """The CASE_MANAGER answers a participant's stated ledger position.

    A ``Read(CaseLedgerEntry)`` names the last canonical entry its sender has
    applied for the case (SYNC-17-001, ADR-0155).  The read tree
    (``create_read_log_entry_tree``) checks the position is one the
    CASE_MANAGER's ledger holds, records the entry's hash as the sender's
    acknowledged position, and replays every entry after it under the replay
    rate bound and the outbox de-duplication (SYNC-17-003, SYNC-17-004).

    The sender standing is ``PARTICIPANT``: an actor off the roster, or a
    participant whose closure the case records, is refused at the door
    (CM-23-018, CM-23-020).  Any other participant's held position has the
    CASE_MANAGER resend each Invite it still owes an answer to, whether or
    not it is active (SYNC-20-001, ADR-0163).  Only an active participant's
    position is then recorded and answered (SYNC-17-002): an inert sender is
    ``REFUSED`` with no replication state recorded and no entry replayed, as
    is any receiver that is not the case's CASE_MANAGER (HP-01-005,
    HP-01-006).  A position the ledger does not hold is logged at WARNING
    and ``REFUSED``, with nothing recorded or sent (SYNC-17-005).  No ledger
    entry is committed either way (SYNC-17-006, SYNC-20-007).

    Spec: SYNC-17-002 through SYNC-17-006, SYNC-04-001, SYNC-15-003,
    SYNC-15-012, SYNC-15-013, SYNC-20-001.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ReadLogEntryReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        super().__init__(dl, sync_port, trigger_activity, wire_render_port)
        self._request = request

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.replay_case_id
        if case_id is None:
            logger.warning(
                "sync: received READ_CASE_LEDGER_ENTRY '%s' from '%s' naming"
                " no case in its context — refusing",
                request.activity_id,
                request.actor_id,
            )
            return HandlerResult.refused(
                "Read(CaseLedgerEntry) names no case in its context"
            )

        position = request.ledger_position
        logger.info(
            "sync: received Read(CaseLedgerEntry) '%s' from peer '%s' for"
            " case '%s', stated position log_index=%d entry_hash=%.16s…",
            request.activity_id,
            request.actor_id,
            case_id,
            position.log_index,
            position.entry_hash,
        )
        tree = create_read_log_entry_tree(
            case_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        return self._run(
            tree,
            request,
            case_id,
            label="ReadLogEntryReceivedBT",
            reader=_read_reading,
        )


def _read_reading(outcome: ReceivedOutcome) -> HandlerResult | None:
    """Name the check a failed ``ReadLogEntryReceivedBT`` run ended at.

    A position the ledger does not hold fails the position check, which
    already logged it at WARNING (SYNC-17-005); it is refused with that
    reason.  An inert sender fails the active check after its owed Invites
    were resent, and is refused (SYNC-17-002, SYNC-20-001).  ``None`` for
    any other run, which the runner reads.
    """
    tree = outcome.tree
    if node_failed(tree, CheckStatedPositionInLedgerNode):
        check = find_node(tree, CheckStatedPositionInLedgerNode)
        assert check is not None  # it ran: node_failed found it
        return HandlerResult.refused(
            f"{check.feedback_message}; nothing recorded or sent (SYNC-17-005)"
        )
    if node_failed(tree, PeerActiveParticipantNode):
        active = find_node(tree, PeerActiveParticipantNode)
        assert active is not None  # it ran: node_failed found it
        return HandlerResult.refused(
            f"{active.feedback_message}; no replication state recorded and"
            " no entry replayed (SYNC-17-002)"
        )
    return None
