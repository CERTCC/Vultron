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

"""The one apply function for embargo and consent entries (ADR-0124).

A ledger entry records one AS2 activity with its object, so the number of
entries follows the number of activity/object pairs, not the number of stored
objects an activity changes (ADR-0122, CLP-07-013).  Two kinds of entry change
the embargo part of the case file:

- **A register step.**  The act's own activity carries the whole step: the
  owner's ``Accept(EmbargoEvent, target=Case)`` is ``ACTIVATE``, with the
  ``SUPERSEDE`` of the embargo in force; ``Remove(EmbargoEvent, target=Case)``
  is ``TERMINATE``, with the ``CANCEL`` of every open proposal;
  ``Reject(EmbargoEvent, target=Case)`` is ``REJECT``; the ``Invite`` that
  proposes an embargo is ``PROPOSE``; and a threat signal abandoning an open
  proposal with no embargo in force is ``CANCEL``.  :class:`RegisterStep`
  names the step; the register's definition says which entries it moves.
- **A consent row.**  A row belongs to a participant, another object, so each
  row the CASE_MANAGER brings into existence or changes is its own
  CASE_MANAGER activity, ``Create(EmbargoConsent)`` or
  ``Update(EmbargoConsent)``, carrying the row in full
  (:class:`ConsentRowChange`).

:func:`apply_embargo_change` applies one of them to an
:class:`EmbargoCaseFile` and returns the case file after it.  The CASE_MANAGER
and every replica call it, so both make the same checks (EMB-18-006).  It
copies: it writes what the entry carries, or performs the step the entry
names, after checking the starting state the entry implies; it mints no id,
reads no clock, reads no store, and runs no lifecycle logic (CM-23-016).  The
register step keeps ADR-0122's invariants and ADR-0130's EM transition check
after every entry, because it goes through
:func:`~vultron.core.models.embargo_register.apply_register_step`.  EM is never
written: it is derived from the register.  An entry whose starting state does
not match is refused with :class:`~vultron.errors.VultronEntryRefusedError`,
and the inputs are left as they were.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum, auto
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.models._helpers import _as_id
from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
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
    FINAL_REGISTER_STATUSES,
    EmbargoRegisterStatus,
    RegisterTrigger,
    register_status_after,
    register_trigger_is_legal,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
    consent_after,
    consent_trigger_is_legal,
)
from vultron.errors import (
    VultronEntryRefusedError,
    VultronInvalidStateTransitionError,
)


class RegisterStepKind(StrEnum):
    """The register step an act's activity carries (ADR-0122, ADR-0130)."""

    #: The ``Invite(EmbargoEvent)`` that proposes a new embargo.
    PROPOSE = auto()
    #: The owner's ``Accept(EmbargoEvent, target=Case)``; supersedes the
    #: embargo in force, if any.
    ACTIVATE = auto()
    #: The owner's ``Reject(EmbargoEvent, target=Case)``.
    REJECT = auto()
    #: ``Remove(EmbargoEvent, target=Case)``; cancels every open proposal.
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
    def _fields_fit_the_kind(self) -> "RegisterStep":
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
    def _row_names_its_participant(self) -> "ConsentRowChange":
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
    ) -> "ConsentRowChange":
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


def _frozen_participants(
    participants: Mapping[str, CaseParticipant],
) -> Mapping[str, CaseParticipant]:
    return MappingProxyType(dict(participants))


@dataclass(frozen=True)
class EmbargoCaseFile:
    """The part of the case file embargo entries change (ADR-0124).

    *case* holds the embargo register; *participants* holds the participant
    records, keyed by the actor id each is attributed to, that hold the
    consent rows.  Only these are read: the apply function reads no store.
    Applying an entry returns a new case file and never changes this one.
    """

    case: VulnerabilityCase
    participants: Mapping[str, CaseParticipant] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "participants", _frozen_participants(self.participants)
        )


def _apply_register_step(
    case_file: EmbargoCaseFile, step: RegisterStep
) -> EmbargoCaseFile:
    case = case_file.case.model_copy(deep=True)
    try:
        case.apply_embargo_register_step(
            step.changes(case), threat_signal=step.threat_signal
        )
    except VultronEntryRefusedError:
        raise
    except (VultronInvalidStateTransitionError, ValueError) as exc:
        # ValueError: the register assignment's own validation (a pydantic
        # ValidationError) refused the result, which is a refusal too.
        raise VultronEntryRefusedError(
            f"{step.kind} of embargo '{step.embargo_id}' does not apply to"
            f" case '{case.id_}': {exc}"
        ) from exc
    return replace(case_file, case=case)


def _participant_for(
    case_file: EmbargoCaseFile, change: ConsentRowChange
) -> CaseParticipant:
    case = case_file.case
    participant = case_file.participants.get(change.actor_id)
    held_id = case.actor_participant_index.get(change.actor_id)
    if participant is None or held_id != participant.id_:
        raise VultronEntryRefusedError(
            f"case '{case.id_}' holds no participant record for"
            f" '{change.actor_id}', so its consent row for embargo"
            f" '{change.row.embargo_id}' cannot be written"
        )
    return participant


