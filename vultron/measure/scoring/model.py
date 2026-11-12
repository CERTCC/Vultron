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
are read from them, never stored beside them, so they cannot disagree.  A
:class:`VendorScore` is one vendor's :class:`SequenceScore`, the unit a
case-level summary reads (#6069).
"""

from __future__ import annotations

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
from vultron.measure.baselines import completion_probabilities
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
        """Refuse a completion that does not extend the prefix, a repeat, or
        weights that do not sum to 1 (EH-07-001: every problem is named)."""
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


class VendorScore(BaseModel):
    """One vendor's case-state sequence, scored (ADR-0182).

    Fields:
        participant: The vendor the sequence belongs to.
        score: Its sequence scored through its completions.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participant: NonEmptyString
    score: SequenceScore
