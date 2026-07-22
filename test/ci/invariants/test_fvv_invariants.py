"""Case-ledger invariant tests for the three-actor FVV scenario.

Reads JSONL case-ledger replica files from ``devlogs/fvv/`` and asserts
universal invariants (via the shared ``common`` library) plus FVV-specific
checks.

Actor set: ``finder``, ``vendor``, ``vendor2``, ``case-actor``.

Universal invariants (1–15) are applied via ``common.py``.

FVV-specific invariants:
- ``invite_actor_to_case`` appears at least once (Vendor1 invites Vendor2).
- Vendor2 replica holds the complete log from genesis (late-joiner backfill).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fvv/`` is absent.

Spec: DEMOMA-09, CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_cross_actor_hash_agreement,
    check_cross_actor_payload_actor_agreement,
    check_cs_state_transitions_observed,
    check_event_type_count,
    check_event_type_present,
    check_genesis_entry_present,
    check_hash_chain,
    check_late_joiner_has_full_history,
    check_log_starts_at_genesis,
    check_nested_objects_inlined,
    check_no_gaps_in_log_indices,
    check_no_rm_state_oscillation,
    check_non_empty_payload_snapshots,
    check_participant_status_schema_completeness,
    check_payload_context_uses_case_uri,
    check_rm_closed_termination,
    load_devlogs,
)

_DEMO_NAME = "fvv"

#: Expected protocol eventTypes in a complete FVV run.
_FVV_EXPECTED_EVENT_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
]

#: Actors with per-actor chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("vendor2"),
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fvv_replicas() -> dict[str, list[dict]]:
    """Load FVV scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_1_local_hash_chain_consistent(
    actor_name: str,
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """Within each contiguous logIndex fragment, hashes chain correctly."""
    entries = fvv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/fvv/")
    violations = check_hash_chain(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_2_cross_actor_hash_agreement(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on entryHash for every shared logIndex."""
    violations = check_cross_actor_hash_agreement(fvv_replicas)
    assert not violations, (
        f"Cross-actor hash mismatches at {len(violations)} logIndex(es):\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_3_cross_actor_payload_actor_agreement(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on payloadSnapshot.actor for every shared logIndex."""
    violations = check_cross_actor_payload_actor_agreement(fvv_replicas)
    assert (
        not violations
    ), "Cross-actor payloadSnapshot.actor mismatches:\n" + "\n".join(
        violations[:20]
    )


@pytest.mark.case_ledger_invariants
def test_invariant_4_non_empty_payload_snapshot(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """Every recorded canonical entry has a non-empty payloadSnapshot."""
    violations = check_non_empty_payload_snapshots(fvv_replicas)
    assert not violations, (
        f"Found {len(violations)} recorded entries with empty payloadSnapshot:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("event_type_val", _FVV_EXPECTED_EVENT_TYPES)
def test_invariant_5_expected_event_types_present(
    event_type_val: str,
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """Each expected protocol eventType appears at least once."""
    violations = check_event_type_present(fvv_replicas, event_type_val)
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_invariant_6_no_rm_state_oscillation(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """No participant changes RM state after first reaching CLOSED."""
    violations = check_no_rm_state_oscillation(fvv_replicas)
    assert not violations, "RM state oscillation after CLOSED:\n" + "\n".join(
        violations
    )


@pytest.mark.case_ledger_invariants
def test_invariant_7_log_terminates_all_rm_closed(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """The log terminates with every participant in RM=CLOSED."""
    violations = check_rm_closed_termination(fvv_replicas)
    assert (
        not violations
    ), f"Participants not in RM=CLOSED at log end: {violations}"


@pytest.mark.case_ledger_invariants
def test_invariant_9_participant_status_schema_completeness(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole list."""
    violations = check_participant_status_schema_completeness(fvv_replicas)
    assert not violations, (
        f"{len(violations)} ParticipantStatus entries missing required fields:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_10_nested_objects_inlined_in_payload(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.object is an inline dict, not a bare ID string."""
    violations = check_nested_objects_inlined(fvv_replicas)
    assert not violations, (
        f"payloadSnapshot.object is a bare ID string in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_11_payload_context_uses_case_uri(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.context matches the entry's case_id for recorded entries."""
    violations = check_payload_context_uses_case_uri(fvv_replicas)
    assert not violations, (
        f"payloadSnapshot.context != case_id in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_12_genesis_entry_present(
    actor_name: str,
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """logIndex=0 is present in the actor's log."""
    entries = fvv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/fvv/")
    violations = check_genesis_entry_present(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_13_log_starts_at_genesis(
    actor_name: str,
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """The first entry in the actor's sorted log has logIndex=0."""
    entries = fvv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/fvv/")
    violations = check_log_starts_at_genesis(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_14_no_gaps_in_log_indices(
    actor_name: str,
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """No gaps within the actor's present logIndex range."""
    entries = fvv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/fvv/")
    violations = check_no_gaps_in_log_indices(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_15_cs_state_transitions_observed(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """All three key CS transitions observed in the authoritative log."""
    violations = check_cs_state_transitions_observed(fvv_replicas)
    assert not violations, "Missing CS-transition observations:\n" + "\n".join(
        violations
    )


# ---------------------------------------------------------------------------
# FVV-specific invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fvv_invite_actor_to_case_present(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least once (Vendor1 invites Vendor2).

    Spec: DEMOMA-09-002.
    """
    violations = check_event_type_count(
        fvv_replicas, "invite_actor_to_case", min_count=1
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fvv_vendor2_late_joiner_has_full_history(
    fvv_replicas: dict[str, list[dict]],
) -> None:
    """Vendor2 replica contains all logIndex values present in vendor replica.

    Vendor2 is a late joiner and must receive the full ledger backfill.
    Spec: DEMOMA-09-004 (SYNC-2 convergence).
    """
    if not fvv_replicas.get("vendor") or not fvv_replicas.get("vendor2"):
        pytest.skip(
            "vendor or vendor2 replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fvv_replicas, early_actor="vendor", late_actor="vendor2"
    )
    assert not violations, "\n".join(violations)
