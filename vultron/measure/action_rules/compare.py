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
"""The comparison of authored rules with move advice, position by position
(ADR-0216, SHD-05-010).

For one vendor's position, each authored rule that matches it, and each
verdict at it, :func:`compare_point` gives one result:

* an **agreement**: the rule's move is harm-free for the vendor;
* a **rule disagreement**: the rule's move is unhelpful for the vendor;
* a **misplaced rule**: the state machines do not allow the rule's move
  here, or the rule's roles may not make it;
* an **unscored rule**: the rule's action is allowed but has no band, as a
  CVD action that changes no state, a step the state model forces next, or
  a move move advice does not score;
* an **unclaimed move**: a move harm-free for the vendor that no matching
  rule names.

An unhelpful move that no rule names gives no result.  A rule that is
undecided at the position (ADR-0216, SHD-05-003) gives no result either; the
comparison lists it as undecided.  The comparison resolves nothing and
changes neither table (SHD-05-013).

A rule joins move advice on the move name and on the participant the move is
for (SHD-05-011): an RM or CS move is the matched vendor's own; an EM move is
the one a participant in the rule's roles can make.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import StrEnum
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.states.cs_invariants import (
    cs_happened_events,
    required_next_cs_events,
)
from vultron.core.states.em import EM_TRIGGER_ROLES, EM_Trigger
from vultron.core.states.rm import RM_Trigger
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules.model import (
    ACTION_MOVES,
    ANY_ROLE,
    CS_MOVE_EVENTS,
    SCORED_MACHINES,
    AuthoredRule,
    Machine,
    MatchStatus,
    Position,
    machine_of,
    trigger_of,
)
from vultron.measure.action_rules.verdicts import MoveVerdict, VendorPoint
from vultron.measure.advice.bands import Band, Part
from vultron.primitives import NonEmptyString


class ResultKind(StrEnum):
    """What the comparison finds for one rule, or one move, at a position."""

    AGREEMENT = "agreement"
    RULE_DISAGREEMENT = "rule disagreement"
    MISPLACED_RULE = "misplaced rule"
    UNSCORED_RULE = "unscored rule"
    UNCLAIMED_MOVE = "unclaimed move"


#: The results the case shadow tool and the docs page flag: an authoring
#: error, or a claim the bands contradict (SHD-06-003).
FLAGGED: frozenset[ResultKind] = frozenset(
    {ResultKind.RULE_DISAGREEMENT, ResultKind.MISPLACED_RULE}
)

#: The results that carry a band, the deciding part and the named changes.
_BANDED = frozenset({ResultKind.AGREEMENT, ResultKind.RULE_DISAGREEMENT})

NO_STATE_CHANGE = "the action changes no state here"
"""Why a rule whose action changes no state at a position is unscored."""

FORCED_STEP = "not measured: this step happens anyway"
"""Why a rule joined to a step the state model forces next is unscored, such
as notifying a vendor that public awareness forces to become aware, or a
publication beside a public exploit and an unaware public (#6676, D19;
SHD-05-030)."""

NOT_MEASURED = "not measured: the rule names no desideratum"
"""Why a rule whose reason is not a desideratum is unscored (SHD-05-028)."""


class DesideratumShift(BaseModel):
    """The vendor's change in one desideratum a rule names.

    Fields:
        desideratum: The desideratum, by plain name.
        change: The change in its expected outcome.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    desideratum: NonEmptyString
    change: Fraction


