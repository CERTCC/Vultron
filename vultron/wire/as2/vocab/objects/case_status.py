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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from typing import TypeAlias, cast

from pydantic import Field, field_serializer, field_validator, model_validator

from vultron.core.models.case_status import VultronCaseStatus
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.models.base import NonEmptyString
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.vocab.base.links import ActivityStreamRef, as_Link
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.objects.base import (
    VultronAS2Object,
    _scalar_ref_id_or_value,
)


class CaseStatus(VultronAS2Object):
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

    @field_validator("em_state", mode="before")
    def validate_em_state(cls, v):
        if isinstance(v, str):
            #
            if v in EM.__members__:
                return EM[v]
            return EM(v)
        return v

    @field_validator("pxa_state", mode="before")
    def validate_pxa_state(cls, v):
        if isinstance(v, str):
            return CS_pxa[v]
        return v

    @model_validator(mode="after")
    def set_name(self):
        if self.name is None:
            self.name = " ".join([self.em_state.name, self.pxa_state.name])
        return self

    @classmethod
    def from_core(cls, core_obj: VultronCaseStatus) -> "CaseStatus":
        return cast("CaseStatus", super().from_core(core_obj))

    def to_core(self) -> VultronCaseStatus:
        data = self._to_core_data()
        data["attributed_to"] = _scalar_ref_id_or_value(
            data.get("attributed_to")
        )
        data["context"] = _scalar_ref_id_or_value(data.get("context"))
        if isinstance(data.get("pxa_state"), str):
            data["pxa_state"] = CS_pxa[data["pxa_state"]]
        return VultronCaseStatus.model_validate(data)


CaseStatusRef: TypeAlias = ActivityStreamRef[CaseStatus]


class ParticipantStatus(VultronAS2Object):
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
    tracking_id: NonEmptyString | None = None
    case_status: CaseStatus | None = None

    @field_serializer("rm_state")
    def serialize_rm_state(self, rm_state: RM) -> str:
        return rm_state.name

    @field_serializer("vfd_state")
    def serialize_vfd_state(self, vfd_state: CS_vfd) -> str:
        return vfd_state.name

    @field_validator("rm_state", mode="before")
    def validate_rm_state(cls, v):
        if isinstance(v, str):
            return RM[v]
        return v

    @field_validator("vfd_state", mode="before")
    def validate_vfd_state(cls, v):
        if isinstance(v, str):
            return CS_vfd[v]
        return v

    @model_validator(mode="after")
    def set_name(self):
        if self.name is None:
            parts = [self.rm_state.name, self.vfd_state.name]
            if self.case_status is not None:
                if self.case_status.name is not None:
                    parts.append(self.case_status.name)
            self.name = " ".join(parts)
        return self

    @classmethod
    def from_core(
        cls, core_obj: VultronParticipantStatus
    ) -> "ParticipantStatus":
        data = core_obj.model_dump(mode="json")
        case_status = data.get("case_status")
        if isinstance(case_status, str):
            data["case_status"] = CaseStatus(
                id_=case_status,
                context=data.get("context"),
                attributed_to=data.get("attributed_to"),
            )
        return cls.model_validate(data)

    def to_core(self) -> VultronParticipantStatus:
        data = self._to_core_data()
        data["attributed_to"] = _scalar_ref_id_or_value(
            data.get("attributed_to")
        )
        data["context"] = _scalar_ref_id_or_value(data.get("context"))
        data["case_status"] = _scalar_ref_id_or_value(data.get("case_status"))
        if isinstance(data.get("vfd_state"), str):
            data["vfd_state"] = CS_vfd[data["vfd_state"]]
        return VultronParticipantStatus.model_validate(data)


ParticipantStatusRef: TypeAlias = ActivityStreamRef[ParticipantStatus]


def main():
    cs = CaseStatus()
    print(f"### {cs.type_} ###")
    print()
    print(cs.to_json(indent=2))
    print()
    print()

    ps = ParticipantStatus(
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
