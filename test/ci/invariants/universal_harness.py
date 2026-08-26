"""Factory for the 16 universal case-ledger invariant test functions.

Each scenario harness calls::

    globals().update(
        make_universal_invariant_tests(
            replicas_fixture="<scenario>_replicas",
            chain_actors=_CHAIN_ACTORS,
            expected_event_types=_XXX_EXPECTED_EVENT_TYPES,
        )
    )

to inject all 16 universal test functions without copying their
implementations (ISSUE-2007, AC-1).

The injected functions use ``request.getfixturevalue(replicas_fixture)``
to retrieve the calling module's scenario-specific replicas fixture at
pytest collection time.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from test.ci.invariants.common import (
    check_causal_edges,
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
    check_per_actor_replica_divergence,
    check_rm_closed_termination,
    load_narrative_edges,
)


def make_universal_invariant_tests(  # noqa: C901
    replicas_fixture: str,
    chain_actors: list,
    expected_event_types: list,
    check_fix_ready: bool = True,
    narrative_path: str | None = None,
) -> dict[str, Any]:
    """Return the universal invariant test functions keyed by name.

    Parameters
    ----------
    replicas_fixture:
        Name of the module-scoped fixture in the calling harness that
        returns ``dict[str, list[dict]]`` — e.g. ``"fv_replicas"``.
    chain_actors:
        Per-scenario ``_CHAIN_ACTORS`` list (``pytest.param`` entries or
        plain strings) passed to ``@pytest.mark.parametrize``.
    expected_event_types:
        Per-scenario ``_XXX_EXPECTED_EVENT_TYPES`` list passed to
        ``@pytest.mark.parametrize``.
    check_fix_ready:
        Forwarded to ``check_cs_state_transitions_observed`` and
        ``check_per_actor_replica_divergence``; set to ``False`` for the
        ``fcv-reject`` scenario where Vendor never advances the VFD state
        machine.
    narrative_path:
        Repo-relative path to the scenario narrative Markdown page that
        carries the machine-readable ``causal_edges:`` front-matter block.
        When provided, injects ``test_invariant_16_causal_edges_in_ledger_order``.
        When absent, that test is omitted (DEMOMA-22-005).
    """
    calling_module = sys._getframe(1).f_globals.get("__name__", __name__)

    @pytest.mark.case_ledger_invariants
    @pytest.mark.parametrize("actor_name", chain_actors)
    def test_invariant_1_local_hash_chain_consistent(
        actor_name: str,
        request: pytest.FixtureRequest,
    ) -> None:
        """Within each contiguous logIndex fragment, hashes chain correctly."""
        replicas = request.getfixturevalue(replicas_fixture)
        entries = replicas.get(actor_name)
        if entries is None:
            pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")
        violations = check_hash_chain(actor_name, entries)
        assert not violations, "\n".join(violations)

    @pytest.mark.case_ledger_invariants
    def test_invariant_2_cross_actor_hash_agreement(
        request: pytest.FixtureRequest,
    ) -> None:
        """All actors agree on entryHash for every shared logIndex."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_cross_actor_hash_agreement(replicas)
        assert not violations, (
            f"Cross-actor hash mismatches at {len(violations)} logIndex(es):\n"
            + "\n".join(violations[:20])
        )

    @pytest.mark.case_ledger_invariants
    def test_invariant_3_cross_actor_payload_actor_agreement(
        request: pytest.FixtureRequest,
    ) -> None:
        """All actors agree on payloadSnapshot.actor for every shared logIndex."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_cross_actor_payload_actor_agreement(replicas)
        assert (
            not violations
        ), "Cross-actor payloadSnapshot.actor mismatches:\n" + "\n".join(
            violations[:20]
        )

    @pytest.mark.case_ledger_invariants
    def test_invariant_4_non_empty_payload_snapshot(
        request: pytest.FixtureRequest,
    ) -> None:
        """Every recorded canonical entry has a non-empty payloadSnapshot."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_non_empty_payload_snapshots(replicas)
        assert not violations, (
            f"Found {len(violations)} recorded entries with empty payloadSnapshot:\n"
            + "\n".join(violations[:20])
        )

    @pytest.mark.case_ledger_invariants
    @pytest.mark.parametrize("event_type_val", expected_event_types)
    def test_invariant_5_expected_event_types_present(
        event_type_val: str,
        request: pytest.FixtureRequest,
    ) -> None:
        """Each expected protocol eventType appears at least once."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_event_type_present(replicas, event_type_val)
        assert not violations, violations[0] if violations else ""

    @pytest.mark.case_ledger_invariants
    def test_invariant_6_no_rm_state_oscillation(
        request: pytest.FixtureRequest,
    ) -> None:
        """No participant changes RM state after first reaching CLOSED."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_no_rm_state_oscillation(replicas)
        assert (
            not violations
        ), "RM state oscillation after CLOSED:\n" + "\n".join(violations)

    @pytest.mark.case_ledger_invariants
    @pytest.mark.xfail(
        strict=False,
        reason="pre-existing bug #2505: FV demo CaseActor never reaches RM.CLOSED",
    )
    def test_invariant_7_log_terminates_all_rm_closed(
        request: pytest.FixtureRequest,
    ) -> None:
        """The log terminates with every participant in RM=CLOSED."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_rm_closed_termination(replicas)
        assert (
            not violations
        ), f"Participants not in RM=CLOSED at log end: {violations}"

    @pytest.mark.case_ledger_invariants
    def test_invariant_9_participant_status_schema_completeness(
        request: pytest.FixtureRequest,
    ) -> None:
        """Every ParticipantStatus snapshot includes emConsentState and cvdRole list."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_participant_status_schema_completeness(replicas)
        assert not violations, (
            f"{len(violations)} ParticipantStatus entries missing required fields:\n"
            + "\n".join(violations[:20])
        )

    @pytest.mark.case_ledger_invariants
    def test_invariant_10_nested_objects_inlined_in_payload(
        request: pytest.FixtureRequest,
    ) -> None:
        """payloadSnapshot.object is an inline dict, not a bare ID string."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_nested_objects_inlined(replicas)
        assert not violations, (
            f"payloadSnapshot.object is a bare ID string in {len(violations)} entries:\n"
            + "\n".join(violations[:20])
        )

    @pytest.mark.case_ledger_invariants
    def test_invariant_11_payload_context_uses_case_uri(
        request: pytest.FixtureRequest,
    ) -> None:
        """payloadSnapshot.context matches the entry's case_id for recorded entries."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_payload_context_uses_case_uri(replicas)
        assert not violations, (
            f"payloadSnapshot.context != case_id in {len(violations)} entries:\n"
            + "\n".join(violations[:20])
        )

    @pytest.mark.case_ledger_invariants
    @pytest.mark.parametrize("actor_name", chain_actors)
    def test_invariant_12_genesis_entry_present(
        actor_name: str,
        request: pytest.FixtureRequest,
    ) -> None:
        """logIndex=0 is present in the actor's log."""
        replicas = request.getfixturevalue(replicas_fixture)
        entries = replicas.get(actor_name)
        if entries is None:
            pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")
        violations = check_genesis_entry_present(actor_name, entries)
        assert not violations, "\n".join(violations)

    @pytest.mark.case_ledger_invariants
    @pytest.mark.parametrize("actor_name", chain_actors)
    def test_invariant_13_log_starts_at_genesis(
        actor_name: str,
        request: pytest.FixtureRequest,
    ) -> None:
        """The first entry in the actor's sorted log has logIndex=0."""
        replicas = request.getfixturevalue(replicas_fixture)
        entries = replicas.get(actor_name)
        if entries is None:
            pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")
        violations = check_log_starts_at_genesis(actor_name, entries)
        assert not violations, "\n".join(violations)

    @pytest.mark.case_ledger_invariants
    @pytest.mark.parametrize("actor_name", chain_actors)
    def test_invariant_14_no_gaps_in_log_indices(
        actor_name: str,
        request: pytest.FixtureRequest,
    ) -> None:
        """No gaps within the actor's present logIndex range."""
        replicas = request.getfixturevalue(replicas_fixture)
        entries = replicas.get(actor_name)
        if entries is None:
            pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")
        violations = check_no_gaps_in_log_indices(actor_name, entries)
        assert not violations, "\n".join(violations)

    @pytest.mark.case_ledger_invariants
    def test_invariant_15_cs_state_transitions_observed(
        request: pytest.FixtureRequest,
    ) -> None:
        """All key CS transitions are recorded in the authoritative log."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_cs_state_transitions_observed(
            replicas, check_fix_ready=check_fix_ready
        )
        assert (
            not violations
        ), "Missing CS-transition observations:\n" + "\n".join(violations)

    @pytest.mark.case_ledger_invariants
    def test_invariant_clp13_no_rejected_invite_entries(
        request: pytest.FixtureRequest,
    ) -> None:
        """No invite_actor_to_case entries with disposition=rejected exist (CLP-13-001)."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_no_rejected_invite_entries(replicas)
        assert not violations, (
            f"Found {len(violations)} spurious rejected invite_actor_to_case"
            f" entries (CLP-13-001 violation):\n" + "\n".join(violations)
        )

    @pytest.mark.case_ledger_invariants
    @pytest.mark.xfail(
        strict=False,
        reason="pre-existing bug #2505: FV demo CaseActor never reaches RM.CLOSED",
    )
    def test_invariant_per_actor_replica_divergence(
        request: pytest.FixtureRequest,
    ) -> None:
        """Each non-case-actor replica satisfies the same state invariants as the authoritative log."""
        replicas = request.getfixturevalue(replicas_fixture)
        violations = check_per_actor_replica_divergence(
            replicas, check_fix_ready=check_fix_ready
        )
        assert not violations, (
            f"{len(violations)} per-actor invariant violation(s):\n"
            + "\n".join(violations)
        )

    result = {
        "test_invariant_1_local_hash_chain_consistent": test_invariant_1_local_hash_chain_consistent,
        "test_invariant_2_cross_actor_hash_agreement": test_invariant_2_cross_actor_hash_agreement,
        "test_invariant_3_cross_actor_payload_actor_agreement": test_invariant_3_cross_actor_payload_actor_agreement,
        "test_invariant_4_non_empty_payload_snapshot": test_invariant_4_non_empty_payload_snapshot,
        "test_invariant_5_expected_event_types_present": test_invariant_5_expected_event_types_present,
        "test_invariant_6_no_rm_state_oscillation": test_invariant_6_no_rm_state_oscillation,
        "test_invariant_7_log_terminates_all_rm_closed": test_invariant_7_log_terminates_all_rm_closed,
        "test_invariant_9_participant_status_schema_completeness": test_invariant_9_participant_status_schema_completeness,
        "test_invariant_10_nested_objects_inlined_in_payload": test_invariant_10_nested_objects_inlined_in_payload,
        "test_invariant_11_payload_context_uses_case_uri": test_invariant_11_payload_context_uses_case_uri,
        "test_invariant_12_genesis_entry_present": test_invariant_12_genesis_entry_present,
        "test_invariant_13_log_starts_at_genesis": test_invariant_13_log_starts_at_genesis,
        "test_invariant_14_no_gaps_in_log_indices": test_invariant_14_no_gaps_in_log_indices,
        "test_invariant_15_cs_state_transitions_observed": test_invariant_15_cs_state_transitions_observed,
        "test_invariant_clp13_no_rejected_invite_entries": test_invariant_clp13_no_rejected_invite_entries,
        "test_invariant_per_actor_replica_divergence": test_invariant_per_actor_replica_divergence,
    }

    if narrative_path is not None:
        _narrative_path = narrative_path

        @pytest.mark.case_ledger_invariants
        def test_invariant_16_causal_edges_in_ledger_order(
            request: pytest.FixtureRequest,
        ) -> None:
            """Every declared causal edge appears in the ledger in causal order (DEMOMA-22-005).

            Reads the scenario narrative page's YAML front-matter to obtain the
            machine-readable ``causal_edges:`` list, then verifies that for each
            observable edge (antecedent, consequent) there exists at least one
            antecedent entry that precedes at least one consequent entry in the
            authoritative log.
            """
            replicas = request.getfixturevalue(replicas_fixture)
            edges = load_narrative_edges(_narrative_path)
            violations = check_causal_edges(replicas, edges)
            assert not violations, (
                f"{len(violations)} causal-edge ordering violation(s):\n"
                + "\n".join(violations)
            )

        test_invariant_16_causal_edges_in_ledger_order.__module__ = (
            calling_module
        )
        result["test_invariant_16_causal_edges_in_ledger_order"] = (
            test_invariant_16_causal_edges_in_ledger_order
        )

    for fn in result.values():
        fn.__module__ = calling_module
    return result
