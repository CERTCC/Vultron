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

from datetime import datetime, timedelta, timezone


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
    return datetime.now(timezone.utc).replace(microsecond=0)
