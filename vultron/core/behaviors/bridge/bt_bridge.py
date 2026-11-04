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

"""BT Bridge Layer - Handler-to-BehaviorTree execution interface.

This package implements the bridge layer between handler functions and py_trees
behavior tree execution. It provides:

1. Setup of py_trees execution context with DataLayer access
2. Blackboard initialization with activity and actor state
3. Single-shot BT execution to completion
4. Result capture and error handling
5. Leadership guard port (SYNC-09-003): single-node always returns True;
   seam for future multi-node Raft leader check.

Per specs/behavior-tree-integration.yaml:
- BT-05-001: Provides BT execution bridge for handler-to-BT invocation
- BT-05-002: Sets up py_trees context with DataLayer access
- BT-05-003: Populates blackboard with activity and actor state
- BT-05-004: Executes tree and returns execution result

Per specs/sync-ledger-replication.yaml:
- SYNC-09-003: Leadership role-check port; always True in single-node.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.blackboard_scope import (
    restore_keys,
    snapshot_keys,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import (
    VultronError,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge.leadership import _default_is_leader
from vultron.core.behaviors.bridge.lock import _BT_GLOBAL_LOCK
from vultron.core.behaviors.bridge.result import BTExecutionResult
from vultron.core.behaviors.bridge.tree_execution import _BridgeExecution
from vultron.core.behaviors.bridge.tree_setup import _BridgeSetup

# The package name, so the bridge logger keeps the name it had before the split.
_LOGGER_PREFIX = __name__.rpartition(".")[0]


class BTBridge(_BridgeSetup, _BridgeExecution):
    """
    Bridge layer for executing behavior trees from handler functions.

    Provides single-shot BT execution with DataLayer integration and
    blackboard management. Handlers invoke BTs through this bridge to
    orchestrate complex workflows while preserving handler protocol.

    The ``is_leader`` attribute is a leadership guard port (SYNC-09-003).
    In single-node deployments it always returns ``True``; replace it with
    a real Raft leader check when multi-node CaseActor cluster support is
    introduced.
    """

    def __init__(
        self,
        datalayer: CasePersistence,
        is_leader: Callable[[], bool] = _default_is_leader,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ):
        """
        Initialize BT bridge with DataLayer access and optional leadership guard.

        Args:
            datalayer: CasePersistence implementation for persistent state access.
            is_leader: Callable returning True iff this node is the
                replication leader.  Defaults to a function that always
                returns True (single-node behaviour).  Per SYNC-09-003.
            trigger_activity: Optional port for constructing outbound wire
                activities from BT nodes (ARCH-01-004).  When provided it is
                placed on the py_trees blackboard under the key
                ``trigger_activity_factory`` so that BT nodes can call it
                without importing from the wire layer.
            sync_port: Optional port for LedgerFanout replication fan-out
                (SYNC-02-002).  When provided it is placed on the py_trees
                blackboard under the key ``sync_port`` so that
                ``CommitCaseLedgerEntryNode`` can fan out
                ``Announce(CaseLedgerEntry)`` activities to participants.
                Without this, ledger entries committed inside BTs are
                persisted locally but not replicated.
            wire_render_port: Optional port for rendering core domain objects
                to wire-shaped (camelCase) JSON (ARCH-20-001).  When provided
                it is placed on the py_trees blackboard under the key
                ``wire_render_port`` so that BT nodes can call it without
                importing from the wire layer (ARCH-01-001, ARCH-01-004).
        """
        self.datalayer = datalayer
        self.is_leader = is_leader
        # Tracks whether the caller provided an explicit guard (not _default_is_leader).
        # Used to distinguish "caller opted in to a specific policy" from "caller
        # accepted the default" so that inheritance from an outer BTBridge execution
        # can be applied only to the latter case (CLP-08-005).
        self._is_leader_explicit: bool = is_leader is not _default_is_leader
        self.trigger_activity = trigger_activity
        self.sync_port = sync_port
        self.wire_render_port = wire_render_port
        self.logger = logging.getLogger(
            f"{_LOGGER_PREFIX}.{self.__class__.__name__}"
        )

    def execute_with_setup(
        self,
        tree: py_trees.behaviour.Behaviour,
        actor_id: str,
        activity: Any = None,
        max_iterations: int = 100,
        **context_data: Any,
    ) -> BTExecutionResult:
        """
        Convenience method combining setup and execution.

        Checks the leadership guard before executing.  If the effective
        ``is_leader()`` returns ``False``, execution is skipped and a FAILURE
        result is returned immediately with a descriptive feedback message
        (SYNC-09-003).  The check runs inside ``_BT_GLOBAL_LOCK`` to prevent
        cross-thread contamination from a concurrent outer execution's
        blackboard state.

        When this bridge was constructed without an explicit ``is_leader``
        callable (``_is_leader_explicit`` is False), the method inherits the
        guard from the current outer BTBridge execution's blackboard key
        ``/is_leader``.  This ensures that an inner ``BTBridge(datalayer=...)``
        constructed inside a BT node (e.g. ``EmitCaseStatusUpdateNode``)
        respects the same leadership constraint as the outer execution rather
        than silently defaulting to always-True (CLP-08-005).  Non-callable
        values on the blackboard are ignored to guard against test pollution.

        ``activity`` and every ``context_data`` key are **execution-scoped**:
        they are restored to their pre-execution values when this call returns,
        on every outcome.  A nested ``execute_with_setup`` that reuses one of
        these keys therefore hands the outer execution's value back when it
        finishes, instead of leaving its own behind for the outer tree's
        remaining ticks to read (#3161).  Consequently a caller must not use one
        of these keys as an *output* channel — pass a mutable ``result_out``
        dict, which is shared by reference and unaffected by the restore.

        Typical usage from handler:
            result = bridge.execute_with_setup(
                tree=ValidateReportBT(...),
                actor_id=actor_id,
                activity=request,
            )

        Args:
            tree: Root behavior node to execute
            actor_id: ID of actor executing this tree
            activity: Optional ActivityStreams activity being processed
            max_iterations: Safety limit on tick count
            **context_data: Additional context for blackboard

        Returns:
            BTExecutionResult with execution status and feedback.  Never raises:
            a failure in ``setup_tree`` is classified the same way
            ``execute_tree`` classifies a failure during the ticks, and each is
            labelled with the phase it came from — see
            ``BTExecutionResult.internal_error``.  The leadership skip is a
            protocol outcome, not an internal error.

        Implements:
            - BT-05-001: BT execution bridge for handler-to-BT invocation
            - SYNC-09-003: Leadership guard check before BT execution
        """
        with _BT_GLOBAL_LOCK:
            # Resolve the effective leadership guard.
            #
            # This check is inside _BT_GLOBAL_LOCK for two reasons:
            #
            # 1. Thread safety: the blackboard is process-global.  Reading
            #    /is_leader outside the lock risks reading a value written by a
            #    concurrent outer execution that has not yet cleaned up, making
            #    this bridge's leadership decision depend on another request's
            #    raft state.  The lock serialises all BT executions, so by the
            #    time we read the blackboard here the previous execution's
            #    cleanup has already run (CLP-08-005, SYNC-09-003).
            #
            # 2. Accurate inheritance: an outer setup_tree() wrote is_leader
            #    to the blackboard before calling execute_tree(), which ticked
            #    the node that spawned this inner bridge.  Reading the
            #    blackboard here (still inside the same re-entrant lock
            #    acquisition) sees the outer value rather than a stale residue.
            #
            # The callable() guard rejects any non-callable that test pollution
            # or a future node might write under the /is_leader key, preventing
            # a TypeError from escaping the error net.
            inherited_raw = (
                self._inherited_port("is_leader")
                if not self._is_leader_explicit
                else None
            )
            inherited = inherited_raw if callable(inherited_raw) else None
            effective_is_leader = (
                inherited if inherited is not None else self.is_leader
            )
            if not effective_is_leader():
                msg = (
                    "BT execution skipped: this node is not the replication"
                    " leader"
                )
                self.logger.warning("%s", msg)
                return BTExecutionResult(
                    status=Status.FAILURE,
                    feedback_message=msg,
                    leader_skipped=True,
                )
            # Execution-scoped blackboard keys: each lives for exactly one BT
            # execution and is reset to its pre-execution state in the finally
            # block below, on EVERY outcome (SUCCESS, FAILURE, Sequence
            # short-circuit, or exception).  The finally block is the single
            # DRY teardown for anything that must not leak across executions —
            # see the comment there for why it covers both resource release and
            # cross-execution state hygiene (#3101).
            managed_keys = [
                "datalayer",
                "trigger_activity_factory",
                "sync_port",
                "is_leader",
                "wire_render_port",
                # Published by ResolveCreationTimeRevisionNode, read by
                # InitializeCreationEmbargoNode and RelayCreationTimeRevisionNode
                # (EP-04-011).  The writer ticks only on the creation arm, so a
                # redelivery that skips that arm would otherwise hand the
                # readers the previous execution's value, and the relay would
                # send an Invite no registration in this act asked for.
                "creation_time_revision_candidate",
                # Published by the node that builds a case's
                # Create(VulnerabilityCase), read by
                # CommitNativeLedgerEntriesNode as the genesis entry
                # (CLP-07-011).  The writer ticks only when this act builds
                # the Create, so a creation that built none must see no id,
                # not the previous execution's, or it would commit another
                # case's Create as its genesis.
                "create_case_activity_id",
                # Published by the RM adjudication guards
                # (CheckParticipantStatusAcceptableNode,
                # AdjudicateRMDeclarationNode), read by EmitRMGapNoteNode.
                # The note runs as a refusal effect (CLP-10-022) whenever any
                # precondition guard refuses, including one ahead of the
                # adjudication that never ticked it, so a previous
                # execution's anomaly must not survive to be noted again.
                "rm_transition_anomaly",
                # The executing actor's identity is execution-scoped too, and for
                # a sharper reason than the ports above.  Every node base in
                # `helpers/` re-reads `/actor_id` into `self.actor_id` in
                # `initialise()` — NOT in `setup()` — and py_trees calls
                # `initialise()` on every tick in which the node was not RUNNING.
                # So without this entry a later sibling of a node that made a
                # nested call read the *inner* execution's actor, not the actor
                # its own tree was executing as (#3516).
                #
                # Reconciliation makes `self.datalayer.actor_id` and `/actor_id`
                # the same actor, and the sites that pass the store's own actor
                # to a nested call (`case/nodes/participant/rm_closure.py`,
                # reached from `case/nodes/leave/advance.py` twice) usually pass
                # the value already on the blackboard.  Where a nested call runs
                # as another actor, `OwnerLeaveSeq`
                # (`case/receive_close_case_tree/closure_effects.py`) ticks the ledger-committing
                # sibling downstream of `AdvanceParticipantToRMClosedNode`, and a
                # leaked actor would reach `payloadSnapshot.actor`: a CLP-07-003
                # identity fault in a canonical entry.
                #
                # Restoring is safe, not merely safer: the restore runs in the
                # *inner* call's own `finally`, after its tree has finished, and
                # puts back exactly the value that same call snapshotted.  It
                # cannot overwrite a live execution.
                "actor_id",
                # The case a delivery is about.  A use case that knows its
                # case passes it as ``context_data``, which the line below
                # scopes; but six nodes publish ``/case_id`` as an *output
                # port* instead (``CaseLookupNode``,
                # ``LoadExistingCaseNode``, the replay and case-creation
                # nodes), and an output port is not ``context_data``, so
                # without this entry their value outlives the execution that
                # wrote it.  A later delivery whose own tree names no case —
                # ``create_ack_report_received_tree`` is one — then resolves
                # that stale id: ``ReceivedPathNode`` and
                # ``CheckIsCaseManagerNode`` both read ``/case_id`` after
                # their constructor argument (``activity_case_id``), so the
                # path stage refused an RK as a replica of a case the RK
                # never named.  In a single-process run the writer can even
                # be a different actor's execution (BT-09).
                "case_id",
                # The CASE_MANAGER actor for the case a trigger acts on.
                # ``ResolveCaseManagerNode`` publishes it, ``None`` on each of
                # its failure arms (BT-17-003).  ``ConstructActivitiesNode``
                # and ``SendTerminateEmbargoActivityNode`` read it strictly,
                # and ``EmitCloseCaseNode`` reads it if present.  Strict does
                # not help against a stale value, which is present: a previous
                # execution's manager would address this execution's
                # activities to another case's manager (BT-09, BTND-03-009).
                "case_manager_id",
                # The CASE_MANAGER's actor id, published by
                # ``FindCaseActorNode`` (replay), ``ReceivedPathNode`` (path
                # stage) and ``CheckIsCaseManagerNode`` (manager-role guard),
                # and read by ``AnnounceCaseOnGenesisRejectNode`` and
                # ``SendMissingEntriesNode``.  A previous execution's value,
                # possibly another actor's, would address a genesis Announce
                # or a replay to the wrong actor (BT-09, BTND-03-009).
                "case_actor_id",
                # --- Output-port keys audited and deliberately NOT scoped ---
                #
                # Each key below has more than one writer, but no reader can
                # see a value an earlier execution left: on every path that
                # reaches a reader, a writer in the same execution ticks first
                # and writes the key, or a sentinel, before the reader runs.
                # Nor does any nested execute_with_setup run between a writer
                # and its reader.  Adding a reader that a writer does not
                # precede on every path means adding the key here.
                #
                # ``activity_ids`` — ConstructActivitiesNode (``None`` on its
                #   failure arms) → QueueToOutboxNode, its next sibling in the
                #   send tree and the embargo proposal and termination trees.
                #
                # ``tail_hash`` / ``tail_index`` — ReconstructChainTailNode →
                #   CreateLogEntryNode in the commit tree, and in the announce
                #   tree CheckHashMatchesNode, BufferOutOfOrderEntryNode and
                #   SendRejectLogEntryNode.  One reader runs after the writer
                #   FAILS: ReconstructOrRejectOnMissingCase is a Selector whose
                #   SendGenesisRejectOnMissingCaseNode arm reads tail_hash.  It
                #   is safe because the writer stores the "" / -1 sentinel
                #   before returning FAILURE on the pre-genesis path.  Its only
                #   other FAILURE, a missing datalayer, makes that arm raise
                #   before it sends, and an unresolvable case id raises.
                #
                # ``log_entry`` / ``log_entry_preexisting`` —
                #   CreateLogEntryNode (both arms write both keys) →
                #   PersistLogEntryNode and FanOutLogEntryNode, its later
                #   siblings in the commit tree.
                #
                # ``invitee_case`` — CheckInviteeNotAlreadyParticipantNode
                #   (``None`` on its duplicate arm), a precondition guard of
                #   the accept-invite tree → _CheckEmbargoActiveStateNode and
                #   _SignEmbargoConsentLeafNode, manager effects that run only
                #   after every guard has passed.
                #
                # ``admission_record_was_prior`` — RecordProposalAdmissionNode
                #   (both SUCCESS arms write it) → LoadExistingCaseNode, which
                #   runs right after it in the same ActTransaction of the
                #   case-proposal tree.
                #
                # ``activity_id`` — _BuildCreateCaseActivityNode →
                #   UpdateActorOutbox, its next sibling in the create-case
                #   trigger tree.  The other writer, CreateCaseActivity, is in
                #   no tree today.
                #
                # ``participant`` — LookupParticipantNode and
                #   FindParticipantByActorIdNode (whose key a caller may
                #   rename, as the sender guard does); nothing reads
                #   ``/participant``.
                #
                # ``/ledger_position/case_id`` and
                #   ``/ledger_position/case_actor_id`` — the scoped copies the
                #   ledger-position stage's FindCaseActorNode writes →
                #   ReplayMissingEntriesNode, its next sibling in that stage.
                #   They are kept off the root keys so the act's own nodes
                #   never read them.
            ]
            # setup_tree() also writes /activity (when one is supplied) and one
            # key per **context_data entry, so those are execution-scoped for
            # exactly the same reason as the fixed keys above — with the same
            # sharpness that a *nested* execute_with_setup passing the same key
            # overwrites the outer execution's value and, without this, never
            # puts it back.  The outer tree then resumes ticking against the
            # inner call's activity or case_id (#3161).
            managed_keys += ["activity", *context_data.keys()]
            storage = py_trees.blackboard.Blackboard.storage
            # Both spellings of every key, and "absent" kept distinct from
            # "None" — see blackboard_scope for why each matters.  Shared with
            # the inbox pipeline, which needs the identical guarantee (#3534).
            previous_values = snapshot_keys(storage, managed_keys)
            try:
                # Two try blocks, not one, so the label always names the phase
                # that actually failed.  A single combined block reported an
                # error raised during the ticks as "BT setup failed", which
                # sends a reader to the wiring when the bug is in a node (#3085).
                #
                # Each is inside a try for the same reason execute_tree() moved
                # bt.setup() inside its own: setup_tree() does fallible work
                # (store cloning, port construction, register_key/setattr over
                # arbitrary context_data), and a programming error there used to
                # escape BTBridge entirely — unclassified, and into a FastAPI
                # background task.  Classify it like any other internal error
                # rather than letting the one call outside the net through
                # (CONCERN-3019).
                try:
                    bt = self.setup_tree(
                        tree, actor_id, activity, **context_data
                    )
                except VultronError as e:
                    return self._exception_result(e, prefix="BT setup failed")
                except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
                    return self._exception_result(
                        e, prefix="BT setup failed", internal_error=True
                    )

                # execute_tree() has its own catch-all, so in the current code
                # nothing reaches these two handlers.  They are the guarantee
                # rather than the mechanism: "a BT execution never escapes the
                # bridge" stays true if that catch-all is ever narrowed, and if
                # something does escape it is labelled as execution, not setup.
                try:
                    return self.execute_tree(bt, max_iterations)
                except VultronError as e:
                    return self._exception_result(
                        e, prefix="BT execution failed"
                    )
                except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
                    return self._exception_result(
                        e, prefix="BT execution failed", internal_error=True
                    )
            finally:
                # Restore managed blackboard keys to their pre-execution state.
                # Blackboard.storage is process-global, so anything setup_tree()
                # or the ticked nodes write there outlives the execution unless
                # reset here.  This single finally is the DRY teardown for two
                # otherwise-separate hazards:
                #
                #  1. Resource release.  setup_tree() writes SqliteDataLayer and
                #     TriggerActivityAdapter objects (both hold sqlite3
                #     connections); leaving them keeps the connections alive
                #     until the next execution overwrites the key.  That delayed
                #     release causes ResourceWarning: unclosed database when GC
                #     runs at an unpredictable moment — typically during the
                #     next test's SQL activity, which pytest promotes to a test
                #     failure via PytestUnraisableExceptionWarning (pytest
                #     9.1.0+).
                #
                #  2. Cross-execution state hygiene.  A node-written key such as
                #     rm_transition_anomaly can be left stranded when a
                #     Sequence FAILURE-short-circuits before its owning node
                #     ticks (#3101).  Resetting it here guarantees no stale
                #     hand-off state bleeds into the next execution, no matter
                #     which node aborted or why.
                #
                # ``trigger_activity_factory`` is included here even though
                # each setup_tree() call re-writes it: restoring the previous
                # value (or removing it when it was absent) ensures that the
                # previous TriggerActivityAdapter reference is released
                # promptly rather than being held until the next execution.
                # Nested execute_with_setup calls are safe because the RLock
                # is reentrant and previous_values captures the outer call's
                # state, so the inner call restores exactly what the outer
                # call wrote.
                restore_keys(storage, previous_values)
