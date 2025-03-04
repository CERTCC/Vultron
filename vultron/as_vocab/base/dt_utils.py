#!/usr/bin/env python
"""
This module contains utilities for working with datetime objects.
"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from datetime import datetime, timedelta

import pytz

from vultron.as_vocab.base.errors import (
    IsoDecodingError,
    IsoEncodingError,
)


def days_from_now_utc(days: int = 45) -> datetime:
    """Get a datetime object representing the current time plus the number of days specified.

    Args:
        days: The number of days to add to the current time

    Returns:
        A datetime object representing the current time plus the number
        of days specified
    """
    return now_utc() + timedelta(days=days)


def now_utc() -> datetime:
    """Get the current time in UTC at one second resolution

    Returns:
        A timezone-aware datetime object representing the current time in UTC
    """
    return datetime.now(pytz.UTC).replace(microsecond=0)


def to_isofmt(dt: datetime | str | None) -> str:
    """Encodes a datetime object into a string.
    If dt isn't actually a datetime, but it is a string, or None, just return it.

    Args:
        dt: a datetime object, or a string, or None

    Returns:
        an iso-formatted date time string if dt is a datetime, otherwise dt
    """
    if isinstance(dt, datetime):
        return datetime.isoformat(dt)
    if dt is None or isinstance(dt, str):
        return dt
    raise IsoEncodingError(f"Can't convert {dt} to string (or None.)")


def from_isofmt(datestring: str | datetime | None) -> datetime:
    """Decodes a string into a datetime object.
    If datestring isn't actually a string, but it is a datetime, or None, just return it.

    Args:
        datestring: an iso-formatted date time string

    Returns:
        a datetime object
    """
    if isinstance(datestring, str):
        return datetime.fromisoformat(datestring)
    if datestring is None or isinstance(datestring, datetime):
        return datestring

    raise IsoDecodingError(
        f"Can't convert {datestring} to datetime (or None.)"
    )
