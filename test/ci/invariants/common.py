"""Shared case-ledger invariant library for per-scenario test files.

Provides composable building-block functions used by all scenario-specific
invariant test files under ``test/ci/invariants/``.  Each building block
either returns a list of violation strings (empty = pass) or raises
``pytest.skip`` when the necessary log data is absent.

Scenario test files import and call these helpers rather than duplicating the
invariant logic inline.  All universal invariants (hash-chain consistency,
cross-actor agreement, RM-closed termination, CS transitions, event-type
completeness) live here.  Scenario-specific checks (e.g., FCV requires
``invite_actor_to_case`` at least twice) belong in the per-scenario file.

Usage pattern::

    from test.ci.invariants.common import (
        load_devlogs,
        check_hash_chain,
        check_cross_actor_hash_agreement,
        check_rm_closed_termination,
        ...
    )

Spec: CLP-07, DEMOMA-12-008.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole

# ---------------------------------------------------------------------------
# Repository layout
# ---------------------------------------------------------------------------

_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REPO_ROOT: Path = Path(__file__).resolve().parents[3]
_DEVLOGS_DIR: Path = _REPO_ROOT / "devlogs"


# ---------------------------------------------------------------------------
# Low-level accessors (re-exported for use in scenario-specific files)
# ---------------------------------------------------------------------------


def load_jsonl(path: Path) -> list[dict]:
    """Return parsed JSON objects from a JSONL file, skipping blank lines."""
    entries: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def log_index(entry: dict) -> int:
    """Return the ``log_index`` from an entry dict."""
    return int(entry.get("log_index", entry.get("logIndex", -1)))


def entry_hash(entry: dict) -> str:
    """Return the ``entryHash`` from an entry dict."""
    return str(entry.get("entryHash", entry.get("entry_hash", "")))


def prev_log_hash(entry: dict) -> str:
    """Return the ``prevLogHash`` from an entry dict."""
    return str(entry.get("prevLogHash", entry.get("prev_log_hash", "")))


def event_type(entry: dict) -> str:
    """Return the ``eventType`` from an entry dict."""
    return str(entry.get("eventType", entry.get("event_type", "")))


def case_id(entry: dict) -> str:
    """Return the ``case_id`` from an entry dict (handles camelCase JSONL)."""
    return str(entry.get("case_id", entry.get("caseId", "")))


def payload(entry: dict) -> dict:
    """Return the ``payloadSnapshot`` from an entry dict."""
    snap = entry.get("payloadSnapshot", entry.get("payload_snapshot", {}))
    return snap if isinstance(snap, dict) else {}


def participant_status_identity_and_rm(
    snapshot: dict,
) -> tuple[str | None, str | None]:
    """Extract participant id + RM state from a status payload snapshot."""
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
# Fixture helpers
# ---------------------------------------------------------------------------


def load_devlogs(
    demo_name: str | None = None,
) -> dict[str, list[dict]]:
    """Load JSONL case ledger files, grouped by actor name.

    Reads every ``*-case-ledger.jsonl`` file under ``devlogs/`` (relative to
    the repo root), optionally scoped to a ``demo_name`` sub-directory.
    Groups entries by the containing actor directory name and sorts each
    actor's entries by ``log_index`` ascending.

    Calls ``pytest.skip`` when ``devlogs/`` is absent, empty, or (when
    ``demo_name`` is given) the scenario sub-directory is absent or empty.

    Returns:
        ``{actor_name: [sorted entry dicts, ...]}``.
    """
    if not _DEVLOGS_DIR.exists():
        pytest.skip(
            "devlogs/ directory not found — run the demo first "
            "(see test/ci/README-case-log-ratchet.md)"
        )

    search_root = _DEVLOGS_DIR / demo_name if demo_name else _DEVLOGS_DIR

    if demo_name and not search_root.exists():
        pytest.skip(
            f"devlogs/{demo_name}/ not found — run the {demo_name} demo first"
        )

    replicas: dict[str, list[dict]] = {}
    for jsonl_file in sorted(search_root.glob("**/*-case-ledger.jsonl")):
        actor_name = jsonl_file.parent.name
        replicas.setdefault(actor_name, []).extend(load_jsonl(jsonl_file))

    if not replicas:
        skip_hint = f"devlogs/{demo_name}/" if demo_name else "devlogs/"
        pytest.skip(
            f"No *-case-ledger.jsonl files found under {skip_hint} — "
            "run the demo first (see test/ci/README-case-log-ratchet.md)"
        )

    for actor in replicas:
        replicas[actor] = sorted(replicas[actor], key=log_index)

    return replicas


def auth_entries(replicas: dict[str, list[dict]]) -> list[dict]:
    """Return the authoritative log, preferring the ``case-actor`` replica."""
    return replicas.get("case-actor", next(iter(replicas.values()), []))


# ---------------------------------------------------------------------------
# Contiguous-fragment helper
# ---------------------------------------------------------------------------


def contiguous_fragments(entries: list[dict]) -> list[list[dict]]:
    """Split a logIndex-sorted entry list into maximal contiguous runs."""
    if not entries:
        return []
    fragments: list[list[dict]] = []
    current: list[dict] = [entries[0]]
    for e in entries[1:]:
        if log_index(e) == log_index(current[-1]) + 1:
            current.append(e)
        else:
            fragments.append(current)
            current = [e]
    fragments.append(current)
    return fragments


# ---------------------------------------------------------------------------
# Universal invariant check functions
# ---------------------------------------------------------------------------
# Each function returns a list of violation strings.  Empty list = pass.
# Callers assert ``not violations``.


def check_hash_chain(
    actor_name: str,
    entries: list[dict],
) -> list[str]:
    """Within each contiguous logIndex fragment, verify hashes chain correctly.

    Spec: CLP-07 (Invariant 1).
    """
    violations: list[str] = []
    for fragment in contiguous_fragments(entries):
        first = fragment[0]
        first_idx = log_index(first)

        if first_idx == 0:
            actual_prev = prev_log_hash(first)
            if not _SHA256_HEX_PATTERN.match(actual_prev):
                violations.append(
                    f"Actor {actor_name!r}: fragment at logIndex=0 "
                    f"prevLogHash={actual_prev!r} is not a valid 64-char hex "
                    f"SHA-256 (per-case genesis hash, CLP-08)"
                )

        for i, e in enumerate(fragment[1:], start=1):
            prev = fragment[i - 1]
            expected = entry_hash(prev)
            if not expected:
                violations.append(
                    f"Actor {actor_name!r}: logIndex={log_index(prev)} "
                    f"has no entryHash — cannot verify hash chain"
                )
                continue
            actual = prev_log_hash(e)
            if not actual:
                violations.append(
                    f"Actor {actor_name!r}: logIndex={log_index(e)} "
                    f"has no prevLogHash — cannot verify hash chain"
                )
                continue
            if actual != expected:
                violations.append(
                    f"Actor {actor_name!r}: logIndex={log_index(e)} "
                    f"prevLogHash={actual[:16]!r} != "
                    f"logIndex={log_index(prev)} entryHash={expected[:16]!r}"
                )
    return violations


def check_cross_actor_hash_agreement(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """All actors agree on entryHash for every shared logIndex (Invariant 2)."""
    by_index: dict[int, dict[str, str]] = {}
    for actor, entries in replicas.items():
        for e in entries:
            idx = log_index(e)
            by_index.setdefault(idx, {})[actor] = entry_hash(e)

    return [
        f"logIndex={idx}: {actor_hashes}"
        for idx, actor_hashes in sorted(by_index.items())
        if len(actor_hashes) > 1 and len(set(actor_hashes.values())) > 1
    ]


def check_cross_actor_payload_actor_agreement(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """All actors agree on payloadSnapshot.actor for every shared logIndex (Invariant 3)."""
    by_index: dict[int, dict[str, str | None]] = {}
    for actor, entries in replicas.items():
        for e in entries:
            idx = log_index(e)
            snap = payload(e)
            actor_val = snap.get("actor")
            by_index.setdefault(idx, {})[actor] = (
                str(actor_val) if actor_val is not None else None
            )

    return [
        f"logIndex={idx}: {actor_vals}"
        for idx, actor_vals in sorted(by_index.items())
        if len(actor_vals) > 1 and len(set(actor_vals.values())) > 1
    ]


def check_non_empty_payload_snapshots(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """Every recorded canonical entry has a non-empty payloadSnapshot (Invariant 4)."""
    return [
        f"Actor {actor!r} logIndex={log_index(e)} eventType={event_type(e)!r}"
        for actor, entries in replicas.items()
        for e in entries
        if e.get("disposition", "recorded") == "recorded" and not payload(e)
    ]


def check_event_type_present(
    replicas: dict[str, list[dict]],
    expected_event_type: str,
) -> list[str]:
    """Assert that an expected eventType appears at least once in the authoritative log.

    Returns a non-empty list when the event type is absent.
    """
    auth = auth_entries(replicas)
    found = {event_type(e) for e in auth}
    if expected_event_type not in found:
        return [
            f"Expected eventType {expected_event_type!r} not found in case-actor log.\n"
            f"Found: {sorted(found)}"
        ]
    return []


def check_event_type_count(
    replicas: dict[str, list[dict]],
    expected_event_type: str,
    min_count: int,
) -> list[str]:
    """Assert that an expected eventType appears at least ``min_count`` times.

    Useful for scenarios where a given event must repeat (e.g., two invitations).
    """
    auth = auth_entries(replicas)
    actual_count = sum(1 for e in auth if event_type(e) == expected_event_type)
    if actual_count < min_count:
        return [
            f"Expected eventType {expected_event_type!r} at least {min_count} "
            f"time(s) in case-actor log; found {actual_count}."
        ]
    return []


def check_no_rm_state_oscillation(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """No participant changes RM state after first reaching CLOSED (Invariant 6)."""
    auth = auth_entries(replicas)
    status_entries = [
        e
        for e in auth
        if event_type(e) == "add_participant_status_to_participant"
    ]

    rm_history: dict[str, list[str]] = {}
    for e in status_entries:
        p_id, rm_state = participant_status_identity_and_rm(payload(e))
        if p_id and rm_state:
            rm_history.setdefault(p_id, []).append(rm_state)

    return [
        f"Participant {p_id!r} changed RM state after CLOSED: {states}"
        for p_id, states in rm_history.items()
        for i, state in enumerate(states)
        if state.upper() in ("CLOSED", "RM.CLOSED") and i < len(states) - 1
    ]


def check_rm_closed_termination(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """The log terminates with every participant in RM=CLOSED (Invariant 7)."""
    auth = auth_entries(replicas)
    latest_rm: dict[str, str] = {}
    for e in auth:
        if event_type(e) != "add_participant_status_to_participant":
            continue
        p_id, rm_state = participant_status_identity_and_rm(payload(e))
        if p_id and rm_state:
            latest_rm[p_id] = rm_state

    if not latest_rm:
        return [
            "No add_participant_status_to_participant entries found in case-actor log"
        ]

    return [
        f"Participant {p!r} final RM state = {s!r}, expected CLOSED"
        for p, s in latest_rm.items()
        if s.upper() not in ("CLOSED", "RM.CLOSED")
    ]


def check_late_joiner_has_full_history(
    replicas: dict[str, list[dict]],
    early_actor: str,
    late_actor: str,
) -> list[str]:
    """Late-joining actor has all logIndex values present in the early actor's replica.

    Spec: CLP-07 (Invariant 8).
    """
    early_entries = replicas.get(early_actor, [])
    late_entries = replicas.get(late_actor, [])

    if not early_entries or not late_entries:
        return (
            []
        )  # skip check — caller should pytest.skip when replicas absent

    early_indices = {log_index(e) for e in early_entries}
    late_indices = {log_index(e) for e in late_entries}
    missing = sorted(early_indices - late_indices)

    if missing:
        return [
            f"Actor {late_actor!r} replica missing {len(missing)} pre-join log entries "
            f"present in {early_actor!r}: logIndex in {missing[:10]}"
            + (" (truncated)" if len(missing) > 10 else "")
        ]
    return []


def _missing_fields_in_status_snap(
    snap: dict,
    valid_em_states: set,
    valid_roles: set,
) -> list[str]:
    """Return field-level violation strings for one ParticipantStatus snapshot."""
    missing: list[str] = []
    if "emConsentState" not in snap and "em_consent_state" not in snap:
        missing.append("emConsentState")
    if "cvdRole" not in snap and "cvd_role" not in snap:
        missing.append("cvdRole")
    em_consent = snap.get("emConsentState", snap.get("em_consent_state"))
    if em_consent not in valid_em_states:
        missing.append("valid emConsentState value")
    cvd_role = snap.get("cvdRole", snap.get("cvd_role"))
    if not isinstance(cvd_role, list) or not cvd_role:
        missing.append("non-empty cvdRole list")
    elif any(role not in valid_roles for role in cvd_role):
        missing.append("valid cvdRole value")
    return missing


def check_participant_status_schema_completeness(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """Every ParticipantStatus snapshot includes emConsentState and cvdRole list (Invariant 9)."""
    auth = auth_entries(replicas)
    status_entries = [
        e
        for e in auth
        if event_type(e) == "add_participant_status_to_participant"
    ]
    if not status_entries:
        return [
            "No add_participant_status_to_participant entries found; cannot check schema completeness"
        ]

    valid_em_states = {
        *(state.name for state in PEC),
        *(state.value for state in PEC),
    }
    valid_roles = {
        *(role.name for role in CVDRole),
        *(role.value for role in CVDRole),
    }

    incomplete: list[str] = []
    for e in status_entries:
        snap = payload(e)
        if isinstance(snap.get("object"), dict):
            snap = snap["object"]
        elif isinstance(snap.get("object_"), dict):
            snap = snap["object_"]
        missing_fields = _missing_fields_in_status_snap(
            snap, valid_em_states, valid_roles
        )
        if missing_fields:
            incomplete.append(
                f"logIndex={log_index(e)}: missing {missing_fields}"
            )

    return incomplete


def check_nested_objects_inlined(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """payloadSnapshot.object is an inline dict, not a bare ID string (Invariant 10)."""
    auth = auth_entries(replicas)
    return [
        (
            f"logIndex={log_index(e)} eventType={event_type(e)!r}: "
            f"object={str(payload(e).get('object', ''))[:60]!r}"
        )
        for e in auth
        if isinstance(
            payload(e).get("object") or payload(e).get("object_"), str
        )
    ]


def check_payload_context_uses_case_uri(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """payloadSnapshot.context matches the entry's case_id for recorded entries (Invariant 11)."""
    auth = auth_entries(replicas)
    mismatches: list[str] = []
    for e in auth:
        if e.get("disposition", "recorded") != "recorded":
            continue
        cid = case_id(e)
        snap = payload(e)
        context = snap.get("context")
        if context is None:
            continue
        if isinstance(context, str) and context != cid:
            mismatches.append(
                f"logIndex={log_index(e)} eventType={event_type(e)!r}: "
                f"context={context[:60]!r} != case_id={cid[:60]!r}"
            )
    return mismatches


