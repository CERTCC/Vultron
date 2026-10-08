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

from vultron.adapters.utils import parse_id, strip_id_prefix
from vultron.core.models.pending_case_inbox import (
    VultronPendingCaseInbox,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.helpers.verification import (
    _all_fetchable_participants_rm_closed,
    _fetch_participant,
)
from vultron.demo.utils import (
    CASE_ACTOR_SLUG,
    DataLayerClient,
    case_actor_id_for_report,
    case_references_report,
    demo_check,
    logfmt,
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
LATE_JOINER_COVERAGE_TIMEOUT: float = 45.0


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
            *timeout_seconds*. When exceptions were swallowed, the last one is
            named in the message — a condition that never *ran* is a different
            fault from one that ran and stayed false, and reporting both as a
            bare timeout sends the reader looking for a slow protocol instead of
            a broken read.
    """
    # The condition is always tried at least once, even with no time left: a
    # wait handed the tail of a shared budget (SharedBudget) must still succeed
    # when its effect has already landed, and fail only when it has not.
    deadline = time.monotonic() + timeout_seconds
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
        if time.monotonic() >= deadline:
            break
        time.sleep(poll_interval)

    if last_exc is not None:
        raise AssertionError(
            f"{error_msg} — the check never completed: every attempt raised"
            f" {type(last_exc).__name__}: {last_exc}"
        ) from last_exc
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


def wait_for_finder_case(
    finder_client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 30.0,
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
    expected_actor_ids: "set[str]",
    # 15 s: conservative cross-container delivery budget (temporal per EDF-06-006).
    timeout_seconds: float = CROSS_CONTAINER_TIMEOUT,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until the case on *vendor_client* reflects all *expected_actor_ids*.

    Gates on identity: all actors in *expected_actor_ids* must appear in
    ``actor_participant_index``.  A count check (``>= N``) would accept the
    wrong participant set — for example CaseActor + Finder instead of
    CaseActor + Vendor — masking a missing invite delivery (EDF-06-002).

    Args:
        vendor_client: DataLayerClient for the container to poll.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected_actor_ids: Set of actor URIs that must all be present as
            participants before the gate passes.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Read this actor's store on the container instead of
            the client's own — typically a self-hosted CaseActor, the only
            store that holds an invitee that never joined (CM-11-006).

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
    fvv omitted the loop entirely — its two bare
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
    ``AnnounceLedgerEntryReceivedUseCase`` (LedgerFanout receive side).

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
        raw = finder_client.get(finder_client.dl_path("CaseLedgerEntrys/"))
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

    Use this before reading the authoritative tail index in close phases to
    ensure the ``close_case`` entry (committed asynchronously by the CaseActor's
    auto-close BT after the last RM.CLOSED) is present before we snapshot the
    tail.  Without this wait, the tail index may exclude ``close_case``, causing
    a coverage-wait 'success' for the wrong tail and a gapped ledger dump
    (issue #1772 Bug B).

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
# Generic DataLayer scan helper
# ---------------------------------------------------------------------------


def _poll_datalayer_for(
    client: DataLayerClient,
    discriminator_fn: Callable[[dict], bool],
    timeout_seconds: float,
    poll_interval: float,
    log_msg: str,
    error_msg: str,
    id_fn: Callable[[str, dict], str] | None = None,
) -> str:
    """Poll the client's own DataLayer until *discriminator_fn* matches.

    The path is ``client.dl_path()`` — the *actor-scoped* collection, not the
    retired unscoped ``/datalayer/``.  Under ADR-0073 there is no store that is
    not some actor's own, so a poll must name whose store it is reading.

    Scans the full DataLayer dict on each tick and calls *discriminator_fn*
    on every ``dict``-typed value.  Returns the matching object's raw ID
    string on the first match.

    Args:
        client: DataLayerClient to poll.
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

    Returns:
        The ID of the first matching object, as *id_fn* derives it.

    Raises:
        AssertionError: If no matching object is found within *timeout_seconds*.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            all_objects = client.get(client.dl_path())
            if isinstance(all_objects, dict):
                for raw_id, obj_data in all_objects.items():
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
        except Exception:  # noqa: BLE001, S110  # ruff-baseline #3326
            pass
        time.sleep(poll_interval)
    raise AssertionError(error_msg)


# ---------------------------------------------------------------------------
# Invite polling helpers
# ---------------------------------------------------------------------------


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
    if obj_data.get("type") != "ReceivedActivityRecord":
        return obj_data
    activity = obj_data.get("activity")
    if not isinstance(activity, dict):
        raise AssertionError(  # noqa: TRY004 — demo_check assertion, not a type error
            f"received-activity record {obj_data.get('id')!r} wraps no"
            f" activity: {activity!r}"
        )
    return activity


def _received_activity_id(raw_id: str, obj_data: dict) -> str:
    """The sender's id for the received activity *obj_data* holds.

    A bare activity is stored under the sender's id (*raw_id*); a record is
    stored under its own id and names the activity's id inside.

    Raises:
        AssertionError: when a record's activity carries no id.
    """
    if obj_data.get("type") != "ReceivedActivityRecord":
        return raw_id
    activity_id = _received_activity(obj_data).get("id")
    if not activity_id:
        raise AssertionError(
            f"received-activity record {raw_id!r} holds an activity with no id"
        )
    return str(activity_id)


def _is_case_invite_for(obj_data: dict, case_id: str, invitee_id: str) -> bool:
    """Return True if *obj_data* holds a case Invite for *invitee_id*/*case_id*.

    A stub Invite names its case in the stub's ``caseId`` (CM-11-013); the
    stub's own ``id`` is ``<case-id>/stub`` and is never parsed.  A full-case
    Invite names the case by URI (AKM-02-003).
    """
    invite = _received_activity(obj_data)
    if invite.get("type") != "Invite":
        return False
    target_raw = invite.get("target")
    if isinstance(target_raw, dict):
        target_case_id = (
            target_raw.get("caseId")
            if target_raw.get("type")
            == VultronObjectType.VULNERABILITY_CASE_STUB.value
            else target_raw.get("id")
        )
    else:
        target_case_id = target_raw
    if target_case_id != case_id:
        return False
    inner = invite.get("object")
    inner_id = inner.get("id") if isinstance(inner, dict) else inner
    return inner_id == invitee_id


def read_received_activity_for(
    client: DataLayerClient, activity_id: str
) -> dict:
    """The activity *activity_id* as the actor behind *client* holds it.

    Reads intake's archive record or the inbox's deferred copy, as
    :func:`_received_activity` describes.

    Raises:
        AssertionError: If the actor holds no activity *activity_id*.
    """
    all_objects = client.get(client.dl_path())
    if isinstance(all_objects, dict):
        for raw_id, obj_data in all_objects.items():
            if (
                isinstance(obj_data, dict)
                and _received_activity_id(str(raw_id), obj_data) == activity_id
            ):
                return _received_activity(obj_data)
    raise AssertionError(
        f"{client.base_url} holds no received activity {activity_id!r}"
    )


def assert_received_from(
    client: DataLayerClient,
    activity_id: str,
    sender_id: str,
    consequence: str,
) -> None:
    """Assert the actor behind *client* received *activity_id* from *sender_id*.

    Args:
        client: DataLayerClient for the receiving actor's container.
        activity_id: The sender's id for the received activity.
        sender_id: The actor the activity must have been emitted as.
        consequence: What goes wrong when it was not, for the failure message.

    Raises:
        AssertionError: If the activity is not held, or another actor sent it.
    """
    actor = read_received_activity_for(client, activity_id).get("actor")
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


def _is_ownership_transfer_offer_for(
    obj_data: dict, case_id: str, transferee_id: str
) -> bool:
    """Return True if *obj_data* is a forwarded Offer(VulnerabilityCase) for *transferee_id*.

    The CaseActor creates a NEW Offer when forwarding an ownership-transfer Offer
    to the transferee (CM-21-005).  The forwarded Offer has::

        type   = "Offer"
        target = transferee_id      # the actor being offered ownership
        object = case_id            # the VulnerabilityCase being transferred

    The original Vendor Offer (addressed to the CaseActor, target=case_actor_id)
    does NOT match this discriminator, so polling for the forwarded Offer on
    Coordinator's DataLayer correctly skips the original.
    """
    if obj_data.get("type") != "Offer":
        return False
    target_raw = obj_data.get("target")
    target_id = (
        target_raw.get("id") if isinstance(target_raw, dict) else target_raw
    )
    if target_id != transferee_id:
        return False
    inner = obj_data.get("object")
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
    ``Offer(target=transferee_id, object=case_id)`` and returns its ID so the
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
        discriminator_fn=lambda obj: _is_ownership_transfer_offer_for(
            obj, case_id, transferee_id
        ),
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
    """Return True if *obj_data* looks like an Offer(CaseParticipant) for *case_id*."""
    if obj_data.get("type") != "Offer":
        return False
    target_raw = obj_data.get("target")
    target_id = (
        target_raw.get("id") if isinstance(target_raw, dict) else target_raw
    )
    if target_id != case_id:
        return False
    inner = obj_data.get("object")
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
    any Offer whose ``target`` matches *case_id* and whose ``object`` resembles
    a CaseParticipant, so the demo can drive the approve step.

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
        discriminator_fn=lambda obj: _is_cp_offer_for_case(obj, case_id),
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


def wait_for_object_stored(
    client: DataLayerClient,
    obj_id: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll *client*'s DataLayer until *obj_id* appears.

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

    Raises:
        AssertionError: If *obj_id* does not appear within *timeout_seconds*.

    Spec: EDF-06-004.
    """

    def _check() -> bool:
        try:
            data = client.get(client.dl_path(obj_id))
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

    def _check() -> bool:
        for obj_id in sorted(missing):
            try:
                if client.get(client.dl_path(obj_id, actor_id=receiver_id)):
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


# ---------------------------------------------------------------------------
# Participant-state polling helpers
# ---------------------------------------------------------------------------


def _wait_for_participant_status_field(
    client: DataLayerClient,
    case_id: str,
    actor_id: str,
    field_name: str,
    expected_states: "set",
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.25,
    dl_actor_id: str | None = None,
) -> None:
    """Poll until *actor_id*'s latest participant status field is in *expected_states*.

    Private shared implementation for :func:`wait_for_participant_vf_state`,
    :func:`wait_for_participant_d_state`, and :func:`wait_for_participant_rm_state`.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        field_name: Attribute name on the participant status object to check
            (e.g. ``"vf_state"``, ``"d_state"``, or ``"rm_state"``).
        expected_states: Set of state values that satisfy the condition.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — see :func:`_fetch_participant`.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
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
                getattr(latest, field_name) if latest is not None else None
            )
            logger.debug(
                "_wait_for_participant_status_field poll #%d: "
                "actor=%r case=%r participant=%r "
                "n_statuses=%d field=%r current=%r expected=%r",
                poll_count,
                actor_id,
                case_id,
                participant.id_,
                n_statuses,
                field_name,
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
        getattr(latest, field_name) if latest is not None else "unknown"
    )
    store = dl_actor_id or client.actor_id
    logger.debug(
        "_wait_for_participant_status_field timed out after %.1f s: "
        "actor=%r case=%r field=%r current=%r expected=%r store=%r",
        timeout_seconds,
        actor_id,
        case_id,
        field_name,
        current_val,
        expected_states,
        store,
    )
    raise AssertionError(
        f"Timed out waiting for actor '{actor_id}' {field_name} to be in "
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
    """Poll until *actor_id*'s latest participant ``vf_state`` is in
    *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``CS_vf`` values that satisfy the condition.
        timeout_seconds: Maximum time to wait (default: 30 s).
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — typically a self-hosted CaseActor.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    _wait_for_participant_status_field(
        client,
        case_id,
        actor_id,
        "vf_state",
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
    """Poll until *actor_id*'s latest participant ``d_state`` is in
    *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``CS_d`` values that satisfy the condition.
        timeout_seconds: Maximum time to wait (default: 30 s).
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — typically a self-hosted CaseActor.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    _wait_for_participant_status_field(
        client,
        case_id,
        actor_id,
        "d_state",
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
        return case.current_status.em_state == expected and (
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
    recipients = invite.get("to")
    if not isinstance(recipients, list):
        recipients = [recipients]
    return invitee_id in [
        r.get("id") if isinstance(r, dict) else r for r in recipients
    ]


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
    """Poll until *actor_id*'s consent row for *embargo_id* is ``ACCEPTED``.

    An Accept always marks the accepted embargo's own row ``ACCEPTED``, including
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
        lambda value: value == EmbargoConsentState.ACCEPTED,
        f"consent for {embargo_id!r} to be ACCEPTED",
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
    """Poll until *actor_id*'s latest participant ``rm_state`` is in
    *expected_states*.

    Args:
        client: DataLayerClient for the target container.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        actor_id: Full URI of the actor to check.
        expected_states: Set of ``RM`` values that satisfy the condition.
        timeout_seconds: Maximum time to wait (default: 30 s).
        poll_interval: Seconds between DataLayer poll attempts.
        dl_actor_id: Full URI of the actor whose *store* to read, when that is
            not the client's own actor — typically a self-hosted CaseActor.

    Raises:
        AssertionError: If the state is not reached within *timeout_seconds*.
    """
    _wait_for_participant_status_field(
        client,
        case_id,
        actor_id,
        "rm_state",
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

    ``pxa_state`` is nested at ``participant.participant_status.case_status
    .pxa_state`` and cannot be reached by the generic
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
                pxa = (
                    getattr(cs, "pxa_state", None) if cs is not None else None
                )
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
    pxa = getattr(cs, "pxa_state", None) if cs is not None else None
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
    ``Announce(CaseLedgerEntry)`` fan-out applied by
    ``ApplyOwnershipTransferFromLedgerNode`` (CM-21-007).  So this reads the
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
