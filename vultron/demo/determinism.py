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

- **Ids.**  Every object id comes from the one minter,
  :func:`vultron.core.models._helpers.new_object_id`, which draws from the
  installed id source (OID-01-011).  The run installs a :class:`SeededUuid4`
  for the block through
  :func:`~vultron.core.models._helpers.install_id_source` and patches nothing
  in the ``uuid`` module (OID-01-012, ADR-0185).  So py_trees, which draws
  ``uuid.uuid4()`` for every behaviour and blackboard client it builds, keeps
  its random ids, and adding a tree node moves no object id in a recording.
- **The clock.**  Every timestamp comes from
  :func:`vultron.core.models._helpers.clock.now_utc`, which reads the ``datetime``
  name on its module at call time so that it can be replaced.  Replacing that
  name, not ``now_utc`` itself, also reaches the ``default_factory=now_utc``
  references that model fields captured at class creation.

The seeded ids are still version-4 UUIDs, and the clock still moves forward
on every read, so nothing that checks their shape or order sees a difference.
"""

import random
import threading
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import py_trees

from vultron.core.models._helpers import (
    SteppingClock,
    clock as helpers_clock,
    install_id_source,
)

# Imported for its import-time work, before any run installs an id source.
# The docs examples build their shared objects at first import inside their
# own id-source scope (#6117), which may not nest inside a recording's
# install, and an example module first imported inside the install would
# draw its objects' ids from the recording's seeded stream.  Loading them
# here, with this module, keeps every first import outside the block.
from vultron.wire.as2.vocab.examples import (  # noqa: F401
    vocab_examples as _vocab_examples,
)

#: The instant a recording's clock starts from.  Fixed so that a recording does
#: not change when it is regenerated on a later day.
RECORDING_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)

#: The seed every recording of the scenario tree is made with (DEMOCI-11-025).
#: One seed for the whole tree, not one per scenario: two scenarios that tell
#: the same opening draw the same ids for it, so their recordings can be
#: byte-identical up to the branch point where they part (DEMOCI-11-018).
TREE_RECORDING_SEED = "vultron-scenario-tree"

#: How far the recording clock moves on each read.  Small enough that about
#: one hundred reads fit in a second of recorded time.  A step of one second
#: would age a held record past a timeout such as the 300-second
#: pre-bootstrap queue window after only 300 unrelated reads, which a real run
#: of the same length never does.
RECORDING_CLOCK_STEP = timedelta(milliseconds=10)


def reset_blackboard() -> None:
    """Drop everything the process-global py_trees blackboard holds.

    ``BTBridge.execute_with_setup`` restores only the keys on its
    ``managed_keys`` list, so any other key a node wrote outlives the run, and
    a demo that runs several trees in one process starts each from whatever
    the last one left.  ``Blackboard.clear()`` drops those keys, and with them
    the client registry, the metadata and the activity stream, which is what
    a run that starts from nothing wants.

    The registered clients do no harm across runs: py_trees names each one
    by a ``uuid.uuid4()`` draw, which :func:`deterministic_run` leaves random,
    so a second recording in one process draws no id the registry holds.
    """
    py_trees.blackboard.Blackboard.clear()


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


@contextmanager
def deterministic_run(
    seed: str,
    start: datetime = RECORDING_EPOCH,
    step: timedelta = RECORDING_CLOCK_STEP,
) -> Generator[None]:
    """Install a seeded id source and a stepping clock for the block.

    The docs examples are already imported when the block starts (see the
    import at the top of this module), so no first import of them runs
    inside it.

    The id source is installed through
    :func:`~vultron.core.models._helpers.install_id_source`, so it restores
    the previous source on exit, also when the block raises, and a
    ``deterministic_run`` nested in another one (or in any other install)
    raises :class:`~vultron.errors.VultronIdSourceInstalledError` rather than
    sharing one stream of ids between two runs.

    Args:
        seed: Seeds the id source.  The same seed gives the same ids.
        start: The instant the clock starts from.
        step: How far the clock moves on each read.
    """
    clock = SteppingClock(start, step=step)
    with (
        install_id_source(SeededUuid4(seed)),
        patch.object(helpers_clock, "datetime", clock),
    ):
        yield


__all__ = [
    "RECORDING_CLOCK_STEP",
    "RECORDING_EPOCH",
    "SeededUuid4",
    "SteppingClock",
    "TREE_RECORDING_SEED",
    "deterministic_run",
    "reset_blackboard",
]
