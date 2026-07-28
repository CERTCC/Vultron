"""Case-ledger invariant tests for the FVCV-handoff scenario.

Reads JSONL case-ledger replica files from ``devlogs/fvcv-handoff/`` and
asserts universal invariants (via the shared ``common`` library) plus
FVCV-handoff-specific checks.

Actor set: ``finder``, ``vendor`` (initial CASE_OWNER), ``coordinator``
(new CASE_OWNER after the ownership handoff), ``vendor2``, ``case-actor``.

FVCV-handoff-specific invariants:
- ``invite_actor_to_case`` appears at least twice (Vendor1 invites
  Coordinator, then Coordinator — as the new owner — invites Vendor2).
- ``accept_invite_actor_to_case`` appears at least twice (Coordinator and
  Vendor2 each accept their invitation).
- Vendor2 is a late joiner — its replica holds the complete log from genesis.

Note on the ownership transfer: the ``Offer(VulnerabilityCase)`` /
``Accept(Offer(VulnerabilityCase))`` handoff is a direct Vendor1 ↔
Coordinator exchange (TRIG-11-001/TRIG-11-002) and does not emit a canonical
CaseActor ledger entry, so it is not observable here.  The demo verifies the
resulting ``attributed_to`` change on both the Vendor1 and Coordinator
DataLayers via ``demo_check`` assertions instead.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fvcv-handoff/`` is absent.

Spec: GitHub issue #1561; CLP-07.
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

_DEMO_NAME = "fvcv-handoff"

#: Expected protocol eventTypes in a complete FVCV-handoff run.
_FVCV_HANDOFF_EXPECTED_EVENT_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
    # DEMOMA-16-005: Vendor1 invites Coordinator (and later Vendor2);
    # Coordinator and Vendor2 both accept.
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("vendor2"),
    pytest.param("finder"),
    pytest.param("coordinator"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fvcv_handoff_replicas() -> dict[str, list[dict]]:
    """Load FVCV-handoff scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_1_local_hash_chain_consistent(
    actor_name: str,
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """Within each contiguous logIndex fragment, hashes chain correctly."""
    entries = fvcv_handoff_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fvcv-handoff/"
        )
    violations = check_hash_chain(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_2_cross_actor_hash_agreement(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on entryHash for every shared logIndex."""
    violations = check_cross_actor_hash_agreement(fvcv_handoff_replicas)
    assert not violations, (
        f"Cross-actor hash mismatches at {len(violations)} logIndex(es):\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_3_cross_actor_payload_actor_agreement(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on payloadSnapshot.actor for every shared logIndex."""
    violations = check_cross_actor_payload_actor_agreement(
        fvcv_handoff_replicas
    )
    assert (
        not violations
    ), "Cross-actor payloadSnapshot.actor mismatches:\n" + "\n".join(
        violations[:20]
    )


@pytest.mark.case_ledger_invariants
def test_invariant_4_non_empty_payload_snapshot(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """Every recorded canonical entry has a non-empty payloadSnapshot."""
    violations = check_non_empty_payload_snapshots(fvcv_handoff_replicas)
    assert not violations, (
        f"Found {len(violations)} recorded entries with empty payloadSnapshot:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("event_type_val", _FVCV_HANDOFF_EXPECTED_EVENT_TYPES)
def test_invariant_5_expected_event_types_present(
    event_type_val: str,
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """Each expected protocol eventType appears at least once."""
    violations = check_event_type_present(
        fvcv_handoff_replicas, event_type_val
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_invariant_6_no_rm_state_oscillation(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """No participant changes RM state after first reaching CLOSED."""
    violations = check_no_rm_state_oscillation(fvcv_handoff_replicas)
    assert not violations, "RM state oscillation after CLOSED:\n" + "\n".join(
        violations
    )


@pytest.mark.case_ledger_invariants
def test_invariant_7_log_terminates_all_rm_closed(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """The log terminates with every participant in RM=CLOSED."""
    violations = check_rm_closed_termination(fvcv_handoff_replicas)
    assert not violations, f"Participants not in RM=CLOSED: {violations}"


@pytest.mark.case_ledger_invariants
def test_invariant_9_participant_status_schema_completeness(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole list."""
    violations = check_participant_status_schema_completeness(
        fvcv_handoff_replicas
    )
    assert not violations, (
        f"{len(violations)} ParticipantStatus entries missing required fields:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_10_nested_objects_inlined_in_payload(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.object is an inline dict, not a bare ID string."""
    violations = check_nested_objects_inlined(fvcv_handoff_replicas)
    assert not violations, (
        f"payloadSnapshot.object is a bare ID string in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_11_payload_context_uses_case_uri(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.context matches the entry's case_id for recorded entries."""
    violations = check_payload_context_uses_case_uri(fvcv_handoff_replicas)
    assert not violations, (
        f"payloadSnapshot.context != case_id in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_12_genesis_entry_present(
    actor_name: str,
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """logIndex=0 is present in the actor's log."""
    entries = fvcv_handoff_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fvcv-handoff/"
        )
    violations = check_genesis_entry_present(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_13_log_starts_at_genesis(
    actor_name: str,
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """The first entry in the actor's sorted log has logIndex=0."""
    entries = fvcv_handoff_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fvcv-handoff/"
        )
    violations = check_log_starts_at_genesis(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_14_no_gaps_in_log_indices(
    actor_name: str,
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """No gaps within the actor's present logIndex range."""
    entries = fvcv_handoff_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fvcv-handoff/"
        )
    violations = check_no_gaps_in_log_indices(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_15_cs_state_transitions_observed(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """All three key CS transitions observed in the authoritative log."""
    violations = check_cs_state_transitions_observed(fvcv_handoff_replicas)
    assert not violations, "Missing CS-transition observations:\n" + "\n".join(
        violations
    )


# ---------------------------------------------------------------------------
# FVCV-handoff-specific invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fvcv_handoff_invite_actor_to_case_at_least_twice(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least twice.

    Vendor1 invites Coordinator; then Coordinator (the new CASE_OWNER after
    the ownership handoff) invites Vendor2.
    """
    violations = check_event_type_count(
        fvcv_handoff_replicas, "invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fvcv_handoff_accept_invite_at_least_twice(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` appears at least twice.

    Coordinator accepts Vendor1's invitation and Vendor2 accepts
    Coordinator's invitation — both mid-case joins land in the canonical
    ledger (PCR-08-008).
    """
    violations = check_event_type_count(
        fvcv_handoff_replicas, "accept_invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fvcv_handoff_vendor2_late_joiner_has_full_history(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """Vendor2 replica contains all logIndex values present in vendor replica.

    Vendor2 is the last actor to join (after the ownership handoff) and must
    receive the full ledger backfill (SYNC-2 convergence).
    """
    if not fvcv_handoff_replicas.get(
        "vendor"
    ) or not fvcv_handoff_replicas.get("vendor2"):
        pytest.skip(
            "vendor or vendor2 replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fvcv_handoff_replicas, early_actor="vendor", late_actor="vendor2"
    )
    assert not violations, "\n".join(violations)
