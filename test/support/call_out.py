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
"""Call-out backends and a seam tick for tests (ADR-0183).

Every call-out backend answers through
:class:`~vultron.core.behaviors.call_out.backend.CallOutBackend` and is read
only by the seam, so a test injects one of these instead of a raw
``py_trees`` node:

- :func:`answering` builds a factory whose backend gives a fixed answer;
  :data:`yes`, :data:`no` and :func:`error` are its common cases.
- :class:`CountingBackend` answers fixed and counts its ticks.
- :func:`tick_call_out` ticks one backend behind the seam and returns the
  status the tree would see.
- :func:`acting` builds an Actuator factory whose backend gives a fixed
  answer and records every request it is called with; :data:`acts` and
  :data:`declines_to_act` are its common cases.
"""

from __future__ import annotations

import gc
import traceback
from types import TracebackType
from typing import Protocol

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.call_out.actuator import (
    ActuationRequest,
    ActuatorBackend,
)
from vultron.core.behaviors.call_out.answer import (
    BINARY_CONTRACT,
    CallOutAnswer,
    CallOutContract,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.guard import (
    SynchronousCallOut,
    unwrap_call_out,
)


class refused_class:
    """Assert the block's class definition is refused, then collect the class.

    A class whose ``__init_subclass__`` raises is already listed in its
    bases' ``__subclasses__()``, with no ABC cache of its own, so it shares
    its first base's.  Until it is collected, an ``isinstance`` check that
    walks it writes a wrong verdict into that base's cache: a bound
    ``AlwaysSucceed`` default then reads as not an ``AlwaysSucceed``, or as
    an Actuator, for the rest of the worker (#6303).  The refusal's
    traceback frames hold the class, so they are cleared before it is
    collected.
    """

    def __init__(self, match: str) -> None:
        self._raises = pytest.raises(TypeError, match=match)

    def __enter__(self) -> None:
        self._raises.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        suppressed = bool(self._raises.__exit__(exc_type, exc, tb))
        if tb is not None:
            traceback.clear_frames(tb)
        del self._raises
        gc.collect()
        return suppressed


#: The reason a test backend's *no* carries unless the test gives one.
TEST_REFUSAL_REASON = "test backend declines"


class FixedAnswerBackend(CallOutBackend):
    """A backend that gives the same answer on every tick."""

    def __init__(
        self,
        name: str = "",
        *,
        fixed: CallOutAnswer,
        contract: CallOutContract = BINARY_CONTRACT,
    ) -> None:
        super().__init__(name)
        self._fixed = fixed
        # An instance attribute shadows the class declaration for this node.
        self.contract = contract  # type: ignore[misc]

    def answer(self) -> CallOutAnswer:
        return self._fixed


class CountingBackend(FixedAnswerBackend):
    """A :class:`FixedAnswerBackend` that counts how often it is ticked."""

    def __init__(self, name: str = "", **kwargs: object) -> None:
        super().__init__(name, **kwargs)  # type: ignore[arg-type]
        self.ticks = 0

    def answer(self) -> CallOutAnswer:
        self.ticks += 1
        return super().answer()


class FixedAnswerFactory(Protocol):
    """A call-out backend factory whose product is a :class:`FixedAnswerBackend`.

    Structurally a
    :class:`~vultron.core.behaviors.call_out.protocol.CallOutBackendFactory`,
    so a test passes it to a tree builder, and its product is typed, so a test
    may also tick it directly with :func:`tick_call_out`.
    """

    def __call__(self, name: str) -> FixedAnswerBackend: ...


def answering(
    fixed: CallOutAnswer,
    contract: CallOutContract = BINARY_CONTRACT,
) -> FixedAnswerFactory:
    """A factory whose backend gives *fixed* against *contract*."""

    def factory(name: str) -> FixedAnswerBackend:
        return FixedAnswerBackend(name, fixed=fixed, contract=contract)

    return factory


def yes_with(outputs: dict[str, object]) -> FixedAnswerFactory:
    """A factory whose backend answers *yes* with *outputs*, as declared."""
    return answering(
        CallOutAnswer.yes(outputs),
        CallOutContract(outputs={k: type(v) for k, v in outputs.items()}),
    )


def no_because(reason: str = TEST_REFUSAL_REASON) -> FixedAnswerFactory:
    """A factory whose backend answers *no* with *reason*."""
    return answering(CallOutAnswer.no(reason))


def error(
    diagnostics: str = "test backend unreachable",
) -> FixedAnswerFactory:
    """A factory whose backend answers *error* with *diagnostics*."""
    return answering(CallOutAnswer.error(diagnostics))


#: A factory whose backend answers *yes* with no outputs.
yes: FixedAnswerFactory = answering(CallOutAnswer.yes())

#: A factory whose backend answers *no* with :data:`TEST_REFUSAL_REASON`.
no: FixedAnswerFactory = no_because()


#: The target :func:`tick_call_out` binds to an unbound Actuator.
TEST_ACTUATION_TARGET = "urn:test:actuation-target"


class FixedAnswerActuator(ActuatorBackend):
    """An Actuator that gives the same answer and records each request."""

    def __init__(self, name: str = "", *, fixed: CallOutAnswer) -> None:
        super().__init__(name)
        self._fixed = fixed
        self.requests: list[ActuationRequest] = []

    def act(self, request: ActuationRequest) -> CallOutAnswer:
        self.requests.append(request)
        return self._fixed


class FixedAnswerActuatorFactory(Protocol):
    """An Actuator factory whose product is a :class:`FixedAnswerActuator`."""

    def __call__(self, name: str) -> FixedAnswerActuator: ...


def acting(fixed: CallOutAnswer) -> FixedAnswerActuatorFactory:
    """An Actuator factory whose backend gives *fixed*."""

    def factory(name: str) -> FixedAnswerActuator:
        return FixedAnswerActuator(name, fixed=fixed)

    return factory


def acting_as(
    label: str, fixed: CallOutAnswer | None = None
) -> FixedAnswerActuatorFactory:
    """An Actuator factory whose backend is named *label*, whatever the tree asks.

    For a test that finds the node a factory placed by its name.  The
    backend answers *fixed*, *yes* by default.
    """
    answer = fixed if fixed is not None else CallOutAnswer.yes()

    def factory(name: str) -> FixedAnswerActuator:
        return FixedAnswerActuator(label, fixed=answer)

    return factory


#: An Actuator factory whose backend answers *yes*: the side effect happened.
acts: FixedAnswerActuatorFactory = acting(CallOutAnswer.yes())

#: An Actuator factory whose backend answers *no* with
#: :data:`TEST_REFUSAL_REASON`: it decided not to act.
declines_to_act: FixedAnswerActuatorFactory = acting(
    CallOutAnswer.no(TEST_REFUSAL_REASON)
)


def bind_test_target(
    node: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    """Bind :data:`TEST_ACTUATION_TARGET` to *node* when it is an unbound Actuator.

    For a test that ticks a bundle's product directly, outside a tree, as a
    tree's ``actuator_call`` would bind it (BT-18-041).  Returns *node*.
    """
    backend = unwrap_call_out(node)
    if isinstance(backend, ActuatorBackend) and backend.target is None:
        backend.bind_target(TEST_ACTUATION_TARGET)
    return node


def tick_call_out(backend: CallOutBackend) -> Status:
    """Tick *backend* behind the seam once; return the status a tree sees.

    An Actuator no tree has bound is bound to :data:`TEST_ACTUATION_TARGET`
    first, as a tree would bind its one target (BT-18-041).
    """
    bind_test_target(backend)
    seam = backend.parent
    if not isinstance(seam, SynchronousCallOut):
        seam = SynchronousCallOut(backend)
    seam.tick_once()
    return seam.status


def answer_for(status: Status) -> CallOutAnswer:
    """The answer a test backend gives for the *status* a test names.

    ``SUCCESS`` is *yes* with no outputs and ``FAILURE`` is *no* with
    :data:`TEST_REFUSAL_REASON`; no other status is an answer.
    """
    if status == Status.SUCCESS:
        return CallOutAnswer.yes()
    if status == Status.FAILURE:
        return CallOutAnswer.no(TEST_REFUSAL_REASON)
    raise ValueError(f"{status} is not a call-out answer")
