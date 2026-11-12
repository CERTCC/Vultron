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


"""Dates measured from one wall-clock read, for callers outside an act.

The core deadline helpers take an act's instant and read no clock (ADR-0176,
CS-13-004).  A demo client stating a deadline before it calls a trigger, or a
test building data outside an act, has no act's instant to pass: it reads the
clock here, once, and measures from it.  A demo client authoring an activity
takes :func:`now` as the activity's instant.  ``test/support/future_dates.py``
re-exports the two deadline helpers, so demos and tests share the one composition
(CS-22-001).
"""

from datetime import datetime, timedelta

from vultron.core.models._helpers.clock import deadline_from, now_utc


def now() -> datetime:
    """One wall-clock read: the instant a demo client authors an activity at.

    A demo client that builds an activity outside any act (an exchange demo
    posting to an inbox) states its ``published`` with this (ADR-0176).
    """
    return now_utc()


def from_now(delta: timedelta) -> datetime:
    """Return the UTC instant *delta* after one wall-clock read."""
    return deadline_from(now(), delta)


def days_from_now(days: int) -> datetime:
    """Return the UTC instant *days* days after one wall-clock read."""
    return from_now(timedelta(days=days))
