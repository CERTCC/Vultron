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

"""The whole replica sync-verification phase of a scenario.

Specs: DEMOMA-23-007.
"""

import logging
from collections.abc import Collection, Sequence

from vultron.demo.helpers.polling import (
    LEDGER_COVERAGE_TIMEOUT,
    wait_for_case_on_container,
    wait_for_participants_on_replicas,
)
from vultron.demo.helpers.polling._poll import _client_in
from vultron.demo.helpers.sync.ledger import (
    ReplicaSpec,
    wait_for_replica_ledger_coverage,
)
from vultron.demo.helpers.sync.replica import (
    verify_replica_state,
)
from vultron.demo.utils import DataLayerClient, demo_check, demo_gate

logger = logging.getLogger(__name__)


def run_sync_verification_phase(
    *,
    auth_client: DataLayerClient,
    auth_label: str,
    auth_actor_id: str,
    reporter_client: DataLayerClient,
    reporter_actor_id: str,
    replicas: ReplicaSpec,
    case_id: str,
    expected_participant_ids: Collection[str] = frozenset(),
    late_joiners: Sequence[DataLayerClient] = (),
    state_checks: ReplicaSpec = (),
    default_coverage_timeout: float = LEDGER_COVERAGE_TIMEOUT,
) -> None:
    """Run a scenario's replica sync-verification phase (DEMOMA-23-007).

    Composes, in order:

    1. The Reporter-case gate: the Reporter must hold the ``VulnerabilityCase`` (and
       so its per-case genesis hash) before any coverage wait, or every
       ``Announce(CaseLedgerEntry)`` is rejected and replayed rather than
       accepted and the coverage timeout reports the wrong problem
       (SYNC-15-001, CLP-08-005, #1873).
    2. :func:`wait_for_replica_ledger_coverage` as the causal gate, nested in
       the Reporter gate so an unseeded Reporter skips it (EDF-06-005).
    3. ``wait_for_participants_on_replicas`` for *expected_participant_ids*,
       when the scenario declares any — a temporal wait (EDF-06-006) that gives
       *late_joiners* the extended participant-index budget (#2852).
    4. :func:`verify_replica_state` in a ``demo_check`` for each replica in
       *state_checks* whose coverage gate passed, against *auth_client*. A
       replica whose coverage timed out — or whose authority held nothing to
       cover — already recorded a ``GATE FAILED``; comparing its state would
       only add the cascading second failure #1911 and #2361 removed
       (EDF-06-005).

    The helper declares no scenario facts of its own: which container is the
    authority, which replicas exist, who joined late, which participants are
    expected and which replicas to state-check all come from the caller.

    Args:
        auth_client: Client for the authoritative container.
        auth_label: Display name of the authority (``"Vendor1"``, ``"C1"``).
        auth_actor_id: Full URI of the authoritative actor.
        reporter_client: Client for the Reporter container, gated first.
        reporter_actor_id: Full URI of the Reporter actor.
        replicas: ``(client, label)`` pairs to wait for coverage on.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        expected_participant_ids: Actor URIs every replica must index. Empty
            means the scenario declares no participant expectation.
        late_joiners: Replica clients that joined late (identity-tested).
        state_checks: ``(client, label)`` pairs to compare against the authority.
        default_coverage_timeout: Coverage budget for non-late-joiner replicas.
    """
    covered: list[DataLayerClient] = []
    with demo_gate(
        "Reporter case seeded before ledger coverage wait (SYNC-15)"
    ):
        wait_for_case_on_container(client=reporter_client, case_id=case_id)
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
                reporter_actor_id=reporter_actor_id,
            )
