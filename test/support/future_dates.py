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

"""Shared far-future date for tests that need a future embargo end_time or deadline.

Tests that used a hardcoded ``datetime(2030, ...)`` literal would time-bomb
once real time passes that date: any validator that checks ``end_time >
now()`` would raise, and any test that depends on the date being in the
future would fail.  Importing :data:`FAR_FUTURE` from here instead of
repeating the arithmetic in each module keeps the fix in one place (CS-22-001).

The value is computed once at import time — well in advance of the current
date — so every test in a run shares a consistent value.
"""

from vultron.core.models._helpers.clock import days_from_now_utc

#: A far-future UTC datetime: five years from today's import-time clock read.
#:
#: Use this anywhere a test needs *some* date that is clearly in the future
#: (embargo ``end_time``, ownership-transfer deadline, RSVP deadline …) but
#: does not care about the specific value.  Five years gives a wide margin
#: while still being a finite, reviewable epoch (CS-13-004).
FAR_FUTURE = days_from_now_utc(365 * 5)
