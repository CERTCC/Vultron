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
"""Run a use case or a tree in a test as one act, as production's edge does.

In production every tree run belongs to an act (ADR-0176): the inbox opens
one per delivery (``process_payload``), a trigger opens its own from its
clock, and a sweep opens one.  A test that calls ``uc.execute()`` or
``BTBridge.execute_with_setup`` directly skips that edge, so a node that reads
the act's instant finds none.  These runners put the edge back:

- :func:`run_in_act` runs a use case.  A use case that holds a clock (every
  trigger) opens its own act from it, so it is run as it is: give it a
  :class:`FixedClock` at construction to pin its instant.  Any other use case
  (received, query) runs inside an act opened here at *at*, the way
  ``process_payload`` runs it.
- :func:`run_tree` runs a tree through a bridge as the outermost run of an
  act at *at*.

Inside a run that already carries an instant (a nested run, or a test that
opened an act itself), both inherit it, as a nested production run does,
and *at* must be omitted.

*at* defaults to the wall clock when the act opens, because most fixtures
are built relative to it ("seven days from now").

The guard in ``test/architecture/test_tests_run_acts_through_the_runner.py``
fails on a direct call anywhere else under ``test/``.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar

import py_trees

from vultron.core.behaviors.bridge.act_instant import (
    act_instant_in_tree_run,
    inherited_act_instant,
    open_act,
)
from vultron.core.behaviors.bridge.bt_bridge import BTBridge
from vultron.core.behaviors.bridge.result import BTExecutionResult

R_co = TypeVar("R_co", covariant=True)


class _Executes(Protocol[R_co]):
    """A use case: anything with a no-argument ``execute()``."""

    def execute(self) -> R_co: ...


class FixedClock:
    """A ``ClockPort`` that always reads *at* (the wall clock when omitted)."""

    def __init__(self, at: datetime | None = None) -> None:
        self._at = at if at is not None else datetime.now(tz=UTC)

    def now(self) -> datetime:
        return self._at


@contextmanager
def in_act(at: datetime | None = None) -> Iterator[datetime]:
    """Open one act at *at* and carry its instant in the tree run.

    Yields the act's instant.  Inside a run that already carries one, yields
    that instant and opens nothing; passing *at* there is a test bug.

    Raises:
        ValueError: *at* given inside a run that already carries an instant.
    """
    inherited = inherited_act_instant()
    if inherited is not None:
        if at is not None and at != inherited:
            raise ValueError(
                f"an act at {inherited.isoformat()} is already open; a nested"
                f" run cannot take its own instant {at.isoformat()}"
            )
        yield inherited
        return
    with open_act(FixedClock(at)) as instant, act_instant_in_tree_run(instant):
        yield instant


def _opens_own_act(use_case: object) -> bool:
    """Whether *use_case* holds an act clock, and so opens its own act."""
    return hasattr(use_case, "_clock")


def run_in_act(
    use_case: _Executes[R_co], *, at: datetime | None = None
) -> R_co:
    """Run ``use_case.execute()`` as one act and return its result.

    A use case that opens its own act (a trigger) runs as it is, and *at*
    must be omitted: pin its instant with a :class:`FixedClock` instead.

    Raises:
        ValueError: *at* given for a use case that opens its own act.
    """
    if _opens_own_act(use_case):
        if at is not None:
            raise ValueError(
                f"{type(use_case).__name__} opens its own act from its clock;"
                " give it FixedClock(at) instead of passing at="
            )
        return use_case.execute()
    with in_act(at):
        return use_case.execute()


def run_tree(
    bridge: BTBridge,
    tree: py_trees.behaviour.Behaviour,
    *args: Any,
    at: datetime | None = None,
    **kwargs: Any,
) -> BTExecutionResult:
    """Run *tree* through *bridge* as the outermost run of an act at *at*.

    Inside a run that already carries an instant, runs nested and inherits
    it.  Other arguments go to ``BTBridge.execute_with_setup`` unchanged.
    """
    if inherited_act_instant() is not None and at is None:
        return bridge.execute_with_setup(tree, *args, **kwargs)
    with open_act(FixedClock(at)) as instant:
        return bridge.execute_with_setup(tree, *args, at=instant, **kwargs)


__all__ = ["FixedClock", "in_act", "run_in_act", "run_tree"]
