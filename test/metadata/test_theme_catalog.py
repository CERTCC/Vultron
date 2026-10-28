"""Tests for the theme catalog loader and the ``theme-labels`` sync.

Pure: no network. The ``gh`` calls go through a fake runner that records each
argument list and answers ``label list`` with a canned payload.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.planning import theme_labels
from vultron.metadata.planning.theme_labels import (
    RemoteLabel,
    compute_drift,
    fetch_labels,
    format_drift,
    main,
)
from vultron.metadata.planning.themes import (
    BEGIN_MARKER,
    END_MARKER,
    ThemeCatalog,
    ThemeStatus,
    load_theme_catalog,
    parse_theme_catalog,
)

_ENTRY_A = """\
  - label: theme:alpha
    outcome: >-
      Alpha works
    in_bounds:
      - alpha things
    out_of_bounds:
      - beta things (beta)
    color: 1d76db
"""

_ENTRY_B = """\
  - label: theme:beta
    outcome: >-
      Beta works
    in_bounds:
      - beta things
    out_of_bounds:
      - alpha things (alpha)
    color: 5319E7
"""

_ENTRY_OLD = """\
  - label: theme:old
    outcome: >-
      Old outcome
    in_bounds:
      - nothing new
    out_of_bounds:
      - every new Issue
    color: 1D76DB
    status: retiring
    replaced_by:
      - theme:alpha
      - theme:beta
"""


def _note(*entries: str, preamble: str = "# Note\n\nProse.\n\n") -> str:
    body = "themes:\n" + "".join(entries)
    return f"{preamble}{BEGIN_MARKER}\n```yaml\n{body}```\n{END_MARKER}\n\nMore.\n"


def _catalog(*entries: str) -> ThemeCatalog:
    return parse_theme_catalog(_note(*entries), "note.md")


@pytest.mark.spec("PAD-02-019")
class TestRepositoryCatalog:
    """The committed note parses and holds the theme set epic #5321 decided."""

    def test_loads(self) -> None:
        catalog = load_theme_catalog()
        assert catalog.themes

    @pytest.mark.parametrize(
        "label",
        [
            "theme:dev-workflow",
            "theme:test-and-ci",
            "theme:multi-case-operations",
            "theme:capability-architecture",
            "theme:verifiable-conformance",
        ],
    )
    def test_active_theme_present(self, label: str) -> None:
        theme = load_theme_catalog().get(label)
        assert theme.status is ThemeStatus.ACTIVE

    def test_project_health_is_retiring_into_its_split(self) -> None:
        theme = load_theme_catalog().get("theme:project-health")
        assert theme.status is ThemeStatus.RETIRING
        assert set(theme.replaced_by) == {
            "theme:dev-workflow",
            "theme:test-and-ci",
        }


class TestParse:
    def test_fields(self) -> None:
        catalog = _catalog(_ENTRY_A, _ENTRY_B, _ENTRY_OLD)
        alpha = catalog.get("theme:alpha")
        assert alpha.outcome == "Alpha works"
        assert alpha.color == "1D76DB"  # held in upper case
        assert alpha.description == "Alpha works"
        assert catalog.labels() == {"theme:alpha", "theme:beta", "theme:old"}
        assert [t.label for t in catalog.active()] == [
            "theme:alpha",
            "theme:beta",
        ]

    def test_retiring_description_names_replacements(self) -> None:
        old = _catalog(_ENTRY_A, _ENTRY_B, _ENTRY_OLD).get("theme:old")
        assert old.description == "Retiring: use theme:alpha or theme:beta"

    def test_get_unknown_raises(self) -> None:
        with pytest.raises(KeyError):
            _catalog(_ENTRY_A).get("theme:nope")


