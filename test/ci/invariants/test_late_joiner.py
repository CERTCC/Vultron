"""Edge-case tests for check_late_joiner_has_full_history.

Covers: gap before join point, out-of-order delivery, and empty replica
edge cases.

AC-1 of ISSUE-1976.
"""

from __future__ import annotations

import hashlib

from test.ci.invariants.common import check_late_joiner_has_full_history

_SHA256 = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
GENESIS_HASH = _SHA256("genesis")


def _entry(log_index: int, entry_hash: str, prev_hash: str) -> dict:
    return {
        "logIndex": log_index,
        "entryHash": entry_hash,
        "prevLogHash": prev_hash,
        "eventType": "noop",
        "case_id": "https://example.org/cases/test",
        "payloadSnapshot": {},
    }


def _chain(tag: str, length: int) -> list[dict]:
    entries = []
    prev = GENESIS_HASH
    for i in range(length):
        h = _SHA256(f"{tag}:{i}")
        entries.append(_entry(i, h, prev))
        prev = h
    return entries


class TestGapBeforeJoinPoint:
    """Late actor joined mid-chain; entries before join are absent."""

    def test_missing_pre_join_entries_detected(self):
        early = _chain("early", 6)
        late = early[3:]  # only indices 3-5
        replicas = {"early": early, "late": late}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert violations
        assert "3" in violations[0] or "missing" in violations[0].lower()

    def test_partial_gap_includes_missing_count(self):
        early = _chain("early", 10)
        late = early[5:]  # missing indices 0-4
        replicas = {"early": early, "late": late}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert violations
        assert (
            "5" in violations[0]
        )  # "5" missing entries or index list shows 0..4


class TestOutOfOrderDelivery:
    """Entries present but delivered in a different order."""

    def test_out_of_order_late_entries_still_detected_if_some_missing(self):
        early = _chain("ooo", 5)
        # late has entries [4, 2, 3] — missing 0 and 1
        late = [early[4], early[2], early[3]]
        replicas = {"early": early, "late": late}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert violations

    def test_out_of_order_but_complete_has_no_violations(self):
        early = _chain("ooo2", 4)
        late_shuffled = [early[3], early[0], early[2], early[1]]
        replicas = {"early": early, "late": late_shuffled}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert not violations


class TestEmptyReplica:
    """Empty replica edge cases."""

    def test_late_actor_absent_from_replicas_returns_no_violations(self):
        early = _chain("empty-test", 5)
        replicas = {"early": early}
        # late_actor not in replicas at all
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert not violations

    def test_early_actor_absent_returns_no_violations(self):
        late = _chain("empty-test2", 5)
        replicas = {"late": late}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert not violations

    def test_both_empty_returns_no_violations(self):
        replicas = {"early": [], "late": []}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert not violations

    def test_late_has_empty_list_returns_no_violations(self):
        early = _chain("empty-test3", 3)
        replicas = {"early": early, "late": []}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert not violations


class TestFullHistoryNoViolation:
    """Late actor has complete history → no violations."""

    def test_late_actor_has_all_entries(self):
        chain = _chain("full", 5)
        replicas = {"early": chain, "late": list(chain)}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert not violations

    def test_late_actor_has_superset_of_early(self):
        early = _chain("super", 3)
        extra_entry = _entry(3, _SHA256("super:3"), early[-1]["entryHash"])
        late = list(early) + [extra_entry]
        replicas = {"early": early, "late": late}
        violations = check_late_joiner_has_full_history(
            replicas, early_actor="early", late_actor="late"
        )
        assert not violations
