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

"""LedgerFanout log-replication helpers for demo workflows.

Provides :func:`verify_replica_state` to assert that a replica actor's case
state matches the authoritative actor, and the two shared
scenario-phase helpers of DEMOMA-23: :func:`wait_for_replica_ledger_coverage`
(the read-authority-tail-then-poll-each-replica loop, DEMOMA-23-005) and
:func:`run_sync_verification_phase` (the whole replica sync-verification
phase, DEMOMA-23-007). A scenario module never calls
``wait_for_contiguous_ledger_coverage`` or ``_get_log_entries_for_case``
itself (DEMOMA-23-006).
"""

import logging
from collections.abc import Collection, Sequence
from typing import Optional

import httpx2 as httpx

from vultron.demo.helpers.polling import (
    CROSS_CONTAINER_TIMEOUT,
    LATE_JOINER_COVERAGE_TIMEOUT,
    LEDGER_COVERAGE_TIMEOUT,
    _client_in,
    _poll_until,
    wait_for_case_on_container,
    wait_for_contiguous_ledger_coverage,
    wait_for_participants_on_replicas,
)
from vultron.demo.utils import DataLayerClient, demo_check, demo_gate
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_ref_id(ref: object) -> Optional[str]:
    """Extract the string ID from an object, ``as_Link``, or string reference."""
    if ref is None:
        return None
    if isinstance(ref, str):
        return ref
    if hasattr(ref, "id_"):
        return str(ref.id_)  # type: ignore[union-attr]
    if hasattr(ref, "href"):
        return str(ref.href)  # type: ignore[union-attr]
    return str(ref)


def _get_log_entries_for_case(
    client: DataLayerClient, case_id: str
) -> list[dict]:
    """Return all ``CaseLedgerEntry`` dicts for *case_id* from the DataLayer.

    .. deprecated::
        This function performs client-side filtering over the full DataLayer
        dump.  Prefer the server-side endpoint instead:
        ``GET /actors/{actor_id}/demo/cases/{case_id}/log``
        (see ``demo_triggers.demo_get_case_ledger``).
    """
    raw = client.get(client.dl_path("CaseLedgerEntrys/"))
    if not isinstance(raw, dict):
        return []
    return [
        v
        for v in raw.values()
        if isinstance(v, dict) and v.get("case_id") == case_id
    ]


# ---------------------------------------------------------------------------
# Public LedgerFanout helpers
# ---------------------------------------------------------------------------


def _case_or_none(client: DataLayerClient, case_id: str) -> Optional[dict]:
    """Read a case from *client*'s own store, or ``None`` if it holds no copy.

    A store that has no copy of the case answers 404, and both the real client and
    the TestClient double raise ``HTTPStatusError`` for that. Callers here want to
    *assert* on absence in their own words, so the 404 is converted rather than
    propagated; anything else is a real transport fault and re-raises.

    This used to rely on ``client.get`` returning a falsy value for a missing
    case, which made the ``assert ... not found`` lines below unreachable against
    a client that raises — that is, against the real one. The demo double had been
    hiding it by raising ``AssertionError`` instead, which those asserts' callers
    happened to expect.
    """
    try:
        return client.get(client.dl_path(case_id))
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise


