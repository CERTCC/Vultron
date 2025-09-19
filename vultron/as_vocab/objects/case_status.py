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

from dataclasses import dataclass, field
from typing import Optional

from dataclasses_json import config
from marshmallow import fields

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.utils import exclude_if_none
from vultron.as_vocab.objects.base import VultronObject
from vultron.bt.embargo_management.states import EM
from vultron.bt.report_management.states import RM
from vultron.case_states.states import CS_pxa, CS_vfd


@activitystreams_object
@dataclass(kw_only=True)
class CaseStatus(VultronObject):
    """
    Represents the case-level (global, participant-agnostic) status of a VulnerabilityCase.
    """

    context: Optional[str] = None  # Case ID goes here
    em_state: EM = field(
        default=EM.NO_EMBARGO,
        metadata={
            "dataclasses_json": {
                "encoder": lambda value: EM(value).name,
                "decoder": lambda name: EM[name],
                "mm_field": fields.Enum,
            }
        },
    )
    pxa_state: CS_pxa = field(
        default=CS_pxa.pxa,
        metadata={
            "dataclasses_json": {
                "encoder": lambda value: CS_pxa(value).name,
                "decoder": lambda name: CS_pxa[name],
                "mm_field": fields.Enum,
            },
        },
    )

    def __post_init__(self) -> None:
        """
        Sets the name of the CaseStatus to the name of the EM state and the name of the PXA state.

        Returns:
            None
        """
        super().__post_init__()
        if self.name is None:
            self.name = " ".join([self.em_state.name, self.pxa_state.name])


@activitystreams_object
@dataclass(kw_only=True)
class ParticipantStatus(VultronObject):
    """
    Represents the status of a participant with respect to a VulnerabilityCase (participant-specific).
    """

    actor: Optional[as_Actor | as_Link | str] = field(default=None)
    context: Optional[as_Object | as_Link | str] = field(default=None)
    rm_state: RM = field(
        default=RM.START,
        repr=True,
        metadata={
            "dataclasses_json": {
                "encoder": lambda value: RM(value).name,
                "decoder": lambda name: RM[name],
                "mm_field": fields.Enum,
            }
        },
    )
    vfd_state: CS_vfd = field(
        default=CS_vfd.vfd,
        metadata={
            "dataclasses_json": {
                "encoder": lambda value: CS_vfd(value).name,
                "decoder": lambda name: CS_vfd[name],
                "mm_field": fields.Enum,
            }
        },
    )
    case_engagement: bool = True
    embargo_adherence: bool = True
    tracking_id: Optional[str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    case_status: Optional[CaseStatus] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    def __post_init__(self) -> None:
        """
        Sets the name of the ParticipantStatus to the name of the RM state, the name of the VFD state, and the name of
        the CaseStatus (if present).

        Returns:
            None
        """
        super().__post_init__()
        if self.name is None:
            parts = [self.rm_state.name, self.vfd_state.name]
            if self.case_status is not None:
                parts.append(self.case_status.name)
            self.name = " ".join(parts)


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
