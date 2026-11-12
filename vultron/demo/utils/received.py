"""Reading received-activity records, offers and case state from an actor's store."""

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

from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.demo.utils.client import DataLayerClient, logfmt
from vultron.demo.utils.inbox import read_stored_of_types
from vultron.demo.utils.served import from_server
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


#: The stored type a received activity is read from: intake's record of
#: the body that arrived, kept under a key the receiver derives (CLP-10-036,
#: ADR-0149).  A row of an
#: activity type under its own id is one the actor authored, never one it
#: received (DL-06-006).
RECEIVED_ACTIVITY_RECORD_TYPE = ReceivedActivityRecord.__name__


def received_activity_or_none(record: dict) -> dict | None:
    """The activity a served record holds, or ``None`` for a receipt stub.

    A refused message leaves a stub with no body (CLP-10-018), so there is no
    activity in it to read.  Use this where a sweep or a predicate runs over
    every one of an actor's received records; use
    :func:`received_activity_in` where the record is known to hold a body and
    its absence is a fault.
    """
    if not isinstance(record.get("received_body"), str):
        return None
    return received_activity_in(record)


def received_activity_in(record: dict) -> dict:
    """The activity a served ``ReceivedActivityRecord`` *record* archives.

    The record keeps the body that arrived, as JSON text (CLP-10-036,
    ADR-0149), so the activity is that body decoded: its sender's own wire
    form.

    Raises:
        AssertionError: when the record holds no JSON object body.
    """
    body = record.get("received_body")
    activity = json.loads(body) if isinstance(body, str) else None
    if not isinstance(activity, dict):
        raise AssertionError(  # noqa: TRY004 — demo_check assertion, not a type error
            f"received-activity record {record.get('id')!r} holds no"
            f" received body: {body!r}"
        )
    return activity


def served_field(obj: dict, wire_key: str, field_name: str) -> object:
    """*obj*'s field served as *wire_key* or, failing that, as *field_name*.

    The store route serves a stored object under one of two shapes: an AS2
    object's fields under their wire (camelCase) names, a bare core record's
    under their field names (``attributed_to``), so a reader that may get
    either shape reads both.  The wire name wins when both are present.
    """
    return obj[wire_key] if wire_key in obj else obj.get(field_name)


def _received_activity_records(
    client: DataLayerClient, actor_id: str | None
) -> dict:
    """The actor's ``ReceivedActivityRecord`` rows, keyed by record id."""
    return read_stored_of_types(
        client, [RECEIVED_ACTIVITY_RECORD_TYPE], actor_id=actor_id
    )


def read_received_record(
    client: DataLayerClient, activity_id: str, actor_id: str | None = None
) -> dict | None:
    """The receiver's ``ReceivedActivityRecord`` for *activity_id*, as served.

    The whole record, not only the activity it holds: its ``stage`` and the
    ``verified_proofs`` the inbox recorded on receipt (SIG-03-004).  Looked
    up by the key the receiver derives from the sender's id
    (:meth:`ReceivedActivityRecord.build_id`, DL-06-006); ``None`` when the
    receiver holds no record of it.

    Args:
        client: DataLayerClient for the receiving actor's container.
        activity_id: The sender's id for the activity.
        actor_id: Whose store to read.  Defaults to *client*'s own actor.
    """
    record = _received_activity_records(client, actor_id).get(
        ReceivedActivityRecord.build_id(activity_id)
    )
    return record if isinstance(record, dict) else None


def read_received_activity(
    client: DataLayerClient, activity_id: str, actor_id: str | None = None
) -> dict | None:
    """The activity *activity_id* as the receiving actor archived it, or ``None``.

    Reads the actor's ``ReceivedActivityRecord`` rows only and looks the record
    up by the key the receiver derives from the sender's id
    (:meth:`ReceivedActivityRecord.build_id`).  A row stored under the sender's
    id is never read: a receiver holds no received activity under the
    sender's id (DL-06-006).

    Unlike the core
    :func:`~vultron.core.use_cases._helpers.read_received_activity`, which
    falls back to the record holding an activity the inbox deferred and
    raises when nothing is held, this reads the archive only and returns
    ``None``.

    Args:
        client: DataLayerClient for the receiving actor's container.
        activity_id: The sender's id for the activity.
        actor_id: Whose store to read.  Defaults to *client*'s own actor.

    Raises:
        AssertionError: when the record found wraps no activity.
    """
    record = read_received_record(client, activity_id, actor_id)
    if record is None:
        return None
    # A receipt stub is what the actor kept of a message it refused: it holds
    # no activity, so the actor received none that a reader can have
    # (CLP-10-018).
    return received_activity_or_none(record)


