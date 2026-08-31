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
"""Read-only demo scenario report tool (DRPT-01 through DRPT-05).

Parses the JSONL case-ledger replica files produced by demo scenario runs
(``{DEVLOGS_DIR}/{demo}/{actor}/{case_slug}-case-ledger.jsonl``, written by
:func:`vultron.demo.helpers.ledger_dump.dump_case_ledgers`) and renders a
selective, human-readable report — "who did what to whom, with what activity,
in what order."

The ``dump-manifest.json`` file that ``dump_case_ledgers`` writes alongside the
replicas (ISSUE-2239) is not part of this tool's input; ``discover_replicas``
globs only ``**/*-case-ledger.jsonl``.

The tool is intentionally standalone (its own ``__main__`` entry point,
invokable as ``python -m vultron.demo.report`` or via the
``vultron-demo-report`` console script) so it stays decoupled from the
demo-run CLI (DC-01) while remaining colocated with the demo code that
produces the ledger files.

Pipeline:

1. :func:`discover_replicas` globs ``**/*-case-ledger.jsonl`` beneath the
   input directory and groups parsed entries by the containing actor
   directory name.
2. :func:`build_timeline` distils each raw entry into a
   :class:`CaseTimelineEvent`, merges all replicas into one canonical
   timeline (de-duplicated by ``entry_hash``, grouped by ``case_id`` then
   ordered by ``log_index`` so distinct cases are never interleaved), and
   computes a per-actor replica-presence indicator.
3. :func:`render_markdown` / :func:`render_html` render the timeline as one
   labelled section per case (DRPT-02-006); both consume
   :class:`CaseTimelineEvent` objects, never raw JSONL dicts.

Spec: ``specs/demo-report.yaml`` (DRPT-01 through DRPT-05).
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import sys
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from vultron.core.models.events.base import MessageSemantics
from vultron.demo.helpers.ledger_dump import default_devlogs_root
from vultron.semantic_registry import lookup_entry

logger = logging.getLogger(__name__)

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
# Tolerant field access (DRPT-02-003)
# ---------------------------------------------------------------------------


def _first(mapping: dict[str, Any], *names: str, default: Any = None) -> Any:
    """Return the first present, non-None value among ``names``.

    Tolerates the camelCase/snake_case spelling split present in the source
    JSONL (e.g. ``logIndex``/``log_index``), mirroring the accessors in
    ``test/ci/test_case_ledger_invariants.py``.
    """
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return default


def _coerce_int(value: Any, default: int) -> int:
    """Best-effort ``int`` coercion; returns ``default`` on failure.

    Keeps :meth:`CaseTimelineEvent.from_raw` tolerant of corrupt entries (e.g.
    a non-numeric ``logIndex``) so a single malformed field degrades one row
    rather than crashing the whole report (DRPT-01-004, DRPT-02-003).
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _actor_uri(actor: Any) -> str | None:
    """Normalize a payload ``actor`` field to a string URI, or ``None``.

    Tolerates both the bare-string spelling and an inline actor object
    (``{"id": "...", "type": "..."}``) so a nested actor does not raise a
    validation error out of the distiller (DRPT-02-003).
    """
    if isinstance(actor, str):
        return actor or None
    if isinstance(actor, dict):
        ref = actor.get("id") or actor.get("id_")
        return str(ref) if ref else None
    return None