def check_genesis_entry_present(
    actor_name: str,
    entries: list[dict],
) -> list[str]:
    """logIndex=0 is present in the actor's log (Invariant 12)."""
    if not entries:
        return [f"Actor {actor_name!r}: no entries found"]
    indices = {log_index(e) for e in entries}
    if 0 not in indices:
        return [
            f"Actor {actor_name!r}: logIndex=0 is absent from the log. "
            f"Lowest present index: {min(indices)}"
        ]
    return []


def check_log_starts_at_genesis(
    actor_name: str,
    entries: list[dict],
) -> list[str]:
    """The first entry in the actor's sorted log has logIndex=0 (Invariant 13)."""
    if not entries:
        return [f"Actor {actor_name!r}: no entries found"]
    first_index = log_index(entries[0])
    if first_index != 0:
        return [
            f"Actor {actor_name!r}: first entry has logIndex={first_index}, "
            f"expected 0 (log is incomplete or not starting at genesis)"
        ]
    return []


def check_no_gaps_in_log_indices(
    actor_name: str,
    entries: list[dict],
) -> list[str]:
    """No gaps within the actor's present logIndex range (Invariant 14)."""
    if not entries:
        return [f"Actor {actor_name!r}: no entries found"]
    indices = sorted(log_index(e) for e in entries)
    min_idx, max_idx = indices[0], indices[-1]
    expected = list(range(min_idx, max_idx + 1))
    gaps = sorted(set(expected) - set(indices))
    if gaps:
        return [
            f"Actor {actor_name!r}: {len(gaps)} gap(s) in logIndex sequence "
            f"[{min_idx}..{max_idx}]: missing {gaps[:10]}"
            + (" (truncated)" if len(gaps) > 10 else "")
        ]
    return []


