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
"""Ratchets over the *checked* half of the scenario generate-vs-check split.

``test_demo_scenario_artifacts.py`` covers the generated artifacts.  This module
covers the consumers ADR-0098 routes to a check instead, because they hold prose
the registry does not and should not carry: the ``mkdocs.yml`` nav, the per-scenario
DEMOMA-16 requirements, the ``notes/`` scenario tables, the planned-scenario
register, and the two ratchets over states that must never appear (a restated
count, a stray include directive).

Every positive assertion here is paired with a **negative** one that mutates a
fixture tree until the check fires.  A consistency check that cannot be made to
fail is indistinguishable from a consistency check that does nothing, and these
are exactly the checks nobody will notice are inert: they pass on a correct
repository, which is the state the repository is normally in.

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11-006 through DEMOCI-11-008,
DEMOCI-11-010; ``specs/meta-specifications.yaml`` MS-13-003.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.metadata.demo_scenarios.prose_checks import (
    SCENARIO_TABLES,
    SCENARIO_TABLE_CONSUMERS,
    consistency_problems,
    missing_event_type_requirements,
    missing_narrative_nav_entries,
    restated_counts,
    scenario_table_problems,
    stray_scenario_includes,
)
from vultron.metadata.demo_scenarios.scenario_groups import (
    PLANNED_REGISTER,
    partition_problems,
    per_scenario_event_type_requirements,
    planned_scenarios,
    scenario_spec_groups,
)
from vultron.metadata.markdown_tables import (
    iter_sections,
    iter_tables,
    split_row,
)
from vultron.metadata.specs.registry import load_registry

_REPO_ROOT = Path(__file__).parents[2]

#: A scenario the registry does not hold, used to make a check fire without
#: touching a real scenario module.
_FAKE = ScenarioSpec(
    name="zz-fake",
    label="ZZ-fake",
    participants="Finder + Vendor",
    feature="Fixture scenario; never registered",
    in_pr_set=True,
)

#: The only registered scenario with no spec group of its own, tracked as
#: ISSUE-3495.  Pinned as a named exception rather than left implicit so that a
#: *second* unspecified scenario fails instead of joining it silently.
_UNSPECIFIED_REGISTERED = frozenset({"fcv-reject"})


@pytest.fixture
def prose_root(tmp_path: Path) -> Path:
    """A throwaway tree holding copies of every checked prose consumer.

    Copied rather than synthesised so a negative test starts from exactly what
    is committed: a fixture that wrote its own starting state could report the
    mutation it introduced while the real file was already wrong for another
    reason.
    """
    paths = {table.path for table in SCENARIO_TABLES}
    paths.update(SCENARIO_TABLE_CONSUMERS)
    paths.add(PLANNED_REGISTER)
    paths.add("mkdocs.yml")
    for relative in sorted(paths):
        source = _REPO_ROOT / relative
        if not source.is_file():
            continue
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return tmp_path


# ---------------------------------------------------------------------------
# markdown_tables — the shared parser both check modules read prose with
# ---------------------------------------------------------------------------


def test_iter_tables_carries_the_heading_and_columns() -> None:
    """A table is returned with the section heading it sits under."""
    text = "# Top\n\n## Rows\n\n| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
    (table,) = iter_tables(text)
    assert table.heading == "Rows"
    assert table.columns == ("A", "B")
    assert table.rows == (("1", "2"), ("3", "4"))
    assert table.column("B") == ("2", "4")


def test_iter_tables_requires_a_delimiter_row() -> None:
    """Prose containing pipes is not a table.

    Without this guard the parser accepts a table whose header was deleted, and
    reports its first data row as the column names.
    """
    text = "## Prose\n\n| this looks like a row but has no delimiter |\n"
    assert iter_tables(text) == ()


@pytest.mark.parametrize(
    "delimiter", ["|---|---|", "|:---:|:---:|", "|:--|--:|", "|-|-|"]
)
def test_iter_tables_accepts_every_delimiter_spelling(delimiter: str) -> None:
    """One dash is enough, and alignment colons are allowed.

    A stricter pattern makes a table written ``|:--|--:|`` invisible rather than
    wrong, and invisible is the failure mode these checks exist to remove: a
    scenario table nothing parses is a scenario table nothing ratchets.
    """
    text = f"## Rows\n\n| A | B |\n{delimiter}\n| 1 | 2 |\n"
    (table,) = iter_tables(text)
    assert table.rows == (("1", "2"),)


def test_iter_tables_keeps_a_header_only_table() -> None:
    """A header with no body rows is a table with no rows, not absent.

    The distinction carries a diagnostic: "the table moved or was renamed" and
    "the table is there and empty" are different repairs, and collapsing them
    reports the first when the second is true.
    """
    (table,) = iter_tables("## Rows\n\n| A |\n|---|\n")
    assert table.columns == ("A",)
    assert table.rows == ()


def test_iter_sections_ignores_a_hash_inside_a_code_fence() -> None:
    """A ``#`` comment in a fenced block does not end a section.

    The hand-rolled predecessor could not tell the difference and documented
    that its target section must contain no fence; callers here inherit no such
    constraint.
    """
    text = "## Real\n\nbefore\n\n```bash\n# not a heading\n```\n\nafter\n"
    headings = [section.heading for section in iter_sections(text)]
    assert headings == ["", "Real"]
    body = "\n".join(line for _number, line in iter_sections(text)[1].lines)
    assert "before" in body and "after" in body


def test_iter_tables_skips_a_table_inside_a_code_fence() -> None:
    """A pipe table shown as an example is not a table.

    Without this, documenting a checked table's shape in a fenced block beneath
    it makes ``_table_for`` see two tables under one heading and fail with
    "expected exactly one" — a check broken by its own documentation.
    """
    text = (
        "## Rows\n\n| A |\n|---|\n| real |\n\n"
        "```markdown\n| A |\n|---|\n| example |\n```\n"
    )
    (table,) = iter_tables(text)
    assert table.rows == (("real",),)


def test_column_raises_on_an_unknown_header() -> None:
    """A renamed column fails loudly rather than reporting every row missing."""
    (table,) = iter_tables("## H\n\n| A |\n|---|\n| 1 |\n")
    with pytest.raises(KeyError, match="no 'Scenario' column"):
        table.column("Scenario")


# ---------------------------------------------------------------------------
# scenario_spec_groups — the MS-13-003 marker as the declared selector
# ---------------------------------------------------------------------------


def test_scenario_groups_name_only_known_scenarios() -> None:
    """Every marked group names a scenario in one of the two registers.

    A marker value matching neither register is a group specifying a scenario
    nobody can find, which is the failure the partition check would otherwise
    report as "absent from both" without saying the name was wrong.
    """
    named = set(scenario_spec_groups())
    known = {spec.name for spec in discover_scenarios()}
    known.update(entry.name for entry in planned_scenarios())
    assert named <= known, (
        "scenario spec groups name scenarios in neither register: "
        f"{sorted(named - known)}"
    )


def test_every_planned_scenario_has_a_spec_group() -> None:
    """A planned-register row is backed by a marked spec group.

    This is the direction that closes the ``vc`` defect: a row asserting a
    scenario is "specified but not yet built" is only true if something
    specifies it.
    """
    missing = sorted(
        {entry.name for entry in planned_scenarios()}
        - set(scenario_spec_groups())
    )
    assert not missing, (
        f"planned scenarios with no spec group: {missing}. Add "
        "'trigger: {type: scenario_start, value: <name>}' to the group "
        "(MS-13-003)."
    )


def test_registered_scenarios_without_a_spec_group_do_not_grow() -> None:
    """Only the known exception is registered without a spec group.

    DEMOCI-11-010 governs scenarios that *have* a group, so ``fcv-reject`` is
    not a partition failure — but it is a corpus gap (ISSUE-3495), and without
    this ratchet the next scenario written without a group joins it invisibly.
    """
    unspecified = {spec.name for spec in discover_scenarios()} - set(
        scenario_spec_groups()
    )
    assert unspecified == _UNSPECIFIED_REGISTERED, (
        "registered scenarios with no spec group changed: expected "
        f"{sorted(_UNSPECIFIED_REGISTERED)}, found {sorted(unspecified)}. A new "
        "scenario needs a spec group carrying MS-13-003's scenario_start "
        "marker; if ISSUE-3495 closed, narrow this expectation."
    )


def _spec_file(groups: list[dict[str, object]]) -> dict[str, object]:
    """Return a minimal valid spec file wrapping *groups*."""
    return {
        "id": "SCN",
        "title": "Scenario Spec",
        "description": "Fixture spec file",
        "version": "0.1",
        "scope": ["prototype"],
        "groups": groups,
    }


def _group(group_id: str, value: str) -> dict[str, object]:
    """Return a minimal scenario_start group whose marker names *value*."""
    return {
        "id": group_id,
        "title": f"{value} Scenario",
        "trigger": {"type": "scenario_start", "value": value},
        "specs": [
            {
                "id": f"{group_id}-001",
                "priority": "MUST",
                "kind": "project",
                "statement": f"{group_id}-001 MUST reach VFDPxa",
                "rationale": "Fixture",
            }
        ],
    }


def test_scenario_spec_groups_rejects_a_malformed_marker_value(
    tmp_path: Path,
) -> None:
    """A marker value outside the name grammar is a declaration error.

    Returning it would make the partition check compare a name that can match
    neither register and report the scenario as absent from both, pointing the
    author at the registers rather than at the typo.
    """
    (tmp_path / "specs.yaml").write_text(
        yaml.dump(_spec_file([_group("SCN-01", "Not A Name")]))
    )
    with pytest.raises(ValueError, match="not a valid scenario name"):
        scenario_spec_groups(load_registry(tmp_path))


def test_scenario_spec_groups_rejects_a_duplicated_scenario(
    tmp_path: Path,
) -> None:
    """Two groups claiming one scenario would let one group's omission hide."""
    (tmp_path / "specs.yaml").write_text(
        yaml.dump(_spec_file([_group("SCN-01", "fv"), _group("SCN-02", "fv")]))
    )
    with pytest.raises(ValueError, match="claimed by two spec groups"):
        scenario_spec_groups(load_registry(tmp_path))


