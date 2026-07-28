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

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.dimensions import EmDimension, PxaDimension


class CaseStatus(CoreObject):
    """Domain representation of a case status snapshot.

    Canonical core type for the Vultron ``CaseStatus`` object.
    ``type_`` is ``"CaseStatus"`` to match the wire value and
    to auto-register this class in :data:`CORE_VOCABULARY`.

    ``context`` (case ID) is required — a status snapshot without a case
    context is not meaningful.  ``attributed_to`` (reporting actor) is
    optional but must be non-empty when present.

    ``em`` and ``pxa`` are dimension objects that own the EM and PXA state
    machines respectively (ADR-0036, SDO-03-001).
    """

    model_config = ConfigDict(alias_generator=to_camel)

    type_: Literal["CaseStatus"] = Field(
        default="CaseStatus",
        validation_alias="type",
        serialization_alias="type",
    )
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    attributed_to: NonEmptyString | None = (
        None  # pyright: ignore[reportGeneralTypeIssues]
    )
    em: EmDimension = Field(default_factory=EmDimension)
    pxa: PxaDimension = Field(default_factory=PxaDimension)

    @model_validator(mode="before")
    @classmethod
    def _migrate_flat_fields(cls, data: Any) -> Any:
        """Accept legacy flat ``em_state``/``pxa_state`` wire-format inputs.

        Wire-layer ``as_CaseStatus`` serialises these as flat string fields.
        When the DataLayer reconstitutes a stored ``VulnerabilityCase``, the
        nested ``case_statuses`` dicts may still carry these keys.  Map them
        to the dimension-object keys so ``model_validate`` succeeds.
        Handles both snake_case and camelCase alias forms.
        """
        if not isinstance(data, dict):
            return data
        _SENTINEL = object()
        em_raw = data.get("em_state", _SENTINEL)
        if em_raw is _SENTINEL:
            em_raw = data.get("emState", _SENTINEL)
        if em_raw is not _SENTINEL and em_raw is not None and "em" not in data:
            data = dict(data)
            data.pop("em_state", None)
            data.pop("emState", None)
            data["em"] = {"state": em_raw}
        pxa_raw = data.get("pxa_state", _SENTINEL)
        if pxa_raw is _SENTINEL:
            pxa_raw = data.get("pxaState", _SENTINEL)
        if (
            pxa_raw is not _SENTINEL
            and pxa_raw is not None
            and "pxa" not in data
        ):
            data = dict(data)
            data.pop("pxa_state", None)
            data.pop("pxaState", None)
            data["pxa"] = {"state": pxa_raw}
        return data
