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

"""Waits on a case ledger: one entry, one event, or contiguous coverage."""

import logging

from vultron.demo.helpers.polling._poll import (
    BACKFILL_PROGRESS_CEILING,
    LEDGER_COVERAGE_TIMEOUT,
    PARTICIPANT_JOIN_TIMEOUT,
    ProgressDeadline,
    _poll_until,
)
from vultron.demo.helpers.polling.case_actor import resolve_case_actor_store_id
from vultron.demo.utils import (
    DataLayerClient,
)

logger = logging.getLogger(__name__)


def wait_for_reporter_log_entry(
    reporter_client: DataLayerClient,
    case_id: str,
    entry_hash: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll reporter's DataLayer until a ``CaseLedgerEntry`` with *entry_hash* appears.

    Proves that the vendor's ``Announce(CaseLedgerEntry)`` outbox activity was
    delivered to the reporter's inbox and processed by
    ``AnnounceLedgerEntryReceivedUseCase`` (LedgerFanout receive side).

    Args:
        reporter_client: DataLayerClient connected to the Reporter container.
        case_id: Full URI of the ``as_VulnerabilityCase`` (used for filtering).
        entry_hash: ``entry_hash`` value of the expected log entry.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the entry does not appear within *timeout_seconds*.

    Spec: SYNC-02-001.
    """

    def _check_with_log() -> bool:
        raw = reporter_client.get(reporter_client.dl_path("CaseLedgerEntrys/"))
        if not isinstance(raw, dict):
            return False
        for v in raw.values():
            if (
                isinstance(v, dict)
                and v.get("case_id") == case_id
                and v.get("entry_hash") == entry_hash
            ):
                logger.info(
                    "Log entry with hash=%s found in reporter's DataLayer",
                    entry_hash[:16],
                )
                return True
        return False

    _poll_until(
        _check_with_log,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for log entry (hash={entry_hash!r}) for case "
        f"{case_id!r} to appear in reporter's DataLayer — replication may "
        "not have completed",
        swallow_exceptions=True,
    )


def _ledger_entry_matches(
    entry: dict,
    case_id: str,
    semantic_type: str,
    log_object_id: "str | None",
    min_log_index: "int | None",
) -> bool:
    """Return True if *entry* satisfies all supplied ledger-event criteria."""
    if entry.get("case_id") != case_id:
        return False
    if entry.get("semantic_type") != semantic_type:
        return False
    if (
        log_object_id is not None
        and entry.get("log_object_id") != log_object_id
    ):
        return False
    if min_log_index is not None:
        idx = entry.get("log_index")
        if not isinstance(idx, int) or idx < min_log_index:
            return False
    return True


def wait_for_ledger_event(
    client: DataLayerClient,
    case_id: str,
    semantic_type: str,
    log_object_id: "str | None" = None,
    min_log_index: "int | None" = None,
    timeout_seconds: float = PARTICIPANT_JOIN_TIMEOUT,
    poll_interval: float = 0.5,
    dl_actor_id: str | None = None,
) -> None:
    """Poll *client*'s DataLayer until a ``CaseLedgerEntry`` matches the given criteria.

    More precise than :func:`wait_for_semantic_type_in_ledger`: when *log_object_id*
    is provided the gate is keyed on ``(semantic_type, log_object_id)``; when
    *min_log_index* is provided the gate additionally requires the matching entry
    to have ``log_index >= min_log_index``.  With neither supplied the behaviour
    is match-any (same as the legacy helper).

    Args:
        client: DataLayerClient connected to the authoritative container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        semantic_type: The ``semantic_type`` value to wait for (e.g. ``"close_case"``).
        log_object_id: When supplied, the ledger entry's ``log_object_id`` must
            also match.  Use this to distinguish multiple events of the same
            type on different objects (EDF-06-002).
        min_log_index: When supplied, only entries with ``log_index >=
            min_log_index`` satisfy the gate.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Read this actor's store instead of *client*'s own.  Pass
            :func:`resolve_case_actor_store_id` when the entry being waited for
            is one only the CaseActor commits: under ADR-0073 the CaseActor's
            store is not its host's, so an event that reaches a participant's
            replica only if the CaseActor ledgers *and replicates* it is not
            observable in the host's store at all.

    Raises:
        AssertionError: If no matching entry appears within *timeout_seconds*.

    Spec: EDF-06-001, EDF-06-002.
    """

    def _check() -> bool:
        raw = client.get(
            client.dl_path("CaseLedgerEntrys/", actor_id=dl_actor_id)
        )
        if not isinstance(raw, dict):
            return False
        for v in raw.values():
            if not isinstance(v, dict):
                continue
            if not _ledger_entry_matches(
                v, case_id, semantic_type, log_object_id, min_log_index
            ):
                continue
            logger.info(
                "Ledger event %r found for case %s"
                " (log_object_id=%r, log_index=%r)",
                semantic_type,
                case_id,
                v.get("log_object_id"),
                v.get("log_index"),
            )
            return True
        return False

    parts = [f"semantic_type={semantic_type!r}"]
    if log_object_id is not None:
        parts.append(f"log_object_id={log_object_id!r}")
    if min_log_index is not None:
        parts.append(f"log_index>={min_log_index}")
    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for ledger event ({', '.join(parts)}) in case "
        f"{case_id!r} at {client.base_url}",
        swallow_exceptions=True,
    )


def wait_for_semantic_type_in_ledger(
    client: DataLayerClient,
    case_id: str,
    semantic_type: str,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.5,
    dl_actor_id: str | None = None,
) -> None:
    """Poll *client*'s DataLayer until a ``CaseLedgerEntry`` with *semantic_type* appears.

    Use this before reading the authoritative tail index when a later step
    depends on an entry the CaseActor commits asynchronously, so the tail
    snapshot includes it.  Without such a wait, the tail index may exclude the
    entry, causing a coverage-wait 'success' for the wrong tail and a gapped
    ledger dump (issue #1772 Bug B).  The close phase no longer reads the
    authority's tail: a closed participant is sent nothing after its own
    closure entries (CM-23-004), so
    :func:`~vultron.demo.helpers.closure.close_case_owner_last` checks each
    replica against that participant's own closure instead.

    Args:
        client: DataLayerClient connected to the authoritative container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        semantic_type: The ``semantic_type`` value to wait for (e.g. ``"close_case"``).
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Read this actor's store instead of *client*'s own.  Pass
            :func:`resolve_case_actor_store_id` when the entry being waited for
            is one only the CaseActor commits: under ADR-0073 the CaseActor's
            store is not its host's, so an event that reaches a participant's
            replica only if the CaseActor ledgers *and replicates* it is not
            observable in the host's store at all.  ``reject_invite_actor_to_case``
            is the case in point — the rejection is self-contained on the
            CaseActor (CLP-10-006) with no participant effect to announce.

    Raises:
        AssertionError: If no entry with *semantic_type* appears within
            *timeout_seconds*.
    """

    wait_for_ledger_event(
        client=client,
        case_id=case_id,
        semantic_type=semantic_type,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        dl_actor_id=dl_actor_id,
    )


def wait_for_contiguous_ledger_coverage(
    client: DataLayerClient,
    case_id: str,
    expected_tail_index: int,
    timeout_seconds: float = LEDGER_COVERAGE_TIMEOUT,
    poll_interval: float = 0.5,
    progress_ceiling: float = BACKFILL_PROGRESS_CEILING,
) -> None:
    """Poll *client*'s DataLayer until it holds all log indices 0…*expected_tail_index*.

    :func:`wait_for_reporter_log_entry` only confirms that the tail entry (by
    hash) has arrived.  Because ``Announce(CaseLedgerEntry)`` activities are
    delivered independently, an intermediate entry (e.g. logIndex=17) can
    arrive *after* the tail entry, so the dump may still capture a gapped log.

    This helper closes that race by polling until the replica's local index
    set is the complete contiguous range ``{0, 1, …, expected_tail_index}``.

    The wait follows the delivery it is waiting on: every poll that finds more
    of the case's entries than any before restarts *timeout_seconds*
    (:class:`ProgressDeadline`), so a late joiner still draining a long
    backfill is waited for, and one whose entries stopped arriving fails
    *timeout_seconds* after the last one landed (#4424).

    Args:
        client: DataLayerClient connected to the replica container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected_tail_index: The highest ``log_index`` the replica must hold
            (inclusive).  Typically obtained from the authoritative actor's
            ledger dump before calling this function.
        timeout_seconds: Seconds the replica may go without receiving another
            of the case's entries before the wait gives up.
        poll_interval: Seconds between DataLayer poll attempts.
        progress_ceiling: Seconds after which the wait gives up however many
            entries are still arriving.

    Raises:
        AssertionError: If the replica stops receiving entries short of full
            contiguous coverage, or *progress_ceiling* passes first.

    Spec: SYNC-10-004 (catch-up gate must require a contiguous canonical log prefix).
    """
    expected_indices = set(range(expected_tail_index + 1))
    progress = ProgressDeadline(timeout_seconds, progress_ceiling)

    def _check() -> bool:
        raw = client.get(client.dl_path("CaseLedgerEntrys/"))
        if not isinstance(raw, dict):
            return False
        present = {
            v["log_index"]
            for v in raw.values()
            if isinstance(v, dict)
            and v.get("case_id") == case_id
            and isinstance(v.get("log_index"), int)
        }
        progress.observe(len(present))
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
        progress=progress,
    )


def _count_case_ledger_entries(client: DataLayerClient, case_id: str) -> int:
    """Count *case_id*'s ledger entries in *client*'s store.

    Read from the ``CaseLedgerEntrys/`` collection, which serves the stored
    rows by field name (``case_id``) without rehydrating them, the same read
    :func:`wait_for_contiguous_ledger_coverage` makes.  It still transfers every
    entry, ``payload_snapshot`` included, on each poll; only the rehydration
    and the rest of the store are saved (#4600).
    """
    raw = client.get(client.dl_path("CaseLedgerEntrys/"))
    if not isinstance(raw, dict):
        return 0
    return sum(
        1
        for obj in raw.values()
        if isinstance(obj, dict) and obj.get("case_id") == case_id
    )


def wait_for_case_actor_ledger_event(
    client: DataLayerClient,
    case_id: str,
    semantic_type: str,
    timeout_seconds: float = PARTICIPANT_JOIN_TIMEOUT,
    poll_interval: float = 0.5,
) -> None:
    """Poll the CaseActor's *own* ledger, read through *client*, for *semantic_type*.

    The gate for "the CASE_MANAGER committed it": the commit lands in the
    CaseActor's store the moment its received-side tree runs, before any
    ``Announce(CaseLedgerEntry)`` has left its outbox.  Under ADR-0073 that
    store is not its host's, so the read is scoped with
    :func:`resolve_case_actor_store_id`; when the case has no co-hosted
    CaseActor the host's own replica is read, which is then the earliest
    observable *client* can offer.

    Waiting here before waiting on any replica separates the two hops a
    transfer takes — trigger → CaseActor inbox → commit, then CaseActor outbox
    → every participant — so a late replica is reported as the fan-out being
    late rather than as the transfer never having happened (EDF-06-002,
    #3602).

    Args:
        client: DataLayerClient for the container that hosts the CaseActor.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        semantic_type: The ``semantic_type`` value to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If no such entry appears within *timeout_seconds*.
    """
    wait_for_semantic_type_in_ledger(
        client=client,
        case_id=case_id,
        semantic_type=semantic_type,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        dl_actor_id=resolve_case_actor_store_id(client, case_id),
    )
