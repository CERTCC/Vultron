"""Tolerant field access over raw case-ledger JSONL entries (CEH-02-002, DRPT-02-003).

A ledger file is read as plain JSON, not validated into core models: the measure
layer is handed archived and foreign ledgers it never validated, and the demo
report must render whatever a run dumped. So every accessor here tolerates both
the camelCase and the snake_case spelling of a field, and the dimension-state
reader searches every depth and spelling a payload snapshot admits
(``notes/case-ledger-parsing.md``).
"""

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

from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Any


def first_present(
    mapping: Mapping[str, object], *names: str, default: object = None
) -> object:
    """Return the first present, non-None value among ``names``.

    Tolerates the camelCase/snake_case spelling split present in the source
    JSONL (e.g. ``logIndex``/``log_index``), mirroring the accessors in
    ``test/ci/invariants/common.py``.
    """
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return default


def coerce_int(value: object, default: int) -> int:
    """Best-effort ``int`` coercion; returns ``default`` on failure.

    Keeps a per-entry distiller tolerant of corrupt entries (e.g. a non-numeric
    ``logIndex``) so a single malformed field degrades one row rather than
    crashing the whole pass (DRPT-01-004, DRPT-02-003).
    """
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return default
    try:
        return int(value)
    except OverflowError, ValueError:
        return default


def actor_uri(actor: object) -> str | None:
    """Normalize a payload ``actor`` field to a string URI, or ``None``.

    Tolerates both the bare-string spelling and an inline actor object
    (``{"id": "...", "type": "..."}``) so a nested actor does not raise a
    validation error out of a distiller (DRPT-02-003).
    """
    if isinstance(actor, str):
        return actor or None
    if isinstance(actor, dict):
        ref = actor.get("id") or actor.get("id_")
        return str(ref) if ref else None
    return None


# ---------------------------------------------------------------------------
# Entry envelope accessors
# ---------------------------------------------------------------------------


def payload_of(entry: Mapping[str, object]) -> dict[str, Any]:
    """Return *entry*'s payload snapshot, or an empty dict when it has none."""
    snapshot = first_present(entry, "payload_snapshot", "payloadSnapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def case_id_of(entry: Mapping[str, object]) -> str | None:
    """Return *entry*'s case id, or ``None`` when it is absent or blank."""
    value = first_present(entry, "case_id", "caseId")
    if isinstance(value, str) and value.strip():
        return value
    return None


def entry_hash_of(entry: Mapping[str, object]) -> str | None:
    """Return *entry*'s entry hash, or ``None`` when it is absent or blank."""
    value = first_present(entry, "entry_hash", "entryHash")
    if isinstance(value, str) and value.strip():
        return value
    return None


def log_index_of(entry: Mapping[str, object]) -> int | None:
    """Return *entry*'s log index, or ``None`` when it is not a usable position.

    A committed entry always carries an integer index ``>= 0`` (CLP-14-010).
    ``bool``, ``float`` and numeric strings are not coerced, since each would
    silently stand in for a real position; neither is a negative index.
    """
    value = first_present(entry, "log_index", "logIndex")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


# ---------------------------------------------------------------------------
# Dimension-state extraction (CEH-02-002)
# ---------------------------------------------------------------------------


class Dimension(StrEnum):
    """A state-machine dimension a payload snapshot can record.

    Each value is the dimension's key in the current serialization; the flat
    spellings a ledger may also carry are in :data:`FLAT_SPELLINGS`.
    """

    RM = "rm"
    EM = "em"
    VF = "vf"
    D = "d"
    PXA = "pxa"


#: The flat keys a dimension may be spelled under, besides its own key: the wire
#: camelCase form and the legacy snake_case form (``notes/case-ledger-parsing.md``).
FLAT_SPELLINGS: Mapping[Dimension, tuple[str, ...]] = {
    Dimension.RM: ("rmState", "rm_state"),
    Dimension.EM: ("emState", "em_state"),
    Dimension.VF: ("vfState", "vf_state"),
    Dimension.D: ("dState", "d_state"),
    Dimension.PXA: ("pxaState", "pxa_state"),
}


def candidate_dicts(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
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


def dimension_state(
    candidates: Iterable[dict[str, Any]],
    dimension: Dimension,
) -> str | None:
    """Extract a single state-machine dimension value from candidate dicts.

    Handles all three live shapes: the bare state value a dimension serializes
    to since ARCH-25-005 (ADR-0099) / SDO-01-004 (``{"rm": "..."}``), the ADR-0036
    one-key mapping (``{"rm": {"state": "..."}}``), and the flat wire and legacy
    spellings (``{"rmState": "..."}``, ``{"rm_state": "..."}``).  Missing one of
    them makes every affected row report ``None``, which is the #2232 / #2262
    failure shape — see ``notes/case-ledger-parsing.md``.
    """
    for candidate in candidates:
        dim = candidate.get(dimension.value)
        if isinstance(dim, dict):
            state = dim.get("state")
            if state:
                return str(state)
        elif isinstance(dim, str) and dim:
            return str(dim)
        for flat in FLAT_SPELLINGS[dimension]:
            value = candidate.get(flat)
            if value:
                return str(value)
    return None


def read_dimension_state(
    snapshot: dict[str, Any], dimension: Dimension
) -> str | None:
    """Return the *dimension* state a payload snapshot records, at any depth.

    The one-call form of :func:`candidate_dicts` and :func:`dimension_state`
    (CEH-02-002).
    """
    return dimension_state(candidate_dicts(snapshot), dimension)
