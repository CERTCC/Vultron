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

"""Per-machine dimension objects for CaseStatus and ParticipantStatus.

Each dimension object is a lightweight Pydantic BaseModel that holds one state
enum and owns immutable transition() validation and guard methods for that
state machine. Transitions return a new dimension object; they never mutate
self.

Design: ADR-0036, spec: specs/status-dimension-objects.yaml (SDO-01 to SDO-04).
"""

from pydantic import BaseModel, field_serializer, field_validator

from vultron.core.states.cs import (
    CS_pxa,
    CS_vfd,
    PXA_ATTACKS_OBSERVED,
    PXA_EXPLOIT_PUBLIC,
    PXA_PUBLIC_AWARE,
    PxaState,
    VFD_FIX_DEPLOYED,
    VFD_FIX_READY,
    VFD_VENDOR_AWARE,
    VfdState,
    PXA_Trigger,
    VFD_Trigger,
    _pxa_transitions,
    _vfd_transitions,
)
from vultron.core.states.em import (
    EM,
    EM_Trigger,
    _transitions as _em_transitions,
)
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    _transitions as _pec_transitions,
)
from vultron.core.states.rm import (
    RM,
    RM_Trigger,
    RM_VALIDATED,
    _transitions as _rm_transitions,
)
from vultron.errors import VultronInvalidStateTransitionError


def _coerce_em(v: object) -> EM:
    if isinstance(v, EM):
        return v
    if isinstance(v, str):
        return EM[v]
    raise ValueError(f"Cannot coerce {v!r} to EM")


def _coerce_rm(v: object) -> RM:
    if isinstance(v, RM):
        return v
    if isinstance(v, str):
        return RM[v]
    raise ValueError(f"Cannot coerce {v!r} to RM")


def _coerce_pec(v: object) -> PEC:
    if isinstance(v, PEC):
        return v
    if isinstance(v, str):
        return PEC[v]
    raise ValueError(f"Cannot coerce {v!r} to PEC")


def _coerce_pxa(v: object) -> CS_pxa:
    if isinstance(v, CS_pxa):
        return v
    if isinstance(v, str):
        return CS_pxa[v]
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return CS_pxa(PxaState(*v))
    raise ValueError(f"Cannot coerce {v!r} to CS_pxa")


def _coerce_vfd(v: object) -> CS_vfd:
    if isinstance(v, CS_vfd):
        return v
    if isinstance(v, str):
        return CS_vfd[v]
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return CS_vfd(VfdState(*v))
    raise ValueError(f"Cannot coerce {v!r} to CS_vfd")


def _apply_transition(
    current_state: object,
    trigger: object,
    transitions: list[dict],
    machine_name: str,
) -> object:
    """Return the destination state for (current_state, trigger).

    Raises VultronInvalidStateTransitionError when no matching transition exists.
    Supports wildcard source "*" (PEC RESET).
    """
    for t in transitions:
        src = t.get("source")
        if src != current_state and src != "*":
            continue
        if t.get("trigger") != trigger:
            continue
        return t["dest"]
    raise VultronInvalidStateTransitionError(
        f"{machine_name}: state '{current_state}' does not accept trigger"
        f" '{trigger}'."
    )


class EmDimension(BaseModel):
    """Embargo Management state dimension object.

    Holds the case-level EM state and owns immutable transition validation.
    Replaces CaseStatus.em_state (SDO-01-001, SDO-03-001).
    """

    state: EM = EM.NO_EMBARGO

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: object) -> EM:
        return _coerce_em(v)

    @field_serializer("state")
    def serialize_state(self, v: EM) -> str:
        return v.name

    def transition(self, trigger: EM_Trigger) -> "EmDimension":
        """Return a new EmDimension with the state after applying *trigger*.

        Raises VultronInvalidStateTransitionError on invalid trigger.
        """
        new_state = _apply_transition(
            self.state, trigger, _em_transitions, "EmDimension"
        )
        return self.model_copy(update={"state": EM(str(new_state))})

    def is_active(self) -> bool:
        return self.state in (EM.ACTIVE, EM.REVISE)

    def is_proposed(self) -> bool:
        return self.state == EM.PROPOSED

    def is_exited(self) -> bool:
        return self.state == EM.EXITED

    def is_none(self) -> bool:
        return self.state == EM.NONE


