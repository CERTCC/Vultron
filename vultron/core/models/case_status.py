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

"""Domain representation of a case status snapshot."""

from typing import Any

from pydantic import field_serializer

from vultron.core.states.em import EM
from vultron.core.states.cs import CS_pxa
from vultron.core.models.base import NonEmptyString, VultronObject


class VultronCaseStatus(VultronObject):
    """Domain representation of a case status snapshot.

    Mirrors the Vultron-specific fields of ``CaseStatus``.
    ``type_`` is ``"CaseStatus"`` to match the wire value.
    """

    type_: str = "CaseStatus"
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    attributed_to: Any  # pyright: ignore[reportGeneralTypeIssues]
    em_state: EM = EM.EMBARGO_MANAGEMENT_NONE
    pxa_state: CS_pxa = CS_pxa.pxa

    @field_serializer("pxa_state")
    def _serialize_pxa_state(self, v: CS_pxa) -> str:
        return v.name
