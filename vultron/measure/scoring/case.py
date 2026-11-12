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

"""A multi-party case's per-vendor scores and how evenly they fall (ADR-0182).

A case is never scored as one sequence: each vendor's sequence is scored
against the one-vendor baseline (:func:`.score_sequence`), and several
vendors' sequences are never combined (CEH-05-006).  The case reports every
vendor's score, and for each of the expected, best and worst scores their
unweighted median and spread across the vendors
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
score with zero spread.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from vultron.measure.scoring.model import SequenceScore, VendorScore
from vultron.measure.scoring.score import score_sequence
from vultron.measure.sequences import (
    CaseStateSequences,
    UnprojectableParticipant,
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
    """A case's per-vendor scores, summarized across its vendors (ADR-0182).

    The medians and spreads are read from the vendors' scores, never stored
    beside them, so they cannot disagree.

    Fields:
        case_id: The case.
        vendors: Each vendor's score, in the order of the sequences it was
            scored from; :func:`score_case` keeps their vendor-awareness
            order.
        unprojectable: Every participant with no sequence, with its reason
            (CEH-05-007), unscored.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    vendors: tuple[VendorScore, ...] = ()
    unprojectable: tuple[UnprojectableParticipant, ...] = ()

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
        self, read: Callable[[SequenceScore], Fraction]
    ) -> AcrossVendors | None:
        """*read* of each vendor's score, across the vendors."""
        if not self.vendors:
            return None
        return AcrossVendors.of(read(vendor.score) for vendor in self.vendors)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expected(self) -> AcrossVendors | None:
        """The vendors' expected scores across the case; ``None`` with no
        vendor to score."""
        return self._across(lambda score: score.expected)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def best(self) -> AcrossVendors | None:
        """The vendors' best scores across the case; ``None`` with no vendor
        to score."""
        return self._across(lambda score: score.best)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def worst(self) -> AcrossVendors | None:
        """The vendors' worst scores across the case; ``None`` with no
        vendor to score."""
        return self._across(lambda score: score.worst)

    def for_participant(self, participant: str) -> VendorScore | None:
        """The score of *participant*, or ``None`` when it has none."""
        for vendor in self.vendors:
            if vendor.participant == participant:
                return vendor
        return None


def score_case(sequences: CaseStateSequences) -> CaseScoreSummary:
    """Score each vendor's sequence and summarize the case across vendors.

    Every vendor is scored alone, against the one-vendor baseline
    (:func:`.score_sequence`); no case-wide sequence is built (CEH-05-006).
    Every unprojectable participant is carried over with its reason
    (CEH-05-007).
    """
    return CaseScoreSummary(
        case_id=sequences.case_id,
        vendors=tuple(score_sequence(s) for s in sequences.sequences),
        unprojectable=tuple(sequences.unprojectable),
    )
