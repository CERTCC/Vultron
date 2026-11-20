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
"""The case's preview, which a stub Invite carries (ADR-0205, ADR-0217).

The stub Invite's ``object`` is a typed reference to the case,
``{id, type, preview}``, and :class:`CasePreview` is its ``preview``: what an
invitee decides on before it may see the case (CM-17-010, MV-10-012).  A
preview is not the case (MV-10-013): an invitee never holds it as a record,
and no replica is seeded from it.

The preview is a loose form of the case (ADR-0217): the case's fields under
the case's names, every one optional, and any of them, at any depth, may hold
a :class:`~vultron.core.models.redacted.Redacted` marker.  It is written by
hand; every object nested in it takes the loose form
:func:`~vultron.core.models.preview_object.loose_form` derives from its class.
It is not a subclass of the case, so a full case is never a preview.

:class:`CasePreview` is one class on both sides of the wire boundary
(ARCH-25-003, ADR-0099): ``as_CasePreview`` is its wire alias.  The extractor
carries a received previewed reference into core as a
:class:`PreviewedCaseReference`, which names the case by its own ``id`` and
holds the preview, so a consumer reads the case from the reference's ``id``
and what the invitee decides on from the preview.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import Field, ValidationInfo, model_validator

from vultron.core.models._helpers import INBOUND_CONTEXT_KEY, new_object_id
from vultron.core.models.base import (
    CoreObject,
    NonEmptyString,
    PropertyValueKind,
    vultron_property,
)
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_preview_envelope import (
    invitation_preview_faults,
    preview_current_status,
    preview_em_state,
    preview_in_force_entry,
)
from vultron.core.models.case_preview_profile import (
    CasePreviewProfile,
    cut_case,
)
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.preview_object import (
    PreviewObject,
    PreviewValue,
    loose_form,
)
from vultron.core.models.redacted import Redactable
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_item import VulnerabilityItem
from vultron.errors import VultronActivityConstructionError

# The loose forms the preview's fields hold.  A type checker reads each as the
# loose base it derives from; at run time each is the derived form.
if TYPE_CHECKING:
    # A projection profile names the acts it keeps by their semantics, whose
    # module reads this one, so the class is named here for checking only.
    from vultron.core.models.case_projection_profile import ProjectionProfile

    CaseLedgerEntryPreview = PreviewObject
    CaseParticipantPreview = PreviewObject
    CaseReferencePreview = PreviewObject
    CaseStatusPreview = PreviewObject
    EmbargoEventPreview = PreviewObject
    EmbargoRegisterEntryPreview = PreviewValue
    LedgerPositionPreview = PreviewValue
    VulnerabilityItemPreview = PreviewObject
    VulnerabilityReportPreview = PreviewObject
else:
    CaseLedgerEntryPreview = loose_form(CaseLedgerEntry)
    CaseParticipantPreview = loose_form(CaseParticipant)
    CaseReferencePreview = loose_form(CaseReference)
    CaseStatusPreview = loose_form(CaseStatus)
    EmbargoEventPreview = loose_form(EmbargoEvent)
    EmbargoRegisterEntryPreview = loose_form(EmbargoRegisterEntry)
    LedgerPositionPreview = loose_form(LedgerPosition)
    VulnerabilityItemPreview = loose_form(VulnerabilityItem)
    VulnerabilityReportPreview = loose_form(VulnerabilityReport)


def _case_property(name: str) -> Any:
    """The case's own description of its field *name*, for the same field
    of the preview, so both name one Vultron property."""
    return VulnerabilityCase.model_fields[name].json_schema_extra


#: The case's id lists, as a preview shows them.
_RedactableIds = Redactable[list[Redactable[NonEmptyString]]]

#: The Vultron property ``ledgerEntries``: the one preview field that is not
#: a case field (ADR-0219).
LEDGER_ENTRIES_PROPERTY = vultron_property(
    "The case ledger entries a case preview cut for a projection keeps, in "
    "log order, each cut by the same profile; a preview may hold an "
    "incomplete ledger",
    PropertyValueKind.LIST,
)


class CasePreview(PreviewObject):
    """The case's preview: what an invitee decides on (CM-17-010, ADR-0217).

    The stub Invite's ``object`` is a typed reference to the case,
    ``{id, type, preview}``, and this is its ``preview``.  The case is named
    by the reference's own ``id``, so the preview names no case of its own
    (ADR-0205 § "The stub Invite's object is a previewed reference to the
    case"):

    - ``type`` is ``CasePreview``, the case's defined preview (MV-10-012).
    - ``id`` is the preview's own, minted like any object's (OID-01-013).
      No reader derives anything from it.
    - ``summary`` is the required human-readable context (CM-17-010, MV-10-001).
      The sender chooses it (CM-17-020): the case's ``stub_summary``,
      written for the invitee rather than for participants.  A receiver
      MUST refuse a preview whose ``summary`` is absent or blank.  On the
      inbound parse path, absence triggers :meth:`_refuse_absent_summary`.
      It is the one case field a marker may not stand in.

    Every other field is the case's field of the same name, optional, and it
    may hold a ``Redacted`` marker (MV-12-001): the sender withholds a value
    it holds (MV-12-004).  An object nested in one is held in its loose form.
    The case bookkeeping a preview never carries (the genesis hash, the
    participant and pending-proposal indexes, the case activity list and the
    owner's ``stubSummary``) is not declared, so a received one is set aside
    as an unknown key (MV-11-003).

    A preview cut for a projection (:meth:`for_projection`, ADR-0219) also
    shows the case's ``ledgerPosition``, the snapshot it is a cut of, and
    may carry ``ledgerEntries``, the ledger entries its profile keeps: the
    one preview field that is not a case field.  An invitation preview
    carries neither (CM-17-025), and :func:`invitation_preview_faults` names
    one that does.

    A sender cuts it from the case by a profile (:meth:`from_case`).  An
    invitation preview shows the Case Owner (``attributedTo``) and, while an
    embargo is in force, its terms and EM state: ``embargoRegister`` reduced
    to the in-force entry and ``caseStatuses`` to the current status
    (CM-17-002, CM-17-013).  :func:`invitation_preview_faults` names what an
    invitation preview lacks of these.

    It is permitted only as that preview (MV-10-002).  The case reference
    carrying a preview cut by :data:`~vultron.core.models.
    case_preview_profile.INVITATION_PROFILE`, with no embargo in force, is::

        {"id": "https://example.org/cases/abc",
         "type": "VulnerabilityCase",
         "preview": {
             "id": "urn:uuid:...",
             "type": "CasePreview",
             "summary": "A remote code execution vulnerability in widget.",
             "name": "Widget RCE",
             "published": "2026-08-03T00:00:00Z",
             "attributedTo": "https://example.org/actors/vendor",
             "caseStatuses": [{"type": "CaseStatus", "...": "..."}],
             "vulnerabilityItems": [{"type": "VulnerabilityItem",
                 "ids": [{"systemName": "CVE",
                          "identifier": "CVE-2026-1234"}]}],
             "caseParticipants": {"type": "Redacted"}}}
    """

    # The preview's own identity: required on a received one, as on any
    # object (MV-10-001), and minted when built here.
    _received_without_id: ClassVar[bool] = False
    id_: NonEmptyString = Field(  # type: ignore[assignment]
        default_factory=new_object_id,
        validation_alias="id",
        serialization_alias="id",
    )
    # Pinned: the type alone identifies the case's preview (MV-10-012), so a
    # preview that claims any other type is refused rather than relabelled.
    type_: Literal["CasePreview"] = Field(
        default="CasePreview",
        validation_alias="type",
        serialization_alias="type",
    )
    summary: NonEmptyString | None = None  # type: ignore[assignment]

    case_participants: (
        Redactable[list[Redactable[NonEmptyString | CaseParticipantPreview]]]
        | None
    ) = Field(
        default=None, json_schema_extra=_case_property("case_participants")
    )
    vulnerability_reports: (
        Redactable[
            list[Redactable[NonEmptyString | VulnerabilityReportPreview]]
        ]
        | None
    ) = Field(
        default=None, json_schema_extra=_case_property("vulnerability_reports")
    )
    vulnerability_items: (
        Redactable[list[Redactable[NonEmptyString | VulnerabilityItemPreview]]]
        | None
    ) = Field(
        default=None, json_schema_extra=_case_property("vulnerability_items")
    )
    case_references: (
        Redactable[list[Redactable[NonEmptyString | CaseReferencePreview]]]
        | None
    ) = Field(
        default=None, json_schema_extra=_case_property("case_references")
    )
    case_statuses: (
        Redactable[list[Redactable[NonEmptyString | CaseStatusPreview]]] | None
    ) = Field(default=None, json_schema_extra=_case_property("case_statuses"))
    notes: _RedactableIds | None = Field(
        default=None, json_schema_extra=_case_property("notes")
    )
    embargo_register: (
        Redactable[list[Redactable[EmbargoRegisterEntryPreview]]] | None
    ) = Field(
        default=None, json_schema_extra=_case_property("embargo_register")
    )
    parent_cases: _RedactableIds | None = Field(
        default=None, json_schema_extra=_case_property("parent_cases")
    )
    child_cases: _RedactableIds | None = Field(
        default=None, json_schema_extra=_case_property("child_cases")
    )
    sibling_cases: _RedactableIds | None = Field(
        default=None, json_schema_extra=_case_property("sibling_cases")
    )
    ledger_position: Redactable[LedgerPositionPreview] | None = Field(
        default=None, json_schema_extra=_case_property("ledger_position")
    )
    ledger_entries: (
        Redactable[list[Redactable[CaseLedgerEntryPreview]]] | None
    ) = Field(default=None, json_schema_extra=LEDGER_ENTRIES_PROPERTY)

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

    @classmethod
    def from_case(
        cls, case: VulnerabilityCase, profile: CasePreviewProfile
    ) -> CasePreview:
        """Cut *case*'s preview by *profile*, one field at a time (ADR-0217).

        Each case field takes its row's chosen operation
        (:func:`~vultron.core.models.case_preview_profile.cut_case`), and the
        result is checked against the envelope.

        Raises:
            VultronActivityConstructionError: When *profile* has no row for a
                case field, so the cut would have to guess; when the cut
                leaves a field the envelope requires it to show without a
                value (no ``stub_summary``, no Case Owner, or no in-force
                embargo while one is in force); when a substitution cannot be
                made (an in-force embargo held only by id, CM-17-011); or
                when the cut breaks the envelope
                (:func:`invitation_preview_faults`).
        """
        preview = cls.model_validate(cut_case(case, profile))
        faults = invitation_preview_faults(preview)
        if faults:
            raise VultronActivityConstructionError(
                f"case {case.id_!r}: the cut preview {'; '.join(faults)}"
                " (CM-17-010, MV-10-007)"
            )
        return preview

    @classmethod
    def for_projection(
        cls,
        case: VulnerabilityCase,
        ledger: Sequence[CaseLedgerEntry],
        profile: ProjectionProfile,
    ) -> CasePreview:
        """Cut *case* and its *ledger* by a projection *profile* (ADR-0219).

        Each case field takes its row's chosen operation, as
        :meth:`from_case` cuts it, and the ledger list holds the entries the
        profile keeps (:meth:`~vultron.core.models.case_projection_profile.
        ProjectionProfile.cut_ledger`).  The invitation envelope does not
        apply: the preview is rendered, never carried by a stub Invite.

        Raises:
            VultronActivityConstructionError: When a substitution cannot be
                made, such as a current status the case holds only by id.
        """
        data = cut_case(case, profile.fields)
        entries = profile.cut_ledger(ledger)
        if entries is not None:
            data["ledger_entries"] = entries
        return cls.model_validate(data)


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


def preview_embargo_id(preview: object) -> str | None:
    """The id of the embargo *preview* carries as its terms (CM-17-002).

    The embargo of the in-force entry of its ``embargoRegister``.  ``None``
    when *preview* is no case preview, carries no in-force entry, or shows
    the embargo without its id or withholds it with a marker: a withheld
    value names no embargo.
    """
    if not isinstance(preview, CasePreview):
        return None
    embargo = getattr(preview_in_force_entry(preview), "embargo", None)
    if isinstance(embargo, str):
        return embargo
    embargo_id = getattr(embargo, "id_", None)
    return embargo_id if isinstance(embargo_id, str) else None


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


__all__ = [
    "LEDGER_ENTRIES_PROPERTY",
    "CasePreview",
    "PreviewedCaseReference",
    "case_preview_of",
    "invitation_preview_faults",
    "preview_current_status",
    "preview_em_state",
    "preview_embargo_id",
    "preview_in_force_entry",
    "previewed_case_id",
]
