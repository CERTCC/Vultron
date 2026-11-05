"""Tests for the ``theme-gate`` create-time theme check.

The Python-level tests are pure: the catalog is a fixture and ``gh`` is a fake
runner. The script-level tests run ``manage_github_issue.sh`` and
``create_epic.sh`` against a stand-in ``gh`` on ``PATH`` (``_fake_gh.py``) to
prove each script refuses before it creates anything.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from test.metadata._fake_runner import FakeRunner
from test.metadata.specs._helpers import write_yaml
from vultron.metadata.file_loading import MetadataLoadErrors
from vultron.metadata.planning.gh import GhError
from vultron.metadata.planning.theme_fit import (
    FindingKind,
    gate as gate_module,
)
from vultron.metadata.planning.theme_fit.gate import (
    ParentIssue,
    fetch_parent,
    gate_findings,
    main,
    split_labels,
)
from vultron.metadata.planning.theme_fit.spec_topics import load_spec_topics
from vultron.metadata.planning.themes import (
    BEGIN_MARKER,
    END_MARKER,
    ThemeCatalog,
    parse_theme_catalog,
)

_ROOT = Path(__file__).parents[2]
_MANAGE = _ROOT / ".agents/skills/manage-github-issue/manage_github_issue.sh"
_CREATE_EPIC = _ROOT / ".agents/skills/create-epic/create_epic.sh"
_FAKE_GH = Path(__file__).with_name("_fake_gh.py")

_CATALOG_YAML = """\
themes:
  - label: theme:alpha
    outcome: Alpha works
    in_bounds: [alpha things]
    out_of_bounds: [beta things]
    color: 1D76DB
  - label: theme:beta
    outcome: Beta works
    in_bounds: [beta things]
    out_of_bounds: [alpha things]
    color: 1D76DB
  - label: theme:old
    outcome: Old outcome
    in_bounds: [nothing new]
    out_of_bounds: [every new Issue]
    color: 1D76DB
    status: retiring
    replaced_by: [theme:alpha]
