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

"""Waits on a case replica: its arrival, participants, notes and owner.

Also the CaseActor's initialized case and the pending-case inbox drain.
"""

import logging
from collections.abc import Sequence

import httpx2 as httpx

from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.demo.helpers.polling._poll import (
    CROSS_CONTAINER_TIMEOUT,
    LATE_JOINER_REPLICA_TIMEOUT,
    PARTICIPANT_JOIN_TIMEOUT,
    REPLICA_PARTICIPANT_TIMEOUT,
    _client_in,
    _poll_until,
)
from vultron.demo.utils import (
    DataLayerClient,
    case_actor_id_for_report,
    case_references_report,
    demo_check,
    served_field,
)
from vultron.demo.utils.served import from_server
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def wait_for_case_on_container(
    client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll *client*'s DataLayer until *case_id* appears.

    Proves that an outbox activity (e.g. ``Create(VulnerabilityCase)``) was
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
        case = from_server(as_VulnerabilityCase, case_data)
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
    (DEMOCI-01-014): :func:`wait_for_case_participants` raises ``AssertionError``
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
        case = from_server(as_VulnerabilityCase, case_data)
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
    applied by ``ApplyOwnershipTransferFromLedgerNode`` (CM-21-030,
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
        attributed_to = served_field(
            case_data, "attributedTo", "attributed_to"
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
            case = from_server(as_VulnerabilityCase, case_raw)
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
    """Poll until nothing is waiting on *case_id* in the recipient's store.

    A message that arrives for a case the recipient has not been seeded with
    waits on its own record, which names the case it waits on (ADR-0059,
    ADR-0154).  This gate confirms that nothing waits on *case_id* any
    more — i.e. the case seed has arrived and all buffered activities were
    processed.

    A held out-of-order ``Announce(CaseLedgerEntry)`` (``HeldLedgerAnnounce``,
    SYNC-14) is intentionally excluded: it waits on a ledger predecessor, not
    on the case seed, so it is no signal that the seed has been processed.

    Args:
        client: DataLayerClient connected to the container to check.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If something is still waiting within
            *timeout_seconds*.

    Spec: EDF-06-001.
    """

    def _check() -> bool:
        try:
            # The by-type route answers a mapping of id to stored row, and a
            # ``CoreRecord`` is stored under its own field names (no AS2
            # spelling), so the waited-on case reads as ``awaiting_case_id``.
            rows = client.get(
                client.dl_path(f"{ReceivedActivityRecord.__name__}s/")
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # No table means nothing has been received, so nothing waits.
                return True
            raise
        if not isinstance(rows, dict):
            return True
        return not any(
            isinstance(row, dict) and row.get("awaiting_case_id") == case_id
            for row in rows.values()
        )

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for activities awaiting case {case_id!r} to drain"
        f" on container {client.base_url}",
        swallow_exceptions=False,
    )
