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

"""The one serialized timestamp form and the reading of claimed times (CS-13)."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import (
    Any,
    overload,
)

from pydantic import BaseModel, SerializerFunctionWrapHandler, field_serializer

from vultron.core.models._helpers.clock import _datetime_type


def format_timestamp(value: datetime) -> str:
    """Return *value* in the one serialized form a time has (CS-13-007).

    RFC 3339 with exactly six fractional-second digits and the offset the
    value carries: ``2026-10-30T12:00:00.000000+00:00``.  The digits are
    written even when the microseconds are zero, so one instant at one offset
    has one string; the case ledger hashes and compares that text
    (ADR-0167).  A carried time keeps its own offset (CS-13-005), so the
    same instant at ``+02:00`` is a different string, as it was received.
    A value with no usable offset -- naive, or carrying a ``tzinfo`` whose
    ``utcoffset()`` is ``None`` -- is read as UTC (CS-13-001), so no time
    reaches the wire without an offset (CS-13-006).
    """
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat(timespec="microseconds")


def timestamp_serializer(*fields: str) -> Any:
    """Return a ``field_serializer`` writing *fields* through :func:`format_timestamp`.

    Assign it in the body of every model that declares a ``datetime`` field,
    under a name of its own, so a subclass's assignment never replaces its
    parent's::

        received_at: datetime
        _serialize_received_at = timestamp_serializer("received_at")

    This factory is not the only route to the form.  The four AS2 timestamps
    every object inherits (``start_time``, ``end_time``, ``published``,
    ``updated``) are covered by hand-written ``field_serializer`` methods on
    the two roots instead -- ``CoreObject._serialize_datetime`` and
    ``as_Object.serialize_datetime`` -- which call :func:`format_timestamp`
    directly and account for most of the fields the ratchet walks.  What
    CS-13-007 rests on is that *every* ``datetime`` field has a serializer
    routing through :func:`format_timestamp`, not that each one uses this
    factory; ``test_every_model_datetime_field_serializes_in_the_fixed_form``
    is what holds that line.

    A decorator, not an ``Annotated`` serializer, because ``serialize_as_any``
    dumps (outbox delivery uses one) skip an ``Annotated`` serializer and fall
    back to Pydantic's own form, which drops the digits of a whole second
    (CS-13-007).  A value that is not a ``datetime`` (``None``, or another
    member of a union) is serialized as the field otherwise would be.
    """

    def _serialize(
        self: Any, value: Any, handler: SerializerFunctionWrapHandler
    ) -> Any:
        if isinstance(value, _datetime_type):
            return format_timestamp(value)
        return handler(value)

    return field_serializer(*fields, mode="wrap", when_used="json")(_serialize)


@overload
def as_utc(value: datetime) -> datetime: ...


@overload
def as_utc(value: None) -> None: ...


def as_utc(value: datetime | None) -> datetime | None:
    """Return *value* as a timezone-aware UTC datetime, or ``None``.

    Wire-deserialized timestamps may be naive (``datetime.fromisoformat`` on an
    offset-less ISO string yields a naive datetime). Assume naive datetimes are
    UTC — consistent with :func:`now_utc` — so time comparisons never mix
    naive and aware values, which would raise ``TypeError``.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def parse_published(value: Any) -> datetime | None:
    """Return *value* as a timezone-aware UTC datetime, or ``None``.

    Accepts a ``datetime`` or an ISO 8601 string; anything else — including a
    string that is not valid ISO 8601 — yields ``None`` so callers can tell
    "absent" from "unparseable" by checking the raw value themselves.  Naive
    inputs are assumed UTC, consistent with :func:`as_utc`.

    Unlike :func:`as_utc`, which only *attaches* UTC to a naive value, an
    aware input in another offset is converted, so the return value is always
    in UTC.  Comparisons work either way — Python compares aware datetimes
    across offsets correctly — but the value is rendered into
    spec-citing violation messages, and a mixed-offset message reads as though
    the guard compared unlike quantities.

    Shared by the case-ledger commit-boundary guard and the per-actor
    predecessor lookup that feeds it, so both read a claimed
    ``payloadSnapshot.published`` the same way (CS-22-001).
    """
    if isinstance(value, _datetime_type):
        parsed: datetime | None = value
    elif isinstance(value, str):
        try:
            parsed = _datetime_type.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    aware = as_utc(parsed)
    assert (
        aware is not None
    )  # parsed is a datetime here; as_utc only returns None for None input
    return aware.astimezone(UTC)


class MissingClaimedTimeError(ValueError):
    """A received object that must carry its sender's time carries none.

    Raised from an inbound ``mode="before"`` validator, so a
    :class:`ValueError` subclass: pydantic converts only ``ValueError`` and
    ``AssertionError`` into a ``ValidationError``.  The parser finds this cause
    in the error list and refuses the activity as missing a ``published``,
    naming where the object sat (CLP-15-010).
    """


def refuse_absent_published(
    cls: type[BaseModel], data: Mapping[str, Any]
) -> None:
    """Raise :class:`MissingClaimedTimeError` when *data* has no ``published``.

    Absent, ``None`` and blank are the same omission (CS-08-001).  For use on
    the inbound path only, before ``absent_times_as_none`` would read the
    omission as ``None``: an object this process authors takes the clock
    default instead.
    """
    value = data.get("published")
    if value is None or (isinstance(value, str) and not value.strip()):
        raise MissingClaimedTimeError(
            f"{cls.__name__} carries no 'published'; a received"
            f" {cls.__name__} must carry the time its sender claims it was"
            " made, and the receiver does not supply its own clock"
            " (SM-05-003, CLP-15-010)"
        )
