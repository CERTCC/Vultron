"""The distilled timeline model, replica discovery and timeline construction (DRPT-01, DRPT-02)."""

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

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from vultron.core.models.events.base import MessageSemantics
from vultron.demo.report.naming import (
    _ACTOR_LIKE_TYPES,
    _WRAPPER_TYPES,
    _actor_uri,
    _candidate_dicts,
    _coerce_int,
    _dimension_state,
    _first,
    collect_actor_names,
    friendly_actor_name,
    friendly_object_label,
)
from vultron.semantic_registry import lookup_entry

#: Glob for the per-actor case-ledger replica files.
_LEDGER_GLOB = "**/*-case-ledger.jsonl"

#: Number of hex characters shown for a truncated ``entry_hash``.
_SHORT_HASH_LEN = 12


class ReportError(Exception):
    """Raised for user-facing failures that map to a non-zero exit code.

    Covers a missing input directory, no matching JSONL files, and JSONL
    parse errors (DRPT-01-004).
    """


# ---------------------------------------------------------------------------
# Distilled timeline model (DRPT-02)
# ---------------------------------------------------------------------------


class CaseTimelineEvent(BaseModel):
    """One canonical timeline event distilled into friendly-readable form.

    This is the reusable, testable "friendly data" layer between JSONL parsing
    and rendering: both renderers consume :class:`CaseTimelineEvent` objects
    rather than raw JSONL dicts (DRPT-02-014).

    Fields:
        case_id: URI of the case this entry belongs to; the primary grouping
            key so distinct cases discovered under one input directory are
            never interleaved (DRPT-02-006).
        log_index: Monotonic per-case index; the canonical ordering key.
        entry_hash: Full SHA-256 hex hash of the entry (chain traceability).
        semantic_type: The entry's semantic type (``semanticType``).
        actor_uri: Full URI of the acting actor (secondary detail).
        target_ref: Full id of the target object (secondary detail).
        target_type: Wire type of the target object.
        activity_target_ref: Full id of the ActivityStreams destination/target
            object — the case or participant that is the *destination* of an
            Offer/Invite (e.g. the case in
            ``Accept(Invite(Actor)[target=VulnerabilityCase])``).
        activity_target_type: Wire type of the destination/target object.
        received_at: Server-generated receipt timestamp (``receivedAt``).
        rm_state / em_state / vf_state / d_state / pxa_state: Resulting
            state-machine dimensions extracted from the payload snapshot, where
            present.
        present_in: Sorted actor-directory names whose replicas hold this
            entry (the per-actor replica-presence indicator, DRPT-02-005).
    """

    case_id: str = ""
    log_index: int = -1
    entry_hash: str = ""
    semantic_type: str = ""
    actor_uri: str | None = None
    actor_display_name: str | None = None
    target_ref: str | None = None
    target_type: str | None = None
    target_display_name: str | None = None
    activity_target_ref: str | None = None
    activity_target_type: str | None = None
    activity_target_display_name: str | None = None
    received_at: str | None = None
    rm_state: str | None = None
    em_state: str | None = None
    vf_state: str | None = None
    d_state: str | None = None
    pxa_state: str | None = None
    present_in: list[str] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> CaseTimelineEvent:
        """Build a distilled event from one raw JSONL entry dict.

        Tolerates camelCase and snake_case spellings throughout (DRPT-02-003).
        """
        payload = _first(
            raw, "payload_snapshot", "payloadSnapshot", default={}
        )
        if not isinstance(payload, dict):
            payload = {}

        raw_object = payload.get("object") or payload.get("object_")
        # Unwrap AS wrapper activities (Accept, Reject, Offer, Invite) until we
        # reach the innermost non-wrapper object (handles Accept(Offer(X))
        # and Accept(Invite(X)[target=Y]) chains).  Track the innermost
        # wrapper's own ``target`` field so callers of nested wrappers (e.g.
        # accept_invite_actor_to_case) still surface the destination.
        _inner_target = None
        while (
            isinstance(raw_object, dict)
            and (raw_object.get("type") or raw_object.get("type_"))
            in _WRAPPER_TYPES
        ):
            _inner_target = raw_object.get("target") or _inner_target
            inner = raw_object.get("object") or raw_object.get("object_")
            if not isinstance(inner, (dict, str)):
                break
            raw_object = inner

        target_ref: str | None = None
        target_type: str | None = None
        if isinstance(raw_object, dict):
            target_ref = raw_object.get("id") or raw_object.get("id_")
            target_type = raw_object.get("type") or raw_object.get("type_")
            # CaseParticipant is a proxy; use attributedTo for name resolution.
            if target_type == "CaseParticipant":
                target_ref = (
                    raw_object.get("attributedTo")
                    or raw_object.get("attributed_to")
                    or target_ref
                )
        elif isinstance(raw_object, str):
            target_ref = raw_object

        # ActivityStreams ``target`` field — top-level payload wins; fall back
        # to the innermost wrapper's target captured during unwrapping.
        raw_dest = payload.get("target") or _inner_target
        activity_target_ref: str | None = None
        activity_target_type: str | None = None
        if isinstance(raw_dest, dict):
            activity_target_ref = raw_dest.get("id") or raw_dest.get("id_")
            activity_target_type = raw_dest.get("type") or raw_dest.get(
                "type_"
            )
            if activity_target_type == "CaseParticipant":
                activity_target_ref = (
                    raw_dest.get("attributedTo")
                    or raw_dest.get("attributed_to")
                    or activity_target_ref
                )
        elif isinstance(raw_dest, str):
            activity_target_ref = raw_dest

        candidates = _candidate_dicts(payload)
        received = _first(raw, "received_at", "receivedAt")

        return cls(
            case_id=str(_first(raw, "case_id", "caseId", default="")),
            log_index=_coerce_int(
                _first(raw, "log_index", "logIndex", default=-1), default=-1
            ),
            entry_hash=str(_first(raw, "entry_hash", "entryHash", default="")),
            semantic_type=str(
                _first(raw, "semantic_type", "semanticType", default="")
            ),
            actor_uri=_actor_uri(payload.get("actor")),
            target_ref=str(target_ref) if target_ref else None,
            target_type=str(target_type) if target_type else None,
            activity_target_ref=(
                str(activity_target_ref) if activity_target_ref else None
            ),
            activity_target_type=(
                str(activity_target_type) if activity_target_type else None
            ),
            received_at=str(received) if received else None,
            rm_state=_dimension_state(candidates, "rm", "rmState", "rm_state"),
            em_state=_dimension_state(candidates, "em", "emState"),
            vf_state=_dimension_state(candidates, "vf", "vfState", "vf_state"),
            d_state=_dimension_state(candidates, "d", "dState", "d_state"),
            pxa_state=_dimension_state(candidates, "pxa", "pxaState"),
        )

    @property
    def actor_label(self) -> str:
        """Friendly acting-actor name (DRPT-03-001).

        Returns the display name from the wire payload when available (resolves
        UUID-based actor URIs to names like "Vendor"), otherwise falls back to
        the URI path-segment heuristic.
        """
        if self.actor_display_name:
            return self.actor_display_name
        return friendly_actor_name(self.actor_uri)

    @property
    def target_label(self) -> str | None:
        """Friendly target label; ``object → destination`` when both are present.

        Actor-like object types (Organization, …) resolve to a display name
        when one was extracted from payload snapshots; otherwise falls back to
        the URI path-segment heuristic via :func:`friendly_actor_name`.
        """
        obj_label: str | None
        dest_label: str | None
        # Prefer the pre-resolved display name (covers UUID-based URIs and the
        # None-type fallback path in friendly_object_label).
        if self.target_display_name:
            obj_label = self.target_display_name
        elif self.target_type in _ACTOR_LIKE_TYPES:
            obj_label = friendly_actor_name(self.target_ref)
        else:
            obj_label = friendly_object_label(
                self.target_type, self.target_ref
            )

        if self.activity_target_display_name:
            dest_label = self.activity_target_display_name
        elif self.activity_target_type in _ACTOR_LIKE_TYPES:
            dest_label = friendly_actor_name(self.activity_target_ref)
        else:
            dest_label = friendly_object_label(
                self.activity_target_type, self.activity_target_ref
            )

        if obj_label and dest_label:
            return f"{obj_label} → {dest_label}"
        return obj_label or dest_label

    @property
    def short_hash(self) -> str:
        """Truncated ``entry_hash`` for compact chain traceability."""
        return self.entry_hash[:_SHORT_HASH_LEN]

    @property
    def cs_state(self) -> str | None:
        """Combined Case State: vf/d dimensions and public state (pxa)."""
        parts = [p for p in (self.vf_state, self.d_state, self.pxa_state) if p]
        return " · ".join(parts) if parts else None

    @property
    def summary(self) -> str:
        """Friendly active-voice summary (DRPT-03-002, DRPT-03-004).

        Looks up the ``SemanticEntry`` phrase template for this semantic type and
        fills named slots with values derived from the event record's resolved
        label properties.  Unknown slot names fall back to ``"—"``.
        """
        try:
            semantics = MessageSemantics(self.semantic_type)
        except ValueError:
            humanized = (
                self.semantic_type.replace("_", " ").strip()
                or "performed an action"
            )
            phrase = humanized
        else:
            entry = lookup_entry(semantics)
            slots: dict[str, str] = defaultdict(lambda: "—")
            slots["actor"] = self.actor_label
            if self.target_label:
                slots["object"] = self.target_label
                slots["target"] = self.target_label
            phrase = entry.phrase.format_map(slots)

        if not self.actor_uri and phrase.startswith("— "):
            phrase = phrase[2:]
        return phrase[:1].upper() + phrase[1:] if phrase else phrase


