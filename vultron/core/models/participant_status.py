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

"""Domain representation of a participant RM-state status record."""

from typing import Any, Literal

from pydantic import (
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    PecDimension,
    RmDimension,
    VfdDimension,
)


def coerce_em_consent_state(value: object) -> PEC | None:
    if value is None:
        return None
    if isinstance(value, PEC):
        return value
    if isinstance(value, str):
        return PEC[value]
    raise TypeError(
        f"Unsupported em_consent_state type: {type(value).__name__}"
    )


def coerce_cvd_roles(value: object) -> list[CVDRole]:
    if value is None:
        return [CVDRole.OTHER]
    if isinstance(value, CVDRole):
        return [value]
    if isinstance(value, str):
        return [CVDRole(value.lower())]
    if isinstance(value, list):
        if not value:
            return [CVDRole.OTHER]
        roles: list[CVDRole] = []
        for item in value:
            if isinstance(item, CVDRole):
                roles.append(item)
                continue
            if isinstance(item, str):
                roles.append(CVDRole(item.lower()))
                continue
            raise TypeError(
                f"Unsupported cvd_role item type: {type(item).__name__}"
            )
        return roles
    raise TypeError(f"Unsupported cvd_role type: {type(value).__name__}")


class ParticipantStatus(CoreObject):
    """Domain representation of a participant RM-state status record.

    Canonical core type for the Vultron ``ParticipantStatus`` object.
    ``type_`` is ``"ParticipantStatus"`` to match the wire value and
    to auto-register this class in :data:`CORE_VOCABULARY`.

    ``context`` (case ID) is required — a participant status is always
    associated with a specific case.

    ``case_status`` embeds the participant's perspective on the case-level
    state (em and pxa) via a nested :class:`CaseStatus` object.

    ``rm``, ``vfd``, and ``consent`` are dimension objects that own the RM,
    VFD, and PEC state machines respectively (ADR-0036, SDO-03-002).
    """

    model_config = ConfigDict(alias_generator=to_camel)

    type_: Literal["ParticipantStatus"] = Field(
        default="ParticipantStatus",
        validation_alias="type",
        serialization_alias="type",
    )
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    rm: RmDimension = Field(default_factory=RmDimension)
    vfd: VfdDimension = Field(default_factory=VfdDimension)
    case_engagement: bool = True
    embargo_adherence: bool = True
    consent: PecDimension | None = None
    cvd_role: list[CVDRole] = Field(default_factory=lambda: [CVDRole.OTHER])
    tracking_id: NonEmptyString | None = None
    case_status: CaseStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_flat_fields(cls, data: Any) -> Any:
        """Accept legacy flat ``rm_state``/``vfd_state``/``em_consent_state`` wire-format inputs.

        Handles both snake_case (``rm_state``) and camelCase alias (``rmState``) keys
        since ``model_validator(mode='before')`` runs before alias normalization.
        """
        if not isinstance(data, dict):
            return data
        data = dict(data)
        _SENTINEL = object()
        rm_raw = data.pop("rm_state", _SENTINEL)
        if rm_raw is _SENTINEL:
            rm_raw = data.pop("rmState", _SENTINEL)
        if rm_raw is not _SENTINEL and rm_raw is not None and "rm" not in data:
            data["rm"] = {"state": rm_raw}
        vfd_raw = data.pop("vfd_state", _SENTINEL)
        if vfd_raw is _SENTINEL:
            vfd_raw = data.pop("vfdState", _SENTINEL)
        if (
            vfd_raw is not _SENTINEL
            and vfd_raw is not None
            and "vfd" not in data
        ):
            data["vfd"] = {"state": vfd_raw}
        pec_raw = data.pop("em_consent_state", _SENTINEL)
        if pec_raw is _SENTINEL:
            pec_raw = data.pop("emConsentState", _SENTINEL)
        if pec_raw is not _SENTINEL and "consent" not in data:
            data["consent"] = (
                {"state": pec_raw} if pec_raw is not None else None
            )
        return data

    @field_serializer("cvd_role")
    def _serialize_cvd_role(self, roles: list[CVDRole]) -> list[str]:
        return [role.name for role in roles]

    @field_validator("cvd_role", mode="before")
    @classmethod
    def _validate_cvd_role(cls, v: object) -> list[CVDRole]:
        return coerce_cvd_roles(v)
