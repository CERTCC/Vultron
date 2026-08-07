"""Case-ledger invariant tests for the FCV-Reject three-actor scenario.

Reads JSONL case-ledger replica files from ``devlogs/fcv-reject/`` and
asserts universal invariants (via the shared ``common`` library) plus
FCV-Reject-specific checks.

Actor set: ``finder``, ``coordinator``, ``case-actor``.
Vendor is intentionally absent: it rejected the invitation and was never
added as a case participant, so it has no case ledger replica.

FCV-Reject-specific invariants (issue #2047):
- ``validate_report`` event type is present (Coordinator validates Finder's report).
- ``invite_actor_to_case`` appears at least once (Coordinator invites Vendor).
- ``reject_invite_actor_to_case`` appears at least once (Vendor's rejection recorded).
- ``accept_invite_actor_to_case`` is absent (Vendor rejected, never accepted).
- ``close_case`` event type is present.
- P-transition observed in Coordinator's add_participant_status entries.
- Vendor replica is absent from devlogs (Vendor was never a participant).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fcv-reject/`` is absent.

Spec: GitHub issue #2047, CLP-07.
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
    check_log_starts_at_genesis,
    check_nested_objects_inlined,
    check_no_gaps_in_log_indices,
    check_no_rejected_invite_entries,
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

_DEMO_NAME = "fcv-reject"

#: Expected protocol eventTypes in a complete FCV-Reject run.
_FCV_REJECT_EXPECTED_EVENT_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param(
        "reject_invite_actor_to_case", id="reject_invite_actor_to_case"
    ),
]

#: Actors that have ledger replicas in the FCV-Reject scenario.
#: Vendor is absent — it rejected the invitation and was never a participant.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("coordinator"),
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fcv_reject_replicas() -> dict[str, list[dict]]:
    """Load FCV-Reject scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_1_local_hash_chain_consistent(
    actor_name: str,
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """Within each contiguous logIndex fragment, hashes chain correctly."""
    entries = fcv_reject_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fcv-reject/"
        )
    violations = check_hash_chain(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_2_cross_actor_hash_agreement(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on entryHash for every shared logIndex."""
    violations = check_cross_actor_hash_agreement(fcv_reject_replicas)
    assert not violations, (
        f"Cross-actor hash mismatches at {len(violations)} logIndex(es):\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_3_cross_actor_payload_actor_agreement(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on payloadSnapshot.actor for every shared logIndex."""
    violations = check_cross_actor_payload_actor_agreement(fcv_reject_replicas)
    assert (
        not violations
    ), "Cross-actor payloadSnapshot.actor mismatches:\n" + "\n".join(
        violations[:20]
    )


@pytest.mark.case_ledger_invariants
def test_invariant_4_non_empty_payload_snapshot(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """Every recorded canonical entry has a non-empty payloadSnapshot."""
    violations = check_non_empty_payload_snapshots(fcv_reject_replicas)
    assert not violations, (
        f"Found {len(violations)} recorded entries with empty payloadSnapshot:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("event_type_val", _FCV_REJECT_EXPECTED_EVENT_TYPES)
def test_invariant_5_expected_event_types_present(
    event_type_val: str,
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """Each expected protocol eventType appears at least once."""
    violations = check_event_type_present(fcv_reject_replicas, event_type_val)
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_invariant_6_no_rm_state_oscillation(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """No participant changes RM state after first reaching CLOSED."""
    violations = check_no_rm_state_oscillation(fcv_reject_replicas)
    assert not violations, "RM state oscillation after CLOSED:\n" + "\n".join(
        violations
    )


@pytest.mark.case_ledger_invariants
def test_invariant_7_log_terminates_all_rm_closed(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """The log terminates with every participant in RM=CLOSED."""
    violations = check_rm_closed_termination(fcv_reject_replicas)
    assert not violations, f"Participants not in RM=CLOSED: {violations}"


@pytest.mark.case_ledger_invariants
def test_invariant_9_participant_status_schema_completeness(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole list."""
    violations = check_participant_status_schema_completeness(
        fcv_reject_replicas
    )
    assert not violations, (
        f"{len(violations)} ParticipantStatus entries missing required fields:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_10_nested_objects_inlined_in_payload(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.object is an inline dict, not a bare ID string."""
    violations = check_nested_objects_inlined(fcv_reject_replicas)
    assert not violations, (
        f"payloadSnapshot.object is a bare ID string in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_11_payload_context_uses_case_uri(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.context matches the entry's case_id for recorded entries."""
    violations = check_payload_context_uses_case_uri(fcv_reject_replicas)
    assert not violations, (
        f"payloadSnapshot.context != case_id in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_12_genesis_entry_present(
    actor_name: str,
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """logIndex=0 is present in the actor's log."""
    entries = fcv_reject_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fcv-reject/"
        )
    violations = check_genesis_entry_present(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_13_log_starts_at_genesis(
    actor_name: str,
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """The first entry in the actor's sorted log has logIndex=0."""
    entries = fcv_reject_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fcv-reject/"
        )
    violations = check_log_starts_at_genesis(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_14_no_gaps_in_log_indices(
    actor_name: str,
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """No gaps within the actor's present logIndex range."""
    entries = fcv_reject_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fcv-reject/"
        )
    violations = check_no_gaps_in_log_indices(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_15_cs_state_transitions_observed(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """All three key CS transitions observed in the authoritative log."""
    violations = check_cs_state_transitions_observed(fcv_reject_replicas)
    assert not violations, "Missing CS-transition observations:\n" + "\n".join(
        violations
    )


@pytest.mark.case_ledger_invariants
def test_invariant_clp13_no_rejected_invite_entries(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """No invite_actor_to_case entries with disposition=rejected exist (CLP-13-001).

    The intentional rejection in this scenario is recorded as a
    ``reject_invite_actor_to_case`` event, NOT as a ``invite_actor_to_case``
    entry with disposition=rejected.  Idempotency guards MUST NOT write
    spurious rejected invite entries for duplicate detection.
    """
    violations = check_no_rejected_invite_entries(fcv_reject_replicas)
    assert not violations, (
        f"Found {len(violations)} spurious rejected invite_actor_to_case"
        f" entries (CLP-13-001 violation):\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# FCV-Reject-specific invariants (issue #2047)
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fcv_reject_validate_report_present(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``validate_report`` event type is present in the log.

    Spec: Coordinator validates Finder's report (Phase 1).
    """
    violations = check_event_type_present(
        fcv_reject_replicas, "validate_report"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_reject_invite_actor_to_case_present(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least once (Coordinator invited Vendor).

    Spec: issue #2047 — Coordinator invites Vendor via invite-actor-to-case.
    """
    violations = check_event_type_present(
        fcv_reject_replicas, "invite_actor_to_case"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_reject_reject_invite_actor_to_case_present(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``reject_invite_actor_to_case`` appears at least once (Vendor's rejection).

    Spec: issue #2047 AC-1 — Vendor sends RI (RM.INVALID) then RC (RM.CLOSED);
    the CaseActor records a reject_invite_actor_to_case ledger entry.
    """
    violations = check_event_type_present(
        fcv_reject_replicas, "reject_invite_actor_to_case"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_reject_accept_invite_absent(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` is absent (Vendor rejected, never accepted).

    Spec: issue #2047 AC-2 — Vendor does NOT appear in the final participant list.
    If this event appears, it means the rejection path incorrectly also accepted.
    """
    all_entries = [
        e for entries in fcv_reject_replicas.values() for e in entries
    ]
    bad = [
        e
        for e in all_entries
        if event_type(e) == "accept_invite_actor_to_case"
    ]
    assert not bad, (
        f"Found {len(bad)} unexpected accept_invite_actor_to_case entries "
        f"(Vendor should have rejected, not accepted): "
        + str([e.get("log_index") for e in bad])
    )


@pytest.mark.case_ledger_invariants
def test_fcv_reject_vendor_has_no_replica(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """Vendor has no case ledger replica (was never added as a participant).

    Spec: issue #2047 AC-2 — Vendor is not in the final participant list.
    """
    assert "vendor" not in fcv_reject_replicas, (
        "Vendor has a case ledger replica but should not: "
        "Vendor rejected the invitation and was never a case participant."
    )


@pytest.mark.case_ledger_invariants
def test_fcv_reject_close_case_present(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``close_case`` event type is present in the log.

    Spec: issue #2047 AC-1 — case reaches terminal RM.CLOSED.
    """
    violations = check_event_type_present(fcv_reject_replicas, "close_case")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_reject_coordinator_p_transition_observed(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """P-transition observed in Coordinator's add_participant_status entries.

    The Coordinator as CASE_OWNER triggers CS.P.
    """
    coordinator_entries = fcv_reject_replicas.get("coordinator")
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
