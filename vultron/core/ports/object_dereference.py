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

"""Driven port: fetch-and-defer for objects a received activity names.

Implemented by the inbox adapter over the receiving actor's store
(``vultron.adapters.driving.fastapi.inbox_dereference``), which also makes the
fetch, by HTTP, after the inbox run (AKM-05-003, AKM-05-007).
"""

from typing import Protocol, runtime_checkable

from vultron.core.models.base import CoreObject
from vultron.core.models.events import VultronEvent
from vultron.core.models.object_fetch import (
    ObjectReference,
    PendingObjectFetch,
)


@runtime_checkable
class ObjectDereferencePort(Protocol):
    """Port: fetch-and-defer for objects a received activity names.

    Gives the inbox's
    :class:`~vultron.core.behaviors.inbox.nodes.dereference.DereferenceCheckNode`
    the receiver's fetch records without adapter imports in core (IO-03-002).
    The fetch itself is the adapter's, run after the inbox run settles; core
    only names what to fetch (AKM-05-007).
    """

    def references_to_fetch(
        self, event: VultronEvent, context_id: str | None
    ) -> list[ObjectReference]:
        """The objects *event* names that the receiver must fetch first."""
        ...  # pragma: no cover

    def fetch_of(self, object_id: str) -> PendingObjectFetch | None:
        """The receiver's fetch record for *object_id*, if any."""
        ...  # pragma: no cover

    def await_fetches(
        self, activity_id: str, references: list[ObjectReference]
    ) -> None:
        """Hold *activity_id* for its replay and wait on each reference's fetch.

        The adapter holds the activity's received body under a key the
        receiver derives (DL-06-006, IO-03-004), and records the activity
        among the waiters of one fetch per reference, starting the fetch
        when none is recorded.
        """
        ...  # pragma: no cover

    def fetched_object(self, fetch: PendingObjectFetch) -> CoreObject:
        """The object a ``FETCHED`` record holds, read from its body.

        Raises:
            VultronValidationError: When the body is not an object the
                vocabulary knows.
        """
        ...  # pragma: no cover

    def release(self, object_id: str, activity_id: str) -> None:
        """Stop *activity_id* waiting on *object_id*'s settled fetch.

        The record is removed once nothing waits on it, so a later activity
        naming the object fetches it afresh.
        """
        ...  # pragma: no cover


__all__ = ["ObjectDereferencePort"]
