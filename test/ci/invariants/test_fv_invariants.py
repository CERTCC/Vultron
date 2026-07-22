"""Case-ledger invariant tests for the two-actor FV (Finder + Vendor) scenario.

Reads JSONL case-ledger replica files from ``devlogs/two-actor/`` and
asserts all universal invariants via the shared ``common`` library plus
FV-specific checks.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/`` or ``devlogs/two-actor/`` is absent, so they
are safe to include in the regular unit-test collection.

Spec: CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_cross_actor_hash_agreement,
    check_cross_actor_payload_actor_agreement,
    check_cs_state_transitions_observed,
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

_DEMO_NAME = "two-actor"

#: Expected protocol eventTypes in a complete FV run.
_FV_EXPECTED_EVENT_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
]

#: Actors with per-actor hash-chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fv_replicas() -> dict[str, list[dict]]:
    """Load FV scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (shared library)
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_1_local_hash_chain_consistent(
    actor_name: str,
    fv_replicas: dict[str, list[dict]],
) -> None:
    """Within each contiguous logIndex fragment, hashes chain correctly.

    Spec: CLP-07.
    """
    entries = fv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")
    violations = check_hash_chain(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_2_cross_actor_hash_agreement(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on entryHash for every shared logIndex."""
    violations = check_cross_actor_hash_agreement(fv_replicas)
    assert not violations, (
        f"Cross-actor hash mismatches at {len(violations)} logIndex(es):\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_3_cross_actor_payload_actor_agreement(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on payloadSnapshot.actor for every shared logIndex."""
    violations = check_cross_actor_payload_actor_agreement(fv_replicas)
    assert not violations, (
        f"Cross-actor payloadSnapshot.actor mismatches at "
        f"{len(violations)} logIndex(es):\n" + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_4_non_empty_payload_snapshot(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """Every recorded canonical entry has a non-empty payloadSnapshot."""
    violations = check_non_empty_payload_snapshots(fv_replicas)
    assert not violations, (
        f"Found {len(violations)} recorded entries with empty payloadSnapshot:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("event_type_val", _FV_EXPECTED_EVENT_TYPES)
def test_invariant_5_expected_event_types_present(
    event_type_val: str,
    fv_replicas: dict[str, list[dict]],
) -> None:
    """Each expected protocol eventType appears at least once.

    Note: ``ack_report`` is intentionally excluded — the two-actor demo uses
    ``auto_create_case=True``, so no pre-case ACK is emitted (see #1133).
    """
    violations = check_event_type_present(fv_replicas, event_type_val)
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_invariant_6_no_rm_state_oscillation(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """No participant changes RM state after first reaching CLOSED."""
    violations = check_no_rm_state_oscillation(fv_replicas)
    assert not violations, "RM state oscillation after CLOSED:\n" + "\n".join(
        violations
    )


@pytest.mark.case_ledger_invariants
def test_invariant_7_log_terminates_all_rm_closed(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """The log terminates with every participant in RM=CLOSED."""
    violations = check_rm_closed_termination(fv_replicas)
    assert (
        not violations
    ), f"Participants not in RM=CLOSED at log end: {violations}"


@pytest.mark.case_ledger_invariants
def test_invariant_8_late_joiner_has_full_history(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """Finder replica contains all logIndex values present in the vendor replica.

    The finder joins after report-to-case promotion; pre-join entries must be
    backfilled.
    """
    if not fv_replicas.get("vendor") or not fv_replicas.get("finder"):
        pytest.skip(
            "vendor or finder replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fv_replicas, early_actor="vendor", late_actor="finder"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_9_participant_status_schema_completeness(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole list."""
    violations = check_participant_status_schema_completeness(fv_replicas)
    assert not violations, (
        f"{len(violations)} ParticipantStatus entries missing required fields:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_10_nested_objects_inlined_in_payload(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.object is an inline dict, not a bare ID string."""
    violations = check_nested_objects_inlined(fv_replicas)
    assert not violations, (
        f"payloadSnapshot.object is a bare ID string in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_11_payload_context_uses_case_uri(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.context matches the entry's case_id for recorded entries."""
    violations = check_payload_context_uses_case_uri(fv_replicas)
    assert not violations, (
        f"payloadSnapshot.context != case_id in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_12_genesis_entry_present(
    actor_name: str,
    fv_replicas: dict[str, list[dict]],
) -> None:
    """logIndex=0 is present in the actor's log."""
    entries = fv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")
    violations = check_genesis_entry_present(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_13_log_starts_at_genesis(
    actor_name: str,
    fv_replicas: dict[str, list[dict]],
) -> None:
    """The first entry in the actor's sorted log has logIndex=0."""
    entries = fv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")
    violations = check_log_starts_at_genesis(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_14_no_gaps_in_log_indices(
    actor_name: str,
    fv_replicas: dict[str, list[dict]],
) -> None:
    """No gaps within the actor's present logIndex range."""
    entries = fv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")
    violations = check_no_gaps_in_log_indices(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_15_cs_state_transitions_observed(
    fv_replicas: dict[str, list[dict]],
) -> None:
    """All three key CS transitions are recorded in the authoritative log.

    Checks vfd_state == "VFd" (fix_ready), "VFD" (fix_deployed), and
    pxa_state starting with "P" (public-aware).
    """
    violations = check_cs_state_transitions_observed(fv_replicas)
    assert not violations, (
        "Missing CS-transition observations in "
        "add_participant_status_to_participant entries:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# FV-specific invariants
# ---------------------------------------------------------------------------
#
# The two-actor (FV) scenario has no scenario-specific ledger invariant beyond
# the universal set: the Finder joins by submitting a report (which creates the
# case), never via an ``invite_actor_to_case`` activity, so no invite event is
# expected in this ledger.  Scenarios that invite a mid-case participant (FVV,
# FVCV-extension, FVCV-handoff) assert the invite event in their own files.
