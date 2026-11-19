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


"""The comparison of authored rules with move advice (ADR-0216, SHD-05-010)."""

import copy
from typing import Any

import pytest

from test.measure.history.builders import (
    OWNER,
    VENDOR as VENDOR_1,
    VENDOR_2,
    two_vendors_ledger,
)
from vultron.core.scoring.potential_actions import Actions
from vultron.core.states.cs import CS
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules import (
    ANY_ROLE,
    FORCED_AWARENESS,
    NO_STATE_CHANGE,
    NOT_MEASURED,
    AuthoredRule,
    ConsentReading,
    PointComparison,
    ProposalConsent,
    ResultKind,
    RulePattern,
    RuleResult,
    VendorPoint,
    authored_rules,
    case_points,
    compare_point,
    compare_points,
    generated_rules,
    point_at,
    vendor_points,
)
from vultron.measure.advice import Band, Part
from vultron.measure.standing import case_standing

_K = ResultKind


def _point(rm: RM, cs: CS, em: EM) -> VendorPoint:
    return point_at(rm, cs, em)


#: The #6492 example: the vendor's report accepted, its fix ready, an
#: embargo active.
_EXTENSION = (RM.ACCEPTED, CS.VFdpxa, EM.ACTIVE)


def _rule(**fields: Any) -> AuthoredRule:
    base: dict[str, Any] = {
        "pattern": RulePattern(),
        "roles": ANY_ROLE,
        "action": Actions.MONITOR_FOR_ATTACKS,
        "reason": "SA",
        "desiderata": ("D≺P",),
        "source": None,
    }
    base.update(fields)
    return AuthoredRule(**base)


def _only(comparison: PointComparison, rule: AuthoredRule) -> RuleResult:
    (result,) = [r for r in comparison.results if r.rule == rule]
    return result


# --- SHD-05-010: one result for each matching rule ---


def _agrees() -> AuthoredRule:
    return _rule(
        action="cs.fix_is_deployed",
        roles=frozenset({CVDRole.VENDOR}),
        desiderata=("D≺P", "D≺X"),
    )


def _disagrees() -> AuthoredRule:
    return _rule(
        action="em.propose",
        pattern=RulePattern(em=frozenset({EM.ACTIVE})),
        desiderata=("D≺P",),
    )


def _not_allowed() -> AuthoredRule:
    return _rule(action="cs.fix_is_ready", roles=frozenset({CVDRole.VENDOR}))


def _wrong_role() -> AuthoredRule:
    return _rule(
        action="em.terminate",
        roles=frozenset({CVDRole.REPORTER}),
        pattern=RulePattern(em=frozenset({EM.ACTIVE})),
    )


def _no_state() -> AuthoredRule:
    return _rule(action=Actions.MONITOR_FOR_ATTACKS)


@pytest.mark.spec("SHD-05-010")
@pytest.mark.parametrize(
    ("make", "kind"),
    [
        (_agrees, _K.AGREEMENT),
        (_disagrees, _K.RULE_DISAGREEMENT),
        (_not_allowed, _K.MISPLACED_RULE),
        (_wrong_role, _K.MISPLACED_RULE),
        (_no_state, _K.UNSCORED_RULE),
    ],
    ids=["agreement", "disagreement", "not-allowed", "wrong-role", "unscored"],
)
def test_each_matching_rule_gets_one_result(make, kind):
    rule = make()
    comparison = compare_point(_point(*_EXTENSION), [rule])
    assert _only(comparison, rule).kind is kind


def test_a_misplaced_rule_says_why():
    comparison = compare_point(
        _point(*_EXTENSION), [_not_allowed(), _wrong_role()]
    )
    assert "allow no cs.fix_is_ready" in (
        _only(comparison, _not_allowed()).reason or ""
    )
    assert "CASE_OWNER" in (_only(comparison, _wrong_role()).reason or "")


def test_a_pec_move_rule_is_unscored():
    rule = _rule(
        action="pec.agree",
        pattern=RulePattern(proposal=frozenset({"INVITED"})),
    )
    point = _point(*_EXTENSION)
    consent = ConsentReading(
        proposals=(ProposalConsent(proposal="p", state="INVITED"),)
    )
    live = VendorPoint(
        position=point.position.model_copy(update={"consent": consent}),
        verdicts=point.verdicts,
    )
    result = _only(compare_point(live, [rule]), rule)
    assert result.kind is _K.UNSCORED_RULE
    assert result.proposal == "p"
    assert "#6677" in (result.reason or "")


@pytest.mark.spec("SHD-05-003")
def test_a_rule_undecided_at_a_point_gives_no_result_and_is_listed():
    rule = _rule(pattern=RulePattern(proposal=frozenset({"INVITED"})))
    comparison = compare_point(_point(*_EXTENSION), [rule])
    assert comparison.undecided == (rule,)
    assert all(r.rule != rule for r in comparison.results)


# --- SHD-05-012, SHD-05-014: what a banded result carries ---