def verify_replica_state(
    auth_client: DataLayerClient,
    replica_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
    reporter_actor_id: str,
    auth_coverage_timeout_seconds: float = CROSS_CONTAINER_TIMEOUT,
    poll_interval_seconds: float = 0.5,
) -> None:
    """Verify that a replica actor's case state matches the authoritative state.

    Checks four properties:

    1. The same ``case_id`` exists in the replica's DataLayer.
    2. ``actor_participant_index`` keys are identical (same participant set).
    3. ``active_embargo`` references the same ID on both sides.
    4. Log-state hash consistency: both sides share the same tail entry hash.

    Args:
        auth_client: DataLayerClient connected to the authoritative container
            (the actor that owns/created the case).
        replica_client: DataLayerClient connected to the replica container
            (the actor that received a replicated copy).
        case_id: Full URI of the ``as_VulnerabilityCase`` being verified.
        vendor_actor_id: Full URI of the Vendor actor (retained for symmetry).
        reporter_actor_id: Full URI of the Reporter/Finder actor (retained for
            future participant-status checks).
        auth_coverage_timeout_seconds: How long to wait for the authoritative
            ledger to catch up to the replica's tail index before declaring
            divergence. Defaults to the cross-container delivery budget.
        poll_interval_seconds: Seconds between authoritative-ledger reads while
            waiting for it to cover the replica's tail index.

    Raises:
        AssertionError: If any replica invariant is violated, *including* a case
            that is absent from either store. An absent case reads as a 404, so
            it is converted here rather than allowed to surface as a transport
            error — which is the whole point of this function: it reports
            replica divergence in the demo's own terms.

    Spec: SYNC-02-002, D5-7-DEMOREPLCHECK-1.
    """
    auth_case_data = _case_or_none(auth_client, case_id)
    assert auth_case_data, f"Authoritative case {case_id!r} not found"
    auth_case = as_VulnerabilityCase.model_validate(auth_case_data)

    replica_case_data = _case_or_none(replica_client, case_id)
    assert replica_case_data, (
        f"Replica does not have a copy of case {case_id!r} — "
        "outbox delivery or inbox processing may have failed"
    )
    replica_case = as_VulnerabilityCase.model_validate(replica_case_data)

    # 1. Same case ID
    assert (
        replica_case.id_ == case_id
    ), f"Replica case ID mismatch: {replica_case.id_!r} != {case_id!r}"
    logger.info("✓ Replica case ID matches: %s", case_id)

    # 2. actor_participant_index keys match
    auth_index = auth_case.actor_participant_index or {}
    replica_index = replica_case.actor_participant_index or {}
    assert set(auth_index.keys()) == set(replica_index.keys()), (
        "Replica actor_participant_index key set differs from authoritative: "
        f"replica={set(replica_index.keys())} "
        f"auth={set(auth_index.keys())}"
    )
    logger.info(
        "✓ Replica actor_participant_index matches (%d participants)",
        len(replica_index),
    )

    # 3. active_embargo ID matches (if present on auth side)
    auth_embargo_id = _extract_ref_id(auth_case.active_embargo)
    replica_embargo_id = _extract_ref_id(replica_case.active_embargo)
    if auth_embargo_id is not None:
        assert auth_embargo_id == replica_embargo_id, (
            f"Replica active_embargo {replica_embargo_id!r} != "
            f"authoritative active_embargo {auth_embargo_id!r}"
        )
        logger.info("✓ Replica active_embargo matches: %s", auth_embargo_id)

    # 4. Log-state hash consistency
    #
    # Read the replica ledger first to fix the tail index we compare at, then
    # wait for the authoritative ledger to catch up to that index. The two
    # ledgers grow independently and new entries propagate between participants
    # with a delay (SYNC fanout), so at any single instant the authoritative
    # copy may not yet hold an entry the replica has already received. Asserting
    # a strict point-in-time superset therefore fires spuriously while an entry
    # is still in flight (issue #2768) — the read order does not matter, because
    # the entry is genuinely still arriving, not merely read in the wrong order.
    # Instead we poll the authoritative ledger until it covers the replica's
    # tail index, and only report divergence if it never does. The bounded wait
    # distinguishes "entry still arriving" from "entry the authoritative
    # single-writer never committed".
    replica_entries = _get_log_entries_for_case(replica_client, case_id)
    assert len(replica_entries) > 0, (
        "Replica has no CaseLedgerEntry records for the case — "
        "LedgerFanout replication did not complete"
    )
    replica_tail = max(replica_entries, key=lambda e: e["log_index"])
    compare_index = replica_tail["log_index"]

    # Filled in by the poll below; the final successful read is what we compare
    # against. An empty authoritative ledger simply never covers compare_index,
    # so it surfaces as the same divergence timeout rather than a separate case.
    auth_entries: list[dict] = []
    auth_entry_by_index: dict[int, dict] = {}

    def _auth_covers_replica_tail() -> bool:
        nonlocal auth_entries, auth_entry_by_index
        auth_entries = _get_log_entries_for_case(auth_client, case_id)
        auth_entry_by_index = {e["log_index"]: e for e in auth_entries}
        return compare_index in auth_entry_by_index

    _poll_until(
        _auth_covers_replica_tail,
        timeout_seconds=auth_coverage_timeout_seconds,
        poll_interval=poll_interval_seconds,
        error_msg=(
            f"Auth ledger never caught up to replica tail index "
            f"{compare_index} within {auth_coverage_timeout_seconds:g}s — the "
            "replica holds an index the authoritative single-writer never "
            "committed (hash-chain divergence)"
        ),
    )

    auth_at_compare = auth_entry_by_index[compare_index]
    auth_tail = max(auth_entries, key=lambda e: e["log_index"])
    if auth_tail["log_index"] > compare_index:
        logger.debug(
            "Auth has grown to index %d past the replica's tail index %d; "
            "comparing at the replica's tail",
            auth_tail["log_index"],
            compare_index,
        )
    assert auth_at_compare["entry_hash"] == replica_tail["entry_hash"], (
        f"Replica log tail hash {replica_tail['entry_hash']!r} != "
        f"authoritative log tail hash at index {compare_index} "
        f"{auth_at_compare['entry_hash']!r} — "
        "hash-chain replication integrity failure"
    )
    logger.info(
        "✓ Replica log tail hash matches auth: %s… (index=%d)",
        replica_tail["entry_hash"][:16],
        replica_tail["log_index"],
    )


