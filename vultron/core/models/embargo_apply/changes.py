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

"""The two kinds of embargo entry change: a register step and a consent row.

A :class:`RegisterStep` names the register step an act's activity carries;
a :class:`ConsentRowChange` carries one consent row in full (ADR-0122,
ADR-0124).
"""

from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.models._helpers import _as_id
from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import (
    RegisterChange,
    activation_changes,
    proposal_changes,
    rejection_changes,
    termination_changes,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import (
    RegisterTrigger,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import (
    VultronEntryRefusedError,
)


class RegisterStepKind(StrEnum):
    """The register step an act's activity carries (ADR-0122, ADR-0130)."""

    #: The ``Invite(EmbargoEvent)`` that proposes a new embargo.
    PROPOSE = auto()
    #: The owner's ``Add(EmbargoEvent)[target=VulnerabilityCase]``; supersedes the
    #: embargo in force, if any.
    ACTIVATE = auto()
    #: The owner's ``Reject(EmbargoEvent)[target=VulnerabilityCase]``.
    REJECT = auto()
    #: ``Remove(EmbargoEvent)``; cancels every open proposal.
    TERMINATE = auto()
    #: A threat signal (CS ``P``, ``X`` or ``A``) abandoning one open proposal
    #: while no embargo is in force (EMB-16-001).
    CANCEL = auto()


class RegisterStep(ValidatedAssignmentMixin, BaseModel):
    """One register step, as the act's activity names it.

    ``embargo`` is the embargo the activity names: the ``EmbargoEvent`` a
    proposal carries inline (required, so a replica copies the embargo and
    never has to dereference it), or the id of the embargo the step decides
    on.
    ``TERMINATE`` ends that embargo and refuses a register whose embargo in
    force is another one, so a replica never ends "whatever is active
    locally".  ``termination`` is required on ``TERMINATE`` and refused
    otherwise: the what and, when recorded, the why the ``TERMINATED`` entry
    stores.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: RegisterStepKind
    embargo: NonEmptyString | EmbargoEvent
    termination: EmbargoTermination | None = None

    @model_validator(mode="after")
    def _fields_fit_the_kind(self) -> RegisterStep:
        """Refuse a termination or embargo object the kind cannot carry."""
        problems: list[str] = []
        if (self.termination is None) == (
            self.kind == RegisterStepKind.TERMINATE
        ):
            problems.append(
                "a termination is required on TERMINATE and refused otherwise"
            )
        if isinstance(self.embargo, EmbargoEvent) != (
            self.kind == RegisterStepKind.PROPOSE
        ):
            problems.append(
                "PROPOSE carries the embargo object inline, and no other"
                " kind does"
            )
        if problems:
            raise ValueError(
                f"Register step {self.kind} on '{self.embargo_id}': "
                + "; ".join(problems)
            )
        return self

    @property
    def embargo_id(self) -> str:
        """The id of the embargo the step names."""
        embargo_id = _as_id(self.embargo)
        assert embargo_id is not None  # NonEmptyString or an EmbargoEvent
        return embargo_id

    @property
    def threat_signal(self) -> bool:
        """True for the threat-signal ``CANCEL`` (EMB-16-001)."""
        return self.kind == RegisterStepKind.CANCEL

    def changes(self, case: VulnerabilityCase) -> list[RegisterChange]:
        """The register changes this step makes to *case*'s register.

        The register's definition says which entries the step moves; nothing
        here decides.

        Raises:
            VultronEntryRefusedError: a ``TERMINATE`` names an embargo that
                is not the one in force on *case*.
        """
        register = case.embargo_register
        match self.kind:
            case RegisterStepKind.PROPOSE:
                return proposal_changes(self.embargo)
            case RegisterStepKind.ACTIVATE:
                return activation_changes(register, self.embargo_id)
            case RegisterStepKind.REJECT:
                return rejection_changes(self.embargo_id)
            case RegisterStepKind.CANCEL:
                return [
                    RegisterChange(
                        embargo_id=self.embargo_id,
                        trigger=RegisterTrigger.CANCEL,
                    )
                ]
            case RegisterStepKind.TERMINATE:
                return self._termination_changes(case)

    def _termination_changes(
        self, case: VulnerabilityCase
    ) -> list[RegisterChange]:
        if case.active_embargo_id != self.embargo_id:
            raise VultronEntryRefusedError(
                f"TERMINATE names embargo '{self.embargo_id}', but the embargo"
                f" in force on case '{case.id_}' is"
                f" {case.active_embargo_id!r}."
            )
        assert self.termination is not None  # required on TERMINATE
        return termination_changes(case.embargo_register, self.termination)


class ConsentRowVerb(StrEnum):
    """The activity a consent-row entry records (ADR-0122)."""

    #: ``Create(EmbargoConsent)``: the CASE_MANAGER brought the row into
    #: existence, such as an ``UNINVITED`` row when an embargo is proposed.
    CREATE = auto()
    #: ``Update(EmbargoConsent)``: the CASE_MANAGER changed the row.
    UPDATE = auto()


class ConsentRowChange(ValidatedAssignmentMixin, BaseModel):
    """One consent row, as a ``Create`` or ``Update`` entry carries it.

    The row must name the participant actor whose consent it is
    (``attributed_to``): a row committed on its own is found by it.  Its id
    must be the one its embargo and actor derive
    (:meth:`EmbargoConsent.build_id`), so every node holds the row under the
    same id; a carried row under any other id is refused.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verb: ConsentRowVerb
    row: EmbargoConsent

    @model_validator(mode="after")
    def _row_names_its_participant(self) -> ConsentRowChange:
        if self.row.attributed_to is None:
            raise ValueError(
                f"Consent row for embargo '{self.row.embargo_id}' names no"
                " participant actor (attributedTo), so no entry can carry it"
            )
        derived = EmbargoConsent.build_id(
            self.row.embargo_id, self.row.attributed_to
        )
        if self.row.id_ != derived:
            raise ValueError(
                f"Consent row for embargo '{self.row.embargo_id}' carries id"
                f" '{self.row.id_}', not the id its embargo and actor derive"
                f" ('{derived}')"
            )
        return self

    @property
    def actor_id(self) -> str:
        """The participant actor whose row this is."""
        assert self.row.attributed_to is not None  # checked at construction
        return self.row.attributed_to

    @classmethod
    def answer(
        cls, *, embargo_id: str, actor_id: str, accept: bool
    ) -> ConsentRowChange:
        """The row change a participant's answer states (ADR-0122).

        ``Accept(Invite(EmbargoEvent))`` states the sender's row for the
        embargo is ``AGREED``, ``Reject`` that it is ``DECLINED``; a row that
        leaves ``INVITED`` carries no deadline (CM-28-013).  The answer's own
        entry carries this change, and no second entry records it
        (CLP-07-013), so the CASE_MANAGER and every replica read the same
        change from the same activity.
        """
        return cls(
            verb=ConsentRowVerb.UPDATE,
            row=EmbargoConsent(
                embargo_id=embargo_id,
                state=(
                    EmbargoConsentState.AGREED
                    if accept
                    else EmbargoConsentState.DECLINED
                ),
                attributed_to=actor_id,
            ),
        )


#: A change one embargo entry carries.
EmbargoChange = RegisterStep | ConsentRowChange
