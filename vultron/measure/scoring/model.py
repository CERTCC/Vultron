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

"""What scoring a case-state sequence yields (ADR-0182).

A :class:`SequenceScore` holds a prefix and every valid completion of it,
each a :class:`Completion` with the walk's probability of it from where the
prefix stands and its desiderata score.  The expected, best and worst scores
are read from them, never stored beside them, so they cannot disagree.

The extended desiderata of ``process_model_desiderata.md`` are scored in
their scopes (ADR-0200): each vendor, and each case-wide group.  A
:class:`TermScore` is one desideratum for its vendors, with the chance it is
met from where the case stands; a :class:`WalkScore` is the terms one walk
scores, with the best and worst they can still reach together; a
:class:`ScopeScore` adds up the walks of one scope.  A scope the joint model
cannot walk from is an :class:`UnscoredScope`, with its reason.

A :class:`VendorScore` is one vendor's :class:`SequenceScore` and its
extended desiderata, the unit a case-level summary reads (#6069).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from fractions import Fraction

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from vultron.core.states.cs_invariants import (
    CS_EVENTS,
    CSEvent,
    ensure_valid_cs_history,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.measure.baselines import Group, completion_probabilities
from vultron.measure.scoring.complete import history_score
from vultron.primitives import NonEmptyString


class Completion(BaseModel):
    """One valid complete history a prefix can still become.

    Fields:
        history: The whole history, prefix included; one of the 70 valid
            complete histories (CSB-17-004).
        probability: The indifference walk's probability of this history
            given the prefix, in ``(0, 1]``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    history: tuple[CSEvent, ...]
    probability: Fraction

    @model_validator(mode="after")
    def _is_a_valid_weighted_history(self) -> Completion:
        problems: list[str] = []
        try:
            ensure_valid_cs_history(self.history)
        except (
            VultronValidationError,
            VultronInvalidStateTransitionError,
        ) as exc:
            problems.append(
                f"{''.join(self.history)} is not a valid complete history:"
                f" {exc}"
            )
        if not 0 < self.probability <= 1:
            problems.append(f"probability {self.probability} is not in (0, 1]")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def score(self) -> Fraction:
        """The history's desiderata score (:func:`.history_score`)."""
        return history_score(self.history)


class SequenceScore(BaseModel):
    """A case-state prefix scored through its valid completions (ADR-0182).

    Fields:
        prefix: The accepted prefix scored; complete when it holds all six
            events.
        completions: Every valid completion of *prefix*, each once, ordered
            by history, each with the walk's probability of it from *prefix*;
            their probabilities sum to 1.  A complete prefix has
            itself as its only completion.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    prefix: tuple[CSEvent, ...]
    completions: tuple[Completion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _completions_partition_the_prefix(self) -> SequenceScore:
        """Refuse completions that do not partition the walk from the prefix.

        A completion that does not extend the prefix, a repeat, weights that
        do not sum to 1, and a disagreement with the walk are each named
        (EH-07-001).
        """
        problems: list[str] = []
        size = len(self.prefix)
        prefix = "".join(self.prefix)
        for completion in self.completions:
            if completion.history[:size] != self.prefix:
                problems.append(
                    f"{''.join(completion.history)} does not extend {prefix}"
                )
        histories = [c.history for c in self.completions]
        if len(set(histories)) != len(histories):
            problems.append("a completion is listed more than once")
        if histories != sorted(histories):
            problems.append("the completions are not ordered by history")
        total = sum((c.probability for c in self.completions), Fraction(0))
        if total != 1:
            problems.append(f"the completion probabilities sum to {total}")
        problems.extend(self._walk_problems())
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _walk_problems(self) -> list[str]:
        """Where the completions differ from the walk's from *prefix*.

        Every valid completion must be listed, each with the probability the
        walk gives it from the prefix (ADR-0182).
        """
        try:
            walk = completion_probabilities(self.prefix)
        except (
            VultronValidationError,
            VultronInvalidStateTransitionError,
        ) as exc:
            return [f"{''.join(self.prefix)} is not a valid prefix: {exc}"]
        listed = {c.history: c.probability for c in self.completions}
        problems = [
            f"the valid completion {''.join(h)} is missing"
            for h in sorted(walk)
            if h not in listed
        ]
        problems.extend(
            f"{''.join(h)} has probability {p}, but the walk gives {walk[h]}"
            for h, p in listed.items()
            if h in walk and walk[h] != p
        )
        return problems

    @property
    def is_complete(self) -> bool:
        """Whether the prefix already holds all six case-state events."""
        return len(self.prefix) == len(CS_EVENTS)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expected(self) -> Fraction:
        """The score expected if the case went on by chance from here."""
        return sum(
            (c.probability * c.score for c in self.completions), Fraction(0)
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def best(self) -> Fraction:
        """The highest score the case can still reach."""
        return max(c.score for c in self.completions)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def worst(self) -> Fraction:
        """The lowest score the case can still reach."""
        return min(c.score for c in self.completions)


class TermScore(BaseModel):
    """One extended desideratum for its vendors, scored from where the case stands.

    Fields:
        notation: The desideratum as ``process_model_desiderata.md`` writes
            it.
        group: Its group on that page.
        vendors: The vendors its vendor numbers stand for, vendor 1 first;
            empty when it names only the case's events.
        weight: What meeting it adds to the score, ``1 - f_d`` for its
            baseline ``f_d`` (ADR-0182).
        met: The walk's probability that it is met, from where the case
            stands: 1 once the record meets it, 0 once the record fails it
            or puts it out of its scope for good.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    notation: NonEmptyString
    group: Group
    vendors: tuple[NonEmptyString, ...] = ()
    weight: Fraction
    met: Fraction

    @model_validator(mode="after")
    def _is_a_weighted_chance(self) -> TermScore:
        problems: list[str] = []
        if not 0 <= self.weight <= 1:
            problems.append(f"weight {self.weight} is not in [0, 1]")
        if not 0 <= self.met <= 1:
            problems.append(f"probability {self.met} is not in [0, 1]")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expected(self) -> Fraction:
        """What the term is expected to add, if the case goes on by chance."""
        return self.weight * self.met


