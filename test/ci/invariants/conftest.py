"""Synthetic in-memory JSONL fixtures for invariant-function unit tests.

Provides plain ``dict`` lists (same format as ``load_jsonl`` output) constructed
entirely in memory so the 15 invariant check-functions in ``common.py`` run
without a ``devlogs/`` directory on disk.

AC-1 of ISSUE-1976.
"""

from __future__ import annotations

import hashlib

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_URI = "https://example.org/cases/test-case"
ACTOR_A = "https://example.org/actors/actor-a"
ACTOR_B = "https://example.org/actors/actor-b"
GENESIS_HASH = hashlib.sha256(b"genesis").hexdigest()


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _make_entry(
    log_index: int,
    entry_hash: str,
    prev_log_hash: str,
    event_type: str,
    case_id: str = CASE_URI,
    payload_snapshot: dict | None = None,
    disposition: str = "recorded",
) -> dict:
    return {
        "logIndex": log_index,
        "entryHash": entry_hash,
        "prevLogHash": prev_log_hash,
        "eventType": event_type,
        "case_id": case_id,
        "payloadSnapshot": payload_snapshot or {},
        "disposition": disposition,
    }


def _build_chain(tag: str, events: list[dict]) -> list[dict]:
    """Return a hash-chained entry list from a list of event dicts."""
    entries: list[dict] = []
    prev = GENESIS_HASH
    for i, ev in enumerate(events):
        h = _sha(f"{tag}:{i}:{ev.get('eventType', 'noop')}")
        entry = _make_entry(
            log_index=i,
            entry_hash=h,
            prev_log_hash=prev,
            event_type=ev.get("eventType", "noop"),
            payload_snapshot=ev.get("payloadSnapshot"),
        )
        prev = h
        entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Canonical payload fragments (reused across fixtures)
# ---------------------------------------------------------------------------

_VALID_STATUS = {
    "object": {
        "attributedTo": ACTOR_A,
        "rmState": "VALID",
        "emConsentState": "SIGNATORY",
        "cvdRole": ["FINDER"],
        "vfState": "vf",
        "caseStatus": {"pxaState": "pxa"},
    }
}

_ACCEPTED_STATUS = {
    "object": {
        "attributedTo": ACTOR_A,
        "rmState": "ACCEPTED",
        "emConsentState": "SIGNATORY",
        "cvdRole": ["FINDER"],
        "vfState": "VF",
        "caseStatus": {"pxaState": "Pxa"},
    }
}

_CLOSED_STATUS = {
    "actor": ACTOR_A,
    "object": {
        "attributedTo": ACTOR_A,
        "rmState": "CLOSED",
        "emConsentState": "NO_EMBARGO",
        "cvdRole": ["FINDER"],
        "vfState": "VF",
        "dState": "D",
        "caseStatus": {"pxaState": "PXA"},
    },
}


def _base_events() -> list[dict]:
    """Five-event sequence that satisfies all 15 invariant checks."""
    return [
        {
            "eventType": "create_case",
            "payloadSnapshot": {
                "actor": ACTOR_A,
                "context": CASE_URI,
            },
        },
        {
            "eventType": "add_participant_status_to_participant",
            "payloadSnapshot": _VALID_STATUS,
        },
        {
            "eventType": "add_participant_status_to_participant",
            "payloadSnapshot": _ACCEPTED_STATUS,
        },
        {
            "eventType": "add_participant_status_to_participant",
            "payloadSnapshot": _CLOSED_STATUS,
        },
        {
            "eventType": "close_case",
            "payloadSnapshot": {"actor": ACTOR_A, "context": CASE_URI},
        },
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def single_actor_replicas() -> dict[str, list[dict]]:
    """One actor (case-actor) with a valid five-entry hash chain."""
    return {"case-actor": _build_chain("case-actor", _base_events())}


@pytest.fixture
def two_actor_replicas() -> dict[str, list[dict]]:
    """Two actors sharing an identical five-entry chain."""
    chain = _build_chain("case-actor", _base_events())
    return {"case-actor": chain, "finder": list(chain)}


@pytest.fixture
def late_joiner_replicas() -> dict[str, list[dict]]:
    """Early actor has five entries; late actor only has the last two (gap 0-2)."""
    early = _build_chain("case-actor", _base_events())
    return {"early": early, "late": early[3:]}


@pytest.fixture
def full_history_replicas() -> dict[str, list[dict]]:
    """Late actor has the complete chain (no missing entries)."""
    chain = _build_chain("case-actor", _base_events())
    return {"early": chain, "late": list(chain)}


# ---------------------------------------------------------------------------
# DEMOCI-10-005: all-skip guard
# ---------------------------------------------------------------------------


class _AllSkipGuard:
    """Force exit-code 1 when every collected test was skipped.

    When devlogs are absent, load_devlogs() calls pytest.skip() at fixture
    level.  A session where all tests skip exits 0 by default, which makes
    CI report green even though no invariant was actually checked.
    DEMOCI-10-005 requires the harness to exit non-zero in this case.
    """

    def __init__(self) -> None:
        self._outcomes: list[str] = []

    def pytest_runtest_logreport(self, report) -> None:
        if report.when == "call" and not getattr(report, "wasxfail", None):
            self._outcomes.append(report.outcome)
        elif report.when == "setup" and report.outcome == "skipped":
            # Fixture-level skip: no "call" phase follows.
            self._outcomes.append("skipped")

    def pytest_sessionfinish(self, session) -> None:
        if self._outcomes and all(o == "skipped" for o in self._outcomes):
            session.exitstatus = 1


def pytest_configure(config) -> None:
    config.pluginmanager.register(_AllSkipGuard(), "_all_skip_guard")
