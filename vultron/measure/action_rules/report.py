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
"""The comparison over every valid position of one vendor, as the generated
docs page states it (SHD-06-004; ADR-0216).

:func:`comparison_report` compares the authored rules at every point of
:func:`~vultron.measure.action_rules.verdicts.vendor_points` and states,
for each authored rule, each outcome it gets: one of the comparison's
results, or undecided for a rule with a PEC part, since those points hold
no consent state (SHD-06-007).  An outcome the rule gets on every history
that reaches a position is written as patterns in the authored rules'
pattern language, grouped as the generated rules are
(:func:`~vultron.measure.action_rules.generated.group_positions`).  Where
the outcome depends on which desiderata a history leaves open, the report
states a conditional outcome: each outcome with the desiderata whose state
gives it, rather than picking one history (#6676, D6; SHD-05-029).

For each move that is an unclaimed move somewhere, the report states where,
in the same way: a conditional outcome there pairs the unclaimed move with
the histories on which the comparison gives no result for it.

Everything here reads; the report changes neither table (SHD-05-013).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.measure.action_rules.authored import authored_rules
from vultron.measure.action_rules.compare import (
    FLAGGED,
    ResultKind,
    RuleResult,
    compare_point,
)
from vultron.measure.action_rules.generated import (
    PositionKey,
    history_branches,
    history_condition,
    patterns_for,
    position_key,
    walk_positions,
)
from vultron.measure.action_rules.model import (
    AuthoredRule,
    MoveName,
    RuleNumbers,
    RulePattern,
)
from vultron.measure.action_rules.verdicts import VendorPoint, vendor_points
from vultron.primitives import NonEmptyString

UNDECIDED: Literal["undecided"] = "undecided"
"""The outcome of a rule whose pattern reads a part the points do not
hold (SHD-05-003)."""

NO_RESULT: Literal["no result"] = "no result"
"""The outcome of a move the comparison gives no result for on a history:
one that is not harm-free there."""

type OutcomeKind = ResultKind | Literal["undecided", "no result"]

#: The order outcomes are stated in.
_KIND_ORDER: tuple[OutcomeKind, ...] = (*ResultKind, UNDECIDED, NO_RESULT)


class Outcome(BaseModel, frozen=True):
    """What the comparison gives one rule, or one move, on one history.

    Fields:
        kind: The result, undecided, or no result.
        reason: Why a misplaced or unscored rule is so.
        blind_spot: The issue a rule disagreement's rule cites.
    """

    # Frozen as a class argument, where type checkers see it: outcomes are
    # gathered in sets.
    model_config = ConfigDict(extra="forbid")

    kind: OutcomeKind
    reason: NonEmptyString | None = None
    blind_spot: int | None = None

    @property
    def flagged(self) -> bool:
        """Whether the page flags it (:data:`FLAGGED`, SHD-06-003)."""
        return self.kind in FLAGGED

    @property
    def label(self) -> str:
        """The outcome as text: its kind, the cited blind spot, and why."""
        text = str(self.kind)
        if self.blind_spot is not None:
            text = f"{text} (blind spot #{self.blind_spot})"
        if self.reason is not None:
            text = f"{text}: {self.reason}"
        return text


class OutcomeSpan(BaseModel):
    """One outcome and the positions where it holds on every history.

    Fields:
        outcome: The outcome.
        patterns: Patterns whose union holds those positions and no other
            valid position.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: Outcome
    patterns: tuple[RulePattern, ...] = Field(min_length=1)


