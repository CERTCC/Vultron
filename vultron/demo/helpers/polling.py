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
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll *client*'s DataLayer until *case_id* appears.

    Proves that an outbox activity (e.g. ``Create(as_VulnerabilityCase)``) was
    delivered to the actor on *client* and its inbox handler processed it.

    In single-server integration tests both actors share the same DataLayer so
    the case is visible immediately.  In a multi-server Docker demo the case
    arrives after the outbox background task completes.

    Args:
        client: DataLayerClient connected to the container to poll.
        case_id: Full URI of the ``as_VulnerabilityCase`` to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If *case_id* does not appear within *timeout_seconds*.
    """

    def _check() -> bool:
        raw = client.get("/datalayer/VulnerabilityCases/")
        return isinstance(raw, dict) and case_id in raw

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for case {case_id!r} to appear in DataLayer "
        f"at {client.base_url} — outbox delivery may not have completed",
        swallow_exceptions=True,
    )


def wait_for_finder_case(
    finder_client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.5,
) -> None:
    """Backward-compatible alias for :func:`wait_for_case_on_container`.

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        case_id: Full URI of the ``as_VulnerabilityCase`` to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.
    """
    wait_for_case_on_container(
        finder_client, case_id, timeout_seconds, poll_interval
    )


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
        case_id: Full URI of the ``as_VulnerabilityCase``.
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
        case = as_VulnerabilityCase(**case_data)
        if len(case.case_participants) >= expected_count:
            return
        time.sleep(poll_interval)

    final_case = as_VulnerabilityCase(
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
        case = as_VulnerabilityCase(**case_data)
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
    """Poll finder's DataLayer until a ``CaseLedgerEntry`` with *entry_hash* appears.

    Proves that the vendor's ``Announce(CaseLedgerEntry)`` outbox activity was
    delivered to the finder's inbox and processed by
    ``AnnounceLedgerEntryReceivedUseCase`` (SYNC-2 receive side).

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        case_id: Full URI of the ``as_VulnerabilityCase`` (used for filtering).
        entry_hash: ``entry_hash`` value of the expected log entry.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the entry does not appear within *timeout_seconds*.

    Spec: SYNC-02-002.
    """

    def _check_with_log() -> bool:
        raw = finder_client.get("/datalayer/CaseLedgerEntrys/")
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


def wait_for_contiguous_ledger_coverage(
    client: DataLayerClient,
    case_id: str,
    expected_tail_index: int,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll *client*'s DataLayer until it holds all log indices 0…*expected_tail_index*.

    :func:`wait_for_finder_log_entry` only confirms that the tail entry (by
    hash) has arrived.  Because ``Announce(CaseLedgerEntry)`` activities are
    delivered independently, an intermediate entry (e.g. logIndex=17) can
    arrive *after* the tail entry, so the dump may still capture a gapped log.

    This helper closes that race by polling until the replica's local index
    set is the complete contiguous range ``{0, 1, …, expected_tail_index}``.

    Args:
        client: DataLayerClient connected to the replica container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected_tail_index: The highest ``log_index`` the replica must hold
            (inclusive).  Typically obtained from the authoritative actor's
            ledger dump before calling this function.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the replica does not have full contiguous coverage
            within *timeout_seconds*.

    Spec: SYNC-10-004 (catch-up gate must require a contiguous canonical log prefix).
    """
    expected_indices = set(range(expected_tail_index + 1))

    def _check() -> bool:
        raw = client.get("/datalayer/CaseLedgerEntrys/")
        if not isinstance(raw, dict):
            return False
        present = {
            v["log_index"]
            for v in raw.values()
            if isinstance(v, dict)
            and v.get("case_id") == case_id
            and isinstance(v.get("log_index"), int)
        }
        missing = expected_indices - present
        if missing:
            logger.debug(
                "Ledger coverage check: %d/%d entries present for case %s; "
                "missing indices: %s",
                len(present),
                expected_tail_index + 1,
                case_id,
                sorted(missing)[:10],
            )
            return False
        logger.info(
            "Ledger fully replicated for case %s (%d entries, indices 0…%d)",
            case_id,
            expected_tail_index + 1,
            expected_tail_index,
        )
        return True

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for contiguous ledger coverage (0…{expected_tail_index}) "
        f"for case {case_id!r} — one or more intermediate entries may not have "
        "been delivered",
        swallow_exceptions=True,
    )


# ---------------------------------------------------------------------------
# Invite polling helpers
# ---------------------------------------------------------------------------


