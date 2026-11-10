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

"""The system stopwatch: the one monotonic read of the core (ADR-0176).

:class:`SystemStopwatch` implements
:class:`~vultron.core.ports.clock.StopwatchPort` over :func:`time.monotonic`.
It measures how long work took against a limit, such as the call-out time
budget (BT-18-015).  It is a named stopwatch site in the clock-read
architecture test (CS-13-002): a reading is not a time of day, never reaches a
decision about the case or a record, and the recording clock does not see it.

It lives in core, not with the system clocks in
``vultron/adapters/driven/clock.py``, because its first holder, the call-out
seam, is built inside tree builders that no composition root reaches.  A test
injects its own stopwatch through the port instead.
"""

import time


class SystemStopwatch:
    """The production stopwatch (``StopwatchPort``)."""

    def seconds(self) -> float:
        """Return :func:`time.monotonic`, in seconds."""
        return time.monotonic()


__all__ = ["SystemStopwatch"]
