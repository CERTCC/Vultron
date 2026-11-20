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

"""Render a case preview cut for a projection as a CSAF 2.1 document.

The second step of a projection (ADR-0219): a call site's profile has cut
the case and its ledger into a
:class:`~vultron.core.models.case_projection.ProjectionCut`, and this module
translates only that cut, with the inputs its call site passes
(:class:`~vultron.core.models.case_projection.ProjectionInputs`),
into a document of the category its call site passes, ``csaf_base`` while
the case holds no products.  It reads no case and no ledger,
so it cannot show what the profile withheld; it selects, and may leave out a
value the preview shows because CSAF cannot express it.

- **A withheld value is an absence.**  A ``Redacted`` marker anywhere in the
  preview renders as nothing, as an omitted field does, and the document
  lists nothing it leaves out.
- **A projection is a pure function of its identity.**  ``tracking.id``
  derives from the case id, the profile's versioned name, the log index of
  the preview's ledger position and, only when the caller supplies them, a
  short digest of the acknowledgments.  The version is ``1``, with one
  revision entry numbered ``1`` (CSAF mandatory test 6.1.21), and every
  document date is the commit time of the ledger entry at the position,
  never a clock read (ADR-0176).
- **One reference names the snapshot**: a ``self`` reference to the case
  that names the entry hash of the position.
- **Involvement from the cut ledger.**  Each act whose kept ledger entries
  have a CSAF meaning, by the crosswalk concept mapping
  (``docs/reference/csaf_crosswalk/concept_mapping.md``), becomes one
  ``completed`` action: a ledger entry records a completed act, never an
  ``attempted`` (an outbox fact) or ``planned`` one.  An action whose CSAF
  category loses a Vultron distinction says it in its ``summary``: whether an
  assessment found the report valid, and that a confirmation records
  acceptance, not only receipt.

The document is built with the generated models (CSAF-05-002).  This module
imports only core models (ARCH-22-001).
"""

import hashlib
import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, JsonValue, TypeAdapter, ValidationError

from vultron.core.models.case_preview import CasePreview
from vultron.core.models.case_preview_envelope import preview_in_force_entry
from vultron.core.models.case_projection import (
    Acknowledgment,
    ProjectingActor,
    ProjectionCut,
    ProjectionInputs,
)
from vultron.core.models.case_projection_profile import named_id
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.redacted import Redacted
from vultron.core.models.vulnerability_item import (
    VulnerabilityItemId,
    csaf_cve_and_ids,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.wire.csaf.models import CommonSecurityAdvisoryFramework
from vultron.wire.csaf.reader import CSAF_21_SCHEMA, CSAF_21_VERSION

#: The categories a call site may pass.  While a case holds no products,
#: the one category a projection can have is ``csaf_base``: the Vulnerability
#: Report and Security Advisory profiles need a product tree and product
#: statuses (ADR-0187, ADR-0219).
CsafCategory = Literal["csaf_base"]

#: The CSAF action category of each act with a CSAF meaning, by the
#: crosswalk concept mapping.  An entry of any other act is left out.
ACTION_CATEGORIES: dict[str, str] = {
    MessageSemantics.SUBMIT_REPORT.value: "notification",
    MessageSemantics.VALIDATE_REPORT.value: "assessment",
    MessageSemantics.INVALIDATE_REPORT.value: "assessment",
    MessageSemantics.ENGAGE_CASE.value: "confirmation",
    MessageSemantics.ACTIVATE_EMBARGO_ON_CASE.value: "embargo",
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value: "confirmation",
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value: "dispute",
}

#: The ``summary`` of an action whose CSAF category loses a Vultron
#: distinction, by the crosswalk concept mapping.
ACTION_SUMMARIES: dict[str, str] = {
    MessageSemantics.VALIDATE_REPORT.value: "The report was found valid.",
    MessageSemantics.INVALIDATE_REPORT.value: "The report was found invalid.",
    MessageSemantics.ENGAGE_CASE.value: (
        "The participant accepted the report for action, not only received it."
    ),
}

#: The CSAF category of a party by the first role it holds, in this order.
_ROLE_CATEGORIES: tuple[tuple[CVDRole, str], ...] = (
    (CVDRole.VENDOR, "vendor"),
    (CVDRole.COORDINATOR, "coordinator"),
    (CVDRole.REPORTER, "discoverer"),
)

#: The length, in hex digits, of the acknowledgments digest in a
#: ``tracking.id``.
ACKNOWLEDGMENTS_DIGEST_LENGTH = 12

_AWARE: TypeAdapter[datetime] = TypeAdapter(AwareDatetime)


def _shown(value: object) -> object | None:
    """*value* as the document may use it: ``None`` for a marker."""
    return None if isinstance(value, Redacted) else value


def _shown_text(value: object) -> str | None:
    """*value* when it is shown, non-empty text."""
    value = _shown(value)
    return value if isinstance(value, str) and value else None


def _shown_items(value: object) -> list[object]:
    """The items a shown list holds that are themselves shown objects: an
    item named only by id, or a marker, has nothing to render."""
    value = _shown(value)
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if item is not None and not isinstance(item, (Redacted, str))
    ]