class RuleResult(BaseModel):
    """One result of the comparison at one position.

    Fields:
        kind: The result.
        vendor: The vendor whose position it is.
        rule: The authored rule; ``None`` only for an unclaimed move.
        proposal: The open proposal a rule with a proposal part matched.
        move: The move joined: the rule's move, or the move its action is
            here; ``None`` for an action that changes no state, or one
            whose step the state model forces next.
        participant: The participant who makes the joined move.
        band: The move's band for the vendor, for an agreement, a rule
            disagreement and an unclaimed move.
        deciding_part: The part that decides that band.
        deciding_size: That part's size.
        changes: For an agreement and a rule disagreement, the vendor's
            change in each desideratum the rule names (SHD-05-012).
        blind_spot: For a rule disagreement, the issue its rule cites as a
            chance-model blind spot (SHD-05-014).
        reason: Why a misplaced rule is misplaced, or why an unscored rule
            has no band.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ResultKind
    vendor: NonEmptyString
    rule: AuthoredRule | None = None
    proposal: NonEmptyString | None = None
    move: NonEmptyString | None = None
    participant: NonEmptyString | None = None
    band: Band | None = None
    deciding_part: Part | None = None
    deciding_size: Fraction | None = None
    changes: tuple[DesideratumShift, ...] = ()
    blind_spot: int | None = None
    reason: NonEmptyString | None = None

    @model_validator(mode="after")
    def _fields_fit_the_kind(self) -> RuleResult:
        problems: list[str] = []
        unclaimed = self.kind is ResultKind.UNCLAIMED_MOVE
        if (self.rule is None) != unclaimed:
            problems.append("only an unclaimed move has no rule")
        scored = self.kind in _BANDED or unclaimed
        if scored != (self.band is not None):
            problems.append(
                "an agreement, a rule disagreement and an unclaimed move"
                " carry a band, and nothing else does"
            )
        if scored and (self.deciding_part is None or self.move is None):
            problems.append("a banded result names its move and its part")
        if self.kind not in _BANDED and self.changes:
            problems.append("only a banded rule result carries its changes")
        if self.blind_spot is not None and (
            self.kind is not ResultKind.RULE_DISAGREEMENT
        ):
            problems.append("only a rule disagreement carries a blind spot")
        needs_reason = self.kind in (
            ResultKind.MISPLACED_RULE,
            ResultKind.UNSCORED_RULE,
        )
        if needs_reason != (self.reason is not None):
            problems.append(
                "a misplaced or unscored rule says why, and nothing else does"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


class PointComparison(BaseModel):
    """The comparison at one vendor's position.

    Fields:
        position: The position.
        results: One result for each matching rule (once for each open
            proposal it matches) in rule order, then each unclaimed move.
        undecided: Each rule undecided here, in rule order (SHD-05-003).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    position: Position
    results: tuple[RuleResult, ...] = ()
    undecided: tuple[AuthoredRule, ...] = ()


def _not_measured(rule: AuthoredRule) -> str:
    """Why a rule that names no desideratum gets no band, with its reason
    (SHD-05-028)."""
    return f"{NOT_MEASURED}; its reason: {rule.reason}"


def rule_move(rule: AuthoredRule, position: Position) -> str | None:
    """The move *rule*'s action is at *position*; ``None`` when it changes
    no state there (:func:`resolve_action`)."""
    return resolve_action(rule, position)[0]


def resolve_action(
    rule: AuthoredRule, position: Position
) -> tuple[str | None, str | None]:
    """The move *rule*'s action is at *position*, or ``None`` and why it
    changes no state there.

    A rule that names a move is that move.  An action of ``Actions`` is the
    move :data:`ACTION_MOVES` gives it, except where the CS event it causes
    has already happened (SHD-05-024).  Either is joined to no move where
    the state model forces its CS event next, whatever anyone does: the
    step happens anyway, so no band can say whether the rule's action
    serves it (#6676, D19; SHD-05-030).  At ``vfdP..`` the vendor becomes
    aware next, notified or not; beside a public exploit the public learns
    of the vul from the exploit, not from a publication.
    """
    named = isinstance(rule.action, str)
    move = (
        rule.action
        if isinstance(rule.action, str)
        else ACTION_MOVES.get(rule.action)
    )
    if move is None:
        return None, NO_STATE_CHANGE
    event = CS_MOVE_EVENTS.get(move)
    if event is None:
        return move, None
    if not named and event in cs_happened_events(position.cs):
        return None, NO_STATE_CHANGE
    if event in required_next_cs_events(position.cs):
        return None, FORCED_STEP
    return move, None


def _role_refusal(rule: AuthoredRule, move: str) -> str | None:
    """Why *rule*'s roles may not make *move*; ``None`` when they may.

    An EM move is made by the role the EM trigger roles table gives it; an
    RM move by the vendor whose report it is, except its receipt, which
    whoever sends the report causes.  A CS move is caused by whoever acts,
    so it constrains no role.
    """
    machine = machine_of(move)
    trigger = trigger_of(move)
    role: CVDRole | None = None
    if machine is Machine.EM:
        role = EM_TRIGGER_ROLES[EM_Trigger(trigger)]
    elif machine is Machine.RM and trigger != RM_Trigger.RECEIVE:
        role = CVDRole.VENDOR
    if role is None or rule.may_take(role):
        return None
    return (
        f"{move} is made by {role.name}, which is not among the rule's"
        f" roles ({rule.roles_label})"
    )


