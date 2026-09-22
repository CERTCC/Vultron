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

from vultron.demo.scenario.registry import (
    ScenarioSpec,
    discover_scenarios,
    is_scenario_name,
)
from vultron.metadata.base import mkdocs_config, nav_paths
from vultron.metadata.demo_scenarios.event_types import (
    UNIVERSAL_EVENT_TYPES,
    HarnessEventTypeError,
    additional_event_types,
    harness_event_types,
)
from vultron.metadata.demo_scenarios.prose_checks import (
    SCENARIO_TABLES,
    SCENARIO_TABLE_CONSUMERS,
    consistency_problems,
    missing_event_type_requirements,
    missing_narrative_nav_entries,
    restated_counts,
    scenario_set_statement_problems,
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

#: Registered scenarios allowed to have no spec group of their own.  Empty since
#: ISSUE-3495 gave ``fcv-reject`` DEMOMA-27, which is what makes the
#: registry-to-group direction checkable at all: while the set was non-empty the
#: assertion could only say "the exception has not grown", and a scenario written
#: without a group would have had to be added here to go green — visible, but
#: still a way in.  Keeping the constant rather than inlining ``set()`` leaves the
#: next genuine exception somewhere to be argued for, with this comment as the
#: bar it has to clear.
_UNSPECIFIED_REGISTERED: frozenset[str] = frozenset()


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
    # Each scenario's invariant harness, because the tick matrix and the
    # ``Additional required`` column are ratcheted against its
    # ``_XXX_EXPECTED_EVENT_TYPES`` constant. Without them ``harness_event_types``
    # finds no file, returns ``None``, and both checks skip every row — so a
    # fixture missing them would make those mutations look unreported.
    paths.update(spec.harness_path for spec in discover_scenarios())
    for relative in sorted(paths):
        source = _REPO_ROOT / relative
        # Every declared path must exist. Skipping a missing one would hide the
        # same hole the check itself used to have: a consumer that moved would
        # drop out of the fixture *and* out of coverage, with the suite green.
        assert source.is_file(), (
            f"{relative} is declared as a checked consumer but does not exist; "
            "update the declaration rather than letting the fixture skip it"
        )
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    # The spec corpus too, so the spec-side checks in ``consistency_problems``
    # resolve against a real registry rather than erroring into a problem line
    # and masking whichever prose mutation a test is actually making.
    shutil.copytree(_REPO_ROOT / "specs", tmp_path / "specs")
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


def test_every_registered_scenario_is_named_by_a_spec_group() -> None:
    """Every registered scenario has a spec group naming it (ISSUE-3495 AC-5).

    The registry-to-group direction, which completes DEMOCI-11-010's partition.
    DEMOCI-11-010 itself constrains only scenarios that *have* a group, so it
    cannot catch a built scenario with no group at all — that was ``fcv-reject``
    until DEMOMA-27, and the invitation-rejection path is the one covered by
    exactly one scenario, so it was the worst one to leave unspecified.

    Asserted as set equality against :data:`_UNSPECIFIED_REGISTERED` rather than
    ``assert not unspecified`` so that adding a genuine exception is a visible
    edit to a documented constant rather than a loosened assertion.
    """
    unspecified = {spec.name for spec in discover_scenarios()} - set(
        scenario_spec_groups()
    )
    assert unspecified == _UNSPECIFIED_REGISTERED, (
        "registered scenarios with no spec group changed: expected "
        f"{sorted(_UNSPECIFIED_REGISTERED)}, found {sorted(unspecified)}. A "
        "registered scenario needs a spec group carrying MS-13-003's "
        "trigger: {type: scenario_start, value: <name>} marker — see DEMOMA-27 "
        "for the smallest example."
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


def test_scenario_table_check_reports_a_wrong_pr_set_mark(
    prose_root: Path,
) -> None:
    """PR-set membership is ratcheted against ``in_pr_set`` (MS-16-002).

    Flipping a member to "covered by" is the drift this closes: the table would
    then disagree with the decorator that actually selects the CI matrix, and
    nothing else in the file could tell.
    """
    table = next(
        candidate
        for candidate in SCENARIO_TABLES
        if candidate.pr_set_column is not None
    )
    target = prose_root / table.path
    target.write_text(
        target.read_text().replace(
            "| fv | ✓ (member) |", "| fv | covered by fvcv-handoff |", 1
        )
    )
    problems = scenario_table_problems(prose_root)
    assert any(
        "'fv'" in problem and "in_pr_set=True" in problem
        for problem in problems
    )


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


# ---------------------------------------------------------------------------
# markdown_tables — the hazards the reader claims to absorb (ISSUE-3504 review)
# ---------------------------------------------------------------------------


def test_iter_sections_carries_the_heading_level() -> None:
    """Each section knows its depth, which is what lets a rule cover subsections."""
    text = "# One\n\na\n\n### Three\n\nb\n\n## Two\n\nc\n"
    levels = {
        section.heading: section.level for section in iter_sections(text)
    }
    assert levels == {"": 0, "One": 1, "Three": 3, "Two": 2}


@pytest.mark.parametrize("indent", ["", " ", "  ", "   "])
def test_iter_tables_skips_a_table_inside_an_indented_fence(
    indent: str,
) -> None:
    """CommonMark allows 1–3 spaces before a fence, and so does the reader.

    The negative half of the fence guarantee. An indented fence is the normal
    form inside a list item, and mkdocs-material admonitions require one
    (``MD046`` is disabled in this repository for that reason), so anchoring the
    fence at column 0 would leave the most common spelling untracked — and a
    pipe table documented inside one would be read as a real table.
    """
    fenced = (
        f"{indent}```markdown\n"
        f"{indent}| Scenario | x |\n"
        f"{indent}|---|---|\n"
        f"{indent}| fv | 1 |\n"
        f"{indent}```\n"
    )
    text = f"## Rows\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n{fenced}"
    tables = iter_tables(text)
    assert len(tables) == 1, (
        f"a fence indented by {len(indent)} space(s) was not tracked, so the "
        "example table inside it was parsed as real"
    )
    assert tables[0].columns == ("A", "B")


@pytest.mark.parametrize("indent", [" ", "  ", "   "])
def test_iter_sections_ignores_a_heading_inside_an_indented_fence(
    indent: str,
) -> None:
    """A ``#`` inside an indented fence is content, not a heading."""
    text = (
        f"## Real\n\n{indent}```text\n{indent}# Not A Heading\n{indent}```\n"
    )
    headings = [section.heading for section in iter_sections(text)]
    assert headings == ["", "Real"]


def test_split_row_drops_only_the_outer_delimiters() -> None:
    """The documented contract: outer pipes delimit, so no phantom cells."""
    assert split_row("| a | b | c |") == ("a", "b", "c")
    assert split_row("|a|b|") == ("a", "b")


def test_split_row_treats_an_escaped_pipe_as_a_literal() -> None:
    """``\\|`` is content, not a separator.

    Splitting on every pipe shifts every later column, so ``column("Spec")``
    would return the tail of its left-hand neighbour and the ratchet would fail
    while naming the wrong column.
    """
    assert split_row(r"| a \| b | y |") == ("a | b", "y")


def test_iter_tables_does_not_merge_two_adjacent_tables() -> None:
    """A delimiter row ends the table above it.

    A delimiter row is itself row-shaped, so without this the second table's
    header and delimiter become data rows of the first — and every "exactly one
    table under this heading" guard passes while handing the caller a table
    holding another table's header.
    """
    text = (
        "## Rows\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n"
        "| C | D |\n|---|---|\n| 3 | 4 |\n"
    )
    first, second = iter_tables(text)
    assert first.columns == ("A", "B")
    assert first.rows == (("1", "2"),)
    assert second.columns == ("C", "D")
    assert second.rows == (("3", "4"),)


def test_column_raises_key_error_naming_the_columns_it_found() -> None:
    """A renamed column fails loudly rather than reporting every row empty."""
    (table,) = iter_tables("## R\n\n| A | B |\n|---|---|\n| 1 | 2 |\n")
    with pytest.raises(KeyError, match="has no 'Missing' column"):
        table.column("Missing")


# ---------------------------------------------------------------------------
# The checks that had no negative test (ISSUE-3504 review)
# ---------------------------------------------------------------------------


def test_event_type_requirement_check_reports_an_unspecified_scenario() -> (
    None
):
    """``missing_event_type_requirements`` can be made to fire.

    Without this the check was inert-by-construction: stubbing the function to
    return nothing left the whole suite green, so the DEMOCI-11-007 requirement
    that every registered scenario has a per-scenario DEMOMA-16 entry was
    enforced by a function nothing could falsify.
    """
    missing = missing_event_type_requirements(specs=(_FAKE,))
    assert missing == [_FAKE.name]


def test_scenario_table_check_reports_a_renamed_heading(
    prose_root: Path,
) -> None:
    """A renamed table heading is a structural failure naming the heading."""
    table = SCENARIO_TABLES[0]
    target = prose_root / table.path
    target.write_text(
        target.read_text().replace(
            f"## {table.heading}", f"## {table.heading} (renamed)"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected exactly one table under"):
        scenario_table_problems(prose_root)


def test_consistency_problems_reports_a_renamed_column_not_a_traceback(
    prose_root: Path,
) -> None:
    """A renamed *column* reaches the CLI as a problem line.

    ``MarkdownTable.column()`` raises ``KeyError`` by design, and
    ``consistency_problems`` caught only ``ValueError`` — so the pre-commit hook
    answered a renamed column with a traceback while its own comment claimed
    both structural failures were wrapped.
    """
    target = prose_root / "notes/demo-ci-scenario-coverage.md"
    target.write_text(
        target.read_text().replace(
            "| Scenario | Covered by minimum set | Rationale |",
            "| Scenario | Covered by min set | Rationale |",
        ),
        encoding="utf-8",
    )
    problems = consistency_problems(prose_root)
    assert any("has no 'Covered by minimum set' column" in p for p in problems)


def test_restated_counts_raises_on_a_declared_consumer_that_moved(
    prose_root: Path,
) -> None:
    """A missing consumer is an error, not a silent skip.

    Skipping it would drop the file out of DEMOCI-11-008 coverage with every
    test still green, which is the opposite of what a ratchet is for.
    """
    (prose_root / SCENARIO_TABLE_CONSUMERS[2]).unlink()
    with pytest.raises(FileNotFoundError, match="does not exist"):
        restated_counts(prose_root)


def test_count_check_exempts_a_subsection_of_a_history_section(
    prose_root: Path,
) -> None:
    """The change-history exemption reaches nested headings.

    ``iter_sections`` is flat, so a ``#### PR log`` inside ``### Change history``
    is its own section whose heading does not match. Without inheritance the
    exemption fires on exactly the lines it exists to protect.
    """
    target = prose_root / "notes/demo-ci-scenario-coverage.md"
    original = target.read_text()
    assert "### Change history" in original
    target.write_text(
        original.replace(
            "### Change history", "### Change history\n\n#### PR log", 1
        ),
        encoding="utf-8",
    )
    assert restated_counts(prose_root) == []


def test_count_check_still_fires_after_a_history_section_closes(
    prose_root: Path,
) -> None:
    """A heading at or above the exempt level ends the exemption.

    The other half of inheritance: if leaving the section did not close it,
    every restatement below a change-history heading would be exempt.
    """
    target = prose_root / "notes/demo-ci-scenario-coverage.md"
    target.write_text(
        target.read_text() + "\n## Later\n\nNine scenarios run here.\n",
        encoding="utf-8",
    )
    problems = restated_counts(prose_root)
    assert any("'Nine scenarios'" in p for p in problems)


# ---------------------------------------------------------------------------
# The aggregate's wiring (ISSUE-3504 review)
# ---------------------------------------------------------------------------


def _mutate_nav(root: Path) -> str:
    """Drop one scenario narrative page from the nav."""
    target = root / "mkdocs.yml"
    spec = sorted(discover_scenarios(), key=lambda s: s.name)[0]
    leaf = spec.narrative_path.removeprefix("docs/")
    text = target.read_text()
    assert leaf in text
    target.write_text(text.replace(leaf, "topics/scenarios/gone.md"))
    return "missing from the mkdocs nav"


def _mutate_scenario_column(root: Path) -> str:
    """Misspell a scenario in a ratcheted ``Scenario`` column."""
    target = root / "notes/demo-ci-invariants.md"
    target.write_text(
        target.read_text().replace(
            "| FVV | DEMOMA-16-003", "| FVVV | DEMOMA-16-003"
        )
    )
    return "the registry has"


def _mutate_undeclared_table(root: Path) -> str:
    """Add a scenario table no ``SCENARIO_TABLES`` entry declares."""
    target = root / "notes/demo-ci-scenario-coverage.md"
    target.write_text(
        target.read_text()
        + "\n## Smuggled\n\n| Scenario | Note |\n|---|---|\n"
        "| fv | a |\n| fvv | b |\n"
    )
    return "no SCENARIO_TABLES entry declares it"


def _mutate_restated_count(root: Path) -> str:
    """Restate the scenario count in a declared consumer."""
    target = root / "notes/demo-ci-diagnostics.md"
    target.write_text(target.read_text() + "\nAll 9 scenarios do this.\n")
    return "restates the scenario count"


def _mutate_stray_include(root: Path) -> str:
    """Plant an include directive outside the MkDocs tree."""
    target = root / "notes/demo-ci-invariants.md"
    target.write_text(
        target.read_text()
        + '\n{% include-markdown "../docs/topics/scenarios/index.md" %}\n'
    )
    return "outside the MkDocs tree"


def _mutate_planned_register(root: Path) -> str:
    """Put a planned scenario in both registers at once."""
    target = root / PLANNED_REGISTER
    text = target.read_text()
    target.write_text(text.replace("| `fcvd` |", "| `fv` |", 1))
    return "fv"


def _mutate_tick(root: Path) -> str:
    """Tick an event type the scenario's harness constant does not require."""
    target = root / "notes/demo-ci-scenario-coverage.md"
    text = target.read_text()
    old = "| fv                | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   |   |   |"
    assert old in text
    target.write_text(
        text.replace(
            old,
            "| fv                | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   |   |",
        )
    )
    return "harness constant says otherwise"


@pytest.mark.parametrize(
    "mutate",
    [
        _mutate_nav,
        _mutate_scenario_column,
        _mutate_undeclared_table,
        _mutate_restated_count,
        _mutate_stray_include,
        _mutate_planned_register,
        _mutate_tick,
    ],
    ids=lambda fn: fn.__name__.removeprefix("_mutate_"),
)
def test_every_sub_check_reaches_the_aggregate(
    prose_root: Path, mutate: object
) -> None:
    """Each sub-check's finding reaches ``consistency_problems``.

    Coverage cannot see this gap: the clean-tree test executes every
    ``problems.extend(...)`` line, so deleting one of them left the whole suite
    green while ``demo-scenarios --check`` — the command the pre-commit hook
    actually runs — silently stopped reporting that requirement.
    """
    expected = mutate(prose_root)  # type: ignore[operator]
    problems = consistency_problems(prose_root)
    assert any(expected in problem for problem in problems), (
        f"mutation should have produced a problem containing {expected!r}; "
        f"got {problems}"
    )


def test_consistency_problems_is_empty_on_the_committed_tree(
    prose_root: Path,
) -> None:
    """The positive half: an unmutated copy of the tree reports nothing."""
    assert consistency_problems(prose_root) == []


# ---------------------------------------------------------------------------
# Planned-register structural guards (ISSUE-3504 review)
# ---------------------------------------------------------------------------


def test_planned_register_rejects_a_second_table_under_its_heading(
    prose_root: Path,
) -> None:
    """Two tables under the register heading is a structural failure.

    A scenario in the second copy can satisfy neither direction of the
    partition, so the guard must fire rather than silently read the first table.
    """
    target = prose_root / PLANNED_REGISTER
    text = target.read_text()
    marker = "| Scenario | Tracking issue | Spec IDs |"
    assert marker in text
    target.write_text(
        text.replace(
            marker,
            f"{marker[:0]}| Scenario | Extra |\n|---|---|\n| `vc` | x |\n\n{marker}",
            1,
        )
    )
    with pytest.raises(ValueError, match="Planned scenario register"):
        planned_scenarios(prose_root)


def test_planned_register_rejects_a_renamed_column(prose_root: Path) -> None:
    """Renaming a declared register column fails loudly.

    ``Tracking issue`` is the likeliest real edit to that table, and a positional
    read would silently take the spec-IDs cell as the issue reference.
    """
    target = prose_root / PLANNED_REGISTER
    target.write_text(
        target.read_text().replace("| Tracking issue |", "| Issue |", 1)
    )
    with pytest.raises((ValueError, KeyError)):
        planned_scenarios(prose_root)


def test_partition_reports_a_scenario_listed_twice_in_the_register(
    prose_root: Path,
) -> None:
    """A duplicated planned row is reported.

    One of four problem classes ``partition_problems`` emits, and the only one
    that had no negative test — so it could have been broken without anything
    failing.
    """
    target = prose_root / PLANNED_REGISTER
    text = target.read_text()
    row = [line for line in text.splitlines() if line.startswith("| `vc`")]
    assert row, "expected a `vc` row in the planned register"
    target.write_text(text.replace(row[0], f"{row[0]}\n{row[0]}", 1))
    problems = partition_problems(prose_root)
    assert any("vc" in problem for problem in problems), problems


# ---------------------------------------------------------------------------
# Extracted shared helpers, tested where they live (ISSUE-3504 review)
# ---------------------------------------------------------------------------


def test_nav_paths_flattens_every_nesting_level(tmp_path: Path) -> None:
    """``nav_paths`` returns every document path the nav reaches.

    Tested directly rather than only through its two callers, because it is a
    shared helper extracted from ``adr/index_gen`` in #3451: a change that broke
    the recursion would surface as "some ADR is missing from the nav", which
    reads like a docs problem rather than a parser one.
    """
    (tmp_path / "mkdocs.yml").write_text(
        "nav:\n"
        "  - Home: index.md\n"
        "  - Topics:\n"
        "      - One: topics/one.md\n"
        "      - Deeper:\n"
        "          - Two: topics/two.md\n"
        "  - bare.md\n",
        encoding="utf-8",
    )
    assert nav_paths(tmp_path) == {
        "index.md",
        "topics/one.md",
        "topics/two.md",
        "bare.md",
    }


def test_nav_paths_ignores_a_path_that_is_only_a_label(tmp_path: Path) -> None:
    """A nav *title* that looks like a path is not a document.

    The structural contract the docstring states: only leaf values count, so a
    section title is never mistaken for a page.
    """
    (tmp_path / "mkdocs.yml").write_text(
        "nav:\n  - notes.md: real.md\n", encoding="utf-8"
    )
    assert nav_paths(tmp_path) == {"real.md"}


def test_mkdocs_config_tolerates_the_custom_tags(tmp_path: Path) -> None:
    """``!ENV`` and ``!!python/name:`` do not stop the nav being read.

    ``mkdocs.yml`` carries both, so a plain ``safe_load`` raises and every nav
    check becomes a crash rather than a finding.
    """
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: !ENV [NAME, 'fallback']\n"
        "markdown_extensions:\n"
        "  - pymdownx.emoji:\n"
        "      emoji_index: !!python/name:material.extensions.emoji.twemoji\n"
        "nav:\n  - Home: index.md\n",
        encoding="utf-8",
    )
    assert mkdocs_config(tmp_path)["nav"] == [{"Home": "index.md"}]


@pytest.mark.parametrize(
    "name", ["fv", "fvcv-handoff", "rcv-embargo", "a1-b2"]
)
def test_is_scenario_name_accepts_the_registry_grammar(name: str) -> None:
    """The public predicate accepts what the registry accepts."""
    assert is_scenario_name(name)


@pytest.mark.parametrize(
    "name",
    ["", "FV", "fv_reject", "fv--x", "-fv", "fv-", "fv.py", "fv reject"],
)
def test_is_scenario_name_rejects_everything_else(name: str) -> None:
    """The rejections are the point: this predicate filters prose.

    Its callers pull backticked spans out of spec statements, where
    ``demo-integration.yml`` and ``push: branches: ["main"]`` also appear. A
    predicate that accepted a dot or a space would report those as scenarios.
    """
    assert not is_scenario_name(name)


def test_harness_event_types_reads_the_pytest_param_form() -> None:
    """The constant is read by AST, including the ``pytest.param`` wrapper.

    Read without importing so ``demo-scenarios --check`` — a pre-commit hook —
    does not execute nine test modules to answer a documentation question.
    """
    spec = next(s for s in discover_scenarios() if s.name == "fv")
    types = harness_event_types(spec, _REPO_ROOT)
    assert types is not None
    assert tuple(types[: len(UNIVERSAL_EVENT_TYPES)]) == UNIVERSAL_EVENT_TYPES


def test_harness_event_types_is_none_when_there_is_no_harness(
    tmp_path: Path,
) -> None:
    """An absent harness is ``None``, which DEMOCI-11-003 reports separately."""
    spec = next(s for s in discover_scenarios() if s.name == "fv")
    assert harness_event_types(spec, tmp_path) is None


def test_harness_event_types_rejects_an_unreadable_constant(
    tmp_path: Path,
) -> None:
    """A constant built by a call is refused rather than read as empty.

    "This scenario exercises no event types" is never the true answer, so
    returning an empty tuple would silently satisfy an all-blank matrix row.
    """
    spec = next(s for s in discover_scenarios() if s.name == "fv")
    target = tmp_path / spec.harness_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("_FV_EXPECTED_EVENT_TYPES = list(SOMETHING)\n")
    with pytest.raises(HarnessEventTypeError, match="not a list or tuple"):
        harness_event_types(spec, tmp_path)


def test_additional_event_types_is_the_non_universal_remainder() -> None:
    """The complement, which is what the ``Additional required`` column holds."""
    harness = (*UNIVERSAL_EVENT_TYPES, "invite_actor_to_case")
    assert additional_event_types(harness) == frozenset(
        {"invite_actor_to_case"}
    )


def test_universal_event_types_match_the_harness_ratchets_copy() -> None:
    """The metadata reader's universal block equals the test ratchet's.

    ``event_types.py`` deliberately does not import
    ``test_universal_event_types._UNIVERSAL_EVENT_TYPES`` — production tooling
    importing a test module is the coupling it exists to avoid — so the two
    spellings are held together here instead of by an import.
    """
    from test.ci.invariants.test_universal_event_types import (
        _UNIVERSAL_EVENT_TYPES,
    )

    assert UNIVERSAL_EVENT_TYPES == _UNIVERSAL_EVENT_TYPES


def test_scenario_set_statement_check_reports_a_stale_enumeration(
    prose_root: Path,
) -> None:
    """A DEMOCI-06 statement that drops a scenario is reported.

    Both statements enumerate scenarios in prose, and until this landed the two
    checks existed only as pytest assertions — so a stale DEMOCI-06-003 passed
    the pre-commit hook and failed later in CI.
    """
    target = prose_root / "specs/demo-ci.yaml"
    target.write_text(
        target.read_text().replace(
            "`fcvcv`, and `fcv-reject`. Together", "`fcvcv`. Together", 1
        ),
        encoding="utf-8",
    )
    problems = scenario_set_statement_problems(prose_root)
    assert any(
        "DEMOCI-06-002 names scenarios" in p for p in problems
    ), problems
