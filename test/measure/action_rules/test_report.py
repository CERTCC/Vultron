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


"""The comparison over every valid position of one vendor, rule by rule
(ADR-0216 rule 8, #6676 AC-5)."""

from functools import cache

import pytest

from test.measure.action_rules.builders import ACTION_RULES_GROUP
from vultron.core.states.cs import CS
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.action_rules import (
    PositionKey,
    ResultKind,
    authored_rules,
    compare_point,
    vendor_points,
)
from vultron.measure.action_rules.report import (
    NO_RESULT,
    UNDECIDED,
    ComparisonReport,
    ConditionalOutcome,
    Outcome,
    OutcomeBranch,
    RuleReport,
    comparison_report,
)

pytestmark = ACTION_RULES_GROUP

_EXTENSION = PositionKey(RM.ACCEPTED, CS.VFdpxa, EM.ACTIVE)


@cache
def _report() -> ComparisonReport:
    return comparison_report()


def _key(point) -> PositionKey:
    p = point.position
    return PositionKey(p.rm, p.cs, p.em)


def _covers(pattern, key: PositionKey) -> bool:
    return (
        pattern.matches_cs(key.cs)
        and (pattern.rm is None or key.rm in pattern.rm)
        and (pattern.em is None or key.em in pattern.em)
    )


def _stated(report: RuleReport, key: PositionKey) -> set[Outcome]:
    """Every outcome *report* states at *key*: a span's that covers it, or
    each branch of its conditional there."""
    found = {
        s.outcome
        for s in report.spans
        if any(_covers(p, key) for p in s.patterns)
    }
    for conditional in report.conditionals:
        if conditional.position == key:
            found |= {b.outcome for b in conditional.branches}
    return found


@pytest.mark.spec("SHD-06-004")
def test_the_report_states_every_rules_result_at_every_valid_position():
    """At each point, each authored rule's result is the one the report
    states at that position, and a rule that does not match there has no
    stated outcome."""
    rules = authored_rules()
    by_number = {r.number: r for r in _report().rules}
    for point in vendor_points():
        key = _key(point)
        comparison = compare_point(point, rules)
        got: dict[int, set[Outcome]] = {}
        for result in comparison.results:
            if result.rule is not None:
                outcome = Outcome(
                    kind=result.kind,
                    reason=result.reason,
                    blind_spot=result.blind_spot,
                )
                got.setdefault(rules.index(result.rule) + 1, set()).add(
                    outcome
                )
        for rule in comparison.undecided:
            got.setdefault(rules.index(rule) + 1, set()).add(
                Outcome(kind=UNDECIDED)
            )
        for number, report in by_number.items():
            stated = _stated(report, key)
            assert got.get(number, set()) <= stated
            assert bool(stated) == (number in got)


def test_the_extension_rule_disagrees_and_cites_its_blind_spot():
    (report,) = [r for r in _report().rules if r.rule.blind_spot == 6492]
    assert report.flagged
    stated = _stated(report, _EXTENSION)
    assert [o.kind for o in stated] == [ResultKind.RULE_DISAGREEMENT]
    assert "#6492" in next(iter(stated)).label


@pytest.mark.spec("SHD-05-029")
def test_a_history_dependent_result_is_stated_as_conditions():
    """D6: where a rule agrees on one history and disagrees on another, the
    report states both, each with the desiderata that give it."""
    conditionals = [
        c
        for r in _report().rules
        for c in r.conditionals
        if {b.outcome.kind for b in c.branches}
        == {ResultKind.AGREEMENT, ResultKind.RULE_DISAGREEMENT}
    ]
    assert conditionals
    for conditional in conditionals:
        assert conditional.flagged
        for branch in conditional.branches:
            assert branch.open or branch.settled
            assert str(branch.outcome.kind) in branch.caveat


@pytest.mark.spec("SHD-06-007")
def test_a_rule_with_a_pec_part_is_undecided_everywhere():
    pec = [r for r in _report().rules if r.rule.pattern.reads_consent]
    assert pec
    for report in pec:
        assert [s.outcome.kind for s in report.spans] == [UNDECIDED]
        assert report.conditionals == ()


def test_the_unclaimed_moves_hold_every_unclaimed_result():
    unclaimed = {u.move: u for u in _report().unclaimed}
    for point in vendor_points():
        key = _key(point)
        for result in compare_point(point, authored_rules()).results:
            if result.kind is not ResultKind.UNCLAIMED_MOVE:
                continue
            assert result.move is not None
            report = unclaimed[result.move]
            assert any(_covers(p, key) for p in report.patterns) or any(
                c.position == key for c in report.conditionals
            )


def test_a_move_unclaimed_on_some_histories_only_says_when():
    conditionals = [c for u in _report().unclaimed for c in u.conditionals]
    assert conditionals
    for conditional in conditionals:
        kinds = [b.outcome.kind for b in conditional.branches]
        assert kinds == [ResultKind.UNCLAIMED_MOVE, NO_RESULT]


def test_an_outcome_label_names_its_blind_spot_and_reason():
    outcome = Outcome(
        kind=ResultKind.RULE_DISAGREEMENT, blind_spot=6492, reason="why"
    )
    assert outcome.label == "rule disagreement (blind spot #6492): why"
    assert outcome.flagged
    assert not Outcome(kind=UNDECIDED).flagged


def test_a_conditional_outcome_needs_two_branches():
    branch = OutcomeBranch(outcome=Outcome(kind=UNDECIDED), open=("D≺P",))
    with pytest.raises(ValueError):
        ConditionalOutcome(position=_EXTENSION, branches=(branch,))


def test_the_report_over_given_points_and_rules_reads_only_them():
    """Given points and rules, the report compares only those."""
    rules = authored_rules()[:3]
    points = [p for p in vendor_points() if _key(p) == _EXTENSION]
    report = comparison_report(points, rules)
    assert {r.number for r in report.rules} <= {1, 2, 3}
