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

"""The Announce(CaseLedgerEntry) received-tree factory."""

import py_trees

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import LedgerActivityContext
from vultron.core.behaviors.sync.announce_tree.effect_slots import (
    create_log_entry_event_effects,
)
from vultron.core.behaviors.sync.nodes import (
    BufferPreGenesisEntryNode,
    CheckEntryAgreesWithCasePositionNode,
    CheckEntryHashIntactNode,
    CheckHashOrRejectOnMismatchNode,
    CheckLedgerEntryAlreadyStoredNode,
    EntryReflectedByCaseCopyNode,
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    ReconstructChainTailNode,
    ReplayHeldSuccessorNode,
    SendGenesisRejectOnMissingCaseNode,
)
from vultron.core.behaviors.sync.nodes.case_copy_effect import (
    StoreRecordsReflectedEntryCarriesNode,
)
from vultron.core.behaviors.sync.nodes.ledger_entry_fault import (
    EmitLedgerEntryFaultNode,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
)

#: The role check of the CASE_MANAGER arm: past the sender guard, an
#: announcement it admits is the CASE_MANAGER's own, echoed back.
AT_CASE_MANAGER = "CheckIsCaseManager"


def create_announce_log_entry_tree(
    *, sender_rule: SenderRule
) -> py_trees.behaviour.Behaviour:
    """Create the BT for an inbound ``Announce(CaseLedgerEntry)``.

    The sender must be the CASE_MANAGER of the case the announced entry
    names (SYNC-13-006, HP-01-006).  The factory composes that guard from the
    use case's declared rule, ahead of both role arms; its node reads the case
    from the entry when the tree runs
    (:class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`).
    At the CASE_MANAGER an admitted announcement is therefore its own, echoed
    back, and only confirms delivery; at a participant it is processed
    against the local chain.

    Args:
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    # Both role checks read a case this actor does not hold as "not the
    # CASE_MANAGER" (ADR-0087 Regime 3), so a participant in the pre-genesis
    # window takes the participant arm, whose replay Reject repairs it
    # (SYNC-15-001, #5513).  The CASE_MANAGER's own echoed Announce is the
    # exception: its sender is the manager, so a case it does not hold is a
    # Regime 1 anomaly and still fails at ERROR.
    case_actor_subtree = py_trees.composites.Sequence(
        name="CaseActorSubtree",
        memory=False,
        children=[
            CheckIsCaseManagerNode(
                name=AT_CASE_MANAGER,
                case_may_be_absent=True,
                own_activity_needs_case=True,
            ),
            LogDeliveryConfirmationNode(name="LogDeliveryConfirmation"),
        ],
    )
    log_entry_event_effects = create_log_entry_event_effects()
    # When the VulnerabilityCase is not yet seeded on this replica, chain tail
    # reconstruction fails and no tail_hash is available for the mismatch check.
    # Wrap reconstruct in a Selector so that on failure we (1) hold the received
    # Announce so the case-seed path can replay it once the genesis anchor is
    # known (SYNC-15-004, SYNC-15-005, #2186), and (2) ask for the case with a
    # genesis Reject (stating no ledger position, read as "replay from
    # genesis") as the loss backstop, at most once per case per interval,
    # exiting the Sequence without persisting the entry (SYNC-15-001,
    # SYNC-15-016, CLP-08-005).  FailureIsSuccess lets the Reject limit run
    # whether or not the entry was buffered, mirroring
    # CheckHashOrRejectOnMismatchNode's forward-gap buffer-and-reject
    # structure.
    reconstruct_or_reject = py_trees.composites.Selector(
        name="ReconstructOrRejectOnMissingCase",
        memory=False,
        children=[
            ReconstructChainTailNode(name="ReconstructChainTail"),
            py_trees.composites.Sequence(
                name="BufferAndRejectOnMissingCase",
                memory=False,
                children=[
                    py_trees.decorators.FailureIsSuccess(
                        name="BufferIfPreGenesis",
                        child=BufferPreGenesisEntryNode(
                            name="BufferPreGenesisEntry"
                        ),
                    ),
                    # Fallback: send the genesis Reject, with the sentinel
                    # tail_hash="" ReconstructChainTailNode wrote before
                    # failing keying its id; it states no ledger position
                    # (SYNC-18-017).  At most one per case per interval, the
                    # held entries draining once the case arrives
                    # (SYNC-15-016, SYNC-15-017).
                    SendGenesisRejectOnMissingCaseNode(
                        name="RejectOnMissingCase"
                    ),
                ],
            ),
        ],
    )
    process_and_store = py_trees.composites.Sequence(
        name="ProcessAndStore",
        memory=False,
        children=[
            reconstruct_or_reject,
            CheckHashOrRejectOnMismatchNode(
                name="CheckHashOrRejectOnMismatch"
            ),
            # An entry at the case's position with another hash is from a
            # different chain than the copy that set it: refused at ERROR,
            # never stored as a no-op (SYNC-16-025).
            CheckEntryAgreesWithCasePositionNode(
                name="CheckEntryAgreesWithCasePosition"
            ),
            # An entry the case copy that replaced this replica's case
            # already reflects is stored without its effects, an idempotent
            # no-op: applying it again over the copy could move the case
            # backwards, or refuse an entry the copy is past.  Only the
            # records it carries that the copy names by id are copied
            # (SYNC-16-023, CM-23-016).
            py_trees.composites.Selector(
                name="ApplyEffectsUnlessReflected",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="StoreReflectedEntry",
                        memory=False,
                        children=[
                            EntryReflectedByCaseCopyNode(
                                name="EntryReflectedByCaseCopy"
                            ),
                            StoreRecordsReflectedEntryCarriesNode(
                                name="StoreRecordsReflectedEntryCarries"
                            ),
                        ],
                    ),
                    # A reflected entry whose records fail to store must not
                    # fall through to its effects: the guard is repeated so
                    # that branch admits only an entry the copy lacks.
                    py_trees.composites.Sequence(
                        name="ApplyUnreflectedEntry",
                        memory=False,
                        children=[
                            py_trees.decorators.Inverter(
                                name="EntryNotReflectedByCaseCopy",
                                child=EntryReflectedByCaseCopyNode(
                                    name="CheckEntryReflectedByCaseCopy"
                                ),
                            ),
                            log_entry_event_effects,
                        ],
                    ),
                ],
            ),
            PersistReceivedLogEntryNode(name="PersistReceivedLogEntry"),
        ],
    )
    entry_processing = py_trees.composites.Selector(
        name="EntryProcessing",
        memory=False,
        children=[
            CheckLedgerEntryAlreadyStoredNode(
                name="CheckLogEntryAlreadyStored"
            ),
            process_and_store,
        ],
    )
    participant_subtree = py_trees.composites.Sequence(
        name="ParticipantGate",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="CheckIsNotCaseManager",
                child=CheckIsCaseManagerNode(
                    name="CheckIsCaseManagerInverse",
                    case_may_be_absent=True,
                    own_activity_needs_case=True,
                ),
            ),
            # An entry that fails its own hash is refused before it can be
            # buffered, applied or stored, and before the already-stored
            # shortcut could skip it unlogged (SYNC-03-006).  The refusal is
            # reported to the CASE_MANAGER with its own fault, and the
            # Selector still fails (SYNC-03-007).
            py_trees.composites.Selector(
                name="HashIntactOrFault",
                memory=False,
                children=[
                    CheckEntryHashIntactNode(name="CheckEntryHashIntact"),
                    EmitLedgerEntryFaultNode(
                        VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
                        name="EmitHashMismatchFault",
                    ),
                ],
            ),
            entry_processing,
            # The entry this delivery stored (or found stored) may be the
            # predecessor a held Announce waits on.  That Announce, as it was
            # received, is replayed through this actor's inbox as its own
            # delivery; its tree replays the next one (SYNC-14-009, ADR-0135).
            ReplayHeldSuccessorNode(name="ReplayHeldSuccessor"),
        ],
    )
    # The replication envelope is never itself a canonical entry (CLP-10-004),
    # so there is no commit stage (``case_id=None``); intake archives the
    # received Announce only and leaves the inlined entry to the chain check.
    return create_receive_activity_tree(
        name="AnnounceLogEntryReceivedBT",
        case_id=None,
        precondition_guards=[],
        sender_rule=sender_rule,
        sender_context=LedgerActivityContext(),
        replica_effects=[
            py_trees.composites.Selector(
                name="AnnounceLogEntryRoles",
                memory=False,
                children=[case_actor_subtree, participant_subtree],
            )
        ],
    )
