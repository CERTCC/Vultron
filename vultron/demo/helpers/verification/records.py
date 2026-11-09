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

"""Activity receipt, the receiver's final case state and CaseActor records."""

import logging

import httpx2 as httpx

from vultron.adapters.utils import parse_id
from vultron.demo.helpers.verification.participants import (
    _fetch_participant,
    _require_case_participant_id,
)
from vultron.demo.helpers.verification.states import (
    _assert_case_notes,
    _assert_vendor_case_status,
    _assert_vendor_participant_state,
)
from vultron.demo.utils import (
    DataLayerClient,
    read_received_activity,
    ref_id,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def recipient_ids(to: object) -> list[str]:
    """The actor ids an activity's ``to`` names, in order.

    AS2 allows ``to`` to be one recipient or a list, and each recipient a bare
    id, an inline wire dict, or a typed object; every shape is read the same.
    """
    recipients = to if isinstance(to, list) else [] if to is None else [to]
    ids = [
        r.get("id") if isinstance(r, dict) else ref_id(r) for r in recipients
    ]
    return [i for i in ids if isinstance(i, str)]


def verify_activity_in_inbox(
    client: DataLayerClient,
    actor_id: str,
    activity_id: str,
) -> bool:
    """Check whether *activity_id* was received and stored by the actor.

    Checks the actor's store directly for the activity — the authoritative
    approach for exchange-demo tests.  Intake records every activity its
    doors admit as a ``ReceivedActivityRecord`` under a key the receiver derives
    from the activity's id (CLP-10-017, ADR-0111), so that record confirms
    receipt; a row under the sender's id never does (DL-06-006).  The inbox
    path itself has no read surface
    (IE-02-004): receipt is verified through the actor's store, which is what
    the datalayer client reads here.

    Args:
        client: DataLayerClient for the target container.
        actor_id: Full URI of the actor whose inbox to check.  This *selects the
            store* read: an activity delivered to one actor is absent from every
            other actor's store (CM-01-001), so a lookup by id alone has no
            answer.  It was logging-only when a container had a single shared
            store, which made "not in the reporter's inbox" report on whichever
            actor the client happened to be bound to.
        activity_id: Full URI of the activity to find.

    Returns:
        ``True`` if found; ``False`` otherwise.
    """
    actor_obj_id = parse_id(actor_id)["object_id"]
    try:
        received = (
            read_received_activity(client, activity_id, actor_id) is not None
        )
    except (httpx.HTTPStatusError, AssertionError):
        # Only a transport/HTTP "not there" answer means "not received".  A bare
        # ``except Exception`` here would report a programming error — an unbound
        # client, a bad key — as a protocol failure, which is how the
        # ``dl_path`` ValueError stayed invisible for a whole CI cycle.
        received = False
    if not received:
        logger.warning(
            "Activity %s not found in DataLayer (actor %s)",
            activity_id,
            actor_obj_id,
        )
        return False
    logger.info(
        "✓ Activity %s found in DataLayer (actor %s)",
        activity_id,
        actor_obj_id,
    )
    return True


def verify_receiver_case_state(
    receiver_client: DataLayerClient,
    case_id: str,
    report_id: str,
    receiver_actor_id: str,
    reporter_actor_id: str,
    question_note_id: str | None = None,
    reply_note_id: str | None = None,
) -> as_VulnerabilityCase:
    """Assert the final authoritative case state on the receiver container.

    Verifies that the case references the submitted report, that all required
    participants are present (receiver, reporter, plus at least one Case
    Actor), and that the receiver participant has reached ``RM.ACCEPTED``
    with ``EM.ACTIVE`` and ``pxa == CS_pxa.pxa``.  Optionally checks that
    *question_note_id* and *reply_note_id* appear in the case notes; a thread
    needs both halves, so pass both ids or neither (one alone raises).

    Args:
        receiver_client: Client connected to the receiver container.
        case_id: Full URI of the ``as_VulnerabilityCase`` to verify.
        report_id: Full URI of the submitted vulnerability report.
        receiver_actor_id: Full URI of the receiver actor.
        reporter_actor_id: Full URI of the reporter actor.
        question_note_id: URI of the question note to assert present; give it
            together with *reply_note_id* or not at all.
        reply_note_id: URI of the reply note to assert present; give it
            together with *question_note_id* or not at all.

    Returns:
        The fetched and validated ``as_VulnerabilityCase``.

    Raises:
        AssertionError: If any invariant is violated, or exactly one note id
            is given.
    """
    final_case = as_VulnerabilityCase(
        **receiver_client.get(receiver_client.dl_path(case_id))
    )

    # Verify required participants are present by ID rather than a raw count,
    # so future changes to the participant set don't silently break CI.
    required_ids = {receiver_actor_id, reporter_actor_id}
    missing = required_ids - set(final_case.actor_participant_index.keys())
    if missing:
        raise AssertionError(
            f"Required participants missing from case: {missing}"
        )
    # At least one Case Actor must be present beyond receiver and reporter.
    other_actors = (
        set(final_case.actor_participant_index.keys()) - required_ids
    )
    if not other_actors:
        raise AssertionError(
            "Expected at least one Case Actor participant in addition to"
            " receiver and reporter"
        )

    report_ids = [
        ref_id(report) or str(report)
        for report in final_case.vulnerability_reports
    ]
    if report_id not in report_ids:
        raise AssertionError(
            "Final case does not reference the submitted report"
        )

    receiver_participant_id = _require_case_participant_id(
        final_case,
        receiver_actor_id,
        "Coordinator",
    )
    _require_case_participant_id(final_case, reporter_actor_id, "Reporter")
    _assert_vendor_participant_state(receiver_client, receiver_participant_id)

    _assert_vendor_case_status(final_case)
    _assert_case_notes(final_case, question_note_id, reply_note_id)
    return final_case


def verify_case_actor_holds_records(
    case_actor_client: DataLayerClient,
    case_id: str,
) -> as_VulnerabilityCase:
    """Verify the dedicated case-actor container holds the canonical case.

    Every actor container proposes its cases to the dedicated case-actor
    container (CP-08-008, DEMOMA-06-004), so the ``VulnerabilityCase`` the
    CaseActor accepted the proposal for must be in that container's CaseActor
    store, with the CaseActor itself as a participant holding
    ``CVDRole.CASE_MANAGER``.  The CaseActor *is* that participant (#1872); no
    separate CaseActor service record is asserted.

    A case found only on the report receiver's container would mean the receiver
    created it locally — the co-located shortcut this topology retires.

    Args:
        case_actor_client: Client connected to the dedicated case-actor
            container, bound to its CaseActor (see
            :func:`~vultron.demo.utils.case_actor_id_on`), since the read is
            per-actor under ADR-0073.
        case_id: Full URI of the case the CaseActor should hold.

    Returns:
        The case as the CaseActor holds it.

    Raises:
        AssertionError: If the case is absent from the CaseActor's store, or the
            CaseActor is not a ``CASE_MANAGER`` participant in it.
        ValueError: If *case_actor_client* is not bound to an actor.
    """
    case_actor_id = case_actor_client.actor_id
    if not case_actor_id:
        raise ValueError(
            "verify_case_actor_holds_records needs a client bound to the"
            " CaseActor: DataLayer reads are per-actor (ADR-0073)"
        )
    try:
        case_data = case_actor_client.get(case_actor_client.dl_path(case_id))
    except httpx.HTTPStatusError as exc:
        # Only a 404 means "absent"; any other status is a different fault and
        # must not be reported as a proposal handled elsewhere.
        if exc.response.status_code != httpx.codes.NOT_FOUND:
            raise
        raise AssertionError(
            f"Dedicated case-actor container ({case_actor_client.base_url})"
            f" does not hold case {case_id!r} in CaseActor {case_actor_id}'s"
            " store: the proposal was not handled there (DEMOMA-06-008)"
        ) from exc
    case = as_VulnerabilityCase.model_validate(case_data)
    participant = _fetch_participant(case_actor_client, case_id, case_actor_id)
    if participant is None:
        raise AssertionError(
            f"CaseActor {case_actor_id} is not a participant in its own copy"
            f" of case {case_id!r}"
        )
    if CVDRole.CASE_MANAGER not in participant.case_roles:
        raise AssertionError(
            f"CaseActor {case_actor_id} participates in case {case_id!r} with"
            f" roles {participant.case_roles}, not CASE_MANAGER"
        )
    logger.info(
        "Dedicated case-actor container holds case %s with CaseActor %s as"
        " CASE_MANAGER",
        case_id,
        case_actor_id,
    )
    return case