def not_received_error(
    client: DataLayerClient,
    activity_id: str,
    actor_id: str | None = None,
    what: str = "activity",
) -> AssertionError:
    """The failure for an actor that holds no received *what* *activity_id*."""
    return AssertionError(
        f"{actor_id or client.actor_id!r} at {client.base_url} holds no"
        f" received {what} {activity_id!r}"
    )


def require_received_activity(
    client: DataLayerClient,
    activity_id: str,
    actor_id: str | None = None,
    what: str = "activity",
) -> dict:
    """The activity *activity_id* the actor received, as archived.

    :func:`read_received_activity`, failing when nothing is archived.

    Args:
        client: DataLayerClient for the receiving actor's container.
        activity_id: The sender's id for the activity.
        actor_id: Whose store to read.  Defaults to *client*'s own actor.
        what: What the activity is, for the failure message.

    Raises:
        AssertionError: If the actor holds no received activity *activity_id*.
    """
    activity = read_received_activity(client, activity_id, actor_id)
    if activity is None:
        raise not_received_error(client, activity_id, actor_id, what)
    return activity


def read_received_activities(
    client: DataLayerClient, activity_type: str, actor_id: str | None = None
) -> list[dict]:
    """Every *activity_type* activity the actor received, as archived.

    Read from the actor's ``ReceivedActivityRecord`` rows only, as
    :func:`read_received_activity` reads one.

    Args:
        client: DataLayerClient for the receiving actor's container.
        activity_type: The wire ``type`` of the activities wanted, e.g.
            ``"Accept"``.
        actor_id: Whose store to read.  Defaults to *client*'s own actor.

    Raises:
        AssertionError: when a record found wraps no activity.
    """
    activities = (
        received_activity_or_none(record)
        for record in _received_activity_records(client, actor_id).values()
        if isinstance(record, dict)
    )
    return [
        a
        for a in activities
        if a is not None and a.get("type") == activity_type
    ]


def verify_received_activity_stored(
    client: DataLayerClient, activity_id: str, actor_id: str | None = None
) -> dict:
    """Verify the receiving actor archived *activity_id*, and log it.

    The received-activity counterpart of :func:`verify_object_stored`: an
    activity delivered to an actor's inbox is held in its archive record,
    never under the sender's id (DL-06-006).

    Args:
        client: DataLayerClient for the receiving actor's container.
        activity_id: The sender's id for the activity.
        actor_id: Whose store to read.  Defaults to *client*'s own actor.

    Returns:
        The archived activity, as the store serves it.

    Raises:
        AssertionError: If the actor holds no received activity *activity_id*.
    """
    activity = require_received_activity(client, activity_id, actor_id)
    logger.info(
        "Received activity archived: %s",
        json.dumps(activity, indent=2, default=str),
    )
    return activity


def get_offer_from_datalayer(
    client: DataLayerClient, vendor_id: str, offer_id: str
) -> as_Offer:
    """Retrieve an Offer the vendor received, from its DataLayer store.

    The Offer is read from the vendor's archive record for it
    (:func:`require_received_activity`): the vendor holds nothing under the
    sender's id (DL-06-006).

    Args:
        client: DataLayerClient instance.
        vendor_id: ID of the vendor actor that received the offer.  Names the
            store to read, so the lookup does not depend on *client*'s own
            binding.
        offer_id: ID of the offer to retrieve.

    Returns:
        The retrieved offer as :class:`as_Offer`.

    Raises:
        AssertionError: If the vendor holds no received Offer *offer_id*.
    """
    raw = from_server(
        as_Offer,
        require_received_activity(
            client, offer_id, actor_id=vendor_id, what="Offer"
        ),
    )
    logger.info("Retrieved Offer: %s", logfmt(raw))
    return raw


def log_case_state(
    client: DataLayerClient,
    case_id: str,
    label: str,
    actor_id: str | None = None,
) -> as_VulnerabilityCase | None:
    """Fetch and log the current state of a case.

    Args:
        client: DataLayerClient for the container to read from.
        case_id: Id of the case to read.
        label: Short description of the point in the flow, for the log line.
        actor_id: Whose replica to read.  Defaults to *client*'s own actor.
            Participants hold their own replicas of a case (PCR), so the state
            logged is always some named actor's view of it, never "the" state.
    """
    try:
        case_data = client.get(client.dl_path(case_id, actor_id=actor_id))
        case = from_server(as_VulnerabilityCase, case_data)
        logger.info(
            "Case state [%s]: reports=%s, participants=%s",
            label,
            len(case.vulnerability_reports),
            len(case.case_participants),
        )
        logger.debug("Case detail [%s]: %s", label, logfmt(case))
        return case
    except Exception as e:  # noqa: BLE001  # ruff-baseline #3326
        logger.warning("Could not fetch case state [%s]: %s", label, e)
        return None
