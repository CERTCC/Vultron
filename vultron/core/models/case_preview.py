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
"""The case's preview, which a stub Invite carries (ADR-0205).

The stub Invite's ``object`` is a typed reference to the case,
``{id, type, preview}``, and :class:`CasePreview` is its ``preview``: what an
invitee decides on before it may see the case (CM-17-010, MV-10-012).  A
preview is not the case (MV-10-013): an invitee never holds it as a record,
and no replica is seeded from it.

:class:`CasePreview` is one class on both sides of the wire boundary
(ARCH-25-003, ADR-0099): ``as_CasePreview`` is its wire alias.  The extractor
carries a received previewed reference into core as a
:class:`PreviewedCaseReference`, which names the case by its own ``id`` and
holds the preview, so a consumer reads the case from the reference's ``id``
and what the invitee decides on from the preview.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationInfo,
    field_serializer,
    model_validator,
)

from vultron.core.models._helpers import INBOUND_CONTEXT_KEY
from vultron.core.models.base import (
    CoreObject,
    NonEmptyString,
    PropertyValueKind,
    vultron_property,
)
from vultron.core.models.case_status import CASE_STATUS_PROPERTY, CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.wire_keys import input_keys, wire_key
from vultron.core.states.em import EM

#: The ``CaseStatus`` fields a preview's ``caseStatus`` keeps on the wire
#: (CM-17-010): what identifies the status object, the time it was made, and
#: its EM state.  ``published`` stays because every ``CaseStatus`` carries
#: one and a receiver refuses a status without it (CLP-15-010).  The status a
#: preview carries is built for the preview, so its other properties are class
#: defaults (``pxaState``) or derived from them (``name``) and say nothing
#: true about the case.
_PREVIEW_CASE_STATUS_FIELDS = (
    "context_",
    "id_",
    "type_",
    "context",
    "published",
    "em",
)

#: Those fields under every spelling a dump may use: the field name, its AS2
#: key and each input alias (ARCH-25-002).
_PREVIEW_CASE_STATUS_KEYS = frozenset(
    key
    for name in _PREVIEW_CASE_STATUS_FIELDS
    for key in (
        name,
        wire_key(name, CaseStatus),
        *input_keys(CaseStatus, name),
    )
)


class CasePreview(CoreObject):
    """The case's preview: what an invitee decides on (CM-17-010, ADR-0205).

    The stub Invite's ``object`` is a typed reference to the case,
    ``{id, type, preview}``, and this is its ``preview``.  The case is named
    by the reference's own ``id``, so the preview names no case of its own
    (ADR-0205 § "The stub Invite's object is a previewed reference to the
    case"):

    - ``type`` is ``CasePreview``, the case's defined preview (MV-10-012).
    - ``id`` is the preview's own, minted like any object's (OID-01-013).
      No reader derives anything from it.
    - ``summary`` is the required human-readable context (CM-17-010, MV-10-001).
      The sender chooses it: the case name MAY be used, or a deliberately less
      revealing string, since the case name can be sensitive to share with an
      invitee not yet bound by the embargo.  A receiver MUST refuse a preview
      whose ``summary`` is absent or blank.  On the inbound parse path,
      absence triggers :meth:`_refuse_absent_summary`.

    It carries nothing else about the case except, when an embargo is active,
    the terms the invitee would agree to by accepting (CM-17-002):
    ``active_embargo`` and ``case_status`` (with its EM state).  The embargo
    is an object or its id, as ActivityStreams allows; this prototype's sender
    always embeds the full ``EmbargoEvent``, since it builds no way to fetch an
    embargo by ID (CM-17-011).

    It is permitted only as that preview (MV-10-002).  Serialised with
    ``exclude_none=True`` the case reference carrying a preview with no active
    embargo is::

        {"id": "https://example.org/cases/abc",
         "type": "VulnerabilityCase",
         "preview": {
             "id": "urn:uuid:...",
             "type": "CasePreview",
             "summary": "A remote code execution vulnerability in widget."}}
    """

    # Pinned: the type alone identifies the case's preview (MV-10-012), so a
    # preview that claims any other type is refused rather than relabelled.
    type_: Literal["CasePreview"] = Field(
        default="CasePreview",
        validation_alias="type",
        serialization_alias="type",
    )
    # A preview states no time of its own; absent unless its sender gave one.
    published: datetime | None = None
    updated: datetime | None = None
    active_embargo: EmbargoEvent | NonEmptyString | None = Field(
        default=None,
        json_schema_extra=vultron_property(
            (
                "The embargo active on a case, as its case preview carries "
                "it: an EmbargoEvent or its id"
            ),
            PropertyValueKind.IRI,
        ),
    )
    case_status: CaseStatus | NonEmptyString | None = Field(
        default=None, json_schema_extra=CASE_STATUS_PROPERTY
    )

    @field_serializer("case_status", mode="wrap")
    def _serialize_embargo_state_only(
        self,
        value: Any,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """Emit only the identity, time and EM state of the ``caseStatus``.

        CM-17-013 asks for ``caseStatus.emState``.  A ``CaseStatus`` also
        carries a PXA state, and the preview's status is not read from the
        case, so that state is the class default and would tell the invitee a
        PXA state nobody observed.  The dump keeps the status's identity, its
        ``published`` time (required on every status, CLP-15-010) and its EM
        state, and drops the rest.
        """
        dumped = handler(value)
        if not isinstance(dumped, dict):
            return dumped
        return {
            key: item
            for key, item in dumped.items()
            if key in _PREVIEW_CASE_STATUS_KEYS
        }

    @model_validator(mode="before")
    @classmethod
    def _refuse_absent_summary(cls, data: Any, info: ValidationInfo) -> Any:
        """Refuse a received preview whose ``summary`` is absent (MV-10-001).

        Blank values are already refused by the ``NonEmptyString`` type.
        This validator covers the absent key, which ``NonEmptyString | None``
        otherwise admits.  It runs only on the inbound wire path
        (``parse_activity`` supplies :data:`INBOUND_CONTEXT_KEY`): a sender
        that omits the summary is at fault, and a receiver that silently
        accepts it gives the invitee no basis for consent.
        """
        if not isinstance(data, dict):
            return data
        context = info.context
        if not isinstance(context, dict) or not context.get(
            INBOUND_CONTEXT_KEY
        ):
            return data
        if data.get("summary") is None:
            raise ValueError(
                "a CasePreview MUST carry a non-empty 'summary' (MV-10-001):"
                " an absent or blank summary gives the invitee no basis for"
                " consent"
            )
        return data


class PreviewedCaseReference(CoreObject):
    """A case named by typed reference, carrying the case's preview.

    ``id_`` is the case's id and ``type_`` its type, ``VulnerabilityCase``
    (ADR-0205).  :attr:`preview` is what the invitee may see before it
    joins.  The class declares no ``Literal`` ``type_``, so ``CORE_TYPE_MAP``
    keys it on its class name, ``PreviewedCaseReference``, which no wire or
    stored ``type`` carries.  It is an in-process projection the extractor
    builds, like the bare :class:`CoreObject` it wraps an otherwise
    unmodelled object in, and is never a case: no replica is built from it
    (MV-10-013).
    """

    preview: CasePreview  # type: ignore[assignment]


def preview_em_state(preview: CasePreview) -> EM | None:
    """The case's EM state *preview*'s status carries (CM-17-013).

    A module function, not a property: a replica slot's reach is checked by
    attribute name (``test_participant_replica_slots_copy.py``), and a
    property named for the status would read as the case's own.
    """
    status = preview.case_status
    return status.em.state if isinstance(status, CaseStatus) else None


def case_preview_of(obj: object) -> CasePreview | None:
    """The preview *obj* carries when it is a previewed case reference."""
    return obj.preview if isinstance(obj, PreviewedCaseReference) else None


def previewed_case_id(obj: object) -> str | None:
    """The case *obj* names when it is a case reference carrying a preview.

    The one reader of a stub Invite's case from a recorded Invite's
    ``object``, as the store reads it back: the reference names the case by
    its own ``id`` (ADR-0205).  ``None`` for anything that carries no
    preview object, such as a whole case or an ``EmbargoEvent``.  AS2 lets
    any object's ``preview`` be a URI string; only an inline preview object
    is a case's preview (MV-10-012).
    """
    preview = getattr(obj, "preview", None)
    if preview is None or isinstance(preview, str):
        return None
    case_id = getattr(obj, "id_", None)
    return case_id if isinstance(case_id, str) and case_id else None