def _is_case_invite_for(obj_data: dict, case_id: str, invitee_id: str) -> bool:
    """Return True if *obj_data* is an Invite(Actor, Case) for *invitee_id*/*case_id*."""
    if obj_data.get("type") != "Invite":
        return False
    target_raw = obj_data.get("target")
    target_id = (
        target_raw.get("id") if isinstance(target_raw, dict) else target_raw
    )
    if target_id != case_id:
        return False
    inner = obj_data.get("object")
    inner_id = inner.get("id") if isinstance(inner, dict) else inner
    return inner_id == invitee_id


def find_case_invite_for_actor(
    client: DataLayerClient,
    case_id: str,
    invitee_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until the CaseActor's Invite(Actor, Case) for *invitee_id* arrives.

    In the ADR-0026 flow the CaseActor emits the Invite to the suggested actor
    after the Case Owner accepts; the invitee must then send Accept(Invite) to
    trigger the trust-bootstrap Announce(VulnerabilityCase) that seeds its case
    replica (MV-10-003/MV-10-004).  This helper polls the invitee's DataLayer
    for that Invite so the demo can drive the accept step.

    Args:
        client: DataLayerClient connected to the invitee container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        invitee_id: Full URI of the actor being invited.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The invite activity ID string.

    Raises:
        AssertionError: If no matching Invite is found within *timeout_seconds*.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            all_objects = client.get("/datalayer/")
            if isinstance(all_objects, dict):
                for raw_id, obj_data in all_objects.items():
                    if not isinstance(obj_data, dict):
                        continue
                    if _is_case_invite_for(obj_data, case_id, invitee_id):
                        obj_id = str(raw_id)
                        logger.info(
                            "Found Invite for actor %s on case %s: %s",
                            invitee_id,
                            case_id,
                            obj_id,
                        )
                        return obj_id
        except Exception:  # noqa: BLE001
            pass
        time.sleep(poll_interval)

    raise AssertionError(
        f"Timed out waiting for CaseActor Invite for actor {invitee_id!r} on"
        f" case {case_id!r} to appear in DataLayer at {client.base_url}"
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
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``CS_vfd`` values that satisfy the condition.
        timeout_seconds: Maximum time to wait (default: 10 s).
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    # Import here to avoid a circular dependency with verification.py.
    from vultron.demo.helpers.verification import (  # noqa: PLC0415
        _fetch_participant,
    )

    deadline = time.monotonic() + timeout_seconds
    poll_count = 0
    while time.monotonic() < deadline:
        poll_count += 1
        participant = _fetch_participant(client, case_id, actor_id)
        if participant is not None:
            latest = participant.participant_status
            n_statuses = len(participant.participant_statuses or [])
            latest_vfd = latest.vfd_state if latest is not None else None
            latest_rm = latest.rm_state if latest is not None else None
            logger.debug(
                "wait_for_participant_vfd_state poll #%d: "
                "actor=%r case=%r participant=%r "
                "n_statuses=%d latest_vfd=%r latest_rm=%r expected=%r",
                poll_count,
                actor_id,
                case_id,
                participant.id_,
                n_statuses,
                latest_vfd,
                latest_rm,
                expected_states,
            )
            if latest is not None and latest.vfd_state in expected_states:
                return
        else:
            logger.debug(
                "wait_for_participant_vfd_state poll #%d: "
                "actor=%r case=%r participant=<not found>",
                poll_count,
                actor_id,
                case_id,
            )
        time.sleep(poll_interval)

    participant = _fetch_participant(client, case_id, actor_id)
    latest = (
        participant.participant_status if participant is not None else None
    )
    current = latest.vfd_state if latest is not None else "unknown"
    rm_state = latest.rm_state if latest is not None else "unknown"
    logger.debug(
        "wait_for_participant_vfd_state timed out after %.1f s: "
        "actor=%r case=%r vfd_state=%r rm_state=%r expected=%r",
        timeout_seconds,
        actor_id,
        case_id,
        current,
        rm_state,
        expected_states,
    )
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
        case_id: Full URI of the ``as_VulnerabilityCase``.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If EM.EXITED is not observed within *timeout_seconds*.
    """
    from vultron.core.states.em import is_em_exited  # noqa: PLC0415

    def _check() -> bool:
        case_data = client.get(f"/datalayer/{case_id}")
        case = as_VulnerabilityCase.model_validate(case_data)
        return is_em_exited(case.current_status.em_state)

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
        case_id: Full URI of the ``as_VulnerabilityCase``.
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
