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
    AliasChoices,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from pydantic.alias_generators import to_camel

from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronProtocolViolationError,
    VultronValidationError,
)
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    DDimension,
    PecDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.wire_keys import input_keys


def coerce_em_consent_state(value: object) -> PEC | None:
    if value is None:
        return None
    if isinstance(value, PEC):
        return value
    if isinstance(value, str):
        # ADR-0091 renamed NO_EMBARGO → UNBOUND; migrate stored legacy values.
        if value == "NO_EMBARGO":
            return PEC.UNBOUND
        return PEC(value)
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

    type_: Literal["ParticipantStatus"] = Field(
        default="ParticipantStatus",
        validation_alias="type",
        serialization_alias="type",
    )
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    # Each dimension serializes to its bare state value (ADR-0099 detail 5), so
    # the alias alone produces the flat wire shape the AS2 form has always used:
    # ``rm`` -> ``{"rmState": "START"}``.  ``AliasChoices`` keeps the legacy flat
    # spellings accepted on input so no caller has to change.
    rm: RmDimension = Field(
        default_factory=RmDimension,
        validation_alias=AliasChoices("rmState", "rm_state", "rm"),
        serialization_alias="rmState",
    )
    vf: VfDimension | None = Field(
        default=None,
        validation_alias=AliasChoices("vfState", "vf_state", "vf"),
        serialization_alias="vfState",
    )
    d: DDimension | None = Field(
        default=None,
        validation_alias=AliasChoices("dState", "d_state", "d"),
        serialization_alias="dState",
    )
    case_engagement: bool = True
    consent: PecDimension | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "emConsentState", "em_consent_state", "consent"
        ),
        serialization_alias="emConsentState",
    )

    @computed_field  # type: ignore[misc]
    @property
    def embargo_adherence(self) -> bool:
        """True iff consent.state == SIGNATORY; False otherwise (CM-18-008, ADR-0056)."""
        return self.consent is not None and self.consent.is_signatory()

    cvd_role: list[CVDRole] = Field(default_factory=lambda: [CVDRole.OBSERVER])
    tracking_id: NonEmptyString | None = None
    case_status: CaseStatus | None = None

    previous_rm_state: RM | None = Field(
        default=None,
        exclude=True,
        description=(
            "Caller-supplied previous RM state for construction-time backward-step"
            " validation (AC-1, ISSUE-3199). When set, the model validator"
            " _validate_rm_backward_step refuses a backward or invalid RM"
            " transition unless force_rm_state=True. Not serialised."
        ),
    )
    force_rm_state: bool = Field(
        default=False,
        exclude=True,
        description=(
            "Suppress the construction-time RM adjacency check. Set only by the"
            " sanctioned closure call sites (same semantics as"
            " CreateParticipantStatusNode.force_rm_state). Not serialised."
        ),
    )

    # There is deliberately no ``_migrate_flat_fields`` before-validator any
    # more.  It hand-translated the flat ``rm_state`` / ``rmState`` spellings
    # into the nested ``{"state": ...}`` form, and was the only AS2 spelling in
    # this module outside an alias.  Both mechanisms ADR-0099 detail 5 introduced
    # now cover its whole job with nothing hand-written: the ``AliasChoices``
    # above accept all three spellings, and ``_ScalarDimension``'s
    # ``_accept_bare_state`` accepts the bare state value the flat form carries.

    @model_validator(mode="before")
    @classmethod
    def _reject_retired_vfd_keys(cls, data: Any) -> Any:
        """Refuse the retired ``vfd_state``/``vfdState`` key (SDO-03-005).

        ADR-0075 split the combined VFD dimension into ``vf`` (vendor fix) and
        ``d`` (deployer deployment).  ``vfd_state`` names neither, so it matches no
        field and no alias — Pydantic's ``extra="ignore"`` default would discard it
        and leave both dimensions at their initial states.  That is silent protocol
        state loss, so it is refused instead.

        Relocated here from ``as_ParticipantStatus`` when that class was collapsed
        into this one (ADR-0099 detail 3, AC-4).  It is the one piece of the wire
        class's behaviour with no core equivalent: the camelCase guards it sat
        beside are obsolete now that core derives AS2 spellings, but a *retired*
        name is not a spelling of anything, so this guard is still load-bearing.

        Raises ``VultronProtocolViolationError``, which subclasses ``ValueError``
        so Pydantic reports it as a validation failure rather than letting it
        escape ``model_validate()``.
        """
        # The camelCase form is derived, not written out: ADR-0099 detail 2 keeps
        # AS2 spellings out of core logic, and an architecture test enforces it
        # (test_core_no_as2_spellings).  Deriving also guarantees the guard matches
        # whatever the project's own generator would have produced.
        retired = "vfd_state"
        if isinstance(data, dict) and (
            retired in data or to_camel(retired) in data
        ):
            raise VultronProtocolViolationError(
                f"{retired}/{to_camel(retired)} is retired (ADR-0075). Use"
                " vf_state for vendor participants and d_state for deployer"
                " participants instead."
            )
        return data

    @model_validator(mode="before")
    @classmethod
    def _enforce_role_dimension_invariant(cls, data: Any) -> Any:
        """Auto-initialise vf/d dimensions based on cvd_role (ADR-0075).

        Uses ``mode="before"`` (ADR-0064) to avoid recursive validation under
        ``validate_assignment=True``.

        VENDOR role → vf must be non-None (auto-set to initial state when absent).
        DEPLOYER role → d must be non-None (auto-set to initial state when absent).

        The raw input may spell a dimension any of the ways its
        ``validation_alias`` accepts, so "is it absent?" asks the field for its
        own input spellings via :func:`input_keys` rather than listing them here
        — core code must not type an AS2 spelling (ADR-0099 detail 2).  The
        empty-dict seed is only a *default*: it is written under the Python field
        name, which is the last choice in each field's ``AliasChoices``, so a
        spelling actually present in the input still wins.
        """
        if not isinstance(data, dict):
            return data
        roles_raw: Any = next(
            (
                data[key]
                for key in input_keys(cls, "cvd_role")
                if data.get(key)
            ),
            [],
        )
        roles = coerce_cvd_roles(roles_raw)
        for role, dimension in (
            (CVDRole.VENDOR, "vf"),
            (CVDRole.DEPLOYER, "d"),
        ):
            absent = all(
                data.get(key) is None for key in input_keys(cls, dimension)
            )
            if role in roles and absent:
                data[dimension] = {}
        return data

    @model_validator(mode="after")
    def _validate_rm_backward_step(self) -> "ParticipantStatus":
        """Refuse invalid RM transitions at construction time (AC-1, ISSUE-3199).

        Fires only when the caller supplies ``previous_rm_state``; the check is
        a no-op when that field is ``None`` (most construction sites do not have
        the previous state in scope).  Same-state re-assertions are allowed
        (idempotent), consistent with how ``_rm_violations`` treats them.  Pass
        ``force_rm_state=True`` to bypass — only the three sanctioned closure
        call sites should ever do this.
        """
        prev = self.previous_rm_state
        if prev is not None and not self.force_rm_state:
            requested = self.rm.state
            if requested != prev and not is_valid_rm_transition(
                prev, requested
            ):
                raise VultronProtocolViolationError(
                    f"Invalid RM transition at construction:"
                    f" {prev!r} → {requested!r} (not adjacent)."
                    " Pass force_rm_state=True to override"
                    " (only sanctioned closure sites)."
                )
        return self

    @field_serializer("cvd_role")
    def _serialize_cvd_role(self, roles: list[CVDRole]) -> list[str]:
        return [role.name for role in roles]

    @field_validator("cvd_role", mode="before")
    @classmethod
    def _validate_cvd_role(cls, v: object) -> list[CVDRole]:
        return coerce_cvd_roles(v)

    # Flat views onto the dimensions, matching ``CaseStatus.em_state``/
    # ``pxa_state``.  The deleted ``as_ParticipantStatus`` carried
    # ``rm_state``/``vf_state``/``d_state`` as real fields, so callers read and
    # assigned them; the dimension remains the owner of the state machine
    # (ADR-0036) and the flat spelling is only how it serializes (ADR-0099
    # detail 5).
    #
    # ``vf`` and ``d`` are legitimately absent for a participant whose role does
    # not carry them (ADR-0075), so those two views are optional in both
    # directions rather than fabricating an initial state on read.

    @property
    def rm_state(self) -> RM:
        """The RM state value. A view onto ``rm.state``."""
        return self.rm.state

    @rm_state.setter
    def rm_state(self, value: RM) -> None:
        self.rm = RmDimension(state=value)

    @property
    def vf_state(self) -> CS_vf | None:
        """The VF state value, or ``None`` when this participant has no VF."""
        return self.vf.state if self.vf is not None else None

    @vf_state.setter
    def vf_state(self, value: CS_vf | None) -> None:
        self.vf = VfDimension(state=value) if value is not None else None

    @property
    def d_state(self) -> CS_d | None:
        """The D state value, or ``None`` when this participant has no D."""
        return self.d.state if self.d is not None else None

    @d_state.setter
    def d_state(self, value: CS_d | None) -> None:
        self.d = DDimension(state=value) if value is not None else None

    @model_validator(mode="after")
    def _set_name(self) -> "ParticipantStatus":
        """Derive the human-readable ``name`` label from the dimension states.

        ``name`` is an optional AS2 property carrying a display label, not
        protocol data. The object derives its own label from its own state, for
        the same reason a dimension serializes its own value (ADR-0099 detail
        5): the fact belongs to the class that holds the state.

        Only set when the caller supplied none, so an explicit ``name`` always
        wins. ``object.__setattr__`` avoids re-entering validation, since
        ``validate_assignment`` is in effect on the core branch (ARCH-21-001).
        """
        if self.name is None:
            parts = [self.rm.state.name]
            if self.vf is not None:
                parts.append(self.vf.state.name)
            if self.d is not None:
                parts.append(self.d.state.name)
            if self.case_status is not None and self.case_status.name:
                parts.append(self.case_status.name)
            object.__setattr__(self, "name", " ".join(parts))
        return self


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
