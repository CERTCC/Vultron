"""The authored action rules beside the move bands, as rows (#6676 AC-4).

Spec: SHD-06-002, SHD-06-003, SHD-06-006.
"""

import pytest

from test.measure.action_rules.builders import make_rule
from test.measure.history.builders import (
    VENDOR as BUILT_VENDOR,
    VENDOR_2 as BUILT_VENDOR_2,
    two_vendors_ledger,
)
from vultron.core.scoring.potential_actions import Actions
from vultron.core.states.cs import CS
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules import (
    PointComparison,
    Position,
    ResultKind,
    RulePattern,
    RuleResult,
    authored_rules,
)
from vultron.measure.standing import StandingRecord, case_standing
from vultron.shadow.dashboard import view

_NAMES = {BUILT_VENDOR: "Vendor One", BUILT_VENDOR_2: "Vendor Two"}


@pytest.fixture(scope="module")
def standing() -> StandingRecord:
    return case_standing(two_vendors_ledger().case_ledger())


def _publish():
    """A rule that the publication serves the end desiderata: the
    two-vendor case's trade-off move."""
    return make_rule(action="cs.public_becomes_aware", desiderata=("P≺X",))


def _of_rule(rows, number=1):
    return [r for r in rows if r["Rule"] == f"Rule {number}"]


def _rows(standing, *rules):
    table = list(rules)
    return view.action_rule_rows(
        view.rule_comparisons(standing, table), _NAMES, table
    )


@pytest.mark.spec("SHD-06-002")
def test_a_trade_off_move_agrees_for_one_vendor_and_disagrees_for_another(
    standing,
):
    rows = _rows(standing, _publish())
    by_vendor = {r["Vendor"]: r["Result"] for r in _of_rule(rows.checked)}
    assert by_vendor == {
        "Vendor One": view.RESULT_FLAGS[ResultKind.AGREEMENT],
        "Vendor Two": view.RESULT_FLAGS[ResultKind.RULE_DISAGREEMENT],
    }


def test_a_checked_rule_shows_its_deciding_part_and_named_changes(standing):
    (first, _) = _of_rule(_rows(standing, _publish()).checked)
    assert first["Rule"] == "Rule 1"
    assert first["Move"] == "cs.public_becomes_aware"
    assert first["Who moves"] == "Vendor One"
    assert str(first["Deciding part"]).startswith("end ")
    assert str(first["Named desiderata"]).startswith("P≺X ")


@pytest.mark.spec("SHD-06-003")
def test_a_rule_disagreement_and_a_misplaced_rule_are_flagged(standing):
    # Neither vendor can make its fix ready here: one has, and the other
    # has not accepted the report.
    not_allowed = make_rule(
        action="cs.fix_is_ready", roles=frozenset({CVDRole.VENDOR})
    )
    rows = _rows(standing, _publish(), not_allowed)
    flags = [r["Result"] for r in rows.checked if r["Rule"] != "—"]
    assert flags.count(view.RESULT_FLAGS[ResultKind.RULE_DISAGREEMENT]) == 1
    assert flags.count(view.RESULT_FLAGS[ResultKind.MISPLACED_RULE]) == 2
    assert rows.flagged == 3
    note = view.flagged_note(rows)
    assert note is not None and note.startswith("3 flagged results")
    assert all(
        str(f).startswith("⚠️")
        for f in flags
        if f != view.RESULT_FLAGS[ResultKind.AGREEMENT]
    )


def test_one_flagged_result_reads_in_the_singular(standing):
    rows = _rows(standing, _publish())
    note = view.flagged_note(rows)
    assert note is not None and note.startswith("1 flagged result:")


def test_no_flagged_result_gives_no_warning(standing):
    agrees = make_rule(
        action="cs.public_becomes_aware",
        desiderata=("P≺X",),
        pattern=RulePattern(cs="VF...."),
    )
    rows = _rows(standing, agrees)
    assert rows.flagged == 0
    assert view.flagged_note(rows) is None


@pytest.mark.spec("SHD-06-006")
def test_an_unscored_rule_has_no_number_and_says_why(standing):
    monitor = make_rule(action=Actions.MONITOR_FOR_ATTACKS)
    rows = _rows(standing, monitor)
    assert _of_rule(rows.checked) == []
    unscored = _of_rule(rows.unnumbered)
    assert {r["Vendor"] for r in unscored} == {"Vendor One", "Vendor Two"}
    for row in unscored:
        assert row["Result"] == view.RESULT_FLAGS[ResultKind.UNSCORED_RULE]
        assert "changes no state" in str(row["Why no number"])
        assert "Deciding part" not in row


@pytest.mark.spec("SHD-06-006")
def test_a_rule_with_a_pec_part_is_undecided_on_a_reading_without_consent(
    standing,
):
    agree = make_rule(
        action="pec.agree",
        roles=frozenset({CVDRole.VENDOR}),
        pattern=RulePattern(
            em=frozenset({EM.PROPOSED}),
            proposal=frozenset({EmbargoConsentState.INVITED}),
        ),
    )
    anywhere = agree.model_copy(
        update={"pattern": agree.pattern.model_copy(update={"em": None})}
    )
    rows = _rows(standing, anywhere)
    assert [r["Result"] for r in rows.unnumbered] == [view.UNDECIDED_FLAG] * 2
    assert {r["Why no number"] for r in rows.unnumbered} == {
        view.UNDECIDED_REASON
    }


def test_an_unclaimed_move_names_no_rule(standing):
    rows = _rows(standing)
    assert rows.checked
    for row in rows.checked:
        assert row["Result"] == view.RESULT_FLAGS[ResultKind.UNCLAIMED_MOVE]
        assert row["Rule"] == "—"
        assert row["Action"] == ""


def test_the_rows_number_the_authored_table_by_default(standing):
    rows = view.action_rule_rows(view.rule_comparisons(standing), _NAMES)
    numbered = [
        r for r in (*rows.checked, *rows.unnumbered) if r["Rule"] != "—"
    ]
    assert numbered
    table = authored_rules()
    for row in numbered:
        rule = table[int(str(row["Rule"]).removeprefix("Rule ")) - 1]
        assert (row["Roles"], row["Action"]) == (
            rule.roles_label,
            rule.action_label,
        )


def test_a_rule_outside_the_numbering_table_is_refused(standing):
    comparisons = view.rule_comparisons(standing, [_publish()])
    with pytest.raises(ValueError):
        view.action_rule_rows(comparisons, _NAMES, [])


def test_a_result_for_one_open_proposal_names_it():
    """A rule with a proposal part matches once for each open proposal, so
    its row names the proposal (SHD-05-020)."""
    rule = make_rule(
        action="em.terminate",
        roles=frozenset({CVDRole.VENDOR}),
        pattern=RulePattern(em=frozenset({EM.ACTIVE})),
    )
    result = RuleResult(
        kind=ResultKind.MISPLACED_RULE,
        vendor=BUILT_VENDOR,
        rule=rule,
        proposal="urn:uuid:proposal-1",
        move="em.terminate",
        reason="em.terminate is made by CASE_OWNER",
    )
    comparison = PointComparison(
        position=Position(
            vendor=BUILT_VENDOR, rm=RM.ACCEPTED, cs=CS.VFdpxa, em=EM.ACTIVE
        ),
        results=(result,),
    )
    (row,) = view.action_rule_rows([comparison], _NAMES, [rule]).checked
    assert row["Note"] == (
        "for proposal urn:uuid:proposal-1; em.terminate is made by CASE_OWNER"
    )