# ---------------------------------------------------------------------------
# Discovery and timeline construction (DRPT-01, DRPT-02)
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file into a list of dicts, skipping blank lines.

    Raises:
        ReportError: if any non-blank line is not valid JSON (DRPT-01-004).
    """
    entries: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReportError(f"Cannot read {path}: {exc}") from exc
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ReportError(
                f"Parse error in {path} line {lineno}: {exc}"
            ) from exc
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def discover_replicas(input_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Discover and parse case-ledger replica files under ``input_dir``.

    Recursively globs ``**/*-case-ledger.jsonl`` and groups the parsed entries
    by the name of the directory that contains each file (DRPT-01-007,
    DRPT-01-003).

    Raises:
        ReportError: if ``input_dir`` is missing, no matching files are found,
            or any file cannot be parsed (DRPT-01-004).
    """
    if not input_dir.exists():
        raise ReportError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise ReportError(f"Input path is not a directory: {input_dir}")

    replicas: dict[str, list[dict[str, Any]]] = {}
    for jsonl_file in sorted(input_dir.glob(_LEDGER_GLOB)):
        actor_name = jsonl_file.parent.name
        replicas.setdefault(actor_name, []).extend(_load_jsonl(jsonl_file))

    if not replicas:
        raise ReportError(f"No {_LEDGER_GLOB!r} files found under {input_dir}")
    return replicas