# ---------------------------------------------------------------------------
# per-scenario DEMOMA-16 requirements — selected by statement, never by ID range
# ---------------------------------------------------------------------------


def test_every_registered_scenario_has_an_event_type_requirement() -> None:
    """Each registered scenario has its own DEMOMA-16 requirement."""
    missing = missing_event_type_requirements()
    assert not missing, (
        f"registered scenarios with no per-scenario DEMOMA-16 requirement: "
        f"{missing} (DEMOCI-11-007)"
    )


@pytest.mark.parametrize(
    "spec_id",
    ["DEMOMA-16-001", "DEMOMA-16-008", "DEMOMA-16-012", "DEMOMA-16-013"],
)
def test_non_per_scenario_requirements_are_not_selected(spec_id: str) -> None:
    """The four DEMOMA-16 requirements that are not per-scenario stay excluded.

    Named individually because an ID-range selector would take three of them
    (DEMOMA-16-008 sits inside the apparent span, -012 and -013 immediately
    after it) and DEMOCI-11-007 warns specifically against that. -001 states the
    universal types; -008 is the spec-to-test sync rule; -012 and -013 are FCVCV
    event *counts*, not an expected-event-types list.
    """
    selected = {
        requirement
        for requirements in per_scenario_event_type_requirements().values()
        for requirement in requirements
    }
    assert spec_id not in selected


