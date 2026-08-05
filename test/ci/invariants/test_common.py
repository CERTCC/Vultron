"""Negative-case tests for every invariant check function in common.py.

Each test confirms that a deliberate violation is detected (non-empty
violation list returned).  The synthetic fixtures in conftest.py supply
the valid baseline; each test modifies that baseline to inject one
specific fault.

AC-1 of ISSUE-1976.
"""

from __future__ import annotations

import hashlib

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
)

CASE_URI = "https://example.org/cases/test-case"
_SHA256 = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
GENESIS_HASH = _SHA256("genesis")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    log_index: int,
    entry_hash: str,
    prev_log_hash: str,
    event_type: str = "noop",
    payload: dict | None = None,
) -> dict:
    return {
        "logIndex": log_index,
        "entryHash": entry_hash,
        "prevLogHash": prev_log_hash,
        "eventType": event_type,
        "case_id": CASE_URI,
        "payloadSnapshot": payload or {},
        "disposition": "recorded",
    }


def _simple_two_entry_chain(actor: str = "case-actor") -> list[dict]:
    h0 = _SHA256(f"{actor}:0")
    h1 = _SHA256(f"{actor}:1")
    return [
        _entry(0, h0, GENESIS_HASH),
        _entry(1, h1, h0),
    ]


# ---------------------------------------------------------------------------
# Invariant 1: check_hash_chain
# ---------------------------------------------------------------------------


def test_check_hash_chain_detects_broken_link():
    broken = _simple_two_entry_chain()
    broken[1]["prevLogHash"] = "a" * 64  # wrong hash
    violations = check_hash_chain("case-actor", broken)
    assert violations


def test_check_hash_chain_detects_missing_entry_hash():
    chain = _simple_two_entry_chain()
    chain[0]["entryHash"] = ""
    violations = check_hash_chain("case-actor", chain)
    assert violations


def test_check_hash_chain_detects_invalid_genesis_prev_hash():
    chain = _simple_two_entry_chain()
    chain[0]["prevLogHash"] = "not-a-hex-hash"
    violations = check_hash_chain("case-actor", chain)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 2: check_cross_actor_hash_agreement
# ---------------------------------------------------------------------------


