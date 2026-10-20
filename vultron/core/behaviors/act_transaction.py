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

:func:`act_transaction` is the block itself.  It also carries the one
exception to "nothing is kept": an entry committed *before* the block opened.
A received act's own entry is committed by intake in its own transaction
(ADR-0111, the gap #4933 closes), so it stands when its consequences roll
back.  The change that entry carries must stand with it, or the CASE_MANAGER
holds a committed entry its own case file does not show, while every replica
copies it.  :func:`commit_and_apply_embargo_entries` names that change with
:func:`apply_after_rollback`, and the block applies it again after the
rollback.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.node_logger import node_logger
from vultron.core.ports.case_persistence import CasePersistence

#: The changes of already-committed entries to apply again when the open
#: block rolls back; ``None`` with no block open.  Scoped to the running
#: context (one tree tick on one thread), never shared between acts.
_AFTER_ROLLBACK: ContextVar[list[Callable[[], None]] | None] = ContextVar(
    "act_transaction_after_rollback", default=None
)


@contextmanager
def act_transaction(datalayer: CasePersistence) -> Iterator[None]:
    """Commit every write in the block as one act, or none of them.

    A ``datalayer.transaction()``, plus the changes named with
    :func:`apply_after_rollback`: when the block raises, they are applied
    after its rollback, then the exception propagates (or, when one of them
    raises, that exception, chained to the first).  A block opened
    inside another is part of it: the outer block also applies them if it
    rolls back in turn, because the outer rollback undoes what the inner
    one applied.

    Raises:
        Exception: whatever the block raised, after every write in it was
            rolled back.
    """
    outer = _AFTER_ROLLBACK.get()
    owed: list[Callable[[], None]] = []
    token = _AFTER_ROLLBACK.set(owed)
    committed = False
    try:
        with datalayer.transaction():
            yield
        committed = True
    finally:
        _AFTER_ROLLBACK.reset(token)
        # The outer block owes them too, whatever happens below: its own
        # rollback would undo what this block applies.
        if outer is not None:
            outer.extend(owed)
        if not committed:
            _apply_each(owed)


def _apply_each(owed: list[Callable[[], None]]) -> None:
    """Run every one of *owed*, in order, even when one of them raises.

    A change that cannot be applied again raises after the rest have run,
    with the block's own failure (and any earlier such failure) as its
    context.
    """
    if not owed:
        return
    first, *rest = owed
    try:
        first()
    finally:
        _apply_each(rest)


def apply_after_rollback(apply: Callable[[], None]) -> None:
    """Have the open :func:`act_transaction` run *apply* if it rolls back.

    *apply* re-applies the change of an entry committed before the block
    opened (a received act's own entry, ADR-0111), so that change stands with
    its entry.  With no block open there is nothing to roll back, so
    *apply* is not kept.
    """
    owed = _AFTER_ROLLBACK.get()
    if owed is not None:
        owed.append(apply)


class ActTransactionError(RuntimeError):
    """A child of an :class:`ActTransaction` did not finish in one tick.

    A plain ``RuntimeError``, not a ``VultronError``: ``BTBridge`` reports it
    as an internal error.  A transaction cannot stay open between ticks, so a
    ``RUNNING`` child is a wiring fault, never a protocol outcome.
    """


class _RolledBack(Exception):
    """Raised inside the block to roll it back when the children fail."""


class ActTransaction(py_trees.composites.Sequence):
    """Run *children* as a ``Sequence`` inside one :func:`act_transaction`.

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
            with act_transaction(datalayer):
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
    "act_transaction",
    "apply_after_rollback",
]