def cs_observations_from_snap(snap: dict) -> tuple[bool, bool, bool]:
    """Extract CS-transition observations from a ParticipantStatus payload.

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


def check_cs_state_transitions_observed(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """All three key CS transitions observed in the authoritative log (Invariant 15).

    Checks vfd_state == "VFd" (fix ready), "VFD" (fix deployed), and
    pxa_state starting with "P" (public aware).
    """
    auth = auth_entries(replicas)
    status_entries = [
        e
        for e in auth
        if event_type(e) == "add_participant_status_to_participant"
    ]
    if not status_entries:
        return [
            "No add_participant_status_to_participant entries found; "
            "cannot check CS-transition invariant"
        ]

    saw_fix_ready = saw_fix_deployed = saw_published = False
    for e in status_entries:
        fix_ready, fix_deployed, published = cs_observations_from_snap(
            payload(e)
        )
        saw_fix_ready |= fix_ready
        saw_fix_deployed |= fix_deployed
        saw_published |= published

    missing: list[str] = []
    if not saw_fix_ready:
        missing.append("vfd_state == 'VFd' (fix_ready) never observed")
    if not saw_fix_deployed:
        missing.append("vfd_state == 'VFD' (fix_deployed) never observed")
    if not saw_published:
        missing.append(
            "pxa_state starting with 'P' (published/public-aware) never observed"
        )
    return missing
