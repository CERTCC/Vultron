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
"""The call-out seam: turn a backend's answer into tree behaviour (ADR-0183).

Every call-out backend gives one answer, *yes*, *no* or *error*, with the data
its capability declares (:mod:`~vultron.core.behaviors.call_out.answer`).
:class:`SynchronousCallOut` is the one place that interprets it:

- *yes* writes the declared outputs to the blackboard and the node succeeds;
- *no* writes the refusal payload to the declared refusal ports and the node
  fails;
- *error* raises :class:`CallOutBackendError`, naming the node, so the message
  is not judged and stays in holding to be tried again.

The seam also rejects an answer that is not a
:class:`~vultron.core.behaviors.call_out.answer.CallOutAnswer`, has a verdict
outside the three, or carries data its declaration does not name, by raising
:class:`CallOutContractError`.  So does a backend that returns
``Status.RUNNING`` (BT-18-011, the general case of the codebase-wide
no-``RUNNING`` invariant from ADR-0080), or one that is not a
:class:`~vultron.core.behaviors.call_out.backend.CallOutBackend`.

Both errors are plain ``RuntimeError`` subclasses, **not**
:class:`~vultron.errors.VultronError`: ``BTBridge`` classifies them via its
``except Exception`` branch as ``internal_error=True``, never as a protocol
``FAILURE``.  A call-out backend is injected from *outside* the repository
(BT-23-004), so only a runtime guard at the seam can police it.

:class:`TimeBoundedCallOut` is the seam with a time budget (BT-18-015).  It
measures, on a stopwatch, how long its backend took to answer, and raises
:class:`CallOutBudgetExceededError`, naming the node and the budget, when the
backend took longer (BT-18-027).  A py_trees tick is synchronous and the
backend runs on the ticking thread, so the seam **detects** an overrun after
the backend returns; it does **not** interrupt the backend.  The late answer
is discarded, so an overrun never becomes a decision, but the worker is held
for as long as the backend takes, every time; a backend that never returns
is not caught here (BT-18-025 forbids the blocking I/O that would cause it).
What the seam bounds is what the tree acts on, not how long a worker waits.
The budget is the local actor's ``ActorConfig.call_out_time_budget``
(BT-18-026), read when a tree builds the node.

The seam is applied uniformly at the bundle boundary via
:func:`guard_call_out_factory`, so every node a call-out bundle hands out is
a :class:`TimeBoundedCallOut`, with no change in the tree-builder call sites.
See :class:`~vultron.core.behaviors.call_out.bundles.base.CallOutBundle`.

References
----------
- ADR-0080: ``docs/adr/0080-protocol-asks-not-suspended-behaviors.md``
- ADR-0183: ``docs/adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md``
- ADR-0176: ``docs/adr/0176-an-act-reads-the-clock-once-at-its-edge.md``
  (elapsed time is a stopwatch, not the clock)
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-002, BT-18-007,
  BT-18-011, BT-18-015, BT-18-018, BT-18-026, BT-18-027
- ``notes/call-out-configuration.md`` — "A Backend Answers Yes, No or Error"
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import timedelta

import py_trees
from py_trees.common import Access, Status

from vultron.config.app import load_actor_config
from vultron.core.behaviors.call_out.answer import (
    CallOutAnswer,
    CallOutVerdict,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.errors import (
    CallOutBackendError,
    CallOutBudgetExceededError,
    CallOutContractError,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.behaviors.stopwatch import SystemStopwatch
from vultron.core.ports.clock import StopwatchPort

#: Sentinel attribute marking a factory returned by :func:`guard_call_out_factory`,
#: so re-wrapping an already-guarded factory (e.g. one bundle's factory passed
#: into another bundle's constructor) is a no-op rather than a nested decorator.
_GUARDED_ATTR = "_vultron_call_out_guarded"


def _check_data(
    node: str,
    what: str,
    data: Mapping[str, object],
    declared: Mapping[str, type],
) -> None:
    """Raise unless *data* names exactly the *declared* ports, typed."""
    undeclared = sorted(set(data) - set(declared))
    missing = sorted(set(declared) - set(data))
    if undeclared or missing:
        raise CallOutContractError(
            f"Call-out backend {node!r} answered {what} with "
            f"undeclared ports {undeclared} and missing ports {missing}; "
            "an answer carries exactly the ports its declaration names "
            "(BT-18-002, ADR-0183)."
        )
    for key, typ in declared.items():
        value = data[key]
        if not isinstance(value, typ):
            raise CallOutContractError(
                f"Call-out backend {node!r} answered {what} with "
                f"{key}={type(value).__name__}, not the declared "
                f"{typ.__name__} (ADR-0183)."
            )


class SynchronousCallOut(py_trees.decorators.Decorator):
    """The call-out seam: turns its backend's answer into tree behaviour.

    Ticks the decorated :class:`CallOutBackend`, takes its answer and, per
    ADR-0183, writes the *yes* outputs and returns ``SUCCESS``, writes the *no*
    refusal payload and returns ``FAILURE``, or raises
    :class:`CallOutBackendError` on *error*.  Anything else raises
    :class:`CallOutContractError`.

    The seam adopts the child's ``name`` so it is transparent to callers that
    navigate a tree by node name; the backend remains available as
    ``self.decorated``.
    """

    def __init__(self, child: py_trees.behaviour.Behaviour) -> None:
        if not isinstance(child, CallOutBackend):
            raise CallOutContractError(
                f"Call-out backend {child.name!r} ({type(child).__name__}) is "
                "not a CallOutBackend; a backend answers yes, no or error "
                "through CallOutBackend.answer() (ADR-0183)."
            )
        # Adopt the child's name so the seam is transparent in tree walks and
        # visualizations; the backend is reachable via ``self.decorated``.
        super().__init__(name=child.name, child=child)
        self._backend: CallOutBackend = child
        contract = child.contract
        # Built here, not in setup(), so a tick without setup() still writes
        # the declared data (BT-23-013).
        self._bb = self.attach_blackboard_client(
            name=f"{type(self).__name__}_{child.name}"
        )
        for key in (*contract.outputs, *contract.refusal_ports):
            self._bb.register_key(key, Access.WRITE)

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        """Tick the backend armed for this one tick, then interpret it.

        The backend refuses any tick it was not armed for, so a backend ticked
        anywhere but here raises (BT-18-037).
        """
        self._backend.arm()
        try:
            yield from super().tick()
        finally:
            self._backend.disarm()

    def update(self) -> Status:
        """Interpret the backend's answer (ADR-0183); forbid ``RUNNING``."""
        answer = self._take_answer()
        if answer.verdict is CallOutVerdict.ERROR:
            self._raise_error(answer)
        self._write(self._checked_data(answer))
        if answer.verdict is CallOutVerdict.YES:
            return Status.SUCCESS
        self.feedback_message = answer.reason or ""
        return Status.FAILURE

    def _take_answer(self) -> CallOutAnswer:
        """The backend's answer for this tick; raise if it gave none."""
        backend = self._backend
        if backend.status == Status.RUNNING:
            raise CallOutContractError(
                f"Call-out backend {backend.name!r} "
                f"({type(backend).__name__}) returned Status.RUNNING; "
                "a call-out point MUST answer synchronously (BT-18-011, "
                "ADR-0080)."
            )
        answer = backend.take_answer()
        if not isinstance(answer, CallOutAnswer) or answer.verdict not in (
            CallOutVerdict.YES,
            CallOutVerdict.NO,
            CallOutVerdict.ERROR,
        ):
            raise CallOutContractError(
                f"Call-out backend {backend.name!r} "
                f"({type(backend).__name__}) gave {answer!r}, not a "
                "CallOutAnswer of yes, no or error (ADR-0183)."
            )
        return answer

    def _checked_data(self, answer: CallOutAnswer) -> dict[str, object]:
        """The blackboard data of a *yes* or *no*, checked against the contract."""
        name = self._backend.name
        contract = self._backend.contract
        if answer.verdict is CallOutVerdict.YES:
            _check_data(name, "yes", answer.outputs, contract.outputs)
            return dict(answer.outputs)
        if contract.refusal_reason_key in answer.refusal:
            raise CallOutContractError(
                f"Call-out backend {name!r} answered no with a refusal field "
                f"named {contract.refusal_reason_key!r}, its reason key; the "
                "reason travels only as the answer's reason (ADR-0183)."
            )
        # The model guarantees a reason on a no answer.
        assert answer.reason is not None
        payload = {
            contract.refusal_reason_key: answer.reason,
            **answer.refusal,
        }
        _check_data(name, "no", payload, contract.refusal_ports)
        return payload

    def _write(self, data: Mapping[str, object]) -> None:
        for key, value in data.items():
            setattr(self._bb, key, value)

    def _raise_error(self, answer: CallOutAnswer) -> None:
        """Log and raise an *error* answer; nothing reaches the blackboard."""
        # The model guarantees diagnostics on an error answer.
        assert answer.diagnostics is not None
        name = self._backend.name
        node_logger(self).warning(
            "Call-out backend %r answered error; the message is not judged:"
            " %s",
            name,
            answer.diagnostics,
        )
        raise CallOutBackendError(name, answer.diagnostics)