def role_category(roles: Iterable[CVDRole]) -> str:
    """The CSAF party category of the first role held, in the order VENDOR,
    COORDINATOR, REPORTER; ``other`` for any other roles."""
    held = set(roles)
    return next(
        (category for role, category in _ROLE_CATEGORIES if role in held),
        "other",
    )


def _origin(actor_id: str) -> str:
    """The origin of *actor_id*, a URI: its scheme and authority."""
    parts = urlsplit(actor_id)
    if not parts.scheme or not parts.netloc:
        raise VultronValidationError(
            f"projecting actor {actor_id!r} has no origin to name the"
            " publisher's namespace by (ADR-0219)"
        )
    return f"{parts.scheme}://{parts.netloc}"


def _publisher(actor: ProjectingActor) -> dict[str, JsonValue]:
    return {
        "category": role_category(actor.roles),
        "name": actor.name,
        "namespace": _origin(actor.id_),
    }


class _Position:
    """The ledger position a preview shows: the snapshot it is a cut of."""

    def __init__(self, preview: CasePreview) -> None:
        position = _shown(preview.ledger_position)
        log_index = _shown(getattr(position, "log_index", None))
        entry_hash = _shown_text(getattr(position, "entry_hash", None))
        if not isinstance(log_index, int) or entry_hash is None:
            raise VultronValidationError(
                f"preview {preview.id_!r} shows no ledger position, so a"
                " projection cannot name the snapshot it shows (ADR-0219)"
            )
        self.log_index = log_index
        self.entry_hash = entry_hash


def acknowledgments_digest(acknowledgments: Sequence[Acknowledgment]) -> str:
    """A short digest of the caller's acknowledgments, written as canonical
    JSON, for a ``tracking.id``."""
    canonical = json.dumps(
        [ack.model_dump(mode="json") for ack in acknowledgments],
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:ACKNOWLEDGMENTS_DIGEST_LENGTH]


def tracking_id(
    case_id: str,
    profile_name: str,
    log_index: int,
    caller_acknowledgments: Sequence[Acknowledgment] | None,
) -> str:
    """The ``tracking.id`` of a projection: its identity (ADR-0219)."""
    parts = [case_id, profile_name, str(log_index)]
    if caller_acknowledgments is not None:
        parts.append(f"ack-{acknowledgments_digest(caller_acknowledgments)}")
    return "/".join(parts)


def _tracking(
    cut: ProjectionCut, inputs: ProjectionInputs, position: _Position
) -> dict[str, JsonValue]:
    preview = cut.preview
    date = inputs.position_committed_at.isoformat()
    return {
        "current_release_date": date,
        "id": tracking_id(
            preview.id_,
            cut.profile_name,
            position.log_index,
            inputs.caller_acknowledgments,
        ),
        "initial_release_date": date,
        "revision_history": [
            {"date": date, "number": "1", "summary": "Initial version."}
        ],
        "status": inputs.status.value,
        "version": "1",
    }


