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

from typing import Literal

from pydantic import Field, field_serializer, field_validator

from vultron.core.states.em import EM
from vultron.core.states.cs import CS_pxa
from vultron.core.models.base import CoreObject, NonEmptyString


class CaseStatus(CoreObject):
    """Domain representation of a case status snapshot.

    Canonical core type for the Vultron ``CaseStatus`` object.
    ``type_`` is ``"CaseStatus"`` to match the wire value and
    to auto-register this class in :data:`CORE_VOCABULARY`.

    ``context`` (case ID) is required — a status snapshot without a case
    context is not meaningful.  ``attributed_to`` (reporting actor) is
    optional but must be non-empty when present.
    """

    type_: Literal["CaseStatus"] = Field(
        default="CaseStatus",
        validation_alias="type",
        serialization_alias="type",
    )
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    attributed_to: NonEmptyString | None = (
        None  # pyright: ignore[reportGeneralTypeIssues]
    )
    em_state: EM = EM.NO_EMBARGO
    pxa_state: CS_pxa = CS_pxa.pxa

    @field_serializer("em_state")
    def _serialize_em_state(self, v: EM) -> str:
        return v.name

    @field_serializer("pxa_state")
    def _serialize_pxa_state(self, v: CS_pxa) -> str:
        return v.name

    @field_validator("em_state", mode="before")
    @classmethod
    def _validate_em_state(cls, v: object) -> EM:
        if isinstance(v, str):
            if v in EM.__members__:
                return EM[v]
            return EM(v)
        return v  # type: ignore[return-value]

    @field_validator("pxa_state", mode="before")
    @classmethod
    def _validate_pxa_state(cls, v: object) -> CS_pxa:
        if isinstance(v, str):
            return CS_pxa[v]
        return v  # type: ignore[return-value]
