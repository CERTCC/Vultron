"""Posting to inboxes and triggers, and reading back what an actor stored."""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import json
import logging
import time
from collections.abc import Sequence

import httpx2 as httpx

from vultron.adapters.utils import parse_id
from vultron.core.models._helpers import _as_id
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.sender_sequence import SenderSequenceOrder
from vultron.demo.utils.client import DataLayerClient, logfmt, postfmt
from vultron.primitives import same_actor_id
from vultron.wire.as2.factories import (
    ledger_position_case_ids,
    sender_sequence_case_ids,
    stamp_ledger_position,
    stamp_sender_sequence,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.base import as_Object

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


# Default wait time (seconds) after posting to an inbox, to allow background
# tasks to complete before checking state. Set to 0 in test environments.
DEFAULT_WAIT_SECONDS: float = 1.0


def _receivers_case_position(
    client: DataLayerClient, actor_id: str, case_id: str
) -> LedgerPosition | None:
    """The ledger position of *actor_id*'s copy of *case_id*, if it holds one.

    Every stored case names the position its case file reflects
    (SYNC-16-005).  ``None`` when the store holds nothing under *case_id*, or
    something other than a case.
    """
    try:
        stored = client.get(client.dl_path(case_id, actor_id=actor_id))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    if (
        not isinstance(stored, dict)
        or stored.get("type") != "VulnerabilityCase"
    ):
        return None
    # The DataLayer route renders the stored record by alias.
    position = stored.get("ledgerPosition")
    return LedgerPosition.model_validate(position) if position else None


def _stamped_as_in_step(
    client: DataLayerClient, actor_id: str, activity: as_Activity
) -> as_Activity:
    """*activity* stating a ledger position, as its sender's adapter stamps it.

    An exchange demo posts a factory-built activity straight to an actor's
    inbox in place of a peer.  A peer that holds the case states its ledger
    tail on every case activity, and the receiver refuses one that states
    none (SYNC-18-001, SYNC-18-015).  The demo stands in for a peer in step
    with the receiver, so it states the position of the receiver's own copy
    of the case.  An activity naming no case the receiver holds is posted as
    it is.
    """
    for case_id in ledger_position_case_ids(activity):
        position = _receivers_case_position(client, actor_id, case_id)
        if position is not None:
            return stamp_ledger_position(activity, position)
    return activity


def _receivers_next_sender_sequence(
    client: DataLayerClient, actor_id: str, case_id: str, sender_id: str
) -> int:
    """The ``senderSequence`` *actor_id* expects next from *sender_id*.

    The receiver's order record for the sender on *case_id* names it
    (SYNC-21-009).  A receiver that has judged none of the sender's numbers
    keeps no record, so the next number is 1: a CASE_MANAGER saves the
    record with the first number it judges.  A receiver that is not the
    case's CASE_MANAGER keeps none either, and reads no number (SYNC-21-001).
    """
    stored = client.get(client.dl_path("SenderSequenceOrders/", actor_id))
    record = (
        stored.get(SenderSequenceOrder.build_id(case_id, sender_id))
        if isinstance(stored, dict)
        else None
    )
    if record is None:
        return 1
    return SenderSequenceOrder.model_validate(record).next_expected


def _numbered_as_in_step(
    client: DataLayerClient, actor_id: str, activity: as_Activity
) -> as_Activity:
    """*activity* numbered as its sender's adapter numbers it, in step.

    A participant numbers each case activity it sends the CASE_MANAGER that
    states a ledger position, and the CASE_MANAGER refuses one that carries
    no number (SYNC-21-001, SYNC-21-017).  The demo stands in for a peer in
    step with the receiver, so it gives the number the receiver expects
    next from the sender: the activity is judged on arrival, as a peer's
    next activity is.  An activity that takes no number (a ledger request,
    or one stating no position), one already numbered, and one the receiver
    sends itself are posted as they are, as is one naming no case the
    receiver holds.
    """
    sender = _as_id(activity.actor)
    if (
        activity.sender_sequence is not None
        or sender is None
        or same_actor_id(sender, actor_id)
    ):
        return activity
    # The activity may name its case through its object (a participant, a
    # proposal): the case is the first one named that the receiver holds,
    # as for the ledger position.
    for case_id in sender_sequence_case_ids(activity):
        if _receivers_case_position(client, actor_id, case_id) is not None:
            number = _receivers_next_sender_sequence(
                client, actor_id, case_id, sender
            )
            return stamp_sender_sequence(activity, number)
    return activity


def post_to_inbox_and_wait(
    client: DataLayerClient,
    actor_id: str,
    activity: as_Activity,
    wait_seconds: float | None = None,
) -> None:
    """POST an activity to an actor's inbox and pause to let background tasks complete.

    Args:
        client: DataLayerClient instance.
        actor_id: ID of the target actor.
        activity: ActivityStreams activity to deliver.
        wait_seconds: Seconds to sleep after posting; defaults to ``DEFAULT_WAIT_SECONDS``.
    """
    activity = _numbered_as_in_step(
        client, actor_id, _stamped_as_in_step(client, actor_id, activity)
    )
    actor_obj_id = parse_id(actor_id)["object_id"]
    logger.debug(
        "Posting activity to %s's inbox: %s", actor_obj_id, logfmt(activity)
    )
    client.post(f"/actors/{actor_obj_id}/inbox/", json=postfmt(activity))
    delay = DEFAULT_WAIT_SECONDS if wait_seconds is None else wait_seconds
    time.sleep(
        delay
    )  # temporal: liveness probe — give BackgroundTasks time to process (EDF-06-006)


def post_to_trigger(
    client: DataLayerClient,
    actor_id: str,
    behavior: str,
    body: dict,
    path_prefix: str = "trigger",
) -> dict:
    """POST to a trigger endpoint and return the response body.
    proactively (e.g. validate-report, engage-case) rather than
    reacting to an inbound activity.

    Args:
        client: DataLayerClient instance.
        actor_id: Full URI of the actor initiating the behavior.
        behavior: Kebab-case behavior name (e.g. ``"validate-report"``).
        body: Request body dict (e.g. ``{"offer_id": "..."}``).
        path_prefix: URL segment before the behavior name.  Use
            ``"trigger"`` (default) for standard trigger endpoints and
            ``"demo"`` for demo-only endpoints such as
            ``add-note-to-case`` and ``sync-log-entry``.

    Returns:
        Response dict from the trigger endpoint.

    The ``(client, actor_id)`` pairing is no longer checked here: demo callers
    reach this through :class:`vultron.demo.actor_session.ActorSession`, which
    verifies that the client's container hosts the actor once at construction
    (DEMOMA-26-008).  ``post_to_trigger`` MUST NOT be called directly outside
    this module and ``actor_session`` (DEMOMA-26-001).
    """
    actor_obj_id = parse_id(actor_id)["object_id"]
    logger.info(
        "Posting trigger '%s' for actor '%s': %s",
        behavior,
        actor_obj_id,
        body,
    )
    return client.post(
        f"/actors/{actor_obj_id}/{path_prefix}/{behavior}", json=body
    )


def verify_object_stored(
    client: DataLayerClient, obj_id: str, actor_id: str | None = None
) -> as_Object:
    """Fetch an object from the DataLayer by ID and verify it is present.

    Logs the stored representation so all fields are visible. Nested objects
    are stored as ID-string references (not inline copies); the log therefore
    shows ID strings for nested fields such as ``object_``, ``target``, etc.
    To inspect a nested object, call ``verify_object_stored`` again with the
    nested object's own ID.

    Args:
        client: DataLayerClient for the container to read from.
        obj_id: Id of the object to fetch.
        actor_id: Whose replica to look in.  Defaults to *client*'s own actor.
            "Is this object stored?" has no answer under ADR-0073 without naming
            an actor, so pass this whenever the read is about an actor other than
            the one the client is bound to — typically because the activity was
            delivered to a different recipient's inbox.

    Returns:
        The retrieved ``as_Object``.

    Raises:
        httpx.HTTPStatusError: If the object is not found.
    """

    def _drop_nulls(value: object) -> object:
        if isinstance(value, dict):
            return {
                k: _drop_nulls(v) for k, v in value.items() if v is not None
            }
        if isinstance(value, list):
            return [_drop_nulls(item) for item in value]
        return value

    obj = client.get(client.dl_path(obj_id, actor_id=actor_id))
    filtered = _drop_nulls(obj)
    logger.info(
        "Stored record (nested objects shown as ID references): %s",
        json.dumps(filtered, indent=2, default=str),
    )
    return as_Object(**obj)


def read_stored_of_types(
    client: DataLayerClient,
    types: Sequence[str],
    actor_id: str | None = None,
) -> dict:
    """The actor's stored objects of *types*, keyed by id, as the store serves them.

    One read of the type-filtered store route: a poll never dumps the whole
    store, whose rehydration slowed the container being polled as it grew
    (#4600).  A reply that is not a mapping reads as holding nothing.

    Args:
        client: DataLayerClient for the actor's container.
        types: The stored types to read.
        actor_id: Whose store to read.  Defaults to *client*'s own actor.
    """
    objects = client.get(
        client.dl_path(actor_id=actor_id), params={"type": list(types)}
    )
    return objects if isinstance(objects, dict) else {}
