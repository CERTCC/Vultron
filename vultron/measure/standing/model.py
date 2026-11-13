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
from vultron.measure.baselines import ORIGINAL, case_state_query
from vultron.measure.history import PxaName, UnreadableEntry
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


class ParticipantStanding(BaseModel):
    """Where one participant stands at the ledger's last entry.

    Fields:
        participant: The participant's actor.
        roles: Its case roles, upper-cased and sorted.
        joined: ``False`` while it is an inert invitee.
        rm: Its report-management state.
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
            return rm_moves(self.rm, None, None)
        vf, d, _ = cs_dimensions(state)
        return rm_moves(self.rm, vf, d)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cs_moves(self) -> tuple[CSMove, ...]:
        """The case-state events allowed from :attr:`case_state`; none
        without one."""
        state = self.case_state
        if state is None:
            return ()
        return cs_moves(state, self.rm)

    @property
    def case_state_prefix(self) -> tuple[CSEvent, ...]:
        """The case-state history scored, which a :class:`CSMove` extends;
        empty without a sequence."""
        return () if self.score is None else self.score.prefix


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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def em_moves(self) -> tuple[EMMove, ...]:
        """The EM moves allowed from :attr:`em` beside :attr:`pxa`."""
        return em_moves(self.em, self.pxa)


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
        if not (
            self.missing_log_indices
            or self.conflicting_log_indices
            or self.unusable_rows
            or self.unreadable_entries
            or self.register_problem
        ):
            raise ValueError("a standing gap must name at least one hole")
        return self


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
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    end_confirmed: bool
    gap: StandingGap | None = None
    case: CaseStanding | None = None
    participants: list[ParticipantStanding] = Field(default_factory=list)

    @model_validator(mode="after")
    def _a_reading_or_its_gap(self) -> StandingRecord:
        problems: list[str] = []
        if self.gap is not None and (self.case or self.participants):
            problems.append("a record with a gap holds no reading")
        if self.gap is None and self.case is None:
            problems.append("a record with no gap holds the case's standing")
        names = [p.participant for p in self.participants]
        if len(set(names)) != len(names):
            problems.append("a participant is listed more than once")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def for_participant(self, participant: str) -> ParticipantStanding | None:
        """The standing of *participant*, or ``None`` when it has none."""
        for standing in self.participants:
            if standing.participant == participant:
                return standing
        return None
