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

"""A case's score for each scope, and how evenly its vendors fall (ADR-0182).

A case is never scored as one sequence: each vendor's sequence is scored
on its own, and several vendors' sequences are never combined (CEH-05-006).
:func:`score_case` scores every scope of ADR-0200: each vendor, on
the twelve original desiderata and its own extended ones, and each
case-wide group of extended desiderata, the embargo group and the
multi-party group (:mod:`~vultron.measure.scoring.extended`).  The case
reports every vendor's score, and for each of the expected, best and worst
scores their unweighted median and spread across the vendors
(:class:`AcrossVendors`).

The spread is the highest score minus the lowest.  It reads as how evenly the
case served its vendors, not as a statistical sample: the public-awareness,
exploit and attack events are shared by every vendor, so the vendors' scores
are not independent draws, and a variance or standard deviation would
describe a sampling distribution the case does not have.  The range assumes
nothing about one, and it says directly how far apart the best-served and
the worst-served vendor are.  It measures evenness across vendors, not
across users: weighting by users or risk is an open question (ADR-0182).

A participant with no sequence keeps its reason (CEH-05-007) and gets no
score.  A two-party case has one vendor, so its summary is that vendor's
score with zero spread.  A vendor whose extended desiderata have no score
(:class:`~vultron.measure.scoring.model.UnscoredScope`) has no total, so
the case has no median and spread for the score it lacks: a median over the
other vendors would read as one over all of them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from vultron.measure.history import CaseEventHistory
from vultron.measure.scoring.extended import (
    embargo_scope,
    multi_party_scope,
    vendor_scope,
)
from vultron.measure.scoring.model import (
    ScopeScore,
    UnscoredScope,
    VendorScore,
)
from vultron.measure.scoring.record import CaseRecord
from vultron.measure.scoring.score import score_prefix
from vultron.measure.sequences import (
    UnprojectableParticipant,
    case_state_sequences,
    one_answer_problems,
)
from vultron.primitives import NonEmptyString


def _median(values: list[Fraction]) -> Fraction:
    """The median of *values*, exact; the mean of the middle two when even."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


class AcrossVendors(BaseModel):
    """One score's unweighted median and spread across a case's vendors.

    Fields:
        median: The median of the vendors' scores; with an even number of
            vendors, the mean of the middle two.
        lowest: The lowest vendor's score.
        highest: The highest vendor's score.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    median: Fraction
    lowest: Fraction
    highest: Fraction

    @model_validator(mode="after")
    def _median_lies_between_the_ends(self) -> AcrossVendors:
        if not self.lowest <= self.median <= self.highest:
            raise ValueError(
                f"the median {self.median} is not between the lowest"
                f" {self.lowest} and the highest {self.highest}"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def spread(self) -> Fraction:
        """The highest score minus the lowest: zero when every vendor ties."""
        return self.highest - self.lowest

    @classmethod
    def of(cls, scores: Iterable[Fraction]) -> AcrossVendors:
        """The median and spread of *scores*, one per vendor.

        Raises:
            ValueError: *scores* is empty; no vendor, no median.
        """
        values = list(scores)
        if not values:
            raise ValueError("a median and spread need at least one vendor")
        return cls(
            median=_median(values), lowest=min(values), highest=max(values)
        )


class CaseScoreSummary(BaseModel):
    """A case's score for each scope, its vendors summarized (ADR-0182).

    The medians and spreads are read from the vendors' scores, never stored
    beside them, so they cannot disagree.

    Fields:
        case_id: The case.
        vendors: Each vendor's score, in the order of the sequences it was
            scored from; :func:`score_case` keeps their vendor-awareness
            order.
        unprojectable: Every participant with no sequence, with its reason
            (CEH-05-007), unscored.
        embargo: The case-wide embargo group, or why it has no score.
        multi_party: The case-wide multi-party group, or why it has no
            score; ``None`` when the case has no vendor.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    vendors: tuple[VendorScore, ...] = ()
    unprojectable: tuple[UnprojectableParticipant, ...] = ()
    embargo: ScopeScore | UnscoredScope
    multi_party: ScopeScore | UnscoredScope | None = None

    @model_validator(mode="after")
    def _one_answer_per_participant(self) -> CaseScoreSummary:
        """Refuse a participant scored twice, or both scored and unscored."""
        problems = one_answer_problems(
            "scored",
            [v.participant for v in self.vendors],
            [u.participant for u in self.unprojectable],
        )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _across(
        self, read: Callable[[VendorScore], Fraction | None]
    ) -> AcrossVendors | None:
        """*read* of each vendor's score, across the vendors; ``None`` with
        no vendor, or a vendor with no total."""
        values = [read(vendor) for vendor in self.vendors]
        if not values or None in values:
            return None
        return AcrossVendors.of(v for v in values if v is not None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expected(self) -> AcrossVendors | None:
        """The vendors' expected scores across the case."""
        return self._across(lambda vendor: vendor.expected)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def best(self) -> AcrossVendors | None:
        """The vendors' best scores across the case."""
        return self._across(lambda vendor: vendor.best)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def worst(self) -> AcrossVendors | None:
        """The vendors' worst scores across the case."""
        return self._across(lambda vendor: vendor.worst)

    def for_participant(self, participant: str) -> VendorScore | None:
        """The score of *participant*, or ``None`` when it has none."""
        for vendor in self.vendors:
            if vendor.participant == participant:
                return vendor
        return None


def score_case(history: CaseEventHistory) -> CaseScoreSummary:
    """Score every scope of the case *history* records (ADR-0200).

    The history is projected onto one sequence per vendor (CEH-05).  Every
    vendor is scored alone: its sequence through its completions
    (:func:`.score_prefix`), and its extended desiderata on the one-vendor
    walk from where it stands.  No case-wide sequence is built
    (CEH-05-006).  Every unprojectable participant is carried over with its
    reason (CEH-05-007).
    """
    sequences = case_state_sequences(history)
    record = CaseRecord(history, sequences.sequences)
    return CaseScoreSummary(
        case_id=history.case_id,
        vendors=tuple(
            VendorScore(
                participant=s.participant,
                score=score_prefix(s.kinds),
                extended=vendor_scope(record, s.participant),
            )
            for s in sequences.sequences
        ),
        unprojectable=tuple(sequences.unprojectable),
        embargo=embargo_scope(record),
        multi_party=multi_party_scope(record),
    )
