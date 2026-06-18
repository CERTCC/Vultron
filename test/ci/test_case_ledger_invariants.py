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
"""CI case-ledger invariant assertion harness (issue #925).

Parses the JSONL case-ledger replica files produced by the two-actor demo
(``devlogs/<demo>/<actor>/*-case-ledger.jsonl``) and asserts a set of
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

See ``README-case-ledger-ratchet.md`` in this directory for the full ratchet
workflow documentation (AC-6).

All tests are tagged ``@pytest.mark.case_ledger_invariants`` for targeted
CI selection (``uv run pytest -m case_ledger_invariants``).  They skip
automatically when ``devlogs/`` is absent, so they are safe to include in
the regular unit-test collection.

Spec: CLP-07.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.roles import CVDRole

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Sentinel hash used for the genesis entry (mirrors vultron.core.models.case_ledger).
#: After per-case genesis hash (CLP-08), genesis prevLogHash is a SHA-256 of case metadata.
_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_DEVLOGS_DIR: Path = _REPO_ROOT / "devlogs"

#: Expected protocol eventTypes that must appear at least once in the
#: case-actor log for a complete two-actor CVD run (AC-4.5).
#: Values are ``MessageSemantics`` string values (StrEnum auto() → lowercase).
#: - fix_ready/fix_deployed/published transitions are recorded as
#:   ``add_participant_status_to_participant`` entries; invariant 15 checks
#:   the actual CS state values within those snapshots.
#: - announce_case_ledger_entry is the replication envelope used by the
#:   CaseActor to broadcast canonical entries, not a canonical entry type
#:   itself (CLP-10-004); it is excluded from EXPECTED_EVENT_TYPES.
EXPECTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "validate_report",
        "add_participant_status_to_participant",
        "close_case",
        "add_note_to_case",
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


def _case_id(entry: dict) -> str:
    """Return the ``case_id`` from an entry dict (handles camelCase JSONL)."""
    return str(entry.get("case_id", entry.get("caseId", "")))


def _payload(entry: dict) -> dict:
    """Return the ``payloadSnapshot`` from an entry dict."""
    snap = entry.get("payloadSnapshot", entry.get("payload_snapshot", {}))
    return snap if isinstance(snap, dict) else {}


def _participant_status_identity_and_rm(
    snapshot: dict,
) -> tuple[str | None, str | None]:
    """Extract participant id + RM state from a status payload snapshot.

    Historical logs may encode ``ParticipantStatus`` directly in
    ``payloadSnapshot`` or nest it under an ``Add`` activity's ``object``.
    """
    p_id = snapshot.get("attributedTo") or snapshot.get("attributed_to")
    rm_state = snapshot.get("rmState") or snapshot.get("rm_state")
    if p_id and rm_state:
        return str(p_id), str(rm_state)

    nested = snapshot.get("object")
    if isinstance(nested, dict):
        nested_id = nested.get("attributedTo") or nested.get("attributed_to")
        nested_rm = nested.get("rmState") or nested.get("rm_state")
        if nested_id and nested_rm:
            return str(nested_id), str(nested_rm)

    return None, None


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def case_ledger_replicas() -> dict[str, list[dict]]:
    """Load all JSONL case ledger files, grouped by actor name.

    Reads every ``*-case-ledger.jsonl`` file under ``devlogs/`` (relative to
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
            "(see test/ci/README-case-ledger-ratchet.md)"
        )

    replicas: dict[str, list[dict]] = {}
    for jsonl_file in sorted(_DEVLOGS_DIR.glob("**/*-case-ledger.jsonl")):
        # Directory layout: devlogs/<demo_name>/<actor_name>/*.jsonl
        actor_name = jsonl_file.parent.name
        replicas.setdefault(actor_name, []).extend(_load_jsonl(jsonl_file))

    if not replicas:
        pytest.skip(
            "No *-case-ledger.jsonl files found under devlogs/ — "
            "run the two-actor demo first (see test/ci/README-case-ledger-ratchet.md)"
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


def _contiguous_fragments(entries: list[dict]) -> list[list[dict]]:
    """Split a logIndex-sorted entry list into maximal contiguous runs.

    Entries are grouped by consecutive logIndex values.  A gap between
    logIndex N and N+2 (i.e. N+1 is missing) starts a new fragment.

    Example: entries with logIndices [2,3,5,6,7,9,10] → three fragments:
        [[2,3], [5,6,7], [9,10]]
    """
    if not entries:
        return []
    fragments: list[list[dict]] = []
    current: list[dict] = [entries[0]]
    for entry in entries[1:]:
        if _log_index(entry) == _log_index(current[-1]) + 1:
            current.append(entry)
        else:
            fragments.append(current)
            current = [entry]
    fragments.append(current)
    return fragments


# ---------------------------------------------------------------------------
# Invariant 1 — per-actor internal hash-chain consistency
# ---------------------------------------------------------------------------

_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("finder"),
]


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _CHAIN_ACTORS)
def test_invariant_1_local_hash_chain_consistent(
    actor_name: str,
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """Within each contiguous logIndex fragment, hashes chain correctly.

    Entries are first split into maximal contiguous runs by logIndex.
    Within each run, consecutive entries must satisfy:

    - ``entry[N].prevLogHash == entry[N-1].entryHash``
    - If the run starts at ``logIndex=0``, that entry's ``prevLogHash``
      must be a valid 64-character hex SHA-256 (the per-case genesis hash,
      CLP-08).

    Cross-fragment boundaries are **not** checked: if logIndex 4 is absent
    the check does not assert that entry 5's prevLogHash equals entry 3's
    entryHash (it doesn't — it references the hash of the missing entry 4).

    Promoted from xfail: confirmed passing once #789 prerequisites landed.
    Spec: CLP-07.
    """
    entries = case_ledger_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")

    for fragment in _contiguous_fragments(entries):
        first = fragment[0]
        first_idx = _log_index(first)

        if first_idx == 0:
            actual_prev = _prev_log_hash(first)
            assert _SHA256_HEX_PATTERN.match(actual_prev), (
                f"Actor {actor_name!r}: fragment starting at logIndex=0 "
                f"prevLogHash={actual_prev!r} is not a valid 64-char hex "
                f"SHA-256 (per-case genesis hash, CLP-08)"
            )

        for i, entry in enumerate(fragment[1:], start=1):
            prev = fragment[i - 1]
            expected = _entry_hash(prev)
            assert expected, (
                f"Actor {actor_name!r}: logIndex={_log_index(prev)} "
                f"has no entryHash — cannot verify hash chain"
            )
            actual = _prev_log_hash(entry)
            assert actual, (
                f"Actor {actor_name!r}: logIndex={_log_index(entry)} "
                f"has no prevLogHash — cannot verify hash chain"
            )
            assert actual == expected, (
                f"Actor {actor_name!r}: logIndex={_log_index(entry)} "
                f"prevLogHash={actual[:16]!r} != "
                f"logIndex={_log_index(prev)} entryHash={expected[:16]!r}"
            )


# ---------------------------------------------------------------------------
# Invariants 2–11 — xfail until upstream fixes land
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_invariant_2_cross_actor_hash_agreement(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on the entryHash for every shared logIndex (AC-4.2)."""
    by_index: dict[int, dict[str, str]] = {}
    for actor, entries in case_ledger_replicas.items():
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


@pytest.mark.case_ledger_invariants
def test_invariant_3_cross_actor_payload_actor_agreement(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """All actors agree on payloadSnapshot.actor for every shared logIndex (AC-4.3)."""
    by_index: dict[int, dict[str, str | None]] = {}
    for actor, entries in case_ledger_replicas.items():
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


@pytest.mark.case_ledger_invariants
def test_invariant_4_non_empty_payload_snapshot(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """Every recorded canonical entry has a non-empty payloadSnapshot (AC-4.4).

    Rejection entries (``disposition != "recorded"``) are excluded.
    """
    empty = [
        f"Actor {actor!r} logIndex={_log_index(e)} eventType={_event_type(e)!r}"
        for actor, entries in case_ledger_replicas.items()
        for e in entries
        if e.get("disposition", "recorded") == "recorded" and not _payload(e)
    ]
    assert not empty, (
        f"Found {len(empty)} recorded entries with empty payloadSnapshot:\n"
        + "\n".join(empty[:20])
    )


_EVENT_TYPE_PARAMS = [
    pytest.param(
        "validate_report",
        marks=[],
        id="validate_report",
    ),
    pytest.param(
        "add_participant_status_to_participant",
        marks=[],
        id="add_participant_status_to_participant",
    ),
    pytest.param(
        "close_case",
        marks=[],
        id="close_case",
    ),
    pytest.param(
        "add_note_to_case",
        marks=[],
        id="add_note_to_case",
    ),
]


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("event_type", _EVENT_TYPE_PARAMS)
def test_invariant_5_expected_event_types_present(
    event_type: str,
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """Each expected protocol eventType appears at least once (AC-4.5).

    Parameterized per event type; each type is tested separately so that
    passing types do not mask missing types, and so that xfail can be
    removed per-type as fixes land.

    Checked against the ``case-actor`` replica (authoritative log).
    Falls back to any available replica when no ``case-actor`` key exists.

    AC-3: Promoted to hard pass for validate_report (#1029);
    other types remain xfail pending #1026 follow-on fixes.
    """
    auth = _auth_entries(case_ledger_replicas)
    found = {_event_type(e) for e in auth}
    assert event_type in found, (
        f"Expected eventType {event_type!r} not found in case-actor log.\n"
        f"Found: {sorted(found)}"
    )


@pytest.mark.case_ledger_invariants
def test_invariant_6_no_rm_state_oscillation(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """No participant changes RM state after first reaching CLOSED (AC-4.6).

    Scans all ``add_participant_status`` entries and verifies that once a
    participant reaches ``RM=CLOSED``, no further state change is recorded.
    Promoted from xfail: confirmed passing as of PR #936.
    """
    auth = _auth_entries(case_ledger_replicas)
    status_entries = [
        e
        for e in auth
        if _event_type(e) == "add_participant_status_to_participant"
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


@pytest.mark.case_ledger_invariants
def test_invariant_7_log_terminates_all_rm_closed(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """The log terminates with every participant in RM=CLOSED (AC-4.7).

    Checks the final ``add_participant_status`` entry per participant.
    """
    auth = _auth_entries(case_ledger_replicas)
    latest_rm: dict[str, str] = {}
    for entry in auth:
        if _event_type(entry) != "add_participant_status_to_participant":
            continue
        p_id, rm_state = _participant_status_identity_and_rm(_payload(entry))
        if p_id and rm_state:
            latest_rm[p_id] = rm_state

    assert (
        latest_rm
    ), "No add_participant_status_to_participant entries found in case-actor log"

    not_closed = {
        p: s
        for p, s in latest_rm.items()
        if s.upper() not in ("CLOSED", "RM.CLOSED")
    }
    assert (
        not not_closed
    ), f"Participants not in RM=CLOSED at log end: {not_closed}"


@pytest.mark.case_ledger_invariants
def test_invariant_8_late_joiner_has_full_history(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """Late-joining participants have the full pre-join canonical history (AC-4.8).

    Checks that the ``finder`` replica contains all logIndex values
    present in the ``vendor`` replica.  The finder joins after
    report-to-case promotion, so pre-join entries must be backfilled.
    Promoted from xfail: confirmed passing once #937 (join-time backfill) landed.
    """
    vendor_entries = case_ledger_replicas.get("vendor", [])
    finder_entries = case_ledger_replicas.get("finder", [])

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


@pytest.mark.case_ledger_invariants
def test_invariant_9_participant_status_schema_completeness(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole list (AC-4.9)."""
    auth = _auth_entries(case_ledger_replicas)
    status_entries = [
        e
        for e in auth
        if _event_type(e) == "add_participant_status_to_participant"
    ]
    assert (
        status_entries
    ), "No add_participant_status_to_participant entries found; cannot check schema completeness"

    incomplete = []
    for entry in status_entries:
        snap = _payload(entry)
        if isinstance(snap.get("object"), dict):
            snap = snap["object"]
        elif isinstance(snap.get("object_"), dict):
            snap = snap["object_"]
        missing_fields = []
        if "emConsentState" not in snap and "em_consent_state" not in snap:
            missing_fields.append("emConsentState")
        if "cvdRole" not in snap and "cvd_role" not in snap:
            missing_fields.append("cvdRole")
        em_consent = snap.get("emConsentState", snap.get("em_consent_state"))
        valid_em_states = {
            *(state.name for state in PEC),
            *(state.value for state in PEC),
        }
        if em_consent not in valid_em_states:
            missing_fields.append("valid emConsentState value")
        cvd_role = snap.get("cvdRole", snap.get("cvd_role"))
        valid_roles = {
            *(role.name for role in CVDRole),
            *(role.value for role in CVDRole),
        }
        if not isinstance(cvd_role, list) or not cvd_role:
            missing_fields.append("non-empty cvdRole list")
        elif any(role not in valid_roles for role in cvd_role):
            missing_fields.append("valid cvdRole value")
        if missing_fields:
            incomplete.append(
                f"logIndex={_log_index(entry)}: missing {missing_fields}"
            )

    assert not incomplete, (
        f"{len(incomplete)} ParticipantStatus entries missing required fields:\n"
        + "\n".join(incomplete[:20])
    )


@pytest.mark.case_ledger_invariants
def test_invariant_10_nested_objects_inlined_in_payload(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.object is an inline dict, not a bare ID string (AC-4.10).

    Promoted from xfail: confirmed passing as of PR #936.
    """
    auth = _auth_entries(case_ledger_replicas)
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


@pytest.mark.case_ledger_invariants
def test_invariant_11_payload_context_uses_case_uri(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """payloadSnapshot.context matches the entry's case_id for recorded entries (AC-4.11).

    Promoted from xfail: confirmed passing as of PR #936.
    """
    auth = _auth_entries(case_ledger_replicas)
    mismatches = []
    for entry in auth:
        if entry.get("disposition", "recorded") != "recorded":
            continue
        case_id = _case_id(entry)
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


# ---------------------------------------------------------------------------
# Invariants 12–14 — per-actor case-ledger quality (two convergence groups)
#
# These tests are split into two groups that converge independently:
#
#   Group A — Fragment integrity (inv 1, inv 14):
#     "For the entries you *do* have, are they self-consistent?"
#     - Invariant 1  (hash chain): each consecutive pair must hash-chain.
#     - Invariant 14 (contiguity): no gaps within the range you hold.
#     The finder passes both inv-1 and inv-14 now that #789 prerequisites
#     are in place.  Both converge independently of backfill.
#
#   Group B — Log completeness (inv 12, inv 13):
#     "Do you hold the full log from genesis?"
#     - Invariant 12: logIndex=0 is present.
#     - Invariant 13: the first sorted entry has logIndex=0.
#     The finder is xfail on both until join-time backfill (#937) lands.
#
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Group A — Fragment contiguity (inv 14)
#
# Checks that the entries an actor *does* hold are gapless within their
# range.  Uses min_idx→max_idx, not 0→max, so a late joiner that holds
# a contiguous run [2..N] passes.
#
# Finder passes (fragment is contiguous).
# ---------------------------------------------------------------------------

_FRAGMENT_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("finder"),  # passes: finder fragment is contiguous
]


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _FRAGMENT_ACTORS)
def test_invariant_14_no_gaps_in_log_indices(
    actor_name: str,
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """No gaps within the actor's present logIndex range (fragment contiguity).

    Checks the range ``[min_idx, max_idx]`` — not necessarily starting from 0.
    A late joiner that holds entries ``[2..N]`` passes; the completeness tests
    (inv 12–13) separately assert that ``logIndex=0`` is also present.

    This invariant is in **Group A** (fragment integrity) and converges
    independently of the join-time backfill fix (#937).
    Spec: CLP-07.
    """
    entries = case_ledger_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")

    indices = sorted(_log_index(e) for e in entries)
    min_idx, max_idx = indices[0], indices[-1]
    expected = list(range(min_idx, max_idx + 1))

    gaps = sorted(set(expected) - set(indices))
    assert not gaps, (
        f"Actor {actor_name!r}: {len(gaps)} gap(s) in logIndex sequence "
        f"[{min_idx}..{max_idx}]: missing {gaps[:10]}"
        + (" (truncated)" if len(gaps) > 10 else "")
    )


# ---------------------------------------------------------------------------
# Group B — Log completeness (inv 12–13)
#
# Checks that an actor holds the *full* log from genesis (logIndex=0).
# Promoted from xfail: confirmed passing once #937 (join-time backfill) landed.
# ---------------------------------------------------------------------------

#: Actor lists for completeness checks.
_COMPLETE_LOG_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("finder"),
]


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _COMPLETE_LOG_ACTORS)
def test_invariant_12_genesis_entry_present(
    actor_name: str,
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """logIndex=0 is present in the actor's log (log completeness).

    Every actor must receive or own the genesis entry.  The finder is a
    late joiner; its replica is backfilled at join-time via #937.

    This invariant is in **Group B** (log completeness).
    Spec: CLP-07.
    """
    entries = case_ledger_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")

    indices = {_log_index(e) for e in entries}
    assert 0 in indices, (
        f"Actor {actor_name!r}: logIndex=0 is absent from the log. "
        f"Lowest present index: {min(indices)}"
    )


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("actor_name", _COMPLETE_LOG_ACTORS)
def test_invariant_13_log_starts_at_genesis(
    actor_name: str,
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """The first entry in the actor's sorted log has logIndex=0 (log ordering).

    The fixture sorts entries by logIndex ascending, so this invariant checks
    both that logIndex=0 exists (invariant 12) and that the log is ordered.

    This invariant is in **Group B** (log completeness).
    Spec: CLP-07.
    """
    entries = case_ledger_replicas.get(actor_name)
    if entries is None:
        pytest.skip(f"No log found for actor {actor_name!r} in devlogs/")

    first_index = _log_index(entries[0])
    assert first_index == 0, (
        f"Actor {actor_name!r}: first entry has logIndex={first_index}, "
        f"expected 0 (log is incomplete or not starting at genesis)"
    )


# ---------------------------------------------------------------------------
# Invariant 15 — CS-transition coverage
# ---------------------------------------------------------------------------


def _cs_observations_from_snap(snap: dict) -> tuple[bool, bool, bool]:
    """Extract CS-transition observations from a ParticipantStatus payload.

    Drills into the nested ``object`` / ``object_`` if the snapshot wraps a
    ``ParticipantStatus`` inside an ``Add`` activity, then checks:

    - ``vfd_state == "VFd"`` (fix_ready)
    - ``vfd_state == "VFD"`` (fix_deployed)
    - ``pxa_state`` first char ``"P"`` (published / public-aware)

    Handles both camelCase and snake_case key variants.

    Returns:
        ``(fix_ready_seen, fix_deployed_seen, published_seen)``
    """
    if isinstance(snap.get("object"), dict):
        snap = snap["object"]
    elif isinstance(snap.get("object_"), dict):
        snap = snap["object_"]

    vfd_state = snap.get("vfdState") or snap.get("vfd_state")

    case_status = snap.get("caseStatus") or snap.get("case_status")
    pxa_state: str | None = None
    if isinstance(case_status, dict):
        pxa_state = case_status.get("pxaState") or case_status.get("pxa_state")

    return (
        vfd_state == "VFd",
        vfd_state == "VFD",
        isinstance(pxa_state, str) and pxa_state[:1] == "P",
    )


@pytest.mark.case_ledger_invariants
def test_invariant_15_cs_state_transitions_observed(
    case_ledger_replicas: dict[str, list[dict]],
) -> None:
    """All three key CS transitions are recorded in the authoritative log.

    Inspects the ``payloadSnapshot`` of every
    ``add_participant_status_to_participant`` entry in the case-actor log and
    asserts that each of the following was observed at least once:

    - ``vfd_state == "VFd"`` — fix_ready transition occurred.
    - ``vfd_state == "VFD"`` — fix_deployed transition occurred.
    - ``pxa_state`` whose first character is uppercase ``"P"`` —
      published / public-aware transition reached.  Field presence alone is
      insufficient; ``case_status`` may exist at baseline with a lowercase
      ``pxa`` value.

    Handles both ``snake_case`` and ``camelCase`` key variants defensively,
    mirroring the approach used in invariants 9–11.

    Spec: CLP-07.
    """
    auth = _auth_entries(case_ledger_replicas)
    status_entries = [
        e
        for e in auth
        if _event_type(e) == "add_participant_status_to_participant"
    ]
    assert status_entries, (
        "No add_participant_status_to_participant entries found; "
        "cannot check CS-transition invariant"
    )

    saw_fix_ready = saw_fix_deployed = saw_published = False
    for entry in status_entries:
        fix_ready, fix_deployed, published = _cs_observations_from_snap(
            _payload(entry)
        )
        saw_fix_ready |= fix_ready
        saw_fix_deployed |= fix_deployed
        saw_published |= published

    missing = []
    if not saw_fix_ready:
        missing.append("vfd_state == 'VFd' (fix_ready) never observed")
    if not saw_fix_deployed:
        missing.append("vfd_state == 'VFD' (fix_deployed) never observed")
    if not saw_published:
        missing.append(
            "pxa_state starting with 'P' (published/public-aware) never observed"
        )

    assert not missing, (
        "Missing CS-transition observations in "
        "add_participant_status_to_participant entries:\n" + "\n".join(missing)
    )
