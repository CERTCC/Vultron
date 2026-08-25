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

"""Unit tests for polling helpers (issue #2202).

Covers new and modified helpers with positive cases (condition satisfied)
and negative cases (timeout → AssertionError).
"""

import inspect
from unittest.mock import MagicMock

import pytest

from vultron.demo.helpers.polling import (
    CROSS_CONTAINER_TIMEOUT,
    LATE_JOINER_REPLICA_TIMEOUT,
    LATE_JOINER_TIMEOUT,
    PARTICIPANT_JOIN_TIMEOUT,
    wait_for_case_attributed_to,
    wait_for_case_participants,
    wait_for_ledger_event,
    wait_for_pending_inbox_quiescent,
)

CASE_ID = "http://example.com/cases/case-123"
ACTOR_A = "http://example.com/actors/finder"
ACTOR_B = "http://example.com/actors/vendor"


# ---------------------------------------------------------------------------
# Timeout constant tests (AC-7)
# ---------------------------------------------------------------------------


def test_cross_container_timeout_value():
    assert CROSS_CONTAINER_TIMEOUT >= 15.0


def test_participant_join_timeout_value():
    assert PARTICIPANT_JOIN_TIMEOUT >= 20.0


def test_late_joiner_timeout_value():
    assert LATE_JOINER_TIMEOUT >= 90.0


def test_late_joiner_replica_timeout_value():
    assert LATE_JOINER_REPLICA_TIMEOUT >= 30.0


# ---------------------------------------------------------------------------
# wait_for_case_participants tests (AC-2)
# ---------------------------------------------------------------------------


def test_wait_for_case_participants_default_timeout_at_least_15s():
    """Default timeout must survive cross-container CI contention (#2305)."""
    sig = inspect.signature(wait_for_case_participants)
    default = sig.parameters["timeout_seconds"].default
    assert default >= 15.0, (
        f"wait_for_case_participants default ({default}s) is too short; "
        "must be >=15 s for cross-container convergence under CI load"
    )


def test_wait_for_case_participants_accepts_set_parameter():
    """Function must accept expected_actor_ids as a set (AC-2)."""
    sig = inspect.signature(wait_for_case_participants)
    assert "expected_actor_ids" in sig.parameters
    assert "expected_count" not in sig.parameters


def test_wait_for_case_participants_succeeds_when_actors_present():
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "type": "VulnerabilityCase",
        "id": CASE_ID,
        "actor_participant_index": {
            ACTOR_A: "participant-a",
            ACTOR_B: "participant-b",
        },
    }
    wait_for_case_participants(
        vendor_client=client,
        case_id=CASE_ID,
        expected_actor_ids={ACTOR_A, ACTOR_B},
        timeout_seconds=1.0,
    )
    client.get.assert_called()


def test_wait_for_case_participants_subset_check():
    """Subset check: additional actors in index do not prevent success."""
    actor_c = "http://example.com/actors/case-actor"
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "type": "VulnerabilityCase",
        "id": CASE_ID,
        "actor_participant_index": {
            ACTOR_A: "p-a",
            ACTOR_B: "p-b",
            actor_c: "p-c",
        },
    }
    wait_for_case_participants(
        vendor_client=client,
        case_id=CASE_ID,
        expected_actor_ids={ACTOR_A, ACTOR_B},
        timeout_seconds=1.0,
    )