def _notes(preview: CasePreview) -> list[dict[str, JsonValue]]:
    """The case's summary and content, then each report's content."""
    notes: list[dict[str, JsonValue]] = []
    summary = _shown_text(preview.summary)
    if summary is not None:
        notes.append({"category": "summary", "text": summary})
    content = _shown_text(preview.content)
    if content is not None:
        notes.append({"category": "description", "text": content})
    for report in _shown_items(preview.vulnerability_reports):
        text = _shown_text(getattr(report, "content", None))
        if text is None:
            continue
        note: dict[str, JsonValue] = {"category": "details", "text": text}
        title = _shown_text(getattr(report, "name", None))
        if title is not None:
            note["title"] = title
        notes.append(note)
    return notes


def _external_references(references: object) -> list[dict[str, JsonValue]]:
    """Each shown case reference as a CSAF ``external`` reference."""
    rendered: list[dict[str, JsonValue]] = []
    for reference in _shown_items(references):
        link = _shown(getattr(reference, "url", None))
        url = _shown_text(getattr(link, "href", None))
        if url is None:
            continue
        summary = _shown_text(getattr(reference, "name", None)) or url
        rendered.append(
            {"category": "external", "summary": summary, "url": url}
        )
    return rendered


def _self_reference(case_id: str, position: _Position) -> dict[str, JsonValue]:
    return {
        "category": "self",
        "summary": (
            f"Vultron case {case_id} at ledger entry {position.log_index},"
            f" entry hash {position.entry_hash}"
        ),
        "url": case_id,
    }


def _acknowledgments(inputs: ProjectionInputs) -> list[dict[str, JsonValue]]:
    return [
        ack.model_dump(mode="json", exclude_defaults=True)
        for ack in inputs.acknowledgments
    ]


def _item_ids(item: object) -> list[VulnerabilityItemId]:
    """The identifiers *item* shows, each in full."""
    ids: list[VulnerabilityItemId] = []
    for entry in _shown_items(getattr(item, "ids", None)):
        system_name = _shown_text(getattr(entry, "system_name", None))
        identifier = _shown_text(getattr(entry, "identifier", None))
        if system_name is not None and identifier is not None:
            ids.append(
                VulnerabilityItemId(
                    system_name=system_name, identifier=identifier
                )
            )
    return ids


def _item_notes(item: object) -> list[dict[str, JsonValue]]:
    notes: list[dict[str, JsonValue]] = []
    for note in _shown_items(getattr(item, "vul_notes", None)):
        category = _shown(getattr(note, "category", None))
        text = _shown_text(getattr(note, "content", None))
        if category is None or text is None:
            continue
        rendered: dict[str, JsonValue] = {
            "category": str(category),
            "text": text,
        }
        for key, field in (
            ("title", "name"),
            ("audience", "intended_audience"),
        ):
            value = _shown_text(getattr(note, field, None))
            if value is not None:
                rendered[key] = value
        notes.append(rendered)
    return notes


def _disclosure_date(preview: CasePreview) -> str | None:
    """The end time of the embargo in force the preview shows, if any."""
    entry = preview_in_force_entry(preview)
    embargo = _shown(getattr(entry, "embargo", None))
    end_time = _shown(getattr(embargo, "end_time", None))
    return end_time.isoformat() if isinstance(end_time, datetime) else None


def _vulnerabilities(preview: CasePreview) -> list[dict[str, JsonValue]]:
    """Each shown vul item with anything to show, in order."""
    disclosure_date = _disclosure_date(preview)
    rendered: list[dict[str, JsonValue]] = []
    for item in _shown_items(preview.vulnerability_items):
        cve, others = csaf_cve_and_ids(_item_ids(item))
        vulnerability: dict[str, JsonValue] = {}
        if cve is not None:
            vulnerability["cve"] = cve
        if others:
            vulnerability["ids"] = [
                {"system_name": entry.system_name, "text": entry.identifier}
                for entry in others
            ]
        title = _shown_text(getattr(item, "name", None))
        if title is not None:
            vulnerability["title"] = title
        notes = _item_notes(item)
        if notes:
            vulnerability["notes"] = list[JsonValue](notes)
        references = _external_references(getattr(item, "references", None))
        if references:
            vulnerability["references"] = list[JsonValue](references)
        if not vulnerability:
            continue
        if disclosure_date is not None:
            vulnerability["disclosure_date"] = disclosure_date
        rendered.append(vulnerability)
    return rendered


