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

"""Fetch a case's participant records from a DataLayer."""

import httpx2 as httpx

from vultron.demo.helpers.seeding.actors import dl_key
from vultron.demo.utils import (
    DataLayerClient,
    ref_id,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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
            client.dl_path(dl_key(participant_id), actor_id=dl_actor_id)
        )
        return as_CaseParticipant(**p_data)
    except (httpx.HTTPStatusError, AssertionError):
        return None


def _fetch_participant_data(client: DataLayerClient, p_id: str) -> dict | None:
    """Fetch a participant record, returning ``None`` for genuine 404s.

    Re-raises for any non-404 error so failures are not silently swallowed.
    """
    try:
        return client.get(client.dl_path(dl_key(p_id)))
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


def verify_participant_status_appended(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    status_id: str,
    dl_actor_id: str | None = None,
) -> None:
    """Raise unless *actor_id*'s participant record carries *status_id*.

    A received ``Add(ParticipantStatus)`` that is refused leaves the record
    unchanged and logs only a WARNING, so a demo step that sends one checks
    the append here (HP-08-008, #4999).

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor whose participant record to check.
        status_id: Full URI of the ``ParticipantStatus`` the ``Add`` carried.
        dl_actor_id: Full URI of the actor whose *store* to read — see
            :func:`_fetch_participant`.

    Raises:
        ValueError: If the participant record is missing or does not carry
            *status_id*.
    """
    participant = _fetch_participant(
        client, case_id, actor_id, dl_actor_id=dl_actor_id
    )
    if participant is None:
        raise ValueError(
            f"Participant record for '{actor_id}' not found in case"
            f" '{case_id}'"
        )
    status_ids = [
        ref_id(s) or str(s) for s in participant.participant_statuses or []
    ]
    if status_id not in status_ids:
        raise ValueError(
            f"ParticipantStatus '{status_id}' not appended to participant"
            f" '{participant.id_}'; it carries {status_ids}"
        )
