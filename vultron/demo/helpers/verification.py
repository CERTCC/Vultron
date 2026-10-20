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

"""Scenario-verification primitives shared across demo workflows.

Lower-level assertion helpers used by milestone verification functions in the
individual scenario modules (e.g. ``rv_demo.py``).  Keeping them here
avoids duplication when future multi-actor scenarios need the same checks.
"""

import logging

import httpx2 as httpx

from vultron.adapters.utils import parse_id
from vultron.core.models.dimensions import dimension_state
from vultron.core.models.participant_status import (
    participant_status_d_state,
    participant_status_vf_state,
)
from vultron.core.predicates.participants import all_participants_rm_closed
from vultron.core.states.cs import (
    CS_d,
    CS_pxa,
    CS_vf,
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
)
from vultron.core.states.em import is_em_embargo_active
from vultron.core.states.rm import RM
from vultron.demo.helpers.seeding import _dl_key
from vultron.demo.utils import (
    DataLayerClient,
    read_received_activity,
    ref_id,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
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


# ---------------------------------------------------------------------------
# Participant fetch helpers
# ---------------------------------------------------------------------------


def _fetch_participant(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    dl_actor_id: str | None = None,
) -> as_CaseParticipant | None:
    """Fetch the as_CaseParticipant record for *actor_id* in *case_id*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor whose participant record to fetch.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor.  Needed for a co-hosted CaseActor (the
            single-container exchange demos): it shares its owner's container
            but not its store
            (ADR-0073#peer-records-in-knowers-store), so reading the owner's
            replica reports the owner's view of a
            participant, not the CaseActor's authoritative one.

    Returns:
        The ``as_CaseParticipant`` or ``None`` if the actor or participant
        record is not found.
    """
    try:
        case_data = client.get(client.dl_path(case_id, actor_id=dl_actor_id))
        case = as_VulnerabilityCase.model_validate(case_data)
        participant_id = case.actor_participant_index.get(actor_id)
        if participant_id is None:
            return None
        p_data = client.get(
            client.dl_path(_dl_key(participant_id), actor_id=dl_actor_id)
        )
        return as_CaseParticipant(**p_data)
    except (httpx.HTTPStatusError, AssertionError):
        return None


def _fetch_participant_data(client: DataLayerClient, p_id: str) -> dict | None:
    """Fetch a participant record, returning ``None`` for genuine 404s.

    Re-raises for any non-404 error so failures are not silently swallowed.
    """
    try:
        return client.get(client.dl_path(_dl_key(p_id)))
    except httpx.HTTPStatusError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise
    except AssertionError as e:
        # TestClient compatibility: make_testclient_call raises AssertionError
        # for 4xx responses; treat only genuine 404s as "not found".
        if "404" in str(e):
            return None
        raise


# ---------------------------------------------------------------------------
# State-assertion helpers
# ---------------------------------------------------------------------------


def _require_case_participant_id(
    case: as_VulnerabilityCase,
    actor_id: str,
    label: str,
) -> str:
    """Return the participant ID for *actor_id* in *case* or raise.

    Args:
        case: The ``as_VulnerabilityCase`` whose index to check.
        actor_id: Full URI of the actor.
        label: Human-readable label for the ``AssertionError`` message.

    Returns:
        The participant ID string.

    Raises:
        AssertionError: If *actor_id* is missing from
            ``case.actor_participant_index``.
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        raise AssertionError(
            f"{label} actor is missing from actor_participant_index"
        )
    return participant_id


def _assert_vendor_participant_state(
    vendor_client: DataLayerClient,
    participant_id: str,
) -> None:
    """Assert that the vendor participant has reached ``RM.ACCEPTED``.

    Args:
        vendor_client: DataLayerClient connected to the Vendor container.
        participant_id: Full URI / DataLayer key of the participant record.

    Raises:
        AssertionError: If the participant has no statuses or the latest
            RM state is not ``RM.ACCEPTED``.
    """
    participant = as_CaseParticipant(
        **vendor_client.get(vendor_client.dl_path(_dl_key(participant_id)))
    )
    latest = participant.participant_status
    if latest is None:
        raise AssertionError("Vendor participant has no participant statuses")
    if latest.rm.state != RM.ACCEPTED:
        raise AssertionError(
            "Vendor participant RM state did not transition to ACCEPTED"
        )


def _assert_vendor_case_status(case: as_VulnerabilityCase) -> None:
    """Assert that *case* has ``EM.ACTIVE`` and ``pxa == CS_pxa.pxa``.

    Raises:
        AssertionError: If either invariant is violated.
    """
    if not is_em_embargo_active(case.em_state):
        raise AssertionError(
            f"Expected ACTIVE final EM state (default embargo activated at"
            f" case creation per EP-04-001), found {case.em_state}"
        )
    pxa = case.current_status.pxa.state
    if (
        is_pxa_public_aware(pxa)
        or is_pxa_exploit_public(pxa)
        or is_pxa_attacks_observed(pxa)
    ):
        raise AssertionError(f"Expected pxa final case state, found {pxa}")


def _assert_case_notes(
    case: as_VulnerabilityCase,
    question_note_id: str | None,
    reply_note_id: str | None,
) -> None:
    """Assert that *question_note_id* and *reply_note_id* are in *case.notes*.

    Both IDs are optional; the check is skipped when both are ``None``.

    Raises:
        AssertionError: If a provided note ID is missing from the case.
    """
    if question_note_id is None and reply_note_id is None:
        return

    note_ids = [ref_id(note) or str(note) for note in case.notes]
    if question_note_id is not None and question_note_id not in note_ids:
        raise AssertionError(
            f"Question note {question_note_id!r} not found in case notes"
        )
    if reply_note_id is not None and reply_note_id not in note_ids:
        raise AssertionError(
            f"Reply note {reply_note_id!r} not found in case notes"
        )


def _check_participant_rm_state_in(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set[RM]",
    label: str,
    dl_actor_id: str | None = None,
) -> None:
    """Assert actor's latest participant RM state is in *expected_states*.

    Used to enforce cross-state protocol invariants such as
    "CS.F entails RM in {ACCEPTED, DEFERRED, CLOSED}" — i.e. a participant
    that has a fix-ready or fix-deployed CS state must also have engaged with
    the case at the RM level.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of acceptable ``RM`` values.
        label: Human-readable label for ``AssertionError`` messages.
        dl_actor_id: When provided, read from this actor's store on *client*
            instead of the client's own default store.  Needed when the
            authoritative record is held by a co-hosted CaseActor rather
            than the container's primary actor (ADR-0073).
    """
    participant = _fetch_participant(
        client, case_id, actor_id, dl_actor_id=dl_actor_id
    )
    if participant is None:
        raise AssertionError(
            f"{label}: participant for actor '{actor_id}' not found"
        )
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"{label}: participant for actor '{actor_id}' has no participant"
            " statuses"
        )
    latest_rm = latest.rm.state
    if latest_rm not in expected_states:
        raise AssertionError(
            f"{label}: expected RM state in {expected_states!r}, "
            f"found {latest_rm!r}"
        )


def _check_participant_vf_state_in(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set[CS_vf]",
    label: str,
) -> None:
    """Assert actor's latest participant VF state is in *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of acceptable ``CS_vf`` values.
        label: Human-readable label for ``AssertionError`` messages.
    """
    participant = _fetch_participant(client, case_id, actor_id)
    if participant is None:
        raise AssertionError(
            f"{label}: participant for actor '{actor_id}' not found"
        )
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"{label}: participant for actor '{actor_id}' has no participant"
            " statuses"
        )
    latest_vf = participant_status_vf_state(latest)
    if latest_vf not in expected_states:
        raise AssertionError(
            f"{label}: expected VF state in {expected_states!r}, "
            f"found {latest_vf!r}"
        )


def _check_participant_d_state_in(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set[CS_d]",
    label: str,
) -> None:
    """Assert actor's latest participant D state is in *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of acceptable ``CS_d`` values.
        label: Human-readable label for ``AssertionError`` messages.
    """
    participant = _fetch_participant(client, case_id, actor_id)
    if participant is None:
        raise AssertionError(
            f"{label}: participant for actor '{actor_id}' not found"
        )
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"{label}: participant for actor '{actor_id}' has no participant"
            " statuses"
        )
    latest_d = participant_status_d_state(latest)
    if latest_d not in expected_states:
        raise AssertionError(
            f"{label}: expected D state in {expected_states!r}, "
            f"found {latest_d!r}"
        )


def _assert_participant_pxa_only(
    participant: as_CaseParticipant,
    label: str,
    actor_id: str,
) -> None:
    """Assert *participant* has a public-aware pxa_state (no VFD check).

    Used for non-vendor/non-deployer receivers (e.g. coordinators) whose
    vf/d state never advances (non-vendor/deployer) — only pxa is meaningful for them
    after a public-disclosure event (CSB-15-003).

    Raises:
        AssertionError: If pxa_state is not public-aware.
    """
    public_aware = {CS_pxa.Pxa, CS_pxa.PxA, CS_pxa.PXa, CS_pxa.PXA}
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"M6 {label}: participant {actor_id!r} has no statuses"
        )
    cs = getattr(latest, "case_status", None)
    pxa = dimension_state(cs, "pxa")
    if pxa not in public_aware:
        raise AssertionError(
            f"M6 {label}: pxa_state is not public-aware, found {pxa!r}"
        )


def _assert_participant_vf_pxa(
    participant: as_CaseParticipant,
    label: str,
    vendor_actor_id: str,
) -> None:
    """Assert *participant* has fix-ready (VF=VF) and a public-aware pxa_state.

    Both fix-ready-only and fix-deployed actors have vf.state == CS_vf.VF.

    Args:
        participant: The ``as_CaseParticipant`` to check.
        label: Human-readable label for ``AssertionError`` messages.
        vendor_actor_id: Full URI of the vendor actor (used in error messages).

    Raises:
        AssertionError: If the participant's vf.state is not CS_vf.VF or
            its pxa_state is not public-aware.
    """
    public_aware = {CS_pxa.Pxa, CS_pxa.PxA, CS_pxa.PXa, CS_pxa.PXA}
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"M6 {label}: participant {vendor_actor_id!r} has no statuses"
        )
    latest_vf = participant_status_vf_state(latest)
    if latest_vf != CS_vf.VF:
        raise AssertionError(
            f"M6 {label}: vfState is not VF (fix ready), found {latest_vf!r}"
        )
    cs = getattr(latest, "case_status", None)
    pxa = dimension_state(cs, "pxa")
    if pxa not in public_aware:
        raise AssertionError(
            f"M6 {label}: pxa_state is not public-aware, found {pxa!r}"
        )


def _all_fetchable_participants_rm_closed(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
) -> bool:
    """Return ``True`` when every fetchable participant is ``RM.CLOSED``.

    Participants on remote containers (fetch returns ``None``) are skipped
    since their state is not locally observable.  Convergence logic is
    delegated to
    :func:`~vultron.core.predicates.participants.all_participants_rm_closed`,
    which includes the CASE_MANAGER (ADR-0051, CM-23-005/CM-23-010) — this
    helper used to describe it as exempt, which is what let ISSUE-2505 stay
    invisible to every scenario's M7 check.

    Args:
        client: DataLayerClient for the container to query.
        case: The ``as_VulnerabilityCase`` whose participant index to walk.

    Returns:
        ``True`` if all locally-fetchable participants are ``RM.CLOSED``;
        ``False`` otherwise.
    """
    core_participants = []
    for p_id in case.actor_participant_index.values():
        p_data = _fetch_participant_data(client, p_id)
        if p_data is None:
            continue  # remote container — not fetchable here
        if not p_data:
            return False
        # No projection step: as_CaseParticipant *is* CaseParticipant
        # (ARCH-25-003, ADR-0099), so validating the fetched payload already yields the
        # core object ``all_participants_rm_closed`` expects.
        participant = as_CaseParticipant(**p_data)
        if not participant.joined:
            # Inert (never-joined) participants are excluded from the active-closure
            # check.  A rejected invitee's RM.CLOSED state is confirmed at the
            # point of rejection (M2 check); replica sync for inert records is
            # not guaranteed across containers (ADR-0114, CM-11-007).
            continue
        core_participants.append(participant)
    if not core_participants:
        # No locally-fetchable participants — cannot confirm closure.
        return False
    return all_participants_rm_closed(core_participants)


def verify_activity_in_inbox(
    client: DataLayerClient,
    actor_id: str,
    activity_id: str,
) -> bool:
    """Check whether *activity_id* was received and stored by the actor.

    Checks the actor's store directly for the activity — the authoritative
    approach for exchange-demo tests.  Intake archives every activity it
    receives as a ``ReceivedActivityRecord`` under a key the receiver derives
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
    *question_note_id* and *reply_note_id* appear in the case notes.

    Args:
        receiver_client: Client connected to the receiver container.
        case_id: Full URI of the ``as_VulnerabilityCase`` to verify.
        report_id: Full URI of the submitted vulnerability report.
        receiver_actor_id: Full URI of the receiver actor.
        reporter_actor_id: Full URI of the reporter actor.
        question_note_id: Optional URI of the question note to assert present.
        reply_note_id: Optional URI of the reply note to assert present.

    Returns:
        The fetched and validated ``as_VulnerabilityCase``.

    Raises:
        AssertionError: If any invariant is violated.
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
            " store: the proposal was not handled there (DEMOMA-06-004)"
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