@pytest.mark.spec("SHD-05-012")
@pytest.mark.parametrize(
    "make", [_agrees, _disagrees], ids=["agree", "disagree"]
)
def test_a_banded_result_carries_its_deciding_part_and_named_changes(make):
    rule = make()
    result = _only(compare_point(_point(*_EXTENSION), [rule]), rule)
    assert result.deciding_part is not None
    assert result.deciding_size is not None
    assert [c.desideratum for c in result.changes] == list(rule.desiderata)


@pytest.mark.spec("SHD-05-014")
def test_the_extension_disagreement_of_6492_carries_its_issue():
    """An authored rule that serves ``D ≺ P`` by an embargo extension,
    against the unhelpful band move advice gives it (#6492)."""
    (extension,) = [
        r
        for r in authored_rules()
        if r.action == "em.propose" and r.pattern.em == {EM.ACTIVE}
    ]
    assert extension.blind_spot == 6492
    assert "D≺P" in extension.desiderata
    result = _only(
        compare_point(_point(*_EXTENSION), authored_rules()), extension
    )
    assert result.kind is _K.RULE_DISAGREEMENT
    assert result.band is Band.UNHELPFUL
    assert result.deciding_size == 0
    assert result.blind_spot == 6492


def test_the_6492_example_deploys_the_fix_in_agreement():
    comparison = compare_point(_point(*_EXTENSION), authored_rules())
    deploy = [
        r
        for r in comparison.results
        if r.move == "cs.fix_is_deployed"
        and r.rule is not None
        and r.rule.roles == {CVDRole.VENDOR}
    ]
    assert [r.kind for r in deploy] == [_K.AGREEMENT]


def test_an_agreement_carries_no_blind_spot():
    rule = _agrees().model_copy(update={"blind_spot": 6492})
    result = _only(compare_point(_point(*_EXTENSION), [rule]), rule)
    assert result.kind is _K.AGREEMENT
    assert result.blind_spot is None


# --- SHD-05-021: unclaimed moves ---


@pytest.mark.spec("SHD-05-021")
def test_a_harm_free_move_no_rule_names_is_unclaimed_and_an_unhelpful_one_is_not():
    point = _point(*_EXTENSION)
    bands = {
        v.move.name: v.score.band
        for v in point.verdicts
        if v.score is not None
    }
    assert Band.HARM_FREE in bands.values()
    assert Band.UNHELPFUL in bands.values()
    comparison = compare_point(point, [])
    unclaimed = [r.move for r in comparison.results]
    assert all(r.kind is _K.UNCLAIMED_MOVE for r in comparison.results)
    assert sorted(unclaimed) == sorted(
        n for n, b in bands.items() if b is Band.HARM_FREE
    )


def test_a_move_a_matching_rule_names_is_not_unclaimed():
    comparison = compare_point(_point(*_EXTENSION), [_agrees()])
    assert "cs.fix_is_deployed" not in {
        r.move for r in comparison.results if r.kind is _K.UNCLAIMED_MOVE
    }


# --- SHD-05-024: an event that has happened makes a no-state action ---


@pytest.mark.spec("SHD-05-024")
def test_a_publication_after_p_is_unscored_and_before_p_joins_the_p_move():
    rule = _rule(action=Actions.PUBLISH_VULNERABILITY, desiderata=("P≺X",))
    after = _only(
        compare_point(_point(RM.ACCEPTED, CS.VFdPxa, EM.NONE), [rule]), rule
    )
    assert after.kind is _K.UNSCORED_RULE
    assert after.reason == NO_STATE_CHANGE
    assert after.move is None
    before = _only(compare_point(_point(*_EXTENSION), [rule]), rule)
    assert before.move == "cs.public_becomes_aware"
    assert before.kind in (_K.AGREEMENT, _K.RULE_DISAGREEMENT)


# --- SHD-05-028: a rule that names no desideratum is not measured ---


@pytest.mark.spec("SHD-05-028")
def test_a_rule_naming_no_desideratum_is_unscored_with_its_reason():
    rule = _disagrees().model_copy(
        update={"desiderata": (), "reason": "Coordination: a test reason"}
    )
    result = _only(compare_point(_point(*_EXTENSION), [rule]), rule)
    assert result.kind is _K.UNSCORED_RULE
    assert result.band is None
    assert NOT_MEASURED in (result.reason or "")
    assert "Coordination: a test reason" in (result.reason or "")


def test_a_misplaced_rule_is_misplaced_even_with_no_desideratum():
    rule = _not_allowed().model_copy(update={"desiderata": ()})
    result = _only(compare_point(_point(*_EXTENSION), [rule]), rule)
    assert result.kind is _K.MISPLACED_RULE


# --- SHD-05-030: the public's awareness is not a publication ---


@pytest.mark.spec("SHD-05-030")
def test_a_publication_where_an_exploit_forces_awareness_is_not_joined():
    rule = _rule(action=Actions.PUBLISH_VULNERABILITY, desiderata=("P≺A",))
    point = _point(RM.ACCEPTED, CS.VFdpXa, EM.NONE)
    forced = [v for v in point.verdicts if v.forced]
    assert [v.move.name for v in forced] == ["cs.public_becomes_aware"]
    result = _only(compare_point(point, [rule]), rule)
    assert result.kind is _K.UNSCORED_RULE
    assert result.move is None
    assert result.reason == FORCED_AWARENESS


