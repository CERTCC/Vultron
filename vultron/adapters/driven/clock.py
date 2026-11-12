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

"""The system clocks behind the two clock ports, and the installed act clock.

:class:`SystemClock` is the act clock in production.  It reads through
:func:`~vultron.core.models._helpers.clock.now_utc`, so each instant keeps the
CS-13-001 form.

:func:`act_clock` is the one place a composition root gets the act clock
from: the system clock, except inside :func:`install_act_clock`, which a
recorded run uses to supply its recording clock through the port
(``vultron.demo.determinism``, ADR-0176).  A recorded run replaces no clock
by patching ``now_utc``'s module; only tests and the docs-example generator,
which runs no act, still do.

:class:`SystemBookkeepingClock` reads the wall clock directly, never through
``now_utc``, so no recording clock ever sees a bookkeeping read and a
bookkeeping read never moves a recording (ADR-0176).
"""

from contextlib import AbstractContextManager
from datetime import UTC, datetime

from vultron.core.models._helpers.clock import now_utc
from vultron.core.models._helpers.scoped_install import ScopedInstall
from vultron.core.ports.clock import ClockPort
from vultron.errors import VultronActClockInstalledError


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


def _refuse_nested_act_clock() -> VultronActClockInstalledError:
    return VultronActClockInstalledError(
        "an act clock is already installed; a recorded run's install does"
        " not nest inside another"
    )


#: The act clock every composition root hands its entry points:
#: :class:`SystemClock` except inside :func:`install_act_clock`.
_ACT_CLOCK: ScopedInstall[ClockPort] = ScopedInstall(
    SystemClock(), _refuse_nested_act_clock
)


def act_clock() -> ClockPort:
    """Return the act clock a composition root hands an act's entry point.

    The system clock, or the clock :func:`install_act_clock` installed.
    Read it when the entry point is wired, never below an act's edge
    (ADR-0176).
    """
    return _ACT_CLOCK.value


def install_act_clock(clock: ClockPort) -> AbstractContextManager[ClockPort]:
    """Make *clock* the act clock for the block, then restore the system one.

    For a recorded run, which supplies its recording clock through the port
    (ADR-0176); production installs nothing.  The install is process-wide:
    every act that opens while the block runs reads *clock*.

    Raises:
        VultronActClockInstalledError: another install is active.
    """
    return _ACT_CLOCK.install(clock)


__all__ = [
    "SystemBookkeepingClock",
    "SystemClock",
    "act_clock",
    "install_act_clock",
]