def _candidate_dicts(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ``snapshot`` plus nested status-bearing dicts.

    A ``ParticipantStatus``/``CaseStatus`` may be encoded directly in the
    payload snapshot or nested under an ``Add`` activity's ``object`` (and a
    ``CaseStatus`` may itself nest under ``caseStatus``). ``VulnerabilityCase``
    payloads carry a ``caseStatuses`` array; each item in that list is also
    added so EM/CS state on early rows is not missed. This flattens all those
    layers so dimension-state extraction can search all of them.
    """
    seen: list[dict[str, Any]] = []

    def _add(node: Any) -> None:
        if not isinstance(node, dict) or any(node is s for s in seen):
            return
        seen.append(node)
        for key in ("object", "object_", "caseStatus", "case_status"):
            _add(node.get(key))
        for list_key in ("caseStatuses", "case_statuses"):
            items = node.get(list_key)
            if isinstance(items, list):
                for item in items:
                    _add(item)

    _add(snapshot)
    return seen


def _dimension_state(
    candidates: Iterable[dict[str, Any]],
    dimension_key: str,
    *flat_names: str,
) -> str | None:
    """Extract a single state-machine dimension value from candidate dicts.

    Handles both the ADR-0036 dimension-object shape (``{"rm": {"state":
    "..."}}``) and the legacy flat wire shape (``{"rmState": "..."}``).
    """
    for candidate in candidates:
        dim = candidate.get(dimension_key)
        if isinstance(dim, dict):
            state = dim.get("state")
            if state:
                return str(state)
        for flat in flat_names:
            value = candidate.get(flat)
            if value:
                return str(value)
    return None


# ---------------------------------------------------------------------------
# Actor name extraction
# ---------------------------------------------------------------------------

#: ActivityStreams actor types whose ``name`` field, when present, maps the
#: ``id`` to a human-readable display name (e.g. "Vendor", "Finder").
_NAME_BEARING_TYPES = frozenset(
    {
        "Organization",
        "Person",
        "Service",
        "Application",
        "Group",
        "Actor",
        "CaseActor",
    }
)


def _collect_actor_names_from_obj(
    obj: Any,
    out: dict[str, str],
) -> None:
    """Recursively scan ``obj`` for actor dicts carrying ``id`` + ``name``.

    Populates ``out`` with ``{id: name}`` mappings for every actor-like object
    found at any nesting level in the payload.  Only the first ``name`` seen for
    a given ``id`` is recorded (first-writer-wins so earlier, more authoritative
    entries dominate).
    """
    if isinstance(obj, list):
        for item in obj:
            _collect_actor_names_from_obj(item, out)
        return
    if not isinstance(obj, dict):
        return
    obj_type = obj.get("type") or obj.get("type_")
    obj_id = obj.get("id") or obj.get("id_")
    obj_name = obj.get("name")
    if (
        obj_type in _NAME_BEARING_TYPES
        and obj_id
        and obj_name
        and isinstance(obj_id, str)
        and isinstance(obj_name, str)
        and obj_name.strip()
        and obj_id not in out
    ):
        out[obj_id] = obj_name.strip()
    # Recurse into common nested keys.  ActivityStreams permits ``actor``,
    # ``object``, ``target``, and ``origin`` to carry a list of objects (e.g.
    # multiple recipients); the list branch at the top of this function scans
    # each element, so a plain recursive call handles scalars and lists alike.
    for key in ("actor", "object", "object_", "target", "origin"):
        _collect_actor_names_from_obj(obj.get(key), out)


def collect_actor_names(
    replicas: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
    """Build a URI→display-name map by scanning all raw ledger entries.

    Walks every payload snapshot in ``replicas`` looking for actor objects
    that carry both an ``id`` (URI) and a ``name`` field.  Returns a
    ``{uri: name}`` mapping used to resolve UUID-based actor URIs to semantic
    labels (e.g. "Vendor", "Finder") in the rendered report.
    """
    names: dict[str, str] = {}
    for actor_key in sorted(replicas):
        for raw in replicas[actor_key]:
            payload = _first(
                raw, "payload_snapshot", "payloadSnapshot", default={}
            )
            if isinstance(payload, dict):
                _collect_actor_names_from_obj(payload, names)
    return names


# ---------------------------------------------------------------------------
# Friendly naming (DRPT-03)
# ---------------------------------------------------------------------------

#: Activity-Streams wrapper types whose ``object`` child is the real semantic target.
_WRAPPER_TYPES = frozenset({"Accept", "Reject", "Offer", "Invite"})

#: Wire types that resolve to actor names; use friendly_actor_name on their id instead of a generic noun.
_ACTOR_LIKE_TYPES = frozenset(
    {
        "Organization",
        "Actor",
        "Service",
        "Application",
        "Person",
        "Group",
        "CaseParticipant",
        "CaseActor",
    }
)

#: Wire object type → friendly noun for event summaries and the target column.
_TARGET_NOUNS: dict[str, str] = {
    "VulnerabilityReport": "report",
    "VulnerabilityCase": "case",
    "CaseProposal": "case proposal",
    "Note": "note",
    "ParticipantStatus": "participant status",
    "CaseStatus": "case status",
    "EmbargoEvent": "embargo",
    "CaseParticipant": "participant",
    "CaseLedgerEntry": "ledger entry",
    "Actor": "actor",
    "Offer": "offer",
    "Accept": "acceptance",
    "Reject": "rejection",
}


def _titleize(segment: str) -> str:
    """Turn a URI/dir segment into a friendly label ("case-actor" → "Case Actor").

    Splits on ``-``/``_``, drops UUID-like hex tokens (so a
    ``case-actor-<uuid>`` sub-actor id collapses to "Case Actor"), and
    capitalizes the remaining words.
    """
    raw = segment.replace("_", " ").replace("-", " ").split()
    words = [w for w in raw if not _looks_like_hex_token(w)]
    if not words:
        words = raw
    return " ".join(w.capitalize() for w in words)


def _looks_like_hex_token(token: str) -> bool:
    """Return True for a pure-hex token of length >= 6 (a likely UUID chunk)."""
    return len(token) >= 6 and all(
        c in "0123456789abcdef" for c in token.lower()
    )


def friendly_actor_name(
    actor_uri: str | None,
    actor_names: dict[str, str] | None = None,
) -> str:
    """Return a short, friendly actor label derived from an actor URI.

    Checks ``actor_names`` first (a URI→display-name map built from payload
    snapshots); falls back to the last URI path segment when no entry is found
    (``…/actors/finder`` → "Finder").  Returns an em dash when no acting actor
    is recorded (e.g. genesis entries).
    """
    if not actor_uri:
        return "—"
    if actor_names and actor_uri in actor_names:
        return actor_names[actor_uri]
    segment = actor_uri.rstrip("/").rsplit("/", 1)[-1]
    return _titleize(segment) or segment


def friendly_target_noun(target_type: str | None) -> str | None:
    """Return a friendly noun for a wire object type (``Note`` → "note")."""
    if not target_type:
        return None
    if target_type in _TARGET_NOUNS:
        return _TARGET_NOUNS[target_type]
    # Fallback: split a CamelCase / prefixed type into lowercase words.
    stripped = (
        target_type[3:] if target_type.startswith("as_") else target_type
    )
    words: list[str] = []
    current = ""
    for char in stripped:
        if char.isupper() and current:
            words.append(current)
            current = char
        else:
            current += char
    if current:
        words.append(current)
    return " ".join(w.lower() for w in words) if words else target_type.lower()


def friendly_object_label(
    obj_type: str | None, obj_ref: str | None
) -> str | None:
    """Return a friendly label for a target object.

    Actor-like types (Organization, Actor, …) are resolved via
    :func:`friendly_actor_name` using their URI so the label reads "Vendor"
    rather than "organization".  All other types fall back to
    :func:`friendly_target_noun`.
    """
    if not obj_type:
        return friendly_actor_name(obj_ref) if obj_ref else None
    if obj_type in _ACTOR_LIKE_TYPES:
        return friendly_actor_name(obj_ref)
    return friendly_target_noun(obj_type)


def event_phrase(event_type: str) -> str:
    """Map an event type to an active-voice phrase via the semantic registry.

    Looks up the ``SemanticEntry`` for *event_type* in ``SEMANTIC_REGISTRY``
    and returns ``entry.phrase`` with all named slots filled with ``"—"``
    (DRPT-03-002).  Falls back to a humanized version of *event_type* when
    the event type is not a recognized ``MessageSemantics`` value.
    """
    try:
        semantics = MessageSemantics(event_type)
    except ValueError:
        humanized = event_type.replace("_", " ").strip()
        return humanized or "performed an action"
    entry = lookup_entry(semantics)
    slots: dict[str, str] = defaultdict(lambda: "—")
    return entry.phrase.format_map(slots)


# ---------------------------------------------------------------------------
# Distilled timeline model (DRPT-02)
# ---------------------------------------------------------------------------


class CaseTimelineEvent(BaseModel):
    """One canonical timeline event distilled into friendly-readable form.

    This is the reusable, testable "friendly data" layer between JSONL parsing
    and rendering: both renderers consume :class:`CaseTimelineEvent` objects
    rather than raw JSONL dicts (DRPT-02-001).

    Fields:
        case_id: URI of the case this entry belongs to; the primary grouping
            key so distinct cases discovered under one input directory are
            never interleaved (DRPT-02-006).
        log_index: Monotonic per-case index; the canonical ordering key.
        entry_hash: Full SHA-256 hex hash of the entry (chain traceability).
        disposition: ``"recorded"`` or ``"rejected"``.
        event_type: Short machine-readable event descriptor (``eventType``).
        actor_uri: Full URI of the acting actor (secondary detail).
        target_ref: Full id of the target object (secondary detail).
        target_type: Wire type of the target object.
        activity_target_ref: Full id of the ActivityStreams destination/target
            object — the case or participant that is the *destination* of an
            Offer/Invite (e.g. the case in
            ``Accept(Invite(object=Org, target=Case))``).
        activity_target_type: Wire type of the destination/target object.
        received_at: Server-generated receipt timestamp (``receivedAt``).
        rm_state / em_state / pec_state / vf_state / d_state / pxa_state: Resulting
            state-machine dimensions extracted from the payload snapshot, where
            present. ``pec_state`` is the per-participant Embargo Consent state
            (NO_EMBARGO, INVITED, SIGNATORY, LAPSED, DECLINED), extracted from
            the ``consent`` dimension object or legacy ``emConsentState`` /
            ``embargoConsentState`` flat fields.
        present_in: Sorted actor-directory names whose replicas hold this
            entry (the per-actor replica-presence indicator, DRPT-02-005).
    """

    case_id: str = ""
    log_index: int = -1
    entry_hash: str = ""
    disposition: str = "recorded"
    event_type: str = ""
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
    pec_state: str | None = None
    vf_state: str | None = None
    d_state: str | None = None
    pxa_state: str | None = None
    present_in: list[str] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "CaseTimelineEvent":
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
        # and Accept(Invite(object=X, target=Y)) chains).  Track the innermost
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
            disposition=str(_first(raw, "disposition", default="recorded")),
            event_type=str(_first(raw, "event_type", "eventType", default="")),
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
            em_state=_dimension_state(candidates, "em", "emState", "em_state"),
            pec_state=_dimension_state(
                candidates,
                "consent",
                "emConsentState",
                "em_consent_state",
                "embargoConsentState",
                "embargo_consent_state",
            ),
            vf_state=_dimension_state(candidates, "vf", "vfState", "vf_state"),
            d_state=_dimension_state(candidates, "d", "dState", "d_state"),
            pxa_state=_dimension_state(
                candidates, "pxa", "pxaState", "pxa_state"
            ),
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

        Looks up the ``SemanticEntry`` phrase template for this event type and
        fills named slots with values derived from the event record's resolved
        label properties.  Unknown slot names fall back to ``"—"``.
        """
        try:
            semantics = MessageSemantics(self.event_type)
        except ValueError:
            humanized = (
                self.event_type.replace("_", " ").strip()
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
        summary = phrase[:1].upper() + phrase[1:] if phrase else phrase
        if self.disposition != "recorded":
            summary = f"{summary} [{self.disposition}]"
        return summary


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
    by the name of the directory that contains each file (DRPT-01-002,
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
    (DRPT-02-004, DRPT-02-005).

    Entries with ``disposition != "recorded"`` are silently skipped; they are
    local-only correlation markers with empty payloads that must not appear in
    the report (DRPT-02-007).

    Actor URIs are resolved to display names extracted from inline actor objects
    in the payload snapshots (e.g. Organization objects carrying a ``name``
    field).  This resolves UUID-based actor URIs (which produce hex-fragment
    labels) to semantic names like "Vendor" or "Finder".
    """
    actor_names = collect_actor_names(replicas)

    by_key: dict[str, CaseTimelineEvent] = {}
    presence: dict[str, set[str]] = {}

    for actor_name in sorted(replicas):
        for raw in replicas[actor_name]:
            event = CaseTimelineEvent.from_raw(raw)
            if event.disposition != "recorded":
                continue
            if event.entry_hash:
                key = event.entry_hash
            else:
                key = (
                    f"__nohash__:{actor_name}:{event.log_index}:"
                    f"{event.event_type}"
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
    # (DRPT-02-006, DRPT-02-004).
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


# ---------------------------------------------------------------------------
# Rendering (DRPT-04)
# ---------------------------------------------------------------------------

_TABLE_HEADERS = [
    "#",
    "ΔT",
    "Actor",
    "Event",
    "Target",
    "RM",
    "EM",
    "PEC",
    "CS",
    "Entry",
]


def _md_cell(text: str) -> str:
    """Escape a value for use inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime.

    Handles both ``Z`` suffix (``fromisoformat`` requires ``+00:00`` on
    Python < 3.11) and ``+00:00`` offset forms.
    """
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _format_delta(
    received_at: str | None,
    prev_received_at: str | None,
) -> str:
    """Return a compact delta string between two ``receivedAt`` timestamps.

    - Returns ``"—"`` when ``received_at`` is ``None`` (no timestamp on this row).
    - Returns ``"+0s"`` when ``prev_received_at`` is ``None`` and ``received_at``
      is set (first timestamped row — anchor point).
    - Returns ``"+Ns"`` / ``"+Nm Ns"`` / ``"+Nh Nm Ns"`` for a positive delta;
      no day component (spec: DRPT-04-007).
    """
    if received_at is None:
        return "—"
    if prev_received_at is None:
        return "+0s"
    try:
        dt_curr = _parse_timestamp(received_at)
        dt_prev = _parse_timestamp(prev_received_at)
    except ValueError:
        return "—"
    total_seconds = round((dt_curr - dt_prev).total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"+{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"+{minutes}m {seconds}s"
    return f"+{seconds}s"


def _case_time_range(
    events: list[CaseTimelineEvent],
) -> tuple[str | None, str | None]:
    """Return ``(min_received_at, max_received_at)`` for a list of events.

    Parses each ``received_at`` string via :func:`_parse_timestamp` so
    comparison is chronological regardless of offset notation (``Z`` vs
    ``+00:00``) or future microsecond precision changes. Returns ``(None,
    None)`` when no event carries a timestamp (DRPT-04-006).
    """
    pairs: list[tuple[str, datetime]] = []
    for e in events:
        if e.received_at is None:
            continue
        try:
            pairs.append((e.received_at, _parse_timestamp(e.received_at)))
        except ValueError:
            logger.debug("Skipping unparseable received_at: %r", e.received_at)
    if not pairs:
        return None, None
    first_str, _ = min(pairs, key=lambda p: p[1])
    last_str, _ = max(pairs, key=lambda p: p[1])
    return first_str, last_str


def _render_markdown_case(
    lines: list[str], events: list[CaseTimelineEvent], actors: list[str]
) -> None:
    """Append one case's markdown table (header + rows) to ``lines``."""
    headers = _TABLE_HEADERS + [_md_cell(a) for a in actors]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    prev_ts: str | None = None
    for event in events:
        delta = _format_delta(event.received_at, prev_ts)
        if event.received_at is not None:
            prev_ts = event.received_at
        row = [
            str(event.log_index),
            _md_cell(delta),
            _md_cell(event.actor_label),
            _md_cell(event.summary),
            _md_cell(event.target_label or ""),
            _md_cell(event.rm_state or ""),
            _md_cell(event.em_state or ""),
            _md_cell(event.pec_state or ""),
            _md_cell(event.cs_state or ""),
            _md_cell(event.short_hash),
        ]
        row += ["✓" if a in event.present_in else "" for a in actors]
        lines.append("| " + " | ".join(row) + " |")


def render_markdown(events: list[CaseTimelineEvent], actors: list[str]) -> str:
    """Render the timeline as a markdown table report (DRPT-04-001).

    Events are partitioned by ``case_id`` into one ``## Case …`` section each
    (DRPT-02-006); within a section there is one row per canonical event over
    the distilled fields, followed by a per-actor replica-presence matrix
    column group (``✓`` = present).
    """
    by_case = group_events_by_case(events)
    lines: list[str] = ["# Case Timeline Report", ""]
    lines.append(f"- Events: {len(events)}")
    lines.append(f"- Cases: {len(by_case)}")
    lines.append(f"- Replicas: {', '.join(actors) if actors else '(none)'}")
    lines.append("")
    lines.append(
        "The trailing per-actor columns are the replica-presence matrix: "
        "`✓` marks the actor replicas that hold each canonical entry."
    )
    lines.append("")

    for case_id, case_events in by_case.items():
        lines.append(f"## Case {_md_cell(case_id or '(unknown)')}")
        lines.append("")
        first, last = _case_time_range(case_events)
        if first is not None and last is not None:
            lines.append(f"- Time range: {_md_cell(first)} – {_md_cell(last)}")
            lines.append("")
        _render_markdown_case(lines, case_events, actors)
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _html_cell(text: str, title: str | None = None) -> str:
    """Return an escaped ``<td>`` cell, optionally with a ``title`` tooltip."""
    attr = f' title="{html.escape(title, quote=True)}"' if title else ""
    return f"<td{attr}>{html.escape(text)}</td>"


def _html_presence_row(event: CaseTimelineEvent, actors: list[str]) -> str:
    """Return the ``<td>`` cells for the replica-presence matrix (DRPT-04-003)."""
    cells: list[str] = []
    for actor in actors:
        present = actor in event.present_in
        symbol = "✅" if present else "⬜"
        label = "present" if present else "absent"
        cells.append(
            f'<td class="presence" title="{html.escape(actor)}: {label}">'
            f"{symbol}</td>"
        )
    return "".join(cells)


_HTML_STYLE = """
:root { color-scheme: light dark; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  margin: 2rem; line-height: 1.4;
}
h1 { margin-bottom: 0.25rem; }
h2 { margin-top: 2rem; font-size: 1.1rem; }
.meta { color: #666; margin-bottom: 1rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
th, td {
  border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left;
  vertical-align: top;
}
th { background: #f0f0f0; }
tr.rejected { background: #fff0f0; }
td.presence { text-align: center; }
th.presence-group { text-align: center; }
code { font-family: ui-monospace, monospace; }
""".strip()


def _render_html_case_table(
    events: list[CaseTimelineEvent], actors: list[str]
) -> str:
    """Return the ``<table>`` element for one case's events."""
    head_cells = "".join(f"<th>{html.escape(h)}</th>" for h in _TABLE_HEADERS)
    presence_head = "".join(
        f'<th class="presence-group" title="Replica presence: {html.escape(a)}">'
        f"{html.escape(a)}</th>"
        for a in actors
    )

    body_rows: list[str] = []
    prev_ts: str | None = None
    for event in events:
        row_class = (
            "" if event.disposition == "recorded" else ' class="rejected"'
        )
        delta = _format_delta(event.received_at, prev_ts)
        if event.received_at is not None:
            prev_ts = event.received_at
        cells = [
            _html_cell(str(event.log_index)),
            _html_cell(delta, title=event.received_at or None),
            _html_cell(event.actor_label, title=event.actor_uri or None),
            _html_cell(event.summary),
            _html_cell(
                event.target_label or "", title=event.target_ref or None
            ),
            _html_cell(event.rm_state or ""),
            _html_cell(event.em_state or ""),
            _html_cell(event.pec_state or ""),
            _html_cell(event.cs_state or ""),
            _html_cell(event.short_hash, title=event.entry_hash or None),
        ]
        body_rows.append(
            f"<tr{row_class}>{''.join(cells)}"
            f"{_html_presence_row(event, actors)}</tr>"
        )

    return (
        "<table>\n<thead>\n<tr>"
        f"{head_cells}{presence_head}</tr>\n</thead>\n<tbody>\n"
        + "\n".join(body_rows)
        + "\n</tbody>\n</table>"
    )


def render_html(events: list[CaseTimelineEvent], actors: list[str]) -> str:
    """Render the timeline as a self-contained static HTML report.

    All styling is inlined in a ``<style>`` block; the document references no
    external CSS, JS, fonts, or network assets, so it renders identically
    offline (DRPT-04-002). Events are partitioned by ``case_id`` into one
    ``<h2>Case …</h2>`` + table section each (DRPT-02-006). The per-actor
    replica-presence matrix is rendered as a per-actor emoji cell per event
    (DRPT-04-003). Full URIs/ids are retained only as ``title`` tooltips
    (DRPT-03-001).
    """
    by_case = group_events_by_case(events)
    sections: list[str] = []
    for case_id, case_events in by_case.items():
        first, last = _case_time_range(case_events)
        time_range_html = ""
        if first is not None and last is not None:
            time_range_html = (
                f'<p class="meta">Time range: {html.escape(first)}'
                f" – {html.escape(last)}</p>\n"
            )
        sections.append(
            f"<h2>Case {html.escape(case_id or '(unknown)')}</h2>\n"
            + time_range_html
            + _render_html_case_table(case_events, actors)
        )

    replicas_label = html.escape(", ".join(actors) if actors else "(none)")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Case Timeline Report</title>\n"
        f"<style>\n{_HTML_STYLE}\n</style>\n"
        "</head>\n<body>\n"
        "<h1>Case Timeline Report</h1>\n"
        f'<p class="meta">Events: {len(events)} &middot; '
        f"Cases: {len(by_case)} &middot; Replicas: {replicas_label}</p>\n"
        '<p class="meta">The trailing per-actor columns are the '
        "replica-presence matrix (✅ present, ⬜ absent).</p>\n"
        + "\n".join(sections)
        + "\n</body>\n</html>\n"
    )


_RENDERERS = {"markdown": render_markdown, "html": render_html}
_EXTENSIONS = {"markdown": ".md", "html": ".html"}


def generate_report(input_dir: Path, fmt: str) -> str:
    """Discover, distil, and render the report for ``input_dir`` in ``fmt``."""
    replicas = discover_replicas(input_dir)
    events = build_timeline(replicas)
    actors = discovered_actors(replicas)
    logger.info(
        "Distilled %d canonical events across %d replicas: %s",
        len(events),
        len(actors),
        ", ".join(actors),
    )
    return _RENDERERS[fmt](events, actors)


# ---------------------------------------------------------------------------
# CLI (DRPT-01-001, DRPT-04-004, DRPT-04-005)
# ---------------------------------------------------------------------------


def default_input_dir() -> Path:
    """Return the default input directory (``DEVLOGS_DIR`` env, else ``devlogs/``).

    Delegates to :func:`vultron.demo.helpers.ledger_dump.default_devlogs_root`
    so this reader and the dump that writes the ledgers cannot disagree about
    where they live (DEMOMA-17-001).
    """
    return default_devlogs_root()


def default_output_path(input_dir: Path, fmt: str) -> Path:
    """Return the default report file path for ``fmt`` under ``input_dir``."""
    return input_dir / f"case-timeline-report{_EXTENSIONS[fmt]}"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the report tool."""
    parser = argparse.ArgumentParser(
        # prog defaults to sys.argv[0], so --help shows the correct name for
        # both `python -m vultron.demo.report` and the `vultron-demo-report`
        # console-script entry point.
        description=(
            "Render a readable report from demo scenario case-ledger JSONL "
            "replica files."
        ),
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=None,
        help=(
            "Directory to scan for **/*-case-ledger.jsonl files "
            "(default: $DEVLOGS_DIR, else devlogs/)."
        ),
    )
    parser.add_argument(
        "--format",
        choices=sorted(_RENDERERS),
        default="markdown",
        help="Output format (default: markdown).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Report output file path (default: <input-dir>/case-timeline-report.*).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open an HTML report in the browser (required for CI).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (DRPT-01-004).

    Callable with no arguments (defaults to ``sys.argv[1:]``) so it also works
    as a console-script target.
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    args = _parse_args(argv)
    input_dir = Path(args.input_dir) if args.input_dir else default_input_dir()
    output_path = (
        Path(args.output)
        if args.output
        else default_output_path(input_dir, args.format)
    )

    try:
        report = generate_report(input_dir, args.format)
    except ReportError as exc:
        logger.error("error: %s", exc)
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    except OSError as exc:
        logger.error("error: cannot write %s: %s", output_path, exc)
        return 1

    logger.info("Wrote %s report → %s", args.format, output_path)

    if args.format == "html" and not args.no_open:
        webbrowser.open(output_path.resolve().as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
