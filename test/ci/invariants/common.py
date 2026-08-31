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
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from vultron.core.states.participant_embargo_consent import PEC
from vultron.demo.helpers.ledger_dump import (
    DUMP_MANIFEST_FILENAME,
    default_devlogs_root,
)
from vultron.enums.roles import CVDRole

# ---------------------------------------------------------------------------
# Repository layout
# ---------------------------------------------------------------------------

_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: Where the harness looks for the ledgers the demo dumped. Resolved by the same
#: helper the dump writes through, so pointing ``DEVLOGS_DIR`` somewhere else
#: cannot silently turn this harness into a no-op skip (DEMOMA-17-001).
_DEVLOGS_DIR: Path = default_devlogs_root()


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


def _read_dump_manifests(search_root: Path) -> list[dict]:
    """Return every readable ``dump-manifest.json`` under *search_root*.

    A manifest is the scenario's own record that its case-ledger dump ran —
    see ``vultron.demo.helpers.ledger_dump``.  Its presence is what lets this
    module tell "the demo never ran" apart from "the demo ran and produced no
    ledger entries" (DEMOCI-10-001).

    Raises:
        Failed: When a manifest exists but cannot be parsed, since a corrupt
            manifest is itself evidence that something went wrong.
    """
    manifests: list[dict] = []
    candidates = [
        search_root / DUMP_MANIFEST_FILENAME,
        *sorted(search_root.glob(f"**/{DUMP_MANIFEST_FILENAME}")),
    ]
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            pytest.fail(
                f"{path} is unreadable ({type(exc).__name__}: {exc}) — the "
                "demo dumped a manifest but it cannot be parsed, so the "
                "invariant result cannot be trusted"
            )
        if not isinstance(data, dict):
            pytest.fail(
                f"{path} parsed as {type(data).__name__}, not an object — the "
                "demo dumped a manifest but it cannot be interpreted, so the "
                "invariant result cannot be trusted"
            )
        manifests.append(data)
    return manifests


def _fail_no_ledgers_despite_dump(
    search_root: Path,
    manifests: list[dict],
) -> None:
    """Fail with the manifests' account of why no ledger files were captured."""
    lines = [
        f"No case-ledger files under {search_root}, but "
        f"{len(manifests)} dump manifest(s) show the demo ran and dumped. "
        "This is a real invariant failure, not missing test data."
    ]
    for manifest in manifests:
        lines.append(
            f"- demo {manifest.get('demoName', '?')!r}: "
            f"case={manifest.get('caseId')!r} "
            f"captured={manifest.get('ledgerFileCount', 0)}"
            f"/{manifest.get('targetCount', 0)} actors"
        )
        reason = manifest.get("reason")
        if reason:
            lines.append(f"    reason: {reason}")
        actors = manifest.get("actors")
        if isinstance(actors, list):
            for actor in actors:
                if not isinstance(actor, dict) or actor.get("captured"):
                    continue
                lines.append(
                    f"    missing {actor.get('actorName', '?')!r} "
                    f"(route {actor.get('routeKey', '?')!r}): "
                    f"{actor.get('reason') or 'no reason recorded'}"
                )
    pytest.fail("\n".join(lines))