def _joins(rule: AuthoredRule, verdict: MoveVerdict, move: str) -> bool:
    if verdict.move.name != move:
        return False
    if machine_of(move) is not Machine.EM:
        return True
    return rule.roles == ANY_ROLE or bool(verdict.roles & rule.roles)


def _rule_result(
    rule: AuthoredRule,
    point: VendorPoint,
    proposal: str | None,
) -> RuleResult:
    position = point.position
    move, no_state = resolve_action(rule, position)

    def result(kind: ResultKind, **fields: object) -> RuleResult:
        return RuleResult.model_validate(
            {
                "kind": kind,
                "vendor": position.vendor,
                "rule": rule,
                "proposal": proposal,
                "move": move,
                **fields,
            }
        )

    def unscored(why: str | None, **fields: object) -> RuleResult:
        """An unscored-rule result; one for a rule that names no
        desideratum also carries the rule's reason (SHD-05-028)."""
        if not rule.measured:
            why = (
                _not_measured(rule)
                if why is None
                else (f"{why}; {_not_measured(rule)}")
            )
        return result(ResultKind.UNSCORED_RULE, reason=why, **fields)

    if move is None:
        return unscored(no_state)
    refusal = _role_refusal(rule, move)
    if refusal is not None:
        return result(ResultKind.MISPLACED_RULE, reason=refusal)
    if machine_of(move) not in SCORED_MACHINES:
        return unscored(f"move advice does not score {move} (#6677)")
    joined = [v for v in point.verdicts if _joins(rule, v, move)]
    if not joined:
        return result(
            ResultKind.MISPLACED_RULE,
            reason=(
                f"the state machines allow no {move} here for the rule's"
                f" roles ({rule.roles_label})"
            ),
        )
    if not rule.measured:
        return unscored(None, participant=joined[0].move.participant)
    scored = [v for v in joined if v.score is not None]
    if not scored:
        return unscored(
            joined[0].unscored, participant=joined[0].move.participant
        )
    verdict = scored[0]
    score = verdict.score
    assert score is not None
    agrees = score.band is Band.HARM_FREE
    return result(
        ResultKind.AGREEMENT if agrees else ResultKind.RULE_DISAGREEMENT,
        participant=verdict.move.participant,
        band=score.band,
        deciding_part=score.deciding_part,
        deciding_size=score.deciding_size,
        changes=tuple(
            DesideratumShift(desideratum=d, change=score.changes[d])
            for d in rule.desiderata
        ),
        blind_spot=None if agrees else rule.blind_spot,
    )


def _unclaimed(point: VendorPoint, claimed: set[str]) -> list[RuleResult]:
    """Each move harm-free for the vendor that no matching rule names, once
    for each move name."""
    found: list[RuleResult] = []
    seen: set[str] = set()
    for verdict in point.verdicts:
        name = verdict.move.name
        score = verdict.score
        if (
            score is None
            or score.band is not Band.HARM_FREE
            or name in claimed
            or name in seen
        ):
            continue
        seen.add(name)
        found.append(
            RuleResult(
                kind=ResultKind.UNCLAIMED_MOVE,
                vendor=point.position.vendor,
                move=name,
                participant=verdict.move.participant,
                band=score.band,
                deciding_part=score.deciding_part,
                deciding_size=score.deciding_size,
            )
        )
    return found


def compare_point(
    point: VendorPoint, rules: Sequence[AuthoredRule]
) -> PointComparison:
    """The comparison of *rules* with the verdicts at *point*.

    Changes neither *rules* nor the verdicts (SHD-05-013).
    """
    results: list[RuleResult] = []
    undecided: list[AuthoredRule] = []
    claimed: set[str] = set()
    for rule in rules:
        match = rule.pattern.match(point.position)
        if match.status is MatchStatus.UNDECIDED:
            undecided.append(rule)
            continue
        if match.status is MatchStatus.UNMATCHED:
            continue
        move = rule_move(rule, point.position)
        if move is not None:
            claimed.add(move)
        for proposal in match.proposals or (None,):
            results.append(_rule_result(rule, point, proposal))
    results.extend(_unclaimed(point, claimed))
    return PointComparison(
        position=point.position,
        results=tuple(results),
        undecided=tuple(undecided),
    )


def compare_points(
    points: Iterable[VendorPoint], rules: Sequence[AuthoredRule]
) -> tuple[PointComparison, ...]:
    """:func:`compare_point` at each of *points*, in order."""
    return tuple(compare_point(point, rules) for point in points)
