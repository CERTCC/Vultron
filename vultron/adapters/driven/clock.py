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

"""The system clocks behind the two clock ports (ADR-0176).

:class:`SystemClock` is the act clock in production.  It reads through
:func:`~vultron.core.models._helpers.clock.now_utc`, so a recorded run that
replaces that module's clock (``vultron.demo.determinism``) still controls
every act's instant until the recording clock arrives through the port
itself (#5760).

:class:`SystemBookkeepingClock` reads the wall clock directly, never through
``now_utc``, so no recording clock ever sees a bookkeeping read and a
bookkeeping read never moves a recording (ADR-0176).
"""

from datetime import UTC, datetime

from vultron.core.models._helpers.clock import now_utc


class SystemClock:
    """The production act clock (``ClockPort``)."""

    def now(self) -> datetime:
        """Return the current UTC instant."""
        return now_utc()


class SystemBookkeepingClock:
    """The production bookkeeping clock (``BookkeepingClockPort``)."""

    def bookkeeping_now(self) -> datetime:
        """Return the current UTC instant, read from the wall clock."""
        return datetime.now(UTC)


__all__ = ["SystemBookkeepingClock", "SystemClock"]