# --- SHD-05-013: the comparison changes neither table ---


@pytest.mark.spec("SHD-05-013")
def test_the_comparison_changes_neither_table():
    authored = authored_rules()
    generated = generated_rules()
    before = (copy.deepcopy(authored), copy.deepcopy(generated))
    comparison = compare_point(_point(*_EXTENSION), authored)
    assert any(r.kind is _K.RULE_DISAGREEMENT for r in comparison.results)
    assert (authored_rules(), generated_rules()) == before


# --- SHD-05-002, SHD-05-011: a live case's vendors ---


@pytest.fixture(scope="module")
def two_vendors() -> tuple[VendorPoint, ...]:
    return case_points(case_standing(two_vendors_ledger().case_ledger()))


@pytest.mark.spec("SHD-05-002")
def test_a_coordinator_rule_matches_once_naming_the_matching_vendor(
    two_vendors,
):
    rule = _rule(
        roles=frozenset({CVDRole.COORDINATOR}),
        pattern=RulePattern(cs="VF...."),
        action=Actions.ENCOURAGE_VENDOR_TO_DEPLOY_FIX,
    )
    results = [
        r
        for c in compare_points(two_vendors, [rule])
        for r in c.results
        if r.rule == rule
    ]
    assert [r.vendor for r in results] == [VENDOR_1]


@pytest.mark.spec("SHD-05-011")
def test_a_rule_joins_the_band_of_its_own_vendor(two_vendors):
    rule = _rule(action="cs.public_becomes_aware", desiderata=("P≺X",))
    by_vendor = {
        r.vendor: r
        for c in compare_points(two_vendors, [rule])
        for r in c.results
        if r.rule == rule
    }
    assert by_vendor[VENDOR_1].participant == VENDOR_1
    assert by_vendor[VENDOR_2].participant == VENDOR_2
    assert by_vendor[VENDOR_1].band is Band.HARM_FREE
    assert by_vendor[VENDOR_2].band is Band.UNHELPFUL


@pytest.mark.spec("SHD-05-011")
def test_an_em_move_rule_joins_the_participant_in_its_role(two_vendors):
    owner_rule = _rule(
        action="em.propose",
        roles=frozenset({CVDRole.CASE_OWNER}),
        pattern=RulePattern(em=frozenset({EM.NONE})),
    )
    vendor_rule = owner_rule.model_copy(
        update={"roles": frozenset({CVDRole.VENDOR})}
    )
    (first, _) = compare_points(two_vendors, [owner_rule, vendor_rule])
    owner, vendor = (_only(first, owner_rule), _only(first, vendor_rule))
    assert owner.participant == OWNER
    assert vendor.participant in (VENDOR_1, VENDOR_2)


@pytest.mark.spec("SHD-05-018")
def test_every_position_of_one_vendor_compares_with_no_misplaced_rule():
    """Each authored rule that names a move matches only positions where
    move advice lists that move for the rule's roles."""
    comparisons = compare_points(vendor_points(), authored_rules())
    misplaced = [
        r
        for c in comparisons
        for r in c.results
        if r.kind is _K.MISPLACED_RULE
    ]
    assert misplaced == []
    kinds = {r.kind for c in comparisons for r in c.results}
    assert kinds == set(ResultKind) - {_K.MISPLACED_RULE}


_BANDED = {
    "band": Band.HARM_FREE,
    "deciding_part": Part.END,
    "deciding_size": 1,
    "move": "cs.fix_is_deployed",
}


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"kind": _K.UNSCORED_RULE, "reason": "r"},
            "only an unclaimed move has no rule",
        ),
        ({"kind": _K.AGREEMENT, "with_rule": True}, "carry a band"),
        (
            {
                "kind": _K.AGREEMENT,
                "with_rule": True,
                "band": Band.HARM_FREE,
            },
            "names its move and its part",
        ),
        (
            {
                "kind": _K.UNCLAIMED_MOVE,
                **_BANDED,
                "changes": [{"desideratum": "D≺P", "change": 1}],
            },
            "only a banded rule result carries its changes",
        ),
        (
            {"kind": _K.UNCLAIMED_MOVE, **_BANDED, "blind_spot": 6492},
            "only a rule disagreement carries a blind spot",
        ),
        (
            {"kind": _K.MISPLACED_RULE, "with_rule": True},
            "a misplaced or unscored rule says why",
        ),
    ],
    ids=[
        "rule-less",
        "agreement-without-band",
        "band-without-part",
        "unclaimed-with-changes",
        "unclaimed-with-blind-spot",
        "misplaced-without-reason",
    ],
)
def test_a_result_whose_fields_do_not_fit_its_kind_is_refused(fields, message):
    fields = dict(fields)
    if fields.pop("with_rule", False):
        fields["rule"] = _no_state()
    with pytest.raises(ValueError, match=message):
        RuleResult.model_validate({"vendor": "v", **fields})
