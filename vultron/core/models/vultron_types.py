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

"""Domain Pydantic types used by core/behaviors/ BT nodes.

These types replace direct AS2 wire imports (VulnerabilityCase, CaseActor,
VendorParticipant, CreateCaseActivity, ParticipantStatus, VulnerabilityReport) in
the core behavior-tree layer.

Each type carries:

- ``as_id``: auto-generated ``urn:uuid:`` identifier
- ``as_type``: string matching the wire-layer AS2 type name so that
  DataLayer round-trips (store then read) continue to work unchanged.
  ``object_to_record`` uses ``as_type`` as the TinyDB table name, and
  ``find_in_vocabulary(as_type)`` locates the corresponding wire class
  for deserialisation.

Types mirror the Vultron-specific fields of their wire counterparts, using
clean Python types (``str`` IDs for cross-references, standard enums) rather
than AS2-specific field annotations.  AS2 boilerplate fields (``as_context``,
``preview``, ``media_type``, ``replies``, ``url``, ``generator``, etc.) are
intentionally omitted.

An outbound serializer in ``vultron/wire/as2/serializer.py`` converts these
domain types to full AS2 wire objects when needed (adapter layer only).

Per architecture notes in ``notes/domain-model-separation.md`` and the
P65-6b task in ``plan/IMPLEMENTATION_PLAN.md``.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
)

from vultron.bt.embargo_management.states import EM
from vultron.bt.report_management.states import RM
from vultron.bt.roles.states import CVDRoles
from vultron.case_states.states import CS_pxa, CS_vfd


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_urn() -> str:
    return f"urn:uuid:{uuid.uuid4()}"


class VultronCaseEvent(BaseModel):
    """Domain representation of a case event log entry.

    Mirrors ``CaseEvent`` from ``vultron.wire.as2.vocab.objects.case_event``
    using identical field names for DataLayer round-trip compatibility.
    """

    object_id: str
    event_type: str
    received_at: datetime = Field(default_factory=_now_utc)


class VultronCaseStatus(BaseModel):
    """Domain representation of a case status snapshot.

    Mirrors the Vultron-specific fields of ``CaseStatus``.
    ``as_type`` is ``"CaseStatus"`` to match the wire value.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "CaseStatus"
    name: str | None = None
    context: str | None = None
    attributed_to: Any | None = None
    em_state: EM = EM.EMBARGO_MANAGEMENT_NONE
    pxa_state: CS_pxa = CS_pxa.pxa


class VultronParticipantStatus(BaseModel):
    """Domain representation of a participant RM-state status record.

    Mirrors the Vultron-specific fields of ``ParticipantStatus``.
    ``as_type`` is ``"ParticipantStatus"`` to match the wire value.

    ``context`` (case ID) is required, matching the wire type's constraint.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "ParticipantStatus"
    name: str | None = None
    context: str
    attributed_to: Any | None = None
    rm_state: RM = RM.START
    vfd_state: CS_vfd = CS_vfd.vfd
    case_engagement: bool = True
    embargo_adherence: bool = True
    tracking_id: str | None = None
    case_status: str | None = None


class VultronParticipant(BaseModel):
    """Domain representation of a case participant.

    Mirrors the Vultron-specific fields of ``CaseParticipant`` and its
    subclasses (VendorParticipant, etc.).
    ``as_type`` is ``"CaseParticipant"`` to match the wire value shared by all
    ``CaseParticipant`` subclasses.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "CaseParticipant"
    name: str | None = None
    attributed_to: Any | None = None
    context: str | None = None
    case_roles: list[CVDRoles] = Field(default_factory=list)
    participant_statuses: list[VultronParticipantStatus] = Field(
        default_factory=list
    )
    accepted_embargo_ids: list[str] = Field(default_factory=list)
    participant_case_name: str | None = None

    @field_serializer("case_roles")
    def _serialize_case_roles(self, value: list[CVDRoles]) -> list[str]:
        return [role.name for role in value]

    @field_validator("case_roles", mode="before")
    @classmethod
    def _validate_case_roles(cls, value: list) -> list:
        if isinstance(value, list) and value and isinstance(value[0], str):
            return [CVDRoles[name] for name in value]
        return value


class VultronOutbox(BaseModel):
    """Minimal outbox representation for domain actor types."""

    items: list[str] = Field(default_factory=list)


class VultronCaseActor(BaseModel):
    """Domain representation of a CaseActor service.

    Mirrors the Vultron-specific fields of ``CaseActor`` (which inherits
    ``as_Service``).  The ``outbox`` field carries the actor's outgoing
    activity IDs and is required so that ``UpdateActorOutbox`` can append
    to it via ``save_to_datalayer``.
    ``as_type`` is ``"Service"`` to match ``CaseActor``'s wire value.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "Service"
    name: str | None = None
    attributed_to: Any | None = None
    context: Any | None = None
    outbox: VultronOutbox = Field(default_factory=VultronOutbox)


class VultronOffer(BaseModel):
    """Domain representation of an Offer activity.

    Mirrors the essential fields of ``as_Offer``.
    ``as_type`` is ``"Offer"`` to match the wire value.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "Offer"
    actor: str | None = None
    object: Any | None = None
    to: Any | None = None
    target: Any | None = None


