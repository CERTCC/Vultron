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
from collections.abc import Callable, Sequence
from typing import Literal, get_args

from vultron.adapters.utils import parse_id, strip_id_prefix
from vultron.core.models.dimensions import dimension_state
from vultron.core.models.pending_case_inbox import (
    VultronPendingCaseInbox,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.helpers.verification import (
    _all_fetchable_participants_rm_closed,
    _fetch_participant,
    recipient_ids,
)
from vultron.demo.utils import (
    CASE_ACTOR_SLUG,
    RECEIVED_ACTIVITY_RECORD_TYPE,
    DataLayerClient,
    case_actor_id_for_report,
    case_references_report,
    demo_check,
    logfmt,
    not_received_error,
    read_received_activity,
    read_stored_of_types,
    received_activity_in,
)
from vultron.enums.object_types import VultronObjectType
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared timeout constants (EDF-06-006, EDF-06-008)
# ---------------------------------------------------------------------------

# 15 s: conservative cross-container delivery budget.
CROSS_CONTAINER_TIMEOUT: float = 15.0
# 20 s: invitation-chain propagation (find invite → accept → case replica seed).
PARTICIPANT_JOIN_TIMEOUT: float = 20.0
# 90 s: late-joiner and complex multi-hop join paths.
LATE_JOINER_TIMEOUT: float = 90.0
# 30 s: late-joiner replica catch-up after the join gate passes.
LATE_JOINER_REPLICA_TIMEOUT: float = 30.0
# 10 s: early participant's replica participant-index propagation budget.
REPLICA_PARTICIPANT_TIMEOUT: float = 10.0
# 30 s: contiguous ledger-coverage budget for a replica that has been receiving
# Announce(CaseLedgerEntry) as each entry was committed. 15 s fired at 0/29
# entries under CI load (#1911, #2337).
LEDGER_COVERAGE_TIMEOUT: float = 30.0
# 45 s: contiguous ledger-coverage budget for a late joiner, which catches up
# from genesis through the CM-17-004 backfill — one Announce per prior entry.
# Both coverage budgets are stall budgets: each newly arrived entry restarts
# them, up to BACKFILL_PROGRESS_CEILING (wait_for_contiguous_ledger_coverage).
LATE_JOINER_COVERAGE_TIMEOUT: float = 45.0
# 300 s: ceiling for a wait that follows a late joiner's backfill
# (:class:`ProgressDeadline`).  Such a wait fails when the joiner's ledger copy
# stops advancing, not when a fixed budget runs out: the backfill is one
# Announce per prior entry, applied one at a time by the joiner's inbox, and
# under CI load it ran from 26 s to over 100 s for the same 50-odd entries
# (#4424).  The ceiling only stops a wait that keeps seeing progress from
# running for ever; it is about three times the slowest backfill seen in CI.
BACKFILL_PROGRESS_CEILING: float = 300.0


def _client_in(
    client: DataLayerClient, clients: "Sequence[DataLayerClient]"
) -> bool:
    """Identity-based membership: is *client* one of *clients*?

    Demo clients are plain objects with no equality of their own, and two
    clients for the same container are still two clients, so membership in a
    late-joiner or covered-replica list is decided by identity, not equality.
    """
    return any(client is candidate for candidate in clients)


# ---------------------------------------------------------------------------
# Generic polling primitive
# ---------------------------------------------------------------------------


class ProgressDeadline:
    """A deadline that moves forward while the awaited cause visibly advances.

    A wait whose effect lands behind a queue of work — a late joiner's
    full-case Invite, queued after the ledger backfill (CM-11-010) — cannot be
    bounded by a fixed budget, because the queue's length times its per-item
    cost under load is not known in advance (#4424).  Gating on the cause
    (EDF-06, ADR-0058) means watching the queue drain: each reading of the
    progress measure that is higher than every earlier one restarts the
    *stall* budget.  The wait then fails only when nothing has advanced for
    ``stall_seconds``, or at ``ceiling_seconds`` from construction, whichever
    comes first.

    With no readings at all it is a plain ``stall_seconds`` deadline.  The
    first reading only sets the baseline, so progress made before the wait
    began earns no extra time.

    Args:
        stall_seconds: Seconds the measure may go without advancing.
        ceiling_seconds: Seconds after construction at which the wait ends
            however much progress it sees; never less than ``stall_seconds``.
    """

    def __init__(self, stall_seconds: float, ceiling_seconds: float) -> None:
        now = time.monotonic()
        self._stall = stall_seconds
        self._ceiling_seconds = max(stall_seconds, ceiling_seconds)
        self._ceiling = now + self._ceiling_seconds
        self._deadline = now + stall_seconds
        self._best: int | None = None

    def observe(self, progress: int) -> None:
        """Record a reading; restart the stall budget if it is a new high."""
        if self._best is None:
            self._best = progress
        elif progress > self._best:
            self._best = progress
            self._deadline = min(time.monotonic() + self._stall, self._ceiling)

    def expired(self) -> bool:
        """Whether the wait has run out of time."""
        return time.monotonic() >= self._deadline

    def describe(self) -> str:
        """Name the last progress reading, for a timeout message."""
        if self._best is None:
            return "no progress reading was taken"
        if (
            self._ceiling_seconds > self._stall
            and self._deadline >= self._ceiling
        ):
            return (
                f"progress reached {self._best} and was still advancing when"
                f" the wait hit its {self._ceiling_seconds:.0f} s ceiling"
            )
        return (
            f"progress reached {self._best}, then did not advance for"
            f" {self._stall:.0f} s"
        )


def _poll_until(
    condition_fn: Callable[[], bool],
    timeout_seconds: float,
    poll_interval: float = 0.5,
    error_msg: str = "Timed out waiting for condition",
    swallow_exceptions: bool = True,
    progress: ProgressDeadline | None = None,
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
        progress: When given, replaces the fixed *timeout_seconds* deadline;
            *condition_fn* feeds it readings, so the wait lasts as long as the
            cause keeps advancing (:class:`ProgressDeadline`).

    Raises:
        AssertionError: If *condition_fn* does not return ``True`` within
            *timeout_seconds*. When exceptions were swallowed, the last one is
            named in the message — a condition that never *ran* is a different
            fault from one that ran and stayed false, and reporting both as a
            bare timeout sends the reader looking for a slow protocol instead of
            a broken read.
    """
    # The condition is always tried at least once, even with no time left: a
    # wait handed the tail of a shared budget (SharedBudget) must still succeed
    # when its effect has already landed, and fail only when it has not.
    deadline = (
        progress
        if progress is not None
        else ProgressDeadline(timeout_seconds, timeout_seconds)
    )
    last_exc: Exception | None = None
    while True:
        try:
            if condition_fn():
                return
            last_exc = None
        except Exception as exc:
            if not swallow_exceptions:
                raise
            last_exc = exc
        if deadline.expired():
            break
        time.sleep(poll_interval)

    if last_exc is not None:
        raise AssertionError(
            f"{error_msg} — the check never completed: every attempt raised"
            f" {type(last_exc).__name__}: {last_exc}"
        ) from last_exc
    if progress is not None:
        raise AssertionError(f"{error_msg} ({progress.describe()})")
    raise AssertionError(error_msg)


# ---------------------------------------------------------------------------
# Container / case polling helpers
# ---------------------------------------------------------------------------


def wait_for_case_on_container(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 30.0,
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
        raw = client.get(client.dl_path("VulnerabilityCases/"))
        return isinstance(raw, dict) and case_id in raw

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for case {case_id!r} to appear in DataLayer "
        f"at {client.base_url} — outbox delivery may not have completed",
        swallow_exceptions=True,
    )


def wait_for_reporter_case(
    reporter_client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.5,
) -> None:
    """Backward-compatible alias for :func:`wait_for_case_on_container`.

    Args:
        reporter_client: DataLayerClient connected to the Reporter container.
        case_id: Full URI of the ``as_VulnerabilityCase`` to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.
    """
    wait_for_case_on_container(
        reporter_client, case_id, timeout_seconds, poll_interval
    )


def wait_for_case_participants(
    vendor_client: DataLayerClient,
    case_id: str,
    expected_actor_ids: "set[str]",
    # 15 s: conservative cross-container delivery budget (temporal per EDF-06-006).
    timeout_seconds: float = CROSS_CONTAINER_TIMEOUT,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until the case on *vendor_client* reflects all *expected_actor_ids*.

    Gates on identity: all actors in *expected_actor_ids* must appear in
    ``actor_participant_index``.  A count check (``>= N``) would accept the
    wrong participant set — for example CaseActor + Reporter instead of
    CaseActor + Vendor — masking a missing invite delivery (EDF-06-002).

    Args:
        vendor_client: DataLayerClient for the container to poll.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected_actor_ids: Set of actor URIs that must all be present as
            participants before the gate passes.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Read this actor's store on the container instead of
            the client's own — typically the CaseActor co-hosted in a
            single-container exchange demo, the only store that holds an
            invitee that never joined (CM-11-006).

    Raises:
        AssertionError: If any expected actor is absent after *timeout_seconds*.

    Spec: EDF-06-002.
    """

    def _check() -> bool:
        case_data = vendor_client.get(
            vendor_client.dl_path(case_id, actor_id=dl_actor_id)
        )
        case = as_VulnerabilityCase(**case_data)
        return expected_actor_ids.issubset(case.actor_participant_index.keys())

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for participants {expected_actor_ids!r} in case "
        f"{case_id!r}",
        swallow_exceptions=True,
    )


def wait_for_participants_on_replicas(
    replica_clients: "Sequence[DataLayerClient]",
    case_id: str,
    expected_actor_ids: "set[str]",
    *,
    late_joiners: "Sequence[DataLayerClient]" = (),
    late_joiner_timeout: float = LATE_JOINER_REPLICA_TIMEOUT,
    default_timeout: float = REPLICA_PARTICIPANT_TIMEOUT,
) -> None:
    """Wait for every replica in *replica_clients* to reflect all participants.

    Sync-verification polls each replica container until its
    ``actor_participant_index`` contains all *expected_actor_ids*.  Late
    joiners (LedgerFanout catch-up from genesis) need extra time for
    participant-index propagation, so any client in *late_joiners* is given
    *late_joiner_timeout* (30 s); all other replicas use *default_timeout*
    (10 s).  Temporal budget per EDF-06-006.

    This is the single implementation of the per-scenario replica
    participant-wait loop: previously each scenario carried its own copy of
    ``for replica_client in (...): p_timeout = 30.0 if ... else 10.0; ...``.
    rvv omitted the loop entirely — its two bare
    :func:`wait_for_case_participants` calls used the 15 s default, so the
    late joiner (Vendor2) never received the extended budget and could time
    out spuriously under CI load (#2852, extending the #2202/#2337
    sync-verification hardening).

    Each replica is polled independently via :func:`wait_for_case_participants`,
    so the identity-based participant check (EDF-06-002) applies unchanged.

    Each per-replica poll runs inside its own ``demo_check`` context
    (DEMOCI-01-011): :func:`wait_for_case_participants` raises ``AssertionError``
    on timeout, and a bare raise from scenario ``_phase_*`` code would crash the
    whole run at the first failure — defeating the failure-accumulation model
    (DEMOCI-01-003/004).  Wrapping here, in the shared helper, means all seven
    scenario callers inherit the fix (DRY) and one replica's timeout no longer
    hides another's: the failure is recorded and the loop continues to the next
    replica rather than propagating.  This mirrors
    :func:`vultron.demo.helpers.sync.wait_for_replica_ledger_coverage`, which
    wraps its per-replica coverage poll internally (#2819, #3384, #3906).

    Args:
        replica_clients: Replica containers to poll, in order.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected_actor_ids: Actor URIs that must all appear as participants.
        late_joiners: Subset of *replica_clients* that joined late and need
            the extended timeout.  Membership is tested by object identity.
        late_joiner_timeout: Timeout for late joiners.
        default_timeout: Timeout for early participants.

    Note:
        Does not raise on a replica timeout — the accumulating ``demo_check``
        records it and lets the scenario continue.  The low-level
        :func:`wait_for_case_participants` primitive keeps its raise-on-timeout
        contract for the unit tests that depend on it.
    """
    for replica_client in replica_clients:
        is_late = _client_in(replica_client, late_joiners)
        label = replica_client.actor_id or replica_client.base_url
        with demo_check(f"replica {label!r} reflects all case participants"):
            wait_for_case_participants(
                vendor_client=replica_client,
                case_id=case_id,
                expected_actor_ids=expected_actor_ids,
                timeout_seconds=(
                    late_joiner_timeout if is_late else default_timeout
                ),
            )


def wait_for_note_in_case(
    client: DataLayerClient,
    case_id: str,
    note_id: str,
    timeout_seconds: float = 30.0,
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
        case_data = client.get(client.dl_path(case_id))
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

    Spec: SYNC-02-002.
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
    event_type: str,
    log_object_id: "str | None",
    min_log_index: "int | None",
) -> bool:
    """Return True if *entry* satisfies all supplied ledger-event criteria."""
    if entry.get("case_id") != case_id:
        return False
    if entry.get("event_type") != event_type:
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
    event_type: str,
    log_object_id: "str | None" = None,
    min_log_index: "int | None" = None,
    timeout_seconds: float = PARTICIPANT_JOIN_TIMEOUT,
    poll_interval: float = 0.5,
    dl_actor_id: str | None = None,
) -> None:
    """Poll *client*'s DataLayer until a ``CaseLedgerEntry`` matches the given criteria.

    More precise than :func:`wait_for_event_type_in_ledger`: when *log_object_id*
    is provided the gate is keyed on ``(event_type, log_object_id)``; when
    *min_log_index* is provided the gate additionally requires the matching entry
    to have ``log_index >= min_log_index``.  With neither supplied the behaviour
    is match-any (same as the legacy helper).

    Args:
        client: DataLayerClient connected to the authoritative container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        event_type: The ``event_type`` value to wait for (e.g. ``"close_case"``).
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
                v, case_id, event_type, log_object_id, min_log_index
            ):
                continue
            logger.info(
                "Ledger event %r found for case %s"
                " (log_object_id=%r, log_index=%r)",
                event_type,
                case_id,
                v.get("log_object_id"),
                v.get("log_index"),
            )
            return True
        return False

    parts = [f"event_type={event_type!r}"]
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


def wait_for_event_type_in_ledger(
    client: DataLayerClient,
    case_id: str,
    event_type: str,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.5,
    dl_actor_id: str | None = None,
) -> None:
    """Poll *client*'s DataLayer until a ``CaseLedgerEntry`` with *event_type* appears.

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
        event_type: The ``event_type`` value to wait for (e.g. ``"close_case"``).
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
        AssertionError: If no entry with *event_type* appears within
            *timeout_seconds*.
    """

    wait_for_ledger_event(
        client=client,
        case_id=case_id,
        event_type=event_type,
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


# ---------------------------------------------------------------------------
# Generic DataLayer scan helper
# ---------------------------------------------------------------------------


def _poll_datalayer_for(
    client: DataLayerClient,
    object_types: Sequence[str],
    discriminator_fn: Callable[[dict], bool],
    timeout_seconds: float,
    poll_interval: float,
    log_msg: str,
    error_msg: str,
    id_fn: Callable[[str, dict], str] | None = None,
    progress_fn: Callable[[], int] | None = None,
    progress_ceiling: float = BACKFILL_PROGRESS_CEILING,
) -> str:
    """Poll the client's own DataLayer until *discriminator_fn* matches.

    The path is ``client.dl_path()`` — the *actor-scoped* collection, not the
    retired unscoped ``/datalayer/``.  Under ADR-0073 there is no store that is
    not some actor's own, so a poll must name whose store it is reading.

    Each tick reads the store's objects of *object_types* — serialized as the
    whole-store dump serializes them — and calls *discriminator_fn* on every
    ``dict``-typed value.  Returns the matching object's raw ID string on the
    first match.  The read is never the whole store: the polled container is
    often the one doing the work being waited on, and rehydrating and
    serializing its every object twice a second slowed that work down as the
    store grew (#4600).

    Args:
        client: DataLayerClient to poll.
        object_types: The stored types the awaited object can be held as.
        discriminator_fn: Callable receiving a single ``dict`` and returning
            ``True`` when the target object is found.
        timeout_seconds: Maximum seconds to wait before raising.
        poll_interval: Seconds between successive GET calls.
        log_msg: ``%``-style format string with a single ``%s`` placeholder
            for the matched object ID; logged at INFO on a successful find.
        error_msg: Message for the ``AssertionError`` raised on timeout.
        id_fn: Maps a match's raw ID and data to the ID returned; the raw ID
            itself when omitted.  A record that wraps another object (a
            received-activity archive) returns the wrapped object's ID.
        progress_fn: Reads how far the work queued ahead of the awaited
            object has got.  When given, *timeout_seconds* is
            a stall budget that each advance restarts, up to
            *progress_ceiling* (:class:`ProgressDeadline`); when omitted it is
            a fixed deadline.
        progress_ceiling: Seconds after which a *progress_fn* wait gives up
            however much progress it sees.

    Returns:
        The ID of the first matching object, as *id_fn* derives it.

    Raises:
        AssertionError: If no matching object is found in time.
    """
    deadline = ProgressDeadline(
        timeout_seconds,
        progress_ceiling if progress_fn is not None else timeout_seconds,
    )
    while not deadline.expired():
        try:
            objects = read_stored_of_types(client, object_types)
            for raw_id, obj_data in objects.items():
                if not isinstance(obj_data, dict):
                    continue
                if discriminator_fn(obj_data):
                    obj_id = (
                        id_fn(str(raw_id), obj_data)
                        if id_fn is not None
                        else str(raw_id)
                    )
                    logger.info(log_msg, obj_id)
                    return obj_id
            # Read progress only after the match, so a reading that raises
            # can never hide an object that has already arrived.
            if progress_fn is not None:
                deadline.observe(progress_fn())
        except Exception:  # noqa: BLE001, S110  # ruff-baseline #3326
            pass
        time.sleep(poll_interval)
    if progress_fn is not None:
        raise AssertionError(f"{error_msg} ({deadline.describe()})")
    raise AssertionError(error_msg)


# ---------------------------------------------------------------------------
# Invite polling helpers
# ---------------------------------------------------------------------------


#: The stored type a received activity is read from: intake's archive record,
#: kept under the receiver's key (CLP-10-017, ADR-0111).  A row of an activity
#: type under the sender's id is never read as a received one (DL-06-006).
_RECEIVED_ACTIVITY_TYPES: tuple[str, ...] = (RECEIVED_ACTIVITY_RECORD_TYPE,)

#: The stored type of an activity the inbox defers until its case is known.
#: A stub Invite is the one the demo waits on: the invitee holds no case until
#: its Accept brings the bootstrap Announce (MV-10-003), so the Invite has not
#: reached intake, and the row ingress keeps under the sender's id is the only
#: copy the invitee holds until the replay (see :func:`_received_activity`).
_DEFERRED_INVITE_TYPE = "Invite"

#: The stored types a received stub Invite can be held as.
_RECEIVED_OR_DEFERRED_INVITE_TYPES: tuple[str, ...] = (
    *_RECEIVED_ACTIVITY_TYPES,
    _DEFERRED_INVITE_TYPE,
)


def _received_activity(obj_data: dict) -> dict:
    """The received activity *obj_data* holds, as the receiver keeps it.

    Intake archives a dispatched activity as a ``ReceivedActivityRecord``
    (CLP-10-017, ADR-0111), which wraps it.  An activity the inbox deferred
    until its case is known — an invitee's Invite, usually — is held bare
    under the sender's id instead.  Mirrors
    :func:`vultron.core.use_cases._helpers.read_received_activity`.

    Raises:
        AssertionError: when a ``ReceivedActivityRecord`` wraps no activity.
    """
    if obj_data.get("type") != RECEIVED_ACTIVITY_RECORD_TYPE:
        return obj_data
    return received_activity_in(obj_data)


def _received_activity_id(raw_id: str, obj_data: dict) -> str:
    """The sender's id for the received activity *obj_data* holds.

    A bare activity is stored under the sender's id (*raw_id*); a record is
    stored under its own id and names the activity's id inside.

    Raises:
        AssertionError: when a record's activity carries no id.
    """
    if obj_data.get("type") != RECEIVED_ACTIVITY_RECORD_TYPE:
        return raw_id
    activity_id = _received_activity(obj_data).get("id")
    if not activity_id:
        raise AssertionError(
            f"received-activity record {raw_id!r} holds an activity with no id"
        )
    return str(activity_id)


def _stub_case_id(stub: dict) -> object:
    """The case a served ``VulnerabilityCaseStub`` names (CM-11-013).

    The archive record serves the objects nested in its activity under their
    field names (``case_id``); a bare activity row serves them under their
    wire names (``caseId``).
    """
    return stub["caseId"] if "caseId" in stub else stub.get("case_id")


def _is_case_invite_for(
    obj_data: dict, case_id: str, invitee_id: str, *, full_case: bool = False
) -> bool:
    """Return True if *obj_data* holds a case Invite for *invitee_id*/*case_id*.

    A stub Invite names its case in the stub's ``caseId`` (CM-11-013); the
    stub's own ``id`` is ``<case-id>/stub`` and is never parsed.  A full-case
    Invite names the case by URI (AKM-02-003).  *full_case* selects which of the
    two is wanted: any case Invite by default, only a full-case one when true.
    """
    invite = _received_activity(obj_data)
    if invite.get("type") != "Invite":
        return False
    target_raw = invite.get("target")
    is_stub = (
        isinstance(target_raw, dict)
        and target_raw.get("type")
        == VultronObjectType.VULNERABILITY_CASE_STUB.value
    )
    if full_case and is_stub:
        return False
    if isinstance(target_raw, dict):
        target_case_id = (
            _stub_case_id(target_raw) if is_stub else target_raw.get("id")
        )
    else:
        target_case_id = target_raw
    if target_case_id != case_id:
        return False
    inner = invite.get("object")
    inner_id = inner.get("id") if isinstance(inner, dict) else inner
    return inner_id == invitee_id


def _read_deferred_activity(
    client: DataLayerClient, activity_id: str, deferred_type: str
) -> dict | None:
    """The *deferred_type* activity *activity_id* the inbox holds for replay.

    ``None`` when the inbox holds no such activity.
    """
    row = read_stored_of_types(client, [deferred_type]).get(activity_id)
    return row if isinstance(row, dict) else None


def read_received_activity_for(
    client: DataLayerClient,
    activity_id: str,
    *,
    deferred_type: str | None = None,
) -> dict:
    """The activity *activity_id* as the actor behind *client* received it.

    Reads intake's archive record (:func:`read_received_activity`).  Only a
    caller waiting on an activity the inbox defers names *deferred_type*, the
    activity's type; the inbox's copy is then read when no record exists yet,
    as :data:`_DEFERRED_INVITE_TYPE` describes.

    Raises:
        AssertionError: If the actor holds no activity *activity_id*.
    """
    activity = read_received_activity(client, activity_id)
    if activity is None and deferred_type is not None:
        activity = _read_deferred_activity(client, activity_id, deferred_type)
    if activity is None:
        raise not_received_error(client, activity_id)
    return activity


def assert_received_from(
    client: DataLayerClient,
    activity_id: str,
    sender_id: str,
    consequence: str,
    *,
    deferred_type: str | None = None,
) -> None:
    """Assert the actor behind *client* received *activity_id* from *sender_id*.

    Args:
        client: DataLayerClient for the receiving actor's container.
        activity_id: The sender's id for the received activity.
        sender_id: The actor the activity must have been emitted as.
        consequence: What goes wrong when it was not, for the failure message.
        deferred_type: The activity's type, when the inbox may still be
            deferring it (:func:`read_received_activity_for`).

    Raises:
        AssertionError: If the activity is not held, or another actor sent it.
    """
    actor = read_received_activity_for(
        client, activity_id, deferred_type=deferred_type
    ).get("actor")
    emitted_as = actor.get("id") if isinstance(actor, dict) else actor
    assert emitted_as == sender_id, (
        f"'{activity_id}' was emitted as '{emitted_as}', not as"
        f" '{sender_id}' — {consequence}"
    )


def find_case_invite_for_actor(
    client: DataLayerClient,
    case_id: str,
    invitee_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until the CaseActor's Invite(Actor, CaseStub) for *invitee_id* arrives.

    The CASE_MANAGER emits every case Invite — after the Case Owner accepts a
    recommendation (ADR-0026) and on the owner's direct invite alike
    (CM-17-007, ADR-0109); the invitee must then send Accept(Invite) to
    trigger the trust-bootstrap Announce(VulnerabilityCase) that seeds its case
    replica (MV-10-003/MV-10-004).  This helper polls the invitee's DataLayer
    for that Invite — archived by intake, or held by the inbox until the case
    bootstrap — so the demo can drive the accept step.

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
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_OR_DEFERRED_INVITE_TYPES,
        discriminator_fn=lambda obj: _is_case_invite_for(
            obj, case_id, invitee_id
        ),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        log_msg=f"Found Invite for actor {invitee_id} on case {case_id}: %s",
        error_msg=(
            f"Timed out waiting for CaseActor Invite for actor {invitee_id!r}"
            f" on case {case_id!r} to appear in DataLayer at {client.base_url}"
        ),
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


def find_full_case_invite_for_actor(
    client: DataLayerClient,
    case_id: str,
    invitee_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
    progress_ceiling: float = BACKFILL_PROGRESS_CEILING,
) -> str:
    """Poll until the CASE_MANAGER's full-case Invite for *invitee_id* arrives.

    The CASE_MANAGER sends it after the join-time ``Announce(VulnerabilityCase)``
    and ledger replay (CM-11-010); the joined participant answers it with
    ``accept-full-case-invite`` or one of its two siblings (CM-11-011).

    Because the Invite is queued after the replay, the invitee's inbox reaches
    it only once every replayed entry before it has been applied, one at a
    time.  The wait is therefore gated on that backfill (EDF-06, ADR-0058):
    each poll that finds more of the case's ledger entries in the invitee's
    store restarts *timeout_seconds*, so a long backfill under CI load is
    waited for and a stalled one fails (#4424).  The count comes from the
    unrehydrated ledger collection, not a store dump (#4600), which saves
    rehydration but still moves every entry per poll.

    Args:
        client: DataLayerClient connected to the invitee container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        invitee_id: Full URI of the joined participant.
        timeout_seconds: Seconds the invitee's ledger copy of the case may go
            without advancing before the wait gives up.
        poll_interval: Seconds between DataLayer poll attempts.
        progress_ceiling: Seconds after which the wait gives up however far
            the backfill is still advancing.

    Returns:
        The full-case Invite activity ID string.

    Raises:
        AssertionError: If no matching Invite is found before the backfill
            stalls or *progress_ceiling* passes.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_case_invite_for(
            obj, case_id, invitee_id, full_case=True
        ),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        progress_fn=lambda: _count_case_ledger_entries(client, case_id),
        progress_ceiling=progress_ceiling,
        log_msg=(
            f"Found full-case Invite for actor {invitee_id} on case"
            f" {case_id}: %s"
        ),
        error_msg=(
            f"Timed out waiting for the full-case Invite for actor"
            f" {invitee_id!r} on case {case_id!r} to appear in DataLayer at"
            f" {client.base_url}"
        ),
    )


def _is_ownership_transfer_offer_for(
    obj_data: dict, case_id: str, transferee_id: str
) -> bool:
    """Return True if *obj_data* is a forwarded Offer(VulnerabilityCase) for *transferee_id*.

    The CaseActor creates a NEW Offer when forwarding an ownership-transfer Offer
    to the transferee (CM-21-005).  The forwarded Offer has::

        type   = "Offer"
        target = transferee_id      # the actor being offered ownership,
                                    # inline Actor or its id (DL-08-003)
        object = case_id            # the VulnerabilityCase being transferred

    The original Vendor Offer (addressed to the CaseActor, target=case_actor_id)
    does NOT match this discriminator, so polling for the forwarded Offer on
    Coordinator's DataLayer correctly skips the original.
    """
    offer = _received_activity(obj_data)
    if offer.get("type") != "Offer":
        return False
    target_raw = offer.get("target")
    target_id = (
        target_raw.get("id") if isinstance(target_raw, dict) else target_raw
    )
    if target_id != transferee_id:
        return False
    inner = offer.get("object")
    inner_id = inner.get("id") if isinstance(inner, dict) else inner
    return inner_id == case_id


def find_ownership_transfer_offer_for_actor(
    client: DataLayerClient,
    case_id: str,
    transferee_id: str,
    timeout_seconds: float = 90.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until the CaseActor's forwarded Offer(VulnerabilityCase) for *transferee_id* arrives.

    In the ADR-0053 ownership-transfer flow, Vendor1's Offer is addressed to the
    CaseActor (``to=[case_actor_id]``).  ``OfferCaseOwnershipTransferReceivedUseCase``
    then creates a NEW forwarded Offer with a different ID and delivers it to the
    transferee's inbox.  Polling for the *original* offer ID with
    ``wait_for_object_stored`` will never succeed on the transferee's container
    because the original Offer is only stored in the CaseActor's DataLayer.

    This helper scans *client*'s DataLayer for any
    ``Offer(target=transferee_id, object=case_id)`` (``target`` an inline Actor
    or its id) and returns its ID so the
    demo can drive the ``accept-case-ownership-transfer`` trigger with the correct
    (forwarded) offer ID.

    Args:
        client: DataLayerClient connected to the transferee's container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        transferee_id: Full URI of the actor being offered case ownership.
        timeout_seconds: Maximum time to wait before raising (default: 90 s).
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The forwarded offer activity ID string.

    Raises:
        AssertionError: If no matching Offer is found within *timeout_seconds*.

    Spec: CM-21-005.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_ownership_transfer_offer_for(
            obj, case_id, transferee_id
        ),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        log_msg=(
            f"Found forwarded Offer(VulnerabilityCase) for"
            f" transferee {transferee_id} on case {case_id}: %s"
        ),
        error_msg=(
            f"Timed out waiting for forwarded Offer(VulnerabilityCase) for"
            f" transferee {transferee_id!r} on case {case_id!r} to appear in"
            f" DataLayer at {client.base_url} — CaseActor outbox delivery may"
            " not have completed (CM-21-005)"
        ),
    )


def _is_cp_offer_for_case(obj_data: dict, case_id: str) -> bool:
    """Return True if *obj_data* holds an Offer(CaseParticipant) for *case_id*."""
    offer = _received_activity(obj_data)
    if offer.get("type") != "Offer":
        return False
    target_raw = offer.get("target")
    target_id = (
        target_raw.get("id") if isinstance(target_raw, dict) else target_raw
    )
    if target_id != case_id:
        return False
    inner = offer.get("object")
    if not isinstance(inner, dict):
        return False
    return bool(
        inner.get("type") in ("CaseParticipant", "as_CaseParticipant")
        or inner.get("case_roles")
    )


def find_cp_offer_for_case(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until an Offer(CaseParticipant) for *case_id* appears in DataLayer.

    After a Coordinator sends suggest-actor-to-case, the CaseActor processes the
    Offer(Actor, Case) and forwards an Offer(CaseParticipant) to the Case
    Owner's inbox (ADR-0026).  This helper polls the Case Owner's DataLayer for
    any received Offer whose ``target`` matches *case_id* and whose ``object``
    resembles a CaseParticipant, so the demo can drive the approve step.  It
    reads intake's archive, the only record holding the participant inline.

    Args:
        client: DataLayerClient connected to the Case Owner's container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The offer activity ID string.

    Raises:
        AssertionError: If no such offer is found within *timeout_seconds*.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_cp_offer_for_case(obj, case_id),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        log_msg=f"Found Offer(CaseParticipant) for case {case_id}: %s",
        error_msg=(
            f"Timed out waiting for Offer(CaseParticipant) for case"
            f" {case_id!r} to appear in DataLayer at {client.base_url}"
        ),
    )


def case_actor_participant_id_in(case: as_VulnerabilityCase) -> str | None:
    """Return the CaseActor's actor URI from *case*'s participant index.

    The read-free half of :func:`find_case_actor_participant_id`, for callers
    that already hold the case (e.g. the one
    :func:`~vultron.demo.helpers.workflow.setup_canonical_case` just polled for)
    and would otherwise have to name a store to re-read it from.
    """
    for actor_id in case.actor_participant_index:
        if strip_id_prefix(actor_id).startswith(CASE_ACTOR_SLUG):
            return actor_id
    return None


def find_case_actor_participant_id(
    client: DataLayerClient,
    case_id: str,
) -> str | None:
    """Return the CaseActor's *actor* URI for *case_id* from *client*'s replica.

    Scans ``actor_participant_index`` for an actor ID whose bare segment starts
    with ``"case-actor"``.  A single read, not a poll: callers use it to resolve
    the CaseActor's URI once the case replica is already known to be present.

    The index is keyed by actor URI (its values are the participant-record
    URIs), so what comes back names the CaseActor itself — it is usable as a
    ``DataLayerClient.dl_path`` actor scope, which is what
    :func:`resolve_case_actor_store_id` builds on.

    Args:
        client: DataLayerClient connected to any container holding the case.
        case_id: Full URI of the ``as_VulnerabilityCase``.

    Returns:
        The CaseActor's actor URI, or ``None`` when the case is unreadable
        or has no CaseActor participant.
    """
    try:
        case_data = client.get(client.dl_path(case_id))
        return case_actor_participant_id_in(
            as_VulnerabilityCase.model_validate(case_data)
        )
    except Exception:  # noqa: BLE001, S110  # ruff-baseline #3326
        pass
    return None


def wait_for_case_actor_ledger_event(
    client: DataLayerClient,
    case_id: str,
    event_type: str,
    timeout_seconds: float = PARTICIPANT_JOIN_TIMEOUT,
    poll_interval: float = 0.5,
) -> None:
    """Poll the CaseActor's *own* ledger, read through *client*, for *event_type*.

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
        event_type: The ``event_type`` value to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If no such entry appears within *timeout_seconds*.
    """
    wait_for_event_type_in_ledger(
        client=client,
        case_id=case_id,
        event_type=event_type,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        dl_actor_id=resolve_case_actor_store_id(client, case_id),
    )


class SharedBudget:
    """One timeout shared by consecutive waits on the same delivery chain.

    When several replicas are fed by one fan-out, waiting on each with its
    own full timeout multiplies the worst case by the number of replicas and
    hides which hop was slow.  A shared budget bounds the whole fan-out once:
    each wait is given what is left.  A wait that starts with nothing left
    still checks its condition once (:func:`_poll_until`), so a replica that
    has already caught up passes, and one that has not fails at once with
    that wait's own message — the budget itself says only how much was left
    (``repr(budget)``), which the scenario logs on exhaustion.

    Args:
        timeout_seconds: The total budget, started on construction.
    """

    def __init__(self, timeout_seconds: float) -> None:
        self._total = timeout_seconds
        self._deadline = time.monotonic() + timeout_seconds

    def remaining(self) -> float:
        """Seconds left, never negative."""
        return max(0.0, self._deadline - time.monotonic())

    def __repr__(self) -> str:
        return (
            f"SharedBudget(total={self._total:.1f}s,"
            f" remaining={self.remaining():.1f}s)"
        )


def resolve_case_actor_store_id(
    client: DataLayerClient,
    case_id: str,
) -> str | None:
    """Return the CaseActor URI to read *case_id*'s authoritative state through.

    A CaseActor owns the case: it is where the participant records are written
    when it applies an RM/EM transition.  Under ADR-0073#peer-records-in-knowers-store it also has
    a store of its own, so a participant's authoritative state is *not* visible
    in the store of the actor that merely self-hosts it — the host's replica
    only advances when a ledger entry it recognises tells it to, and the
    per-participant RM transitions the CaseActor makes are not ledgered as
    ``add_participant_status_to_participant`` events.  Reading the host's
    replica therefore reports a stale ``RM.START`` indefinitely.

    Returns ``None`` — meaning "read *client*'s own actor, as before" — when
    either the case has no CaseActor participant, or the CaseActor lives in some
    other container.  In the latter case *client* cannot address its store at
    all, and scoping to it would 404 on every poll rather than fall back.

    Args:
        client: DataLayerClient for the container to read through.
        case_id: Full URI of the ``as_VulnerabilityCase``.

    Returns:
        The CaseActor's actor URI when it is co-hosted with *client*'s own
        actor, else ``None``.
    """
    case_actor_id = find_case_actor_participant_id(client, case_id)
    if case_actor_id is None or client.actor_id is None:
        return None
    if (
        parse_id(case_actor_id)["base_url"]
        != parse_id(client.actor_id)["base_url"]
    ):
        logger.debug(
            "CaseActor %s is not hosted by %s — reading %s's own store",
            case_actor_id,
            client.base_url,
            client.actor_id,
        )
        return None
    return case_actor_id


def case_manager_store(
    client: DataLayerClient,
    case_id: str,
    case_manager_client: DataLayerClient | None = None,
) -> tuple[DataLayerClient, str | None]:
    """Return ``(client, dl_actor_id)`` to read *case_id*'s CASE_MANAGER store.

    When the CaseActor runs in its own container — the dedicated case-actor
    container of the Docker scenarios (DEMOMA-06-004) — no participant's
    container can address its store, and a participant's replica is no
    substitute: the CaseActor applies some participant transitions without a
    ledger entry, so a replica can lag them indefinitely.  *case_manager_client*
    names that container, bound to the CaseActor, and is read as-is.

    Without one, *client* is read, scoped to a CaseActor it co-hosts
    (:func:`resolve_case_actor_store_id`) — the single-container exchange demos.

    Args:
        client: The participant client the caller would otherwise read through.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        case_manager_client: Client for the CaseActor's own container, if the
            caller has one.

    Returns:
        The client to read through and the ``dl_path`` actor scope to pass it.
    """
    if case_manager_client is not None:
        return case_manager_client, None
    return client, resolve_case_actor_store_id(client, case_id)


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
        forwarding pattern — e.g. ``OfferCaseOwnershipTransferReceivedUseCase``
        creating a new forwarded Offer), the original *obj_id* will never
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

    The gate for "the receiver took in this delivery": intake archives every
    activity it receives as a ``ReceivedActivityRecord`` under the receiver's
    key (CLP-10-017, ADR-0111), and that record is the only place a received
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


# ---------------------------------------------------------------------------
# Participant-state polling helpers
# ---------------------------------------------------------------------------

ParticipantDimension = Literal["rm", "vf", "d"]
"""The ``ParticipantStatus`` dimension fields a participant poll can read."""


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
    deadline = time.monotonic() + timeout_seconds
    poll_count = 0
    while time.monotonic() < deadline:
        poll_count += 1
        participant = _fetch_participant(
            client, case_id, actor_id, dl_actor_id=dl_actor_id
        )
        if participant is not None:
            latest = participant.participant_status
            n_statuses = len(participant.participant_statuses or [])
            current_val = (
                dimension_state(latest, dimension)
                if latest is not None
                else None
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
            if latest is not None and current_val in expected_states:
                return
        else:
            logger.debug(
                "_wait_for_participant_status_field poll #%d: "
                "actor=%r case=%r participant=<not found>",
                poll_count,
                actor_id,
                case_id,
            )
        time.sleep(poll_interval)

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


def _is_embargo_invite_for(
    obj_data: dict, embargo_id: str, invitee_id: str
) -> bool:
    """Return True if *obj_data* holds an ``Invite`` of *embargo_id* to *invitee_id*.

    The relayed Invite names its embargo in ``object`` (inline or by id) and its
    invitee as the sole ``to`` recipient (EP-09-010).
    """
    invite = _received_activity(obj_data)
    if invite.get("type") != "Invite":
        return False
    inner = invite.get("object")
    inner_id = inner.get("id") if isinstance(inner, dict) else inner
    if inner_id != embargo_id:
        return False
    return invitee_id in recipient_ids(invite.get("to"))


def find_embargo_invite_for_actor(
    client: DataLayerClient,
    embargo_id: str,
    invitee_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll until the CASE_MANAGER's relayed ``Invite(EmbargoEvent)`` arrives.

    The CASE_MANAGER relays every embargo proposal, first or revised, to each
    participant but the proposer (EP-09-002).  The invitee answers only an
    Invite addressed to it (EP-09-003), so a demo polls the invitee's own
    DataLayer for it rather than reading another participant's mail.

    Args:
        client: DataLayerClient connected to the invitee's container.
        embargo_id: Full URI of the proposed ``EmbargoEvent``.
        invitee_id: Full URI of the invited actor.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The relayed Invite's activity ID.

    Raises:
        AssertionError: If no matching Invite is found within *timeout_seconds*.
    """
    return _poll_datalayer_for(
        client=client,
        object_types=_RECEIVED_ACTIVITY_TYPES,
        discriminator_fn=lambda obj: _is_embargo_invite_for(
            obj, embargo_id, invitee_id
        ),
        id_fn=_received_activity_id,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        log_msg=f"Found Invite of embargo {embargo_id} for {invitee_id}: %s",
        error_msg=(
            f"Timed out waiting for the relayed Invite of embargo"
            f" {embargo_id!r} to actor {invitee_id!r} to appear in the"
            f" DataLayer at {client.base_url}"
        ),
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

    deadline = time.monotonic() + timeout_seconds
    poll_count = 0
    while time.monotonic() < deadline:
        poll_count += 1
        participant = _fetch_participant(client, case_id, actor_id)
        if participant is not None:
            latest = participant.participant_status
            if latest is not None:
                cs = getattr(latest, "case_status", None)
                pxa = dimension_state(cs, "pxa")
                logger.debug(
                    "wait_for_participant_pxa_state poll #%d: "
                    "actor=%r case=%r pxa=%r expected=%r",
                    poll_count,
                    actor_id,
                    case_id,
                    pxa,
                    expected_states,
                )
                if pxa in expected_states:
                    return
        time.sleep(poll_interval)

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


def wait_for_case_attributed_to(
    client: DataLayerClient,
    case_id: str,
    expected_attributed_to: str,
    timeout_seconds: float = PARTICIPANT_JOIN_TIMEOUT,
    poll_interval: float = 0.5,
) -> None:
    """Poll until *case_id*'s ``attributed_to`` field equals *expected_attributed_to*.

    Observes the ownership transfer on *client*'s replica of the case.  The
    CaseActor's own store is the authority (CM-21-002, CM-21-004); every other
    replica — the old owner's included — learns the new owner only from the
    ``Announce(CaseLedgerEntry)`` fan-out of the ``update_case_owner`` entry,
    applied by ``ApplyOwnershipTransferFromLedgerNode`` (CM-21-007,
    CLP-07-013).  So this reads the
    replica whose view is being asserted (EDF-06-002); to gate on the commit
    itself, use :func:`wait_for_case_actor_ledger_event` first (#3602).

    Args:
        client: DataLayerClient connected to the committing actor's container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected_attributed_to: The actor URI that must appear as
            ``attributed_to``.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the field does not match within *timeout_seconds*.

    Spec: EDF-06-001, EDF-06-002.
    """

    def _check() -> bool:
        case_data = client.get(client.dl_path(case_id))
        if not isinstance(case_data, dict):
            return False
        attributed_to = case_data.get("attributedTo") or case_data.get(
            "attributed_to"
        )
        if isinstance(attributed_to, dict):
            attributed_to = attributed_to.get("id") or attributed_to.get("id_")
        if attributed_to == expected_attributed_to:
            logger.info(
                "Case %s attributed_to updated to %s",
                case_id,
                expected_attributed_to,
            )
            return True
        return False

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for case {case_id!r}"
        f" attributed_to={expected_attributed_to!r}"
        f" on container {client.base_url}",
        swallow_exceptions=True,
    )


def wait_for_initialized_case(
    client: DataLayerClient,
    report_id: str,
    timeout_seconds: float = PARTICIPANT_JOIN_TIMEOUT,
    poll_interval: float = 0.5,
) -> as_VulnerabilityCase:
    """Poll the CaseActor's store until *report_id*'s case has participants.

    After ``ProposeReportCaseToActorNode`` runs during report validation the
    CaseActor creates the canonical ``VulnerabilityCase`` with vendor, reporter,
    and CaseActor as initial participants.  A one-shot read races this creation;
    this helper polls instead, giving the BT time to complete.

    The CaseActor URI is derived from *report_id* via
    :func:`~vultron.demo.utils.case_actor_id_for_report`.  The CaseActor
    identity is constant per container, so its store may hold several cases;
    only the case whose ``vulnerability_reports`` include *report_id* counts
    (:func:`~vultron.demo.utils.case_references_report`).

    Args:
        client: DataLayerClient for the container that hosts the CaseActor.
        report_id: URI of the report whose proposal created the case.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Returns:
        The ``as_VulnerabilityCase`` for *report_id* with non-empty
        ``case_participants``.

    Raises:
        AssertionError: If no initialized VulnerabilityCase for *report_id*
            appears within *timeout_seconds*.

    Spec: ISSUE-2359 / ADR-0041.
    """
    case_actor_id = case_actor_id_for_report(report_id)
    found: list[as_VulnerabilityCase] = []

    def _check() -> bool:
        cases_by_id: dict = client.get(
            client.dl_path("VulnerabilityCases/", actor_id=case_actor_id)
        )
        for case_raw in cases_by_id.values():
            case = as_VulnerabilityCase(**case_raw)
            if case.case_participants and case_references_report(
                case, report_id
            ):
                found.append(case)
                logger.info(
                    "Initialized VulnerabilityCase for report %s found in"
                    " CaseActor store %s: %s",
                    report_id,
                    case_actor_id,
                    case.id_,
                )
                return True
        return False

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for initialized VulnerabilityCase for report"
        f" {report_id!r} in CaseActor store {case_actor_id!r}"
        f" at {client.base_url}",
        swallow_exceptions=True,
    )
    assert found, (
        "invariant: _poll_until returns only when _check returned True"
    )
    return found[0]


def wait_for_pending_inbox_quiescent(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = CROSS_CONTAINER_TIMEOUT,
    poll_interval: float = 0.5,
) -> None:
    """Poll until the ``VultronPendingCaseInbox`` for *case_id* is empty or absent.

    ``VultronPendingCaseInbox`` holds deferred activity IDs for a case that has
    not yet been seeded in the recipient's DataLayer (ADR-0059).  This gate
    confirms that the pending inbox has been drained — i.e. the case seed has
    arrived and all buffered activities were processed.

    ``LedgerGapBuffer`` (ADR-0037) is intentionally excluded: it is an
    in-memory structure not observable via the DataLayer API and therefore
    cannot be used as a harness gate.

    Args:
        client: DataLayerClient connected to the container to check.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the pending inbox is still non-empty within
            *timeout_seconds*.

    Spec: EDF-06-001.
    """
    pending_id = VultronPendingCaseInbox.build_id(case_id)

    def _check() -> bool:
        try:
            data = client.get(client.dl_path(pending_id))
            if not data:
                return True
            activity_ids = data.get("activity_ids", [])
            return len(activity_ids) == 0
        except Exception:  # noqa: BLE001  # ruff-baseline #3326
            return True

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for PendingCaseInbox for case {case_id!r} to drain"
        f" on container {client.base_url}",
        swallow_exceptions=False,
    )
