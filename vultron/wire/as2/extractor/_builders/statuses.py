"""Builders for received ``CaseStatus`` and ``ParticipantStatus`` objects.

Each state dimension is coerced from its wire form to its core enum, and a
received status must carry its ``published`` (CLP-15-010).
"""

from datetime import datetime
from typing import Any

from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    DDimension,
    EmDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
    dimension_state,
)
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
)
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.wire.as2.errors import (
    VultronParseMissingPublishedError,
)
from vultron.wire.as2.extractor._builders.fields import _get_id, _get_timestamp


def _status_published(status: object) -> datetime:
    """A received ``CaseStatus``'s ``published``, which it must carry.

    ``parse_activity`` refuses a status without one (CLP-15-010), so this
    never mints a time to stand in for a missing one.

    Raises:
        VultronParseMissingPublishedError: When *status* carries no
            ``published``, naming the status.
    """
    published = _get_timestamp(status, "published")
    if published is None:
        raise VultronParseMissingPublishedError(
            f"CaseStatus {_get_id(status)!r} carries no 'published' (CLP-15-010)"
        )
    return published


def _coerce_em(raw: object) -> EM:
    if isinstance(raw, EM):
        return raw
    if isinstance(raw, str):
        return EM[raw] if raw in EM.__members__ else EM(raw)
    return EM.NONE


def _coerce_pxa(raw: object) -> CS_pxa:
    if isinstance(raw, CS_pxa):
        return raw
    if isinstance(raw, str):
        return CS_pxa[raw]
    return CS_pxa.pxa


def _coerce_rm(raw: object) -> RM:
    if isinstance(raw, RM):
        return raw
    if isinstance(raw, str):
        return RM[raw]
    return RM.START


def _coerce_vf(raw: object) -> CS_vf | None:
    if raw is None:
        return None
    if isinstance(raw, CS_vf):
        return raw
    if isinstance(raw, str):
        try:
            return CS_vf[raw]
        except KeyError:
            raise ValueError(f"Unknown CS_vf value: {raw!r}") from None
    return None


def _coerce_d(raw: object) -> CS_d | None:
    if raw is None:
        return None
    if isinstance(raw, CS_d):
        return raw
    if isinstance(raw, str):
        try:
            return CS_d[raw]
        except KeyError:
            raise ValueError(f"Unknown CS_d value: {raw!r}") from None
    return None


def _build_case_status_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    case_context = _get_id(getattr(obj, "context", None))
    attributed_to = _get_id(getattr(obj, "attributed_to", None))
    if object_id and case_context:
        return {
            "object_": CaseStatus(
                id_=object_id,
                name=getattr(obj, "name", None),
                context=case_context,
                attributed_to=attributed_to,
                em=EmDimension(state=_coerce_em(dimension_state(obj, "em"))),
                pxa=PxaDimension(
                    state=_coerce_pxa(dimension_state(obj, "pxa"))
                ),
                published=_status_published(obj),
                updated=_get_timestamp(obj, "updated"),
            )
        }
    return {}


def _build_participant_status_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    ctx = _get_id(getattr(obj, "context", None)) or ""
    wire_case_status = getattr(obj, "case_status", None)
    if object_id:
        # Extract embedded CaseStatus into a CaseStatus core object so
        # that pxa and em are propagated across the wire boundary.
        core_case_status: CaseStatus | None = None
        if wire_case_status is not None:
            cs_id = _get_id(wire_case_status)
            cs_context = (
                _get_id(getattr(wire_case_status, "context", None)) or ctx
            )
            cs_attributed_to = _get_id(
                getattr(wire_case_status, "attributed_to", None)
            )
            if cs_id and cs_context:
                core_case_status = CaseStatus(
                    id_=cs_id,
                    context=cs_context,
                    attributed_to=cs_attributed_to,
                    em=EmDimension(
                        state=_coerce_em(
                            dimension_state(wire_case_status, "em")
                        )
                    ),
                    pxa=PxaDimension(
                        state=_coerce_pxa(
                            dimension_state(wire_case_status, "pxa")
                        )
                    ),
                    published=_status_published(wire_case_status),
                    updated=_get_timestamp(wire_case_status, "updated"),
                )
        return {
            "object_": ParticipantStatus(
                id_=object_id,
                name=getattr(obj, "name", None),
                context=ctx,
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                rm=RmDimension(state=_coerce_rm(dimension_state(obj, "rm"))),
                vf=(
                    VfDimension(state=_vf)
                    if (_vf := _coerce_vf(dimension_state(obj, "vf")))
                    is not None
                    else None
                ),
                d=(
                    DDimension(state=_d)
                    if (_d := _coerce_d(dimension_state(obj, "d"))) is not None
                    else None
                ),
                cvd_role=coerce_cvd_roles(
                    getattr(obj, "cvd_role", getattr(obj, "cvd_roles", None))
                ),
                case_status=core_case_status,
                published=_get_timestamp(obj, "published"),
                updated=_get_timestamp(obj, "updated"),
            )
        }
    return {}
