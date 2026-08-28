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
    DDimension,
    EmDimension,
    PecDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.core.models.base import NonEmptyString
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.vocab.base.links import ActivityStreamRef, as_Link
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.objects.base import (
    VultronAS2Object,
    _scalar_ref_id_or_value,
    _strip_core_context,
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


def _coerce_vf_or_none(v: object) -> CS_vf | None:
    if v is None:
        return None
    if isinstance(v, CS_vf):
        return v
    if isinstance(v, str):
        return CS_vf[v]
    return None


def _coerce_d_or_none(v: object) -> CS_d | None:
    if v is None:
        return None
    if isinstance(v, CS_d):
        return v
    if isinstance(v, str):
        return CS_d[v]
    return None


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
        data = core_obj.model_dump(mode="json")
        _strip_core_context(data)
        # Project dimension dicts to the flat em_state/pxa_state wire fields.
        em_dim = data.pop("em", {})
        pxa_dim = data.pop("pxa", {})
        data["em_state"] = (
            em_dim.get("state") if isinstance(em_dim, dict) else em_dim
        )
        data["pxa_state"] = (
            pxa_dim.get("state") if isinstance(pxa_dim, dict) else pxa_dim
        )
        return cast("as_CaseStatus", cls.model_validate(data))

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
    vf_state: CS_vf | None = None
    d_state: CS_d | None = None
    case_engagement: bool = True
    embargo_adherence: bool = False
    em_consent_state: PEC | None = Field(
        default=None,
        validation_alias="emConsentState",
        serialization_alias="emConsentState",
    )
    cvd_role: list[CVDRole] = Field(
        default_factory=lambda: [CVDRole.OBSERVER],
        validation_alias="cvdRole",
        serialization_alias="cvdRole",
    )
    tracking_id: NonEmptyString | None = None
    case_status: as_CaseStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_retired_vfd_keys(cls, data: object) -> object:
        """Reject wire messages that still use the retired vfd_state/vfdState key.

        Sending vfd_state after the VF/D split is a protocol error (SDO-03-005):
        silently dropping the data would cause silent state-loss.
        """
        if isinstance(data, dict):
            if "vfd_state" in data or "vfdState" in data:
                raise ValueError(
                    "vfd_state/vfdState is retired (ADR-0075). Use vf_state"
                    " for vendor participants and d_state for deployer"
                    " participants instead."
                )
        return data

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
            "vf" in data
            and isinstance(data["vf"], dict)
            and "vf_state" not in data
        ):
            data["vf_state"] = data.pop("vf", {}).get("state")
        if (
            "d" in data
            and isinstance(data["d"], dict)
            and "d_state" not in data
        ):
            data["d_state"] = data.pop("d", {}).get("state")
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

    @field_serializer("vf_state")
    def serialize_vf_state(self, vf_state: CS_vf | None) -> str | None:
        return vf_state.name if vf_state is not None else None

    @field_serializer("d_state")
    def serialize_d_state(self, d_state: CS_d | None) -> str | None:
        return d_state.name if d_state is not None else None

    @field_validator("rm_state", mode="before")
    @classmethod
    def validate_rm_state(cls, v: object) -> RM:
        return _coerce_rm(v)

    @field_validator("vf_state", mode="before")
    @classmethod
    def validate_vf_state(cls, v: object) -> CS_vf | None:
        return _coerce_vf_or_none(v)

    @field_validator("d_state", mode="before")
    @classmethod
    def validate_d_state(cls, v: object) -> CS_d | None:
        return _coerce_d_or_none(v)

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
            parts = [self.rm_state.name]
            if self.vf_state is not None:
                parts.append(self.vf_state.name)
            if self.d_state is not None:
                parts.append(self.d_state.name)
            if self.case_status is not None:
                if self.case_status.name is not None:
                    parts.append(self.case_status.name)
            self.name = " ".join(parts)
        return self

    @classmethod
    def from_core(
        cls, core_obj: CoreParticipantStatus
    ) -> "as_ParticipantStatus":
        data = core_obj.model_dump(mode="json")
        _strip_core_context(data)
        # _migrate_core_dimension_format handles rm/vf/d/consent dim-dict → flat.
        # case_status needs explicit conversion so em/pxa dims cross the boundary.
        data.pop("case_status", None)
        if core_obj.case_status is not None:
            data["case_status"] = as_CaseStatus.from_core(core_obj.case_status)
        return cast("as_ParticipantStatus", cls.model_validate(data))

    def to_core(self) -> CoreParticipantStatus:
        data = self._to_core_data()
        data["attributed_to"] = _scalar_ref_id_or_value(
            data.get("attributed_to")
        )
        data["context"] = _scalar_ref_id_or_value(data.get("context"))
        # Map wire flat fields to dimension objects for the core model.
        rm_raw = data.pop("rm_state", None)
        vf_raw = data.pop("vf_state", None)
        d_raw = data.pop("d_state", None)
        pec_raw = data.pop("em_consent_state", None)
        data["rm"] = RmDimension(state=_coerce_rm(rm_raw))
        vf_coerced = _coerce_vf_or_none(vf_raw)
        data["vf"] = (
            VfDimension(state=vf_coerced) if vf_coerced is not None else None
        )
        d_coerced = _coerce_d_or_none(d_raw)
        data["d"] = (
            DDimension(state=d_coerced) if d_coerced is not None else None
        )
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
        vf_state=CS_vf.Vf,
        case_status=cs,
    )
    print(f"### {ps.type_} ###")
    print()
    print(ps.to_json(indent=2))
    print()
    print()


if __name__ == "__main__":
    main()
