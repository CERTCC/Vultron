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

"""Reads of, and waits on, what an actor stored or received.

A received activity is read from the record intake made, kept under the
receiver's key (CLP-10-036, ADR-0111), never from a row under the sender's
id (DL-06-006).
"""

import logging

from vultron.demo.helpers.polling._poll import (
    CROSS_CONTAINER_TIMEOUT,
    _poll_datalayer_for,
    _poll_until,
)
from vultron.demo.utils import (
    RECEIVED_ACTIVITY_RECORD_TYPE,
    DataLayerClient,
    logfmt,
    not_received_error,
    read_received_activity,
    received_activity_in,
)

logger = logging.getLogger(__name__)


#: The stored type a received activity is read from: the record intake made,
#: kept under the receiver's key (CLP-10-036, ADR-0111).  A row of an activity
#: type under the sender's id is never read as a received one (DL-06-006).
_RECEIVED_ACTIVITY_TYPES: tuple[str, ...] = (RECEIVED_ACTIVITY_RECORD_TYPE,)


def _received_activity_id(raw_id: str, obj_data: dict) -> str:
    """The sender's id for the received activity the record *obj_data* holds.

    The record is stored under the receiver's own id (*raw_id*) and names
    the activity's id inside.

    Raises:
        AssertionError: when the record's activity carries no id.
    """
    activity_id = received_activity_in(obj_data).get("id")
    if not activity_id:
        raise AssertionError(
            f"received-activity record {raw_id!r} holds an activity with no id"
        )
    return str(activity_id)


def _ref_id(value: object) -> object:
    """The id a wire field names: an inline object's ``id``, else the value.

    An activity's ``actor``, ``object`` and ``target`` each carry either an
    inline object or its id (DL-08-003).
    """
    return value.get("id") if isinstance(value, dict) else value


def read_received_activity_for(
    client: DataLayerClient, activity_id: str
) -> dict:
    """The activity *activity_id* as the actor behind *client* received it.

    Reads the record intake made (:func:`read_received_activity`), the only
    copy of a received activity the actor keeps (DL-06-006).

    Raises:
        AssertionError: If the actor holds no activity *activity_id*.
    """
    activity = read_received_activity(client, activity_id)
    if activity is None:
        raise not_received_error(client, activity_id)
    return activity


def assert_received_from(
    client: DataLayerClient,
    activity_id: str,
    sender_id: str,
    consequence: str,
) -> None:
    """Assert the actor behind *client* received *activity_id* from *sender_id*.

    Args:
        client: DataLayerClient for the receiving actor's container.
        activity_id: The sender's id for the received activity.
        sender_id: The actor the activity must have been emitted as.
        consequence: What goes wrong when it was not, for the failure message.

    Raises:
        AssertionError: If the activity is not held, or another actor sent it.
    """
    emitted_as = _ref_id(
        read_received_activity_for(client, activity_id).get("actor")
    )
    assert emitted_as == sender_id, (
        f"'{activity_id}' was emitted as '{emitted_as}', not as"
        f" '{sender_id}' — {consequence}"
    )


def wait_for_object_stored(
    client: DataLayerClient,
    obj_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
    actor_id: str | None = None,
) -> None:
    """Poll *client*'s DataLayer until *obj_id* appears.

    For an object the actor stores under its own id.  An activity the actor
    *received* is not one: it is held in the receiver's archive record, never
    under the sender's id (DL-06-006), so wait on it with
    :func:`wait_for_received_activity`.

    .. warning::
        **Only valid when the recipient stores the same object ID.**  When the
        receiving actor creates a *new* derived object in response (the
        propose-then-execute pattern — e.g.
        ``ProposeCaseOwnershipTransferReceivedUseCase`` making the Offer from
        the owner's proposal), the original *obj_id* will never
        appear in the recipient's DataLayer.  Use
        :func:`find_ownership_transfer_offer_for_actor` or a similar semantic
        scan in those cases.  See EDF-06-004 and issue #2178.

    Args:
        client: DataLayerClient connected to the container to poll.
        obj_id: Full URI of the object to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.
        actor_id: Whose store to poll.  Defaults to *client*'s own actor;
            name the recipient when it is not the actor *client* is bound to
            (ADR-0073).

    Raises:
        AssertionError: If *obj_id* does not appear within *timeout_seconds*.

    Spec: EDF-06-004.
    """

    def _check() -> bool:
        try:
            data = client.get(client.dl_path(obj_id, actor_id=actor_id))
            if data:
                logger.info(
                    "Object %s found in DataLayer at %s",
                    logfmt(obj_id),
                    client.base_url,
                )
                return True
        except Exception:  # noqa: BLE001, S110  # ruff-baseline #3326
            pass
        return False

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for object {obj_id!r} to appear in DataLayer "
        f"at {client.base_url} — outbox delivery may not have completed",
        swallow_exceptions=True,
    )


