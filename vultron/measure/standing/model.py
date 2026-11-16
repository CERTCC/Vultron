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
"""The standing record: where a case stands at its ledger's last entry.

A :class:`StandingRecord` holds, for the case, its EM state and public state
(:class:`CaseStanding`), and for each participant its report-management
state and, for a vendor with a case-state sequence, its compound case state
and that sequence's score (:class:`ParticipantStanding`).  EM is one state
for the case, derived from its embargo register (ADR-0122); each
participant stands in it.

Everything that follows from the states is read from them, never stored
beside them, so it cannot disagree: each desideratum's status is read from
the score's completions (:class:`DesideratumStanding`), and each allowed move
from the states (:mod:`~vultron.measure.standing.moves`).

A ledger with a hole yields no reading at all, only the
:class:`StandingGap` that names the hole: a measure over a history with a
hole is wrong, not imprecise (CEH-02-006).
"""

from __future__ import annotations

from enum import StrEnum
from fractions import Fraction

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_dimensions,
    replay_cs_history,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.measure.baselines import ORIGINAL, case_state_query
from vultron.measure.history import (
    CaseEventHistory,
    PxaName,
    UnreadableEntry,
)
from vultron.measure.ledger import UnusableRow
from vultron.measure.scoring import SequenceScore, met_desiderata
from vultron.measure.sequences import UnprojectableParticipant
from vultron.measure.standing.moves import (
    CSMove,
    CSName,
    EMMove,
    RMMove,
    cs_moves,
    em_moves,
    rm_moves,
)
from vultron.primitives import NonEmptyString


class DesideratumStatus(StrEnum):
    """Whether a vendor's case has met a desideratum (ADR-0190)."""

    #: Every valid completion of the sequence meets it: nothing left can
    #: break it.
    MET = "met"
    #: No valid completion meets it: it is already broken.
    BROKEN = "broken"
    #: Some completions meet it and some do not: the moves still to come
    #: decide it.
    OPEN = "open"


class DesideratumStanding(BaseModel):
    """One original desideratum and whether a vendor's case has met it.

    Fields:
        notation: The desideratum as the Measuring CVD pages print it.
        before: The case-state event the desideratum wants first.
        after: The case-state event it wants after *before*.
        status: Met, broken or still open.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    notation: NonEmptyString
    before: CSEvent
    after: CSEvent
    status: DesideratumStatus


def desiderata_standing(
    score: SequenceScore,
) -> tuple[DesideratumStanding, ...]:
    """Each original desideratum's status, read from *score*'s completions.

    A desideratum every completion meets is met, one none meets is broken,
    and any other is open, so the status agrees with the score it is read
    from.  In the catalog order of :data:`~vultron.measure.baselines.ORIGINAL`.
    """
    met_by = [set(met_desiderata(c.history)) for c in score.completions]
    standings = []
    for desideratum in ORIGINAL:
        meeting = sum(desideratum in met for met in met_by)
        if meeting == len(met_by):
            status = DesideratumStatus.MET
        elif meeting == 0:
            status = DesideratumStatus.BROKEN
        else:
            status = DesideratumStatus.OPEN
        (ordering,) = case_state_query(desideratum.query).orderings
        standings.append(
            DesideratumStanding(
                notation=desideratum.notation,
                before=ordering.before,
                after=ordering.after,
                status=status,
            )
        )
    return tuple(standings)


class CaseStanding(BaseModel):
    """Where the case itself stands at the ledger's last entry.

    Fields:
        em: The case's EM state, derived from its embargo register
            (ADR-0122).  Every participant stands in this one state.
        pxa: The case's public state, as the CASE_MANAGER adopted it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    em: EM
    pxa: PxaName


