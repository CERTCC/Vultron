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

"""Close the actor stores after a test, never under a sender-sequence hold timer.

The hold timer reads every hosted actor's store, on its app's event loop and
in the worker thread each round is offloaded to (SYNC-21-011).  Closing a
SQLite connection under a read on another thread segfaults the interpreter,
which kills the xdist worker and fails the run with no assertion behind it
(#6148).  So per-test disposal first stops any timer a test left running,
then disposes, then fails that test by name.

After disposal it also closes any connection a disposed in-memory store opened
during the test, and fails that test too
(``test.support.orphan_store_connections``, #6001).
"""

import asyncio

from test.support.orphan_store_connections import close_orphan_connections
from vultron.adapters.driving.fastapi.sender_sequence_holds import (
    SenderSequenceHoldTimer,
    finish_sender_sequence_hold_timer,
    running_sender_sequence_hold_timers,
)

#: How long a stop waits for the timer's round in progress to finish.
STOP_TIMEOUT_SECONDS = 10.0


class HoldTimerLeakedError(RuntimeError):
    """A sender-sequence hold timer was still running at store disposal."""


def stop_hold_timer_from_another_thread(
    timer: SenderSequenceHoldTimer,
    *,
    timeout: float = STOP_TIMEOUT_SECONDS,
) -> None:
    """Stop *timer* from outside its event loop and wait for its task to end.

    Signalled and awaited on the timer's own loop, as the lifespan's shutdown
    does, never cancelled: a cancelled task reads as ended while its round's
    worker thread may still be reading a store.

    Raises:
        HoldTimerLeakedError: the timer's loop is no longer running, so
            nothing can end the task, or its round did not finish within
            *timeout*.
        RuntimeError: called from the timer's own loop thread, where the wait
            would deadlock.
    """
    loop = timer.task.get_loop()
    try:
        running_here = asyncio.get_running_loop() is loop
    except RuntimeError:
        running_here = False
    if running_here:
        raise RuntimeError(
            "stop_hold_timer_from_another_thread() was called on the timer's"
            " own loop; await finish_sender_sequence_hold_timer() there."
        )
    if not loop.is_running():
        raise HoldTimerLeakedError(
            "a sender-sequence hold timer's event loop stopped with the timer"
            " still running, so it cannot be stopped; the actor stores were"
            " not disposed (#6148)."
        )
    stopped = asyncio.run_coroutine_threadsafe(
        finish_sender_sequence_hold_timer(timer), loop
    )
    try:
        stopped.result(timeout=timeout)
    except TimeoutError as exc:
        raise HoldTimerLeakedError(
            f"a sender-sequence hold timer's round did not finish within"
            f" {timeout}s of being stopped; the actor stores were not"
            f" disposed (#6148)."
        ) from exc


def dispose_actor_stores_between_tests() -> None:
    """Dispose every actor store, first stopping any hold timer still running.

    The body of the root conftest's ``_dispose_actor_stores_between_tests``.
    A timer that cannot be stopped leaves the stores open: a later test fails
    on their rows, but no store is closed under a read.

    Then closes any connection a disposed in-memory store opened during the
    test (#6001).

    Raises:
        HoldTimerLeakedError: a timer was still running.  When it was stopped,
            the stores are disposed before this is raised, so only the test
            that leaked it fails.
        OrphanStoreConnectionError: a disposed in-memory store opened a
            connection during the test.  It is closed before this is raised,
            so no later test fails on its ``ResourceWarning``.
    """
    from vultron.adapters.driven.datalayer_sqlite import (
        reset_datalayer,
        reset_store_claimants,
    )

    leaked = running_sender_sequence_hold_timers()
    for timer in leaked:
        stop_hold_timer_from_another_thread(timer)
    reset_datalayer()
    reset_store_claimants()
    try:
        close_orphan_connections()
    finally:
        if leaked:
            raise HoldTimerLeakedError(
                f"{len(leaked)} sender-sequence hold timer(s) still running"
                " at store disposal: a fixture or test started the production"
                " lifespan and did not stop the timer before it ended.  The"
                " timer was stopped and the stores disposed.  Exit the"
                " TestClient (its shutdown awaits the timer), or stop it with"
                " stop_hold_timer_from_another_thread() as"
                " test/demo/conftest.py's client fixture does (#6148)."
            )