class TimeBoundedCallOut(SynchronousCallOut):
    """The call-out seam with a time budget (BT-18-015, BT-18-027).

    Reads *stopwatch* just before it ticks its backend and again when the
    backend has returned.  When the backend took longer than *budget*, it
    discards the answer, whatever its verdict, and raises
    :class:`CallOutBudgetExceededError` naming the node and the budget;
    otherwise it interprets the answer as :class:`SynchronousCallOut` does.

    It **detects** an overrun after the fact and does **not** interrupt the
    backend: the backend runs on the ticking thread, and a py_trees tick is
    synchronous.  So a slow backend still holds the worker for as long as it
    takes, on every call; the seam only guarantees that the tree never acts on
    a late answer, and that the operator sees which node was slow.

    A stopwatch reading is not a time of day: it feeds this limit and nothing
    else (ADR-0176).
    """

    def __init__(
        self,
        child: py_trees.behaviour.Behaviour,
        *,
        budget: timedelta,
        stopwatch: StopwatchPort,
    ) -> None:
        if budget.total_seconds() <= 0:
            raise CallOutContractError(
                f"Call-out backend {child.name!r} was given a time budget of "
                f"{budget}; a budget must be positive (BT-18-015)."
            )
        super().__init__(child)
        self.budget = budget
        self._stopwatch = stopwatch
        self._started: float | None = None

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        """Start the stopwatch, then tick as :class:`SynchronousCallOut`."""
        self._started = self._stopwatch.seconds()
        try:
            yield from super().tick()
        finally:
            self._started = None

    def update(self) -> Status:
        """Raise on an overrun; otherwise interpret the answer (ADR-0183)."""
        if self._started is None:
            raise CallOutContractError(
                f"Call-out seam {self.name!r} was updated outside its own "
                "tick, so it cannot time its backend (BT-18-015)."
            )
        elapsed = timedelta(seconds=self._stopwatch.seconds() - self._started)
        if elapsed > self.budget:
            # Discard the late answer so no later tick can read it.
            self._backend.take_answer()
            error = CallOutBudgetExceededError(
                self._backend.name, self.budget, elapsed
            )
            node_logger(self).warning("%s", error)
            raise error
        return super().update()


