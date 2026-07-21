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
individual scenario modules (e.g. ``two_actor_demo.py``).  Keeping them here
avoids duplication when future multi-actor scenarios need the same checks.
"""

import logging
from typing import Optional

import httpx2 as httpx

from vultron.core.states.cs import (
    CS_pxa,
    CS_vfd,
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
)
from vultron.core.states.em import is_em_embargo_active
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.demo.helpers.seeding import _dl_key
from vultron.demo.utils import DataLayerClient, ref_id
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Participant fetch helpers
# ---------------------------------------------------------------------------


def _fetch_participant(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
) -> Optional[as_CaseParticipant]:
    """Fetch the as_CaseParticipant record for *actor_id* in *case_id*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor whose participant record to fetch.

    Returns:
        The ``as_CaseParticipant`` or ``None`` if the actor or participant
        record is not found.
    """
    try:
        case_data = client.get(f"/datalayer/{case_id}")
        case = as_VulnerabilityCase.model_validate(case_data)
        participant_id = case.actor_participant_index.get(actor_id)
        if participant_id is None:
            return None
        p_data = client.get(f"/datalayer/{_dl_key(participant_id)}")
        return as_CaseParticipant(**p_data)
    except (httpx.HTTPStatusError, AssertionError):
        return None


def _fetch_participant_data(client: DataLayerClient, p_id: str) -> dict | None:
    """Fetch a participant record, returning ``None`` for genuine 404s.

    Re-raises for any non-404 error so failures are not silently swallowed.
    """
    try:
        return client.get(f"/datalayer/{_dl_key(p_id)}")
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
        **vendor_client.get(f"/datalayer/{_dl_key(participant_id)}")
    )
    latest = participant.participant_status
    if latest is None:
        raise AssertionError("Vendor participant has no participant statuses")
    if latest.rm_state != RM.ACCEPTED:
        raise AssertionError(
            "Vendor participant RM state did not transition to ACCEPTED"
        )


def _assert_vendor_case_status(case: as_VulnerabilityCase) -> None:
    """Assert that *case* has ``EM.ACTIVE`` and ``pxa == CS_pxa.pxa``.

    Raises:
        AssertionError: If either invariant is violated.
    """
    if not is_em_embargo_active(case.current_status.em_state):
        raise AssertionError(
            f"Expected ACTIVE final EM state (default embargo activated at"
            f" case creation per EP-04-001), found {case.current_status.em_state}"
        )
    pxa = case.current_status.pxa_state
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


def _check_participant_vfd_state_in(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set[CS_vfd]",
    label: str,
) -> None:
    """Assert actor's latest participant vfd_state is in *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of acceptable ``CS_vfd`` values.
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
    latest_vfd = latest.vfd_state
    if latest_vfd not in expected_states:
        raise AssertionError(
            f"{label}: expected vfd_state in {expected_states!r}, "
            f"found {latest_vfd!r}"
        )


def _assert_participant_vfd_pxa(
    participant: as_CaseParticipant,
    label: str,
    vendor_actor_id: str,
) -> None:
    """Assert *participant* has VFD and a public-aware pxa_state.

    Args:
        participant: The ``as_CaseParticipant`` to check.
        label: Human-readable label for ``AssertionError`` messages.
        vendor_actor_id: Full URI of the vendor actor (used in error messages).

    Raises:
        AssertionError: If the participant's vfd_state is not VFD or its
            pxa_state is not public-aware.
    """
    public_aware = {CS_pxa.Pxa, CS_pxa.PxA, CS_pxa.PXa, CS_pxa.PXA}
    latest = participant.participant_status
    if latest is None:
        raise AssertionError(
            f"M6 {label}: participant {vendor_actor_id!r} has no statuses"
        )
    if latest.vfd_state != CS_vfd.VFD:
        raise AssertionError(
            f"M6 {label}: vfd_state is not VFD, found {latest.vfd_state!r}"
        )
    cs = getattr(latest, "case_status", None)
    pxa = getattr(cs, "pxa_state", None) if cs is not None else None
    if pxa not in public_aware:
        raise AssertionError(
            f"M6 {label}: pxa_state is not public-aware, found {pxa!r}"
        )


def _all_fetchable_participants_rm_closed(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
) -> bool:
    """Return ``True`` when every fetchable, non-CASE_MANAGER participant is
    ``RM.CLOSED``.

    Participants on remote containers (fetch returns ``None``) are skipped
    since their state is not locally observable.

    Args:
        client: DataLayerClient for the container to query.
        case: The ``as_VulnerabilityCase`` whose participant index to walk.

    Returns:
        ``True`` if all locally-fetchable non-receiver participants are
        ``RM.CLOSED``; ``False`` otherwise.
    """
    for p_id in case.actor_participant_index.values():
        p_data = _fetch_participant_data(client, p_id)
        if p_data is None:
            continue  # remote container — not fetchable here
        if not p_data:
            return False
        p = as_CaseParticipant(**p_data)
        if CVDRole.CASE_MANAGER in (p.case_roles or []):
            continue
        latest = p.participant_status
        if latest is None:
            return False
        if latest.rm_state != RM.CLOSED:
            return False
    return True


def verify_receiver_case_state(
    receiver_client: DataLayerClient,
    case_id: str,
    report_id: str,
    receiver_actor_id: str,
    reporter_actor_id: str,
    question_note_id: Optional[str] = None,
    reply_note_id: Optional[str] = None,
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
        **receiver_client.get(f"/datalayer/{case_id}")
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


def verify_case_actor_unused(
    case_actor_client: Optional[DataLayerClient],
    case_id: str,
) -> None:
    """Verify the dedicated CaseActor container remains unused in D5-2.

    Per D5-1-G3, the per-case ``VultronCaseActor`` co-locates in the
    receiver container for D5-2.  The standalone ``case-actor`` service
    participates in the Docker topology but should not hold the created
    ``as_VulnerabilityCase``.

    Args:
        case_actor_client: Optional client connected to the dedicated
            CaseActor container.  When ``None`` the check is skipped.
        case_id: Full URI of the case that should be absent.

    Raises:
        AssertionError: If the case is unexpectedly present on the dedicated
            CaseActor container.
    """
    if case_actor_client is None:
        return

    case_actor_cases = case_actor_client.get("/datalayer/VulnerabilityCases/")
    if case_id in case_actor_cases:
        raise AssertionError(
            "Dedicated case-actor container unexpectedly persisted the D5-2"
            " case"
        )
