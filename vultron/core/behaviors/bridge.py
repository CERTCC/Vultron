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

"""
BT Bridge Layer - Handler-to-BehaviorTree execution interface.

This module implements the bridge layer between handler functions and py_trees
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
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import py_trees
from py_trees.common import Status
from py_trees.display import unicode_tree

from vultron.core.behaviors.store_scope import port_for_store, store_for_actor
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)

# py_trees uses a process-global blackboard (Blackboard.storage).
# FastAPI runs synchronous BackgroundTask callables in a thread-pool
# executor, so two BT executions can run on different threads at the
# same time, corrupting each other's actor_id / datalayer entries.
# This lock serialises BT executions from *different* threads while
# allowing same-thread re-entrancy (e.g. lifecycle.py nodes that call
# execute_with_setup internally).  RLock is used instead of Lock to
# prevent deadlock in those re-entrant paths.
_BT_GLOBAL_LOCK = threading.RLock()


@dataclass
class BTExecutionResult:
    """Result of BT execution returned to handler.

    ``internal_error`` separates the two things a bare ``FAILURE`` used to
    conflate: a protocol outcome the tree is entitled to report, and a
    programming error that escaped a node. Callers that make a protocol
    decision from a failure — retry, re-buffer, log level — should consult it,
    because retrying a code bug never converges. See CONCERN-3019.

    Read the flag as *"an internal error reached the bridge"*, not *"no bug
    occurred"*. Two known gaps, both tracked in CONCERN-3019:

    - Node ``update()`` bodies catch broadly by convention, so a crash swallowed
      inside a node arrives here as an ordinary ``FAILURE`` (or even
      ``SUCCESS``) and is never flagged.
    - Nodes that run a sub-tree through their own ``BTBridge`` discard the inner
      result's flag and return a bare ``Status.FAILURE``, so a crash inside a
      nested subtree is not visible in the outer result.
    """

    status: Status
    feedback_message: str = ""
    errors: list[str] | None = None
    internal_error: bool = False


def _default_is_leader() -> bool:
    """Default leadership guard for single-node deployments.

    Always returns ``True`` — the single-node CaseActor is permanently the
    replication leader.  In a future multi-node deployment this function is
    replaced by an actual Raft leader check.

    Per SYNC-09-003, SYNC-06-003.
    """
    return True


class BTBridge:
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
        self.trigger_activity = trigger_activity
        self.sync_port = sync_port
        self.wire_render_port = wire_render_port
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )

    def _store_for_actor(self, actor_id: str) -> CasePersistence:
        """Return the store belonging to *actor_id* (ADR-0073, BT-05-005).

        BT-05-002 and BT-05-003 put ``datalayer`` and ``actor_id`` on the
        blackboard as two independent facts.  Under per-actor storage they are
        one fact: a store is always some actor's own, so the executing actor's
        identity *determines* which store the tree operates on.  Reconciling
        them here makes every write a node performs — ``outbox_append()`` above
        all — correct by construction, rather than correct only when the caller
        remembered to inject a matching DataLayer.

        The delegated-emit pattern is what makes this load-bearing.  A trigger
        that emits on the CaseActor's behalf runs with ``actor_id`` set to the
        CaseActor (CM-24-001) while the injected DataLayer belongs to the
        *requesting* actor.  Without reconciliation the activity is created in
        one store and queued in the other's outbox, so the CaseActor never
        delivers it and the outbox entry names an activity its own store does
        not hold (PCR-08-007, CM-24-004).

        Scoping is skipped unless the DataLayer reports a concrete ``actor_id``
        that differs, which leaves test doubles and any non-actor-scoped
        implementation untouched.  That fall-through is the first of BT-05-005's
        two recorded exceptions: a store that cannot name its own actor has
        nothing to reconcile against.

        The guard logic itself lives in
        :func:`~vultron.core.behaviors.store_scope.store_for_actor` so that this
        node, ``WritePendingReportCaseLinkNode`` and the demo seeding helpers
        cannot drift apart on what "that actor's store" means.

        ``require_same_authority`` is set, and the fall-through is the point of
        it — BT-05-005's second exception.  The executing actor is not always one
        this node hosts: after a
        handoff the case's CaseActor is on the container that first received the
        report (CP-08-003) while the owner is elsewhere, and
        ``_find_case_actor_id`` resolves it by *identity shape*
        (``.../actors/case-actor``, ADR-0041) which answers for remote
        containers too.  ``clone_for_actor`` would then mint an empty local
        store under a foreign actor's name, and the tree would run against
        nothing: no case to enrich the wire object from (CM-17-002), no case to
        read a genesis hash out of, so ``ReconstructChainTailNode`` cannot
        anchor the chain and the ledger commit fails outright (CLP-08-005) —
        ``invite-actor-to-case`` returns 422 rather than degrading (#2484).

        So a foreign-authority actor keeps the store it was handed: the store of
        the actor whose request this is, which does hold the case and its
        ledger.  The *wire* identity is unaffected — the Invite still goes out
        with ``actor`` set to the CaseActor and ``attributedTo`` the requester
        (PCR-08-007) — and the CaseActor's canonical ledger learns of it the
        only way a remote store ever can, over the wire via the ``cc:`` copy
        (CLP-10-001).  Callers that queue work for the executing actor must fall
        back the same way; see ``trigger_invite_actor_to_case``.

        That last part is enforced, not merely intended: a *ledger commit* must
        not ride along on this fall-through, or the requester mints a canonical
        index in its own replica while the real CaseActor mints its own from the
        ``cc:`` copy and the chain forks (#2626).
        :class:`~vultron.core.behaviors.sync.nodes.ledger_authority.DeclineForeignLedgerCommitNode`
        makes ``CommitLogEntryBT`` decline in exactly the case this method falls
        through on, reusing this same guard so the two cannot disagree
        (CLP-10-014).

        Reconciling the store is necessary but not sufficient — see
        :meth:`_ports_for_store` for the other half.
        """
        return (
            store_for_actor(
                self.datalayer, actor_id, require_same_authority=True
            )
            or self.datalayer
        )

    def _ports_for_store(self, store: CasePersistence) -> tuple[
        "TriggerActivityPort | None",
        "SyncActivityPort | None",
        "WireRenderPort | None",
    ]:
        """Return this bridge's driven ports, rebound to *store* (DL-07-009).

        ``_store_for_actor`` reconciles the store the *nodes* write through.  The
        driven adapters on the blackboard hold a second, independent reference to
        a DataLayer — the one they were constructed with — and that reference is
        what persists an outbound activity.  Leaving it alone splits a single
        emit across two stores: ``TriggerActivityAdapter.invite_actor_to_case``
        creates the ``Invite`` in the *requesting* actor's store while
        ``EmitInviteActorToCaseNode`` appends its id to the *executing* actor's
        outbox.  Nothing raises; the outbox handler simply reports the activity
        "not found in DataLayer for actor …", skips delivery, and the invitee is
        never told it was invited (ISSUE-2548).

        This is the delegated-emit path the class docstring on
        ``SvcInviteActorToCaseUseCase`` describes: a trigger addressed to the case
        owner runs with ``actor_id`` set to the CaseActor, so the two references
        disagree by construction rather than by mistake.

        A port this bridge was not given is *inherited* from the blackboard
        rather than left alone, because the blackboard is process-global
        (``Blackboard.storage``) and the nested-bridge pattern relies on that:
        an emit node builds its ledger-commit tree with
        ``BTBridge(datalayer=...)`` and no ports, so whatever the last execution
        wrote is what the commit tree's ``LedgerFanoutNode`` picks up.  Within
        one request that inheritance is intended — the ports belong to the
        execution in progress.  Across requests it is a store leak: a node
        hosting several actors runs actor A's trigger, then actor B's, and B's
        ``Announce(CaseLedgerEntry)`` is persisted through A's adapter into A's
        store (ADR-0073, CM-01-001).  Rebinding on the way through makes the
        inheritance safe by construction instead of safe by luck, so the port a
        nested tree reads always writes the store that tree runs in.

        Ports that do not opt in are returned unchanged; see
        :func:`~vultron.core.behaviors.store_scope.port_for_store`.
        """
        return (
            port_for_store(
                self.trigger_activity
                or self._inherited_port("trigger_activity_factory"),
                store,
            ),
            port_for_store(
                self.sync_port or self._inherited_port("sync_port"), store
            ),
            port_for_store(
                self.wire_render_port
                or self._inherited_port("wire_render_port"),
                store,
            ),
        )

    @staticmethod
    def _inherited_port(key: str) -> Any:
        """Return the port currently on the blackboard under *key*, or ``None``.

        Read straight out of ``Blackboard.storage`` rather than through a
        ``Client``: registering READ access for a key that may never have been
        written raises, and "no port has been set yet" is the ordinary case for
        the first execution in a process.
        """
        return py_trees.blackboard.Blackboard.storage.get(f"/{key}")

    def setup_tree(
        self,
        tree: py_trees.behaviour.Behaviour,
        actor_id: str,
        activity: Any = None,
        **context_data: Any,
    ) -> py_trees.trees.BehaviourTree:
        """
        Set up behavior tree with blackboard and execution context.

        Args:
            tree: Root behavior node to execute
            actor_id: ID of actor executing this tree (for state isolation)
            activity: Optional ActivityStreams activity being processed
            **context_data: Additional context to populate in blackboard

        Returns:
            Configured BehaviourTree ready for execution

        Implements:
            - BT-05-002: Sets up py_trees context with DataLayer access
            - BT-05-003: Populates blackboard with activity and actor state
        """
        self.logger.debug(f"Setting up BT for actor {actor_id}")

        # Create py_trees BehaviourTree wrapper
        bt = py_trees.trees.BehaviourTree(root=tree)

        # Populate blackboard with execution context
        blackboard = py_trees.blackboard.Client(name=f"BTBridge-{actor_id}")
        blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.WRITE
        )
        blackboard.register_key(
            key="actor_id", access=py_trees.common.Access.WRITE
        )

        store = self._store_for_actor(actor_id)
        trigger_activity, sync_port, wire_render_port = self._ports_for_store(
            store
        )

        blackboard.datalayer = store
        blackboard.actor_id = actor_id

        if trigger_activity is not None:
            blackboard.register_key(
                key="trigger_activity_factory",
                access=py_trees.common.Access.WRITE,
            )
            blackboard.trigger_activity_factory = trigger_activity

        if sync_port is not None:
            blackboard.register_key(
                key="sync_port",
                access=py_trees.common.Access.WRITE,
            )
            blackboard.sync_port = sync_port

        if wire_render_port is not None:
            blackboard.register_key(
                key="wire_render_port",
                access=py_trees.common.Access.WRITE,
            )
            blackboard.wire_render_port = wire_render_port

        if activity is not None:
            blackboard.register_key(
                key="activity", access=py_trees.common.Access.WRITE
            )
            blackboard.activity = activity

        # Register any additional context data
        for key, value in context_data.items():
            blackboard.register_key(
                key=key, access=py_trees.common.Access.WRITE
            )
            setattr(blackboard, key, value)

        self.logger.info(f"BT setup complete for actor {actor_id}")

        # BT scaffolding, not protocol story — DEBUG only (SL-04-007).
        if self.logger.isEnabledFor(logging.DEBUG):
            tree_repr = unicode_tree(tree, show_status=True)
            self.logger.debug(f"BT structure:\n{tree_repr}")

        return bt

    def execute_tree(
        self, bt: py_trees.trees.BehaviourTree, max_iterations: int = 100
    ) -> BTExecutionResult:
        """
        Execute behavior tree to completion or max iterations.

        Single-shot execution model per BT-01-002: BT executes to completion
        (or max iterations) per invocation, not continuous tick loop.

        Args:
            bt: Configured BehaviourTree ready for execution
            max_iterations: Safety limit on tick count (default: 100)

        Returns:
            BTExecutionResult with final status, feedback, any errors, and the
            ``internal_error`` classification.  A FAILURE is flagged
            ``internal_error=True`` when it did not come from a protocol
            decision: an exception that is not a ``VultronError``, a root left
            in ``INVALID`` mid-execution, or ``max_iterations`` exhausted.
            A node returning FAILURE, or raising a ``VultronError``
            deliberately, leaves the flag ``False``.  See
            ``BTExecutionResult`` for the two cases the flag cannot see.

        Implements:
            - BT-05-004: Executes tree and returns execution result
            - BT-01-002: BTs execute to completion per invocation
            - BT-01-003: No continuous tick-based polling loops
        """
        self.logger.debug("Starting BT execution")

        errors: list[str] = []
        iteration = 0

        try:
            # Inside the try: a node whose setup() raises used to escape
            # execute_tree uncaught *and* skip the shutdown in `finally`,
            # so setup-time crashes were neither classified nor cleaned up.
            bt.setup()

            while iteration < max_iterations:
                iteration += 1
                bt.tick()

                root_status = bt.root.status

                # Terminal states: SUCCESS or FAILURE
                if root_status in (Status.SUCCESS, Status.FAILURE):
                    feedback = bt.root.feedback_message

                    # SL-04-001/AC-18: a bare "Status.FAILURE" is not a story.
                    # Fold the failing leaf's reason into the line that was
                    # already emitted, rather than adding a second record —
                    # many callers treat FAILURE as an expected idempotent
                    # skip and log their own explanation at DEBUG.
                    detail = feedback
                    if root_status == Status.FAILURE:
                        detail = (
                            detail
                            or self.get_failure_reason(bt.root)
                            or "<no reason reported>"
                        )
                    self.logger.info(
                        "BT execution completed: %s after %d ticks - %s",
                        root_status,
                        iteration,
                        detail,
                    )
                    # Tree dump is scaffolding, not story — DEBUG (SL-04-007).
                    if self.logger.isEnabledFor(logging.DEBUG):
                        tree_repr = unicode_tree(bt.root, show_status=True)
                        self.logger.debug(f"Final BT state:\n{tree_repr}")

                    return BTExecutionResult(
                        status=root_status,
                        feedback_message=feedback,
                        errors=None,
                    )

                # RUNNING: continue ticking
                if root_status == Status.RUNNING:
                    self.logger.debug(f"BT still running (tick {iteration})")
                    continue

                # INVALID: should not happen during execution
                if root_status == Status.INVALID:
                    # Not a protocol outcome — a tree in INVALID mid-execution
                    # is malformed, so retrying it cannot converge.
                    error_msg = f"BT entered INVALID state at tick {iteration}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                    return BTExecutionResult(
                        status=Status.FAILURE,
                        feedback_message=error_msg,
                        errors=errors,
                        internal_error=True,
                    )

            # Max iterations reached without completion.  Also not a protocol
            # outcome: a tree that will not settle in `max_iterations` ticks
            # will not settle on a retry either.
            error_msg = (
                f"BT execution exceeded max iterations ({max_iterations})"
            )
            self.logger.error(error_msg)
            errors.append(error_msg)
            return BTExecutionResult(
                status=Status.FAILURE,
                feedback_message=error_msg,
                errors=errors,
                internal_error=True,
            )

        except VultronError as e:
            # A node raised a domain error deliberately (28 such sites, e.g.
            # sync/nodes/canonical_entry.py).  Treated as attributable to the
            # protocol rather than to us.  Not a blanket retry licence: a
            # malformed peer message will not parse on a retry either, and
            # VultronActivityConstructionError wraps what is really a factory
            # misuse.  Consult the exception, not just the flag.
            error_msg = f"BT execution failed: {type(e).__name__}: {e}"
            self.logger.exception(error_msg)
            errors.append(error_msg)
            return BTExecutionResult(
                status=Status.FAILURE,
                feedback_message=error_msg,
                errors=errors,
            )

        except Exception as e:
            # Anything else is a programming error — a wrong-typed port, a
            # missing attribute, a bad key.  Still caught, because a half-ticked
            # tree must not escape into a FastAPI background task, but flagged
            # so callers do not mistake it for a protocol outcome and retry it
            # forever (CONCERN-3019).
            error_msg = (
                f"BT execution failed with internal error: "
                f"{type(e).__name__}: {e}"
            )
            self.logger.exception(error_msg)
            errors.append(error_msg)
            return BTExecutionResult(
                status=Status.FAILURE,
                feedback_message=error_msg,
                errors=errors,
                internal_error=True,
            )

        finally:
            # A raise here would replace the classified result with an
            # unrelated exception, losing the failure that actually mattered.
            try:
                bt.shutdown()
            except Exception:
                self.logger.exception("BT shutdown failed; result preserved")

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

        Checks the leadership guard before executing.  If ``is_leader()``
        returns ``False``, execution is skipped and a FAILURE result is
        returned immediately with a descriptive feedback message
        (SYNC-09-003).

        Typical usage from handler:
            result = bridge.execute_with_setup(
                tree=ValidateReportBT(...),
                actor_id=actor_id,
                activity=dispatchable.payload
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
            ``execute_tree`` classifies a failure during the ticks — see
            ``BTExecutionResult.internal_error``.  The leadership skip is a
            protocol outcome, not an internal error.

        Implements:
            - BT-05-001: BT execution bridge for handler-to-BT invocation
            - SYNC-09-003: Leadership guard check before BT execution
        """
        if not self.is_leader():
            msg = (
                "BT execution skipped: this node is not the replication leader"
            )
            self.logger.warning(msg)
            return BTExecutionResult(
                status=Status.FAILURE,
                feedback_message=msg,
            )
        with _BT_GLOBAL_LOCK:
            managed_keys = ["datalayer", "trigger_activity_factory"]
            storage = py_trees.blackboard.Blackboard.storage
            key_aliases: set[str] = set()
            for key in managed_keys:
                key_aliases.add(key)
                key_aliases.add(f"/{key}")
            previous_values = {
                key: (key in storage, storage.get(key)) for key in key_aliases
            }
            try:
                # Inside the try for the same reason execute_tree() moved
                # bt.setup() inside its own: setup_tree() does fallible work
                # (store cloning, port construction, register_key/setattr over
                # arbitrary context_data), and a programming error there used to
                # escape BTBridge entirely — unclassified, and into a FastAPI
                # background task.  Classify it like any other internal error
                # rather than letting the one call outside the net through
                # (CONCERN-3019).
                bt = self.setup_tree(tree, actor_id, activity, **context_data)
                return self.execute_tree(bt, max_iterations)
            except VultronError as e:
                error_msg = f"BT setup failed: {type(e).__name__}: {e}"
                self.logger.exception(error_msg)
                return BTExecutionResult(
                    status=Status.FAILURE,
                    feedback_message=error_msg,
                    errors=[error_msg],
                )
            except Exception as e:
                error_msg = (
                    f"BT setup failed with internal error: "
                    f"{type(e).__name__}: {e}"
                )
                self.logger.exception(error_msg)
                return BTExecutionResult(
                    status=Status.FAILURE,
                    feedback_message=error_msg,
                    errors=[error_msg],
                    internal_error=True,
                )
            finally:
                # Restore managed blackboard keys to their pre-execution state.
                # setup_tree() writes these keys to Blackboard.storage, which
                # is process-global; without explicit cleanup the entries
                # persist after execution, keeping SqliteDataLayer objects and
                # TriggerActivityAdapter objects (both hold sqlite3 connections)
                # alive until the next BT execution overwrites them.  That
                # delayed release causes ResourceWarning: unclosed database
                # when GC runs at an unpredictable moment — typically during
                # the next test's SQL activity, which pytest promotes to a test
                # failure via PytestUnraisableExceptionWarning (pytest 9.1.0+).
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
                for _key, (_had_value, _value) in previous_values.items():
                    if _had_value:
                        storage[_key] = _value
                    else:
                        storage.pop(_key, None)

    @staticmethod
    def get_failure_reason(
        tree: py_trees.behaviour.Behaviour,
    ) -> str:
        """Return a human-readable explanation for a tree that returned FAILURE.

        Performs a depth-first walk of the tree and returns the
        ``feedback_message`` of the first node whose status is
        ``Status.FAILURE``.  If no node carries a message, the class name of
        that node is returned instead.  If the tree succeeded (or is still
        RUNNING), an empty string is returned.

        Args:
            tree: Root behavior node to inspect.

        Returns:
            First FAILURE node's ``feedback_message``, its class name, or
            ``""`` when no FAILURE node is found.
        """
        stack = [tree]
        while stack:
            node = stack.pop()
            if node.status == Status.FAILURE:
                if not node.children:
                    # Leaf node — this is the actual source of failure.
                    return node.feedback_message or node.__class__.__name__
                # Composite node — the failure originates in a child.
                stack.extend(reversed(node.children))
        return ""

    @staticmethod
    def get_tree_visualization(
        tree: py_trees.behaviour.Behaviour, show_status: bool = False
    ) -> str:
        """
        Get unicode visualization of behavior tree structure.

        Useful for logging tree structure from handlers or debugging.

        Args:
            tree: Root behavior node to visualize
            show_status: Include node execution status in visualization

        Returns:
            String representation of tree with unicode art
        """
        return unicode_tree(tree, show_status=show_status)
