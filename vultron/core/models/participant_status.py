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
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    DDimension,
    PecDimension,
    RmDimension,
    VfDimension,
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
        return [CVDRole.OBSERVER]
    if isinstance(value, CVDRole):
        return [value]
    if isinstance(value, str):
        return [CVDRole(value.lower())]
    if isinstance(value, list):
        if not value:
            return [CVDRole.OBSERVER]
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

    ``rm``, ``vf``, ``d``, and ``consent`` are dimension objects that own the
    RM, VF, D, and PEC state machines respectively (ADR-0036, ADR-0075,
    SDO-03-002).  ``vf`` is non-None for VENDOR participants; ``d`` is
    non-None for DEPLOYER participants; a participant with both roles carries
    both.
    """

    model_config = ConfigDict(alias_generator=to_camel)

    type_: Literal["ParticipantStatus"] = Field(
        default="ParticipantStatus",
        validation_alias="type",
        serialization_alias="type",
    )
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    rm: RmDimension = Field(default_factory=RmDimension)
    vf: VfDimension | None = None
    d: DDimension | None = None
    case_engagement: bool = True
    consent: PecDimension | None = None

    @computed_field  # type: ignore[misc]
    @property
    def embargo_adherence(self) -> bool:
        """True iff consent.state == SIGNATORY; False otherwise (CM-18-008, ADR-0056)."""
        return self.consent is not None and self.consent.is_signatory()

    cvd_role: list[CVDRole] = Field(default_factory=lambda: [CVDRole.OBSERVER])
    tracking_id: NonEmptyString | None = None
    case_status: CaseStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_flat_fields(cls, data: Any) -> Any:
        """Accept legacy flat ``rm_state``/``vf_state``/``d_state``/``em_consent_state`` inputs.

        Handles both snake_case and camelCase alias keys since this runs before
        alias normalization.
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
        vf_raw = data.pop("vf_state", _SENTINEL)
        if vf_raw is _SENTINEL:
            vf_raw = data.pop("vfState", _SENTINEL)
        if vf_raw is not _SENTINEL and vf_raw is not None and "vf" not in data:
            data["vf"] = {"state": vf_raw}
        d_raw = data.pop("d_state", _SENTINEL)
        if d_raw is _SENTINEL:
            d_raw = data.pop("dState", _SENTINEL)
        if d_raw is not _SENTINEL and d_raw is not None and "d" not in data:
            data["d"] = {"state": d_raw}
        pec_raw = data.pop("em_consent_state", _SENTINEL)
        if pec_raw is _SENTINEL:
            pec_raw = data.pop("emConsentState", _SENTINEL)
        if pec_raw is not _SENTINEL and "consent" not in data:
            data["consent"] = (
                {"state": pec_raw} if pec_raw is not None else None
            )
        return data

    @model_validator(mode="before")
    @classmethod
    def _enforce_role_dimension_invariant(cls, data: Any) -> Any:
        """Auto-initialise vf/d dimensions based on cvd_role (ADR-0075).

        Pydantic v2 runs mode='before' validators in reverse definition order,
        so this validator fires *before* _migrate_flat_fields.  Flat keys
        (``vf_state``/``vfState``, ``d_state``/``dState``) are therefore
        detected here and excluded from the empty-dict seed; _migrate_flat_fields
        will hydrate them on its subsequent pass.  Uses ``mode="before"``
        (ADR-0064) to avoid recursive validation under ``validate_assignment=True``.

        VENDOR role → vf must be non-None (auto-set to initial state when absent).
        DEPLOYER role → d must be non-None (auto-set to initial state when absent).
        """
        if not isinstance(data, dict):
            return data
        roles_raw = data.get("cvd_role") or data.get("cvdRole") or []
        roles = coerce_cvd_roles(roles_raw)
        # Pydantic v2 runs mode='before' validators in reverse definition order,
        # so this validator fires before _migrate_flat_fields. Skip seeding when
        # a flat key is already present — _migrate_flat_fields will hydrate it.
        vf_absent = (
            data.get("vf") is None
            and data.get("vf_state") is None
            and data.get("vfState") is None
        )
        if CVDRole.VENDOR in roles and vf_absent:
            data["vf"] = {}
        d_absent = (
            data.get("d") is None
            and data.get("d_state") is None
            and data.get("dState") is None
        )
        if CVDRole.DEPLOYER in roles and d_absent:
            data["d"] = {}
        return data

    @field_serializer("cvd_role")
    def _serialize_cvd_role(self, roles: list[CVDRole]) -> list[str]:
        return [role.name for role in roles]

    @field_validator("cvd_role", mode="before")
    @classmethod
    def _validate_cvd_role(cls, v: object) -> list[CVDRole]:
        return coerce_cvd_roles(v)


