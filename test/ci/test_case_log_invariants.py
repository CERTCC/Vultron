#!/usr/bin/env python
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
"""CI case-log invariant assertion harness (issue #925).

Parses the JSONL case-log replica files produced by the two-actor demo
(``devlogs/<demo>/<actor>/*-case-log.jsonl``) and asserts a set of
canonical-log invariants.

All invariants that are not yet passing are decorated with
``pytest.mark.xfail`` and cite the implementation issue that will resolve
them.  The ratchet workflow:

- Each invariant is a discrete test function (AC-2).
- Invariants expected to pass today have no ``xfail`` decorator (AC-3).
- Future-fix invariants use ``@pytest.mark.xfail(strict=False, reason=...)``
  so CI reports-but-does-not-fail on unexpected passes (AC-5).
- When a fix lands, remove the ``xfail`` decorator from the corresponding
  test to promote it to a permanent regression guard (AC-3).

See ``README-case-log-ratchet.md`` in this directory for the full ratchet
workflow documentation (AC-6).

All tests are tagged ``@pytest.mark.case_log_invariants`` for targeted
CI selection (``uv run pytest -m case_log_invariants``).  They skip
automatically when ``devlogs/`` is absent, so they are safe to include in
the regular unit-test collection.

Spec: CLP-07.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Sentinel hash used for the genesis entry (mirrors vultron.core.models.case_log).
GENESIS_HASH: str = "0" * 64

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_DEVLOGS_DIR: Path = _REPO_ROOT / "devlogs"

#: Expected protocol eventTypes that must appear at least once in the
#: case-actor log for a complete two-actor CVD run (AC-4.5).
EXPECTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "validate_report",
        "accept_report",
        "propose_embargo",
        "accept_embargo",
        "notify_fix_ready",
        "notify_fix_deployed",
        "notify_published",
        "close_case",
        "add_note",
        "announce_case_log_entry",
    }
)


# ---------------------------------------------------------------------------
# Low-level accessors
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict]:
    """Return parsed JSON objects from a JSONL file, skipping blank lines."""
    entries: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def _log_index(entry: dict) -> int:
    """Return the ``log_index`` from an entry dict."""
    return int(entry.get("log_index", entry.get("logIndex", -1)))


def _entry_hash(entry: dict) -> str:
    """Return the ``entryHash`` from an entry dict."""
    return str(entry.get("entryHash", entry.get("entry_hash", "")))


def _prev_log_hash(entry: dict) -> str:
    """Return the ``prevLogHash`` from an entry dict."""
    return str(entry.get("prevLogHash", entry.get("prev_log_hash", "")))


def _event_type(entry: dict) -> str:
    """Return the ``eventType`` from an entry dict."""
    return str(entry.get("eventType", entry.get("event_type", "")))


def _payload(entry: dict) -> dict:
    """Return the ``payloadSnapshot`` from an entry dict."""
    snap = entry.get("payloadSnapshot", entry.get("payload_snapshot", {}))
    return snap if isinstance(snap, dict) else {}


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def case_log_replicas() -> dict[str, list[dict]]:
    """Load all JSONL case log files, grouped by actor name.

    Reads every ``*-case-log.jsonl`` file under ``devlogs/`` (relative to
    the repo root) and groups entries by the containing actor directory name
    (e.g. ``"finder"``, ``"vendor"``, ``"case-actor"``).  Entries within
    each actor are sorted by ``log_index`` ascending.

    Skips all tests in this module when ``devlogs/`` is absent or empty,
    so the suite remains safe to collect without demo artifacts.

    Returns:
        ``{actor_name: [sorted entry dicts, ...]}``.
    """
    if not _DEVLOGS_DIR.exists():
        pytest.skip(
            "devlogs/ directory not found — run the two-actor demo first "
            "(see test/ci/README-case-log-ratchet.md)"
        )

    replicas: dict[str, list[dict]] = {}
    for jsonl_file in sorted(_DEVLOGS_DIR.glob("**/*-case-log.jsonl")):
        # Directory layout: devlogs/<demo_name>/<actor_name>/*.jsonl
        actor_name = jsonl_file.parent.name
        replicas.setdefault(actor_name, []).extend(_load_jsonl(jsonl_file))

    if not replicas:
        pytest.skip(
            "No *-case-log.jsonl files found under devlogs/ — "
            "run the two-actor demo first (see test/ci/README-case-log-ratchet.md)"
        )

    # Stable sort within each actor by log_index ascending.
    for actor in replicas:
        replicas[actor] = sorted(replicas[actor], key=_log_index)

    return replicas


# ---------------------------------------------------------------------------
# Helper: select the authoritative log (prefer case-actor replica)
# ---------------------------------------------------------------------------


def _auth_entries(replicas: dict[str, list[dict]]) -> list[dict]:
    """Return the authoritative log, preferring the ``case-actor`` replica."""
    return replicas.get("case-actor", next(iter(replicas.values()), []))


# ---------------------------------------------------------------------------
# Invariant 1 — expected to pass today (AC-4.1)
# ---------------------------------------------------------------------------


@pytest.mark.case_log_invariants
def test_invariant_1_local_hash_chain_consistent(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """Each actor's local hash chain is internally consistent (AC-4.1).

    For entries sorted by ``log_index``:

    - The first entry's ``prevLogHash`` MUST equal ``GENESIS_HASH``.
    - Each subsequent entry's ``prevLogHash`` MUST equal its predecessor's
      ``entryHash``.

    This invariant is expected to pass today.
    Spec: CLP-07.
    """
    for actor, entries in case_log_replicas.items():
        if not entries:
            continue

        first = entries[0]
        actual_prev = _prev_log_hash(first)
        assert actual_prev == GENESIS_HASH, (
            f"Actor {actor!r}: first entry (logIndex={_log_index(first)}) "
            f"prevLogHash={actual_prev!r} != GENESIS_HASH"
        )

        for i, entry in enumerate(entries[1:], start=1):
            expected = _entry_hash(entries[i - 1])
            assert expected, (
                f"Actor {actor!r}: entry[{i - 1}] "
                f"(logIndex={_log_index(entries[i - 1])}) "
                f"has no entryHash — cannot verify hash chain"
            )
            actual = _prev_log_hash(entry)
            assert actual, (
                f"Actor {actor!r}: entry[{i}] (logIndex={_log_index(entry)}) "
                f"has no prevLogHash — cannot verify hash chain"
            )
            assert actual == expected, (
                f"Actor {actor!r}: entry[{i}] (logIndex={_log_index(entry)}) "
                f"prevLogHash={actual[:16]!r} != "
                f"entry[{i - 1}] entryHash={expected[:16]!r}"
            )


# ---------------------------------------------------------------------------
# Invariants 2–11 — xfail until upstream fixes land
# ---------------------------------------------------------------------------


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Cross-actor hash agreement requires CaseActor commit-path uniqueness; "
        "will pass when #789 lands"
    ),
)
def test_invariant_2_cross_actor_hash_agreement(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on the entryHash for every shared logIndex (AC-4.2).

    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    by_index: dict[int, dict[str, str]] = {}
    for actor, entries in case_log_replicas.items():
        for entry in entries:
            idx = _log_index(entry)
            by_index.setdefault(idx, {})[actor] = _entry_hash(entry)

    mismatches = [
        f"logIndex={idx}: {actor_hashes}"
        for idx, actor_hashes in sorted(by_index.items())
        if len(actor_hashes) > 1 and len(set(actor_hashes.values())) > 1
    ]
    assert not mismatches, (
        f"Cross-actor hash mismatches at {len(mismatches)} logIndex(es):\n"
        + "\n".join(mismatches[:20])
    )


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Cross-actor payloadSnapshot.actor agreement requires CaseActor "
        "commit-path uniqueness; will pass when #789 lands"
    ),
)
def test_invariant_3_cross_actor_payload_actor_agreement(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on payloadSnapshot.actor for every shared logIndex (AC-4.3).

    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    by_index: dict[int, dict[str, str | None]] = {}
    for actor, entries in case_log_replicas.items():
        for entry in entries:
            idx = _log_index(entry)
            snap = _payload(entry)
            actor_val = snap.get("actor")
            by_index.setdefault(idx, {})[actor] = (
                str(actor_val) if actor_val is not None else None
            )

    mismatches = [
        f"logIndex={idx}: {actor_vals}"
        for idx, actor_vals in sorted(by_index.items())
        if len(actor_vals) > 1 and len(set(actor_vals.values())) > 1
    ]
    assert not mismatches, (
        f"Cross-actor payloadSnapshot.actor mismatches at "
        f"{len(mismatches)} logIndex(es):\n" + "\n".join(mismatches[:20])
    )


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Non-empty payloadSnapshot requires the commit-boundary guard and "
        "removal of synthetic checkpoint events (see issue #789)"
    ),
)
def test_invariant_4_non_empty_payload_snapshot(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """Every recorded canonical entry has a non-empty payloadSnapshot (AC-4.4).

    Rejection entries (``disposition != "recorded"``) are excluded.
    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    empty = [
        f"Actor {actor!r} logIndex={_log_index(e)} eventType={_event_type(e)!r}"
        for actor, entries in case_log_replicas.items()
        for e in entries
        if e.get("disposition", "recorded") == "recorded" and not _payload(e)
    ]
    assert not empty, (
        f"Found {len(empty)} recorded entries with empty payloadSnapshot:\n"
        + "\n".join(empty[:20])
    )


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "All expected protocol eventTypes require the CaseActor commit-path "
        "implementation; will pass when #789 ACs are satisfied"
    ),
)
def test_invariant_5_expected_event_types_present(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """All expected protocol eventTypes appear at least once (AC-4.5).

    Checked against the ``case-actor`` replica (authoritative log).
    Falls back to any available replica when no ``case-actor`` key exists.
    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    auth = _auth_entries(case_log_replicas)
    found = {_event_type(e) for e in auth}
    missing = EXPECTED_EVENT_TYPES - found
    assert not missing, (
        f"Missing expected eventTypes in case-actor log: {sorted(missing)}\n"
        f"Found: {sorted(found)}"
    )


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "RM terminal-state guard must prevent add_participant_status "
        "oscillation after CLOSED; see issue #789"
    ),
)
def test_invariant_6_no_rm_state_oscillation(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """No participant changes RM state after first reaching CLOSED (AC-4.6).

    Scans all ``add_participant_status`` entries and verifies that once a
    participant reaches ``RM=CLOSED``, no further state change is recorded.
    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    auth = _auth_entries(case_log_replicas)
    status_entries = [
        e for e in auth if _event_type(e) == "add_participant_status"
    ]

    rm_history: dict[str, list[str]] = {}
    for entry in status_entries:
        snap = _payload(entry)
        p_id = snap.get("attributedTo") or snap.get("attributed_to")
        rm_state = snap.get("rmState") or snap.get("rm_state")
        if p_id and rm_state:
            rm_history.setdefault(str(p_id), []).append(str(rm_state))

    violations = [
        f"Participant {p_id!r} changed RM state after CLOSED: {states}"
        for p_id, states in rm_history.items()
        for i, state in enumerate(states)
        if state.upper() in ("CLOSED", "RM.CLOSED") and i < len(states) - 1
    ]
    assert not violations, "RM state oscillation after CLOSED:\n" + "\n".join(
        violations
    )


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Log must terminate with all participants in RM=CLOSED; "
        "requires the RM terminal-state guard (see issue #789)"
    ),
)
def test_invariant_7_log_terminates_all_rm_closed(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """The log terminates with every participant in RM=CLOSED (AC-4.7).

    Checks the final ``add_participant_status`` entry per participant.
    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    auth = _auth_entries(case_log_replicas)
    latest_rm: dict[str, str] = {}
    for entry in auth:
        if _event_type(entry) != "add_participant_status":
            continue
        snap = _payload(entry)
        p_id = snap.get("attributedTo") or snap.get("attributed_to")
        rm_state = snap.get("rmState") or snap.get("rm_state")
        if p_id and rm_state:
            latest_rm[str(p_id)] = str(rm_state)

    assert (
        latest_rm
    ), "No add_participant_status entries found in case-actor log"

    not_closed = {
        p: s
        for p, s in latest_rm.items()
        if s.upper() not in ("CLOSED", "RM.CLOSED")
    }
    assert (
        not not_closed
    ), f"Participants not in RM=CLOSED at log end: {not_closed}"


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Late-joining participants require join-time history backfill; "
        "will pass when #791 join-time backfill AC lands"
    ),
)
def test_invariant_8_late_joiner_has_full_history(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """Late-joining participants have the full pre-join canonical history (AC-4.8).

    Checks that the ``finder`` replica contains all logIndex values
    present in the ``vendor`` replica.  The finder joins after
    report-to-case promotion, so pre-join entries must be backfilled.
    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    vendor_entries = case_log_replicas.get("vendor", [])
    finder_entries = case_log_replicas.get("finder", [])

    if not vendor_entries or not finder_entries:
        pytest.skip(
            "vendor or finder replica absent; cannot check late-joiner invariant"
        )

    vendor_indices = {_log_index(e) for e in vendor_entries}
    finder_indices = {_log_index(e) for e in finder_entries}
    missing = sorted(vendor_indices - finder_indices)

    assert not missing, (
        f"Finder replica missing {len(missing)} pre-join log entries "
        f"present in vendor: logIndex in {missing[:10]}"
        + (" (truncated)" if len(missing) > 10 else "")
    )


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "ParticipantStatus entries must include emConsentState and cvdRole; "
        "requires the ParticipantStatus schema completeness fix (see issue #789)"
    ),
)
def test_invariant_9_participant_status_schema_completeness(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole (AC-4.9).

    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    auth = _auth_entries(case_log_replicas)
    status_entries = [
        e for e in auth if _event_type(e) == "add_participant_status"
    ]
    assert (
        status_entries
    ), "No add_participant_status entries found; cannot check schema completeness"

    incomplete = []
    for entry in status_entries:
        snap = _payload(entry)
        missing_fields = []
        if "emConsentState" not in snap and "em_consent_state" not in snap:
            missing_fields.append("emConsentState")
        if "cvdRole" not in snap and "cvd_role" not in snap:
            missing_fields.append("cvdRole")
        if missing_fields:
            incomplete.append(
                f"logIndex={_log_index(entry)}: missing {missing_fields}"
            )

    assert not incomplete, (
        f"{len(incomplete)} ParticipantStatus entries missing required fields:\n"
        + "\n".join(incomplete[:20])
    )


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Nested protocol objects must be inlined in payloadSnapshot, not "
        "represented as bare ID strings; requires the "
        "'Inline nested objects in canonical snapshots' fix"
    ),
)
def test_invariant_10_nested_objects_inlined_in_payload(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.object is an inline dict, not a bare ID string (AC-4.10).

    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    auth = _auth_entries(case_log_replicas)
    bare_ids = [
        (
            f"logIndex={_log_index(e)} eventType={_event_type(e)!r}: "
            f"object={str(_payload(e).get('object', ''))[:60]!r}"
        )
        for e in auth
        if isinstance(
            _payload(e).get("object") or _payload(e).get("object_"), str
        )
    ]
    assert not bare_ids, (
        f"payloadSnapshot.object is a bare ID string in {len(bare_ids)} entries:\n"
        + "\n".join(bare_ids[:20])
    )


@pytest.mark.case_log_invariants
@pytest.mark.xfail(
    strict=False,
    reason=(
        "payloadSnapshot context must reference the case URI, not the report "
        "URI; requires the 'Snapshot context normalization at promotion' fix"
    ),
)
def test_invariant_11_payload_context_uses_case_uri(
    case_log_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.context matches the entry's case_id for recorded entries (AC-4.11).

    When this xfail is unexpectedly promoted to XPASS, remove the
    ``xfail`` decorator to make it a permanent regression guard.
    """
    auth = _auth_entries(case_log_replicas)
    mismatches = []
    for entry in auth:
        if entry.get("disposition", "recorded") != "recorded":
            continue
        case_id = entry.get("case_id", "")
        snap = _payload(entry)
        context = snap.get("context")
        if context is None:
            continue
        if isinstance(context, str) and context != case_id:
            mismatches.append(
                f"logIndex={_log_index(entry)} eventType={_event_type(entry)!r}: "
                f"context={context[:60]!r} != case_id={case_id[:60]!r}"
            )

    assert not mismatches, (
        f"payloadSnapshot.context != case_id in {len(mismatches)} entries:\n"
        + "\n".join(mismatches[:20])
    )