def _require_open_entry(case: VulnerabilityCase, embargo_id: str) -> None:
    """Refuse a row change for an embargo the register lacks or has closed."""
    entry = case.embargo_register_entry(embargo_id)
    if entry is None:
        raise VultronEntryRefusedError(
            f"case '{case.id_}' holds no register entry for embargo"
            f" '{embargo_id}', so no consent row for it can be written"
        )
    if entry.status in FINAL_REGISTER_STATUSES:
        raise VultronEntryRefusedError(
            f"embargo '{embargo_id}' is {entry.status} on case '{case.id_}',"
            " so its consent rows accept no change (ADR-0122)"
        )


def _one_move(held: EmbargoConsentState, carried: EmbargoConsentState) -> bool:
    """True when one consent trigger moves *held* to *carried* (CM-18-003)."""
    return any(
        consent_trigger_is_legal(held, trigger)
        and consent_after(held, trigger) == carried
        for trigger in PEC_Trigger
    )


def _row_problem(
    held: EmbargoConsent | None, change: ConsentRowChange
) -> str | None:
    """Why *change* does not start from *held*, or ``None`` when it does."""
    carried = change.row
    if change.verb == ConsentRowVerb.CREATE:
        if held is not None:
            return "the participant already holds a row for it"
        if carried.state != EmbargoConsentState.UNINVITED and not _one_move(
            EmbargoConsentState.UNINVITED, carried.state
        ):
            return f"a new row cannot start {carried.state}"
        return None
    if held is None:
        return "the participant holds no row for it to update"
    if (held.state, held.rsvp_deadline) == (
        carried.state,
        carried.rsvp_deadline,
    ):
        return "the carried row changes nothing"
    if held.state == carried.state:
        # A fresh invitation's deadline on a row still waiting (CM-28-013).
        return (
            None
            if carried.state == EmbargoConsentState.INVITED
            else f"only an INVITED row's deadline changes in place, not a"
            f" {carried.state} row's"
        )
    if not _one_move(held.state, carried.state):
        return f"no consent transition moves {held.state} to {carried.state}"
    return None


def _apply_consent_row(
    case_file: EmbargoCaseFile, change: ConsentRowChange
) -> EmbargoCaseFile:
    participant = _participant_for(case_file, change)
    embargo_id = change.row.embargo_id
    _require_open_entry(case_file.case, embargo_id)
    held = participant.held_row(embargo_id)
    problem = _row_problem(held, change)
    if problem is not None:
        raise VultronEntryRefusedError(
            f"{change.verb} of '{change.actor_id}''s consent row for embargo"
            f" '{embargo_id}' does not apply: {problem}"
        )
    copied = participant.model_copy(deep=True)
    copied.copy_consent_row(change.row)
    return replace(
        case_file,
        participants={**case_file.participants, change.actor_id: copied},
    )


def apply_embargo_change(
    case_file: EmbargoCaseFile, change: EmbargoChange
) -> EmbargoCaseFile:
    """Apply one embargo entry's *change* to *case_file*; return the result.

    The one apply function for the embargo register and consent rows,
    shared by the CASE_MANAGER's trial apply and apply and by every replica
    (ADR-0124, CM-23-016, EMB-18-006).  A :class:`RegisterStep` performs the
    step the act's activity names, through
    :meth:`VulnerabilityCase.apply_embargo_register_step`, so the register
    invariants and the EM transition check hold after the entry.  A
    :class:`ConsentRowChange` writes the row it carries, after checking that
    the participant is on the case, the embargo is in the register and not
    final, and the row starts where the entry implies: a ``Create`` needs no
    row yet, an ``Update`` a held row that one consent transition (or a
    fresh deadline on an ``INVITED`` row) moves to the carried one.

    Reads only *case_file*; mints no id, reads no clock and runs no
    lifecycle logic.  *case_file* is left as it was.

    Raises:
        VultronEntryRefusedError: the entry does not apply to *case_file*.
    """
    if isinstance(change, RegisterStep):
        return _apply_register_step(case_file, change)
    return _apply_consent_row(case_file, change)


#: The status a register step leaves the entry it names in.
_STEP_RESULT: Mapping[RegisterStepKind, EmbargoRegisterStatus] = (
    MappingProxyType(
        {
            RegisterStepKind.PROPOSE: EmbargoRegisterStatus.PROPOSED,
            RegisterStepKind.ACTIVATE: EmbargoRegisterStatus.ACTIVE,
            RegisterStepKind.REJECT: EmbargoRegisterStatus.REJECTED,
            RegisterStepKind.TERMINATE: EmbargoRegisterStatus.TERMINATED,
            RegisterStepKind.CANCEL: EmbargoRegisterStatus.CANCELLED,
        }
    )
)


