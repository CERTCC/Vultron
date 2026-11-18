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
"""Each desideratum of a vendor's scope, and whether its case has met it.

:func:`desiderata_standing` reads one status for each desideratum of
:func:`~vultron.measure.baselines.scope_desiderata`, the list move advice
sums too: an original desideratum's from the case-state sequence's
completions, an extended one's from its term in the vendor's case score
(:mod:`~vultron.measure.scoring.extended`).  Each status agrees with the
score it is read from, so the page and the score cannot disagree.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vultron.core.states.cs_invariants import CSEvent
from vultron.measure.baselines import (
    Desideratum,
    EventKind,
    Group,
    ordered_cs_events,
    scope_desiderata,
)
from vultron.measure.scoring import (
    ExtendedScore,
    SequenceScore,
    TermScore,
    UnscoredScope,
    met_desiderata,
)
from vultron.primitives import NonEmptyString


class DesideratumStatus(StrEnum):
    """Whether a vendor's case has met a desideratum (ADR-0190)."""

    #: Nothing left can break it: every valid completion of the sequence
    #: meets an original desideratum, and every end the vendor's walk can
    #: reach meets an extended one or never enters its scope.
    MET = "met"
    #: Nothing left can meet it: no valid completion, or no reachable end,
    #: meets it.
    BROKEN = "broken"
    #: Some completions or ends meet it and some do not: the moves still to
    #: come decide it.
    OPEN = "open"
    #: It orders an event the case's source cannot observe, so the case
    #: cannot say whether it is met (CRD-02-005).
    UNKNOWN = "unknown"
    #: An extended desideratum of a vendor whose case stands in no state of
    #: the one-vendor model, so no walk reads it (``UnscoredScope``).
    UNSCORED = "unscored"


class DesideratumStanding(BaseModel):
    """One desideratum of a vendor's scope and whether its case has met it.

    Fields:
        notation: The desideratum as the Measuring CVD pages print it.  The
            first of a group of equivalent desiderata stands for the group
            (ADR-0200 rule 2).
        group: Its group on ``process_model_desiderata.md``.
        before: The event the desideratum wants first.
        after: The event it wants after *before*.
        status: Met, broken, still open, unknown when it orders an event
            the source cannot observe, or unscored when no walk reads it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    notation: NonEmptyString
    group: Group
    before: EventKind
    after: EventKind
    status: DesideratumStatus


def _status(meeting: int, met_by: list[set[Desideratum]]) -> DesideratumStatus:
    """Met when every completion meets it, broken when none does, else
    open."""
    if meeting == len(met_by):
        return DesideratumStatus.MET
    if meeting == 0:
        return DesideratumStatus.BROKEN
    return DesideratumStatus.OPEN


def _chance_status(term: TermScore) -> DesideratumStatus:
    """Met when the walk meets *term* from every end it can reach, broken
    when from none, else open.

    *term*'s expected outcome is 1 exactly when every reachable end meets it
    or never enters its scope, and 0 exactly when none does, since every
    step the walk can take has a chance above 0.
    """
    if term.met == 1:
        return DesideratumStatus.MET
    if term.met == 0:
        return DesideratumStatus.BROKEN
    return DesideratumStatus.OPEN


def _terms(extended: ExtendedScore | UnscoredScope) -> dict[str, TermScore]:
    if isinstance(extended, UnscoredScope):
        return {}
    return {
        t.notation: t for t in (*extended.end.terms, *extended.embargo.terms)
    }


def _standing(
    desideratum: Desideratum, status: DesideratumStatus
) -> DesideratumStanding:
    (ordering,) = desideratum.query.orderings
    return DesideratumStanding(
        notation=desideratum.notation,
        group=desideratum.group,
        before=ordering.before.kind,
        after=ordering.after.kind,
        status=status,
    )


def desiderata_standing(
    score: SequenceScore,
    extended: ExtendedScore | UnscoredScope,
    unobservable: frozenset[CSEvent] = frozenset(),
) -> tuple[DesideratumStanding, ...]:
    """Each desideratum of a vendor's scope and its status, in the order of
    :func:`~vultron.measure.baselines.scope_desiderata`.

    A desideratum that orders an event in *unobservable* is unknown: the
    sequence reads that event as not yet happened, which the source cannot
    say (CRD-02-005).  Of the rest, an original one is read from *score*'s
    completions: met when every completion meets it, broken when none does,
    and open otherwise.  An extended one is read from its term in
    *extended*, the vendor's walk from where it stands, in the same three
    ways (:func:`_chance_status`), and is unscored when *extended* is an
    :class:`~vultron.measure.scoring.UnscoredScope`.  Each status agrees
    with the score it is read from.

    Raises:
        ValueError: *extended* holds no term for an extended desideratum of
            the scope, so it was not scored from the same list.
    """
    met_by = [set(met_desiderata(c.history)) for c in score.completions]
    terms = _terms(extended)
    standings = []
    for desideratum in scope_desiderata():
        if ordered_cs_events(desideratum) & unobservable:
            status = DesideratumStatus.UNKNOWN
        elif desideratum.group is Group.ORIGINAL:
            status = _status(sum(desideratum in met for met in met_by), met_by)
        elif isinstance(extended, UnscoredScope):
            status = DesideratumStatus.UNSCORED
        elif desideratum.notation in terms:
            status = _chance_status(terms[desideratum.notation])
        else:
            raise ValueError(
                f"the vendor's score has no term for {desideratum.notation}"
            )
        standings.append(_standing(desideratum, status))
    return tuple(standings)