def load_devlogs(
    demo_name: str | None = None,
) -> dict[str, list[dict]]:
    """Load JSONL case ledger files, grouped by actor name.

    Reads every ``*-case-ledger.jsonl`` file under ``devlogs/`` (relative to
    the repo root), optionally scoped to a ``demo_name`` sub-directory.
    Groups entries by the containing actor directory name and sorts each
    actor's entries by ``log_index`` ascending.

    Calls ``pytest.skip`` when there is no evidence the demo ever ran:
    ``devlogs/`` absent, the scenario sub-directory absent, or no ledger files
    *and* no ``dump-manifest.json``.

    Calls ``pytest.fail`` when a ``dump-manifest.json`` is present but no
    ledger files are: the scenario ran, dumped, and still produced no ledger
    entries, which is a real invariant failure that must not be skipped over
    (DEMOCI-10-001, ISSUE-2239).

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

    # Read the manifests unconditionally: DEMOCI-10-003 fails on a manifest that
    # is present but unparseable whatever else the dump produced, so this check
    # cannot live inside the `not replicas` branch below.
    manifests = _read_dump_manifests(search_root)

    if not replicas:
        if manifests:
            _fail_no_ledgers_despite_dump(search_root, manifests)
        skip_hint = f"devlogs/{demo_name}/" if demo_name else "devlogs/"
        msg = (
            f"No *-case-ledger.jsonl files found under {skip_hint} and no "
            f"{DUMP_MANIFEST_FILENAME} — run the demo first "
            "(see test/ci/README-case-log-ratchet.md)"
        )
        if demo_name:
            # The scenario directory exists but contains neither ledger files
            # nor a dump manifest — the dump never ran at all.  This is a
            # real failure (crashed before any output was written), not a
            # "demo has not been run yet" skip (ISSUE-2411 Gap 2).
            pytest.fail(msg)
        pytest.skip(msg)

    for actor in replicas:
        replicas[actor] = sorted(replicas[actor], key=log_index)

    # Filter to the most recent run's case when the manifest provides a caseId.
    # Without this, accumulated JSONL files from prior local runs chain entries
    # from different cases together and break the hash-chain invariant (issue #2273).
    manifest_case_ids = {m.get("caseId") for m in manifests if m.get("caseId")}
    if len(manifest_case_ids) == 1:
        (filter_id,) = manifest_case_ids
        for actor in replicas:
            replicas[actor] = [
                e for e in replicas[actor] if case_id(e) == filter_id
            ]

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
    """The log terminates with every participant in RM=CLOSED (Invariant 7).

    Recognises two event types as RM-state carriers:

    - ``add_participant_status_to_participant``: explicit RM state for the
      participant in the ``payloadSnapshot`` (pre-ADR-0050 CS transitions).
    - ``close_case``: signals ``RM=CLOSED`` for the departing actor whose ID
      is in ``payloadSnapshot.actor`` (ADR-0050 canonical closure path via
      ``Leave(VulnerabilityCase)``).
    """
    auth = auth_entries(replicas)
    latest_rm: dict[str, str] = {}
    for e in auth:
        et = event_type(e)
        snap = payload(e)
        if et == "add_participant_status_to_participant":
            p_id, rm_state = participant_status_identity_and_rm(snap)
            if p_id and rm_state:
                latest_rm[p_id] = rm_state
        elif et == "close_case":
            # close_case entries record the departing actor in payloadSnapshot.actor
            # (ADR-0050: Leave(VulnerabilityCase) is the canonical RM closure path).
            actor_val = snap.get("actor")
            if isinstance(actor_val, dict):
                actor_val = actor_val.get("id")
            if isinstance(actor_val, str) and actor_val:
                latest_rm[actor_val] = "CLOSED"

    if not latest_rm:
        return [
            "No add_participant_status_to_participant or close_case entries"
            " found in case-actor log"
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

    vf_state = snap.get("vfState") or snap.get("vf_state")
    d_state = snap.get("dState") or snap.get("d_state")

    case_status = snap.get("caseStatus") or snap.get("case_status")
    pxa_state: str | None = None
    if isinstance(case_status, dict):
        pxa_state = case_status.get("pxaState") or case_status.get("pxa_state")

    return (
        vf_state == "VF",
        d_state == "D",
        isinstance(pxa_state, str) and pxa_state[:1] == "P",
    )


def check_cs_state_transitions_observed(
    replicas: dict[str, list[dict]],
    *,
    check_fix_ready: bool = True,
) -> list[str]:
    """Key CS transitions observed in the authoritative log (Invariant 15).

    Checks pxa_state starting with "P" (public aware) for all scenarios.
    When ``check_fix_ready=True`` (default), also checks vf_state == "VF"
    (fix ready, CS_vf.VF).  Set ``check_fix_ready=False`` for scenarios where
    no Vendor ever becomes a case participant and therefore no actor advances
    the VF state machine (e.g. fcv-reject: Vendor rejects the invitation).

    Fix-deployed (d_state == "D") is NOT checked here because demo scenarios
    use vendor-only actors (CVDRole.VENDOR, no CVDRole.DEPLOYER); per
    CSB-15-002 those actors stop at CS_vf.VF and never reach CS_d.D.
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

    saw_fix_ready = saw_published = False
    for e in status_entries:
        fix_ready, _, published = cs_observations_from_snap(payload(e))
        saw_fix_ready |= fix_ready
        saw_published |= published

    missing: list[str] = []
    if check_fix_ready and not saw_fix_ready:
        missing.append("vf_state == 'VF' (fix_ready) never observed")
    if not saw_published:
        missing.append(
            "pxa_state starting with 'P' (published/public-aware) never observed"
        )
    return missing


