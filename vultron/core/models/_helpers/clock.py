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

"""The one wall-clock read of the core model, and the pure time helpers.

:func:`stamp_after`, :func:`deadline_from` and :func:`days_after` read no
clock: each takes the act's instant as an argument (ADR-0176).

:func:`now_utc` looks up ``datetime`` on this module at call time, so a test
or the docs-example generator, which runs no act, replaces ``clock.datetime``
to control the clock.  A recorded demo run does not: it installs its
recording clock through the act clock port (``vultron.demo.determinism``,
ADR-0176).
"""

import threading
from datetime import UTC, datetime, timedelta, timezone
from typing import (
    TypedDict,
    overload,
)

from vultron.errors import VultronValidationError

# Frozen reference to the real datetime type used for isinstance guards.
# `now_utc` looks up `datetime` by name at call time so that tests can
# monkeypatch `_helpers.clock.datetime` to control the clock; those patches must not
# break isinstance() calls in parse_published, so we capture the real class here
# before any patch can replace the module-level name.
_datetime_type = datetime


class SteppingClock:
    """A ``datetime`` stand-in whose ``now()`` advances *step* on every call.

    Lives beside the clock it can replace, and one stand-in serves every
    caller that controls time: the deterministic demo recordings, which
    install it as the act clock (``vultron.demo.determinism``, which
    re-exports this class), the docs example generator, and the tests that
    pin a stamp by replacing ``clock.datetime``.  Its ``now()`` is the act
    clock port's one operation.

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


class AuthoredTimes(TypedDict):
    """The ``published``/``updated`` pair, typed for ``**`` unpacking."""

    published: datetime
    updated: datetime


def authored_times(at: datetime) -> AuthoredTimes:
    """``published`` and ``updated`` for an object authored at *at*.

    *at* is the instant of the act that makes the object (ADR-0176): pass
    ``**authored_times(at)`` where the object is built, so the two author
    times are stated once and no model reads the clock.
    """
    return AuthoredTimes(published=at, updated=at)


class EmbargoAuthoredTimes(AuthoredTimes):
    """:class:`AuthoredTimes` plus an embargo's ``start_time``."""

    start_time: datetime


def embargo_authored_times(at: datetime) -> EmbargoAuthoredTimes:
    """The times of an embargo authored at *at*: it starts when it is made.

    Pass as ``**embargo_authored_times(at)`` (ADR-0176).
    """
    return EmbargoAuthoredTimes(published=at, updated=at, start_time=at)


def is_aware(value: datetime) -> bool:
    """Whether *value* is timezone-aware: it has a ``tzinfo`` that gives an
    offset (CS-13-001)."""
    return value.tzinfo is not None and value.utcoffset() is not None


def _require_aware_utc(at: datetime) -> datetime:
    """Return *at* in UTC; raise when it is naive (CS-13-001, CS-13-009)."""
    if not is_aware(at):
        raise ValueError("an act's instant must be timezone-aware")
    return at.astimezone(UTC)


def stamp_after(at: datetime, latest: datetime | None) -> datetime:
    """Return *at*, or one microsecond after *latest* if *at* is not later.

    The stamp for a record that must sort strictly after *latest*
    (CM-29-005), computed from the act's instant *at* and read from no clock
    (ADR-0176).  Stamps one act writes share its instant, so the second of
    them, and any stamp after a *latest* from a peer whose clock runs ahead,
    is *latest* plus the smallest step a stored time can show (ADR-0167).
    The result is in UTC whatever offset *at* or *latest* carries
    (CS-13-001, CS-13-009).

    Raises:
        ValueError: when *at* is naive.
    """
    stamp = _require_aware_utc(at)
    if latest is None or latest < stamp:
        return stamp
    return latest.astimezone(UTC) + timedelta(microseconds=1)


def deadline_from(at: datetime, delta: timedelta) -> datetime:
    """Return the UTC instant *delta* after the act's instant *at* (CS-13-004).

    The one place deadline arithmetic lives: a resolved duration
    (``InitialEmbargoDuration.duration``) becomes an ``end_time`` here,
    measured from the act's instant and read from no clock (ADR-0176), so
    every deadline the application produces is aware and UTC.

    Raises:
        ValueError: when *at* is naive.
    """
    return _require_aware_utc(at) + delta


def days_after(at: datetime, days: int) -> datetime:
    """Return the UTC instant *days* days after the act's instant *at*.

    Raises:
        ValueError: when *at* is naive.
    """
    return deadline_from(at, timedelta(days=days))


@overload
def require_aware(value: datetime, field: str = ...) -> datetime: ...


@overload
def require_aware(value: None, field: str = ...) -> None: ...


def require_aware(
    value: datetime | None, field: str = "end_time"
) -> datetime | None:
    """Return *value* when it is timezone-aware; else raise.

    What a request body can judge about a deadline it carries: whether the
    deadline is in the future depends on the act that reads it, so that is
    :func:`require_future_aware`'s question, asked against the act's instant
    (ADR-0176).  ``None`` passes through: an optional deadline that was not
    stated is not a deadline to check.

    Raises:
        ValueError: naive (``tzinfo`` or ``utcoffset()`` is ``None``).
    """
    if value is not None and not is_aware(value):
        raise ValueError(f"{field} must be timezone-aware")
    return value


@overload
def require_future_aware(
    value: datetime, field: str = ..., *, at: datetime
) -> datetime: ...


@overload
def require_future_aware(
    value: None, field: str = ..., *, at: datetime
) -> None: ...


def require_future_aware(
    value: datetime | None, field: str = "end_time", *, at: datetime
) -> datetime | None:
    """Return *value* when it is timezone-aware and after *at*; else raise.

    The one check for a deadline a caller *states* — an embargo end, a
    proposed embargo end, an answer deadline — judged against *at*, the
    instant of the act that reads it, never a clock read (ADR-0176).  A
    trigger passes its act's instant; the request body checks only that the
    deadline is aware (:func:`require_aware`), so the two layers cannot drift
    on what a well-formed deadline is (CS-13-001, CS-22-001).  ``None``
    passes through.

    Raises:
        VultronValidationError: naive, or not strictly after *at*.  A
            ``ValueError``, so a request answers it as a client fault.
    """
    if value is None:
        return None
    if not is_aware(value):
        raise VultronValidationError(f"{field} must be timezone-aware")
    if value <= at:
        raise VultronValidationError(
            f"{field} must be in the future (after {at.isoformat()})"
        )
    return value
