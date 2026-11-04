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

"""Read the authority's ledger tail and wait for replicas to cover it.

Specs: DEMOMA-23-005, DEMOMA-23-006.
"""

import logging
from collections.abc import Sequence

from vultron.demo.helpers.polling import (
    LATE_JOINER_COVERAGE_TIMEOUT,
    LEDGER_COVERAGE_TIMEOUT,
    wait_for_contiguous_ledger_coverage,
)
from vultron.demo.helpers.polling._poll import _client_in
from vultron.demo.utils import DataLayerClient, demo_gate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_ref_id(ref: object) -> str | None:
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
) -> list[DataLayerClient]:
    """Wait for every replica to hold the authority's ledger tail contiguously.

    Reads the authority's ``CaseLedgerEntry`` tail once, then polls each replica
    in *replicas* order until it holds indices ``0…tail`` (SYNC-10-004). When
    the authority holds no entries there is nothing to cover: every replica
    wait is skipped, one failure naming the *authority* is recorded in the same
    demo context the waits would have used, and no replica counts as covered.
    The fault is the writer's, not the fan-out's, so the failure must not be
    left for a replica-side state check to report as "replication did not
    complete" (EDF-06-005: one causal event, one recorded failure).

    This is the single implementation of the loop that every scenario module
    used to carry as the causal gate before the notes phase (DEMOMA-23-005,
    #3042).  The temporal check after case closure no longer covers the
    authority's tail: a closed participant is sent nothing after its own
    closure entries (CM-23-004), so each leaver's replica is checked against
    its own closure instead (:func:`wait_for_replica_ledger_ending_at`).

    Each per-replica wait runs inside its own ``demo_gate`` — the wait is a
    precondition for the steps that follow (EDF-06-005, DEMOCI-01-007) — so a
    timeout is recorded by the failure accumulator and the loop continues to
    the next replica instead of propagating (DEMOCI-01-014).

    Timeouts (EDF-06-008): the chain being bounded is the authority's outbox →
    ``Announce(CaseLedgerEntry)`` ``BackgroundTasks`` delivery → replica inbox,
    one hop per entry, all containers on one Compose network. An early
    participant has been receiving entries as they were committed and gets
    ``LEDGER_COVERAGE_TIMEOUT`` (15 s fired under CI load, #1911, #2337). A
    late joiner catches up from genesis through the CM-17-004 backfill — one
    ``Announce`` per prior entry — and gets ``LATE_JOINER_COVERAGE_TIMEOUT``.
    Neither is below any budget a scenario carried before the loop was shared;
    a scenario that needs a different budget passes another named constant,
    never a literal.  Each budget is how long a replica may go without
    receiving another entry, not a total: a replica still draining a long
    backfill keeps being waited for, up to ``BACKFILL_PROGRESS_CEILING``
    (#4424).

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

    Returns:
        The replica clients whose wait passed, in *replicas* order — empty when
        the authority held nothing to cover. A caller gating a dependent step
        on coverage (EDF-06-005) tests membership by identity.
    """
    entries = _get_log_entries_for_case(auth_client, case_id)
    if not entries:
        with demo_gate(
            f"authority {auth_client.base_url} holds ledger entries to cover "
            f"({phase_label})"
        ):
            raise AssertionError(
                f"Authority {auth_client.base_url} holds no CaseLedgerEntry "
                f"records for case {case_id!r}; nothing for "
                f"{len(replicas)} replica(s) to cover — the writer, not "
                "LedgerFanout replication, is at fault"
            )
        return []
    tail = max(entries, key=lambda e: e["log_index"])
    tail_index: int = tail["log_index"]
    logger.info(
        "Waiting for %d replica(s) to cover authority tail (hash=%s… index=%d)",
        len(replicas),
        tail["entry_hash"][:16],
        tail_index,
    )
    covered: list[DataLayerClient] = []
    for replica_client, label in replicas:
        is_late = _client_in(replica_client, late_joiners)
        with demo_gate(f"{label} ledger coverage ({phase_label})"):
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


def wait_for_replica_ledger_ending_at(
    client: DataLayerClient,
    case_id: str,
    tail_index: int,
    timeout_seconds: float = LATE_JOINER_COVERAGE_TIMEOUT,
) -> None:
    """Wait until *client*'s replica holds ``0…tail_index``, then nothing more.

    The closure-phase coverage wait for a participant that has left: it is
    sent the entries recording its own closure and nothing after them
    (CM-23-004), so its replica's ledger ends at the last of those, not at
    the CASE_MANAGER's tail.  Waits for the contiguous prefix (SYNC-10-004),
    then checks once that no later entry reached the replica.

    The absence half is one read, so it is best-effort: no cause can be
    awaited for an entry that should never arrive, and a wrongly sent entry
    committed just before the read (the Case Owner's case, whose tail is
    followed at once by the CASE_MANAGER's own closure) may still be in
    flight.  The backstops are the
    recipient-selection unit tests (``test/core/participants/test_recipients.py``)
    and the CI per-replica termination invariant, which reads each replica's
    final export after the run.

    Bounded by ``LATE_JOINER_COVERAGE_TIMEOUT`` by default (EDF-06-008): a
    late joiner may still be draining its backfill when it leaves.  The
    budget is a ceiling, so an early participant pays nothing for it.

    Args:
        client: DataLayerClient bound to the departed participant's replica.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        tail_index: The ``log_index`` of the last entry recording the
            participant's own closure, as the CASE_MANAGER's ledger holds it.
        timeout_seconds: Maximum time to wait for the prefix.

    Raises:
        AssertionError: If the prefix does not arrive in time, or the replica
            holds an entry past *tail_index*.
    """
    wait_for_contiguous_ledger_coverage(
        client=client,
        case_id=case_id,
        expected_tail_index=tail_index,
        timeout_seconds=timeout_seconds,
    )
    beyond = sorted(
        index
        for e in _get_log_entries_for_case(client, case_id)
        if isinstance(index := e.get("log_index"), int) and index > tail_index
    )
    if beyond:
        raise AssertionError(
            f"replica {client.actor_id!r} holds entries {beyond} of case"
            f" {case_id!r} after logIndex={tail_index}, the last entry"
            " recording its own closure; a closed participant is sent"
            " nothing after it (CM-23-004)"
        )
