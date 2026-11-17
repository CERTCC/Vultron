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

"""Refuse to close the actor stores while a sender-sequence hold timer runs.

The hold timer reads every hosted actor's store from its app's event-loop
thread (SYNC-21-011).  Closing a SQLite connection under a read on another
thread segfaults the interpreter, which kills the xdist worker and fails the
run with no assertion behind it (#6148).  A test that leaves a timer running
must fail in its own teardown, with a name, instead.
"""

from vultron.adapters.driving.fastapi.sender_sequence_holds import (
    running_sender_sequence_hold_timers,
)


class HoldTimerLeakedError(RuntimeError):
    """A sender-sequence hold timer was still running at store disposal."""


def refuse_disposal_under_live_hold_timer() -> None:
    """Raise :class:`HoldTimerLeakedError` if any hold timer still runs.

    Called before the stores are disposed, so a leak is reported by the test
    that left it, and nothing is closed under the timer's read.
    """
    running = running_sender_sequence_hold_timers()
    if running:
        raise HoldTimerLeakedError(
            f"{len(running)} sender-sequence hold timer(s) still running at"
            " store disposal: a fixture or test started the production"
            " lifespan and did not stop the timer before it ended.  Exit the"
            " TestClient (its shutdown awaits the timer), or stop it as"
            " test/demo/conftest.py's client fixture does (#6148)."
        )
