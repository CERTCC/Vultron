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

"""The one wall-clock read of the core model, and deadlines measured from it.

:func:`now_utc` looks up ``datetime`` on this module at call time, so a test or
a deterministic demo run replaces ``clock.datetime`` to control the clock.
"""

import threading
from datetime import UTC, datetime, timedelta, timezone
from typing import (
    overload,
)

# Frozen reference to the real datetime type used for isinstance guards.
# `now_utc` looks up `datetime` by name at call time so that tests can
# monkeypatch `_helpers.clock.datetime` to control the clock; those patches must not
# break isinstance() calls in parse_published, so we capture the real class here
# before any patch can replace the module-level name.
_datetime_type = datetime


class SteppingClock:
    """A ``datetime`` stand-in whose ``now()`` advances *step* on every call.

    Lives beside the clock it replaces because replacing ``clock.datetime`` is
    the documented way to control time (module docstring), and one stand-in
    serves every caller that does so: the deterministic demo recordings
    (``vultron.demo.determinism``, which re-exports this class), the docs
    example generator, and the tests that pin a stamp.

    The first call returns ``start + step``; ``step=timedelta(0)`` freezes the
    clock at *start*.  *start* must be timezone-aware, as ``now_utc()``
    promises its callers (CS-13-001).

    Only ``now()`` is provided.  This module keeps a private reference to the
    real class for its ``isinstance`` guards, so any other attribute a patched
    path reaches for raises ``AttributeError`` instead of returning a wrong
    time.  Reads are serialized, because in-process deliveries run on worker
    threads.
    """

    def __init__(
        self, start: datetime, step: timedelta = timedelta(seconds=1)
    ) -> None:
        if start.tzinfo is None:
            raise ValueError("SteppingClock start must be timezone-aware")
        self._t = start
        self._step = step
        self._lock = threading.Lock()

    def now(self, tz: timezone | None = None) -> datetime:
        with self._lock:
            self._t += self._step
            current = self._t
        return current.astimezone(tz) if tz is not None else current


def now_utc() -> datetime:
    """Return the current UTC instant, microseconds kept (CS-13-007)."""
    return datetime.now(UTC)


def now_utc_after(latest: datetime | None) -> datetime:
    """Return ``now_utc()``, or one microsecond after *latest* if later.

    For a stamp that must sort strictly after *latest* (CS-13-002): when the
    clock has not passed *latest* (two reads in one clock tick, or a *latest*
    from a peer whose clock runs ahead), the result is *latest* plus the
    smallest step a stored time can show.  The bump is returned in UTC
    whatever offset *latest* carries (CS-13-001).
    """
    now = now_utc()
    if latest is None or latest < now:
        return now
    return latest.astimezone(UTC) + timedelta(microseconds=1)


def from_now_utc(delta: timedelta) -> datetime:
    """Return the UTC instant *delta* from now (CS-13-004).

    The one place embargo-deadline arithmetic lives: a resolved duration
    (``InitialEmbargoDuration.duration``) becomes an ``end_time`` here, so
    every deadline the application produces is aware and UTC.
    """
    return now_utc() + delta


def days_from_now_utc(days: int) -> datetime:
    """Return a UTC datetime *days* in the future."""
    return from_now_utc(timedelta(days=days))


@overload
def require_future_aware(value: datetime, field: str = ...) -> datetime: ...


@overload
def require_future_aware(value: None, field: str = ...) -> None: ...


def require_future_aware(
    value: datetime | None, field: str = "end_time"
) -> datetime | None:
    """Return *value* when it is timezone-aware and in the future; else raise.

    The one validator for a deadline a caller *states* — an embargo end, a
    proposed embargo end — shared by the core trigger request models and the
    HTTP body models that mirror them, so the two layers cannot drift on what
    a well-formed deadline is (CS-13-001, CS-22-001).  ``None`` passes
    through: an optional deadline that was not stated is not a deadline to
    check.

    Raises:
        ValueError: naive (``tzinfo`` or ``utcoffset()`` is ``None``) or not
            strictly after now.
    """
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    if value <= now_utc():
        raise ValueError(f"{field} must be in the future")
    return value