def test_per_scenario_requirements_cover_the_unbuilt_scenarios() -> None:
    """``fcvd`` and ``vc`` are mapped even though neither is registered.

    The registry-to-spec direction alone would ignore DEMOMA-16-014 and -015,
    which is the blind spot that let a ``vc`` row sit in a table of available
    demos with a spec group, a tracking issue and no implementation.
    """
    mapping = per_scenario_event_type_requirements()
    assert mapping["fcvd"] == ("DEMOMA-16-014",)
    assert mapping["vc"] == ("DEMOMA-16-015",)


# ---------------------------------------------------------------------------
# the planned-scenario register and the partition (DEMOCI-11-010)
# ---------------------------------------------------------------------------


def test_planned_register_rows_carry_an_issue_and_spec_ids() -> None:
    """Every register row parses into a name, an issue and spec IDs."""
    entries = planned_scenarios()
    assert entries, "the planned-scenario register is empty"
    for entry in entries:
        assert entry.issues, f"{entry.name} names no tracking issue"
        assert entry.spec_ids, f"{entry.name} names no spec IDs"


def test_planned_register_requires_its_heading(prose_root: Path) -> None:
    """A renamed heading fails structurally rather than reading as empty."""
    target = prose_root / PLANNED_REGISTER
    target.write_text(
        target.read_text().replace(
            "## Planned scenario register", "## Some other heading"
        )
    )
    with pytest.raises(ValueError, match="no table under a"):
        planned_scenarios(prose_root)