def time_bounded_call_out(
    node: py_trees.behaviour.Behaviour,
) -> TimeBoundedCallOut:
    """Put *node* behind the time-bounded seam, with the configured budget.

    The budget is the local actor's ``ActorConfig.call_out_time_budget``,
    read now, when the tree is built (BT-18-026); the stopwatch is the
    system stopwatch.  Idempotent: a :class:`TimeBoundedCallOut` is returned
    unchanged, and a plain :class:`SynchronousCallOut` has its backend moved
    behind a time-bounded seam, so no factory product escapes the budget.
    """
    if isinstance(node, TimeBoundedCallOut):
        return node
    if isinstance(node, SynchronousCallOut):
        node = node.decorated
    return TimeBoundedCallOut(
        node,
        budget=load_actor_config().call_out_time_budget,
        stopwatch=SystemStopwatch(),
    )


def guard_call_out_factory(
    factory: CallOutBackendFactory,
) -> CallOutBackendFactory:
    """Wrap *factory* so the node it produces sits behind the seam.

    Returns a new :class:`CallOutBackendFactory` whose product is the original
    node wrapped in :class:`TimeBoundedCallOut` by
    :func:`time_bounded_call_out`.  A product that is not a
    :class:`CallOutBackend` raises :class:`CallOutContractError` when the tree
    is built.  Idempotent: an already-guarded factory is returned unchanged,
    and a node that is already a seam is not double-wrapped.
    """
    if getattr(factory, _GUARDED_ATTR, False):
        return factory

    def guarded(name: str) -> py_trees.behaviour.Behaviour:
        return time_bounded_call_out(factory(name))

    setattr(guarded, _GUARDED_ATTR, True)
    return guarded


def unwrap_call_out(
    node: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    """Return the backend behind a seam, else *node*.

    Convenience for callers (and tests) that need the underlying backend node
    rather than the transparent seam.
    """
    if isinstance(node, SynchronousCallOut):
        return node.decorated
    return node


__all__ = [
    "CallOutBackendError",
    "CallOutBudgetExceededError",
    "CallOutContractError",
    "SynchronousCallOut",
    "TimeBoundedCallOut",
    "guard_call_out_factory",
    "time_bounded_call_out",
    "unwrap_call_out",
]
