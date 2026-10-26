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

"""Fetch-and-defer for the inbox: the port, the settlement and the replay.

An activity naming an object its receiver must fetch first waits, held whole,
on a :class:`~vultron.core.models.object_fetch.PendingObjectFetch`
(:class:`FastAPIDereferencePort`, AKM-05-007).  After the inbox run, outside
the actor's inbox lock, the open fetches are made
(:func:`open_fetches`, an :class:`~vultron.adapters.driven.http_object_fetch.ObjectFetcher`),
and each result is settled under the lock (:func:`settle_fetch`): a fetched
case object is stored, a fetched profile is kept on the record for its
waiters, and a failed fetch is logged at WARNING (AKM-05-008).  Either way
the waiting activities are queued again, and the inbox queue drain replays
them (IE-06-004).
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from vultron.adapters.driven.http_object_fetch import ObjectFetchResult
from vultron.adapters.driven.inbox_replay_adapter import InboxReplayAdapter
from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.core.models.base import CoreObject
from vultron.core.models.events import VultronEvent
from vultron.core.models.object_fetch import (
    ObjectFetchState,
    ObjectFetchUse,
    ObjectReference,
    PendingObjectFetch,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.dereference import references_to_fetch
from vultron.errors import (
    VultronError,
    VultronValidationError,
    VultronWiringError,
)
from vultron.primitives import same_actor_id
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

logger = logging.getLogger(__name__)

#: The record type every fetch is stored under.
FETCH_RECORD_TYPE = "PendingObjectFetch"


def parse_fetched_object(
    body: dict[str, Any], object_id: str
) -> CoreObject | as_Base:
    """The object a fetch answered with, typed by its ``type``.

    Raises:
        VultronValidationError: When the body names no type the vocabulary
            knows, does not validate as that type, or is not the object
            *object_id* names.
    """
    type_name = body.get("type")
    if not isinstance(type_name, str) or not type_name:
        raise VultronValidationError(
            f"the fetched body for {object_id!r} names no type"
        )
    try:
        cls = find_in_vocabulary(type_name)
        parsed = cls.model_validate(body)
    except (KeyError, ValueError) as exc:
        raise VultronValidationError(
            f"the fetched body for {object_id!r} is not a valid"
            f" {type_name!r}: {exc}"
        ) from exc
    if not isinstance(parsed, (CoreObject, as_Base)):
        raise VultronValidationError(
            f"the fetched body for {object_id!r} is a {type_name!r}, which"
            " is not an object"
        )
    parsed_id = getattr(parsed, "id_", None)
    if not isinstance(parsed_id, str) or not same_actor_id(
        parsed_id, object_id
    ):
        raise VultronValidationError(
            f"the fetched object {parsed_id!r} is not the {object_id!r}"
            " that was asked for"
        )
    return parsed


def _fetch_record(dl: DataLayer, object_id: str) -> PendingObjectFetch | None:
    record = dl.read(PendingObjectFetch.build_id(object_id))
    return record if isinstance(record, PendingObjectFetch) else None


class FastAPIDereferencePort:
    """Fetch-and-defer port over the receiving actor's store.

    Args:
        actor_dl: The receiving actor's DataLayer, which holds the fetch
            records and the held activities.
        actor_id: Canonical URI of the receiving actor.
        staging: The inbox run's inline-object staging, which holds a
            waiting activity for its replay.
    """

    def __init__(
        self,
        actor_dl: DataLayer,
        actor_id: str,
        staging: InlineObjectStaging,
    ) -> None:
        self._dl = actor_dl
        self._actor_id = actor_id
        self._staging = staging

    def references_to_fetch(
        self, event: VultronEvent, context_id: str | None
    ) -> list[ObjectReference]:
        """Core's answer, over this actor's store (AKM-05-007)."""
        # The actor's SQLite store is a CasePersistence too; the port is
        # typed as the narrower DataLayer (see the action-rules route).
        return references_to_fetch(
            event, cast(CasePersistence, self._dl), self._actor_id, context_id
        )

    def fetch_of(self, object_id: str) -> PendingObjectFetch | None:
        """The fetch record for *object_id*, if any."""
        return _fetch_record(self._dl, object_id)

    def await_fetches(
        self, activity_id: str, references: list[ObjectReference]
    ) -> None:
        """Hold *activity_id* and record it as a waiter of each fetch.

        The activity is held before any record names it, so a failed hold
        records nothing; all of it commits together.
        """
        with self._dl.transaction():
            self._staging.hold_for_replay(activity_id)
            for reference in references:
                record = _fetch_record(
                    self._dl, reference.object_id
                ) or PendingObjectFetch.for_reference(reference)
                if activity_id not in record.waiting_activity_ids:
                    record = record.model_copy(
                        update={
                            "waiting_activity_ids": [
                                *record.waiting_activity_ids,
                                activity_id,
                            ]
                        }
                    )
                self._dl.save(record)
                logger.info(
                    "Activity %s for actor_id=%s waits on the fetch of '%s'"
                    " from %s (AKM-05-007)",
                    activity_id,
                    self._actor_id,
                    reference.object_id,
                    reference.host_actor_id,
                )

    def fetched_object(self, fetch: PendingObjectFetch) -> CoreObject:
        """The handed-off object a ``FETCHED`` record holds."""
        if fetch.fetched_body is None:
            raise VultronValidationError(
                f"the fetch of {fetch.object_id!r} holds no fetched body"
            )
        parsed = parse_fetched_object(
            json.loads(fetch.fetched_body), fetch.object_id
        )
        if not isinstance(parsed, CoreObject):
            raise VultronValidationError(
                f"the fetched {fetch.object_id!r} is a"
                f" {type(parsed).__name__}, not a core object"
            )
        return parsed

    def release(self, object_id: str, activity_id: str) -> None:
        """Drop *activity_id* from the settled fetch; remove an unawaited one."""
        record = _fetch_record(self._dl, object_id)
        if record is None:
            return
        remaining = [
            waiter
            for waiter in record.waiting_activity_ids
            if waiter != activity_id
        ]
        if remaining:
            self._dl.save(
                record.model_copy(update={"waiting_activity_ids": remaining})
            )
        else:
            self._dl.delete(record.type_, record.id_)


def open_fetches(dl: DataLayer) -> list[PendingObjectFetch]:
    """Every fetch in *dl* still ``PENDING``."""
    return [
        record
        for record in dl.list_objects(FETCH_RECORD_TYPE)
        if isinstance(record, PendingObjectFetch)
        and record.state is ObjectFetchState.PENDING
    ]


def _store_fetched(
    dl: DataLayer, fetch: PendingObjectFetch, fetched: CoreObject | as_Base
) -> None:
    """Keep a fetched case object, never over one already held (MV-10-003)."""
    if dl.read(fetch.object_id) is not None:
        logger.info(
            "Fetched '%s', which is already held; keeping the held copy",
            fetch.object_id,
        )
        return
    dl.save(fetched)


def settle_fetch(
    dl: DataLayer, actor_id: str, object_id: str, result: ObjectFetchResult
) -> list[str]:
    """Record what the fetch of *object_id* came to, and queue its waiters.

    A fetched ``STORE`` object is stored and its record removed; a fetched
    ``HAND_OFF`` object is kept on the record for its waiters.  A failed
    fetch, or a body that is not the object asked for, is logged at
    WARNING and the record marked ``FAILED`` (AKM-05-008).  Each waiter
    that waits on no other open fetch is queued for its replay.  All of it
    commits together.

    Returns:
        The activity ids queued for replay.
    """
    with dl.transaction():
        fetch = _fetch_record(dl, object_id)
        if fetch is None or fetch.state is not ObjectFetchState.PENDING:
            return []
        attempts = fetch.attempts + result.attempts
        failure = result.failure
        fetched: CoreObject | as_Base | None = None
        if result.body is not None:
            try:
                fetched = parse_fetched_object(result.body, object_id)
            except VultronError as exc:
                failure = str(exc)
        if fetched is None:
            reason = failure or "the fetch returned nothing"
            logger.warning(
                "Fetch of '%s' from %s for actor_id=%s failed after %d"
                " attempt(s): %s; waiting activities %s go on without it"
                " (AKM-05-008)",
                object_id,
                fetch.host_actor_id,
                actor_id,
                attempts,
                reason,
                fetch.waiting_activity_ids,
            )
            dl.save(
                fetch.model_copy(
                    update={
                        "state": ObjectFetchState.FAILED,
                        "attempts": attempts,
                        "failure_reason": reason,
                    }
                )
            )
        elif fetch.use is ObjectFetchUse.STORE:
            _store_fetched(dl, fetch, fetched)
            dl.delete(fetch.type_, fetch.id_)
        else:
            dl.save(
                fetch.model_copy(
                    update={
                        "state": ObjectFetchState.FETCHED,
                        "attempts": attempts,
                        "fetched_body": json.dumps(result.body),
                    }
                )
            )
        return _queue_ready_waiters(dl, fetch.waiting_activity_ids)


def _queue_ready_waiters(dl: DataLayer, waiters: list[str]) -> list[str]:
    """Queue each waiter that waits on no other open fetch."""
    still_waiting = {
        waiter
        for record in open_fetches(dl)
        for waiter in record.waiting_activity_ids
    }
    replay = InboxReplayAdapter(dl)
    queued: list[str] = []
    for waiter in waiters:
        if waiter in still_waiting:
            continue
        try:
            replay.replay_held(waiter)
        except VultronWiringError:
            # Nothing holds it, so there is nothing to replay; the record of
            # the fetch it waited on is settled all the same.
            logger.exception(
                "Activity %s waited on a fetch but is not held for its"
                " replay (DL-06-006)",
                waiter,
            )
            continue
        queued.append(waiter)
    return queued


__all__ = [
    "FastAPIDereferencePort",
    "open_fetches",
    "parse_fetched_object",
    "settle_fetch",
]
