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

"""Waits on a case's embargo: its EM state, proposal index and consent."""

import logging
from collections.abc import Callable

from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.helpers.polling._poll import _poll_until
from vultron.demo.helpers.verification import (
    _fetch_participant,
)
from vultron.demo.utils import (
    DataLayerClient,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def wait_for_case_em_state(
    client: DataLayerClient,
    case_id: str,
    expected: EM,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
    active_embargo_id: str | None = None,
) -> None:
    """Poll until the case EM state is *expected*.

    EM moves when the CASE_MANAGER commits a transition and the ledger entry
    reaches the replica, so a replica reads the new state some time after the
    trigger returned (ADR-0058).

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected: The EM state to wait for.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — the CASE_MANAGER's canonical case, for
            instance (see :func:`resolve_case_actor_store_id`).
        active_embargo_id: When given, the case must also name this embargo as
            its active one.  A revised embargo leaves ``EM.ACTIVE`` and comes
            back to it, so EM alone cannot tell a replica that has applied the
            revision from one that has not yet heard of it.

    Raises:
        AssertionError: If *expected* is not observed within *timeout_seconds*.
    """

    def _check() -> bool:
        case_data = client.get(client.dl_path(case_id, actor_id=dl_actor_id))
        case = as_VulnerabilityCase.model_validate(case_data)
        return case.em_state == expected and (
            active_embargo_id is None
            or case.active_embargo_id == active_embargo_id
        )

    store = dl_actor_id or client.actor_id
    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for case '{case_id}' EM state to reach"
        f" {expected.name}"
        + (
            f" with active embargo {active_embargo_id!r}"
            if active_embargo_id is not None
            else ""
        )
        + f" in the store of {store!r} at {client.base_url}",
        swallow_exceptions=True,
    )


def wait_for_case_em_terminated(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until the case EM state is ``EM.EXITED``.

    After the Vendor (CASE_OWNER) reports public disclosure, the Case Actor
    automatically initiates embargo teardown.  This helper waits for the
    teardown to be reflected in the DataLayer.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If EM.EXITED is not observed within *timeout_seconds*.
    """
    wait_for_case_em_state(
        client, case_id, EM.EXITED, timeout_seconds, poll_interval
    )


def wait_for_embargo_proposal_indexed(
    client: DataLayerClient,
    case_id: str,
    embargo_id: str,
    invite_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until the invitee's case maps *embargo_id* to *invite_id*.

    The relayed Invite is readable as soon as intake archives it, but the
    accept and reject triggers correlate an embargo with its Invite through the
    case's proposal index, which the received tree writes last (ID-04-005).
    An answer posted between the two builds its Accept with no object, so the
    Invite alone is not evidence the invitee can answer yet (EDF-06-002).

    Args:
        client: DataLayerClient connected to the invitee's container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        embargo_id: Full URI of the proposed ``EmbargoEvent``.
        invite_id: The relayed Invite's activity ID, as the invitee holds it.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the index does not name *invite_id* within
            *timeout_seconds*.
    """

    def _check() -> bool:
        case = as_VulnerabilityCase.model_validate(
            client.get(client.dl_path(case_id))
        )
        return case.pending_embargo_proposal_index.get(embargo_id) == invite_id

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for the case '{case_id}' at {client.base_url} to"
        f" index Invite {invite_id!r} for embargo {embargo_id!r}",
        swallow_exceptions=True,
    )


def wait_for_participant_embargo_consent(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    embargo_id: str,
    expected: EmbargoConsentState,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until *actor_id*'s consent for *embargo_id* reaches *expected*.

    Consent moves when the CASE_MANAGER commits the participant's answer, and
    a replica learns it from the ledger (EP-09-003), so it reads the new value
    some time after the answer's trigger returned.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor whose consent to check.
        embargo_id: Full URI of the embargo being tracked.
        expected: The :class:`~vultron.core.states.participant_embargo_consent.EmbargoConsentState` to wait for.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — see :func:`_fetch_participant`.

    Raises:
        AssertionError: If *expected* is not observed within *timeout_seconds*.
    """
    _wait_for_participant_embargo_field(
        client,
        case_id,
        actor_id,
        lambda participant: participant.consent_for(embargo_id),
        lambda value: value == expected,
        f"embargo consent to reach {expected.name}",
        timeout_seconds,
        poll_interval,
        dl_actor_id,
    )


def wait_for_participant_embargo_accepted(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    embargo_id: str,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until *actor_id*'s consent row for *embargo_id* is ``AGREED``.

    An Accept always marks the accepted embargo's own row ``AGREED``, including
    for a proposed revision (ADR-0122), so the revision's row is the trace of it.
    Read it where the CASE_MANAGER commits it: an owner that activates a longer
    revision first lapses every signatory that has not answered (EP-05-001).

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor whose answer to check.
        embargo_id: The embargo the actor answered.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — see :func:`_fetch_participant`.

    Raises:
        AssertionError: If the answer is not observed within *timeout_seconds*.
    """
    _wait_for_participant_embargo_field(
        client,
        case_id,
        actor_id,
        lambda participant: participant.consent_for(embargo_id),
        lambda value: value == EmbargoConsentState.AGREED,
        f"consent for {embargo_id!r} to be AGREED",
        timeout_seconds,
        poll_interval,
        dl_actor_id,
    )


def _wait_for_participant_embargo_field(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    read: Callable[[as_CaseParticipant], object],
    satisfied: Callable[[object], bool],
    description: str,
    timeout_seconds: float,
    poll_interval: float,
    dl_actor_id: str | None,
) -> None:
    """Poll one embargo field of a participant record until *satisfied*.

    The timeout names the last value read, and the last read error when no poll
    completed, so a slow commit and a broken read look different.
    """
    current: list[object] = ["no participant record"]

    def _check() -> bool:
        participant = _fetch_participant(
            client, case_id, actor_id, dl_actor_id=dl_actor_id
        )
        if participant is None:
            return False
        current[0] = read(participant)
        return satisfied(current[0])

    store = dl_actor_id or client.actor_id
    try:
        _poll_until(
            _check,
            timeout_seconds,
            poll_interval,
            "unused",
            swallow_exceptions=True,
        )
    except AssertionError as exc:
        # Built after the wait: ``current`` is what the last poll read.
        cause = (
            f"; {exc.__cause__.__class__.__name__}: {exc.__cause__}"
            if exc.__cause__ is not None
            else ""
        )
        raise AssertionError(
            f"Timed out waiting for actor '{actor_id}' {description};"
            f" current={current[0]!r} (polled {client.base_url}, store of"
            f" {store!r}){cause}"
        ) from exc