def check_no_rejected_invite_entries(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """No invite_actor_to_case entries with disposition=rejected exist (CLP-13-001).

    Idempotency guards MUST NOT write any CaseLedgerEntry.  A spurious
    ``disposition="rejected"`` entry on an ``invite_actor_to_case`` event type
    indicates an idempotency guard incorrectly wrote to the ledger.

    Returns one violation string per offending entry.
    """
    violations: list[str] = []
    for actor, entries in replicas.items():
        for e in entries:
            if (
                event_type(e) == "invite_actor_to_case"
                and e.get("disposition") == "rejected"
            ):
                violations.append(
                    f"Actor {actor!r} logIndex={log_index(e)}: spurious"
                    f" rejected invite_actor_to_case entry (CLP-13-001 violation)"
                )
    return violations


def check_per_actor_replica_divergence(
    replicas: dict[str, list[dict]],
    *,
    check_fix_ready: bool = True,
) -> list[str]:
    """Each non-case-actor replica satisfies the same state invariants as the authoritative log.

    Runs RM-state and CS-transition invariants against every replica that is
    not ``case-actor``.  The ``{actor: entries}`` single-actor dict causes
    ``auth_entries()`` to fall back to the actor's own entries, reusing the
    existing canonical check logic without modification (ISSUE-2411 Gap 1).

    Actors whose replica contains no ``add_participant_status_to_participant``
    entries are skipped for the three status-dependent checks; they have no
    state-machine observations to verify.

    Args:
        replicas: All loaded replicas for the scenario.
        check_fix_ready: Passed through to ``check_cs_state_transitions_observed``.
            Set ``False`` for scenarios where no Vendor ever becomes a participant
            (e.g. fcv-reject), matching the canonical invariant's behaviour.
    """
    violations: list[str] = []
    for actor, entries in replicas.items():
        if actor == "case-actor":
            continue
        actor_dict = {actor: entries}
        prefix = f"Actor {actor!r}"
        for msg in check_no_rm_state_oscillation(actor_dict):
            violations.append(f"{prefix}: {msg}")
        has_status_entries = any(
            event_type(e) == "add_participant_status_to_participant"
            for e in entries
        )
        if has_status_entries:
            for msg in check_rm_closed_termination(actor_dict):
                violations.append(f"{prefix}: {msg}")
            for msg in check_participant_status_schema_completeness(
                actor_dict
            ):
                violations.append(f"{prefix}: {msg}")
            for msg in check_cs_state_transitions_observed(
                actor_dict, check_fix_ready=check_fix_ready
            ):
                violations.append(f"{prefix}: {msg}")
    return violations


# ---------------------------------------------------------------------------
# Narrative causal-edge helpers (DEMOMA-22-004, DEMOMA-22-005)
# ---------------------------------------------------------------------------

#: Regex that matches the YAML front-matter block at the top of a Markdown file.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

#: Repo root, used to resolve relative narrative paths from the test runner.
_REPO_ROOT: Path = Path(__file__).parent.parent.parent.parent


def load_narrative_edges(narrative_path: str | Path) -> list[dict]:
    """Parse causal edges from the YAML front-matter of a scenario narrative page.

    Returns a list of edge dicts, each with at least ``antecedent`` and
    ``consequent`` keys and an optional ``observable`` key (defaults to
    ``True``).  Edges with ``observable: false`` are returned but the caller
    should skip them in ordering checks.

    Calls ``pytest.skip`` when the narrative file is absent (the documentation
    hasn't been written yet) or when the front-matter contains no
    ``causal_edges`` key (e.g. an index page).
    """
    path = (
        _REPO_ROOT / narrative_path
        if not Path(narrative_path).is_absolute()
        else Path(narrative_path)
    )
    if not path.is_file():
        pytest.skip(
            f"Narrative page {path} not found — write the scenario narrative first"
        )
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        pytest.skip(
            f"{path} has no YAML front-matter — add causal_edges: block"
        )
    raw = yaml.safe_load(m.group(1))
    data: dict = raw if isinstance(raw, dict) else {}
    raw_edges = data.get("causal_edges", [])
    edges: list[dict] = [e for e in raw_edges if isinstance(e, dict)]
    if not edges:
        pytest.skip(f"{path} front-matter has no causal_edges list")
    return edges


def check_causal_edges(
    replicas: dict[str, list[dict]],
    edges: list[dict],
) -> list[str]:
    """Assert that each declared observable causal edge appears in log-index order.

    For each edge with ``observable`` not ``False``, finds all log entries
    whose ``eventType`` matches the ``antecedent`` and ``consequent`` fields
    and verifies that at least one antecedent entry appears before at least
    one consequent entry (i.e. ``min(antecedent_indices) < max(consequent_indices)``).

    Returns a list of violation strings (empty = all edges satisfied).
    Diagnostic output names the unsatisfied edge and the indices that were
    observed, so failures are self-explanatory (DEMOMA-22-006-AC-6).
    """
    auth = auth_entries(replicas)
    if not auth:
        return [
            "No authoritative log entries found; cannot check causal edges"
        ]

    violations: list[str] = []

    for edge in edges:
        if not edge.get("observable", True):
            continue
        antecedent = edge.get("antecedent", "")
        consequent = edge.get("consequent", "")
        consequent_actor = edge.get("consequent_actor", "")

        ant_indices = [
            log_index(e) for e in auth if event_type(e) == antecedent
        ]
        con_indices = [
            log_index(e) for e in auth if event_type(e) == consequent
        ]

        if not ant_indices:
            violations.append(
                f"Edge [{antecedent!r} → {consequent!r}]: "
                f"no {antecedent!r} entry found in authoritative log"
            )
            continue
        if not con_indices:
            violations.append(
                f"Edge [{antecedent!r} → {consequent!r}]: "
                f"no {consequent!r} entry found in authoritative log"
                + (
                    f" (expected actor: {consequent_actor!r})"
                    if consequent_actor
                    else ""
                )
            )
            continue
        if min(ant_indices) >= max(con_indices):
            violations.append(
                f"Edge [{antecedent!r} → {consequent!r}]: "
                f"no valid ordering found — "
                f"antecedent indices {sorted(ant_indices)}, "
                f"consequent indices {sorted(con_indices)}"
                + (
                    f" (consequent_actor: {consequent_actor!r})"
                    if consequent_actor
                    else ""
                )
            )

    return violations


def _parse_ts(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _clp14_005_unique_indices(sorted_entries: list[dict]) -> list[str]:
    seen: set[int] = set()
    violations: list[str] = []
    for entry in sorted_entries:
        idx = log_index(entry)
        if idx in seen:
            violations.append(f"CLP-14-005: duplicate logIndex={idx}")
        else:
            seen.add(idx)
    return violations


def _clp14_002_build_ts_entries(
    sorted_entries: list[dict],
) -> tuple[list[str], list[tuple[int, datetime]]]:
    violations: list[str] = []
    ts_entries: list[tuple[int, datetime]] = []
    for entry in sorted_entries:
        idx = log_index(entry)
        raw = entry.get("published")
        if raw is None:
            violations.append(
                f"CLP-14-002: logIndex={idx} "
                f"eventType={event_type(entry)!r} has null published"
            )
            continue
        dt = _parse_ts(raw)
        if dt is None:
            violations.append(
                f"CLP-14-002: logIndex={idx} published "
                f"{raw!r} is not a valid ISO 8601 timestamp"
            )
        else:
            ts_entries.append((idx, dt))
    return violations, ts_entries


def _clp14_003_monotone(ts_entries: list[tuple[int, datetime]]) -> list[str]:
    violations: list[str] = []
    for i in range(1, len(ts_entries)):
        prev_idx, prev_ts = ts_entries[i - 1]
        curr_idx, curr_ts = ts_entries[i]
        if curr_ts < prev_ts:
            violations.append(
                f"CLP-14-003: logIndex={curr_idx} published {curr_ts} "
                f"regresses before logIndex={prev_idx} published {prev_ts}"
            )
    return violations


def _clp14_006_no_predate_case(
    sorted_entries: list[dict],
    ts_entries: list[tuple[int, datetime]],
) -> list[str]:
    case_ts: datetime | None = None
    for entry in sorted_entries:
        if event_type(entry) == "create_case":
            raw = entry.get("published")
            if raw is not None:
                case_ts = _parse_ts(raw)
                if case_ts is None:
                    idx = log_index(entry)
                    return [
                        f"CLP-14-006: unevaluated — create_case logIndex={idx} "
                        f"has malformed published {raw!r} (CLP-14-002)"
                    ]
            break
    if case_ts is None:
        return []
    return [
        f"CLP-14-006: logIndex={idx} published {ts} "
        f"predates case creation {case_ts}"
        for idx, ts in ts_entries
        if ts < case_ts
    ]


def check_clp14_timestamp_invariants(
    replicas: dict[str, list[dict]],
) -> list[str]:
    """Check CLP-14-001–CLP-14-006 timestamp invariants against ledger entries.

    CLP-14-002: every entry must have a non-null ``published`` timestamp.
    CLP-14-003: ``published`` values must be monotonically non-decreasing by
                ``logIndex``.
    CLP-14-005: ``logIndex`` values must be unique within the ledger.
    CLP-14-006: no entry may predate the case-creation entry
                (``eventType == "create_case"``).

    Entries without a ``published`` field are flagged for CLP-14-002 and
    skipped for ordering checks so the violation list stays focused.

    Authority note: this harness checks ``CaseLedgerEntry.published`` — the
    trusted *commit* timestamp written by the ledger layer — not the
    ``payloadSnapshot.published`` field checked by ``_validate_entry_timestamps``
    at commit time.  The two fields can diverge: a payload whose claimed
    ``published`` predates the case may pass this harness if its commit
    timestamp does not, and vice versa.
    """
    auth = auth_entries(replicas)
    if not auth:
        return []
    sorted_entries = sorted(auth, key=log_index)
    v002, ts_entries = _clp14_002_build_ts_entries(sorted_entries)
    return (
        _clp14_005_unique_indices(sorted_entries)
        + v002
        + _clp14_003_monotone(ts_entries)
        + _clp14_006_no_predate_case(sorted_entries, ts_entries)
    )
