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
date — so every test in a run shares a consistent value.  Its microseconds are
truncated on purpose: the reason sits on :data:`FAR_FUTURE` itself, beside the
call that does it, and it is load-bearing for wire assertions in two other
modules.  Do not "simplify" it away.

Three idioms, and which one to reach for
========================================

A test that names a date is asking one of three different questions, and only
the first is :data:`FAR_FUTURE`'s.  A sweep that replaces date literals MUST
decide which question each site asks before touching it.

1. *"Some date plausibly ahead, which I expect to be accepted."*  Use
   :data:`FAR_FUTURE`.  The specific instant does not matter, so an absolute
   literal buys nothing and adds a time bomb.

2. *"A date implausibly far ahead, which I expect to be refused."*  Keep the
   absolute ``datetime(2099, ...)`` literal.  Substituting :data:`FAR_FUTURE`
   could land the value *inside* the tolerance the test is probing and turn a
   refusal test green for the wrong reason: CLP-14-007 bounds how far ahead a
   claimed ``published`` may be, and
   ``test_clp_14_007_future_timestamp_payload_rejected`` in
   ``test/core/models/test_clp_14_15_invariants.py`` asserts the
   ``VultronCanonicalEntryError`` that bound raises.  Five years ahead may sit
   inside a tolerance a 2099 date is safely outside.

3. *"This exact instant."*  Keep the literal: the value *is* the assertion.  A
   naive-to-UTC coercion test needs both halves to name one instant
   (``test_naive_deadline_is_read_as_utc`` in
   ``test/core/models/test_case_participant.py``), a pinned instant anchors a
   serialization or ordering expectation, and a deliberately *past* date is not
   a future date at all.

An idiom 2 or idiom 3 site stays as it is, carrying a one-line reason that says
which it is.  See also ``notes/testing-pitfalls.md`` § "Assertion Quality".
"""

from vultron.core.models._helpers.clock import days_from_now_utc

#: A far-future UTC datetime: five years from today's import-time clock read.
#:
#: Use this anywhere a test needs *some* date that is clearly in the future
#: (embargo ``end_time``, ownership-transfer deadline, RSVP deadline …) but
#: does not care about the specific value.  Five years gives a wide margin
#: while still being a finite, reviewable epoch (CS-13-004).
#:
#: The microseconds are truncated on purpose.  A test that asserts how this
#: instant was *serialized* is asserting the fixed six-digit form, which pads
#: a whole second to ``.000000`` where :meth:`datetime.isoformat` writes no
#: fraction at all (CS-13-007).  A clock-read microsecond would make the two
#: forms coincide, so such an assertion would stop telling them apart — and
#: would break outright on the one read in a million that lands on zero.
FAR_FUTURE = days_from_now_utc(365 * 5).replace(microsecond=0)