class OutcomeBranch(BaseModel):
    """One outcome of a conditional outcome, and the history that gives it.

    Fields:
        outcome: The outcome.
        open: The deciding desiderata still open on every history that
            gives it, by plain name.
        settled: The deciding desiderata already met or broken on every
            such history.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: Outcome
    open: tuple[NonEmptyString, ...] = ()
    settled: tuple[NonEmptyString, ...] = ()

    @property
    def caveat(self) -> str:
        """The branch as text: its outcome, and when it holds."""
        return (
            f"{self.outcome.label}"
            f" {history_condition(self.open, self.settled)}"
        )


class ConditionalOutcome(BaseModel):
    """Outcomes that depend on the history at one position (#6676, D6).

    Fields:
        position: The vendor's RM, CS and EM states.
        branches: Each outcome with the desiderata that give it, in outcome
            order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    position: PositionKey
    branches: tuple[OutcomeBranch, ...] = Field(min_length=2)

    @property
    def flagged(self) -> bool:
        """Whether a branch is flagged."""
        return any(b.outcome.flagged for b in self.branches)

    @property
    def caveat(self) -> str:
        """Each branch's outcome and when it holds."""
        return "; ".join(b.caveat for b in self.branches)


class RuleReport(BaseModel):
    """One authored rule's outcomes over every valid position of one vendor.

    Fields:
        number: The rule's place in the authored table, from 1.
        rule: The rule.
        spans: Each outcome it gets on every history somewhere, in outcome
            order.
        conditionals: Each position where its outcome depends on the
            history, in walk order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int = Field(gt=0)
    rule: AuthoredRule
    spans: tuple[OutcomeSpan, ...] = ()
    conditionals: tuple[ConditionalOutcome, ...] = ()

    @property
    def flagged(self) -> bool:
        """Whether any of its outcomes is flagged."""
        return any(s.outcome.flagged for s in self.spans) or any(
            c.flagged for c in self.conditionals
        )


class UnclaimedReport(BaseModel):
    """Where one move is an unclaimed move (SHD-05-021).

    Fields:
        move: The move.
        patterns: Patterns over the positions where it is unclaimed on
            every history; empty when it is unclaimed on some histories
            only.
        conditionals: Each position where it is unclaimed on some
            histories, in walk order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: MoveName
    patterns: tuple[RulePattern, ...] = ()
    conditionals: tuple[ConditionalOutcome, ...] = ()

    @model_validator(mode="after")
    def _unclaimed_somewhere(self) -> UnclaimedReport:
        if not (self.patterns or self.conditionals):
            raise ValueError(
                f"{self.move} is reported unclaimed but has neither a"
                " pattern nor a conditional outcome where it is"
            )
        return self


class ComparisonReport(BaseModel):
    """The comparison over every valid position of one vendor.

    Fields:
        rules: Each authored rule that matches or is undecided at some
            position, in table order.
        unclaimed: Each move that is unclaimed somewhere, in the order the
            walk first scores it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rules: tuple[RuleReport, ...] = ()
    unclaimed: tuple[UnclaimedReport, ...] = ()


type _Variants = dict[PositionKey, list[tuple[Outcome, frozenset[str]]]]


def _outcome(result: RuleResult) -> Outcome:
    return Outcome(
        kind=result.kind, reason=result.reason, blind_spot=result.blind_spot
    )


def _order(variants: _Variants) -> list[Outcome]:
    """Every outcome of *variants*, by kind, then as first found."""
    found = list(dict.fromkeys(o for vs in variants.values() for o, _ in vs))
    return sorted(found, key=lambda o: _KIND_ORDER.index(o.kind))


def _split(
    variants: _Variants, every: Sequence[PositionKey]
) -> tuple[list[OutcomeSpan], list[ConditionalOutcome]]:
    """The spans of the outcomes *variants* give on every history, and the
    conditional outcomes where they do not."""
    order = _order(variants)
    steady: dict[Outcome, list[PositionKey]] = {}
    conditionals = []
    for key, found in variants.items():
        outcomes = {o for o, _ in found}
        if len(outcomes) == 1:
            steady.setdefault(found[0][0], []).append(key)
            continue
        branches = history_branches(found, order)
        conditionals.append(
            ConditionalOutcome(
                position=key,
                branches=tuple(
                    OutcomeBranch(
                        outcome=b.outcome, open=b.open, settled=b.settled
                    )
                    for b in branches
                ),
            )
        )
    spans = [
        OutcomeSpan(
            outcome=outcome,
            patterns=patterns_for(steady[outcome], every),
        )
        for outcome in order
        if outcome in steady
    ]
    return spans, conditionals


def comparison_report(
    points: Sequence[VendorPoint] | None = None,
    rules: Sequence[AuthoredRule] | None = None,
) -> ComparisonReport:
    """The comparison of *rules* at *points*, rule by rule.

    *points* defaults to every valid position of one vendor
    (:func:`vendor_points`) and *rules* to the authored table.  Changes
    neither (SHD-05-013).
    """
    points = vendor_points() if points is None else points
    rules = authored_rules() if rules is None else rules
    every = walk_positions(points)
    number = RuleNumbers(rules)
    by_rule: dict[int, _Variants] = {}  # by rule number
    by_move: dict[str, _Variants] = {}
    for point in points:
        key = position_key(point)
        opened = frozenset(point.open_desiderata or ())
        comparison = compare_point(point, rules)
        for rule in comparison.undecided:
            by_rule.setdefault(number(rule), {}).setdefault(key, []).append(
                (Outcome(kind=UNDECIDED), opened)
            )
        unclaimed: set[str] = set()
        for result in comparison.results:
            if result.rule is None:
                assert result.move is not None, "an unclaimed move names it"
                unclaimed.add(result.move)
                continue
            by_rule.setdefault(number(result.rule), {}).setdefault(
                key, []
            ).append((_outcome(result), opened))
        for name in dict.fromkeys(
            v.move.name for v in point.verdicts if v.score is not None
        ):
            kind: OutcomeKind = (
                ResultKind.UNCLAIMED_MOVE if name in unclaimed else NO_RESULT
            )
            by_move.setdefault(name, {}).setdefault(key, []).append(
                (Outcome(kind=kind), opened)
            )
    reports = []
    for n in sorted(by_rule):
        spans, conditionals = _split(by_rule[n], every)
        reports.append(
            RuleReport(
                number=n,
                rule=rules[n - 1],
                spans=tuple(spans),
                conditionals=tuple(conditionals),
            )
        )
    return ComparisonReport(
        rules=tuple(reports), unclaimed=tuple(_unclaimed(by_move, every))
    )


def _unclaimed(
    by_move: dict[str, _Variants], every: Sequence[PositionKey]
) -> list[UnclaimedReport]:
    found = []
    for move, variants in by_move.items():
        spans, conditionals = _split(variants, every)
        held = [
            s for s in spans if s.outcome.kind is ResultKind.UNCLAIMED_MOVE
        ]
        if not (held or conditionals):
            continue
        found.append(
            UnclaimedReport(
                move=move,
                patterns=held[0].patterns if held else (),
                conditionals=tuple(conditionals),
            )
        )
    return found


__all__ = [
    "ComparisonReport",
    "ConditionalOutcome",
    "NO_RESULT",
    "Outcome",
    "OutcomeBranch",
    "OutcomeKind",
    "OutcomeSpan",
    "RuleReport",
    "UNDECIDED",
    "UnclaimedReport",
    "comparison_report",
]