"""

_NOTE = (
    f"# Note\n\n{BEGIN_MARKER}\n```yaml\n{_CATALOG_YAML}```\n{END_MARKER}\n"
)

_ALPHA_BODY = "Theme: theme:alpha — makes alpha work.\n\nDetails."
_IDEA = "Design idea: one parser feeds every alpha check."
_ALPHA_EPIC_BODY = f"{_ALPHA_BODY}\n{_IDEA}"
_ALPHA_TITLE = "Alpha checks agree on every input"
_TOPICS = frozenset({"PAD", "SYNC"})


@pytest.fixture
def catalog() -> ThemeCatalog:
    return parse_theme_catalog(_NOTE, "note.md")


def _parent(*labels: str, is_open: bool = True) -> ParentIssue:
    return ParentIssue(number=7, is_open=is_open, labels=frozenset(labels))


def _kinds(found: Sequence[tuple[FindingKind, str]]) -> list[FindingKind]:
    return [kind for kind, _ in found]


class TestLeaf:
    def test_one_theme_reason_line_and_matching_parent_pass(
        self, catalog: ThemeCatalog
    ) -> None:
        found = gate_findings(
            ["size:M", "theme:alpha"],
            _ALPHA_BODY,
            catalog,
            parent=_parent("theme:alpha", "needs-planning"),
        )
        assert found == []

    @pytest.mark.spec("PAD-02-014")
    def test_missing_theme_is_refused(self, catalog: ThemeCatalog) -> None:
        found = gate_findings(["size:M"], _ALPHA_BODY, catalog)
        assert _kinds(found) == [FindingKind.LEAF_THEME_COUNT]

    @pytest.mark.spec("PAD-02-014")
    def test_two_themes_are_refused(self, catalog: ThemeCatalog) -> None:
        body = "Theme: theme:alpha theme:beta — does both."
        found = gate_findings(["theme:alpha", "theme:beta"], body, catalog)
        assert _kinds(found) == [FindingKind.LEAF_THEME_COUNT]

    @pytest.mark.spec("PAD-02-014")
    def test_unlisted_and_retiring_themes_are_refused(
        self, catalog: ThemeCatalog
    ) -> None:
        unknown = gate_findings(
            ["theme:gamma"], "Theme: theme:gamma — x.", catalog
        )
        retiring = gate_findings(
            ["theme:old"], "Theme: theme:old — x.", catalog
        )
        assert _kinds(unknown) == [FindingKind.UNKNOWN_THEME]
        assert _kinds(retiring) == [FindingKind.RETIRING_THEME]

    @pytest.mark.spec("PAD-02-018")
    @pytest.mark.parametrize(
        "body",
        [
            "No reason line at all.",
            "Theme: theme:alpha",
            "Theme: theme:alpha —",
            "Theme: theme:beta — names the wrong label.",
        ],
        ids=["absent", "no-dash", "no-outcome", "other-label"],
    )
    def test_missing_reason_line_is_refused(
        self, catalog: ThemeCatalog, body: str
    ) -> None:
        found = gate_findings(["theme:alpha"], body, catalog)
        assert _kinds(found) == [FindingKind.MISSING_REASON_LINE]

    @pytest.mark.spec("PAD-02-017")
    def test_parent_with_a_different_theme_is_refused(
        self, catalog: ThemeCatalog
    ) -> None:
        found = gate_findings(
            ["theme:alpha"], _ALPHA_BODY, catalog, parent=_parent("theme:beta")
        )
        assert found == [
            (
                FindingKind.THEME_MISMATCH,
                "carries `theme:alpha`; parent #7 carries `theme:beta`",
            )
        ]

    @pytest.mark.spec("PAD-02-017")
    def test_parent_with_no_theme_is_refused(
        self, catalog: ThemeCatalog
    ) -> None:
        found = gate_findings(
            ["theme:alpha"], _ALPHA_BODY, catalog, parent=_parent("size:M")
        )
        assert _kinds(found) == [FindingKind.THEME_MISMATCH]

    def test_parent_carrying_the_theme_among_two_passes(
        self, catalog: ThemeCatalog
    ) -> None:
        found = gate_findings(
            ["theme:alpha"],
            _ALPHA_BODY,
            catalog,
            parent=_parent("theme:beta", "theme:alpha"),
        )
        assert found == []

    @pytest.mark.spec("PAD-01-007")
    def test_closed_parent_is_refused(self, catalog: ThemeCatalog) -> None:
        found = gate_findings(
            ["theme:alpha"],
            _ALPHA_BODY,
            catalog,
            parent=_parent("theme:alpha", is_open=False),
        )
        assert _kinds(found) == [FindingKind.UNPARENTED]

    def test_every_violation_is_reported(self, catalog: ThemeCatalog) -> None:
        found = gate_findings(
            ["theme:old"],
            "no line",
            catalog,
            parent=_parent("theme:beta", is_open=False),
        )
        assert _kinds(found) == [
            FindingKind.RETIRING_THEME,
            FindingKind.MISSING_REASON_LINE,
            FindingKind.UNPARENTED,
            FindingKind.THEME_MISMATCH,
        ]

    def test_label_case_does_not_matter(self, catalog: ThemeCatalog) -> None:
        found = gate_findings(
            ["Theme:Alpha"],
            _ALPHA_BODY,
            catalog,
            parent=_parent("theme:alpha"),
        )
        assert found == []


@pytest.mark.spec("PAD-02-015")
class TestEpic:
    def test_one_theme_passes(self, catalog: ThemeCatalog) -> None:
        assert (
            gate_findings(
                ["theme:alpha"],
                _ALPHA_EPIC_BODY,
                catalog,
                title=_ALPHA_TITLE,
                epic=True,
            )
            == []
        )

    def test_two_themes_with_a_named_split_pass(
        self, catalog: ThemeCatalog
    ) -> None:
        body = (
            "Theme: theme:alpha theme:beta — both halves.\n"
            "Theme split: theme:alpha covers A; theme:beta covers B.\n"
            f"{_IDEA}"
        )
        found = gate_findings(
            ["theme:alpha", "theme:beta"], body, catalog, epic=True
        )
        assert found == []

    def test_two_themes_without_a_split_are_refused(
        self, catalog: ThemeCatalog
    ) -> None:
        body = f"Theme: theme:alpha — a.\nTheme: theme:beta — b.\n{_IDEA}"
        found = gate_findings(
            ["theme:alpha", "theme:beta"], body, catalog, epic=True
        )
        assert _kinds(found) == [FindingKind.EPIC_THEME_COUNT]

    def test_no_theme_is_refused(self, catalog: ThemeCatalog) -> None:
        found = gate_findings([], _ALPHA_EPIC_BODY, catalog, epic=True)
        assert _kinds(found) == [FindingKind.EPIC_THEME_COUNT]


class TestEpicForm:
    """The title and body form checks ``--epic`` adds (PAD-02-030 to 038)."""

    @staticmethod
    def _gate(
        catalog: ThemeCatalog,
        title: str = _ALPHA_TITLE,
        body: str = _ALPHA_EPIC_BODY,
    ) -> list[FindingKind]:
        return _kinds(
            gate_findings(
                ["theme:alpha"],
                body,
                catalog,
                title=title,
                epic=True,
                spec_topics=_TOPICS,
            )
        )

    @pytest.mark.spec("PAD-02-032")
    @pytest.mark.parametrize(
        "title",
        [
            "Alpha checks agree on every input (ADR-0099)",
            "Alpha checks agree, as ADR 12 says",
            "Alpha checks meet PAD-02-030",
            "Messages arrive in any order (SYNC-19)",
            "Alpha checks agree, as adr-0099 says",
            "Alpha checks agree, as ADR\u20130099 says",
            "Alpha checks meet pad-02-030",
            "Messages arrive in any order (sync-19)",
        ],
        ids=[
            "adr-number",
            "adr-spaced",
            "spec-id",
            "group-id",
            "adr-lowercase",
            "adr-en-dash",
            "spec-id-lowercase",
            "group-id-lowercase",
        ],
    )
    def test_an_id_in_the_title_is_refused(
        self, catalog: ThemeCatalog, title: str
    ) -> None:
        assert self._gate(catalog, title=title) == [FindingKind.EPIC_TITLE_ID]

    @pytest.mark.spec("PAD-02-032")
    @pytest.mark.parametrize(
        "title",
        [
            "Vultron cases and CSAF 2.1 documents translate into each other",
            "Peers reject CVE-2024-1234 reports with SHA-256 mismatches",
            "Readers can map Vultron states onto CVSS and AS2",
            "Titles keep UTF-16 text and COVID-19 notes over TLS-13",
        ],
        ids=["version", "cve-and-hash", "acronyms", "not-a-spec-topic"],
    )
    def test_id_shaped_words_that_are_not_ids_pass(
        self, catalog: ThemeCatalog, title: str
    ) -> None:
        assert self._gate(catalog, title=title) == []

    @pytest.mark.spec("PAD-02-030")
    @pytest.mark.parametrize(
        "title", ["Epic: alpha checks", "epic : alpha checks"]
    )
    def test_a_title_starting_with_epic_label_is_refused(
        self, catalog: ThemeCatalog, title: str
    ) -> None:
        assert self._gate(catalog, title=title) == [
            FindingKind.EPIC_TITLE_PREFIX
        ]

    @pytest.mark.spec("PAD-02-030")
    def test_epic_later_in_the_title_passes(
        self, catalog: ThemeCatalog
    ) -> None:
        title = "Every open Epic reads on the board as a claim"
        assert self._gate(catalog, title=title) == []

    @pytest.mark.spec("PAD-02-038")
    @pytest.mark.parametrize(
        "body",
        [
            _ALPHA_BODY,
            f"{_ALPHA_BODY}\nDesign idea:",
            f"{_ALPHA_BODY}\nThe design idea: one parser.",
        ],
        ids=["absent", "empty", "not-at-line-start"],
    )
    def test_no_design_idea_line_is_refused(
        self, catalog: ThemeCatalog, body: str
    ) -> None:
        assert self._gate(catalog, body=body) == [
            FindingKind.MISSING_DESIGN_IDEA
        ]

    @pytest.mark.spec("PAD-02-038")
    def test_an_empty_design_idea_line_is_named_as_empty(
        self, catalog: ThemeCatalog
    ) -> None:
        found = gate_findings(
            ["theme:alpha"],
            f"{_ALPHA_BODY}\nDesign idea:",
            catalog,
            title=_ALPHA_TITLE,
            epic=True,
        )
        assert found == [
            (
                FindingKind.MISSING_DESIGN_IDEA,
                "no `Design idea:` line; the `Design idea:` line has no "
                "approach after the colon",
            )
        ]

    @pytest.mark.spec("PAD-02-038")
    def test_a_fenced_design_idea_line_does_not_count(
        self, catalog: ThemeCatalog
    ) -> None:
        body = f"{_ALPHA_BODY}\n```md\n{_IDEA}\n**Design idea:** x\n```\n"
        found = gate_findings(
            ["theme:alpha"], body, catalog, title=_ALPHA_TITLE, epic=True
        )
        assert found == [
            (FindingKind.MISSING_DESIGN_IDEA, "no `Design idea:` line")
        ]

    @pytest.mark.spec("PAD-02-034")
    @pytest.mark.parametrize(
        "outcome",
        [
            "alpha checks agree on every input",
            "Alpha checks agree on every input, for every reader",
            "alpha checks agree on every",
        ],
        ids=["copy", "copy-with-more", "cut-down"],
    )
    def test_an_outcome_repeating_the_title_is_refused(
        self, catalog: ThemeCatalog, outcome: str
    ) -> None:
        body = f"Theme: theme:alpha — {outcome}\n{_IDEA}"
        assert self._gate(catalog, body=body) == [
            FindingKind.THEME_OUTCOME_REPEATS
        ]

    @pytest.mark.spec("PAD-02-034")
    @pytest.mark.parametrize(
        "idea",
        [
            "Design idea: makes alpha work",
            "Design idea: Makes `alpha` work!",
            f"Design idea: {_ALPHA_TITLE}.",
        ],
        ids=["theme-outcome", "outcome-case-and-punctuation", "title"],
    )
    def test_a_design_idea_repeating_outcome_or_title_is_refused(
        self, catalog: ThemeCatalog, idea: str
    ) -> None:
        body = f"{_ALPHA_BODY}\n{idea}"
        assert self._gate(catalog, body=body) == [
            FindingKind.DESIGN_IDEA_REPEATS
        ]

    @pytest.mark.spec("PAD-02-034")
    def test_a_section_repeating_the_line_is_refused(
        self, catalog: ThemeCatalog
    ) -> None:
        body = (
            f"{_ALPHA_EPIC_BODY}\n\n## Design idea\n\n"
            "One parser feeds\nevery alpha check.\n\n## Children\n- #1"
        )
        assert self._gate(catalog, body=body) == [
            FindingKind.DESIGN_SECTION_REPEATS
        ]

    @pytest.mark.spec("PAD-02-034")
    def test_a_cut_down_copy_of_the_title_is_refused(
        self, catalog: ThemeCatalog
    ) -> None:
        title = "Alpha checks agree on every input from every source"
        body = (
            f"{_ALPHA_BODY}\nDesign idea: alpha checks agree on every input."
        )
        assert self._gate(catalog, title=title, body=body) == [
            FindingKind.DESIGN_IDEA_REPEATS
        ]

    @pytest.mark.spec("PAD-02-034")
    def test_the_line_under_its_own_heading_is_not_a_repeat(
        self, catalog: ThemeCatalog
    ) -> None:
        body = f"{_ALPHA_BODY}\n\n## Design idea\n\n{_IDEA}\n\n## Children\n"
        assert self._gate(catalog, body=body) == []

    @pytest.mark.spec("PAD-02-034")
    def test_a_fenced_comment_does_not_end_the_section(
        self, catalog: ThemeCatalog
    ) -> None:
        body = (
            f"{_ALPHA_EPIC_BODY}\n\n## Design idea\n\n```sh\n# setup\n```\n"
            "One parser feeds every alpha check.\n"
        )
        assert self._gate(catalog, body=body) == [
            FindingKind.DESIGN_SECTION_REPEATS
        ]

    @pytest.mark.spec("PAD-02-034")
    @pytest.mark.parametrize(
        "fence",
        ["~~~\n```\n~~~", "````\n```\n````"],
        ids=["backticks-in-tildes", "short-run-in-long"],
    )
    def test_an_inner_fence_does_not_close_the_outer_one(
        self, catalog: ThemeCatalog, fence: str
    ) -> None:
        body = (
            f"{_ALPHA_EPIC_BODY}\n\n## Design idea\n\n"
            "The parser lives in `alpha/parse.py`.\n"
            f"{fence}\n\n## Children\n\nOne parser feeds every alpha check.\n"
        )
        assert self._gate(catalog, body=body) == []

    @pytest.mark.spec("PAD-02-034")
    def test_a_repeating_section_is_one_finding_for_two_lines(
        self, catalog: ThemeCatalog
    ) -> None:
        body = (
            f"{_ALPHA_EPIC_BODY}\nDesign idea: every alpha check shares it."
            "\n\n## Design idea\n\nOne parser feeds every alpha check, and "
            "every alpha check shares it.\n"
        )
        assert self._gate(catalog, body=body) == [
            FindingKind.DESIGN_SECTION_REPEATS
        ]

    @pytest.mark.spec("PAD-02-038")
    @pytest.mark.parametrize(
        "line",
        [
            "**Design idea:** one parser.",
            "- Design idea: one parser.",
            "design idea: x",
        ],
        ids=["bold", "bulleted", "lowercase"],
    )
    def test_a_near_miss_line_is_named(
        self, catalog: ThemeCatalog, line: str
    ) -> None:
        found = gate_findings(
            ["theme:alpha"],
            f"{_ALPHA_BODY}\n{line}",
            catalog,
            title=_ALPHA_TITLE,
            epic=True,
        )
        assert _kinds(found) == [FindingKind.MISSING_DESIGN_IDEA]
        assert line[:20] in found[0][1]
        assert "start the line with `Design idea:`" in found[0][1]

    @pytest.mark.spec("PAD-02-034")
    def test_a_section_adding_detail_passes(
        self, catalog: ThemeCatalog
    ) -> None:
        body = (
            f"{_ALPHA_EPIC_BODY}\n\n## Design idea\n\n"
            "The parser lives in `alpha/parse.py`; checks import it.\n"
        )
        assert self._gate(catalog, body=body) == []

    def test_every_form_breach_is_reported(
        self, catalog: ThemeCatalog
    ) -> None:
        assert self._gate(
            catalog, title="Epic: alpha (ADR-0001)", body=_ALPHA_BODY
        ) == [
            FindingKind.EPIC_TITLE_ID,
            FindingKind.EPIC_TITLE_PREFIX,
            FindingKind.MISSING_DESIGN_IDEA,
        ]

    def test_a_leaf_gets_no_form_checks(self, catalog: ThemeCatalog) -> None:
        found = gate_findings(
            ["theme:alpha"], _ALPHA_BODY, catalog, title="Epic: ADR-0001"
        )
        assert found == []


def _spec_file(topic: str) -> dict[str, object]:
    """The smallest spec file the registry loads, declaring *topic*."""
    return {
        "id": topic,
        "title": f"{topic} specs",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [
            {
                "id": f"{topic}-01",
                "title": "Group",
                "specs": [
                    {
                        "id": f"{topic}-01-001",
                        "priority": "SHOULD",
                        "kind": "process",
                        "statement": "A thing SHOULD be done.",
                        "rationale": "Because testing.",
                    }
                ],
            }
        ],
    }


class TestLoadSpecTopics:
    def test_reads_each_file_s_top_level_id(self, tmp_path: Path) -> None:
        write_yaml(tmp_path, _spec_file("PAD"), filename="a.yaml")
        write_yaml(tmp_path, _spec_file("SYNC"), filename="b.yaml")
        (tmp_path / "notes.md").write_text("id: NOPE\n")
        assert load_spec_topics(tmp_path) == frozenset({"PAD", "SYNC"})

    def test_no_topics_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_spec_topics(tmp_path)

    def test_an_invalid_spec_file_raises(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text("id: PAD\ntitle: x\n")
        with pytest.raises(MetadataLoadErrors, match=r"a\.yaml"):
            load_spec_topics(tmp_path)

    def test_the_repository_topics_load(self) -> None:
        assert {"PAD", "SYNC"} <= load_spec_topics()


def test_split_labels_accepts_comma_lists() -> None:
    assert split_labels(["size:M, theme:alpha", "bug", " "]) == [
        "size:M",
        "theme:alpha",
        "bug",
    ]


def _view(state: str, *labels: str) -> str:
    return json.dumps(
        {"state": state, "labels": [{"name": label} for label in labels]}
    )


class TestFetchParent:
    def test_reads_state_and_labels(self) -> None:
        fake = FakeRunner(_view("OPEN", "theme:alpha"))
        parent = fetch_parent(7, "o/r", fake)
        assert parent == ParentIssue(7, True, frozenset({"theme:alpha"}))
        assert fake.calls == [
            ["issue", "view", "7", "--repo", "o/r", "--json", "state,labels"]
        ]

    @pytest.mark.parametrize("reply", ["not json", "{}", '{"state": 1}'])
    def test_unreadable_reply_raises(self, reply: str) -> None:
        with pytest.raises(GhError):
            fetch_parent(7, "o/r", FakeRunner(reply))


class TestMain:
    @pytest.fixture
    def note(self, tmp_path: Path) -> Path:
        path = tmp_path / "themes.md"
        path.write_text(_NOTE, encoding="utf-8")
        return path

    @pytest.fixture
    def body(self, tmp_path: Path) -> Path:
        path = tmp_path / "body.md"
        path.write_text(_ALPHA_BODY, encoding="utf-8")
        return path

    def _args(self, note: Path, body: Path, *extra: str) -> list[str]:
        return [
            "--catalog",
            str(note),
            "--body-file",
            str(body),
            "--repo",
            "o/r",
            *extra,
        ]

    def test_passing_issue_exits_0(self, note: Path, body: Path) -> None:
        fake = FakeRunner(_view("OPEN", "theme:alpha"))
        args = self._args(
            note, body, "--label", "theme:alpha", "--parent", "7"
        )
        assert main(args, run=fake) == 0

    def test_refused_issue_exits_1_and_names_the_rule(
        self, note: Path, body: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake = FakeRunner(_view("OPEN", "theme:beta"))
        args = self._args(
            note, body, "--label", "theme:alpha", "--parent", "7"
        )
        assert main(args, run=fake) == 1
        assert "PAD-02-017" in capsys.readouterr().err

    def test_no_parent_makes_no_gh_call(self, note: Path, body: Path) -> None:
        fake = FakeRunner("")
        assert (
            main(self._args(note, body, "--label", "theme:alpha"), fake) == 0
        )
        assert fake.calls == []

    def test_an_unloadable_spec_corpus_exits_2(
        self,
        note: Path,
        body: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def broken() -> frozenset[str]:
            raise MetadataLoadErrors([], summary="1 spec file(s) failed")

        monkeypatch.setattr(gate_module, "load_spec_topics", broken)
        args = self._args(
            note, body, "--epic", "--title", _ALPHA_TITLE, "--label", "x"
        )
        assert main(args, run=FakeRunner("")) == 2
        assert "spec file(s) failed" in capsys.readouterr().err

    def test_gh_failure_exits_2(self, note: Path, body: Path) -> None:
        def failing(args: Sequence[str]) -> str:
            raise subprocess.CalledProcessError(1, ["gh"], stderr="boom")

        args = self._args(
            note, body, "--label", "theme:alpha", "--parent", "7"
        )
        assert main(args, run=failing) == 2

    def test_missing_catalog_exits_2(self, tmp_path: Path, body: Path) -> None:
        args = self._args(
            tmp_path / "absent.md", body, "--label", "theme:alpha"
        )
        assert main(args, run=FakeRunner("")) == 2

    def test_unreadable_body_exits_2(self, note: Path, tmp_path: Path) -> None:
        args = self._args(
            note, tmp_path / "absent.md", "--label", "theme:alpha"
        )
        assert main(args, run=FakeRunner("")) == 2

    @pytest.mark.parametrize(
        "title", [None, "", "  "], ids=["absent", "empty", "blank"]
    )
    def test_epic_without_a_title_exits_2(
        self, note: Path, body: Path, title: str | None
    ) -> None:
        args = self._args(note, body, "--label", "theme:alpha", "--epic")
        if title is not None:
            args += ["--title", title]
        with pytest.raises(SystemExit) as exc:
            main(args, run=FakeRunner(""))
        assert exc.value.code == 2

    @pytest.mark.spec("PAD-02-032")
    def test_epic_title_group_id_uses_the_repository_topics(
        self, note: Path, tmp_path: Path
    ) -> None:
        body = tmp_path / "epic.md"
        body.write_text(_ALPHA_EPIC_BODY, encoding="utf-8")
        args = self._args(note, body, "--label", "theme:alpha", "--epic")
        assert main([*args, "--title", "Alpha (SYNC-19)"], FakeRunner("")) == 1
        assert main([*args, "--title", "Alpha (UTF-16)"], FakeRunner("")) == 0

    @pytest.mark.spec("PAD-02-032")
    def test_epic_title_is_checked(
        self,
        note: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        body = tmp_path / "epic.md"
        body.write_text(_ALPHA_EPIC_BODY, encoding="utf-8")
        base = self._args(note, body, "--label", "theme:alpha", "--epic")
        assert main([*base, "--title", _ALPHA_TITLE], run=FakeRunner("")) == 0
        assert (
            main([*base, "--title", "Alpha (ADR-0001)"], FakeRunner("")) == 1
        )
        assert "PAD-02-032" in capsys.readouterr().err


# --- the scripts that call the gate ----------------------------------------


class _Gh:
    """A stand-in ``gh`` on ``PATH`` that answers from canned rules."""

    def __init__(self, tmp_path: Path, rules: list[dict[str, object]]) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(f'#!/bin/sh\nexec python3 "{_FAKE_GH}" "$@"\n')
        gh.chmod(0o755)
        self.log = tmp_path / "gh.log"
        self.log.touch()
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps(rules), encoding="utf-8")
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_GH_LOG": str(self.log),
            "FAKE_GH_RULES": str(rules_file),
        }

    def run(self, *argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            check=False,
            env=self.env,
            timeout=120,
        )

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def created(self) -> bool:
        return any("createIssue" in " ".join(call) for call in self.calls())


_THEME = "theme:dev-workflow"
_BODY = f"Theme: {_THEME} — tests the gate.\n\nBody."
_EPIC_BODY = f"{_BODY}\nDesign idea: a stand-in gh answers every call."


def _parent_rule(*labels: str) -> dict[str, object]:
    return {"match": ["issue view 42"], "stdout": _view("OPEN", *labels)}


def _label_rule(name: str, label_id: str | None) -> dict[str, object]:
    label = {"id": label_id} if label_id else None
    return {
        "match": [f'label(name: "{name}")'],
        "stdout": json.dumps({"data": {"repository": {"label": label}}}),
    }


def _create_rules() -> list[dict[str, object]]:
    return [
        _label_rule("size:M", "L_size"),
        _label_rule(_THEME, "L_theme"),
        {
            "match": ["createIssue"],
            "stdout": json.dumps(
                {
                    "data": {
                        "createIssue": {
                            "issue": {"number": 99, "id": "I_99", "url": "u"}
                        }
                    }
                }
            ),
        },
        {
            "match": ["issue(number: 42) { id }"],
            "stdout": json.dumps(
                {"data": {"repository": {"issue": {"id": "I_42"}}}}
            ),
        },
        {
            "match": ["{ id } }"],
            "stdout": json.dumps({"data": {"repository": {"id": "R_1"}}}),
        },
    ]


def _manage(
    gh: _Gh, *labels: str, body: str = _BODY, extra: Sequence[str] = ()
) -> subprocess.CompletedProcess[str]:
    args = [str(_MANAGE), "--title", "T", "--body", body]
    args += ["--issue-type-id", "IT_task", "--parent", "42", "--planned"]
    for label in labels:
        args += ["--label", label]
    return gh.run(*args, *extra)


@pytest.mark.spec("PAD-02-023")
class TestManageScriptGate:
    @pytest.mark.spec("PAD-02-014")
    @pytest.mark.parametrize(
        "labels",
        [("size:M",), (_THEME, "theme:test-and-ci")],
        ids=["missing", "multiple"],
    )
    def test_refuses_wrong_theme_count(
        self, tmp_path: Path, labels: tuple[str, ...]
    ) -> None:
        gh = _Gh(tmp_path, [_parent_rule(_THEME)])
        result = _manage(gh, *labels)
        assert result.returncode == 1
        assert "PAD-02-014" in result.stderr
        assert not gh.created()

    @pytest.mark.spec("PAD-02-018")
    def test_refuses_missing_theme_line(self, tmp_path: Path) -> None:
        gh = _Gh(tmp_path, [_parent_rule(_THEME)])
        result = _manage(gh, _THEME, body="No reason line.")
        assert result.returncode == 1
        assert "PAD-02-018" in result.stderr
        assert not gh.created()

    @pytest.mark.spec("PAD-02-017")
    def test_refuses_parent_with_a_different_theme(
        self, tmp_path: Path
    ) -> None:
        gh = _Gh(tmp_path, [_parent_rule("theme:test-and-ci")])
        result = _manage(gh, _THEME)
        assert result.returncode == 1
        assert "PAD-02-017" in result.stderr
        assert not gh.created()

    def test_creates_with_its_labels_when_the_gate_passes(
        self, tmp_path: Path
    ) -> None:
        gh = _Gh(tmp_path, [_parent_rule(_THEME), *_create_rules()])
        result = _manage(gh, "size:M", _THEME)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "99"
        create = next(c for c in gh.calls() if "createIssue" in " ".join(c))
        assert 'labelIds: ["L_size","L_theme"]' in " ".join(create)
        # The labels ride on createIssue: no separate edit can fail after it.
        assert not any(c[:2] == ["issue", "edit"] for c in gh.calls())

    def test_missing_label_stops_before_create(self, tmp_path: Path) -> None:
        gh = _Gh(
            tmp_path,
            [
                _parent_rule(_THEME),
                _label_rule("size:Q", None),
                *_create_rules(),
            ],
        )
        result = _manage(gh, "size:Q", _THEME)
        assert result.returncode == 1
        assert "does not exist" in result.stderr
        assert not gh.created()

    def test_a_failure_after_create_says_not_to_create_again(
        self, tmp_path: Path
    ) -> None:
        # The milestone PATCH has no rule, so the fake gh fails it.
        gh = _Gh(tmp_path, [_parent_rule(_THEME), *_create_rules()])
        result = _manage(gh, "size:M", _THEME, extra=("--milestone", "3"))
        assert result.returncode != 0
        assert "#99 was created" in result.stderr
        assert "--issue-number 99" in result.stderr

    def test_a_refusal_gives_no_partial_create_warning(
        self, tmp_path: Path
    ) -> None:
        gh = _Gh(tmp_path, [_parent_rule("theme:test-and-ci")])
        result = _manage(gh, _THEME)
        assert result.returncode == 1
        assert "Do not create it again" not in result.stderr

    def test_update_mode_skips_the_gate(self, tmp_path: Path) -> None:
        gh = _Gh(
            tmp_path,
            [
                {
                    "match": ["issue(number: 5) { id }"],
                    "stdout": json.dumps(
                        {"data": {"repository": {"issue": {"id": "I_5"}}}}
                    ),
                },
                {"match": ["issue edit 5"], "stdout": ""},
            ],
        )
        result = gh.run(str(_MANAGE), "--issue-number", "5", "--label", "x")
        assert result.returncode == 0, result.stderr
        assert not any(c[:2] == ["issue", "view"] for c in gh.calls())


_EPIC_CREATED: dict[str, object] = {
    "match": ["createIssue"],
    "stdout": json.dumps(
        {"data": {"createIssue": {"issue": {"number": 77, "url": "u"}}}}
    ),
}


class _EpicTree:
    """A copy of the create-epic skill tree with stub board helpers.

    The run touches neither the real board-id cache nor the board.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        skills = tmp_path / "tree/.agents/skills"
        (skills / "create-epic").mkdir(parents=True)
        (skills / "shared").mkdir()
        self.script = skills / "create-epic/create_epic.sh"
        self.script.write_text(_CREATE_EPIC.read_text())
        self.script.chmod(0o755)
        (skills / "shared/label-id.sh").write_text(
            (_ROOT / ".agents/skills/shared/label-id.sh").read_text()
        )
        (skills / "shared/board-id.sh").write_text('echo "ID_$1_${2:-}"\n')
        self.board_log = tmp_path / "board.log"
        self.add_to_project = skills / "shared/add-to-project.sh"
        self.add_to_project.write_text(f'echo "$@" >> "{self.board_log}"\n')

    def gh(self, *rules: dict[str, object]) -> _Gh:
        gh = _Gh(self.tmp_path, list(rules))
        # The copy lives outside the checkout, so point it at the real one.
        gh.env["VULTRON_PROJECT_DIR"] = str(_ROOT)
        return gh


