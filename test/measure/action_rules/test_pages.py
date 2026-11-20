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


"""The action rules' generated docs: one command builds them, and a check
fails when the committed ones are stale (#6676 AC-5)."""

import re

import pytest

from test.measure.action_rules.builders import ACTION_RULES_GROUP
from vultron.measure.action_rules import (
    authored_rules,
    conditional_verdicts,
    generated_rules,
    move_advice_desiderata,
)
from vultron.measure.action_rules.pages import (
    AUTHORED_TABLE,
    COMPARISON,
    GENERATED_RULES,
    ROOT,
    WRITE_COMMAND,
    built_fragments,
    main,
    stale_fragments,
)
from vultron.measure.action_rules.report import comparison_report

pytestmark = ACTION_RULES_GROUP

_PAGE = ROOT / "docs/topics/measuring_cvd/action_rule_comparison.md"
_OTHER_USES = ROOT / "docs/topics/other_uses/action_rules.md"


def _pattern_of(math: str) -> str:
    """The ``vfdpxa`` pattern a table cell's math spells."""
    return math.strip("$").replace(r"\cdot", ".").replace(" ", "")


def _rows(text: str, heading: str | None = None) -> list[list[str]]:
    """The body rows of the table under *heading*, or of the only table."""
    if heading is not None:
        text = text.split(f"### {heading}\n", 1)[1].split("\n### ", 1)[0]
    rows = [line for line in text.splitlines() if line.startswith("| ")]
    return [
        [c.strip() for c in re.split(r"(?<!\\)\|", row)[1:-1]]
        for row in rows[1:]
    ]


@pytest.mark.spec("SHD-05-008")
def test_the_command_writes_every_fragment(tmp_path, capsys):
    assert main(["--write", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    for path in (GENERATED_RULES, COMPARISON, AUTHORED_TABLE):
        assert (tmp_path / path).read_text(encoding="utf-8") == (
            built_fragments()[path]
        )
        assert f"wrote {path}" in out
    assert main(["--check", "--root", str(tmp_path)]) == 0


@pytest.mark.spec("SHD-05-009")
def test_the_check_names_a_stale_or_missing_fragment(tmp_path, capsys):
    main(["--write", "--root", str(tmp_path)])
    capsys.readouterr()
    (tmp_path / COMPARISON).write_text("edited by hand\n", encoding="utf-8")
    (tmp_path / AUTHORED_TABLE).unlink()
    assert main(["--check", "--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert f"stale: {COMPARISON}; run {WRITE_COMMAND}" in err
    assert f"stale: {AUTHORED_TABLE}" in err
    assert str(GENERATED_RULES) not in err


@pytest.mark.spec("SHD-05-009")
def test_the_committed_fragments_are_current():
    """The committed fragments equal what the command builds from the
    current move advice and authored rules; run the command if not."""
    assert stale_fragments() == [], f"run {WRITE_COMMAND}"


@pytest.mark.spec("SHD-06-004")
def test_the_page_lists_every_generated_rule_and_conditional_verdict():
    text = built_fragments()[GENERATED_RULES]
    rules = _rows(text, "Generated rules")
    assert len(rules) == len(generated_rules())
    for row, rule in zip(rules, generated_rules(), strict=True):
        assert row[0] == f"`{rule.move}`"
        assert row[2] == str(rule.band)
        assert (row[3] != "") == rule.forced
    conditionals = _rows(text, "Conditional verdicts")
    assert [r[3] for r in conditionals] == [
        c.caveat for c in conditional_verdicts()
    ]


@pytest.mark.spec("SHD-06-004")
def test_the_page_states_each_rules_results_and_flags_disagreements():
    text = built_fragments()[COMPARISON]
    report = comparison_report()
    every = _rows(text, "Every result, rule by rule")
    expected = sum(len(r.spans) + len(r.conditionals) for r in report.rules)
    assert len(every) == expected
    flagged = _rows(text, "Rule disagreements and misplaced rules")
    assert flagged
    assert all(r[3].startswith("⚠️") for r in flagged)
    assert any("blind spot #6492" in r[3] for r in flagged)
    unclaimed = _rows(text, "Unclaimed moves")
    assert [r[0] for r in unclaimed] == [
        f"`{u.move}`" for u in report.unclaimed
    ]


@pytest.mark.spec("SHD-06-007")
def test_the_page_shows_each_rule_with_a_pec_part_as_undecided():
    rows = _rows(built_fragments()[COMPARISON], "Every result, rule by rule")
    numbers = [
        n
        for n, rule in enumerate(authored_rules(), start=1)
        if rule.pattern.reads_consent
    ]
    assert numbers
    for number in numbers:
        results = {r[3] for r in rows if r[0] == f"Rule {number}"}
        assert results == {"undecided"}


@pytest.mark.spec("SHD-06-004")
def test_the_page_is_in_the_nav_and_includes_its_fragments():
    nav = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "'topics/measuring_cvd/action_rule_comparison.md'" in nav
    page = _PAGE.read_text(encoding="utf-8")
    for fragment in (GENERATED_RULES, COMPARISON):
        assert f'{{% include-markdown "./{fragment.name}" %}}' in page
    other = _OTHER_USES.read_text(encoding="utf-8")
    assert f'{{% include-markdown "./{AUTHORED_TABLE.name}" %}}' in other


@pytest.mark.spec("SHD-06-005")
def test_the_authored_table_holds_one_row_for_each_carried_over_rule():
    rows = _rows(built_fragments()[AUTHORED_TABLE])
    carried = [
        (n, r) for n, r in enumerate(authored_rules(), start=1) if r.source
    ]
    assert len(rows) == len(carried)
    catalog = move_advice_desiderata()
    for row, (number, rule) in zip(rows, carried, strict=True):
        assert row[0] == str(number)
        assert _pattern_of(row[1].split("<br/>")[0]) == rule.pattern.cs
        for part in (rule.pattern.rm, rule.pattern.em, rule.pattern.proposal):
            for state in part or ():
                assert state.name in row[1]
        assert _pattern_of(row[2]) == rule.source.pattern
        assert row[3] == rule.roles_label
        action = rule.action if rule.move is None else rule.source.action
        assert row[4] == action.name.replace("_", " ").capitalize()
        assert row[5] == rule.reason.replace("|", r"\|")
        for desideratum in rule.desiderata:
            assert catalog[desideratum].notation in row[6]
        if rule.move is not None:
            assert row[7] == f"`{rule.move}`"


def test_a_pattern_with_other_parts_shows_them_beside_its_cs_part():
    rows = _rows(built_fragments()[AUTHORED_TABLE])
    (first, *_) = rows
    assert first[1].startswith("$") and "<br/>EM ACTIVE, REVISE" in first[1]