def change_is_in_place(
    case_file: EmbargoCaseFile, change: EmbargoChange
) -> bool:
    """True when *case_file* already holds what applying *change* writes.

    For a replica re-applying an entry it had applied but not yet stored
    (its case saved, the process stopped before the entry was persisted):
    the entry is then an idempotent no-op, not a refusal, as every other
    replica slot treats a re-delivered entry.  A register step is in place
    when the entry it names holds the status the step leaves it in (the
    step's other moves were saved with it); a consent row is in place when
    the participant holds exactly the carried row.  Reads only *case_file*.

    The CASE_MANAGER does not use this: its trial apply refuses an entry
    that would change nothing, so it never commits one.
    """
    case = case_file.case
    if isinstance(change, RegisterStep):
        entry = case.embargo_register_entry(change.embargo_id)
        return (
            entry is not None
            and entry.status == _STEP_RESULT[change.kind]
            and entry.termination == change.termination
        )
    participant = case_file.participants.get(change.actor_id)
    if participant is None or (
        case.actor_participant_index.get(change.actor_id) != participant.id_
    ):
        return False
    return participant.held_row(change.row.embargo_id) == change.row


def _register_successors(
    status: EmbargoRegisterStatus,
) -> frozenset[EmbargoRegisterStatus]:
    """Every status a register entry at *status* can reach, *status* excluded."""
    reached: set[EmbargoRegisterStatus] = set()
    frontier = [status]
    while frontier:
        current = frontier.pop()
        for trigger in RegisterTrigger:
            if register_trigger_is_legal(current, trigger):
                after = register_status_after(current, trigger)
                if after not in reached:
                    reached.add(after)
                    frontier.append(after)
    return frozenset(reached)


def _consent_successors(
    state: EmbargoConsentState,
) -> frozenset[EmbargoConsentState]:
    """Every state a consent row at *state* reaches in one move or more."""
    reached: set[EmbargoConsentState] = set()
    frontier = [state]
    while frontier:
        current = frontier.pop()
        for trigger in PEC_Trigger:
            if consent_trigger_is_legal(current, trigger):
                after = consent_after(current, trigger)
                if after not in reached:
                    reached.add(after)
                    frontier.append(after)
    return frozenset(reached)


def case_file_is_past(
    case_file: EmbargoCaseFile, change: EmbargoChange
) -> bool:
    """True when *case_file* has already moved on from what *change* writes.

    For a replica whose seed was taken after the entry (CM-23-016: the
    replica is its seed plus the entries since).  A replica seeded with the
    case still replays the ledger from genesis over that seed, so each
    effect moves forward only (ADR-0114): an entry the seed is already past
    is an idempotent no-op, not a refusal.  The caller asks only once
    :func:`apply_embargo_change` has refused the entry, so a legal move is
    always applied.

    A register step is past when the entry it names holds a status the
    step's result leads to (the register is acyclic).  A consent row is past
    when the participant already holds a row for the embargo and either the
    embargo's register entry is final (its rows were frozen after every
    change committed to them, ADR-0122), the entry is a ``Create`` (a row is
    created once), or the held state is one the carried state leads to.
    Anything else, such as a missing participant, register entry or row, is
    a real gap and stays refused.  Reads only *case_file*.
    """
    case = case_file.case
    embargo_id = (
        change.embargo_id
        if isinstance(change, RegisterStep)
        else change.row.embargo_id
    )
    entry = case.embargo_register_entry(embargo_id)
    if entry is None:
        return False
    if isinstance(change, RegisterStep):
        return entry.status in _register_successors(_STEP_RESULT[change.kind])
    participant = case_file.participants.get(change.actor_id)
    if participant is None or (
        case.actor_participant_index.get(change.actor_id) != participant.id_
    ):
        return False
    held = participant.held_row(embargo_id)
    if held is None:
        return False
    return (
        entry.status in FINAL_REGISTER_STATUSES
        or change.verb == ConsentRowVerb.CREATE
        or held.state in _consent_successors(change.row.state)
    )


def changed_objects(
    before: EmbargoCaseFile, after: EmbargoCaseFile
) -> list[VulnerabilityCase | CaseParticipant]:
    """The stored objects *after* holds that differ from *before*.

    The case first, then participant records in actor order: what a caller
    persists once the entries that made the changes have committed.
    """
    objects: list[VulnerabilityCase | CaseParticipant] = []
    if after.case is not before.case:
        objects.append(after.case)
    objects.extend(
        record
        for actor_id, record in sorted(after.participants.items())
        if before.participants.get(actor_id) is not record
    )
    return objects


__all__ = [
    "ConsentRowChange",
    "ConsentRowVerb",
    "EmbargoCaseFile",
    "EmbargoChange",
    "RegisterStep",
    "RegisterStepKind",
    "apply_embargo_change",
    "case_file_is_past",
    "change_is_in_place",
    "changed_objects",
]
