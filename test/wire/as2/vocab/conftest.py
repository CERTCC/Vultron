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

"""Fixtures for the vocabulary example tests.

The ``py_trees`` blackboard is cleared for every test by the root
``test/conftest.py`` (TB-06-005), so this directory no longer carries its own
copy of that fixture.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

import vultron.core.models._helpers as _clock_module
import vultron.wire.as2.vocab.examples.embargo as _embargo_examples

#: One millisecond before a minute (and therefore a second) tick.
STRADDLE_START = datetime(2026, 10, 1, 16, 37, 59, 999_000, tzinfo=UTC)


class _StraddlingClock(datetime):
    """A ``datetime`` whose ``now()`` advances 1 ms on every read.

    Starting at :data:`STRADDLE_START`, the second read already falls in the
    next second *and* the next minute, so any value derived from two separate
    clock reads differs at second and at minute resolution.
    """

    reads = 0

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        moment = STRADDLE_START + timedelta(milliseconds=cls.reads)
        cls.reads += 1
        return moment if tz is None else moment.astimezone(tz)


@pytest.fixture
def straddling_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[type]:
    """Make every clock read an example can reach straddle a minute boundary.

    Patches ``now_utc()``'s module (the ``published``/``updated`` and
    ``start_time`` default factories of every wire and core object) and the
    embargo example module's own ``datetime`` name, if it still has one.
    """
    _StraddlingClock.reads = 0
    monkeypatch.setattr(_clock_module, "datetime", _StraddlingClock)
    monkeypatch.setattr(
        _embargo_examples, "datetime", _StraddlingClock, raising=False
    )
    yield _StraddlingClock