def test_wait_for_case_participants_raises_on_timeout():
    """Missing actor → AssertionError after timeout."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "type": "VulnerabilityCase",
        "id": CASE_ID,
        "actor_participant_index": {ACTOR_A: "p-a"},
    }
    with pytest.raises(
        AssertionError, match="Timed out waiting for participants"
    ):
        wait_for_case_participants(
            vendor_client=client,
            case_id=CASE_ID,
            expected_actor_ids={ACTOR_A, ACTOR_B},
            timeout_seconds=0,
            poll_interval=0.01,
        )


# ---------------------------------------------------------------------------
# wait_for_ledger_event tests (AC-1)
# ---------------------------------------------------------------------------

_LEDGER_ENTRY = {
    "type": "CaseLedgerEntry",
    "case_id": CASE_ID,
    "event_type": "close_case",
    "log_object_id": CASE_ID,
    "log_index": 5,
}


def _make_ledger_client(entries: list) -> MagicMock:
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {str(i): e for i, e in enumerate(entries)}
    return client


def test_wait_for_ledger_event_match_any():
    client = _make_ledger_client([_LEDGER_ENTRY])
    wait_for_ledger_event(
        client=client,
        case_id=CASE_ID,
        event_type="close_case",
        timeout_seconds=1.0,
    )


def test_wait_for_ledger_event_keyed_by_object_id():
    client = _make_ledger_client([_LEDGER_ENTRY])
    wait_for_ledger_event(
        client=client,
        case_id=CASE_ID,
        event_type="close_case",
        log_object_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_ledger_event_keyed_by_min_log_index():
    client = _make_ledger_client([_LEDGER_ENTRY])
    wait_for_ledger_event(
        client=client,
        case_id=CASE_ID,
        event_type="close_case",
        min_log_index=5,
        timeout_seconds=1.0,
    )


def test_wait_for_ledger_event_object_id_mismatch_then_timeout():
    """Wrong log_object_id → never satisfied → AssertionError."""
    client = _make_ledger_client([_LEDGER_ENTRY])
    with pytest.raises(
        AssertionError, match="Timed out waiting for ledger event"
    ):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            event_type="close_case",
            log_object_id="http://example.com/cases/other-case",
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_ledger_event_min_log_index_too_high_then_timeout():
    """Entry with log_index=5 does not satisfy min_log_index=6."""
    client = _make_ledger_client([_LEDGER_ENTRY])
    with pytest.raises(
        AssertionError, match="Timed out waiting for ledger event"
    ):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            event_type="close_case",
            min_log_index=6,
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_ledger_event_wrong_event_type_then_timeout():
    client = _make_ledger_client([_LEDGER_ENTRY])
    with pytest.raises(
        AssertionError, match="Timed out waiting for ledger event"
    ):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            event_type="open_case",
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_ledger_event_empty_ledger_then_timeout():
    client = _make_ledger_client([])
    with pytest.raises(AssertionError):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            event_type="close_case",
            timeout_seconds=0,
            poll_interval=0.01,
        )


# ---------------------------------------------------------------------------
# wait_for_case_attributed_to tests (AC-4)
# ---------------------------------------------------------------------------


def test_wait_for_case_attributed_to_succeeds_string_value():
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "id": CASE_ID,
        "attributed_to": ACTOR_A,
    }
    wait_for_case_attributed_to(
        client=client,
        case_id=CASE_ID,
        expected_attributed_to=ACTOR_A,
        timeout_seconds=1.0,
    )


def test_wait_for_case_attributed_to_succeeds_dict_value():
    """Also handles attributed_to as a dict with an 'id' key."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "id": CASE_ID,
        "attributedTo": {"id": ACTOR_A, "type": "Actor"},
    }
    wait_for_case_attributed_to(
        client=client,
        case_id=CASE_ID,
        expected_attributed_to=ACTOR_A,
        timeout_seconds=1.0,
    )


def test_wait_for_case_attributed_to_wrong_actor_then_timeout():
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "id": CASE_ID,
        "attributed_to": ACTOR_B,
    }
    with pytest.raises(AssertionError, match="Timed out waiting for case"):
        wait_for_case_attributed_to(
            client=client,
            case_id=CASE_ID,
            expected_attributed_to=ACTOR_A,
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_case_attributed_to_missing_field_then_timeout():
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {"id": CASE_ID}
    with pytest.raises(AssertionError):
        wait_for_case_attributed_to(
            client=client,
            case_id=CASE_ID,
            expected_attributed_to=ACTOR_A,
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_case_attributed_to_default_timeout():
    sig = inspect.signature(wait_for_case_attributed_to)
    default = sig.parameters["timeout_seconds"].default
    assert default >= 20.0


# ---------------------------------------------------------------------------
# wait_for_pending_inbox_quiescent tests (AC-8)
# ---------------------------------------------------------------------------


def test_wait_for_pending_inbox_quiescent_absent():
    """Returns immediately when pending inbox is absent (falsy data)."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {}
    wait_for_pending_inbox_quiescent(
        client=client,
        case_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_pending_inbox_quiescent_empty_list():
    """Returns immediately when activity_ids is empty."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {"activity_ids": []}
    wait_for_pending_inbox_quiescent(
        client=client,
        case_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_pending_inbox_quiescent_exception_treated_as_quiescent():
    """Exceptions from client.get → treat as quiescent (inbox does not exist)."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.side_effect = Exception("404 not found")
    wait_for_pending_inbox_quiescent(
        client=client,
        case_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_pending_inbox_quiescent_raises_when_not_empty():
    """Non-empty activity_ids → AssertionError after timeout."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "activity_ids": ["http://example.com/activities/act-1"]
    }
    with pytest.raises(AssertionError, match="PendingCaseInbox"):
        wait_for_pending_inbox_quiescent(
            client=client,
            case_id=CASE_ID,
            timeout_seconds=0,
            poll_interval=0.01,
        )