class TestMarkers:
    @pytest.mark.parametrize("marker", [BEGIN_MARKER, END_MARKER])
    def test_missing_marker(self, marker: str) -> None:
        text = _note(_ENTRY_A).replace(marker, "")
        with pytest.raises(MetadataLoadError, match="exactly one"):
            parse_theme_catalog(text, "note.md")

    def test_doubled_marker(self) -> None:
        text = _note(_ENTRY_A) + f"\n{BEGIN_MARKER}\n"
        with pytest.raises(MetadataLoadError, match="found 2"):
            parse_theme_catalog(text, "note.md")

    def test_inverted_markers(self) -> None:
        text = f"{END_MARKER}\n```yaml\nthemes: []\n```\n{BEGIN_MARKER}\n"
        with pytest.raises(MetadataLoadError, match="precedes"):
            parse_theme_catalog(text, "note.md")

    @pytest.mark.parametrize(
        "inner",
        [
            "themes: []\n",  # no fence
            "```text\nthemes: []\n```\n",  # wrong info string
            "Prose.\n```yaml\nthemes: []\n```\n",  # extra content
            "```yaml\nthemes: []\n```\n```yaml\nx: 1\n```\n",  # two fences
        ],
    )
    def test_not_one_yaml_fence(self, inner: str) -> None:
        text = f"{BEGIN_MARKER}\n{inner}{END_MARKER}\n"
        with pytest.raises(MetadataLoadError, match="exactly one"):
            parse_theme_catalog(text, "note.md")


class TestFaultLocation:
    def test_yaml_fault_reads_at_note_line(self) -> None:
        text = _note(_ENTRY_A + "  - label: [unclosed\n")
        with pytest.raises(MetadataLoadError) as info:
            parse_theme_catalog(text, "note.md")
        bad = text.splitlines().index("  - label: [unclosed") + 1
        assert info.value.path == "note.md"
        assert info.value.line is not None
        assert bad <= info.value.line <= bad + 2

    def test_schema_fault_reads_at_note_line(self) -> None:
        text = _note(_ENTRY_A.replace("color: 1d76db", "color: blue"))
        with pytest.raises(MetadataLoadError) as info:
            parse_theme_catalog(text, "note.md")
        assert (
            info.value.line == text.splitlines().index("    color: blue") + 1
        )


class TestValidation:
    @pytest.mark.parametrize(
        ("entries", "fault"),
        [
            ((_ENTRY_A, _ENTRY_A), "listed twice"),
            ((_ENTRY_A, _ENTRY_OLD), "theme:beta, which is not an active"),
            (
                (
                    _ENTRY_A,
                    _ENTRY_B,
                    _ENTRY_OLD.replace("theme:alpha\n", "theme:old\n"),
                ),
                "theme:old, which is not an active",
            ),
            (
                (_ENTRY_OLD.split("    replaced_by:", maxsplit=1)[0],),
                "must list `replaced_by`",
            ),
            (
                (
                    _ENTRY_A + "    replaced_by:\n      - theme:beta\n",
                    _ENTRY_B,
                ),
                "only a retiring theme",
            ),
            ((_ENTRY_A.replace("theme:alpha", "alpha"),), "label"),
            ((_ENTRY_A.replace("theme:alpha", "theme:Alpha"),), "label"),
            ((_ENTRY_A.replace("1d76db", "#1d76db"),), "color"),
            (
                (
                    _ENTRY_A.replace(
                        "    in_bounds:\n      - alpha things\n",
                        "    in_bounds: []\n",
                    ),
                ),
                "in_bounds",
            ),
            ((_ENTRY_A.replace("color:", "colour:"),), "colour"),
            (
                (_ENTRY_A.replace("Alpha works", "x" * 101),),
                "GitHub allows 100",
            ),
            (
                (
                    _ENTRY_A.replace(
                        ">-\n      Alpha works", "|\n      Alpha\n      works"
                    ),
                ),
                "one line",
            ),
        ],
    )
    def test_rejected(self, entries: tuple[str, ...], fault: str) -> None:
        with pytest.raises(
            MetadataLoadError, match="invalid theme catalog"
        ) as info:
            _catalog(*entries)
        assert fault in str(info.value)

    def test_empty_catalog_rejected(self) -> None:
        text = f"{BEGIN_MARKER}\n```yaml\nthemes: []\n```\n{END_MARKER}\n"
        with pytest.raises(MetadataLoadError, match="themes"):
            parse_theme_catalog(text, "note.md")


def _remote(name: str, description: str, color: str) -> RemoteLabel:
    return RemoteLabel(name=name, description=description, color=color)


