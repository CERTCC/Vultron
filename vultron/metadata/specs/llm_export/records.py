"""Export records for the LLM projection: requirements, relationships, steps,
topics and edges.
"""

from __future__ import annotations

from typing import Any

from vultron.metadata.specs.registry import (
    effective_scope,
    effective_tags,
)
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    Spec,
    SpecFile,
    SpecGroup,
)

#: Topics whose requirements apply to every change regardless of its primary
#: topic.  Single source of truth for ``spec-dump --cross-cutting``; skills
#: reference the flag rather than repeating this list.
CROSS_CUTTING_TOPICS: tuple[str, ...] = ("ARCH", "CS", "TB", "HP", "SL", "EH")


def _behavioral_fields(spec: BehavioralSpec) -> dict[str, Any]:
    """Return the fields only a :class:`BehavioralSpec` carries.

    Split out of :func:`_spec_record` so that function stays within the
    complexity gate as optional fields are added to the export.
    """
    rec: dict[str, Any] = {}
    if spec.preconditions:
        rec["preconditions"] = [p.description for p in spec.preconditions]
    if spec.steps:
        rec["steps"] = [_step_record(s) for s in spec.steps]
    if spec.postconditions:
        rec["postconditions"] = [p.description for p in spec.postconditions]
    return rec


def _spec_record(
    spec: Spec,
    group: SpecGroup,
    file: SpecFile,
) -> dict[str, Any]:
    """Build a flat, inheritance-resolved dict for a single spec."""
    rec: dict[str, Any] = {
        "id": spec.id,
        "topic": file.id,
        "group": group.id,
        "group_title": group.title,
        "type": (
            "behavioral" if isinstance(spec, BehavioralSpec) else "statement"
        ),
        "priority": spec.priority.value,
        "statement": spec.statement,
        "kind": spec.kind.value,
        "scope": [s.value for s in effective_scope(spec, group, file)],
    }

    tags = effective_tags(spec, file)
    if tags:
        rec["tags"] = [t.value for t in tags]

    rec["rationale"] = spec.rationale

    # ``note`` carries the caveats that keep a requirement from being read the
    # wrong way — which side an obligation binds, what a receiver must *not* do
    # about it.  Dropping it made that guidance unreachable for any agent
    # following AGENTS.md, which says to load specs through this exporter and
    # never to read raw ``specs/*.yaml``.  ``_rel_record`` already exports a
    # relationship's ``note``; omitting the spec-level one was an oversight.
    if spec.note is not None:
        rec["note"] = spec.note

    if not spec.testable:
        rec["testable"] = False

    if spec.relationships:
        rec["relationships"] = [_rel_record(r) for r in spec.relationships]

    # A cited requirement no relationship links, with why (SR-13-022): an
    # agent reading the statement's citation needs the reason it is unlinked.
    if spec.see_also:
        rec["see_also"] = [
            {"spec_id": entry.spec_id, "reason": entry.reason}
            for entry in spec.see_also
        ]

    if spec.adr:
        rec["adr"] = list(spec.adr)

    rec["verification"] = spec.verification

    if isinstance(spec, BehavioralSpec):
        rec.update(_behavioral_fields(spec))

    return rec


def _rel_record(r: object) -> dict[str, str]:
    d: dict[str, str] = {
        "rel_type": r.rel_type.value,  # type: ignore[attr-defined]
        "spec_id": r.spec_id,  # type: ignore[attr-defined]
    }
    if r.note is not None:  # type: ignore[attr-defined]
        d["note"] = r.note  # type: ignore[attr-defined]
    return d


def _step_record(s: object) -> dict[str, Any]:
    d: dict[str, Any] = {
        "order": s.order,  # type: ignore[attr-defined]
        "actor": s.actor,  # type: ignore[attr-defined]
        "action": s.action,  # type: ignore[attr-defined]
    }
    if s.expected is not None:  # type: ignore[attr-defined]
        d["expected"] = s.expected  # type: ignore[attr-defined]
    return d


def _topic_record(file: SpecFile) -> dict[str, str]:
    return {
        "id": file.id,
        "title": file.title,
    }


def _edge_record(spec_id: str, relationship: object) -> dict[str, str]:
    edge: dict[str, str] = {
        "from": spec_id,
        "rel_type": relationship.rel_type.value,  # type: ignore[attr-defined]
        "to": relationship.spec_id,  # type: ignore[attr-defined]
    }
    if relationship.note:  # type: ignore[attr-defined]
        edge["note"] = relationship.note  # type: ignore[attr-defined]
    return edge


def _slim_record(spec: Spec) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "id": spec.id,
        "priority": spec.priority.value,
        "statement": spec.statement,
    }
    # ``note`` is kept even in slim output: it is the guidance that stops a
    # requirement being implemented on the wrong side (see _spec_record).
    if spec.note is not None:
        rec["note"] = spec.note
    return rec


def _full_edges(spec_id: str, spec: Spec) -> list[dict[str, str]]:
    edges = [_edge_record(spec_id, r) for r in spec.relationships or []]
    edges.extend(
        {"from": spec_id, "rel_type": "derives_from", "to": adr_id}
        for adr_id in spec.adr or []
    )
    return edges
