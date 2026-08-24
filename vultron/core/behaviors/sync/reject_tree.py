#!/usr/bin/env python
"""Behavior tree factory for inbound Reject(CaseLedgerEntry) handling."""

import py_trees

from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.sync.nodes import (
    AnnounceCaseOnGenesisRejectNode,
    FindCaseActorNode,
    ReplayMissingEntriesNode,
    UpdateReplicationStateNode,
)


def create_reject_log_entry_tree() -> py_trees.behaviour.Behaviour:
    """Create the BT for inbound ``Reject(CaseLedgerEntry)`` handling.

    The genesis pre-seed announces a ``VulnerabilityCase`` authored as the
    CaseActor, so it is role-gated: only the case's ``CASE_MANAGER`` may
    announce canonical case state.  The gate resolves the role **from the
    case** rather than comparing against the CaseActor entity that
    ``FindCaseActorNode`` looks up — the authority is a role, and its holder
    may be any Actor type (CLP-09 precedent; see ADR-0072).

    A non-manager skips the pre-seed rather than failing: replaying entries it
    already holds is still correct, and only the authoritative actor may seed a
    peer's replica.
    """
    return py_trees.composites.Sequence(
        name="RejectLogEntryReceivedBT",
        memory=False,
        children=[
            UpdateReplicationStateNode(name="UpdateReplicationState"),
            FindCaseActorNode(name="FindCaseActor"),
            # When the peer has no VulnerabilityCase yet (last_accepted_hash=""),
            # send Announce(VulnerabilityCase) before replaying entries so the
            # peer can anchor its hash chain (SYNC-15-002).
            py_trees.composites.Selector(
                name="GuardedAnnounceCaseOnGenesisRejectBT",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="AnnounceCaseIfCaseManager",
                        memory=False,
                        children=[
                            CheckIsCaseManagerNode(),
                            AnnounceCaseOnGenesisRejectNode(
                                name="AnnounceCaseOnGenesisReject"
                            ),
                        ],
                    ),
                    py_trees.behaviours.Success(
                        name="AnnounceCaseSkippedNotCaseManager"
                    ),
                ],
            ),
            ReplayMissingEntriesNode(name="ReplayMissingEntries"),
        ],
    )
