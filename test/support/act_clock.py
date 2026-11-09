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

from datetime import UTC, datetime

from vultron.core.behaviors.bridge.lock import _BT_GLOBAL_LOCK

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