def test_partition_holds_on_the_committed_tree() -> None:
    """Every spec'd scenario sits in exactly one register (DEMOCI-11-010)."""
    problems = partition_problems()
    assert not problems, "\n".join(problems)


def test_partition_reports_a_scenario_in_both_registers() -> None:
    """A planned scenario that is also registered is reported."""
    both = discover_scenarios() + (
        ScenarioSpec(
            name="fcvd",
            label="FCVD",
            participants="Finder + Coordinator + Vendor + Deployer",
            feature="Fixture: pretend fcvd is built",
            in_pr_set=False,
        ),
    )
    problems = partition_problems(specs=both)
    assert any("in both registers" in problem for problem in problems)


def test_partition_reports_a_scenario_in_neither_register() -> None:
    """A spec'd scenario that is neither registered nor planned is reported."""
    without_fv = tuple(
        spec for spec in discover_scenarios() if spec.name != "fv"
    )
    problems = partition_problems(specs=without_fv)
    assert any(
        "'fv' (DEMOMA-06) is in neither register" in problem
        for problem in problems
    )


def test_partition_reports_a_planned_row_with_no_spec_group(
    prose_root: Path,
) -> None:
    """A register row nothing specifies is reported."""
    target = prose_root / PLANNED_REGISTER
    target.write_text(
        target.read_text().replace(
            "| `vc` |", "| `zz-fake` | #1 | DEMOMA-99 | fixture |\n| `vc` |", 1
        )
    )
    problems = partition_problems(root=prose_root)
    assert any(
        "'zz-fake'" in problem and "no spec group specifies it" in problem
        for problem in problems
    )


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("#2591", "names no tracking issue"),
        ("DEMOMA-25, DEMOMA-16-015", "names no spec IDs"),
    ],
)
def test_partition_reports_an_incomplete_planned_row(
    prose_root: Path, cell: str, expected: str
) -> None:
    """DEMOCI-11-010 requires both the tracking issue and the spec IDs.

    The whole cell is emptied, not one ID within it: clearing ``DEMOMA-25``
    alone leaves ``DEMOMA-16-015`` behind, and the row still names *a* spec ID.
    """
    target = prose_root / PLANNED_REGISTER
    text = target.read_text()
    assert text.count(cell) >= 1
    target.write_text(text.replace(cell, "", 1))
    problems = partition_problems(root=prose_root)
    assert any(expected in problem for problem in problems)


# ---------------------------------------------------------------------------
# mkdocs nav completeness (DEMOCI-11-007)
# ---------------------------------------------------------------------------


def test_every_narrative_page_is_in_the_mkdocs_nav() -> None:
    """Each registered scenario's narrative page is reachable from the nav."""
    missing = missing_narrative_nav_entries()
    assert not missing, (
        f"scenario narrative pages absent from the mkdocs nav: {missing}. The "
        "nav's labels are hand-written, so it is checked for completeness "
        "rather than generated (DEMOCI-11-007)."
    )


def test_nav_check_reports_an_unnavved_scenario() -> None:
    """A scenario whose narrative page is not in the nav is reported."""
    missing = missing_narrative_nav_entries(specs=(_FAKE,))
    assert missing == ["zz-fake: docs/topics/scenarios/zz-fake.md"]


# ---------------------------------------------------------------------------
# the notes/ scenario tables (DEMOCI-11-007)
# ---------------------------------------------------------------------------


def test_notes_scenario_tables_agree_with_the_registry() -> None:
    """Every declared ``notes/`` scenario table holds the registry's rows."""
    problems = scenario_table_problems()
    assert not problems, "\n".join(problems)


def test_scenario_table_check_reports_a_missing_row(prose_root: Path) -> None:
    """Dropping a row from a checked table is reported, naming the table.

    The row is located by parsing its first cell, not by a string prefix: the
    committed tables pad the ``Scenario`` column for readability, so
    ``startswith("| fv  ")`` would stop finding the row the moment someone
    reflowed the table and this test would pass vacuously.
    """
    table = SCENARIO_TABLES[0]
    target = prose_root / table.path
    kept = [
        line
        for line in target.read_text().splitlines()
        if not (line.startswith("|") and split_row(line)[0].strip() == "fv")
    ]
    target.write_text("\n".join(kept) + "\n")
    problems = scenario_table_problems(prose_root)
    assert any(table.heading in problem for problem in problems)