def participant_status_rm_state(status: object) -> RM:
    """Return the RM state of a single ``ParticipantStatus``.

    This is the canonical RM-dimension reader.  Core :class:`ParticipantStatus`
    carries a nested ``rm: RmDimension`` (ADR-0036, SDO-03-002); the wire
    projection ``as_ParticipantStatus`` carries a flat ``rm_state: RM`` and no
    ``rm`` attribute at all.  Reading ``rm`` off a wire-shaped status therefore
    yields ``None``, and every caller that tolerated that ``None`` silently
    took a wrong branch — the defect behind issue #2232.

    A status object always has an RM state in the canonical shape (``rm`` has a
    ``default_factory``), so there is no legitimate ``None`` outcome here: an
    absent or unusable ``rm`` means the object is not core-shaped, and that is a
    defect to surface rather than absorb (ARCH-15-001..004).

    Callers for whom *absence* is legitimate — e.g. a participant with an empty
    ``participant_statuses`` list — must make that check themselves before
    calling, per the lenient-helper rule in ``notes/domain-validation.md``.

    Args:
        status: A single participant status object.

    Returns:
        The :class:`RM` state recorded on *status*.

    Raises:
        VultronValidationError: when *status* exposes no usable ``rm``
            dimension — typically because it is a wire-shaped status that
            should have been normalised at the wire→core boundary.
    """
    rm = getattr(status, "rm", None)
    if rm is None:
        raise VultronValidationError(
            f"ParticipantStatus {getattr(status, 'id_', status)!r} has no 'rm'"
            f" dimension (got a {type(status).__name__}). Core"
            " ParticipantStatus uses a nested 'rm: RmDimension'; the wire"
            " shape uses a flat 'rm_state'. Convert at the wire→core boundary"
            " (as_ParticipantStatus.to_core()) instead of reading the wire"
            " shape here. See issue #2232."
        )
    state = getattr(rm, "state", None)
    if not isinstance(state, RM):
        raise VultronValidationError(
            f"ParticipantStatus {getattr(status, 'id_', status)!r} has an 'rm'"
            f" dimension with no valid RM state (got {state!r}). See issue"
            " #2232."
        )
    return state


def participant_status_vf_state(status: object) -> CS_vf | None:
    """Return the VF state of a single ``ParticipantStatus``, or None.

    Returns ``None`` when the participant has no ``vf`` dimension (i.e. is not
    a VENDOR participant).  Raises when ``vf`` is present but malformed.

    Args:
        status: A single participant status object.

    Returns:
        The :class:`CS_vf` state, or ``None`` for non-VENDOR participants.

    Raises:
        VultronValidationError: when *status* has a ``vf`` attribute but it
            carries no valid VF state — typically a shape mismatch.
    """
    vf = getattr(status, "vf", None)
    if vf is None:
        return None
    state = getattr(vf, "state", None)
    if not isinstance(state, CS_vf):
        raise VultronValidationError(
            f"ParticipantStatus {getattr(status, 'id_', status)!r} has a 'vf'"
            f" dimension with no valid VF state (got {state!r})."
        )
    return state


def participant_status_d_state(status: object) -> CS_d | None:
    """Return the D state of a single ``ParticipantStatus``, or None.

    Returns ``None`` when the participant has no ``d`` dimension (i.e. is not
    a DEPLOYER participant).  Raises when ``d`` is present but malformed.

    Args:
        status: A single participant status object.

    Returns:
        The :class:`CS_d` state, or ``None`` for non-DEPLOYER participants.

    Raises:
        VultronValidationError: when *status* has a ``d`` attribute but it
            carries no valid D state — typically a shape mismatch.
    """
    d = getattr(status, "d", None)
    if d is None:
        return None
    state = getattr(d, "state", None)
    if not isinstance(state, CS_d):
        raise VultronValidationError(
            f"ParticipantStatus {getattr(status, 'id_', status)!r} has a 'd'"
            f" dimension with no valid D state (got {state!r})."
        )
    return state
