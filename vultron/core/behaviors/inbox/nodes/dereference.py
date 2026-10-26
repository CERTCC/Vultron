#!/usr/bin/env python
"""Inbox pipeline step 5: defer an activity until the objects it names arrive.

A receiver that does not hold an object a received activity names fetches it
from whoever holds it, and the activity waits, held whole, until the fetch
settles (AKM-05-007, ADR-0107).  The fetch is the adapter's, made after the
inbox run; this step only decides, through the
:class:`~vultron.core.behaviors.inbox.models.ObjectDereferencePort`, whether
the activity waits, and hands a fetched object that is never stored to the
event it was fetched for.

Per specs/actor-knowledge-model.yaml AKM-05-007 and AKM-05-008.
"""

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

from __future__ import annotations

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.inbox.nodes.pipeline import (
    KEY_CONTEXT_ID,
    KEY_DEREFERENCE,
    KEY_EVENT,
    _InboxNodeWithPorts,
)
from vultron.core.models.events import VultronEvent
from vultron.core.models.object_fetch import (
    ObjectFetchState,
    ObjectReference,
    PendingObjectFetch,
)
from vultron.core.ports.object_dereference import ObjectDereferencePort
from vultron.core.services.dereference import with_fetched_object
from vultron.errors import VultronError


class DereferenceCheckNode(_InboxNodeWithPorts):
    """Step 5: defer the activity while a fetch of an object it names is open.

    Asks the port which objects the event names that the receiver must fetch
    (:func:`~vultron.core.services.dereference.references_to_fetch`).  For
    each one:

    - no fetch recorded, or one still ``PENDING``: the activity waits on it;
    - ``FETCHED`` (an object handed off, never stored): the event takes the
      fetched object in place of its reference, and stops waiting;
    - ``FAILED``: the activity stops waiting and goes on with the reference
      unresolved, so the path that needs the object refuses it as it did
      before dereference existed (AKM-05-008).

    An activity waiting on any fetch is held for its replay and deferred
    (``deferred`` outcome); otherwise the node writes the event, with every
    handed-off object in place, and passes to dispatch.  A store-kept object
    needs no hand-off: once fetched it is held, so the replay rehydrates it
    and no reference to it remains.

    Passes through to SUCCESS when no port is wired.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        "inbox_event_in": PortInformation(data_type=object, required=True),
        KEY_CONTEXT_ID: PortInformation(data_type=object, required=False),
        KEY_DEREFERENCE: PortInformation(data_type=object, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        **_InboxNodeWithPorts.OUTPUT_PORTS,
        KEY_EVENT: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            # Read and write of the event share one slot, as the rehydrate
            # step's activity does.
            "inbox_event_in": f"/{KEY_EVENT}",
            KEY_EVENT: f"/{KEY_EVENT}",
            KEY_CONTEXT_ID: f"/{KEY_CONTEXT_ID}",
            KEY_DEREFERENCE: f"/{KEY_DEREFERENCE}",
        }

    def update(self) -> Status:
        try:
            event: VultronEvent = self.get_input("inbox_event_in")
        except (KeyError, NoDataAvailable) as exc:
            return self._reject(f"Missing blackboard key: {exc}")
        try:
            port: ObjectDereferencePort | None = self.get_input(
                KEY_DEREFERENCE
            )
        except (NotImplementedError, NoDataAvailable, KeyError):
            port = None
        if port is None:
            return Status.SUCCESS
        try:
            context_id: str | None = self.get_input(KEY_CONTEXT_ID)
        except (NotImplementedError, NoDataAvailable):
            context_id = None

        outstanding: list[ObjectReference] = []
        for reference in port.references_to_fetch(event, context_id):
            fetch = port.fetch_of(reference.object_id)
            if fetch is None or fetch.state is ObjectFetchState.PENDING:
                outstanding.append(reference)
                continue
            port.release(reference.object_id, event.activity_id)
            if fetch.state is ObjectFetchState.FAILED:
                self.logger.info(
                    "%s: activity_id=%s goes on without '%s', whose fetch"
                    " failed: %s",
                    self.name,
                    event.activity_id,
                    reference.object_id,
                    fetch.failure_reason,
                )
                continue
            event = self._hand_off(event, reference, port, fetch)

        if outstanding:
            port.await_fetches(event.activity_id, outstanding)
            waited = ", ".join(repr(r.object_id) for r in outstanding)
            return self._defer(f"Deferred: awaiting the fetch of {waited}")

        self._set_output(KEY_EVENT, event)
        return Status.SUCCESS

    def _hand_off(
        self,
        event: VultronEvent,
        reference: ObjectReference,
        port: ObjectDereferencePort,
        fetch: PendingObjectFetch,
    ) -> VultronEvent:
        """The event carrying the fetched object, or unchanged if it is unfit.

        A fetched body that is not the object named, or not one the event
        can carry, is treated as a failed fetch: the event goes on with its
        reference, and the path that needs the object refuses it.
        """
        try:
            fetched = port.fetched_object(fetch)
            return with_fetched_object(event, reference, fetched)
        except VultronError as exc:
            self.logger.warning(
                "%s: activity_id=%s goes on without '%s': the fetched object"
                " is unfit (%s)",
                self.name,
                event.activity_id,
                reference.object_id,
                exc,
            )
            return event


__all__ = ["DereferenceCheckNode"]
