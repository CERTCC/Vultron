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
"""

from __future__ import annotations

from collections.abc import Callable

from py_trees.common import Status

from vultron.core.behaviors.call_out.answer import (
    BINARY_CONTRACT,
    CallOutAnswer,
    CallOutContract,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.guard import SynchronousCallOut
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory

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


def answering(
    fixed: CallOutAnswer,
    contract: CallOutContract = BINARY_CONTRACT,
) -> CallOutBackendFactory:
    """A factory whose backend gives *fixed* against *contract*."""

    def factory(name: str) -> FixedAnswerBackend:
        return FixedAnswerBackend(name, fixed=fixed, contract=contract)

    return factory


def yes_with(outputs: dict[str, object]) -> CallOutBackendFactory:
    """A factory whose backend answers *yes* with *outputs*, as declared."""
    return answering(
        CallOutAnswer.yes(outputs),
        CallOutContract(outputs={k: type(v) for k, v in outputs.items()}),
    )


def no_because(reason: str = TEST_REFUSAL_REASON) -> CallOutBackendFactory:
    """A factory whose backend answers *no* with *reason*."""
    return answering(CallOutAnswer.no(reason))


def error(
    diagnostics: str = "test backend unreachable",
) -> CallOutBackendFactory:
    """A factory whose backend answers *error* with *diagnostics*."""
    return answering(CallOutAnswer.error(diagnostics))


#: A factory whose backend answers *yes* with no outputs.
yes: Callable[[str], FixedAnswerBackend] = answering(CallOutAnswer.yes())  # type: ignore[assignment]

#: A factory whose backend answers *no* with :data:`TEST_REFUSAL_REASON`.
no: Callable[[str], FixedAnswerBackend] = no_because()  # type: ignore[assignment]


def tick_call_out(backend: CallOutBackend) -> Status:
    """Tick *backend* behind the seam once; return the status a tree sees."""
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