# ---------------------------------------------------------------------------
# Shared scenario-phase helpers (DEMOMA-23-005, DEMOMA-23-007)
# ---------------------------------------------------------------------------

#: ``(replica_client, display_label)`` pairs, in the order they are polled.
ReplicaSpec = Sequence[tuple[DataLayerClient, str]]


def wait_for_replica_ledger_coverage(
    auth_client: DataLayerClient,
    replicas: ReplicaSpec,
    case_id: str,
    *,
    late_joiners: Sequence[DataLayerClient] = (),
    late_joiner_timeout: float = LATE_JOINER_COVERAGE_TIMEOUT,
    default_timeout: float = LEDGER_COVERAGE_TIMEOUT,
    phase_label: str = "sync-verification phase",
    causal: bool = True,
) -> list[DataLayerClient]:
    """Wait for every replica to hold the authority's ledger tail contiguously.

    Reads the authority's ``CaseLedgerEntry`` tail once, then polls each replica
    in *replicas* order until it holds indices ``0…tail`` (SYNC-10-004). When
    the authority holds no entries there is nothing to cover: every replica
    wait is skipped and every replica counts as covered, so a dependent state
    check still runs and reports the empty ledger loudly.

    This is the single implementation of the loop that every scenario module
    used to carry twice — once as the causal gate before the notes phase and
    once as the temporal check after case closure (DEMOMA-23-005, #3042).

    Each per-replica wait runs inside its own demo context so a timeout is
    recorded by the failure accumulator and the loop continues to the next
    replica instead of propagating (DEMOCI-01-011):

    - ``causal=True`` wraps in ``demo_gate`` — the wait is a precondition for
      the steps that follow (EDF-06-005, DEMOCI-01-007).
    - ``causal=False`` wraps in ``demo_check`` and labels the wait as temporal
      (EDF-06-006): after case closure nothing depends on coverage except the
      forensic ledger dump, which the harness runs regardless.

    Timeouts (EDF-06-008): the chain being bounded is the authority's outbox →
    ``Announce(CaseLedgerEntry)`` ``BackgroundTasks`` delivery → replica inbox,
    one hop per entry, all containers on one Compose network. An early
    participant has been receiving entries as they were committed and gets
    ``LEDGER_COVERAGE_TIMEOUT`` (15 s fired under CI load, #1911, #2337). A
    late joiner catches up from genesis through the CM-17-004 backfill — one
    ``Announce`` per prior entry — and gets ``LATE_JOINER_COVERAGE_TIMEOUT``.
    Neither is below any budget a scenario carried before the loop was shared;
    a scenario that needs a different budget passes another named constant,
    never a literal.

    Args:
        auth_client: Client for the container whose ledger is authoritative
            for *case_id* (the CASE_MANAGER's host).
        replicas: ``(client, label)`` pairs to poll, in order. The label
            appears in the demo context description and the log.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        late_joiners: Subset of the replica clients that joined after earlier
            entries were committed. Membership is tested by object identity.
        late_joiner_timeout: Per-replica budget for late joiners.
        default_timeout: Per-replica budget for every other replica.
        phase_label: Names the phase in each context description.
        causal: ``True`` for a ``demo_gate`` per replica, ``False`` for a
            ``demo_check``.

    Returns:
        The replica clients whose wait passed, in *replicas* order. A caller
        gating a dependent step on coverage (EDF-06-005) tests membership by
        identity; a temporal caller ignores it.
    """
    entries = _get_log_entries_for_case(auth_client, case_id)
    if not entries:
        logger.warning(
            "Authority %s holds no ledger entries for case %s; skipping "
            "replica coverage waits (%s)",
            auth_client.base_url,
            case_id,
            phase_label,
        )
        return [client for client, _ in replicas]
    tail = max(entries, key=lambda e: e["log_index"])
    tail_index: int = tail["log_index"]
    logger.info(
        "Waiting for %d replica(s) to cover authority tail (hash=%s… index=%d)",
        len(replicas),
        tail["entry_hash"][:16],
        tail_index,
    )
    context = demo_gate if causal else demo_check
    temporal = "" if causal else " — temporal wait (EDF-06-006)"
    covered: list[DataLayerClient] = []
    for replica_client, label in replicas:
        is_late = _client_in(replica_client, late_joiners)
        with context(f"{label} ledger coverage ({phase_label}){temporal}"):
            wait_for_contiguous_ledger_coverage(
                client=replica_client,
                case_id=case_id,
                expected_tail_index=tail_index,
                timeout_seconds=(
                    late_joiner_timeout if is_late else default_timeout
                ),
            )
            logger.info("  %s ledger synchronized", label)
            covered.append(replica_client)
    return covered


