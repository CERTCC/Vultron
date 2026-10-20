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

"""One DataLayer transaction for an act and every consequence its tree commits.

An act's consequences commit all at once or not at all (CLP-07-015,
ADR-0146).  Some of them are committed by later nodes in the act's tree, such
as the stub re-issue (CM-11-016) and the relay of a proposal (EP-09-002).
:class:`ActTransaction` runs the act's commit node and those later nodes as
one ``Sequence`` inside one ``CasePersistence.transaction()``: when any child
raises or fails, nothing any of them wrote is kept.

A received act's own entry is one of them: the received-tree factory runs
the guarded commit of that entry inside the same ``ActTransaction`` as the
effects that commit its consequences (``as_one_act=True``, ADR-0151), so a
received act succeeds or fails as a whole, as a trigger act does.
"""

import logging
from collections.abc import Iterator
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.node_logger import node_logger
from vultron.core.ports.case_persistence import CasePersistence


class ActTransactionError(RuntimeError):
    """A child of an :class:`ActTransaction` did not finish in one tick.

    A plain ``RuntimeError``, not a ``VultronError``: ``BTBridge`` reports it
    as an internal error.  A transaction cannot stay open between ticks, so a
    ``RUNNING`` child is a wiring fault, never a protocol outcome.
    """


class _RolledBack(Exception):
    """Raised inside the block to roll it back when the children fail."""


class ActTransaction(py_trees.composites.Sequence):
    """Run *children* as a ``Sequence`` inside one DataLayer transaction.

    Place the act's commit node and every later node that commits a
    consequence of it among *children* (CLP-07-015, ADR-0146).  Returns the
    ``Sequence``'s status: ``SUCCESS`` commits every write the children made,
    and ``FAILURE`` rolls all of them back.  A child that raises rolls them
    back and the exception propagates to ``BTBridge``, as without the
    wrapper.  The decision is made before the parent sees this node's status.

    Every child must finish in one tick: a ``RUNNING`` result stops the
    children, rolls the block back and raises :class:`ActTransactionError`.

    Composable: an ``ActTransaction`` inside another is part of the outer
    one, so a subtree that wraps its own act (``terminate_embargo_bt``) may
    run inside a larger one (a rejection that ends the embargo).
    """

    # py_trees types ``Behaviour.logger`` as its own logger class; nodes
    # rebind it to a stdlib logger (``node_logger``).
    logger: logging.Logger  # type: ignore[assignment]

    def __init__(
        self, name: str, children: list[py_trees.behaviour.Behaviour]
    ) -> None:
        super().__init__(name=name, memory=False, children=children)
        self.logger = node_logger(self)  # type: ignore[assignment]

    def setup(self, **kwargs: Any) -> None:
        """Register read access to the BTBridge ``datalayer`` key."""
        super().setup(**kwargs)
        self._blackboard = self.attach_blackboard_client(name=self.name)
        self._blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.READ
        )

    def _datalayer(self) -> CasePersistence | None:
        blackboard = getattr(self, "_blackboard", None)
        if blackboard is None:
            return None
        try:
            return cast(CasePersistence | None, blackboard.datalayer)
        except KeyError:
            return None

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        datalayer = self._datalayer()
        if datalayer is None:
            self.feedback_message = "DataLayer not found in blackboard"
            self.logger.error("%s: %s", self.name, self.feedback_message)
            self.stop(Status.FAILURE)
            yield self
            return
        try:
            with datalayer.transaction():
                yield from self._tick_children()
        except _RolledBack:
            self.logger.info(
                "%s: a step failed, so nothing the act wrote is kept"
                " (CLP-07-015)",
                self.name,
            )
        yield self

    def _tick_children(self) -> Iterator[py_trees.behaviour.Behaviour]:
        """Tick the ``Sequence``; raise to roll back unless it succeeded.

        Stops before the ``Sequence`` yields itself, so the transaction ends
        before the parent reads this node's status.
        """
        for node in super().tick():
            if node is self:
                break
            yield node
        if self.status == Status.RUNNING:
            running = getattr(self.current_child, "name", None)
            # INVALID stops every running child; the act itself failed.
            self.stop(Status.INVALID)
            self.status = Status.FAILURE
            raise ActTransactionError(
                f"{self.name}: child {running!r} returned"
                " RUNNING; an act's transaction cannot stay open between"
                " ticks (CLP-07-015)"
            )
        if self.status != Status.SUCCESS:
            raise _RolledBack


__all__ = [
    "ActTransaction",
    "ActTransactionError",
]
