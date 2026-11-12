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


"""A demo client's one clock read per act, and dates measured from it.

The core deadline helpers take an act's instant and read no clock (ADR-0176,
CS-13-004).  A demo client is an actor outside the application: a step it
takes (authoring an activity, or stating a deadline before it calls a
trigger) is the client's own act, and :func:`now` is that act's one read, at
its edge.  It reads the act clock the composition root installed
(:func:`~vultron.adapters.driven.clock.act_clock`), so in a recorded run the
client's times come from the recording clock, in step with the acts they
cause, and the recording repeats byte for byte; elsewhere it is the system
clock.  ``test/support/future_dates.py`` re-exports the two deadline helpers,
so demos and tests share the one composition (CS-22-001).
"""

from datetime import datetime, timedelta

from vultron.adapters.driven.clock import act_clock
from vultron.core.models._helpers.clock import deadline_from


def now() -> datetime:
    """One read of the act clock: the instant of a demo client's act.

    A demo client that builds an activity outside any act of the application
    (an exchange demo posting to an inbox) states its ``published`` with this
    (ADR-0176).
    """
    return act_clock().now()


def from_now(delta: timedelta) -> datetime:
    """Return the UTC instant *delta* after one read of the act clock."""
    return deadline_from(now(), delta)


def days_from_now(days: int) -> datetime:
    """Return the UTC instant *days* days after one read of the act clock."""
    return from_now(timedelta(days=days))