def run_sync_verification_phase(
    *,
    auth_client: DataLayerClient,
    auth_label: str,
    auth_actor_id: str,
    finder_client: DataLayerClient,
    finder_actor_id: str,
    replicas: ReplicaSpec,
    case_id: str,
    expected_participant_ids: Collection[str] = frozenset(),
    late_joiners: Sequence[DataLayerClient] = (),
    state_checks: ReplicaSpec = (),
    default_coverage_timeout: float = LEDGER_COVERAGE_TIMEOUT,
) -> None:
    """Run a scenario's replica sync-verification phase (DEMOMA-23-007).

    Composes, in order:

    1. The Finder-case gate: the Finder must hold the ``VulnerabilityCase`` (and
       so its per-case genesis hash) before any coverage wait, or every
       ``Announce(CaseLedgerEntry)`` is rejected and replayed rather than
       accepted and the coverage timeout reports the wrong problem
       (SYNC-15-001, CLP-08-005, #1873).
    2. :func:`wait_for_replica_ledger_coverage` as the causal gate, nested in
       the Finder gate so an unseeded Finder skips it (EDF-06-005).
    3. ``wait_for_participants_on_replicas`` for *expected_participant_ids*,
       when the scenario declares any — a temporal wait (EDF-06-006) that gives
       *late_joiners* the extended participant-index budget (#2852).
    4. :func:`verify_replica_state` in a ``demo_check`` for each replica in
       *state_checks* whose coverage gate passed, against *auth_client*. A
       replica whose coverage timed out already recorded a ``GATE FAILED``;
       comparing its state would only add the cascading second failure #1911
       and #2361 removed (EDF-06-005).

    The helper declares no scenario facts of its own: which container is the
    authority, which replicas exist, who joined late, which participants are
    expected and which replicas to state-check all come from the caller.

    Args:
        auth_client: Client for the authoritative container.
        auth_label: Display name of the authority (``"Vendor1"``, ``"C1"``).
        auth_actor_id: Full URI of the authoritative actor.
        finder_client: Client for the Finder container, gated first.
        finder_actor_id: Full URI of the Finder (reporter) actor.
        replicas: ``(client, label)`` pairs to wait for coverage on.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected_participant_ids: Actor URIs every replica must index. Empty
            means the scenario declares no participant expectation.
        late_joiners: Replica clients that joined late (identity-tested).
        state_checks: ``(client, label)`` pairs to compare against the authority.
        default_coverage_timeout: Coverage budget for non-late-joiner replicas.
    """
    covered: list[DataLayerClient] = []
    with demo_gate("Finder case seeded before ledger coverage wait (SYNC-15)"):
        wait_for_case_on_container(client=finder_client, case_id=case_id)
        covered = wait_for_replica_ledger_coverage(
            auth_client,
            replicas,
            case_id,
            late_joiners=late_joiners,
            default_timeout=default_coverage_timeout,
        )

    if expected_participant_ids:
        # Temporal (EDF-06-006): participant-index propagation budget, with the
        # extended late-joiner allowance; see wait_for_participants_on_replicas.
        wait_for_participants_on_replicas(
            replica_clients=[client for client, _ in replicas],
            case_id=case_id,
            expected_actor_ids=set(expected_participant_ids),
            late_joiners=late_joiners,
        )

    for replica_client, label in state_checks:
        if not _client_in(replica_client, covered):
            logger.info(
                "  %s replica state check skipped: its ledger coverage gate "
                "did not pass",
                label,
            )
            continue
        with demo_check(
            f"{label} replica matches authoritative {auth_label} state"
        ):
            verify_replica_state(
                auth_client=auth_client,
                replica_client=replica_client,
                case_id=case_id,
                vendor_actor_id=auth_actor_id,
                reporter_actor_id=finder_actor_id,
            )