class PxaDimension(BaseModel):
    """PXA (public/exploit/attacks) case state dimension object.

    Holds the participant-agnostic public state and owns immutable transition
    validation.  Replaces CaseStatus.pxa_state (SDO-01-001, SDO-03-001).
    """

    state: CS_pxa = CS_pxa.pxa

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: object) -> CS_pxa:
        return _coerce_pxa(v)

    @field_serializer("state")
    def serialize_state(self, v: CS_pxa) -> str:
        return v.name

    def transition(self, trigger: PXA_Trigger) -> "PxaDimension":
        """Return a new PxaDimension with the state after applying *trigger*.

        Raises VultronInvalidStateTransitionError on invalid trigger.
        """
        new_state = _apply_transition(
            self.state, trigger, _pxa_transitions, "PxaDimension"
        )
        return self.model_copy(update={"state": CS_pxa(new_state)})

    def is_public_aware(self) -> bool:
        return self.state in PXA_PUBLIC_AWARE

    def is_exploit_public(self) -> bool:
        return self.state in PXA_EXPLOIT_PUBLIC

    def is_attacks_observed(self) -> bool:
        return self.state in PXA_ATTACKS_OBSERVED

    def is_embargo_eligible(self) -> bool:
        """Return True when no P/X/A bit is set (EMB-01-002, EMB-02-002)."""
        return self.state == CS_pxa.pxa


class RmDimension(BaseModel):
    """Report Management state dimension object.

    Holds the per-participant RM state and owns immutable transition validation.
    Replaces ParticipantStatus.rm_state (SDO-01-001, SDO-03-002).
    """

    state: RM = RM.START

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: object) -> RM:
        return _coerce_rm(v)

    @field_serializer("state")
    def serialize_state(self, v: RM) -> str:
        return v.name

    def transition(self, trigger: RM_Trigger) -> "RmDimension":
        """Return a new RmDimension with the state after applying *trigger*.

        Raises VultronInvalidStateTransitionError on invalid trigger.
        """
        new_state = _apply_transition(
            self.state, trigger, _rm_transitions, "RmDimension"
        )
        return self.model_copy(update={"state": RM(str(new_state))})

    def is_validated(self) -> bool:
        return self.state in RM_VALIDATED

    def is_accepted(self) -> bool:
        return self.state == RM.ACCEPTED

    def is_closed(self) -> bool:
        return self.state == RM.CLOSED

    def is_terminal(self) -> bool:
        return self.state == RM.CLOSED


class VfdDimension(BaseModel):
    """VFD (vendor/fix/deploy) vendor fix path dimension object.

    Holds the per-participant vendor fix path state and owns immutable
    transition validation.  Replaces ParticipantStatus.vfd_state
    (SDO-01-001, SDO-03-002).
    """

    state: CS_vfd = CS_vfd.vfd

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: object) -> CS_vfd:
        return _coerce_vfd(v)

    @field_serializer("state")
    def serialize_state(self, v: CS_vfd) -> str:
        return v.name

    def transition(self, trigger: VFD_Trigger) -> "VfdDimension":
        """Return a new VfdDimension with the state after applying *trigger*.

        Raises VultronInvalidStateTransitionError on invalid trigger.
        """
        new_state = _apply_transition(
            self.state, trigger, _vfd_transitions, "VfdDimension"
        )
        return self.model_copy(update={"state": CS_vfd(new_state)})

    def is_vendor_aware(self) -> bool:
        return self.state in VFD_VENDOR_AWARE

    def is_fix_ready(self) -> bool:
        return self.state in VFD_FIX_READY

    def is_fix_deployed(self) -> bool:
        return self.state in VFD_FIX_DEPLOYED


class PecDimension(BaseModel):
    """Participant Embargo Consent dimension object.

    Holds a single participant's embargo consent state and owns immutable
    transition validation.  Replaces ParticipantStatus.em_consent_state
    (SDO-01-001, SDO-03-002).
    """

    state: PEC = PEC.NO_EMBARGO

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: object) -> PEC:
        return _coerce_pec(v)

    @field_serializer("state")
    def serialize_state(self, v: PEC) -> str:
        return v.name

    def transition(self, trigger: PEC_Trigger) -> "PecDimension":
        """Return a new PecDimension with the state after applying *trigger*.

        Raises VultronInvalidStateTransitionError on invalid trigger.
        Supports the RESET wildcard ("*" → NO_EMBARGO from any state).
        """
        new_state = _apply_transition(
            self.state, trigger, _pec_transitions, "PecDimension"
        )
        return self.model_copy(update={"state": PEC(str(new_state))})

    def is_signatory(self) -> bool:
        return self.state == PEC.SIGNATORY

    def is_declined(self) -> bool:
        return self.state == PEC.DECLINED

    def is_invited(self) -> bool:
        return self.state == PEC.INVITED

    def is_lapsed(self) -> bool:
        return self.state == PEC.LAPSED