def wait_for_received_activity(
    client: DataLayerClient,
    activity_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
    actor_id: str | None = None,
) -> None:
    """Poll the receiver's store until it has archived *activity_id*.

    The gate for "the receiver took in this delivery": intake records every
    activity its doors admit as a ``ReceivedActivityRecord`` under the receiver's
    key (CLP-10-036, ADR-0111), and that record is the only place a received
    activity is read from (DL-06-006), so the wait is on it rather than on a
    row under the sender's id (EDF-06-002).

    Args:
        client: DataLayerClient connected to the receiver's container.
        activity_id: The sender's id for the activity.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between poll attempts.
        actor_id: Whose store to poll.  Defaults to *client*'s own actor;
            name the recipient when it is not the actor *client* is bound to
            (ADR-0073).

    Raises:
        AssertionError: If the activity is not archived within
            *timeout_seconds*.
    """
    _poll_until(
        lambda: (
            read_received_activity(client, activity_id, actor_id=actor_id)
            is not None
        ),
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for {actor_id or client.actor_id!r} at"
        f" {client.base_url} to archive received activity {activity_id!r} —"
        " outbox delivery may not have completed",
        swallow_exceptions=True,
    )


def wait_for_report_submission_stored(
    client: DataLayerClient,
    receiver_id: str,
    report_id: str,
    offer_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll the receiver's own store until a submitted report and its Offer land.

    The reporter's ``submit-report`` trigger delivers the ``Offer`` through its
    outbox, so the receiver stores the report and the Offer when its inbox has
    processed that delivery -- after the trigger returns, not before.  This
    gates on that stored effect (EDF-06-002, EDF-06-003, DEMOMA-22-002) rather
    than on anything the demo itself delivered.

    Both reads name *receiver_id* explicitly (ADR-0073), so the result does not
    depend on *client*'s own binding.

    Args:
        client: DataLayerClient connected to the receiver's container.
        receiver_id: Actor id whose store to read.
        report_id: Id of the submitted ``VulnerabilityReport``.
        offer_id: Id of the submit-report ``Offer``.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between poll attempts.

    Raises:
        AssertionError: If either object is still absent at the deadline.
    """
    missing: set[str] = {report_id, offer_id}

    def _stored(obj_id: str) -> bool:
        # The Offer is a received activity, read from the receiver's archive
        # record (DL-06-006); the report it carried is stored under its own id.
        if obj_id == offer_id:
            return (
                read_received_activity(client, offer_id, actor_id=receiver_id)
                is not None
            )
        return bool(client.get(client.dl_path(obj_id, actor_id=receiver_id)))

    def _check() -> bool:
        for obj_id in sorted(missing):
            try:
                if _stored(obj_id):
                    missing.discard(obj_id)
            except Exception:  # noqa: BLE001, S110
                pass
        return not missing

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for the submitted report/offer in {receiver_id!r}'s"
        f" DataLayer at {client.base_url} — the reporter's outbox delivery may"
        " not have completed",
        swallow_exceptions=True,
    )


def wait_for_reporter_introduction(
    client: DataLayerClient,
    reporter_id: str,
    receiver_id: str,
    report_id: str,
    case_id: str | None = None,
    timeout_seconds: float = CROSS_CONTAINER_TIMEOUT,
    poll_interval: float = 0.5,
) -> str:
    """Poll the reporter's store until its report's link is bound by the receiver.

    The reporter's ``submit-report`` trigger writes a pending
    ``ReportCaseLink`` that names the actor it sent the report to
    (CBT-01-005).  The receiver's ``Create(VulnerabilityCase)`` introduction
    binds that link to the case only on the trusted route, and records the
    receiver as ``case_creator_id`` (CBT-01-001, CBT-01-006).  So a bound link
    naming *receiver_id* is the committed effect of a trusted introduction, read
    where it commits (EDF-06-002).  An introduction refused because no trust
    anchor names its sender (CBT-01-011) leaves no such link, and this wait
    times out.

    Args:
        client: DataLayerClient connected to the reporter's container.
        reporter_id: The report submitter, whose store is read (ADR-0073).
        receiver_id: The actor the report was submitted to.
        report_id: Id of the submitted ``VulnerabilityReport``.
        case_id: The case the link must be bound to, when the caller knows
            which case the receiver opened for the report.  ``None`` accepts
            a link bound to any case.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between poll attempts.

    Returns:
        The id of the case the reporter's link is bound to.

    Raises:
        AssertionError: If no bound link naming *receiver_id* (and bound to
            *case_id*, when given) appears in time.
    """

    def _bound_by_receiver(link: dict) -> bool:
        bound_to = link.get("case_id")
        return (
            link.get("report_id") == report_id
            and link.get("case_creator_id") == receiver_id
            and bool(bound_to)
            and (case_id is None or bound_to == case_id)
        )

    return _poll_datalayer_for(
        client.model_copy(update={"actor_id": reporter_id}),
        ("ReportCaseLink",),
        _bound_by_receiver,
        timeout_seconds,
        poll_interval,
        log_msg=(
            f"Reporter {reporter_id!r} trusted {receiver_id!r}'s introduction"
            " of case %s"
        ),
        error_msg=(
            f"Timed out waiting for {reporter_id!r}'s ReportCaseLink for report"
            f" {report_id!r} to be bound by {receiver_id!r}'s introduction"
            + (f" of case {case_id!r}" if case_id is not None else "")
            + " —"
            " the report did not go through the reporter's submit-report"
            " trigger, or the introduction was refused (CBT-01-011)"
        ),
        id_fn=lambda _raw_id, link: str(link["case_id"]),
    )