@dataclass(frozen=True)
class _Act:
    """One act of the cut ledger with a CSAF meaning, read from its first
    kept entry."""

    act_id: str
    category: str
    log_index: int
    actor: str
    recipients: tuple[str, ...]
    in_reply_to: str | None
    date: str
    summary: str | None = None

    @property
    def action_id(self) -> str:
        return f"ACT-{self.log_index}"


def _read_act(entry: object) -> _Act | None:
    """The act *entry* records, or ``None`` when it has no CSAF meaning or
    shows too little to be an action: no act id, actor or time."""
    semantic_type = str(_shown(getattr(entry, "semantic_type", None)) or "")
    category = ACTION_CATEGORIES.get(semantic_type)
    payload = _shown(getattr(entry, "payload_snapshot", None))
    if category is None or not isinstance(payload, dict):
        return None
    act_id = _shown_text(payload.get("id")) or _shown_text(
        getattr(entry, "log_object_id", None)
    )
    log_index = _shown(getattr(entry, "log_index", None))
    actor = named_id(payload.get("actor"))
    date = _act_date(
        payload.get("published"), _shown(getattr(entry, "published", None))
    )
    if (
        act_id is None
        or actor is None
        or date is None
        or not isinstance(log_index, int)
    ):
        return None
    # CSAF forbids one entity as both actor and recipient (test 6.1.64.4).
    recipients = tuple(
        recipient
        for recipient in (
            named_id(value) for value in _as_list(payload.get("to"))
        )
        if recipient is not None and recipient != actor
    )
    return _Act(
        act_id=act_id,
        category=category,
        log_index=log_index,
        actor=actor,
        recipients=recipients,
        in_reply_to=named_id(payload.get("inReplyTo")),
        date=date,
        summary=ACTION_SUMMARIES.get(semantic_type),
    )


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _act_date(claimed: object, committed: object) -> str | None:
    """The act's claimed ``published`` time, else its commit stamp.

    The crosswalk takes the time the sender gives for the act (CLP-15-004);
    an entry whose snapshot states none falls back to the stamp the
    CASE_MANAGER committed it at.
    """
    for value in (claimed, committed):
        try:
            return _AWARE.validate_python(value).isoformat()
        except ValidationError:
            continue
    return None


def _acts(preview: CasePreview) -> list[_Act]:
    """The acts of the cut ledger with a CSAF meaning, one per act, in log
    order; an act's later entries join its first."""
    acts: dict[str, _Act] = {}
    for entry in _shown_items(preview.ledger_entries):
        act = _read_act(entry)
        if act is not None:
            acts.setdefault(act.act_id, act)
    return list(acts.values())


def _participants(preview: CasePreview) -> dict[str, tuple[str, str]]:
    """The party category and name of each actor among the participants the
    preview shows; an actor the preview does not show is ``other`` and
    named by its id."""
    parties: dict[str, tuple[str, str]] = {}
    for participant in _shown_items(preview.case_participants):
        actor = _shown_text(getattr(participant, "attributed_to", None))
        if actor is None:
            continue
        held = _shown(getattr(participant, "case_roles", None))
        roles = [
            role
            for role in (held if isinstance(held, list) else [])
            if isinstance(role, CVDRole)
        ]
        name = _shown_text(getattr(participant, "name", None)) or actor
        parties[actor] = (role_category(roles), name)
    return parties


