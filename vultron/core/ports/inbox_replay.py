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

"""Driven port that replays a held received activity through the inbox.

A held ``Announce(CaseLedgerEntry)`` that a commit or a case seed makes
appliable is a delivery of its own (SYNC-14-009, ADR-0135): core does not run
its tree inside the delivery that made it appliable.  It asks this port to
replay the ``Announce`` it holds, the one that was received, through the
receiving actor's own inbox, whose sole entry point is ``process_payload``
(IO-02-003).  The drain therefore runs the same path as in-order delivery by
construction (SYNC-14-008), and nothing is built or attributed to a sender
who did not send it.

See also:
    - ``vultron/adapters/driven/inbox_replay_adapter.py`` — adapter
    - ``vultron/core/behaviors/sync/nodes/replay_held.py`` — the node that
      calls it
"""

from typing import Protocol


class InboxReplayPort(Protocol):
    """Driven port: replay a held received activity through this inbox."""

    def replay_held(self, activity_id: str) -> None:
        """Queue the held received activity *activity_id* for replay.

        The activity's received body is already held for the replay, in a
        ``DeferredInboxActivity`` (IO-03-004).  The adapter queues the id for
        the receiving actor's inbox processing and does not process it: the
        replay runs after the delivery that called this method has finished,
        and parses the held body again, so it carries the first delivery's
        received evidence (VM-08-002).

        Args:
            activity_id: The sender's id for the held activity.
        """
        ...


__all__ = ["InboxReplayPort"]
