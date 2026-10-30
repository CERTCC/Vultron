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

"""Seeded ids and a stepping clock, so a scenario run repeats byte for byte.

A scenario recording (#3901) is checked for staleness by comparing a fresh run
with the committed file, so every id, timestamp and hash in it must come out the
same on every run.  Two sources vary between runs, and :func:`deterministic_run`
replaces both:

- **Ids.**  Every generated id is a ``uuid4``.  The run replaces
  ``uuid.uuid4`` with a seeded generator, and also every module attribute bound
  to it by ``from uuid import uuid4``, which a patch of the ``uuid`` module
  alone does not reach.
- **The clock.**  Every timestamp comes from
  :func:`vultron.core.models._helpers.now_utc`, which reads the ``datetime``
  name on its module at call time so that it can be replaced.  Replacing that
  name, not ``now_utc`` itself, also reaches the ``default_factory=now_utc``
  references that model fields captured at class creation.

The patched ids are still version-4 UUIDs, and the clock still moves forward
on every read, so nothing that checks their shape or order sees a difference.
"""

import random
import sys
import threading
import uuid
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import py_trees

from vultron.core.models import _helpers

#: The instant a recording's clock starts from.  Fixed so that a recording does
#: not change when it is regenerated on a later day.
RECORDING_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)

#: The seed every recording of the scenario tree is made with (DEMOCI-11-025).
#: One seed for the whole tree, not one per scenario: two scenarios that tell
#: the same opening draw the same ids for it, so their recordings can be
#: byte-identical up to the branch point where they part (DEMOCI-11-018).
TREE_RECORDING_SEED = "vultron-scenario-tree"

#: How far the recording clock moves on each read.  ``now_utc()`` keeps whole
#: seconds, so about one hundred reads share a second.  A step of one second
#: would age a held record past a timeout such as the 300-second
#: pre-bootstrap queue window after only 300 unrelated reads, which a real run
#: of the same length never does.
RECORDING_CLOCK_STEP = timedelta(milliseconds=10)


def reset_blackboard() -> None:
    """Drop everything the process-global py_trees blackboard holds.

    Two kinds of leak outlive one tree, and a demo that runs several trees in
    one process has to clear both:

    * **keys.** ``BTBridge.execute_with_setup`` restores only the keys on its
      ``managed_keys`` list, so any other key a node wrote outlives the run.
    * **clients.** ``py_trees.blackboard.Client`` registers itself under a
      ``uuid4`` that nothing unregisters, so a seeded id source (:func:
      `deterministic_run`) redraws an id the registry already holds and
      py_trees refuses the registration.

    ``Blackboard.clear()`` drops both, and with them the metadata and the
    activity stream, which is what a run that starts from nothing wants.
    """
    py_trees.blackboard.Blackboard.clear()


class SteppingClock:
    """A ``datetime`` stand-in whose ``now()`` advances *step* on every call.

    The first call returns ``start + step``; ``step=timedelta(0)`` freezes the
    clock at *start*.  *start* must be timezone-aware, as ``now_utc()`` promises
    its callers (CS-13-001).

    Only ``now()`` is provided.  ``_helpers`` keeps a private reference to the
    real class for its ``isinstance`` guards, so any other attribute a patched
    path reaches for raises ``AttributeError`` instead of returning a wrong
    time.  Reads are serialized, because in-process deliveries run on worker
    threads.
    """

    def __init__(
        self, start: datetime, step: timedelta = timedelta(seconds=1)
    ) -> None:
        if start.tzinfo is None:
            raise ValueError("SteppingClock start must be timezone-aware")
        self._t = start
        self._step = step
        self._lock = threading.Lock()

    def now(self, tz: timezone | None = None) -> datetime:
        with self._lock:
            self._t += self._step
            current = self._t
        return current.astimezone(tz) if tz is not None else current


class SeededUuid4:
    """A ``uuid.uuid4`` stand-in that draws its bits from a seeded generator.

    A ``str`` seed is hashed by :class:`random.Random` itself, not by
    ``hash()``, so the sequence does not depend on ``PYTHONHASHSEED``.
    """

    def __init__(self, seed: str) -> None:
        self._rng = random.Random(seed)  # noqa: S311  # ids, not secrets
        self._lock = threading.Lock()

    def __call__(self) -> uuid.UUID:
        with self._lock:
            bits = self._rng.getrandbits(128)
        return uuid.UUID(int=bits, version=4)


def _modules_binding(value: object, name: str) -> list[str]:
    """Return the loaded modules whose attribute *name* is *value*."""
    return sorted(
        module_name
        for module_name, module in list(sys.modules.items())
        if module is not None and getattr(module, name, None) is value
    )


@contextmanager
def deterministic_run(
    seed: str,
    start: datetime = RECORDING_EPOCH,
    step: timedelta = RECORDING_CLOCK_STEP,
) -> Generator[None]:
    """Replace the id source and the clock for the duration of the block.

    A module imported inside the block that runs ``from uuid import uuid4``
    binds the seeded generator, which is correct while the block runs.  On
    exit those bindings are put back to the real ``uuid4`` too, so a later run
    in the same process does not depend on what this one imported.

    Args:
        seed: Seeds the id generator.  The same seed gives the same ids.
        start: The instant the clock starts from.
        step: How far the clock moves on each read.
    """
    ids = SeededUuid4(seed)
    clock = SteppingClock(start, step=step)
    real_uuid4 = uuid.uuid4
    try:
        with ExitStack() as stack:
            for module_name in _modules_binding(real_uuid4, "uuid4"):
                stack.enter_context(
                    patch.object(sys.modules[module_name], "uuid4", ids)
                )
            stack.enter_context(patch.object(_helpers, "datetime", clock))
            yield
    finally:
        for module_name in _modules_binding(ids, "uuid4"):
            vars(sys.modules[module_name])["uuid4"] = real_uuid4


__all__ = [
    "RECORDING_CLOCK_STEP",
    "RECORDING_EPOCH",
    "SeededUuid4",
    "SteppingClock",
    "deterministic_run",
]
