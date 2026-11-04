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

"""Waits on a participant's status: its RM, VF, D and PXA states."""

import logging
import time
from collections.abc import Callable
from typing import Literal, get_args

from vultron.core.models.dimensions import dimension_state
from vultron.core.states.cs import CS_pxa
from vultron.demo.helpers.polling._poll import _poll_until
from vultron.demo.helpers.verification.participants import (
    _fetch_participant,
)
from vultron.demo.helpers.verification.states import (
    _all_fetchable_participants_rm_closed,
)
from vultron.demo.utils import (
    DataLayerClient,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


ParticipantDimension = Literal["rm", "vf", "d"]
"""The ``ParticipantStatus`` dimension fields a participant poll can read."""


def _poll_participant(
    fetch: Callable[[], as_CaseParticipant | None],
    reached: Callable[[as_CaseParticipant | None, int], bool],
    timeout_seconds: float,
    poll_interval: float,
) -> bool:
    """Re-read a participant record until *reached* accepts it, or time runs out.

    The loop the participant-state waits share.  *fetch* reads the record
    (``None`` when it is absent); *reached* is given that read and the 1-based
    poll number, and logs what it saw.  Unlike :func:`_poll_until` there is no
    read once the deadline has passed: each caller re-reads the record itself
    to name its current state in the timeout message.

    Returns:
        ``True`` when *reached* accepted a read, ``False`` at the deadline.
    """
    deadline = time.monotonic() + timeout_seconds
    poll_count = 0
    while time.monotonic() < deadline:
        poll_count += 1
        if reached(fetch(), poll_count):
            return True
        time.sleep(poll_interval)
    return False


def _wait_for_participant_status_field(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    dimension: ParticipantDimension,
    expected_states: "set",
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until *actor_id*'s latest participant status dimension is in *expected_states*.

    Private shared implementation for :func:`wait_for_participant_vf_state`,
    :func:`wait_for_participant_d_state`, and :func:`wait_for_participant_rm_state`.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        dimension: Dimension field on the participant status object whose
            state to check (``"vf"``, ``"d"``, or ``"rm"``).  An absent
            dimension (``vf`` on a non-VENDOR) reads as ``None``.
        expected_states: Set of state values that satisfy the condition.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — see :func:`_fetch_participant`.

    Raises:
        ValueError: If *dimension* is not a ``ParticipantStatus`` dimension
            field, so a misspelled name fails at once instead of timing out.
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    if dimension not in get_args(ParticipantDimension):
        raise ValueError(
            f"Unknown participant status dimension {dimension!r}; "
            f"expected one of {get_args(ParticipantDimension)}"
        )

    def _reached(
        participant: as_CaseParticipant | None, poll_count: int
    ) -> bool:
        if participant is None:
            logger.debug(
                "_wait_for_participant_status_field poll #%d: "
                "actor=%r case=%r participant=<not found>",
                poll_count,
                actor_id,
                case_id,
            )
            return False
        latest = participant.participant_status
        n_statuses = len(participant.participant_statuses or [])
        current_val = (
            dimension_state(latest, dimension) if latest is not None else None
        )
        logger.debug(
            "_wait_for_participant_status_field poll #%d: "
            "actor=%r case=%r participant=%r "
            "n_statuses=%d dimension=%r current=%r expected=%r",
            poll_count,
            actor_id,
            case_id,
            participant.id_,
            n_statuses,
            dimension,
            current_val,
            expected_states,
        )
        return latest is not None and current_val in expected_states

    if _poll_participant(
        lambda: _fetch_participant(
            client, case_id, actor_id, dl_actor_id=dl_actor_id
        ),
        _reached,
        timeout_seconds,
        poll_interval,
    ):
        return

    participant = _fetch_participant(
        client, case_id, actor_id, dl_actor_id=dl_actor_id
    )
    latest = (
        participant.participant_status if participant is not None else None
    )
    current_val = (
        dimension_state(latest, dimension) if latest is not None else "unknown"
    )
    store = dl_actor_id or client.actor_id
    logger.debug(
        "_wait_for_participant_status_field timed out after %.1f s: "
        "actor=%r case=%r dimension=%r current=%r expected=%r store=%r",
        timeout_seconds,
        actor_id,
        case_id,
        dimension,
        current_val,
        expected_states,
        store,
    )
    raise AssertionError(
        f"Timed out waiting for actor '{actor_id}' {dimension} state to be in "
        f"{expected_states!r}; current={current_val!r}"
        f" (polled {client.base_url}, store of {store!r})"
    )


def wait_for_participant_vf_state(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set",
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until *actor_id*'s latest participant VF state (``vf.state``) is in
    *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``CS_vf`` values that satisfy the condition.
        timeout_seconds: Maximum time to wait (default: 30 s).
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — typically the CaseActor co-hosted in
            a single-container exchange demo.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    _wait_for_participant_status_field(
        client,
        case_id,
        actor_id,
        "vf",
        expected_states,
        timeout_seconds,
        poll_interval,
        dl_actor_id=dl_actor_id,
    )


def wait_for_participant_d_state(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set",
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until *actor_id*'s latest participant D state (``d.state``) is in
    *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``CS_d`` values that satisfy the condition.
        timeout_seconds: Maximum time to wait (default: 30 s).
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — typically the CaseActor co-hosted in
            a single-container exchange demo.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    _wait_for_participant_status_field(
        client,
        case_id,
        actor_id,
        "d",
        expected_states,
        timeout_seconds,
        poll_interval,
        dl_actor_id=dl_actor_id,
    )


def wait_for_participant_rm_state(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set",
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until *actor_id*'s latest participant RM state (``rm.state``) is in
    *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``RM`` values that satisfy the condition.
        timeout_seconds: Maximum time to wait (default: 30 s).
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — typically the CaseActor co-hosted in
            a single-container exchange demo.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    _wait_for_participant_status_field(
        client,
        case_id,
        actor_id,
        "rm",
        expected_states,
        timeout_seconds,
        poll_interval,
        dl_actor_id=dl_actor_id,
    )


def wait_for_all_participants_rm_closed(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until all participants in *case_id* have ``RM.CLOSED`` as their
    latest status.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If any participant is not RM.CLOSED within
            *timeout_seconds*.
    """

    def _check() -> bool:
        case_data = client.get(client.dl_path(case_id))
        case = as_VulnerabilityCase.model_validate(case_data)
        return _all_fetchable_participants_rm_closed(client, case)

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for all participants in case '{case_id}' "
        "to reach RM.CLOSED",
        swallow_exceptions=True,
    )


def wait_for_participant_pxa_state(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set | None" = None,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until *actor_id*'s participant status shows a public-aware pxa_state.

    The PXA state is nested at ``participant.participant_status.case_status
    .pxa.state`` and cannot be reached by the generic
    :func:`_wait_for_participant_status_field` (which handles only top-level
    fields on ``as_ParticipantStatus``).  This helper handles the two-level
    attribute access explicitly.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``CS_pxa`` values that satisfy the condition.
            Defaults to all public-aware states: ``{Pxa, PxA, PXa, PXA}``.
        timeout_seconds: Maximum time to wait (default: 30 s).
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the expected pxa_state is not reached within
            *timeout_seconds*.

    Spec: DEMOMA-06-002.
    """
    if expected_states is None:
        expected_states = {CS_pxa.Pxa, CS_pxa.PxA, CS_pxa.PXa, CS_pxa.PXA}

    wanted = expected_states

    def _reached(
        participant: as_CaseParticipant | None, poll_count: int
    ) -> bool:
        if participant is None or participant.participant_status is None:
            return False
        cs = getattr(participant.participant_status, "case_status", None)
        pxa = dimension_state(cs, "pxa")
        logger.debug(
            "wait_for_participant_pxa_state poll #%d: "
            "actor=%r case=%r pxa=%r expected=%r",
            poll_count,
            actor_id,
            case_id,
            pxa,
            wanted,
        )
        return pxa in wanted

    if _poll_participant(
        lambda: _fetch_participant(client, case_id, actor_id),
        _reached,
        timeout_seconds,
        poll_interval,
    ):
        return

    participant = _fetch_participant(client, case_id, actor_id)
    latest = (
        participant.participant_status if participant is not None else None
    )
    cs = getattr(latest, "case_status", None) if latest is not None else None
    pxa = dimension_state(cs, "pxa")
    raise AssertionError(
        f"Timed out waiting for actor '{actor_id}' pxa_state to be in "
        f"{expected_states!r}; current={pxa!r}"
        f" (polled {client.base_url})"
    )