def build_timeline(
    replicas: dict[str, list[dict[str, Any]]],
) -> list[CaseTimelineEvent]:
    """Merge per-actor replicas into one canonical, ordered timeline.

    De-duplicates replicated entries by ``entry_hash`` (falling back to a
    per-source key for degenerate hashless entries), records which actors'
    replicas hold each entry, and orders the result by ``log_index`` ascending
    (DRPT-02-004, DRPT-02-005, DRPT-02-015).

    Actor URIs are resolved to display names extracted from inline actor objects
    in the payload snapshots (e.g. Organization objects carrying a ``name``
    field).  This resolves UUID-based actor URIs (which produce hex-fragment
    labels) to semantic names like "Vendor" or "Reporter".
    """
    actor_names = collect_actor_names(replicas)

    by_key: dict[str, CaseTimelineEvent] = {}
    presence: dict[str, set[str]] = {}

    for actor_name in sorted(replicas):
        for raw in replicas[actor_name]:
            event = CaseTimelineEvent.from_raw(raw)
            if event.entry_hash:
                key = event.entry_hash
            else:
                key = (
                    f"__nohash__:{actor_name}:{event.log_index}:"
                    f"{event.semantic_type}"
                )
            by_key.setdefault(key, event)
            presence.setdefault(key, set()).add(actor_name)

    events: list[CaseTimelineEvent] = []
    for key, event in by_key.items():
        event.present_in = sorted(presence[key])
        if event.actor_uri and event.actor_uri in actor_names:
            event.actor_display_name = actor_names[event.actor_uri]
        if event.target_ref and event.target_ref in actor_names:
            event.target_display_name = actor_names[event.target_ref]
        if (
            event.activity_target_ref
            and event.activity_target_ref in actor_names
        ):
            event.activity_target_display_name = actor_names[
                event.activity_target_ref
            ]
        events.append(event)

    # Group by case first so distinct cases discovered under one input
    # directory are never interleaved, then order within a case by log_index
    # (DRPT-02-006, DRPT-02-016).
    events.sort(key=lambda e: (e.case_id, e.log_index, e.entry_hash))
    return events


def group_events_by_case(
    events: list[CaseTimelineEvent],
) -> dict[str, list[CaseTimelineEvent]]:
    """Partition an ordered timeline into one list per ``case_id``.

    Preserves the incoming (case-contiguous, log-index-ordered) order both
    across and within cases, so the result is a ready-to-render mapping of
    ``case_id -> events`` (DRPT-02-006).
    """
    grouped: dict[str, list[CaseTimelineEvent]] = {}
    for event in events:
        grouped.setdefault(event.case_id, []).append(event)
    return grouped


def discovered_actors(replicas: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Return the sorted list of discovered actor-directory names."""
    return sorted(replicas)
