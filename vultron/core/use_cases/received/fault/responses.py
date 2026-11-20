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

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_intake_only_received_tree,
)
from vultron.core.behaviors.case.received_run import (
    OutcomeReader,
    ReceivedOutcome,
    find_named,
    find_node,
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
from vultron.core.models.events.fault import (
    CreateProcessingFaultReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.errors import VultronBTInternalError

#: Builds the one tree a fault's delivery runs, from the received fault and
#: the use case's declared sender rule.  The tree finds what the fault is
#: about itself (BT-25-009), so its shape is the same for every fault of its
#: class (BTND-01-009).
type FaultTreeBuilder = Callable[
    [CreateProcessingFaultReceivedEvent, SenderRule],
    py_trees.behaviour.Behaviour,
]


@dataclass(frozen=True)
class FaultResponse:
    """How the receiver answers a fault of one failure class.

    ``build_tree`` builds the delivery's one tree (CLP-10-005); ``reader``
    reads only the finished run (HP-01-003, ADR-0195), and every refusal is
    a node's declaration.  ``judges`` is ``False`` for a tree that judges
    nothing, whose failure past its doors is a local fault.  A fault about a
    ledger is the case's CASE_MANAGER's alone to act on: its tree declares
    the manager path, so the path stage refuses any replica (HP-01-005,
    HP-01-039).
    """

    label: str
    """Names the response's tree in a reason, e.g. ``"CaseDivergedFaultReceivedBT"``."""
    build_tree: FaultTreeBuilder
    reader: OutcomeReader
    judges: bool = True


def _archive_tree(
    fault: CreateProcessingFaultReceivedEvent, rule: SenderRule
) -> py_trees.behaviour.Behaviour:
    """The intake-only tree: a fault with no effect is only archived."""
    del fault, rule  # nothing here depends on them
    return create_intake_only_received_tree("CreateProcessingFaultReceivedBT")


def _archive_reader(outcome: ReceivedOutcome) -> HandlerResult | None:
    """``SKIPPED``: nothing correlates the fault to its ask yet (#2883).

    A door guard's refusal (the case is fully closed) is the runner's; any
    other failure of the intake-only tree is a local fault.
    """
    if not outcome.succeeded:
        return None
    return HandlerResult.skipped(
        "ask-register correlation not implemented (#2883)"
    )


def _case_diverged_tree(
    fault: CreateProcessingFaultReceivedEvent, rule: SenderRule
) -> py_trees.behaviour.Behaviour:
    return create_case_diverged_fault_tree(
        sender_id=fault.actor_id,
        sender_rule=rule,
        fault_published=(
            None if fault.activity is None else fault.activity.published
        ),
    )


def _reseed_reader(outcome: ReceivedOutcome) -> HandlerResult | None:
    """The verdict on a case-diverged fault (SYNC-16-003, SYNC-16-004).

    ``APPLIED`` when a case copy was queued; ``SKIPPED`` when the re-seed
    cooldown held it back.  Every refusal is a node's declaration, which
    the runner reads: a fault that names no ``Add(CaseLedgerEntry)`` this
    actor sent (the lookup's miss guard, BT-25-010), a sender that is not an
    active participant (the sender guard, and the re-seed itself,
    CM-10-004), and any replica, refused by the path stage (HP-01-005).
    """
    if not outcome.succeeded:
        # A failure is the runner's to read from the declarations.
        return None
    # The re-seed this fault asks for sits in the tree's own CASE_MANAGER
    # gate; the factory's answer to a stamped ledger position holds
    # another, which a fault (no ledgerPosition, SYNC-18-017) never runs.
    gate = find_named(outcome.tree, RESEED_GATE_NAME)
    reseed = None if gate is None else find_node(gate, ReseedPeerNode)
    if reseed is None:
        raise VultronBTInternalError(
            f"{outcome.label}: tree has no re-seed node"
        )
    if reseed.reseeded:
        return HandlerResult.applied()
    # A withheld peer fails the re-seed with its declared refusal, so a
    # successful run that sent no copy was held back by the cooldown.
    return HandlerResult.skipped(
        f"the sender was re-seeded with case '{reseed.case_id}'"
        " within the cooldown; no case copy sent (SYNC-16-004)"
    )


def _hash_mismatch_tree(
    fault: CreateProcessingFaultReceivedEvent, rule: SenderRule
) -> py_trees.behaviour.Behaviour:
    return create_hash_mismatch_fault_tree(
        sender_id=fault.actor_id, sender_rule=rule
    )


def _hash_mismatch_reader(outcome: ReceivedOutcome) -> HandlerResult | None:
    """The verdict on a hash-mismatch fault (SYNC-03-008, SYNC-03-010).

    ``SKIPPED`` once the CASE_MANAGER has logged the fault and checked its
    own copy, since nothing changes.  Every refusal is a node's declaration,
    which the runner reads: a fault that names no ``Add(CaseLedgerEntry)``
    this actor sent (the lookup's miss guard, BT-25-010), a sender that is
    not an active participant (the sender guard), and any replica, refused
    by the path stage (HP-01-005).
    """
    if not outcome.succeeded:
        # A failure is the runner's to read from the declarations.
        return None
    report = find_node(outcome.tree, ReportHashMismatchNode)
    if report is None or report.own_copy is None:
        raise VultronBTInternalError(
            f"{outcome.label}: the run did not check this actor's own copy"
        )
    return HandlerResult.skipped(
        f"hash mismatch on ledger entry '{report.entry_id}' logged; own"
        f" copy {report.own_copy.value}; nothing is sent, re-seeded or"
        " recorded for it (SYNC-03-008)"
    )


#: The case-diverged response (SYNC-16-003).
CASE_DIVERGED = FaultResponse(
    label="CaseDivergedFaultReceivedBT",
    build_tree=_case_diverged_tree,
    reader=_reseed_reader,
)

#: The hash-mismatch response (SYNC-03-008).
HASH_MISMATCH = FaultResponse(
    label="HashMismatchFaultReceivedBT",
    build_tree=_hash_mismatch_tree,
    reader=_hash_mismatch_reader,
)

#: A failure class with no entry in a use case's ``responses``.
ARCHIVE_ONLY = FaultResponse(
    label="CreateProcessingFaultReceivedBT",
    build_tree=_archive_tree,
    reader=_archive_reader,
    judges=False,
)