@pytest.fixture
def epic_tree(tmp_path: Path) -> _EpicTree:
    return _EpicTree(tmp_path)


@pytest.mark.spec("PAD-02-025")
class TestCreateEpicScriptGate:
    def test_requires_a_theme_argument(self, tmp_path: Path) -> None:
        gh = _Gh(tmp_path, [])
        result = gh.run(str(_CREATE_EPIC), "T", _EPIC_BODY, "Someday")
        assert result.returncode != 0
        assert "Usage" in result.stderr
        assert gh.calls() == []

    @pytest.mark.spec("PAD-02-018")
    def test_refuses_missing_theme_line(self, tmp_path: Path) -> None:
        gh = _Gh(tmp_path, [])
        result = gh.run(str(_CREATE_EPIC), "T", "No line.", "Someday", _THEME)
        assert result.returncode == 1
        assert "PAD-02-018" in result.stderr
        assert gh.calls() == []

    @pytest.mark.spec("PAD-02-015")
    def test_refuses_two_themes_without_a_split(self, tmp_path: Path) -> None:
        gh = _Gh(tmp_path, [])
        result = gh.run(
            str(_CREATE_EPIC),
            "T",
            _EPIC_BODY,
            "Someday",
            _THEME,
            "theme:test-and-ci",
        )
        assert result.returncode == 1
        assert "PAD-02-015" in result.stderr
        assert gh.calls() == []

    @pytest.mark.parametrize("theme", [f"{_THEME},theme:test-and-ci", "x,"])
    def test_refuses_a_comma_joined_theme(
        self, tmp_path: Path, theme: str
    ) -> None:
        gh = _Gh(tmp_path, [])
        result = gh.run(str(_CREATE_EPIC), "T", _EPIC_BODY, "Someday", theme)
        assert result.returncode == 1
        assert "one theme per argument" in result.stderr
        assert gh.calls() == []

    @pytest.mark.spec("PAD-02-032")
    def test_refuses_an_id_in_the_title(self, tmp_path: Path) -> None:
        gh = _Gh(tmp_path, [])
        result = gh.run(
            str(_CREATE_EPIC), "T (ADR-0001)", _EPIC_BODY, "Someday", _THEME
        )
        assert result.returncode == 1
        assert "PAD-02-032" in result.stderr
        assert gh.calls() == []

    @pytest.mark.spec("PAD-02-038")
    def test_refuses_a_missing_design_idea(self, tmp_path: Path) -> None:
        gh = _Gh(tmp_path, [])
        result = gh.run(str(_CREATE_EPIC), "T", _BODY, "Someday", _THEME)
        assert result.returncode == 1
        assert "PAD-02-038" in result.stderr
        assert gh.calls() == []

    def test_creates_labelled_and_scheduled_when_the_gate_passes(
        self, epic_tree: _EpicTree
    ) -> None:
        gh = epic_tree.gh(_label_rule(_THEME, "L_theme"), _EPIC_CREATED)
        result = gh.run(
            str(epic_tree.script), "T", _EPIC_BODY, "Later", _THEME
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "77"
        create = next(c for c in gh.calls() if "createIssue" in " ".join(c))
        joined = " ".join(create)
        assert 'labelIds: ["L_theme"]' in joined
        assert "ID_issue-type_Epic" in joined
        assert epic_tree.board_log.read_text().split() == ["77", "Later"]

    def test_missing_label_stops_before_create(
        self, epic_tree: _EpicTree
    ) -> None:
        gh = epic_tree.gh(_label_rule(_THEME, None), _EPIC_CREATED)
        result = gh.run(
            str(epic_tree.script), "T", _EPIC_BODY, "Later", _THEME
        )
        assert result.returncode == 1
        assert "does not exist" in result.stderr
        assert not gh.created()
        assert not epic_tree.board_log.exists()

    def test_a_failed_board_add_says_not_to_create_again(
        self, epic_tree: _EpicTree
    ) -> None:
        epic_tree.add_to_project.write_text("exit 3\n")
        gh = epic_tree.gh(_label_rule(_THEME, "L_theme"), _EPIC_CREATED)
        result = gh.run(
            str(epic_tree.script), "T", _EPIC_BODY, "Later", _THEME
        )
        assert result.returncode == 3
        assert "Epic #77 was created" in result.stderr
        assert "do not create it again" in result.stderr
        assert result.stdout.strip() == ""


# --- the one creation path ---------------------------------------------------

_SKILLS = _ROOT / ".agents/skills"
_CREATORS = {"create-issue", "manage-github-issue", "create-epic"}
_REST_CREATE = re.compile(
    r"\bgh\s+api\b(?=[^\n]*/issues(?![/\w]))(?=[^\n]*(?:-X\s*|--method[\s=]+)POST)",
    re.IGNORECASE,
)
_DIRECT_CALLS = (
    re.compile(r"\bgh\b[^\n`]*?\bissue\s+create\b"),
    re.compile(r"\bcreateIssue\b"),
    re.compile(r"\bcreate_epic\.sh\b"),
    _REST_CREATE,
)
_FILING_PROSE = re.compile(
    r"\b(?:create|file|open)s?\s+an?\s+(?:new\s+)?(?:gh\s+|github\s+)?"
    r"`?(?:type:)?(?:bug|task|feature|idea|concern)?`?\s*issue\b",
    re.IGNORECASE,
)


def _skill_files() -> list[Path]:
    return sorted(
        path
        for path in _SKILLS.rglob("*")
        if path.is_file()
        and path.suffix in {".md", ".sh", ".py"}
        and path.relative_to(_SKILLS).parts[0] not in _CREATORS
    )


def _commands(text: str, needle: str) -> list[str]:
    """Each shell command in *text* that names *needle*, continuations joined."""
    lines = text.splitlines()
    found: list[str] = []
    for i, line in enumerate(lines):
        if needle not in line:
            continue
        command = [line]
        j = i
        while lines[j].rstrip().endswith("\\") and j + 1 < len(lines):
            j += 1
            command.append(lines[j])
        found.append("\n".join(command))
    return found


@pytest.mark.spec("PAD-02-022")
class TestCreationPath:
    def test_the_scan_sees_skill_files(self) -> None:
        names = {p.relative_to(_SKILLS).parts[0] for p in _skill_files()}
        assert {"build", "bugfix", "plan-issue", "update-plan"} <= names
        assert not names & _CREATORS

    def test_no_skill_calls_a_creation_api_directly(self) -> None:
        offenders = [
            f"{path.relative_to(_ROOT)}: {call}"
            for path in _skill_files()
            for call in _DIRECT_CALLS
            if call.search(path.read_text(encoding="utf-8"))
        ]
        assert offenders == []

    def test_no_skill_runs_the_create_mode_of_the_manage_script(self) -> None:
        offenders = [
            f"{path.relative_to(_ROOT)}: {command.splitlines()[0].strip()}"
            for path in _skill_files()
            for command in _commands(
                path.read_text(encoding="utf-8"), "manage_github_issue.sh"
            )
            if "--title" in command and "--issue-number" not in command
        ]
        assert offenders == []

    def test_a_skill_that_files_issues_names_create_issue(self) -> None:
        # Prose such as "file a Bug issue" must say how: a skill that tells
        # the agent to create an issue and never names `create-issue` leaves
        # it to improvise the type, theme, and parent.
        offenders = [
            str(path.relative_to(_ROOT))
            for path in _skill_files()
            if _FILING_PROSE.search(text := path.read_text(encoding="utf-8"))
            and "create-issue" not in text
        ]
        assert offenders == []

    def test_the_detector_catches_a_create_call(self) -> None:
        text = (
            "N=$(.agents/skills/manage-github-issue/manage_github_issue.sh \\\n"
            '  --title "x" \\\n'
            "  --planned)\n"
            "manage_github_issue.sh --issue-number 5 --title y\n"
        )
        commands = _commands(text, "manage_github_issue.sh")
        assert len(commands) == 2
        assert "--title" in commands[0] and "--planned" in commands[0]
        assert "--issue-number" in commands[1]

    @pytest.mark.parametrize(
        "text",
        [
            "gh issue create --title x",
            "gh -R CERTCC/Vultron issue  create --title x",
            "gh api repos/CERTCC/Vultron/issues -X POST -f title=x",
            "gh api --method POST repos/o/r/issues -f title=x",
            "mutation { createIssue(input: {}) }",
            "bash create_epic.sh T B Someday theme:x",
        ],
    )
    def test_the_direct_call_patterns_catch(self, text: str) -> None:
        assert any(call.search(text) for call in _DIRECT_CALLS)

    @pytest.mark.parametrize(
        "text",
        [
            "gh issue view 5 --json state",
            "gh api repos/o/r/issues/5/comments -X POST -f body=x",
            "gh api repos/o/r/issues/5 -X PATCH -f milestone=3",
        ],
    )
    def test_the_direct_call_patterns_pass(self, text: str) -> None:
        assert not any(call.search(text) for call in _DIRECT_CALLS)


_CREATE_ISSUE_SKILL = _SKILLS / "create-issue/SKILL.md"


@pytest.mark.spec("PAD-02-024")
class TestUnattendedAutoCalve:
    """`create-issue`'s no-user branch calves rather than orphans.

    The skill is prose an agent follows, so the check pins what that branch
    tells the agent to do: calve through `create-epic`, at `Someday`, marked
    `<!-- auto-calved -->`, and parent the issue on it.
    """

    @staticmethod
    def _branch() -> str:
        text = _CREATE_ISSUE_SKILL.read_text(encoding="utf-8")
        match = re.search(
            r"\*\*No user present\*\*:(.*?)(?=\n\S|\n\s*\n\S)", text, re.S
        )
        assert match, "create-issue has no 'No user present' branch"
        return match.group(1)

    @pytest.mark.parametrize(
        "phrase", ["`create-epic`", "Someday Epic", "`<!-- auto-calved -->`"]
    )
    def test_the_branch_names(self, phrase: str) -> None:
        assert phrase in " ".join(self._branch().split())

    def test_the_skill_never_leaves_an_orphan(self) -> None:
        text = _CREATE_ISSUE_SKILL.read_text(encoding="utf-8")
        assert "Never create the issue without a parent" in text


def test_the_gate_runs_as_a_module_without_a_double_import() -> None:
    """``create_epic.sh`` runs the gate with ``python -m``.

    If the package imported the gate, ``runpy`` would warn that the module was
    already loaded, on every Issue and Epic created.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error::RuntimeWarning",
            "-m",
            "vultron.metadata.planning.theme_fit.gate",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "RuntimeWarning" not in result.stderr