class ParticipantStanding(BaseModel):
    """Where one participant stands at the ledger's last entry.

    Fields:
        participant: The participant's actor.
        roles: Its case roles, upper-cased and sorted.
        joined: ``False`` while it is an inert invitee.
        rm: Its report-management state.
        case: The case's EM and public state, which every participant stands
            in.
        score: The score of its case-state sequence, for a vendor with one
            (:func:`~vultron.measure.scoring.score_sequence`).  The prefix
            scored is the history an allowed :class:`CSMove` extends.
        unscored: Why it has no case-state sequence, for every other
            participant (CEH-05-007).  Exactly one of *score* and *unscored*
            is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participant: NonEmptyString
    roles: tuple[NonEmptyString, ...] = ()
    joined: bool = True
    rm: RM
    case: CaseStanding
    score: SequenceScore | None = None
    unscored: UnprojectableParticipant | None = None

    @model_validator(mode="after")
    def _scored_or_says_why_not(self) -> ParticipantStanding:
        problems: list[str] = []
        if (self.score is None) == (self.unscored is None):
            problems.append(
                "a participant has either a score or the reason it has none"
            )
        if (
            self.unscored is not None
            and self.unscored.participant != self.participant
        ):
            problems.append(
                f"the reason given is {self.unscored.participant}'s, not"
                f" {self.participant}'s"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def case_state(self) -> CSName | None:
        """The compound case state its scored sequence reaches; ``None``
        with no sequence."""
        if self.score is None:
            return None
        return replay_cs_history(self.score.prefix)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def desiderata(self) -> tuple[DesideratumStanding, ...]:
        """Each original desideratum met, broken or open; none unscored."""
        if self.score is None:
            return ()
        return desiderata_standing(self.score)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rm_moves(self) -> tuple[RMMove, ...]:
        """The report-management moves allowed from :attr:`rm`."""
        state = self.case_state
        if state is None:
            return rm_moves(self.participant, self.rm, None, None)
        vf, d, _ = cs_dimensions(state)
        return rm_moves(self.participant, self.rm, vf, d)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cs_moves(self) -> tuple[CSMove, ...]:
        """The case-state events allowed from :attr:`case_state`; none
        without one."""
        state = self.case_state
        if state is None:
            return ()
        return cs_moves(self.participant, state, self.rm)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def em_moves(self) -> tuple[EMMove, ...]:
        """The EM moves its roles allow it to make from the case's EM
        state (:data:`~vultron.core.states.em.EM_TRIGGER_ROLES`)."""
        return em_moves(
            self.participant, self.cvd_roles, self.case.em, self.case.pxa
        )

    @property
    def cvd_roles(self) -> tuple[CVDRole, ...]:
        """Its :attr:`roles` that name a :class:`CVDRole`."""
        return tuple(
            CVDRole[role] for role in self.roles if role in CVDRole.__members__
        )

    @property
    def case_state_prefix(self) -> tuple[CSEvent, ...]:
        """The case-state history scored, which a :class:`CSMove` extends;
        empty without a sequence."""
        return () if self.score is None else self.score.prefix


class DesideratumChange(BaseModel):
    """One vendor's change in one desideratum's expected outcome.

    Fields:
        vendor: The vendor the desideratum is scored for.
        other_vendor: The second vendor of the two-vendor desideratum
            ``V_i ≺ F_j``; ``None`` for every other desideratum.
        notation: The desideratum as the Measuring CVD pages print it.
        change: The expected outcome after the move minus before it
            (:func:`~vultron.measure.baselines.outcome_change`): positive
            when the move makes the desideratum likelier to be met than
            leaving the case to chance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vendor: NonEmptyString
    other_vendor: NonEmptyString | None = None
    notation: NonEmptyString
    change: Fraction


