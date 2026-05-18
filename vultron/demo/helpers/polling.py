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

"""Polling helpers for demo workflows.

Provides a generic ``_poll_until`` primitive and all ``wait_for_*`` functions
used across demo scenarios.  Centralising polling logic here eliminates
boilerplate and ensures a single place to tune timeout/interval defaults.
"""

import logging
import time
from typing import Callable

from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic polling primitive
# ---------------------------------------------------------------------------


def _poll_until(
    condition_fn: Callable[[], bool],
    timeout_seconds: float,
    poll_interval: float = 0.5,
    error_msg: str = "Timed out waiting for condition",
    swallow_exceptions: bool = True,
) -> None:
    """Poll *condition_fn* until it returns ``True`` or the deadline passes.

    Args:
        condition_fn: Callable returning ``True`` when the condition is met.
        timeout_seconds: Maximum time to wait in seconds.
        poll_interval: Seconds between successive calls to *condition_fn*.
        error_msg: Message for the ``AssertionError`` raised on timeout.
        swallow_exceptions: When ``True``, exceptions raised by *condition_fn*
            are caught and treated as ``False`` (poll continues).  When
            ``False``, exceptions propagate immediately.

    Raises:
        AssertionError: If *condition_fn* does not return ``True`` within
            *timeout_seconds*.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if condition_fn():
                return
        except Exception:  # noqa: BLE001
            if not swallow_exceptions:
                raise
        time.sleep(poll_interval)

    raise AssertionError(error_msg)


# ---------------------------------------------------------------------------
# Container / case polling helpers
# ---------------------------------------------------------------------------


def wait_for_case_on_container(
    finder_client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll *client*'s DataLayer until *case_id* appears.

    Proves that an outbox activity (e.g. ``Create(VulnerabilityCase)``) was
    delivered to the actor on *client* and its inbox handler processed it.

    In single-server integration tests both actors share the same DataLayer so
    the case is visible immediately.  In a multi-server Docker demo the case
    arrives after the outbox background task completes.

    Args:
        finder_client: DataLayerClient connected to the container to poll.
        case_id: Full URI of the ``VulnerabilityCase`` to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If *case_id* does not appear within *timeout_seconds*.
    """

    def _check() -> bool:
        raw = finder_client.get("/datalayer/VulnerabilityCases/")
        return isinstance(raw, dict) and case_id in raw

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for case {case_id!r} to appear in DataLayer "
        f"at {finder_client.base_url} — outbox delivery may not have completed",
        swallow_exceptions=True,
    )


# Backward-compatible alias used by ``two_actor_demo.py`` and its tests.
wait_for_finder_case = wait_for_case_on_container


