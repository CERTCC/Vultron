"""Use case for received Create(ProcessingFault) NACK messages.

A sender receives this when a receiver could not process its activity
(ADR-0080, ASK-07-001).  The response depends on the fault's failure class:
a replica's case-diverged fault makes the CASE_MANAGER re-seed it
(SYNC-16-003, ADR-0142); a replica's hash-mismatch fault is logged at ERROR
beside a re-check of the CASE_MANAGER's own copy (SYNC-03-010); every other
class is archived and skipped until the
outstanding-request register correlates it to its ask (#2883).
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

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

import py_trees

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.intake_only_received_tree import (
    create_intake_only_received_tree,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    ClearRefusedAssertionNode,
)
from vultron.core.behaviors.case.refusal_notice_received_tree import (
    refusal_notice_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)
from vultron.core.behaviors.sync.divergence_tree import (
    create_case_diverged_fault_tree,
)
from vultron.core.behaviors.sync.hash_mismatch_tree import (
    create_hash_mismatch_fault_tree,
)
from vultron.core.behaviors.sync.nodes.hash_mismatch import (
    ReportHashMismatchNode,
)
from vultron.core.behaviors.sync.nodes.reseed import (
    ReseedPeerNode,
    announced_ledger_entry,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.fault import (
    CreateProcessingFaultReceivedEvent,
    RefusalNoticeReceivedEvent,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    case_manager_verdict,
    door_refusal,
    find_node,
    verdict_from_bt,
)
from vultron.errors import VultronBTInternalError, VultronNotFoundError

logger = logging.getLogger(__name__)


#: Builds the one tree a fault's delivery runs, from the entry the fault
#: reports refusing (``None`` when it names none this store sent), the
#: received fault and the use case's declared sender rule.
type FaultTreeBuilder = Callable[
    [
        CaseLedgerEntry | None,
        CreateProcessingFaultReceivedEvent,
        SenderRule,
    ],
    py_trees.behaviour.Behaviour,
]

#: Reads the verdict of a finished run, given the tree, its result, the
#: store and the entry the tree was built from.
type FaultVerdictReader = Callable[
    [
        py_trees.behaviour.Behaviour,
        BTExecutionResult,
        CasePersistence,
        CaseLedgerEntry | None,
    ],
    HandlerResult,
]


@dataclass(frozen=True)
class FaultResponse:
    """How the receiver answers a fault of one failure class.

    ``build_tree`` builds the delivery's one tree (CLP-10-005);
    ``read_verdict`` turns its run into the handler's verdict (HP-01-003).
    """

    build_tree: FaultTreeBuilder
    read_verdict: FaultVerdictReader
    reads_refused_entry: bool = True
    """Whether the response needs the entry the fault reports refusing."""


def _archive_tree(
    refused_entry: CaseLedgerEntry | None,
    fault: CreateProcessingFaultReceivedEvent,
    rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """The intake-only tree: a fault with no effect is only archived."""
    del refused_entry, fault, rule  # nothing here depends on them
    return create_intake_only_received_tree("CreateProcessingFaultReceivedBT")


def _archive_verdict(
    tree: py_trees.behaviour.Behaviour,
    result: BTExecutionResult,
    dl: CasePersistence,
    refused_entry: CaseLedgerEntry | None,
) -> HandlerResult:
    """``SKIPPED``: nothing correlates the fault to its ask yet (#2883)."""
    del dl, refused_entry
    verdict = applied_or_raise(
        tree, result, label="CreateProcessingFaultReceivedBT"
    )
    if verdict.disposition is HandlerDisposition.REFUSED:
        return verdict  # a door guard refused: the case is fully closed
    return HandlerResult.skipped(
        "ask-register correlation not implemented (#2883)"
    )


def _unnamed_entry_refusal(
    tree: py_trees.behaviour.Behaviour,
    result: BTExecutionResult,
    *,
    label: str,
    answer: str,
    spec_id: str,
) -> HandlerResult:
    """The refusal of a fault that names no ``Announce(CaseLedgerEntry)``
    this actor sent: there is no case to *answer* for.

    *spec_id* is the requirement of the response that cannot run.  A door
    guard's own refusal is kept, since it names the closer cause.
    """
    if (refusal := door_refusal(tree)) is not None:
        return refusal
    applied_or_raise(tree, result, label=label)
    return HandlerResult.refused(
        "the fault names no Announce(CaseLedgerEntry) this actor sent, so it"
        f" names no case to {answer} ({spec_id}, ASK-07-004)"
    )


def _case_diverged_tree(
    refused_entry: CaseLedgerEntry | None,
    fault: CreateProcessingFaultReceivedEvent,
    rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    return create_case_diverged_fault_tree(
        refused_entry, sender_id=fault.actor_id, sender_rule=rule
    )


def _reseed_verdict(
    tree: py_trees.behaviour.Behaviour,
    result: BTExecutionResult,
    dl: CasePersistence,
    refused_entry: CaseLedgerEntry | None,
) -> HandlerResult:
    """The verdict on a case-diverged fault (SYNC-16-003, SYNC-16-004).

    ``APPLIED`` when a case copy was queued; ``SKIPPED`` when the re-seed
    cooldown held it back; ``REFUSED`` for a fault that names no
    ``Announce(CaseLedgerEntry)`` this actor sent, for a sender that is not
    an active participant, and at any receiver that is not the case's
    CASE_MANAGER (HP-01-005).
    """
    label = "CaseDivergedFaultReceivedBT"
    if refused_entry is None:
        return _unnamed_entry_refusal(
            tree, result, label=label, answer="re-seed", spec_id="SYNC-16-003"
        )
    verdict = case_manager_verdict(
        tree,
        verdict_from_bt(tree, result, label=label),
        dl,
        refused_entry.case_id,
    )
    if verdict.disposition is not HandlerDisposition.APPLIED:
        return verdict
    reseed = find_node(tree, ReseedPeerNode)
    if reseed is None:
        raise VultronBTInternalError(f"{label}: tree has no re-seed node")
    if reseed.reseeded:
        return verdict
    if reseed.withheld:
        # Unreachable behind the ACTIVE_PARTICIPANT sender guard, which asks
        # the same predicate; refused the same way if it is ever reached.
        return HandlerResult.refused(
            f"the sender is not an active participant of case"
            f" '{refused_entry.case_id}'; no case copy sent (CM-10-004)"
        )
    return HandlerResult.skipped(
        f"the sender was re-seeded with case '{refused_entry.case_id}'"
        " within the cooldown; no case copy sent (SYNC-16-004)"
    )


def _hash_mismatch_tree(
    refused_entry: CaseLedgerEntry | None,
    fault: CreateProcessingFaultReceivedEvent,
    rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    return create_hash_mismatch_fault_tree(
        refused_entry,
        announce_id=fault.failed_activity_id,
        sender_id=fault.actor_id,
        sender_rule=rule,
    )


def _hash_mismatch_verdict(
    tree: py_trees.behaviour.Behaviour,
    result: BTExecutionResult,
    dl: CasePersistence,
    refused_entry: CaseLedgerEntry | None,
) -> HandlerResult:
    """The verdict on a hash-mismatch fault (SYNC-03-008, SYNC-03-010).

    ``SKIPPED`` once the CASE_MANAGER has logged the fault and checked its
    own copy, since nothing changes; ``REFUSED`` for a fault that names no
    ``Announce(CaseLedgerEntry)`` this actor sent, for a sender that is not
    an active participant, and at any receiver that is not the case's
    CASE_MANAGER (HP-01-005).
    """
    label = "HashMismatchFaultReceivedBT"
    if refused_entry is None:
        return _unnamed_entry_refusal(
            tree,
            result,
            label=label,
            answer="report on",
            spec_id="SYNC-03-008",
        )
    verdict = case_manager_verdict(
        tree,
        verdict_from_bt(tree, result, label=label),
        dl,
        refused_entry.case_id,
    )
    if verdict.disposition is not HandlerDisposition.APPLIED:
        return verdict
    report = find_node(tree, ReportHashMismatchNode)
    if report is None or report.own_copy is None:
        raise VultronBTInternalError(
            f"{label}: the run did not check this actor's own copy"
        )
    return HandlerResult.skipped(
        f"hash mismatch on ledger entry '{refused_entry.id_}' logged; own"
        f" copy {report.own_copy.value}; nothing is sent, re-seeded or"
        " recorded for it (SYNC-03-008)"
    )


#: A failure class with no entry in a use case's ``responses``.
ARCHIVE_ONLY = FaultResponse(
    build_tree=_archive_tree,
    read_verdict=_archive_verdict,
    reads_refused_entry=False,
)


class CreateProcessingFaultReceivedUseCase:
    """Answer a received ``Create(ProcessingFault)`` by its failure class.

    Every fault is logged at WARNING, naming its sender, class and failed
    activity.  The response is then chosen by the fault's class, one
    :class:`FaultResponse` in :attr:`responses` per class that has an effect:

    - ``LedgerEntryRefused/CaseDiverged`` — at the case's CASE_MANAGER,
      re-seed the replica with ``Announce(VulnerabilityCase)`` of the current
      case, rate-bounded per peer, ledgering nothing (SYNC-16-002,
      SYNC-16-003, SYNC-16-004, SYNC-16-008).
    - ``LedgerEntryRefused/HashMismatch`` — at the case's CASE_MANAGER, log
      the fault at ERROR and re-check its own stored copy of the named entry,
      changing nothing and reporting ``SKIPPED``: neither a replay nor a
      re-seed can heal a hash mismatch (SYNC-03-008, SYNC-03-010).

    A class with no entry is only archived, as every received tree archives
    what arrived (CLP-10-018), and reports ``SKIPPED``: correlating it to the
    ask it answers is #2883 (:data:`ARCHIVE_ONLY`).  A new class's effect is
    a new entry; ``execute`` builds and runs exactly one tree whatever the
    class (CLP-10-005).

    A fault carries no case (ASK-07-006).  When its ``inReplyTo`` names an
    ``Announce(CaseLedgerEntry)`` this actor sent, the entry that announce
    carried is read from this store and handed to the response, so the case
    is the entry's.

    The sender rule is declared once, below, and the receive-tree factory
    composes it into the tree of every class that has an effect: at the
    CASE_MANAGER the sender must be an active participant of the case the
    fault concerns (CM-10-004, SYNC-16-003), and at a participant the fault
    must come from the CASE_MANAGER (PCR-03-001).  A class that is only
    archived runs no guard, because nothing it does is gated on a sender's
    standing.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    #: The response to each failure class that has an effect.
    responses: ClassVar[Mapping[str, FaultResponse]] = MappingProxyType(
        {
            VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED: FaultResponse(
                build_tree=_case_diverged_tree, read_verdict=_reseed_verdict
            ),
            VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH: FaultResponse(
                build_tree=_hash_mismatch_tree,
                read_verdict=_hash_mismatch_verdict,
            ),
        }
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateProcessingFaultReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._request = request

    def execute(self) -> HandlerResult:
        request = self._request
        logger.warning(
            "ProcessingFault received from '%s': failed activity '%s'"
            " (failure class: '%s', fault: '%s', carried by Create: '%s')",
            request.actor_id,
            # A fault may omit inReplyTo; say so rather than print 'None'.
            request.failed_activity_id or "<not named: no inReplyTo>",
            request.failure_class,
            request.fault_id,
            request.activity_id,
        )
        response = self.responses.get(request.failure_class, ARCHIVE_ONLY)
        refused_entry = (
            self._refused_entry() if response.reads_refused_entry else None
        )
        tree = response.build_tree(
            refused_entry, request, self.sender_entitlement
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = response.read_verdict(tree, result, self._dl, refused_entry)
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "ProcessingFault '%s' from '%s' refused: %s",
                request.fault_id,
                request.actor_id,
                verdict.reason,
            )
        return verdict

    def _refused_entry(self) -> CaseLedgerEntry | None:
        """The entry the fault's ``inReplyTo`` announce carried, if this
        store sent it; read-only."""
        failed_id = self._request.failed_activity_id
        if failed_id is None:
            return None
        try:
            return announced_ledger_entry(
                self._dl,
                failed_id,
                resolve_receiving_actor_id(
                    self._dl, self._request.receiving_actor_id
                ),
            )
        except VultronNotFoundError:
            return None


class RefusalNoticeReceivedUseCase:
    """Read the CASE_MANAGER's refusal notice for an activity this actor sent.

    The notice is a ``Reject`` of the refused activity, inline (CLP-05-001,
    ADR-0141).  Only the case's CASE_MANAGER sends one, so any other sender,
    and any notice reaching the CASE_MANAGER itself, is refused (HP-01-006).
    From the CASE_MANAGER, the participant closes the pending assertion it
    recorded for the refused activity (CLP-06-006) and logs the refusal at
    WARNING; it writes no case state and re-sends nothing (CLP-06-005).

    ``APPLIED`` when a pending entry was closed; ``SKIPPED`` when none was
    pending (timed out, or never recorded), since nothing changes.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_participant=any_of(SenderEntitlementKind.CASE_MANAGER)
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: RefusalNoticeReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._wire_render_port = wire_render_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        tree = refusal_notice_received_tree(
            case_id=request.case_id,
            refused_activity_id=request.refused_activity_id,
            reason=request.reason,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="RefusalNoticeReceivedBT"
        )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            return verdict
        clear = find_node(tree, ClearRefusedAssertionNode)
        if clear is not None and clear.cleared:
            return verdict
        return HandlerResult.skipped(
            f"refusal notice for '{request.refused_activity_id}': no pending"
            " assertion to close"
        )
