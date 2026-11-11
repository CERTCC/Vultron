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

"""An act's one clock read, and the tree-run key that carries it (ADR-0176).

An **act** is one trigger invocation, the processing of one inbound delivery,
or one sweep.  Each act has one instant, read once from the act clock, and
everything below its entry point takes the instant instead of reading a
clock:

- :func:`open_act` is the entry point's half for a trigger or a sweep.  It
  takes the tree lock, then reads the act clock once, and the caller holds
  the lock until the act commits.  Queueing for the lock is therefore not
  decision time.
- :func:`stamp_arrival` and :func:`open_received_act` are the two halves for
  a received message: the inbox reads the act clock once when the message
  arrives, before it queues for the tree lock, and the processing takes the
  lock and runs at that arrival stamp.  Every judgment about the message
  uses the stamp, even when it is held and replayed later, so a backlog
  never makes an on-time message late.
- :func:`act_instant_in_tree_run` places the instant in the tree run's shared
  state as ``/at`` and puts back what was there on exit; the inbox pipeline
  uses it for the delivery it processes.  ``BTBridge.execute_with_setup(...,
  at=...)`` does the same for an act's outermost run, through
  :func:`place_act_instant` and its own key restore.  A nested run inherits
  ``/at``.
- :func:`read_act_instant` is the node's half.  A node that needs the time
  calls it when it ticks; it raises when the run carries no instant, and it
  never reads the clock.

A held activity replayed later is an act of its own, and its instant is the
arrival stamp its held record carries, never the instant of the act that
released it.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

import py_trees

from vultron.core.behaviors.blackboard_scope import (
    key_aliases,
    restore_keys,
    snapshot_keys,
)
from vultron.core.behaviors.bridge.lock import _BT_GLOBAL_LOCK
from vultron.core.models._helpers import is_aware
from vultron.core.ports.clock import ClockPort
from vultron.errors import VultronMissingActInstantError, VultronWiringError

#: The blackboard key a tree run carries its act's instant under, read as
#: ``/at``.
ACT_INSTANT_KEY = "at"


def _require_aware(at: object, source: str) -> datetime:
    """Return *at* when it is a timezone-aware ``datetime``; else raise."""
    if not isinstance(at, datetime):
        raise VultronWiringError(
            f"{source} gave {type(at).__name__}, not a datetime, as an act's"
            " instant (ADR-0176)"
        )
    if not is_aware(at):
        raise VultronWiringError(
            f"{source} gave a naive datetime as an act's instant (CS-13-001)"
        )
    return at


@contextmanager
def open_act(clock: ClockPort) -> Iterator[datetime]:
    """Open one act: take the tree lock, then read *clock* once.

    Yields the act's instant with the lock held; the lock is released when
    the block exits, so the act holds it until it commits.  The lock is
    re-entrant, so the bridge taking it again inside the act is safe, and a
    replay processed inside another act opens an act of its own.

    Raises:
        VultronWiringError: *clock* returned something other than a
            timezone-aware ``datetime``.
    """
    with _BT_GLOBAL_LOCK:
        yield _require_aware(clock.now(), type(clock).__name__)


def stamp_arrival(clock: ClockPort) -> datetime:
    """Read *clock* once for a message arriving now; return its arrival stamp.

    The inbox calls this when a message arrives, before the message queues
    for the tree lock, so the time spent waiting for the lock is not charged
    to the sender (ADR-0176).  The stamp is the instant of every act that
    processes the message, its replays included (:func:`open_received_act`).

    Raises:
        VultronWiringError: *clock* returned something other than a
            timezone-aware ``datetime``.
    """
    return _require_aware(clock.now(), type(clock).__name__)


@contextmanager
def open_received_act(arrived_at: datetime) -> Iterator[datetime]:
    """Open the act that processes a received message stamped *arrived_at*.

    Takes the tree lock and yields *arrived_at* as the act's instant, with
    the lock held until the block exits.  No clock is read: the message's
    arrival stamp (:func:`stamp_arrival`) is its instant, at its first
    processing and at every replay of it.

    Raises:
        VultronWiringError: *arrived_at* is not a timezone-aware
            ``datetime``.
    """
    at = _require_aware(arrived_at, "open_received_act")
    with _BT_GLOBAL_LOCK:
        yield at


@contextmanager
def act_instant_in_tree_run(at: datetime) -> Iterator[None]:
    """Place *at* in the tree run's shared state as ``/at`` for the block.

    Both spellings of the key are set, and the state they had before is put
    back on exit, absent kept distinct from ``None`` (``blackboard_scope``),
    so the instant of one act never outlives it.  Call it with the tree lock
    held: the blackboard is process-global.

    Raises:
        VultronWiringError: *at* is not a timezone-aware ``datetime``.
    """
    _require_aware(at, "act_instant_in_tree_run")
    storage = py_trees.blackboard.Blackboard.storage
    saved = snapshot_keys(storage, [ACT_INSTANT_KEY])
    try:
        place_act_instant(at)
        yield
    finally:
        restore_keys(storage, saved)


def place_act_instant(at: datetime) -> None:
    """Set both spellings of ``/at`` to *at*, with no restore.

    For a caller that already snapshots and restores the key with its other
    run-scoped keys, as ``BTBridge.execute_with_setup`` does; anything else
    uses :func:`act_instant_in_tree_run`.

    Raises:
        VultronWiringError: *at* is not a timezone-aware ``datetime``.
    """
    _require_aware(at, "place_act_instant")
    storage = py_trees.blackboard.Blackboard.storage
    for alias in key_aliases(ACT_INSTANT_KEY):
        storage[alias] = at


def inherited_act_instant() -> datetime | None:
    """The instant of the tree run in progress, or ``None`` outside one.

    For the bridge, which inherits an enclosing run's instant the way it
    inherits ``/is_leader``.  A node calls :func:`read_act_instant` instead.
    """
    value = py_trees.blackboard.Blackboard.storage.get(f"/{ACT_INSTANT_KEY}")
    return value if isinstance(value, datetime) else None


def read_act_instant() -> datetime:
    """Return the instant of the act this tree run belongs to.

    A node calls this when it ticks, never at build time: a time read at
    build would be read before the act took the lock (ADR-0176).

    Raises:
        VultronMissingActInstantError: The run carries no ``/at``.  Never
            answered by reading the clock (ARCH-10-001); ``BTBridge``
            classifies it as an internal error.
    """
    at = inherited_act_instant()
    if at is None:
        raise VultronMissingActInstantError(
            "this tree run carries no act instant (/at): start it inside an"
            " act (open_act) or pass the act's instant to the outermost"
            " BTBridge run (ADR-0176)"
        )
    return at


__all__ = [
    "ACT_INSTANT_KEY",
    "act_instant_in_tree_run",
    "inherited_act_instant",
    "open_act",
    "open_received_act",
    "place_act_instant",
    "read_act_instant",
    "stamp_arrival",
]