class VultronAccept(BaseModel):
    """Domain representation of an Accept activity.

    Mirrors the essential fields of ``as_Accept``.
    ``as_type`` is ``"Accept"`` to match the wire value.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "Accept"
    actor: str | None = None
    object: Any | None = None


class VultronCreateCaseActivity(BaseModel):
    """Domain representation of a Create(Case) activity.

    Mirrors the essential fields of ``as_CreateCase``.
    ``as_type`` is ``"Create"`` to match the wire value.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "Create"
    actor: str | None = None
    object: str | None = None


class VultronReport(BaseModel):
    """Domain representation of a vulnerability report.

    Mirrors the Vultron-specific fields of ``VulnerabilityReport``.
    Policy implementations receive this type when evaluating credibility and
    validity.
    ``as_type`` is ``"VulnerabilityReport"`` to match the wire value.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "VulnerabilityReport"
    name: str | None = None
    summary: str | None = None
    content: Any | None = None
    url: str | None = None
    media_type: str | None = None
    attributed_to: Any | None = None
    context: Any | None = None
    published: datetime | None = None
    updated: datetime | None = None


def _init_case_statuses() -> list:
    return [VultronCaseStatus()]


class VultronCase(BaseModel):
    """Domain representation of a vulnerability case.

    Mirrors the Vultron-specific fields of ``VulnerabilityCase``.  Cross-
    references to related objects are stored as ``str`` ID values, which are
    valid members of the corresponding wire-type union fields (e.g.
    ``VulnerabilityReportRef``, ``CaseParticipantRef``), ensuring DataLayer
    round-trip compatibility.

    ``as_type`` is ``"VulnerabilityCase"`` so that TinyDB stores this in the
    same table as wire-created cases and ``record_to_object`` can round-trip
    it via the wire vocabulary registry.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "VulnerabilityCase"
    name: str | None = None
    summary: str | None = None
    content: str | None = None
    url: str | None = None
    context: Any | None = None
    attributed_to: Any | None = None
    published: datetime | None = None
    updated: datetime | None = None
    case_participants: list[str | VultronParticipant] = Field(
        default_factory=list
    )
    actor_participant_index: dict[str, str] = Field(default_factory=dict)
    vulnerability_reports: list[str] = Field(default_factory=list)
    case_statuses: list[str | VultronCaseStatus] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    active_embargo: str | None = None
    proposed_embargoes: list[str] = Field(default_factory=list)
    case_activity: list[str] = Field(default_factory=list)
    events: list[VultronCaseEvent] = Field(default_factory=list)
    parent_cases: list[str] = Field(default_factory=list)
    child_cases: list[str] = Field(default_factory=list)
    sibling_cases: list[str] = Field(default_factory=list)


class VultronActivity(BaseModel):
    """Domain representation of an AS2 activity for DataLayer storage.

    ``as_type`` is required and must be set to the actual activity type
    (e.g. ``"Offer"``, ``"Accept"``, ``"Invite"``, ``"Leave"``, ``"Read"``).

    Field names match the wire-layer ``as_Activity`` internal names so that
    a stored ``VultronActivity`` can be round-tripped through
    ``record_to_object`` and deserialized as the appropriate AS2 activity
    subclass.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str
    actor: str | None = None
    as_object: str | None = None
    target: str | None = None
    origin: str | None = None
    context: str | None = None
    in_reply_to: str | None = None


class VultronNote(BaseModel):
    """Domain representation of a Note.

    ``as_type`` is ``"Note"`` to match the wire value.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "Note"
    name: str | None = None
    summary: str | None = None
    content: str | None = None
    url: str | None = None
    attributed_to: str | None = None
    context: str | None = None


class VultronEmbargoEvent(BaseModel):
    """Domain representation of an EmbargoEvent.

    ``as_type`` is ``"Event"`` to match the wire value (EmbargoEvent inherits
    as_Event and does not override as_type).
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "Event"
    name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    published: datetime | None = None
    updated: datetime | None = None
    context: str | None = None


__all__ = [
    "VultronAccept",
    "VultronActivity",
    "VultronCase",
    "VultronCaseActor",
    "VultronCaseEvent",
    "VultronCaseStatus",
    "VultronCreateCaseActivity",
    "VultronEmbargoEvent",
    "VultronNote",
    "VultronOffer",
    "VultronOutbox",
    "VultronParticipant",
    "VultronParticipantStatus",
    "VultronReport",
]
