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

"""The two clocks the application reads, as driven ports (ADR-0176).

- :class:`ClockPort` is the **act clock**.  Only an act's entry point holds
  it, and the act reads it once: a trigger or sweep after it takes the tree
  lock (:func:`vultron.core.behaviors.bridge.act_instant.open_act`), and a
  received message on arrival, before it queues for the lock
  (:func:`~vultron.core.behaviors.bridge.act_instant.stamp_arrival`; its
  processing opens with ``open_received_act``).  Everything below that
  point takes the act's instant instead of reading a clock.
- :class:`BookkeepingClockPort` is the **bookkeeping clock**: adapter times
  such as when a delivery was dead-lettered.  Such a time is not an act's
  instant and never enters the case ledger, so it has its own port and its
  own operation name: a bookkeeping clock cannot be passed where an act clock
  is wanted, and a bookkeeping read never moves the act clock.

The composition root supplies both: the system clocks in
``vultron/adapters/driven/clock.py`` in production.

A stopwatch that measures elapsed time against a limit is neither of these,
and arrives with the first limit that needs it (#3423).
"""

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class ClockPort(Protocol):
    """The act clock: one operation, the current time (ADR-0176)."""

    def now(self) -> datetime:
        """Return the current instant, timezone-aware and in UTC (CS-13-001)."""
        ...


@runtime_checkable
class BookkeepingClockPort(Protocol):
    """The bookkeeping clock: the time an adapter records a fact of its own.

    Never an act's instant, and never read by core (ADR-0176).
    """

    def bookkeeping_now(self) -> datetime:
        """Return the current instant, timezone-aware and in UTC (CS-13-001)."""
        ...


__all__ = ["BookkeepingClockPort", "ClockPort"]