def test_scenario_table_check_reports_a_wrong_spec_id(
    prose_root: Path,
) -> None:
    """The ``Spec`` column is checked against the spec corpus, not just present.

    The wrong ID is a *real* requirement belonging to another scenario
    (DEMOMA-16-003 specifies FVV), not a made-up one. That is the mistake a
    copy-pasted row actually makes, and an existence check would pass it. It
    also keeps this fixture from citing a phantom spec ID, which SR-04-008
    rejects repo-wide.
    """
    table = next(
        candidate
        for candidate in SCENARIO_TABLES
        if candidate.spec_column is not None
    )
    target = prose_root / table.path
    target.write_text(
        target.read_text().replace(
            "| FV | DEMOMA-16-002 |", "| FV | DEMOMA-16-003 |", 1
        )
    )
    problems = scenario_table_problems(prose_root)
    assert any(
        "DEMOMA-16-003" in problem and "'FV'" in problem
        for problem in problems
    )


# ---------------------------------------------------------------------------
# no restated counts (DEMOCI-11-008)
# ---------------------------------------------------------------------------


def test_no_consumer_restates_the_scenario_count() -> None:
    """No scenario-table consumer states how many scenarios there are."""
    findings = restated_counts()
    assert not findings, "\n".join(findings)


@pytest.mark.parametrize(
    "prose",
    [
        "The 9 demo scenarios each exercise a path.",
        "There are nine scenarios.",
        "the full 9-scenario suite runs on main",
        "all eight multi-actor\nscenarios emit it",
    ],
)
def test_count_check_flags_a_restatement(prose_root: Path, prose: str) -> None:
    """Digits, words, the hyphenated form, and a wrapped count all fire.

    The wrapped case is not hypothetical: one live restatement read ``all eight
    multi-actor\\n  scenarios``, which a line-at-a-time scan misses entirely.
    """
    target = _markdown_consumer(prose_root)
    target.write_text(f"# Heading\n\n{prose}\n")
    assert restated_counts(prose_root)


@pytest.mark.parametrize(
    "prose",
    [
        "## Change history\n\nlist updated from 8 to 9 scenarios",
        "## Changelog\n\nthe suite grew to 9 scenarios",
    ],
)
def test_count_check_exempts_a_history_section(
    prose_root: Path, prose: str
) -> None:
    """A change-history section records a past state and keeps its count.

    Rewriting it would destroy the record rather than remove a copy, so the
    exemption is keyed on the heading — visible to whoever writes the sentence.
    """
    target = _markdown_consumer(prose_root)
    target.write_text(f"# Heading\n\n{prose}\n")
    assert not restated_counts(prose_root)


@pytest.mark.parametrize(
    "prose",
    [
        "added by PR #2018 as a scenario-specific type",
        "the FCVCV 5-Party Scenario involves five actors",
        "a two-actor baseline",
        "one scenario per matrix entry",
        "the DEMOMA-16 scenario event types are per-scenario",
        "see ADR-0098 scenarios for the rationale",
    ],
)
def test_count_check_ignores_text_that_counts_something_else(
    prose_root: Path, prose: str
) -> None:
    """An issue number, a spec ID, a decision ID, a party count: not findings.

    Each shape appears in live prose in these very files. The ID cases are the
    reason the guard is ``(?<![#\\w-])`` rather than ``(?<!#)``: ``DEMOMA-16``
    and ``ADR-0098`` both end in digits that a bare word-boundary reads as a
    count, and these files cite spec and ADR IDs next to the word "scenario"
    constantly.
    """
    target = _markdown_consumer(prose_root)
    target.write_text(f"# Heading\n\n{prose}\n")
    assert not restated_counts(prose_root)


def test_count_check_flags_two_modifier_words(prose_root: Path) -> None:
    """``all nine multi-actor demo scenarios`` is a restatement.

    Two modifier words are allowed because real prose uses them; the guard that
    keeps ``#2018 as a scenario-specific type`` out is the identifier lookbehind,
    not a one-word limit.
    """
    target = _markdown_consumer(prose_root)
    target.write_text("# Heading\n\nall nine multi-actor demo scenarios\n")
    assert restated_counts(prose_root)


