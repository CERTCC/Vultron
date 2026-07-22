#!/usr/bin/env python
"""
Provides Case Status objects for the Vultron ActivityStreams Vocabulary.
"""

# pyright: reportGeneralTypeIssues=false

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from typing import TypeAlias, cast

from pydantic import Field, field_serializer, field_validator, model_validator

from vultron.core.models.case_status import CaseStatus as CoreCaseStatus
from vultron.core.models.participant_status import (
    ParticipantStatus as CoreParticipantStatus,
    coerce_cvd_roles,
)
from vultron.core.models.dimensions import (
    EmDimension,
    PecDimension,
    PxaDimension,
    RmDimension,
    VfdDimension,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.core.models.base import NonEmptyString
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.vocab.base.links import ActivityStreamRef, as_Link
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.objects.base import (
    VultronAS2Object,
    _scalar_ref_id_or_value,
)


def _coerce_em(v: object) -> EM:
    if isinstance(v, EM):
        return v
    if isinstance(v, str):
        if v in EM.__members__:
            return EM[v]
        return EM(v)
    return EM.NO_EMBARGO


def _coerce_pxa(v: object) -> CS_pxa:
    if isinstance(v, CS_pxa):
        return v
    if isinstance(v, str):
        return CS_pxa[v]
    return CS_pxa.pxa


def _coerce_rm(v: object) -> RM:
    if isinstance(v, RM):
        return v
    if isinstance(v, str):
        return RM[v]
    return RM.START


def _coerce_vfd(v: object) -> CS_vfd:
    if isinstance(v, CS_vfd):
        return v
    if isinstance(v, str):
        return CS_vfd[v]
    return CS_vfd.vfd


def _coerce_pec_or_none(v: object) -> PEC | None:
    if v is None:
        return None
    if isinstance(v, PEC):
        return v
    if isinstance(v, str):
        return PEC[v]
    return None


class as_CaseStatus(VultronAS2Object):
    """
    Represents the case-level (global, participant-agnostic) status of a VulnerabilityCase.
    """

    type_: VO_type = Field(
        default=VO_type.CASE_STATUS,
        validation_alias="type",
        serialization_alias="type",
    )

    context: NonEmptyString | None = None  # Case ID goes here
    em_state: EM = EM.NO_EMBARGO
    pxa_state: CS_pxa = CS_pxa.pxa

    @field_serializer("em_state")
    def serialize_em_state(self, em_state: EM) -> str:
        return em_state.name

    @field_serializer("pxa_state")
    def serialize_pxa_state(self, pxa_state: CS_pxa) -> str:
        return pxa_state.name

    @model_validator(mode="before")
    @classmethod
    def _migrate_core_dimension_format(cls, data: object) -> object:
        """Map core dimension-object format (``em: {state: ...}``) to flat wire fields."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if (
            "em" in data
            and isinstance(data["em"], dict)
            and "em_state" not in data
        ):
            data["em_state"] = data.pop("em", {}).get("state")
        if (
            "pxa" in data
            and isinstance(data["pxa"], dict)
            and "pxa_state" not in data
        ):
            data["pxa_state"] = data.pop("pxa", {}).get("state")
        return data

    @field_validator("em_state", mode="before")
    @classmethod
    def validate_em_state(cls, v: object) -> EM:
        return _coerce_em(v)

    @field_validator("pxa_state", mode="before")
    @classmethod
    def validate_pxa_state(cls, v: object) -> CS_pxa:
        return _coerce_pxa(v)

    @model_validator(mode="after")
    def set_name(self) -> "as_CaseStatus":
        if self.name is None:
            self.name = " ".join([self.em_state.name, self.pxa_state.name])
        return self

    @classmethod
    def from_core(cls, core_obj: CoreCaseStatus) -> "as_CaseStatus":
        # Project dimension objects to flat EM/PXA enum fields for wire format.
        return cast(
            "as_CaseStatus",
            cls.model_validate(
                {
                    "id": core_obj.id_,
                    "type": VO_type.CASE_STATUS,
                    "context": core_obj.context,
                    "attributed_to": core_obj.attributed_to,
                    "em_state": core_obj.em.state.name,
                    "pxa_state": core_obj.pxa.state.name,
                }
            ),
        )

    def to_core(self) -> CoreCaseStatus:
        data = self._to_core_data()
        data["attributed_to"] = _scalar_ref_id_or_value(
            data.get("attributed_to")
        )
        data["context"] = _scalar_ref_id_or_value(data.get("context"))
        # Map wire flat fields to dimension objects for the core model.
        em_raw = data.pop("em_state", None)
        pxa_raw = data.pop("pxa_state", None)
        data["em"] = EmDimension(state=_coerce_em(em_raw))
        data["pxa"] = PxaDimension(state=_coerce_pxa(pxa_raw))
        return CoreCaseStatus.model_validate(data)


as_CaseStatusRef: TypeAlias = ActivityStreamRef[as_CaseStatus]


class as_ParticipantStatus(VultronAS2Object):
    """
    Represents the status of a participant with respect to a VulnerabilityCase (participant-specific).
    """

    type_: VO_type = Field(
        default=VO_type.PARTICIPANT_STATUS,
        validation_alias="type",
        serialization_alias="type",
    )

    context: (
        as_Object | as_Link | str
    )  # pyright: ignore[reportGeneralTypeIssues]
    rm_state: RM = RM.START
    vfd_state: CS_vfd = CS_vfd.vfd
    case_engagement: bool = True
    embargo_adherence: bool = True
    em_consent_state: PEC | None = Field(
        default=None,
        validation_alias="emConsentState",
        serialization_alias="emConsentState",
    )
    cvd_role: list[CVDRole] = Field(
        default_factory=lambda: [CVDRole.OTHER],
        validation_alias="cvdRole",
        serialization_alias="cvdRole",
    )
    tracking_id: NonEmptyString | None = None
    case_status: as_CaseStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_core_dimension_format(cls, data: object) -> object:
        """Map core dimension-object format back to flat wire fields on round-trip."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if (
            "rm" in data
            and isinstance(data["rm"], dict)
            and "rm_state" not in data
        ):
            data["rm_state"] = data.pop("rm", {}).get("state")
        if (
            "vfd" in data
            and isinstance(data["vfd"], dict)
            and "vfd_state" not in data
        ):
            data["vfd_state"] = data.pop("vfd", {}).get("state")
        if (
            "consent" in data
            and isinstance(data["consent"], dict)
            and "emConsentState" not in data
            and "em_consent_state" not in data
        ):
            data["emConsentState"] = data.pop("consent", {}).get("state")
        return data

    @field_serializer("rm_state")
    def serialize_rm_state(self, rm_state: RM) -> str:
        return rm_state.name

    @field_serializer("vfd_state")
    def serialize_vfd_state(self, vfd_state: CS_vfd) -> str:
        return vfd_state.name

    @field_validator("rm_state", mode="before")
    @classmethod
    def validate_rm_state(cls, v: object) -> RM:
        return _coerce_rm(v)

    @field_validator("vfd_state", mode="before")
    @classmethod
    def validate_vfd_state(cls, v: object) -> CS_vfd:
        return _coerce_vfd(v)

    @field_validator("em_consent_state", mode="before")
    @classmethod
    def validate_em_consent_state(cls, v: object) -> PEC | None:
        return _coerce_pec_or_none(v)

    @field_validator("cvd_role", mode="before")
    @classmethod
    def validate_cvd_role(cls, v: object) -> list[CVDRole]:
        return coerce_cvd_roles(v)

    @field_serializer("cvd_role")
    def serialize_cvd_role(self, cvd_role: list[CVDRole]) -> list[str]:
        return [role.name for role in cvd_role]

    @model_validator(mode="after")
    def set_name(self) -> "as_ParticipantStatus":
        if self.name is None:
            parts = [self.rm_state.name, self.vfd_state.name]
            if self.case_status is not None:
                if self.case_status.name is not None:
                    parts.append(self.case_status.name)
            self.name = " ".join(parts)
        return self

    @classmethod
    def from_core(
        cls, core_obj: CoreParticipantStatus
    ) -> "as_ParticipantStatus":
        # Project dimension objects to flat enum fields for wire format.
        consent_state = (
            core_obj.consent.state if core_obj.consent is not None else None
        )
        wire_data: dict = {
            "id": core_obj.id_,
            "type": VO_type.PARTICIPANT_STATUS,
            "context": core_obj.context,
            "attributed_to": core_obj.attributed_to,
            "rm_state": core_obj.rm.state.name,
            "vfd_state": core_obj.vfd.state.name,
            "case_engagement": core_obj.case_engagement,
            "embargo_adherence": core_obj.embargo_adherence,
            "emConsentState": (
                consent_state.name if consent_state is not None else None
            ),
            "cvdRole": [r.name for r in core_obj.cvd_role],
            "tracking_id": core_obj.tracking_id,
        }
        if core_obj.case_status is not None:
            wire_data["case_status"] = as_CaseStatus.from_core(
                core_obj.case_status
            )
        return cast("as_ParticipantStatus", cls.model_validate(wire_data))

    def to_core(self) -> CoreParticipantStatus:
        data = self._to_core_data()
        data["attributed_to"] = _scalar_ref_id_or_value(
            data.get("attributed_to")
        )
        data["context"] = _scalar_ref_id_or_value(data.get("context"))
        # Map wire flat fields to dimension objects for the core model.
        rm_raw = data.pop("rm_state", None)
        vfd_raw = data.pop("vfd_state", None)
        pec_raw = data.pop("em_consent_state", None)
        data["rm"] = RmDimension(state=_coerce_rm(rm_raw))
        data["vfd"] = VfdDimension(state=_coerce_vfd(vfd_raw))
        pec_coerced = _coerce_pec_or_none(pec_raw)
        data["consent"] = (
            PecDimension(state=pec_coerced)
            if pec_coerced is not None
            else None
        )
        # Convert embedded CaseStatus wire object (or its serialised dict) to
        # CoreCaseStatus so em and pxa cross the boundary.
        wire_case_status = data.get("case_status")
        if isinstance(wire_case_status, as_CaseStatus):
            data["case_status"] = wire_case_status.to_core()
        elif isinstance(wire_case_status, dict):
            cs_obj = as_CaseStatus.model_validate(wire_case_status)
            data["case_status"] = cs_obj.to_core()
        else:
            data["case_status"] = None
        return CoreParticipantStatus.model_validate(data)


as_ParticipantStatusRef: TypeAlias = ActivityStreamRef[as_ParticipantStatus]


def main() -> None:
    cs = as_CaseStatus()
    print(f"### {cs.type_} ###")
    print()
    print(cs.to_json(indent=2))
    print()
    print()

    ps = as_ParticipantStatus(
        attributed_to="foo",
        context="bar",
        rm_state=RM.RECEIVED,
        vfd_state=CS_vfd.Vfd,
        case_status=cs,
    )
    print(f"### {ps.type_} ###")
    print()
    print(ps.to_json(indent=2))
    print()
    print()


if __name__ == "__main__":
    main()
