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

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from vultron.errors import LedgerReadError
from vultron.measure.ledger import (
    Dimension,
    actor_uri,
    candidate_dicts,
    coerce_int,
    collect_actor_names,
    dimension_state,
    display_label,
    entry_references,
    first_present,
    friendly_actor_name,
    label_names,
    payload_of,
    read_ledger_file,
    render_event_phrase,
)

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
        payload = payload_of(raw)

        refs = entry_references(payload)
        candidates = candidate_dicts(payload)
        received = first_present(raw, "received_at", "receivedAt")

        return cls(
            case_id=str(first_present(raw, "case_id", "caseId", default="")),
            log_index=coerce_int(
                first_present(raw, "log_index", "logIndex", default=-1),
                default=-1,
            ),
            entry_hash=str(
                first_present(raw, "entry_hash", "entryHash", default="")
            ),
            semantic_type=str(
                first_present(raw, "semantic_type", "semanticType", default="")
            ),
            actor_uri=actor_uri(payload.get("actor")),
            target_ref=refs.object_ref,
            target_type=refs.object_type,
            activity_target_ref=refs.target_ref,
            activity_target_type=refs.target_type,
            received_at=str(received) if received else None,
            rm_state=dimension_state(candidates, Dimension.RM),
            em_state=dimension_state(candidates, Dimension.EM),
            vf_state=dimension_state(candidates, Dimension.VF),
            d_state=dimension_state(candidates, Dimension.D),
            pxa_state=dimension_state(candidates, Dimension.PXA),
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

    def _reference_label(
        self, ref: str | None, obj_type: str | None, display_name: str | None
    ) -> str | None:
        """Label one reference through the shared resolver (DRPT-03-009).

        *display_name* is the name :func:`build_timeline` resolved for *ref*;
        without one, :func:`~vultron.measure.ledger.display_label` names the
        case "case" and never shows a bare URI or UUID.
        """
        names = {ref: display_name} if ref and display_name else {}
        return display_label(
            ref, obj_type, names, case_id=self.case_id or None
        )

    @property
    def target_label(self) -> str | None:
        """Friendly target label; ``object → destination`` when both are present.

        Each half is the display name :func:`build_timeline` resolved for it
        (an actor's name, or for a participant the actor it stands for), else
        the shared :func:`~vultron.measure.ledger.display_label`: the case reads
        "case", a typed object its type's noun, and an opaque id an "unnamed"
        label, never a bare URI or UUID (DRPT-03-001, DRPT-03-009).
        """
        obj_label = self._reference_label(
            self.target_ref, self.target_type, self.target_display_name
        )
        dest_label = self._reference_label(
            self.activity_target_ref,
            self.activity_target_type,
            self.activity_target_display_name,
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
        actor = self.actor_label if self.actor_uri else None
        return render_event_phrase(
            self.semantic_type, actor, self.target_label
        )


# ---------------------------------------------------------------------------
# Discovery and timeline construction (DRPT-01, DRPT-02)
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file strictly: the report refuses a file with a bad row.

    A thin wrapper over the shared tolerant reader,
    :func:`vultron.measure.ledger.read_ledger_file`, which degrades a bad row
    instead (CEH-02-008).  The report tool wants the opposite, so this raises
    when the tolerant reader reports any unusable row.

    Raises:
        ReportError: if the file cannot be read, or any non-blank line is not a
            JSON object (DRPT-01-004).
    """
    try:
        ledger_file = read_ledger_file(path)
    except LedgerReadError as exc:
        raise ReportError(str(exc)) from exc
    if ledger_file.unusable_rows:
        raise ReportError(
            "; ".join(row.describe() for row in ledger_file.unusable_rows)
        )
    return ledger_file.entries


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
    # Targets may name a participant by its id; this map names the actor it
    # stands for, the same way the case-history dump does (DRPT-03-009).
    target_names = label_names(replicas)

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
        if event.target_ref and event.target_ref in target_names:
            event.target_display_name = target_names[event.target_ref]
        if (
            event.activity_target_ref
            and event.activity_target_ref in target_names
        ):
            event.activity_target_display_name = target_names[
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
