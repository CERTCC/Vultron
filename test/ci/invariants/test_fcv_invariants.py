"""Case-ledger invariant tests for the FCV three-actor scenario.

Reads JSONL case-ledger replica files from ``devlogs/fcv/`` and
asserts universal invariants (via the shared ``common`` library) plus
FCV-specific checks.

Actor set: ``finder``, ``coordinator``, ``vendor``, ``case-actor``.

FCV-specific invariants (DEMOMA-12-008/009):
- ``validate_report`` event type is present (Coordinator validates Finder's report).
- ``invite_actor_to_case`` appears at least twice (Finder + Vendor invitations).
- ``close_case`` event type is present.
- CS transitions VFd and VFD observed in Vendor's add_participant_status entries.
- P-transition observed in Coordinator's add_participant_status entries.
- Vendor is a late joiner — replica holds the complete log from genesis.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fcv/`` is absent.

Spec: DEMOMA-12, CLP-07.
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
    cs_observations_from_snap,
    event_type,
    load_devlogs,
    payload,
)

_DEMO_NAME = "fcv"

#: Expected protocol eventTypes in a complete FCV run.
_FCV_EXPECTED_EVENT_TYPES = [
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
    pytest.param("coordinator"),
    pytest.param("vendor"),
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fcv_replicas() -> dict[str, list[dict]]:
    """Load FCV scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_1_local_hash_chain_consistent(
    actor_name: str,
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """Within each contiguous logIndex fragment, hashes chain correctly."""
    entries = fcv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/fcv/")
    violations = check_hash_chain(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_2_cross_actor_hash_agreement(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on entryHash for every shared logIndex."""
    violations = check_cross_actor_hash_agreement(fcv_replicas)
    assert not violations, (
        f"Cross-actor hash mismatches at {len(violations)} logIndex(es):\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_3_cross_actor_payload_actor_agreement(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on payloadSnapshot.actor for every shared logIndex."""
    violations = check_cross_actor_payload_actor_agreement(fcv_replicas)
    assert (
        not violations
    ), "Cross-actor payloadSnapshot.actor mismatches:\n" + "\n".join(
        violations[:20]
    )


@pytest.mark.case_ledger_invariants
def test_invariant_4_non_empty_payload_snapshot(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """Every recorded canonical entry has a non-empty payloadSnapshot."""
    violations = check_non_empty_payload_snapshots(fcv_replicas)
    assert not violations, (
        f"Found {len(violations)} recorded entries with empty payloadSnapshot:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("event_type_val", _FCV_EXPECTED_EVENT_TYPES)
def test_invariant_5_expected_event_types_present(
    event_type_val: str,
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """Each expected protocol eventType appears at least once."""
    violations = check_event_type_present(fcv_replicas, event_type_val)
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_invariant_6_no_rm_state_oscillation(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """No participant changes RM state after first reaching CLOSED."""
    violations = check_no_rm_state_oscillation(fcv_replicas)
    assert not violations, "RM state oscillation after CLOSED:\n" + "\n".join(
        violations
    )


@pytest.mark.case_ledger_invariants
def test_invariant_7_log_terminates_all_rm_closed(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """The log terminates with every participant in RM=CLOSED."""
    violations = check_rm_closed_termination(fcv_replicas)
    assert not violations, f"Participants not in RM=CLOSED: {violations}"


@pytest.mark.case_ledger_invariants
def test_invariant_9_participant_status_schema_completeness(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole list."""
    violations = check_participant_status_schema_completeness(fcv_replicas)
    assert not violations, (
        f"{len(violations)} ParticipantStatus entries missing required fields:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_10_nested_objects_inlined_in_payload(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.object is an inline dict, not a bare ID string."""
    violations = check_nested_objects_inlined(fcv_replicas)
    assert not violations, (
        f"payloadSnapshot.object is a bare ID string in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_11_payload_context_uses_case_uri(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.context matches the entry's case_id for recorded entries."""
    violations = check_payload_context_uses_case_uri(fcv_replicas)
    assert not violations, (
        f"payloadSnapshot.context != case_id in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_12_genesis_entry_present(
    actor_name: str,
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """logIndex=0 is present in the actor's log."""
    entries = fcv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/fcv/")
    violations = check_genesis_entry_present(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_13_log_starts_at_genesis(
    actor_name: str,
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """The first entry in the actor's sorted log has logIndex=0."""
    entries = fcv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/fcv/")
    violations = check_log_starts_at_genesis(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_14_no_gaps_in_log_indices(
    actor_name: str,
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """No gaps within the actor's present logIndex range."""
    entries = fcv_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/fcv/")
    violations = check_no_gaps_in_log_indices(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_15_cs_state_transitions_observed(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """All three key CS transitions observed in the authoritative log."""
    violations = check_cs_state_transitions_observed(fcv_replicas)
    assert not violations, "Missing CS-transition observations:\n" + "\n".join(
        violations
    )


# ---------------------------------------------------------------------------
# FCV-specific invariants (DEMOMA-12-008/009)
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fcv_validate_report_present(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """``validate_report`` event type is present in the log.

    Spec: DEMOMA-12-002 (Coordinator validates Finder's report).
    """
    violations = check_event_type_present(fcv_replicas, "validate_report")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_invite_actor_to_case_at_least_twice(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least twice (Finder + Vendor invitations).

    Spec: DEMOMA-12-003 (Coordinator invites Finder),
    DEMOMA-12-004 (Coordinator invites Vendor directly).
    """
    violations = check_event_type_count(
        fcv_replicas, "invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_close_case_present(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """``close_case`` event type is present in the log.

    Spec: DEMOMA-12-005 (case reaches terminal RM.CLOSED).
    """
    violations = check_event_type_present(fcv_replicas, "close_case")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_vendor_late_joiner_has_full_history(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """Vendor replica contains all logIndex values present in coordinator replica.

    Vendor is a late joiner (invited after case creation) and must receive the
    full ledger backfill.  Spec: DEMOMA-12-004 (SYNC-2 convergence).
    """
    if not fcv_replicas.get("coordinator") or not fcv_replicas.get("vendor"):
        pytest.skip(
            "coordinator or vendor replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fcv_replicas, early_actor="coordinator", late_actor="vendor"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fcv_vendor_vfd_and_vfd_transitions_observed(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """CS transitions VFd and VFD observed in Vendor's add_participant_status entries.

    Spec: DEMOMA-12-009(4) — Vendor fix path; only Vendor has VFD role.
    """
    vendor_entries = fcv_replicas.get("vendor")
    if not vendor_entries:
        pytest.skip(
            "vendor replica absent; cannot check Vendor VFd/VFD transitions"
        )

    status_entries = [
        e
        for e in vendor_entries
        if event_type(e) == "add_participant_status_to_participant"
    ]
    if not status_entries:
        pytest.skip(
            "No add_participant_status_to_participant entries in vendor log"
        )

    saw_fix_ready = saw_fix_deployed = False
    for e in status_entries:
        fix_ready, fix_deployed, _ = cs_observations_from_snap(payload(e))
        saw_fix_ready |= fix_ready
        saw_fix_deployed |= fix_deployed

    missing: list[str] = []
    if not saw_fix_ready:
        missing.append("Vendor: vfd_state == 'VFd' (fix_ready) never observed")
    if not saw_fix_deployed:
        missing.append(
            "Vendor: vfd_state == 'VFD' (fix_deployed) never observed"
        )
    assert not missing, "Missing Vendor CS transitions:\n" + "\n".join(missing)


@pytest.mark.case_ledger_invariants
def test_fcv_coordinator_p_transition_observed(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """P-transition observed in Coordinator's add_participant_status entries.

    The Coordinator as CASE_OWNER triggers CS.P (DEMOMA-07-003(4)).
    Spec: DEMOMA-12-009(4).
    """
    coordinator_entries = fcv_replicas.get("coordinator")
    if not coordinator_entries:
        pytest.skip(
            "coordinator replica absent; cannot check Coordinator P-transition"
        )

    status_entries = [
        e
        for e in coordinator_entries
        if event_type(e) == "add_participant_status_to_participant"
    ]
    if not status_entries:
        pytest.skip(
            "No add_participant_status_to_participant entries in coordinator log"
        )

    saw_published = any(
        cs_observations_from_snap(payload(e))[2] for e in status_entries
    )
    assert saw_published, (
        "Coordinator: pxa_state starting with 'P' (public-aware) never observed "
        "in add_participant_status_to_participant entries"
    )
