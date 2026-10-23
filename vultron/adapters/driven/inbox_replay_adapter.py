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

"""Adapter implementing :class:`~vultron.core.ports.inbox_replay.InboxReplayPort`.

Replays a held received activity, a held ``Announce(CaseLedgerEntry)``, through
the receiving actor's own inbox as a delivery of its own (SYNC-14-009,
ADR-0135).  The activity is already held as the body that arrived, in a
``DeferredInboxActivity`` keyed by the receiver (IO-03-004, DL-06-006); this
adapter only appends its id to the actor's inbox queue.

That queue is the inbox's existing scheduling path: the delivery that made the
entry appliable is still running when the port is called, and once it ends
``run_inbox_pipeline`` pops the queued id and replays the held activity through
``process_payload`` under the same actor lock (IO-02-003, BT-11-001).  The
older ``inbox_handler`` queue worker drains the same queue and rebuilds from
the same record.  The replay parses the held body again, so it carries the
evidence the first delivery did (VM-08-002); intake already archived that
delivery, so it archives nothing new (CLP-10-017).
"""

import logging

from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


class InboxReplayAdapter:
    """Queue a held received activity for this actor's own inbox.

    Args:
        dl: The receiving actor's own DataLayer (ADR-0073), whose inbox queue
            the inbox loop drains.
    """

    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def replay_held(self, activity_id: str) -> None:
        """Queue *activity_id*, which must be held for its replay.

        An id already queued is not queued twice.

        Raises:
            VultronWiringError: When nothing holds *activity_id*: a queued id
                with no held body would be dropped by the replay
                (DL-06-006).
        """
        held = self._dl.read(DeferredInboxActivity.build_id(activity_id))
        if not isinstance(held, DeferredInboxActivity):
            raise VultronWiringError(
                f"inbox replay: nothing holds activity '{activity_id}' for"
                " its replay, so queueing it would drop it (DL-06-006)"
            )
        if activity_id in self._dl.inbox_list():
            logger.debug(
                "inbox replay: activity '%s' is already queued for actor '%s'",
                activity_id,
                getattr(self._dl, "actor_id", None),
            )
            return
        self._dl.inbox_append(activity_id)
        logger.debug(
            "inbox replay: queued held activity '%s' for actor '%s'",
            activity_id,
            getattr(self._dl, "actor_id", None),
        )


__all__ = ["InboxReplayAdapter"]
