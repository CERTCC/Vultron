"""Case-ledger invariant tests for the four-actor FCCV-extension scenario.

Reads JSONL case-ledger replica files from ``devlogs/fccv-extension/`` and
asserts universal invariants (via the shared ``common`` library) plus
FCCV-extension-specific checks.

Actor set: ``finder``, ``vendor`` (C1/Coordinator1 on coordinator container),
``coordinator`` (C2/Coordinator2 on actor5 container), ``vendor2`` (Vendor on
vendor container), ``case-actor``.

Note on actor-name mapping: the devlog dump uses FVCV-style directory names to
reuse the same docker-compose containers.  ``vendor`` == C1 (coordinator
container); ``coordinator`` == C2 (actor5 container); ``vendor2`` == Vendor
(vendor container).

FCCV-extension-specific invariants:
- ``invite_actor_to_case`` appears at least twice (C2 invitation + Vendor
  invitation via CaseActor).
- ``offer_case_participant`` appears at least once (C2 suggests Vendor via
  ADR-0026).
- Vendor (``vendor2``) is a late joiner — its replica holds the complete log
  from genesis (SYNC-2 backfill).
- CS transitions VFd and VFD observed in Vendor actor-status entries.
- CS transition P (public-aware) observed in C1 (``vendor``) actor-status
  entries (C1 triggers CS.P as CASE_OWNER).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fccv-extension/`` is absent.

Spec: DEMOMA-13 (GitHub issue #1620), CLP-07.
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

_DEMO_NAME = "fccv-extension"

#: Expected protocol eventTypes in a complete FCCV-extension run.
_FCCV_EXTENSION_EXPECTED_EVENT_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
    # C1 invites C2, then CaseActor invites Vendor (via ADR-0026 path).
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    # C2 suggests Vendor via the ADR-0026 suggest-actor flow.
    pytest.param("offer_case_participant", id="offer_case_participant"),
    # C2 accepts C1's invite; Vendor accepts CaseActor's invite.
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
#: Directory names follow FVCV convention: vendor=C1, coordinator=C2, vendor2=Vendor.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),  # C1 (coordinator container)
    pytest.param("coordinator"),  # C2 (actor5 container, coordinator2)
    pytest.param("vendor2"),  # Vendor (vendor container)
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fccv_extension_replicas() -> dict[str, list[dict]]:
    """Load FCCV-extension scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_1_local_hash_chain_consistent(
    actor_name: str,
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Within each contiguous logIndex fragment, hashes chain correctly."""
    entries = fccv_extension_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fccv-extension/"
        )
    violations = check_hash_chain(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_2_cross_actor_hash_agreement(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on entryHash for every shared logIndex."""
    violations = check_cross_actor_hash_agreement(fccv_extension_replicas)
    assert not violations, (
        f"Cross-actor hash mismatches at {len(violations)} logIndex(es):\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_3_cross_actor_payload_actor_agreement(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on payloadSnapshot.actor for every shared logIndex."""
    violations = check_cross_actor_payload_actor_agreement(
        fccv_extension_replicas
    )
    assert (
        not violations
    ), "Cross-actor payloadSnapshot.actor mismatches:\n" + "\n".join(
        violations[:20]
    )


@pytest.mark.case_ledger_invariants
def test_invariant_4_non_empty_payload_snapshot(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Every recorded canonical entry has a non-empty payloadSnapshot."""
    violations = check_non_empty_payload_snapshots(fccv_extension_replicas)
    assert not violations, (
        f"Found {len(violations)} recorded entries with empty payloadSnapshot:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize(
    "event_type_val", _FCCV_EXTENSION_EXPECTED_EVENT_TYPES
)
def test_invariant_5_expected_event_types_present(
    event_type_val: str,
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Each expected protocol eventType appears at least once."""
    violations = check_event_type_present(
        fccv_extension_replicas, event_type_val
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_invariant_6_no_rm_state_oscillation(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """No participant changes RM state after first reaching CLOSED."""
    violations = check_no_rm_state_oscillation(fccv_extension_replicas)
    assert not violations, "RM state oscillation after CLOSED:\n" + "\n".join(
        violations
    )


@pytest.mark.case_ledger_invariants
def test_invariant_7_log_terminates_all_rm_closed(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """The log terminates with every participant in RM=CLOSED."""
    violations = check_rm_closed_termination(fccv_extension_replicas)
    assert not violations, f"Participants not in RM=CLOSED: {violations}"


@pytest.mark.case_ledger_invariants
def test_invariant_9_participant_status_schema_completeness(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole list."""
    violations = check_participant_status_schema_completeness(
        fccv_extension_replicas
    )
    assert not violations, (
        f"{len(violations)} ParticipantStatus entries missing required fields:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_10_nested_objects_inlined_in_payload(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.object is an inline dict, not a bare ID string."""
    violations = check_nested_objects_inlined(fccv_extension_replicas)
    assert not violations, (
        f"payloadSnapshot.object is a bare ID string in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_11_payload_context_uses_case_uri(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.context matches the entry's case_id for recorded entries."""
    violations = check_payload_context_uses_case_uri(fccv_extension_replicas)
    assert not violations, (
        f"payloadSnapshot.context != case_id in {len(violations)} entries:\n"
        + "\n".join(violations[:20])
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_12_genesis_entry_present(
    actor_name: str,
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """logIndex=0 is present in the actor's log."""
    entries = fccv_extension_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fccv-extension/"
        )
    violations = check_genesis_entry_present(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_13_log_starts_at_genesis(
    actor_name: str,
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """The first entry in the actor's sorted log has logIndex=0."""
    entries = fccv_extension_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fccv-extension/"
        )
    violations = check_log_starts_at_genesis(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_14_no_gaps_in_log_indices(
    actor_name: str,
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """No gaps within the actor's present logIndex range."""
    entries = fccv_extension_replicas.get(actor_name)
    if entries is None:
        pytest.skip(
            f"No log found for actor {actor_name!r} in devlogs/fccv-extension/"
        )
    violations = check_no_gaps_in_log_indices(actor_name, entries)
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_invariant_15_cs_state_transitions_observed(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """All three key CS transitions observed in the authoritative log."""
    violations = check_cs_state_transitions_observed(fccv_extension_replicas)
    assert not violations, "Missing CS-transition observations:\n" + "\n".join(
        violations
    )


# ---------------------------------------------------------------------------
# FCCV-extension-specific invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fccv_extension_invite_actor_to_case_at_least_twice(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least twice (C2 + Vendor invitations).

    Spec: DEMOMA-13-003 (C1 invites C2), DEMOMA-13-005 (CaseActor invites
    Vendor via ADR-0026 path).
    """
    violations = check_event_type_count(
        fccv_extension_replicas, "invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fccv_extension_offer_case_participant_present(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """``offer_case_participant`` appears at least once (C2 suggests Vendor).

    Spec: DEMOMA-13-004 (C2 uses the ADR-0026 suggest-actor flow).
    """
    violations = check_event_type_present(
        fccv_extension_replicas, "offer_case_participant"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fccv_extension_vendor_late_joiner_has_full_history(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Vendor (vendor2) replica contains all logIndex values present in C1 (vendor) replica.

    Vendor is a late joiner and must receive the full ledger backfill from
    CaseActor (SYNC-2).
    Spec: DEMOMA-13-007 (SYNC-2 convergence).
    """
    if not fccv_extension_replicas.get(
        "vendor"
    ) or not fccv_extension_replicas.get("vendor2"):
        pytest.skip(
            "vendor (C1) or vendor2 (Vendor) replica absent; "
            "cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fccv_extension_replicas, early_actor="vendor", late_actor="vendor2"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fccv_extension_c2_late_joiner_has_full_history(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """C2 (coordinator) replica contains all logIndex values present in C1 (vendor) replica.

    C2 joins after initial case creation when C1 invites them; CaseActor must
    backfill all prior entries to C2.
    Spec: DEMOMA-13-007 (SYNC-2 convergence).
    """
    if not fccv_extension_replicas.get(
        "vendor"
    ) or not fccv_extension_replicas.get("coordinator"):
        pytest.skip(
            "vendor (C1) or coordinator (C2) replica absent; "
            "cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fccv_extension_replicas, early_actor="vendor", late_actor="coordinator"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fccv_extension_accept_invite_at_least_twice(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` appears at least twice (C2 + Vendor accepts).

    Spec: DEMOMA-13-003 (C2 accepts C1 invite), DEMOMA-13-005 (Vendor accepts
    CaseActor invite via ADR-0026 path).
    """
    violations = check_event_type_count(
        fccv_extension_replicas, "accept_invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""