@pytest.mark.spec("PAD-02-021")
class TestDrift:
    catalog = _catalog(_ENTRY_A, _ENTRY_B, _ENTRY_OLD)

    def test_in_sync(self) -> None:
        remote = [
            _remote(
                "theme:alpha", "Alpha works", "1d76db"
            ),  # case-insensitive
            _remote("theme:beta", "Beta works", "5319E7"),
            _remote(
                "theme:old",
                "Retiring: use theme:alpha or theme:beta",
                "1D76DB",
            ),
            _remote("size:S", "anything", "000000"),  # not a theme: ignored
        ]
        drift = compute_drift(self.catalog, remote)
        assert drift.in_sync
        assert format_drift(drift) == "theme labels match the catalog."

    def test_missing_changed_unlisted(self) -> None:
        remote = [
            _remote("theme:alpha", "Stale words", "1D76DB"),
            _remote("theme:old", "Old outcome", "FFFFFF"),
            _remote("theme:zeta", "Nobody listed me", "1D76DB"),
        ]
        drift = compute_drift(self.catalog, remote)
        assert [t.label for t in drift.missing] == ["theme:beta"]
        assert {c.theme.label: c.fields() for c in drift.changed} == {
            "theme:alpha": ("description",),
            "theme:old": ("description", "color"),
        }
        assert [r.name for r in drift.unlisted] == ["theme:zeta"]
        assert not drift.in_sync
        report = format_drift(drift)
        assert "missing   theme:beta" in report
        assert "'Stale words' -> 'Alpha works'" in report
        assert "unlisted  theme:zeta" in report
        assert drift.to_json() == {
            "missing": ["theme:beta"],
            "changed": [
                {"label": "theme:alpha", "fields": ["description"]},
                {"label": "theme:old", "fields": ["description", "color"]},
            ],
            "unlisted": ["theme:zeta"],
            "in_sync": False,
        }

    def test_name_differing_only_in_case_is_a_change(self) -> None:
        remote = [
            _remote("Theme:Alpha", "Alpha works", "1D76DB"),
            _remote("theme:beta", "Beta works", "5319E7"),
            _remote(
                "theme:old",
                "Retiring: use theme:alpha or theme:beta",
                "1D76DB",
            ),
        ]
        drift = compute_drift(self.catalog, remote)
        assert drift.missing == ()
        assert drift.unlisted == ()
        assert [c.fields() for c in drift.changed] == [("name",)]


class TestFetch:
    def test_null_description_and_color_read_as_empty(self) -> None:
        labels = fetch_labels(
            "o/r",
            run=lambda _: json.dumps(
                [{"name": "theme:a", "description": None, "color": None}]
            ),
        )
        assert labels == (RemoteLabel("theme:a", "", ""),)

    @pytest.mark.parametrize("raw", ["not json", "[{}]", "{}", "[1]"])
    def test_unreadable_listing_raises(self, raw: str) -> None:
        with pytest.raises(theme_labels.LabelSyncError):
            fetch_labels("o/r", run=lambda _: raw)

    def test_gh_not_installed_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def missing(*_: object, **__: object) -> None:
            raise FileNotFoundError("gh")

        monkeypatch.setattr(theme_labels.subprocess, "run", missing)
        with pytest.raises(theme_labels.LabelSyncError, match="not installed"):
            fetch_labels("o/r")


class _FakeGh:
    """Records ``gh`` calls; answers ``label list`` with *labels*."""

    def __init__(
        self, labels: list[dict[str, str]], fail: bool = False
    ) -> None:
        self.labels = labels
        self.fail = fail
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        if self.fail:
            raise subprocess.CalledProcessError(1, ["gh"], stderr="boom")
        if list(args[:2]) == ["label", "list"]:
            return json.dumps(self.labels)
        return ""

    def verbs(self) -> list[tuple[str, str]]:
        return [(c[1], c[2]) for c in self.calls if c[1] != "list"]


@pytest.fixture
def note(tmp_path: Path) -> Path:
    path = tmp_path / "epic-themes.md"
    path.write_text(_note(_ENTRY_A, _ENTRY_B), encoding="utf-8")
    return path


_DRIFTED = [
    {"name": "theme:alpha", "description": "Stale", "color": "1d76db"},
    {"name": "theme:zeta", "description": "Unlisted", "color": "1d76db"},
]


