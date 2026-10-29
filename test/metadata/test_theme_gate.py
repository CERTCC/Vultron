"""Tests for the ``theme-gate`` create-time theme check.

The Python-level tests are pure: the catalog is a fixture and ``gh`` is a fake
runner. The script-level tests run ``manage_github_issue.sh`` and
``create_epic.sh`` against a stand-in ``gh`` on ``PATH`` (``_fake_gh.py``) to
prove each script refuses before it creates anything.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from vultron.metadata.planning.gh import GhError
from vultron.metadata.planning.theme_fit import FindingKind
from vultron.metadata.planning.theme_fit.gate import (
    ParentIssue,
    fetch_parent,
    gate_findings,
    main,
    split_labels,
)
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
            parent=_parent("theme:alpha", "needs-decomposition"),
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
            gate_findings(["theme:alpha"], _ALPHA_BODY, catalog, epic=True)
            == []
        )

    def test_two_themes_with_a_named_split_pass(
        self, catalog: ThemeCatalog
    ) -> None:
        body = (
            "Theme: theme:alpha theme:beta — both halves.\n"
            "Theme split: theme:alpha covers A; theme:beta covers B."
        )
        found = gate_findings(
            ["theme:alpha", "theme:beta"], body, catalog, epic=True
        )
        assert found == []

    def test_two_themes_without_a_split_are_refused(
        self, catalog: ThemeCatalog
    ) -> None:
        body = "Theme: theme:alpha — a.\nTheme: theme:beta — b."
        found = gate_findings(
            ["theme:alpha", "theme:beta"], body, catalog, epic=True
        )
        assert _kinds(found) == [FindingKind.EPIC_THEME_COUNT]

    def test_no_theme_is_refused(self, catalog: ThemeCatalog) -> None:
        found = gate_findings([], _ALPHA_BODY, catalog, epic=True)
        assert _kinds(found) == [FindingKind.EPIC_THEME_COUNT]


def test_split_labels_accepts_comma_lists() -> None:
    assert split_labels(["size:M, theme:alpha", "bug", " "]) == [
        "size:M",
        "theme:alpha",
        "bug",
    ]


class _FakeGh:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        return self.reply


def _view(state: str, *labels: str) -> str:
    return json.dumps(
        {"state": state, "labels": [{"name": label} for label in labels]}
    )


class TestFetchParent:
    def test_reads_state_and_labels(self) -> None:
        fake = _FakeGh(_view("OPEN", "theme:alpha"))
        parent = fetch_parent(7, "o/r", fake)
        assert parent == ParentIssue(7, True, frozenset({"theme:alpha"}))
        assert fake.calls == [
            ["issue", "view", "7", "--repo", "o/r", "--json", "state,labels"]
        ]

    @pytest.mark.parametrize("reply", ["not json", "{}", '{"state": 1}'])
    def test_unreadable_reply_raises(self, reply: str) -> None:
        with pytest.raises(GhError):
            fetch_parent(7, "o/r", _FakeGh(reply))


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
        fake = _FakeGh(_view("OPEN", "theme:alpha"))
        args = self._args(
            note, body, "--label", "theme:alpha", "--parent", "7"
        )
        assert main(args, run=fake) == 0

    def test_refused_issue_exits_1_and_names_the_rule(
        self, note: Path, body: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake = _FakeGh(_view("OPEN", "theme:beta"))
        args = self._args(
            note, body, "--label", "theme:alpha", "--parent", "7"
        )
        assert main(args, run=fake) == 1
        assert "PAD-02-017" in capsys.readouterr().err

    def test_no_parent_makes_no_gh_call(self, note: Path, body: Path) -> None:
        fake = _FakeGh("")
        assert (
            main(self._args(note, body, "--label", "theme:alpha"), fake) == 0
        )
        assert fake.calls == []

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
        assert main(args, run=_FakeGh("")) == 2

    def test_unreadable_body_exits_2(self, note: Path, tmp_path: Path) -> None:
        args = self._args(
            note, tmp_path / "absent.md", "--label", "theme:alpha"
        )
        assert main(args, run=_FakeGh("")) == 2


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


def _parent_rule(*labels: str) -> dict[str, object]:
    return {"match": ["issue view 42"], "stdout": _view("OPEN", *labels)}


def _create_rules() -> list[dict[str, object]]:
    return [
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
        {"match": ["issue edit 99"], "stdout": ""},
    ]


def _manage(
    gh: _Gh, *labels: str, body: str = _BODY
) -> subprocess.CompletedProcess[str]:
    args = [str(_MANAGE), "--title", "T", "--body", body]
    args += ["--issue-type-id", "IT_task", "--parent", "42", "--planned"]
    for label in labels:
        args += ["--label", label]
    return gh.run(*args)


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

    def test_creates_when_the_gate_passes(self, tmp_path: Path) -> None:
        gh = _Gh(tmp_path, [_parent_rule(_THEME), *_create_rules()])
        result = _manage(gh, "size:M", _THEME)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "99"
        assert gh.created()
        edit = next(c for c in gh.calls() if c[:3] == ["issue", "edit", "99"])
        assert edit[-1] == f"size:M,{_THEME}"

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


@pytest.mark.spec("PAD-02-025")
class TestCreateEpicScriptGate:
    def test_requires_a_theme_argument(self, tmp_path: Path) -> None:
        gh = _Gh(tmp_path, [])
        result = gh.run(str(_CREATE_EPIC), "T", _BODY, "Someday")
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
            _BODY,
            "Someday",
            _THEME,
            "theme:test-and-ci",
        )
        assert result.returncode == 1
        assert "PAD-02-015" in result.stderr
        assert gh.calls() == []


# --- the one creation path ---------------------------------------------------

_SKILLS = _ROOT / ".agents/skills"
_CREATORS = {"create-issue", "manage-github-issue", "create-epic"}
_DIRECT_CALLS = ("gh issue create", "createIssue", "create_epic.sh")


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
            if call in path.read_text(encoding="utf-8")
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