class ScoredMove(BaseModel):
    """One allowed move, with each vendor's change in expected outcome.

    Fields:
        move: The move, naming the participant who can make it.
        changes: Each vendor's change in each desideratum's expected
            outcome if the move came next, for a move that changes state
            and names a step of the case's joint model.
        unscored: Why a move that changes state carries no number: the case
            has no vendor, or the move moves no vendor's state.

    A move that keeps every state, as a second embargo proposal while one is
    open does, is :attr:`advice`: it carries neither a number nor a reason.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: RMMove | CSMove | EMMove
    changes: tuple[DesideratumChange, ...] | None = None
    unscored: NonEmptyString | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def advice(self) -> bool:
        """Whether the move keeps every state, so it is advice with no
        number."""
        return self.move.source == self.move.destination

    @model_validator(mode="after")
    def _a_number_or_why_not(self) -> ScoredMove:
        if self.advice:
            if self.changes is not None or self.unscored is not None:
                raise ValueError("advice carries no number and no reason")
        elif (self.changes is None) == (self.unscored is None):
            raise ValueError(
                "a move that changes state carries its changes or the"
                " reason it has none"
            )
        return self


class StandingGap(BaseModel):
    """What keeps a ledger from yielding a standing record (CEH-02-006).

    At least one field is set; each names one kind of hole.

    Fields:
        missing_log_indices: Indices no copy of the ledger supplied.
        conflicting_log_indices: Indices at which the copies disagree.
        unusable_rows: Rows naming the case that could not be placed; any
            may be an entry the ledger lacks.
        unreadable_entries: Entries, or records in one, the history could
            not read, so a state they record may be missing.
        register_problem: Why the embargo register the ledger records holds
            no EM state: it breaks a register invariant.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    missing_log_indices: list[int] = Field(default_factory=list)
    conflicting_log_indices: list[int] = Field(default_factory=list)
    unusable_rows: list[UnusableRow] = Field(default_factory=list)
    unreadable_entries: list[UnreadableEntry] = Field(default_factory=list)
    register_problem: NonEmptyString | None = None

    @model_validator(mode="after")
    def _names_a_hole(self) -> StandingGap:
        if not any(getattr(self, name) for name in type(self).model_fields):
            raise ValueError("a standing gap must name at least one hole")
        return self

    @classmethod
    def of(
        cls, history: CaseEventHistory, register_problem: str | None = None
    ) -> StandingGap | None:
        """The holes in *history*, and *register_problem*; ``None`` with
        none."""
        holes = {
            "missing_log_indices": history.missing_log_indices,
            "conflicting_log_indices": history.conflicting_log_indices,
            "unusable_rows": history.unusable_rows,
            "unreadable_entries": history.unreadable_entries,
            "register_problem": register_problem,
        }
        return cls.model_validate(holes) if any(holes.values()) else None


class StandingRecord(BaseModel):
    """Where one case stands at its ledger's last entry (ADR-0190, level 1).

    Fields:
        case_id: The case.
        end_confirmed: Whether the entries prove nothing follows the last
            one.  ``False`` means the case may have moved on since; the
            record is where it stood at the last entry the input holds.
        gap: The holes that keep the ledger from a reading, or ``None``.
        case: The case's own standing; ``None`` exactly when *gap* is set.
        participants: Each participant's standing, in the order the ledger
            first records each; empty when *gap* is set.
        moves: Every participant's allowed moves, in participant order,
            each with each vendor's change in expected outcome; empty when
            *gap* is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    end_confirmed: bool
    gap: StandingGap | None = None
    case: CaseStanding | None = None
    participants: list[ParticipantStanding] = Field(default_factory=list)
    moves: list[ScoredMove] = Field(default_factory=list)

    @model_validator(mode="after")
    def _a_reading_or_its_gap(self) -> StandingRecord:
        problems: list[str] = []
        if self.gap is not None and (
            self.case or self.participants or self.moves
        ):
            problems.append("a record with a gap holds no reading")
        if self.gap is None and self.case is None:
            problems.append("a record with no gap holds the case's standing")
        names = [p.participant for p in self.participants]
        if len(set(names)) != len(names):
            problems.append("a participant is listed more than once")
        problems.extend(
            f"{p.participant} stands in another case state than the case's"
            for p in self.participants
            if p.case != self.case
        )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def for_participant(self, participant: str) -> ParticipantStanding | None:
        """The standing of *participant*, or ``None`` when it has none."""
        for standing in self.participants:
            if standing.participant == participant:
                return standing
        return None