def _sum(values: Iterable[Fraction]) -> Fraction:
    return sum(values, Fraction(0))


class WalkScore(BaseModel):
    """The terms one walk scores, from one joint state (ADR-0182).

    The best and worst are what the terms can still reach together, at one
    end of the walk, so they can be closer together than the terms' own
    extremes added up.

    Fields:
        terms: The terms, in catalog order.
        best: The highest sum of the terms' weights met at one reachable
            end.
        worst: The lowest such sum.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    terms: tuple[TermScore, ...] = Field(min_length=1)
    best: Fraction
    worst: Fraction

    @model_validator(mode="after")
    def _ends_bound_the_expectation(self) -> WalkScore:
        """Refuse a best or worst no end could have, or out of order."""
        problems: list[str] = []
        reachable = _sum(t.weight for t in self.terms if t.met > 0)
        certain = _sum(t.weight for t in self.terms if t.met == 1)
        if not self.worst <= self.expected <= self.best:
            problems.append(
                f"the expected score {self.expected} is not between the"
                f" worst {self.worst} and the best {self.best}"
            )
        if self.best > reachable:
            problems.append(
                f"the best {self.best} is more than the terms that can still"
                f" be met add up to, {reachable}"
            )
        if self.worst < certain:
            problems.append(
                f"the worst {self.worst} is less than the terms already met"
                f" add up to, {certain}"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expected(self) -> Fraction:
        """The score expected if the case went on by chance from here."""
        return _sum(t.expected for t in self.terms)


class ScopeScore(BaseModel):
    """One scope's extended desiderata, scored (ADR-0200).

    A scope's terms can take more than one walk: the multi-party group walks
    each vendor and each pair of vendors on its own (ADR-0182).  Its
    expected score is exact, the sum of the walks'.  Its best and worst add
    up each walk's, so with more than one walk they bound what the case can
    reach rather than state it: the walks share the case's events, and no
    walk over the whole case is built.

    Fields:
        walks: The walks, each with its terms.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    walks: tuple[WalkScore, ...] = Field(min_length=1)

    @property
    def terms(self) -> tuple[TermScore, ...]:
        """Every term of every walk, in walk order."""
        return tuple(t for walk in self.walks for t in walk.terms)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expected(self) -> Fraction:
        """The score expected if the case went on by chance from here."""
        return _sum(w.expected for w in self.walks)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def best(self) -> Fraction:
        """The walks' best scores, added up."""
        return _sum(w.best for w in self.walks)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def worst(self) -> Fraction:
        """The walks' worst scores, added up."""
        return _sum(w.worst for w in self.walks)


class UnscoredScope(BaseModel):
    """A scope with no score, because the walk cannot go on from the case.

    Fields:
        reason: Why: the joint state the case stands in breaks a rule of the
            joint model, named.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: NonEmptyString


class VendorScore(BaseModel):
    """One vendor, scored on every desideratum in its scope (ADR-0182).

    Its score adds up the twelve original desiderata, scored on its
    case-state sequence, and the extended desiderata of its own scope:
    report handling and its fix before the embargo ends on its own terms.
    The two take chance from different models, each the smallest that
    holds its desiderata (ADR-0182), so the best and worst add up each
    one's.  They are a bound on what the vendor can still reach, not a
    score it can reach: the two walks share the vendor's events and the
    case's.

    Fields:
        participant: The vendor the sequence belongs to.
        score: Its sequence scored through its completions, on the twelve
            original desiderata.
        extended: Its extended desiderata, or why they have no score.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participant: NonEmptyString
    score: SequenceScore
    extended: ScopeScore | UnscoredScope

    def _total(
        self, read: Callable[[SequenceScore | ScopeScore], Fraction]
    ) -> Fraction | None:
        """*read* of both parts, added; ``None`` with the extended part
        unscored."""
        if isinstance(self.extended, UnscoredScope):
            return None
        return read(self.score) + read(self.extended)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expected(self) -> Fraction | None:
        """The vendor's expected score."""
        return self._total(lambda part: part.expected)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def best(self) -> Fraction | None:
        """The vendor's best score: a bound, the two parts' best added."""
        return self._total(lambda part: part.best)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def worst(self) -> Fraction | None:
        """The vendor's worst score: a bound, the two parts' worst
        added."""
        return self._total(lambda part: part.worst)
