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

"""Deterministic stand-ins for the ``datetime`` name that ``now_utc()`` reads.

``vultron.core.models._helpers.now_utc`` looks ``datetime`` up on its module at
call time precisely so a test can replace it::

    monkeypatch.setattr(_helpers, "datetime", SteppingClock(start))

Only ``now()`` is provided.  The helper module keeps a private reference to the
real class for its ``isinstance`` guards, so any other attribute a patched path
reaches for raises ``AttributeError`` loudly instead of returning a wrong time.
Never ``time.sleep()`` to cross a second boundary in a test: pin the clock.
"""

from datetime import datetime, timedelta, timezone


class SteppingClock:
    """A ``datetime`` stand-in whose ``now()`` advances *step* on every call.

    The first call returns ``start + step``; ``step=timedelta(0)`` freezes the
    clock at *start*.  *start* must be timezone-aware, as ``now_utc()`` promises
    its callers (CS-13-001).
    """

    def __init__(
        self, start: datetime, step: timedelta = timedelta(seconds=1)
    ) -> None:
        if start.tzinfo is None:
            raise ValueError("SteppingClock start must be timezone-aware")
        self._t = start
        self._step = step

    def now(self, tz: timezone | None = None) -> datetime:
        self._t += self._step
        return self._t
