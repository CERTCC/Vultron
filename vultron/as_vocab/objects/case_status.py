#!/usr/bin/env python
"""
Provides Case Status objects for the Vultron ActivityStreams Vocabulary.
"""
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

from pydantic import field_serializer, field_validator, model_validator

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.objects.base import VultronObject
from vultron.bt.embargo_management.states import EM
from vultron.bt.report_management.states import RM
from vultron.case_states.states import CS_pxa, CS_vfd


@activitystreams_object
class CaseStatus(VultronObject):
    """
    Represents the case-level (global, participant-agnostic) status of a VulnerabilityCase.
    """

    context: str | None = None  # Case ID goes here
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
            return EM[v]
        return v

    @field_validator("pxa_state", mode="before")
    def validate_pxa_state(cls, v):
        if isinstance(v, str):
            return CS_pxa[v]
        return v

    @model_validator(mode="after")
    def set_name(cls, self):
        if self.name is None:
            self.name = " ".join([self.em_state.name, self.pxa_state.name])
        return self

@activitystreams_object
class ParticipantStatus(VultronObject):
    """
    Represents the status of a participant with respect to a VulnerabilityCase (participant-specific).
    """

    actor: as_Actor | as_Link | str = None
    context: as_Object | as_Link | str = None
    rm_state: RM = RM.START
    vfd_state: CS_vfd = CS_vfd.vfd
    case_engagement: bool = True
    embargo_adherence: bool = True
    tracking_id: str | None = None
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
    def set_name(cls, self):
        if self.name is None:
            parts = [self.rm_state.name, self.vfd_state.name]
            if self.case_status is not None:
                parts.append(self.case_status.name)
            self.name = " ".join(parts)
        return self



def main():
    cs = CaseStatus()
    print(f"### {cs.as_type} ###")
    print()
    print(cs.to_json(indent=2))
    print()
    print()

    ps = ParticipantStatus(
        rm_state=RM.RECEIVED, vfd_state=CS_vfd.Vfd, case_status=cs
    )
    print(f"### {ps.as_type} ###")
    print()
    print(ps.to_json(indent=2))
    print()
    print()


if __name__ == "__main__":
    main()
