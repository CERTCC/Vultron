"""`readability_audit.py` parses docs prose into sentences without textstat.

Only `score()` needs textstat, which `uvx` supplies at run time; these tests
cover the markup stripping, sentence splitting, scope and path handling.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/readability-audit/readability_audit.py"
)

_spec = importlib.util.spec_from_file_location("readability_audit", SCRIPT)
assert _spec is not None and _spec.loader is not None
ra = importlib.util.module_from_spec(_spec)
sys.modules["readability_audit"] = ra  # dataclasses resolve the module by name
_spec.loader.exec_module(ra)


def _sentences(md: str) -> list[str]:
    return [
        s
        for b in ra.blocks(ra.strip_markup(md))
        for line in ra.units(b)
        for s in ra.sentences_of(line)
    ]


@pytest.mark.parametrize(
    "md",
    [
        "First sentence here (see X.)\nSecond sentence starts here.",
        'He said "go."\nThen we left.',
        "He said “go.”\nThen we left.",
        "A list follows [ref.]\nThen we left.",
    ],
)
def test_stop_before_closer_ends_the_line_sentence(md: str) -> None:
    assert len(_sentences(md)) == 2


@pytest.mark.parametrize(
    "line",
    [
        'He said "go." Then we left.',
        "It ends here (see X.) Then we left.",
    ],
)
def test_stop_before_closer_splits_within_a_line(line: str) -> None:
    assert len(ra.sentences_of(line)) == 2


def test_wrapped_sentence_is_rejoined() -> None:
    assert _sentences("This sentence is\nwrapped mid-way.") == [
        "This sentence is wrapped mid-way."
    ]


def test_literal_dollar_amounts_keep_the_prose_between() -> None:
    md = "It costs $5 per unit.\nThis prose line matters.\nIt costs $10 later."
    assert _sentences(md) == [
        "It costs $5 per unit.",
        "This prose line matters.",
        "It costs $10 later.",
    ]


def test_inline_math_is_stripped_across_lines() -> None:
    md = "Let $x =\n  \\begin{cases} 1 \\end{cases}$ hold.\nNext one."
    assert _sentences(md) == ["Let  hold.", "Next one."]


def test_inline_math_does_not_cross_a_blank_line() -> None:
    md = "Price is $5 here.\n\nAnother $x$ term."
    assert _sentences(md) == ["Price is $5 here.", "Another  term."]


@pytest.mark.parametrize(
    ("md", "expected"),
    [
        ("````markdown\n```python\nx = 1.\n```\n````\nDone.", ["Done."]),
        ("~~~python\nx = 1. y = 2.\n~~~\nDone.", ["Done."]),
        (
            "- Item text.\n\n    ```python\n    x = 1.\n    ```\n\nDone.",
            ["Item text.", "Done."],
        ),
        ('```python\nprint("```")\n```\nDone.', ["Done."]),
    ],
)
def test_fenced_code_is_stripped(md: str, expected: list[str]) -> None:
    assert _sentences(md) == expected


def test_snake_case_identifier_keeps_its_underscore() -> None:
    assert "CASE_MANAGER" in ra.strip_markup("The _CASE_MANAGER_ acts.")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("docs/howto/page.md", True),
        ("docs/adr/0001-x.md", False),
        ("docs/reference/code/x.md", False),
        ("notes/x.md", False),
    ],
)
def test_in_scope_follows_the_style_guide(path: str, expected: bool) -> None:
    assert ra.in_scope(path) is expected


def test_targets_accept_absolute_and_relative_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tmp_path / "docs" / "howto" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("Text.\n")
    expected = [("docs/howto/page.md", page)]
    assert ra.targets([str(page.parent)], tmp_path) == expected
    monkeypatch.chdir(tmp_path / "docs")
    assert ra.targets(["howto"], tmp_path) == expected


def test_targets_refuse_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no such file"):
        ra.targets([str(tmp_path / "missing.md")], tmp_path)


def test_targets_refuse_a_path_outside_the_repo(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(ValueError, match="not inside the repository"):
        ra.targets([str(tmp_path)], root)
