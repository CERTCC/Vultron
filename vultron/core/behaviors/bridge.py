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

Per specs/behavior-tree-integration.md:
- BT-05-001: Provides BT execution bridge for handler-to-BT invocation
- BT-05-002: Sets up py_trees context with DataLayer access
- BT-05-003: Populates blackboard with activity and actor state
- BT-05-004: Executes tree and returns execution result

Per specs/sync-log-replication.md:
- SYNC-09-003: Leadership role-check port; always True in single-node.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable

import py_trees
from py_trees.common import Status
from py_trees.display import unicode_tree

from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


@dataclass
class BTExecutionResult:
    """Result of BT execution returned to handler."""

    status: Status
    feedback_message: str = ""
    errors: list[str] | None = None


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
        datalayer: DataLayer,
        is_leader: Callable[[], bool] = _default_is_leader,
    ):
        """
        Initialize BT bridge with DataLayer access and optional leadership guard.

        Args:
            datalayer: DataLayer implementation for persistent state access.
            is_leader: Callable returning True iff this node is the
                replication leader.  Defaults to a function that always
                returns True (single-node behaviour).  Per SYNC-09-003.
        """
        self.datalayer = datalayer
        self.is_leader = is_leader
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )

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

        blackboard.datalayer = self.datalayer
        blackboard.actor_id = actor_id

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

        # Log tree structure for visibility (DEBUG level)
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
            BTExecutionResult with final status, feedback, and any errors

        Implements:
            - BT-05-004: Executes tree and returns execution result
            - BT-01-002: BTs execute to completion per invocation
            - BT-01-003: No continuous tick-based polling loops
        """
        self.logger.debug("Starting BT execution")

        bt.setup()
        errors = []
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1
                bt.tick()

                root_status = bt.root.status

                # Terminal states: SUCCESS or FAILURE
                if root_status in (Status.SUCCESS, Status.FAILURE):
                    feedback = bt.root.feedback_message

                    # Log final tree state with status visualization
                    tree_repr = unicode_tree(bt.root, show_status=True)
                    self.logger.info(
                        f"BT execution completed: {root_status} after {iteration} ticks - {feedback}"
                    )
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
                    error_msg = f"BT entered INVALID state at tick {iteration}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                    return BTExecutionResult(
                        status=Status.FAILURE,
                        feedback_message=error_msg,
                        errors=errors,
                    )

            # Max iterations reached without completion
            error_msg = (
                f"BT execution exceeded max iterations ({max_iterations})"
            )
            self.logger.error(error_msg)
            errors.append(error_msg)
            return BTExecutionResult(
                status=Status.FAILURE,
                feedback_message=error_msg,
                errors=errors,
            )

        except Exception as e:
            error_msg = f"BT execution failed with exception: {e}"
            self.logger.exception(error_msg)
            errors.append(error_msg)
            return BTExecutionResult(
                status=Status.FAILURE,
                feedback_message=error_msg,
                errors=errors,
            )

        finally:
            bt.shutdown()

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
            BTExecutionResult with execution status and feedback

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
        bt = self.setup_tree(tree, actor_id, activity, **context_data)
        return self.execute_tree(bt, max_iterations)

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