def _involvement(preview: CasePreview) -> dict[str, JsonValue] | None:
    """The coordination timeline of the cut ledger; ``None`` when no act
    maps, because its lists may not be empty."""
    acts = _acts(preview)
    if not acts:
        return None
    parties = _participants(preview)
    entity_ids: dict[str, str] = {}

    def entity(actor: str) -> str:
        return entity_ids.setdefault(actor, f"EID-{len(entity_ids) + 1}")

    by_act = {act.act_id: act.action_id for act in acts}
    actions: list[JsonValue] = []
    for act in acts:
        action: dict[str, JsonValue] = {
            "acting_entity_refs": [entity(act.actor)],
            "action_id": act.action_id,
            "category": act.category,
            "date": act.date,
            "status": "completed",
        }
        if act.recipients:
            action["receiving_entity_refs"] = [
                entity(recipient) for recipient in act.recipients
            ]
        if act.summary is not None:
            action["summary"] = act.summary
        if act.in_reply_to in by_act:
            action["referenced_action_ids"] = [by_act[act.in_reply_to]]
        actions.append(action)
    entities: list[JsonValue] = []
    for actor, entity_id in entity_ids.items():
        category, name = parties.get(actor, ("other", actor))
        entities.append(
            {"category": category, "entity_id": entity_id, "name": name}
        )
    return {"actions": actions, "entities": entities}


def _sections(
    preview: CasePreview, inputs: ProjectionInputs
) -> Iterator[tuple[str, JsonValue]]:
    """The optional ``document`` sections the preview gives a value."""
    notes = _notes(preview)
    if notes:
        yield "notes", list[JsonValue](notes)
    acknowledgments = _acknowledgments(inputs)
    if acknowledgments:
        yield "acknowledgments", list[JsonValue](acknowledgments)
    involvement = _involvement(preview)
    if involvement is not None:
        yield "involvement", involvement


def render_csaf(
    cut: ProjectionCut,
    inputs: ProjectionInputs,
    *,
    category: CsafCategory,
) -> dict[str, JsonValue]:
    """Render *cut* as a CSAF 2.1 document.

    Reads only *cut*, *inputs* and *category*, which the call site passes
    (ADR-0219).  The preview's ``id`` is the
    case's, as both projection profiles include it, and its distribution
    label and identity name the profile that cut it.  The result has been
    checked by the generated models, written as JSON with no unset or
    ``None`` member.

    Raises:
        VultronValidationError: When the preview shows no ledger position,
            so the document has no identity, or the projecting actor's id
            has no origin.
        pydantic.ValidationError: When the document the preview gives does
            not pass the generated models, which is a defect here.
    """
    preview = cut.preview
    position = _Position(preview)
    case_id = preview.id_
    references: list[JsonValue] = [
        _self_reference(case_id, position),
        *_external_references(preview.case_references),
    ]
    document: dict[str, JsonValue] = {
        "category": category,
        "csaf_version": CSAF_21_VERSION,
        "distribution": {"tlp": {"label": cut.distribution.value}},
        "publisher": _publisher(inputs.projecting_actor),
        "references": references,
        "title": _shown_text(preview.name) or f"Vultron case {case_id}",
        "tracking": _tracking(cut, inputs, position),
        **dict(_sections(preview, inputs)),
    }
    data: dict[str, JsonValue] = {
        "$schema": CSAF_21_SCHEMA,
        "document": document,
    }
    vulnerabilities = _vulnerabilities(preview)
    if vulnerabilities:
        data["vulnerabilities"] = list[JsonValue](vulnerabilities)
    parsed = CommonSecurityAdvisoryFramework.model_validate(data)
    rendered: dict[str, JsonValue] = parsed.model_dump(
        mode="json", by_alias=True, exclude_unset=True
    )
    return rendered


__all__ = [
    "ACKNOWLEDGMENTS_DIGEST_LENGTH",
    "ACTION_CATEGORIES",
    "ACTION_SUMMARIES",
    "CsafCategory",
    "acknowledgments_digest",
    "render_csaf",
    "role_category",
    "tracking_id",
]
