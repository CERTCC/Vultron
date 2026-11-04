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

"""BTBridge execution: tick a tree to completion and classify the outcome.

Per specs/behavior-tree-integration.yaml:
- BT-05-004: Executes tree and returns execution result
- BT-01-002: BTs execute to completion per invocation
"""

import logging

import py_trees
from py_trees.common import Status
from py_trees.display import unicode_tree

from vultron.core.behaviors.bridge.result import BTExecutionResult
from vultron.errors import (
    INTERNAL_FAULTS,
    VultronError,
)


class _BridgeExecution:
    """Tick loop, exception classification and failure reporting for :class:`BTBridge`.

    A mixin of ``BTBridge`` only; ``logger`` is set by ``BTBridge.__init__``.
    """

    logger: logging.Logger

    def _exception_result(
        self,
        e: BaseException,
        *,
        prefix: str,
        internal_error: bool = False,
    ) -> BTExecutionResult:
        """Build the FAILURE result for an exception caught at a bridge boundary.

        The bridge catches exceptions at three boundaries — the ticks inside
        ``execute_tree``, and ``setup_tree`` and ``execute_tree`` as called from
        ``execute_with_setup`` — each split by whether the exception is a
        ``VultronError``, so six handlers in total.  Every one of them owes the
        caller the same three consistent facts: a message naming the exception
        type, a log record at the level that classification implies, and a
        matching ``internal_error`` flag.  Keeping them in one place is what
        stops the three from drifting apart: #3080 was a log-level divergence
        between two of these handlers that a reader comparing them could not
        tell was accidental (CS-22-001).

        The one broad handler in this module that does *not* come here is the
        ``bt.shutdown()`` guard in ``execute_tree``'s ``finally``: it has no
        result to build, because its whole job is to preserve the result the
        classified handlers already returned.

        ``internal_error`` is the single input that drives all three outputs,
        rather than each handler deciding independently:

        - ``False`` — a protocol outcome the tree is entitled to report (a
          deliberate ``VultronError``).  Logged at WARNING, no traceback, and
          the message is bare ``"<prefix>: <Type>: <msg>"``.
        - ``True`` — a programming error that escaped a node.  Logged with
          ``logger.exception`` (ERROR + traceback, which requires that this
          method be called from inside the ``except`` block), and the message
          says so: ``"<prefix> with internal error: <Type>: <msg>"``.

        Args:
            e: The caught exception.  Its type name is always included,
                because ``str(e)`` is empty for several common cases
                (e.g. a bare ``AttributeError``).
            prefix: Which boundary was crossed — ``"BT setup failed"`` or
                ``"BT execution failed"``.  The two must stay distinguishable
                so an execution error is never reported as a setup error.
            internal_error: Classification, as described above.  A
                ``VultronWiringError`` is always internal: a missing DataLayer
                or port is our composition fault, not the protocol's, whatever
                base class it shares (#2255).  A ``VultronBTInternalError`` is
                internal too: a node raises it to carry a nested bridge's
                ``internal_error`` across the hop (#4113).

        Returns:
            A FAILURE ``BTExecutionResult`` carrying the composed message as
            both ``feedback_message`` and the sole entry in ``errors``.
        """
        internal_error = internal_error or isinstance(e, INTERNAL_FAULTS)
        if internal_error:
            error_msg = (
                f"{prefix} with internal error: {type(e).__name__}: {e}"
            )
            self.logger.exception("%s", error_msg)
        else:
            error_msg = f"{prefix}: {type(e).__name__}: {e}"
            self.logger.warning("%s", error_msg)

        return BTExecutionResult(
            status=Status.FAILURE,
            feedback_message=error_msg,
            errors=[error_msg],
            internal_error=internal_error,
        )

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
                    # Guard kept: lazy args do not skip the unicode_tree call.
                    if self.logger.isEnabledFor(logging.DEBUG):
                        tree_repr = unicode_tree(bt.root, show_status=True)
                        self.logger.debug("Final BT state:\n%s", tree_repr)

                    return BTExecutionResult(
                        status=root_status,
                        feedback_message=feedback,
                        errors=None,
                    )

                # RUNNING: continue ticking
                if root_status == Status.RUNNING:
                    self.logger.debug("BT still running (tick %s)", iteration)
                    continue

                # INVALID: should not happen during execution
                if root_status == Status.INVALID:
                    # Not a protocol outcome — a tree in INVALID mid-execution
                    # is malformed, so retrying it cannot converge.
                    error_msg = f"BT entered INVALID state at tick {iteration}"
                    self.logger.error("%s", error_msg)
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
            self.logger.error("%s", error_msg)
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
            #
            # ``errors`` is provably empty on both exception paths — the two
            # branches that append to it (INVALID, max_iterations) return
            # immediately — so the helper's single-entry list is the same list
            # this handler used to build.
            return self._exception_result(e, prefix="BT execution failed")

        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            # Anything else is a programming error — a wrong-typed port, a
            # missing attribute, a bad key.  Still caught, because a half-ticked
            # tree must not escape into a FastAPI background task, but flagged
            # so callers do not mistake it for a protocol outcome and retry it
            # forever (CONCERN-3019).
            return self._exception_result(
                e, prefix="BT execution failed", internal_error=True
            )

        finally:
            # A raise here would replace the classified result with an
            # unrelated exception, losing the failure that actually mattered.
            try:
                bt.shutdown()
            except Exception:
                self.logger.exception("BT shutdown failed; result preserved")

    @staticmethod
    def get_failure_reason(
        tree: py_trees.behaviour.Behaviour,
    ) -> str:
        """Return a human-readable explanation for a tree that returned FAILURE.

        Follows the chain of FAILURE nodes down from the root and returns the
        ``feedback_message`` of the leaf it ends at, or that leaf's class name
        when it carries no message.  At each failed composite it follows the
        *last* failed child: a failed Sequence has exactly one, and in a failed
        Selector every child failed, so the last is the final attempt.  The
        first is usually the cheap "already done?" guard whose failure is what
        sent the Selector on, and naming it hides the real cause.  A decorator
        that failed while its child did not (an ``Inverter``) is itself the
        leaf.  If the tree succeeded (or is still RUNNING), an empty string is
        returned.

        Args:
            tree: Root behavior node to inspect.

        Returns:
            The failing leaf's ``feedback_message``, its class name, or
            ``""`` when the tree did not fail.
        """
        node = tree
        if node.status != Status.FAILURE:
            return ""
        while True:
            failed = [c for c in node.children if c.status == Status.FAILURE]
            if not failed:
                return node.feedback_message or node.__class__.__name__
            node = failed[-1]

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
