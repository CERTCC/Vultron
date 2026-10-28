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
"""Tests of the ratchet-baseline marker parser behind ARCH-18-003."""

import ast
from pathlib import Path
from textwrap import dedent

import pytest

from vultron.metadata.ratchet_markers import (
    Baseline,
    baselines_in_source,
    is_ratchet_name,
    is_terminal_value,
    scan_paths,
    violations,
)

_PATH = Path("test/example.py")


def _one(source: str) -> Baseline:
    (baseline,) = baselines_in_source(dedent(source), _PATH)
    return baseline


def _problems(source: str) -> list[str]:
    return violations(baselines_in_source(dedent(source), _PATH))


# --- the four cases ARCH-18-003 names ------------------------------------


def test_a_non_empty_baseline_with_no_marker_fails() -> None:
    problems = _problems("""\
        # Known violations.
        KNOWN_VIOLATIONS: frozenset[str] = frozenset({"a.py"})
        """)
    assert len(problems) == 1
    assert "test/example.py:2 KNOWN_VIOLATIONS" in problems[0]
    assert "names no owner" in problems[0]


@pytest.mark.parametrize(
    "marker",
    ["# permanent:", "# permanent:   ", "# permanent: because we said so"],
)
def test_a_permanent_marker_that_cites_nothing_fails(marker: str) -> None:
    problems = _problems(f"{marker}\nKNOWN_ALLOWLIST = frozenset({{'a'}})\n")
    assert len(problems) == 1
    assert "cites no issue" in problems[0]


@pytest.mark.parametrize(
    "value",
    [
        "frozenset()",
        "frozenset({})",
        "set()",
        "[]",
        "()",
        "{}",
        "0",
        "0.0",
        "MappingProxyType({})",
        "types.MappingProxyType({})",
        "sorted([])",
    ],
)
def test_a_terminal_baseline_needs_no_marker(value: str) -> None:
    baseline = _one(f"KNOWN_VIOLATIONS = {value}\n")
    assert baseline.terminal
    assert baseline.violations() == []


@pytest.mark.parametrize(
    "marker",
    [
        "# owner: #1906",
        "# permanent: ADR-0087 (regime exceptions)",
        "# permanent: ARCH-01-006 (the one sanctioned exception)",
        "# permanent: #3933",
    ],
)
def test_a_correctly_marked_baseline_passes(marker: str) -> None:
    source = f"""\
        # ---------------------------------------------------------------
        # Explanation of the baseline.
        # ---------------------------------------------------------------
        {marker}
        KNOWN_VIOLATIONS: frozenset[str] = frozenset(
            {{
                "a.py",
            }}
        )
        """
    assert _problems(source) == []


# --- marker placement and parsing ----------------------------------------


def test_owner_issue_is_parsed_for_the_closed_owner_report() -> None:
    baseline = _one(
        "# owner: #3928\nACTIVITY_TYPE_EXEMPTIONS = frozenset({'X'})\n"
    )
    assert baseline.owners == (3928,)
    assert baseline.permanent == ()


def test_a_trailing_marker_on_the_assignment_line_counts() -> None:
    baseline = _one("MAX_ITEMS = 5  # owner: #12\n")
    assert baseline.owners == (12,)
    assert baseline.violations() == []


def test_a_hash_inside_a_string_is_not_a_trailing_comment() -> None:
    baseline = _one('KNOWN_TAGS = frozenset({"#1"})\n')
    assert baseline.owners == ()
    assert len(baseline.violations()) == 1


def test_a_marker_separated_by_a_blank_line_does_not_count() -> None:
    problems = _problems(
        "# owner: #12\n\nKNOWN_VIOLATIONS = frozenset({'a'})\n"
    )
    assert len(problems) == 1
    assert "names no owner" in problems[0]


def test_an_owner_marker_naming_no_issue_fails_even_on_a_terminal_baseline() -> (
    None
):
    problems = _problems(
        "# owner: none (terminal value)\nKNOWN_X = frozenset()\n"
    )
    assert len(problems) == 1
    assert "names no issue" in problems[0]


def test_both_markers_on_one_baseline_fail() -> None:
    problems = _problems(
        "# owner: #12\n# permanent: ADR-0087\nKNOWN_X = frozenset({'a'})\n"
    )
    assert len(problems) == 1
    assert "both" in problems[0]


def test_a_computed_value_is_treated_as_non_empty() -> None:
    baseline = _one("KNOWN_X = frozenset(_derive())\n")
    assert not baseline.terminal
    assert len(baseline.violations()) == 1


def test_only_module_level_constants_are_baselines() -> None:
    source = dedent("""\
        def f():
            KNOWN_X = {"a"}
        class C:
            KNOWN_Y = {"a"}
        """)
    assert baselines_in_source(source, _PATH) == []


# --- names and values ----------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("KNOWN_VIOLATIONS", True),
        ("_KNOWN_UNDISPATCHABLE", True),
        ("_BASELINE", True),
        ("LINE_BASELINE", True),
        ("MAX_UNCOVERED", True),
        ("__MAX_DEPTH", True),
        ("ACTIVITY_TYPE_EXEMPTIONS", True),
        ("_DECLARED_EXCLUSIONS", False),
        ("UNKNOWN_X", False),
        ("known_violations", False),
        ("KNOWN", False),
        ("BASELINE", False),
    ],
)
def test_ratchet_names(name: str, expected: bool) -> None:
    assert is_ratchet_name(name) is expected


@pytest.mark.parametrize(
    "value",
    ["1", "-1", "True", "False", "''", "frozenset({'a'})", "dict(a=1)", "f()"],
)
def test_non_terminal_values(value: str) -> None:
    assert not is_terminal_value(ast.parse(value, mode="eval").body)


def test_scan_paths_reads_each_file(tmp_path: Path) -> None:
    owned = tmp_path / "owned.py"
    owned.write_text("# owner: #7\nKNOWN_X = {'a'}\n", encoding="utf-8")
    unowned = tmp_path / "unowned.py"
    unowned.write_text("KNOWN_Y = {'a'}\n", encoding="utf-8")
    found = scan_paths([owned, unowned])
    assert [(b.name, b.owners) for b in found] == [
        ("KNOWN_X", (7,)),
        ("KNOWN_Y", ()),
    ]
    assert len(violations(found)) == 1


def test_scan_paths_raises_on_a_file_that_does_not_parse(
    tmp_path: Path,
) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("KNOWN_X = (\n", encoding="utf-8")
    with pytest.raises(SyntaxError):
        scan_paths([broken])
