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

"""SYNC-2 log-replication helpers for demo workflows.

Provides :func:`trigger_log_commit` to commit a log entry and fan it out to
all case participants, and :func:`verify_replica_state` to assert that a
replica actor's case state matches the authoritative actor.

``verify_finder_replica_state`` is kept as a backward-compatible alias.
"""

import logging
from typing import Optional

from vultron.demo.utils import DataLayerClient, post_to_trigger
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

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
    """Return all ``CaseLogEntry`` dicts for *case_id* from the DataLayer."""
    raw = client.get("/datalayer/CaseLogEntrys/")
    if not isinstance(raw, dict):
        return []
    return [
        v
        for v in raw.values()
        if isinstance(v, dict) and v.get("case_id") == case_id
    ]


# ---------------------------------------------------------------------------
# Public SYNC-2 helpers
# ---------------------------------------------------------------------------


def trigger_log_commit(
    client: DataLayerClient,
    actor_id: str,
    case_id: str,
    event_type: str,
    object_id: str | None = None,
) -> str:
    """Commit a log entry for *case_id* and return the entry hash.

    POSTs to ``/actors/{actor_id}/demo/sync-log-entry`` and returns the
    ``entry_hash`` from the response.  The entry is also fanned out to all
    case participants via ``Announce(CaseLogEntry)`` activities queued in the
    actor's outbox.

    Args:
        client: DataLayerClient connected to the CaseActor container.
        actor_id: Full URI of the actor committing the log entry.
        case_id: Full URI of the ``VulnerabilityCase``.
        event_type: Short machine-readable event descriptor.
        object_id: Optional URI of the primary object.  Defaults to
            *case_id* when not supplied.

    Returns:
        The ``entry_hash`` of the newly committed log entry.

    Spec: SYNC-02-002, SYNC-02-003.
    """
    result = post_to_trigger(
        client=client,
        actor_id=actor_id,
        behavior="sync-log-entry",
        body={
            "case_id": case_id,
            "object_id": object_id if object_id is not None else case_id,
            "event_type": event_type,
        },
        path_prefix="demo",
    )
    entry_hash: str = result["entry_hash"]
    logger.info(
        "Log entry committed for case '%s': hash=%s, index=%d",
        case_id,
        entry_hash[:16],
        result.get("log_index", -1),
    )
    return entry_hash


def verify_replica_state(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
    reporter_actor_id: str,
) -> None:
    """Verify that a replica actor's case state matches the authoritative state.

    Checks four properties:

    1. The same ``case_id`` exists in the replica's DataLayer.
    2. ``actor_participant_index`` keys are identical (same participant set).
    3. ``active_embargo`` references the same ID on both sides.
    4. Log-state hash consistency: both sides share the same tail entry hash.

    Args:
        finder_client: DataLayerClient connected to the authoritative container.
        vendor_client: DataLayerClient connected to the replica container.
        case_id: Full URI of the ``VulnerabilityCase`` being verified.
        vendor_actor_id: Full URI of the Vendor actor (retained for symmetry).
        reporter_actor_id: Full URI of the Reporter/Finder actor (retained for
            future participant-status checks).

    Raises:
        AssertionError: If any replica invariant is violated.

    Spec: SYNC-02-002, D5-7-DEMOREPLCHECK-1.
    """
    auth_case_data = finder_client.get(f"/datalayer/{case_id}")
    assert auth_case_data, f"Authoritative case {case_id!r} not found"
    auth_case = VulnerabilityCase.model_validate(auth_case_data)

    replica_case_data = vendor_client.get(f"/datalayer/{case_id}")
    assert replica_case_data, (
        f"Replica does not have a copy of case {case_id!r} — "
        "outbox delivery or inbox processing may have failed"
    )
    replica_case = VulnerabilityCase.model_validate(replica_case_data)

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
    auth_entries = _get_log_entries_for_case(finder_client, case_id)
    replica_entries = _get_log_entries_for_case(vendor_client, case_id)
    assert len(replica_entries) > 0, (
        "Replica has no CaseLogEntry records for the case — "
        "SYNC-2 replication did not complete"
    )
    auth_tail = max(auth_entries, key=lambda e: e["log_index"])
    replica_tail = max(replica_entries, key=lambda e: e["log_index"])
    assert auth_tail["entry_hash"] == replica_tail["entry_hash"], (
        f"Replica log tail hash {replica_tail['entry_hash']!r} != "
        f"authoritative log tail hash {auth_tail['entry_hash']!r} — "
        "hash-chain replication integrity failure"
    )
    logger.info(
        "✓ Replica log tail hash matches auth: %s… (index=%d)",
        replica_tail["entry_hash"][:16],
        replica_tail["log_index"],
    )


# Backward-compatible alias for code that calls verify_finder_replica_state.
verify_finder_replica_state = verify_replica_state
