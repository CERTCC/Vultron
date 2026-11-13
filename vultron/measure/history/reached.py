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
"""The states a case's ledger has reached at its last entry.

The derivation compares each entry's state with the state already reached
(CEH-04-001), so when the walk ends it holds what each dimension has reached.
:class:`ReachedState` keeps that, for a measure that reads where a case
stands rather than how it got there.

It is the walk's own record, not a second reading of the ledger: a state an
entry names behind the one reached is excluded here as it is from the events
(CEH-04-015).  It also holds what the events cannot show: an inert
participant's report management, which yields no event until it joins
(CEH-04-010), and the embargo register entries still proposed, from which the
case's EM state is derived (ADR-0122).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    model_validator,
)

from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    derive_em,
)
from vultron.core.states.rm import RM
from vultron.primitives import NonEmptyString

#: A public state, serialized by its ``pxa`` notation (``CS_pxa`` values are
#: tuples, which say nothing to a reader).
PxaName = Annotated[
    CS_pxa, PlainSerializer(lambda state: state.name, return_type=str)
]


class ReachedParticipant(BaseModel):
    """What one participant has reached at the ledger's last entry.

    Fields:
        participant: The participant's actor.
        rm: Its report-management state.  An inert participant's state is
            the one its records name, though it is no case event yet
            (CEH-04-010).
        roles: Every case role its records name, upper-cased and sorted.
        joined: ``False`` while the participant is an inert invitee that has
            not accepted its invitation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participant: NonEmptyString
    rm: RM = RM.START
    roles: tuple[NonEmptyString, ...] = ()
    joined: bool = True

    @model_validator(mode="after")
    def _roles_are_sorted_once(self) -> ReachedParticipant:
        if list(self.roles) != sorted(set(self.roles)):
            raise ValueError("roles must be sorted and listed once each")
        return self


class ReachedState(BaseModel):
    """The states a case's ledger has reached at its last entry.

    Fields:
        participants: Every participant the ledger records, in the order
            the walk first met each.
        pxa: The case's public state, as the CASE_MANAGER adopted it
            (CEH-03-012).
        embargo_register: Each embargo register entry the ledger names, by embargo
            id, with the status the ledger's steps leave it in.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participants: list[ReachedParticipant] = Field(default_factory=list)
    pxa: PxaName = CS_pxa.pxa
    embargo_register: dict[str, EmbargoRegisterStatus] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def _one_record_per_participant(self) -> ReachedState:
        names = [p.participant for p in self.participants]
        if len(set(names)) != len(names):
            raise ValueError("a participant is listed more than once")
        return self

    def em(self) -> EM:
        """The case's EM state, derived from :attr:`embargo_register` (ADR-0122).

        Raises:
            VultronInvalidStateTransitionError: the register breaks one of its
                invariants, so no EM state applies (:func:`derive_em`).
        """
        return derive_em(self.embargo_register.values())

    def for_participant(self, participant: str) -> ReachedParticipant | None:
        """What *participant* has reached, or ``None`` when it is unknown."""
        for reached in self.participants:
            if reached.participant == participant:
                return reached
        return None
