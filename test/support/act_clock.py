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
"""An act clock for tests that checks how an act reads it (ADR-0176)."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, tzinfo
from unittest.mock import patch

from vultron.core.behaviors.bridge.lock import _BT_GLOBAL_LOCK
from vultron.core.models._helpers import clock as helpers_clock

#: The instant a :class:`CountingClock` returns when given none.
ACT_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def tree_lock_held() -> bool:
    """Whether the calling thread holds the tree lock."""
    return bool(_BT_GLOBAL_LOCK._is_owned())  # type: ignore[attr-defined]


class CountingClock:
    """A ``ClockPort`` that counts its reads and notes whether the lock was held.

    Returns *instants* in turn, then repeats the last one; :data:`ACT_AT`
    when none are given.
    """

    def __init__(self, *instants: datetime) -> None:
        self._instants = list(instants) or [ACT_AT]
        self.reads = 0
        self.locked_at_read: list[bool] = []

    def now(self) -> datetime:
        self.locked_at_read.append(tree_lock_held())
        value = self._instants[min(self.reads, len(self._instants) - 1)]
        self.reads += 1
        return value


class NoClock(datetime):
    """A ``datetime`` whose ``now()`` fails, so any clock read is caught.

    A subclass, so an ``isinstance`` check against ``datetime`` still holds
    in a module whose ``datetime`` it replaces.
    """

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:  # type: ignore[override]
        raise AssertionError(
            "read the clock below an act's edge; take the act's instant"
            " instead (ADR-0176)"
        )


@contextmanager
def no_clock() -> Iterator[None]:
    """Fail any read of the wall clock behind ``now_utc`` while it is held.

    For a test that a helper is a pure function of the instant it is given
    (ADR-0176): the read raises, so the helper cannot pass by reading a clock
    that happens to agree with the instant.
    """
    with patch.object(helpers_clock, "datetime", NoClock):
        yield


@contextmanager
def clock_at(at: datetime) -> Iterator[None]:
    """Hold the clock at *at*, a microsecond per read, while an act at *at*
    runs.

    The act's instant judges each claimed timestamp (CLP-14-007, CLP-14-008),
    while what the act stamps still reads the clock until #5758, so a test
    that pins an act away from the wall clock pins the clock with it: one
    act's instant and its stamps agree, as in production (ADR-0176).
    """
    with patch.object(
        helpers_clock,
        "datetime",
        helpers_clock.SteppingClock(at, step=timedelta(microseconds=1)),
    ):
        yield
