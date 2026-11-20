"""The action rules on the case shadow tool's page, run headless with
Streamlit's ``AppTest`` (#6676 AC-4).

The rv recording reaches the #6492 extension position (the vendor's report
accepted, its fix ready, an embargo active) just after entry #16, and ends
with the embargo exited and the case public: the page's rules follow the
picked point.

Spec: SHD-06-001, SHD-06-003, SHD-06-006.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterator
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from vultron.config import config_override
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.action_rules import ResultKind
from vultron.shadow.analysis import analyse, point_analysis
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.app import APP_PATH
from vultron.shadow.readers import VultronCaseReader

#: Seconds one script run may take; the first run imports the measures.
_TIMEOUT = 60

_RV = RECORDINGS_DIR / "rv" / "case-actor.jsonl"

#: Just after this entry of the rv recording the vendor stands at the
#: #6492 extension position.
_EXTENSION_ENTRY = 16

#: The columns of the rules the bands check.
_CHECKED = [
    "Vendor",
    "Result",
    "Rule",
    "Roles",
    "Action",
    "Move",
    "Who moves",
    "Deciding part",
    "Named desiderata",
    "Note",
]

#: The columns of the rules with no number.
_UNNUMBERED = ["Vendor", "Result", "Rule", "Roles", "Action", "Why no number"]

_DISAGREEMENT = view.RESULT_FLAGS[ResultKind.RULE_DISAGREEMENT]
_MISPLACED = view.RESULT_FLAGS[ResultKind.MISPLACED_RULE]


def _rule_tables(at: AppTest) -> dict[str, list[dict[Hashable, Any]]]:
    """The page's two action-rule tables, each as its rows; empty for one
    drawn empty."""
    found: dict[str, list[dict[Hashable, Any]]] = {
        "checked": [],
        "unnumbered": [],
    }
    for frame in at.dataframe:
        columns = frame.value.columns.tolist()
        for name, wanted in (
            ("checked", _CHECKED),
            ("unnumbered", _UNNUMBERED),
        ):
            if columns == wanted:
                found[name] = frame.value.to_dict("records")
    return found


def _expected(log_index: int | None) -> view.RuleRows:
    """The rows the view gives the rv case at *log_index*, or now."""
    analysis = analyse(
        VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RV))
    )
    if log_index is not None:
        analysis = point_analysis(analysis, log_index)
    assert analysis.standing is not None
    return view.action_rule_rows(
        view.rule_comparisons(analysis.standing), analysis.actor_names
    )


def _point_picker(at: AppTest):
    (picker,) = [box for box in at.selectbox if box.label.startswith("Show")]
    return picker


@pytest.fixture
def rv_page() -> Iterator[AppTest]:
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(RECORDINGS_DIR)):
        at = AppTest.from_file(str(APP_PATH), default_timeout=_TIMEOUT).run()
        at.selectbox[0].select("rv/case-actor.jsonl").run()
        assert not at.exception
        yield at


@pytest.mark.spec("SHD-06-001")
@pytest.mark.spec("SHD-06-003")
def test_the_rules_follow_the_picked_point_and_flag_the_extension(rv_page):
    """At the extension position the page shows the matching rules beside
    the bands and flags the #6492 rule disagreement; where the case stands
    now it shows that point's rules, and the flag is gone."""
    now = _rule_tables(rv_page)
    assert "Action rules" in [str(h.value) for h in rv_page.subheader]
    _point_picker(rv_page).select(_EXTENSION_ENTRY).run()
    assert not rv_page.exception
    at_point = _rule_tables(rv_page)
    expected = _expected(_EXTENSION_ENTRY)
    assert at_point["checked"] == [dict(r) for r in expected.checked]
    assert at_point["unnumbered"] == [dict(r) for r in expected.unnumbered]
    (extension,) = [
        r
        for r in at_point["checked"]
        if r["Result"] == _DISAGREEMENT and r["Move"] == "em.propose"
    ]
    assert "cites blind spot #6492" in str(extension["Note"])
    assert any(
        str(w.value).startswith(f"{expected.flagged} flagged")
        for w in rv_page.warning
    )
    assert now != at_point
    assert now["checked"] == [dict(r) for r in _expected(None).checked]
    assert _DISAGREEMENT not in {r["Result"] for r in now["checked"]}


@pytest.mark.spec("SHD-06-006")
def test_the_rules_with_no_number_are_shown_apart(rv_page):
    """An unscored rule is listed with why it has no number, never with a
    deciding part."""
    tables = _rule_tables(rv_page)
    assert tables["unnumbered"]
    assert {r["Result"] for r in tables["unnumbered"]} <= {
        view.RESULT_FLAGS[ResultKind.UNSCORED_RULE],
        view.UNDECIDED_FLAG,
    }
    assert all(r["Why no number"] for r in tables["unnumbered"])
    (expander,) = [
        e for e in rv_page.expander if str(e.label).startswith("Rules with")
    ]
    assert str(expander.label).endswith(f"({len(tables['unnumbered'])})")


_MISPLACED_PAGE = """
from test.measure.action_rules.builders import make_rule
from test.measure.history.builders import two_vendors_ledger
from vultron.enums.roles import CVDRole
from vultron.measure.standing import case_standing
from vultron.shadow.dashboard.page.action_rules import _show_action_rules

rule = make_rule(action="cs.fix_is_ready", roles=frozenset({CVDRole.VENDOR}))
_show_action_rules(
    case_standing(two_vendors_ledger().case_ledger()), {}, rules=[rule]
)
"""


@pytest.mark.spec("SHD-06-003")
def test_a_misplaced_rule_is_flagged_on_the_page():
    """A rule naming a move neither vendor may make here is flagged."""
    at = AppTest.from_string(_MISPLACED_PAGE, default_timeout=_TIMEOUT).run()
    assert not at.exception
    results = [r["Result"] for r in _rule_tables(at)["checked"]]
    assert results.count(_MISPLACED) == 2
    assert any("2 flagged results" in str(w.value) for w in at.warning)
