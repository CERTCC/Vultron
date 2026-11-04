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

"""The response a received ProcessingFault gets, per failure class.

A replica's case-diverged fault makes the CASE_MANAGER re-seed it
(SYNC-16-003, ADR-0142); a replica's hash-mismatch fault is logged at ERROR
beside a re-check of the CASE_MANAGER's own copy (SYNC-03-010); every other
class is archived and skipped (:data:`ARCHIVE_ONLY`, #2883).
"""

from collections.abc import Callable
from dataclasses import dataclass

import py_trees

from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.behaviors.case.intake_only_received_tree import (
    create_intake_only_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderRule,
)
from vultron.core.behaviors.sync.divergence_tree import (
    RESEED_GATE_NAME,
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
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.fault import (
    CreateProcessingFaultReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    case_manager_verdict,
    door_refusal,
    find_named,
    find_node,
    verdict_from_bt,
)
from vultron.errors import VultronBTInternalError

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
        refused_entry,
        sender_id=fault.actor_id,
        sender_rule=rule,
        fault_published=(
            None if fault.activity is None else fault.activity.published
        ),
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
    # The re-seed this fault asks for sits in the tree's own CASE_MANAGER
    # gate; the factory's answer to a stamped ledger position holds another,
    # which a fault (no ledgerPosition, SYNC-18-017) never runs.
    gate = find_named(tree, RESEED_GATE_NAME)
    reseed = None if gate is None else find_node(gate, ReseedPeerNode)
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
    """The hash-mismatch tree, or the intake-only one for a fault that names
    no ``Announce(CaseLedgerEntry)`` this actor sent (ADR-0032: the tree
    receives the entry and its ``Announce`` id, never ``None``)."""
    announce_id = fault.failed_activity_id
    # The entry is read from the Announce announce_id names, so the second
    # test only narrows the event's optional field for the type checker.
    if refused_entry is None or announce_id is None:
        return create_intake_only_received_tree("HashMismatchFaultReceivedBT")
    return create_hash_mismatch_fault_tree(
        refused_entry,
        announce_id=announce_id,
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