@pytest.mark.spec("PAD-02-019", "PAD-02-020")
class TestMain:
    def test_dry_run_changes_nothing(self, note: Path) -> None:
        gh = _FakeGh(_DRIFTED)
        assert main(["--catalog", str(note)], run=gh) == 1
        assert gh.verbs() == []

    def test_dry_run_in_sync_exits_zero(self, note: Path) -> None:
        gh = _FakeGh(
            [
                {
                    "name": "theme:alpha",
                    "description": "Alpha works",
                    "color": "1d76db",
                },
                {
                    "name": "theme:beta",
                    "description": "Beta works",
                    "color": "5319e7",
                },
            ]
        )
        assert main(["--catalog", str(note)], run=gh) == 0

    def test_apply_creates_and_edits_never_deletes(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        gh = _FakeGh(_DRIFTED)
        # The unlisted label survives, so drift remains and the exit is 1.
        assert main(["--catalog", str(note), "--apply"], run=gh) == 1
        assert gh.verbs() == [
            ("create", "theme:beta"),
            ("edit", "theme:alpha"),
        ]
        create = next(c for c in gh.calls if c[1] == "create")
        assert create[create.index("--color") + 1] == "5319E7"
        assert create[create.index("--description") + 1] == "Beta works"
        assert all("delete" not in c for c in gh.calls)
        assert "applied 2 label change(s)." in capsys.readouterr().out

    def test_apply_without_unlisted_exits_zero(self, note: Path) -> None:
        gh = _FakeGh(_DRIFTED[:1])
        assert main(["--catalog", str(note), "--apply"], run=gh) == 0

    def test_json(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["--catalog", str(note), "--json"], run=_FakeGh(_DRIFTED))
        out = json.loads(capsys.readouterr().out)
        assert out["missing"] == ["theme:beta"]
        assert out["unlisted"] == ["theme:zeta"]

    def test_repo_flag_reaches_gh(self, note: Path) -> None:
        gh = _FakeGh([])
        main(["--catalog", str(note), "--repo", "o/r", "--apply"], run=gh)
        assert all(c[c.index("--repo") + 1] == "o/r" for c in gh.calls)

    def test_gh_failure_exits_two(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--catalog", str(note)], run=_FakeGh([], fail=True)) == 2
        assert "boom" in capsys.readouterr().err

    def test_apply_failure_exits_two(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        listing = _FakeGh(_DRIFTED)

        def gh(args: Sequence[str]) -> str:
            if args[1] == "create":
                raise subprocess.CalledProcessError(1, ["gh"], stderr="denied")
            return listing(args)

        assert main(["--catalog", str(note), "--apply"], run=gh) == 2
        assert "denied" in capsys.readouterr().err

    def test_apply_renames_a_case_mismatched_label(self, note: Path) -> None:
        gh = _FakeGh(
            [
                {
                    "name": "Theme:Alpha",
                    "description": "Alpha works",
                    "color": "1d76db",
                },
                {
                    "name": "theme:beta",
                    "description": "Beta works",
                    "color": "5319e7",
                },
            ]
        )
        assert main(["--catalog", str(note), "--apply"], run=gh) == 0
        (edit,) = [c for c in gh.calls if c[1] == "edit"]
        assert edit[2] == "Theme:Alpha"
        assert edit[edit.index("--name") + 1] == "theme:alpha"

    def test_json_apply_keeps_stdout_json(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(
            ["--catalog", str(note), "--json", "--apply"],
            run=_FakeGh(_DRIFTED),
        )
        captured = capsys.readouterr()
        assert json.loads(captured.out)["missing"] == ["theme:beta"]
        assert "applied 2 label change(s)." in captured.err

    def test_unreadable_listing_exits_two(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--catalog", str(note)], run=lambda _: "not json") == 2
        assert "could not read" in capsys.readouterr().err

    def test_gh_not_installed_exits_two(
        self, note: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def missing(*_: object, **__: object) -> None:
            raise FileNotFoundError("gh")

        monkeypatch.setattr(theme_labels.subprocess, "run", missing)
        assert main(["--catalog", str(note)]) == 2

    def test_missing_catalog_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        gh = _FakeGh([])
        assert main(["--catalog", str(tmp_path / "absent.md")], run=gh) == 2
        assert "absent.md" in capsys.readouterr().err
        assert gh.calls == []

    def test_bad_catalog_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = tmp_path / "bad.md"
        bad.write_text("no markers here\n", encoding="utf-8")
        gh = _FakeGh([])
        assert main(["--catalog", str(bad)], run=gh) == 2
        assert "exactly one" in capsys.readouterr().err
        assert gh.calls == []
