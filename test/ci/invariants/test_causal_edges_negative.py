"""Negative-path tests for check_causal_edges (AC-5, DEMOMA-22-005).

Verifies that ``check_causal_edges`` returns violations when the declared
edge list is corrupted — either by reversing the expected ordering, by naming
event types that are absent from the log, or by supplying an empty log.

These tests use synthetic replica data; no real devlog fixtures are needed.
They are deliberately NOT tagged ``@pytest.mark.case_ledger_invariants`` so
they run in the regular unit suite, not the integration suite.
"""

from __future__ import annotations

from test.ci.invariants.common import check_causal_edges

# ---------------------------------------------------------------------------
# Synthetic ledger helpers
# ---------------------------------------------------------------------------


def _make_entry(log_idx: int, evt: str) -> dict:
    """Return a minimal ledger entry dict for testing."""
    return {"log_index": log_idx, "eventType": evt}


def _replicas(*entries: dict) -> dict[str, list[dict]]:
    """Wrap a flat entry list into a replicas dict with a case-actor key."""
    return {"case-actor": list(entries)}


# ---------------------------------------------------------------------------
# Negative tests: corrupted ordering
# ---------------------------------------------------------------------------


def test_reversed_edge_fails() -> None:
    """Declaring A → B fails when B always precedes A in the log."""
    replicas = _replicas(
        _make_entry(0, "engage_case"),
        _make_entry(1, "validate_report"),
    )
    edges = [{"antecedent": "validate_report", "consequent": "engage_case"}]
    # validate_report only appears at index 1; engage_case only at index 0.
    # min(antecedent)=1 >= max(consequent)=0 → violation.
    violations = check_causal_edges(replicas, edges)
    assert violations, "Expected a violation for reversed edge, got none"
    assert "validate_report" in violations[0]
    assert "engage_case" in violations[0]


def test_missing_antecedent_fails() -> None:
    """A declared antecedent that does not appear in the log is a violation."""
    replicas = _replicas(
        _make_entry(0, "engage_case"),
        _make_entry(1, "close_case"),
    )
    edges = [{"antecedent": "validate_report", "consequent": "engage_case"}]
    violations = check_causal_edges(replicas, edges)
    assert violations
    assert "validate_report" in violations[0]


def test_missing_consequent_fails() -> None:
    """A declared consequent that does not appear in the log is a violation."""
    replicas = _replicas(
        _make_entry(0, "validate_report"),
        _make_entry(1, "add_note_to_case"),
    )
    edges = [{"antecedent": "validate_report", "consequent": "engage_case"}]
    violations = check_causal_edges(replicas, edges)
    assert violations
    assert "engage_case" in violations[0]


def test_unobservable_edge_is_skipped() -> None:
    """Edges with ``observable: false`` are not checked and never produce violations."""
    replicas = _replicas(
        _make_entry(0, "engage_case"),
        _make_entry(1, "validate_report"),
    )
    # reversed order but observable=false → must not fail
    edges = [
        {
            "antecedent": "validate_report",
            "consequent": "engage_case",
            "observable": False,
        }
    ]
    violations = check_causal_edges(replicas, edges)
    assert (
        not violations
    ), f"Unexpected violations for unobservable edge: {violations}"


def test_empty_log_returns_violation() -> None:
    """An empty authoritative log produces a single top-level violation."""
    replicas: dict = {}
    edges = [{"antecedent": "validate_report", "consequent": "engage_case"}]
    violations = check_causal_edges(replicas, edges)
    assert violations
    assert "No authoritative log" in violations[0]


def test_valid_ordering_passes() -> None:
    """A correctly ordered (A, B) pair produces no violations."""
    replicas = _replicas(
        _make_entry(0, "validate_report"),
        _make_entry(1, "engage_case"),
    )
    edges = [{"antecedent": "validate_report", "consequent": "engage_case"}]
    violations = check_causal_edges(replicas, edges)
    assert not violations, f"Unexpected violations: {violations}"


def test_multiple_edges_partial_failure_reported() -> None:
    """When multiple edges are declared, only violated ones appear in the result."""
    replicas = _replicas(
        _make_entry(0, "validate_report"),
        _make_entry(1, "engage_case"),
        _make_entry(2, "close_case"),
        # add_note_to_case is absent — any edge requiring it will fail
    )
    edges = [
        {"antecedent": "validate_report", "consequent": "engage_case"},  # pass
        {"antecedent": "validate_report", "consequent": "close_case"},  # pass
        {
            "antecedent": "validate_report",
            "consequent": "add_note_to_case",
        },  # fail: absent
    ]
    violations = check_causal_edges(replicas, edges)
    assert len(violations) == 1
    assert "add_note_to_case" in violations[0]