def test_check_cross_actor_hash_agreement_detects_disagreement():
    h0 = _SHA256("actor-a:0")
    entry_a = _entry(0, h0, GENESIS_HASH)
    entry_b = _entry(0, _SHA256("different"), GENESIS_HASH)
    replicas = {"actor-a": [entry_a], "actor-b": [entry_b]}
    violations = check_cross_actor_hash_agreement(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 3: check_cross_actor_payload_actor_agreement
# ---------------------------------------------------------------------------


def test_check_cross_actor_payload_actor_agreement_detects_disagreement():
    h0 = _SHA256("shared:0")
    entry_a = _entry(0, h0, GENESIS_HASH, payload={"actor": "alice"})
    entry_b = _entry(0, h0, GENESIS_HASH, payload={"actor": "bob"})
    replicas = {"actor-a": [entry_a], "actor-b": [entry_b]}
    violations = check_cross_actor_payload_actor_agreement(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 4: check_non_empty_payload_snapshots
# ---------------------------------------------------------------------------


def test_check_non_empty_payload_snapshots_detects_empty_payload():
    h0 = _SHA256("x:0")
    entry = _entry(0, h0, GENESIS_HASH, payload={})
    entry["disposition"] = "recorded"
    replicas = {"case-actor": [entry]}
    violations = check_non_empty_payload_snapshots(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 5a: check_event_type_present
# ---------------------------------------------------------------------------


def test_check_event_type_present_returns_violation_when_absent():
    h0 = _SHA256("ev:0")
    entry = _entry(0, h0, GENESIS_HASH, event_type="something_else")
    replicas = {"case-actor": [entry]}
    violations = check_event_type_present(replicas, "missing_event_type")
    assert violations


# ---------------------------------------------------------------------------
# Invariant 5b: check_event_type_count
# ---------------------------------------------------------------------------


def test_check_event_type_count_returns_violation_when_below_min():
    h0 = _SHA256("ev:0")
    entry = _entry(
        0, h0, GENESIS_HASH, event_type="add_participant_status_to_participant"
    )
    replicas = {"case-actor": [entry]}
    violations = check_event_type_count(
        replicas, "add_participant_status_to_participant", 3
    )
    assert violations


# ---------------------------------------------------------------------------
# Invariant 6: check_no_rm_state_oscillation
# ---------------------------------------------------------------------------


def test_check_no_rm_state_oscillation_detects_post_closed_transition():
    actor_id = "https://example.org/actors/a"
    h0, h1 = (_SHA256(f"osc:{i}") for i in range(2))
    entries = [
        _entry(
            0,
            h0,
            GENESIS_HASH,
            event_type="add_participant_status_to_participant",
            payload={
                "object": {
                    "attributedTo": actor_id,
                    "rmState": "CLOSED",
                    "emConsentState": "SIGNATORY",
                    "cvdRole": ["FINDER"],
                }
            },
        ),
        _entry(
            1,
            h1,
            h0,
            event_type="add_participant_status_to_participant",
            payload={
                "object": {
                    "attributedTo": actor_id,
                    "rmState": "ACCEPTED",  # post-CLOSED → oscillation
                    "emConsentState": "SIGNATORY",
                    "cvdRole": ["FINDER"],
                }
            },
        ),
    ]
    replicas = {"case-actor": entries}
    violations = check_no_rm_state_oscillation(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 7: check_rm_closed_termination
# ---------------------------------------------------------------------------


def test_check_rm_closed_termination_detects_open_participant():
    actor_id = "https://example.org/actors/open"
    h0 = _SHA256("open:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": actor_id,
                "rmState": "ACCEPTED",  # not CLOSED
                "emConsentState": "SIGNATORY",
                "cvdRole": ["FINDER"],
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_rm_closed_termination(replicas)
    assert violations


def test_check_rm_closed_termination_returns_violation_when_no_status_entries():
    h0 = _SHA256("nostatus:0")
    entry = _entry(
        0, h0, GENESIS_HASH, event_type="create_case", payload={"actor": "x"}
    )
    replicas = {"case-actor": [entry]}
    violations = check_rm_closed_termination(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 8: check_late_joiner_has_full_history
# ---------------------------------------------------------------------------


def test_check_late_joiner_has_full_history_detects_gap(late_joiner_replicas):
    violations = check_late_joiner_has_full_history(
        late_joiner_replicas, early_actor="early", late_actor="late"
    )
    assert violations


def test_check_late_joiner_has_full_history_no_violation_when_complete(
    full_history_replicas,
):
    violations = check_late_joiner_has_full_history(
        full_history_replicas, early_actor="early", late_actor="late"
    )
    assert not violations


# ---------------------------------------------------------------------------
# Invariant 9: check_participant_status_schema_completeness
# ---------------------------------------------------------------------------


def test_check_participant_status_schema_completeness_detects_missing_field():
    h0 = _SHA256("schema:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": "https://example.org/actors/x",
                "rmState": "VALID",
                # emConsentState intentionally missing
                "cvdRole": ["FINDER"],
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_participant_status_schema_completeness(replicas)
    assert violations


def test_check_participant_status_schema_completeness_detects_invalid_role():
    h0 = _SHA256("role:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": "https://example.org/actors/x",
                "rmState": "VALID",
                "emConsentState": "SIGNATORY",
                "cvdRole": ["NOT_A_REAL_ROLE"],
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_participant_status_schema_completeness(replicas)
    assert violations


def test_check_participant_status_schema_completeness_no_status_entries_is_violation():
    h0 = _SHA256("nostatus2:0")
    entry = _entry(
        0, h0, GENESIS_HASH, event_type="create_case", payload={"actor": "x"}
    )
    replicas = {"case-actor": [entry]}
    violations = check_participant_status_schema_completeness(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 10: check_nested_objects_inlined
# ---------------------------------------------------------------------------


def test_check_nested_objects_inlined_detects_bare_id_string():
    h0 = _SHA256("inline:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={"object": "https://example.org/objects/bare-id"},
    )
    replicas = {"case-actor": [entry]}
    violations = check_nested_objects_inlined(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 11: check_payload_context_uses_case_uri
# ---------------------------------------------------------------------------


def test_check_payload_context_uses_case_uri_detects_mismatch():
    h0 = _SHA256("ctx:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="create_case",
        payload={"context": "https://example.org/cases/WRONG"},
    )
    entry["case_id"] = CASE_URI
    replicas = {"case-actor": [entry]}
    violations = check_payload_context_uses_case_uri(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 12: check_genesis_entry_present
# ---------------------------------------------------------------------------


def test_check_genesis_entry_present_detects_missing_genesis():
    h1 = _SHA256("nogenesis:1")
    entry = _entry(1, h1, _SHA256("prev"), event_type="noop")
    violations = check_genesis_entry_present("case-actor", [entry])
    assert violations


def test_check_genesis_entry_present_detects_empty_log():
    violations = check_genesis_entry_present("case-actor", [])
    assert violations


# ---------------------------------------------------------------------------
# Invariant 13: check_log_starts_at_genesis
# ---------------------------------------------------------------------------


def test_check_log_starts_at_genesis_detects_non_zero_start():
    h2 = _SHA256("nzstart:2")
    entry = _entry(2, h2, _SHA256("prev"), event_type="noop")
    violations = check_log_starts_at_genesis("case-actor", [entry])
    assert violations


def test_check_log_starts_at_genesis_detects_empty_log():
    violations = check_log_starts_at_genesis("case-actor", [])
    assert violations


# ---------------------------------------------------------------------------
# Invariant 14: check_no_gaps_in_log_indices
# ---------------------------------------------------------------------------


def test_check_no_gaps_in_log_indices_detects_gap():
    h0 = _SHA256("gap:0")
    entries = [
        _entry(0, h0, GENESIS_HASH),
        _entry(2, _SHA256("gap:2"), h0),  # index 1 is missing
    ]
    violations = check_no_gaps_in_log_indices("case-actor", entries)
    assert violations


def test_check_no_gaps_in_log_indices_detects_empty_log():
    violations = check_no_gaps_in_log_indices("case-actor", [])
    assert violations


# ---------------------------------------------------------------------------
# Invariant 15: check_cs_state_transitions_observed
# ---------------------------------------------------------------------------


def test_check_cs_state_transitions_observed_detects_missing_fix_ready():
    actor_id = "https://example.org/actors/x"
    h0 = _SHA256("csv:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": actor_id,
                "rmState": "VALID",
                "emConsentState": "SIGNATORY",
                "cvdRole": ["FINDER"],
                "vfdState": "vfd",  # never VFd or VFD
                "caseStatus": {"pxaState": "Pxa"},
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_cs_state_transitions_observed(replicas)
    assert violations


def test_check_cs_state_transitions_observed_detects_no_status_entries():
    h0 = _SHA256("csnostatus:0")
    entry = _entry(
        0, h0, GENESIS_HASH, event_type="create_case", payload={"actor": "x"}
    )
    replicas = {"case-actor": [entry]}
    violations = check_cs_state_transitions_observed(replicas)
    assert violations