def wait_for_case_participants(
    vendor_client: DataLayerClient,
    case_id: str,
    expected_count: int,
    timeout_seconds: float = 5.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until the case on *vendor_client* reflects *expected_count* participants.

    Args:
        vendor_client: DataLayerClient for the container to poll.
        case_id: Full URI of the ``VulnerabilityCase``.
        expected_count: Minimum number of participants to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the participant count is not reached within
            *timeout_seconds*.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        case_data = vendor_client.get(f"/datalayer/{case_id}")
        case = VulnerabilityCase(**case_data)
        if len(case.case_participants) >= expected_count:
            return
        time.sleep(poll_interval)

    final_case = VulnerabilityCase(
        **vendor_client.get(f"/datalayer/{case_id}")
    )
    raise AssertionError(
        "Timed out waiting for participant count "
        f"{expected_count}; found {len(final_case.case_participants)}"
    )


def wait_for_note_in_case(
    client: DataLayerClient,
    case_id: str,
    note_id: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll until *note_id* appears in the ``notes`` list of the case.

    Used to confirm that an outbox-delivered note has been processed by the
    receiving actor's inbox handler.

    Args:
        client: DataLayerClient for the container to poll.
        case_id: Full URI of the case.
        note_id: Full URI of the note to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If *note_id* does not appear within *timeout_seconds*.
    """

    def _check() -> bool:
        case_data = client.get(f"/datalayer/{case_id}")
        case = VulnerabilityCase(**case_data)
        note_ids = [
            n if isinstance(n, str) else getattr(n, "id_", str(n))
            for n in case.notes
        ]
        return note_id in note_ids

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for note {note_id!r} to appear in case "
        f"{case_id!r}",
        swallow_exceptions=True,
    )


def wait_for_finder_log_entry(
    finder_client: DataLayerClient,
    case_id: str,
    entry_hash: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll finder's DataLayer until a ``CaseLogEntry`` with *entry_hash* appears.

    Proves that the vendor's ``Announce(CaseLogEntry)`` outbox activity was
    delivered to the finder's inbox and processed by
    ``AnnounceLogEntryReceivedUseCase`` (SYNC-2 receive side).

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        case_id: Full URI of the ``VulnerabilityCase`` (used for filtering).
        entry_hash: ``entry_hash`` value of the expected log entry.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the entry does not appear within *timeout_seconds*.

    Spec: SYNC-02-002.
    """

    def _check() -> bool:
        raw = finder_client.get("/datalayer/CaseLogEntrys/")
        if not isinstance(raw, dict):
            return False
        return any(
            isinstance(v, dict)
            and v.get("case_id") == case_id
            and v.get("entry_hash") == entry_hash
            for v in raw.values()
        )

    def _check_with_log() -> bool:
        raw = finder_client.get("/datalayer/CaseLogEntrys/")
        if not isinstance(raw, dict):
            return False
        for v in raw.values():
            if (
                isinstance(v, dict)
                and v.get("case_id") == case_id
                and v.get("entry_hash") == entry_hash
            ):
                logger.info(
                    "Log entry with hash=%s found in finder's DataLayer",
                    entry_hash[:16],
                )
                return True
        return False

    _poll_until(
        _check_with_log,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for log entry (hash={entry_hash!r}) for case "
        f"{case_id!r} to appear in finder's DataLayer — replication may "
        "not have completed",
        swallow_exceptions=True,
    )


# ---------------------------------------------------------------------------
# Participant-state polling helpers
# ---------------------------------------------------------------------------


def wait_for_participant_vfd_state(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    expected_states: "set",
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until *actor_id*'s latest participant ``vfd_state`` is in
    *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``CS_vfd`` values that satisfy the condition.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    # Import here to avoid a circular dependency with verification.py.
    from vultron.demo.helpers.verification import (  # noqa: PLC0415
        _fetch_participant,
    )

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        participant = _fetch_participant(client, case_id, actor_id)
        if participant is not None:
            latest = participant.participant_status
            if latest is not None and latest.vfd_state in expected_states:
                return
        time.sleep(poll_interval)

    participant = _fetch_participant(client, case_id, actor_id)
    latest = (
        participant.participant_status if participant is not None else None
    )
    current = latest.vfd_state if latest is not None else "unknown"
    raise AssertionError(
        f"Timed out waiting for actor '{actor_id}' vfd_state to be in "
        f"{expected_states!r}; current={current!r}"
    )


def wait_for_case_em_terminated(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until the case EM state is ``EM.EXITED``.

    After the Vendor (CASE_OWNER) reports public disclosure, the Case Actor
    automatically initiates embargo teardown.  This helper waits for the
    teardown to be reflected in the DataLayer.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``VulnerabilityCase``.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If EM.EXITED is not observed within *timeout_seconds*.
    """
    from vultron.core.states.em import EM  # noqa: PLC0415

    def _check() -> bool:
        case_data = client.get(f"/datalayer/{case_id}")
        case = VulnerabilityCase.model_validate(case_data)
        return case.current_status.em_state == EM.EXITED

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for case '{case_id}' EM state to reach EXITED"
        " — embargo teardown may not have completed",
        swallow_exceptions=True,
    )


def wait_for_all_participants_rm_closed(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until all participants in *case_id* have ``RM.CLOSED`` as their
    latest status.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``VulnerabilityCase``.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If any participant is not RM.CLOSED within
            *timeout_seconds*.
    """
    from vultron.demo.helpers.verification import (  # noqa: PLC0415
        _all_fetchable_participants_rm_closed,
    )

    def _check() -> bool:
        case_data = client.get(f"/datalayer/{case_id}")
        case = VulnerabilityCase.model_validate(case_data)
        return _all_fetchable_participants_rm_closed(client, case)

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for all participants in case '{case_id}' "
        "to reach RM.CLOSED",
        swallow_exceptions=True,
    )