def test_count_check_does_not_section_a_non_markdown_consumer(
    prose_root: Path,
) -> None:
    """A ``#`` comment is not a heading, so it cannot grant the exemption.

    ``demo-integration.yml`` is ~50 comment lines. Sectioning it on ``#`` would
    make every comment a "heading", and one containing the word "history" would
    then silence DEMOCI-11-008 for everything below it.
    """
    target = prose_root / ".github" / "workflows" / "demo-integration.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# Change history of the matrix\n"
        "#   push to main — full 9-scenario suite\n"
    )
    findings = restated_counts(prose_root)
    assert any("9-scenario" in finding for finding in findings)


@pytest.mark.parametrize("heading", ["Prechangelog", "Ahistorical notes"])
def test_history_exemption_needs_the_whole_word(
    prose_root: Path, heading: str
) -> None:
    """The exemption is a word match, not a substring match.

    ``\\b(?:change )?history|changelog\\b`` binds each ``\\b`` to one outer
    alternative, so it exempts any heading merely *containing* "changelog" —
    handing a silent opt-out to a heading that was never meant to have one.
    """
    target = _markdown_consumer(prose_root)
    target.write_text(f"## {heading}\n\nthe 9 demo scenarios\n")
    assert restated_counts(prose_root)


def _markdown_consumer(root: Path) -> Path:
    """Return a declared markdown consumer to write fixture prose into."""
    return root / next(
        path
        for path in SCENARIO_TABLE_CONSUMERS
        if path.endswith(".md") and path.startswith("notes/")
    )


# ---------------------------------------------------------------------------
# no stray include directives (DEMOCI-11-006)
# ---------------------------------------------------------------------------


def test_no_stray_scenario_include_directives() -> None:
    """No file outside the MkDocs tree sources a scenario table by include."""
    findings = stray_scenario_includes()
    assert not findings, "\n".join(findings)


def test_include_check_flags_a_scenario_table_include(
    prose_root: Path,
) -> None:
    """An include directive naming a scenario table outside docs/ is reported."""
    target = prose_root / "notes" / "fixture.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '# Fixture\n\n{% include-markdown "../vultron/demo/scenario/README.md" %}\n'
    )
    findings = stray_scenario_includes(prose_root)
    assert len(findings) == 1
    assert "notes/fixture.md:3" in findings[0]


def test_include_check_ignores_a_directive_with_no_target(
    prose_root: Path,
) -> None:
    """``AGENTS.md`` cites the directive in prose and must not trip the check.

    A directive with no quoted target cannot source anything, so it is a mention
    of the mechanism rather than a use of it. This is the qualifier that keeps
    DEMOCI-11-006's ratchet from firing on its own documentation.
    """
    target = prose_root / "AGENTS.md"
    target.write_text(
        "# Fixture\n\nshares content by `{% include-markdown %}` fragment\n"
    )
    assert stray_scenario_includes(prose_root) == []


def test_include_check_ignores_a_non_scenario_include(
    prose_root: Path,
) -> None:
    """The "for a scenario table" qualifier is load-bearing, not decoration."""
    target = prose_root / "notes" / "fixture.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('# Fixture\n\n{% include-markdown "./glossary.md" %}\n')
    assert stray_scenario_includes(prose_root) == []


# ---------------------------------------------------------------------------
# the checks reach the hook that developers actually run
# ---------------------------------------------------------------------------


def test_consistency_problems_is_clean_on_the_committed_tree() -> None:
    """``demo-scenarios --check`` reports nothing on a correct repository."""
    problems = consistency_problems()
    assert not problems, "\n".join(problems)


def test_consistency_problems_survives_a_broken_register(
    prose_root: Path,
) -> None:
    """A structural register failure becomes a problem line, not a traceback.

    ``--check`` runs from a pre-commit hook, where an exception tells the
    developer less than the exception's own message does.
    """
    target = prose_root / PLANNED_REGISTER
    target.write_text("# Future Demo Ideas\n\nno register here\n")
    problems = consistency_problems(prose_root)
    assert any("Planned scenario register" in problem for problem in problems)
