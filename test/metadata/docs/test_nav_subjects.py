"""Tests for the nav-section subject check (DF-11-020, DF-11-025, DF-09-009).

The failures are attributed per MS-17-001.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import repo_root
from vultron.metadata.docs import nav_subjects
from vultron.metadata.docs.nav_subjects import check_nav_subjects, main
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors


def _page(subject: str | None) -> str:
    if subject is None:
        return "# T\n"
    return f"---\nsubject: {subject}\n---\n# T\n"


def _repo(tmp_path: Path, nav: object, pages: dict[str, str | None]) -> Path:
    (tmp_path / "mkdocs.yml").write_text(yaml.safe_dump({"nav": nav}))
    for rel, subject in pages.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_page(subject), encoding="utf-8")
    return tmp_path


_PAGES: dict[str, str | None] = {
    "index.md": "neutral",
    "spec/a.md": "protocol",
    "spec/b.md": "protocol",
    "spec/c.md": "protocol",
    "impl/x.md": "implementation",
    "impl/y.md": "implementation",
    "notes.md": "neutral",
}

_NAV: list[object] = [
    {"Home": ["index.md"]},
    {"Protocol": ["spec/a.md", {"Deeper": ["spec/b.md", "spec/c.md"]}]},
    {"Implementation": ["impl/x.md", "impl/y.md", "notes.md"]},
    {"CERT/CC": "https://certcc.github.io/"},
]


def _failures(root: Path) -> tuple[MetadataLoadError, ...]:
    with pytest.raises(MetadataLoadErrors) as info:
        check_nav_subjects(root)
    return info.value.failures


@pytest.mark.spec("DF-11-020")
class TestSections:
    def test_separated_nav_passes(self, tmp_path):
        result = check_nav_subjects(_repo(tmp_path, _NAV, _PAGES))

        assert (result.sections, result.pages) == (4, 7)

    def test_neutral_pages_sit_beside_either_subject(self, tmp_path):
        nav = [
            {"Mixed": ["notes.md", "spec/a.md"]},
            {"M2": ["notes.md", "impl/x.md"]},
        ]

        assert check_nav_subjects(_repo(tmp_path, nav, _PAGES)).sections == 2

    def test_implementation_page_in_a_protocol_section_fails(self, tmp_path):
        nav = [{"Protocol": ["spec/a.md", "spec/b.md", "impl/x.md"]}]

        [failure] = _failures(_repo(tmp_path, nav, _PAGES))

        assert failure.path == "mkdocs.yml"
        message = str(failure)
        assert "'Protocol'" in message
        assert "implementation page(s) docs/impl/x.md" in message
        assert "beside 2 protocol page(s) (first: docs/spec/a.md)" in message
        assert "DF-11-020" in message

    def test_a_tie_names_both_subjects(self, tmp_path):
        nav = [{"Mixed": ["spec/a.md", "impl/x.md"]}]

        [failure] = _failures(_repo(tmp_path, nav, _PAGES))

        assert (
            "holds protocol page(s) docs/spec/a.md and implementation page(s) "
            "docs/impl/x.md;" in str(failure)
        )

    def test_every_section_holding_both_is_reported_innermost_first(
        self, tmp_path
    ):
        nav = [
            {
                "Protocol": [
                    "spec/a.md",
                    {"Deeper": ["spec/b.md", "impl/x.md"]},
                ]
            }
        ]

        failures = _failures(_repo(tmp_path, nav, _PAGES))

        assert [str(f).split("'")[1] for f in failures] == [
            "Protocol > Deeper",
            "Protocol",
        ]

    def test_a_mix_across_subgroups_is_reported_at_their_parent(
        self, tmp_path
    ):
        nav = [
            {
                "Tab": [
                    {"P": ["spec/a.md"]},
                    {"I": ["impl/x.md"]},
                ]
            }
        ]

        [failure] = _failures(_repo(tmp_path, nav, _PAGES))

        assert "'Tab'" in str(failure)

    def test_every_mixing_section_is_reported(self, tmp_path):
        nav = [
            {"One": ["spec/a.md", "impl/x.md"]},
            {"Two": ["spec/b.md", "impl/y.md"]},
        ]

        assert len(_failures(_repo(tmp_path, nav, _PAGES))) == 2

    def test_a_page_without_a_valid_subject_counts_as_neither(self, tmp_path):
        """``docs-frontmatter`` reports it; one fault, one tool."""
        pages = {**_PAGES, "bare.md": None, "odd.md": "protocolish"}
        nav = [
            {"P": ["spec/a.md", "bare.md", "odd.md"]},
            {"I": ["impl/x.md", "bare.md"]},
        ]

        assert check_nav_subjects(_repo(tmp_path, nav, pages)).pages == 4

    def test_unparsable_frontmatter_is_read_once_and_left_to_docs_frontmatter(
        self, tmp_path
    ):
        root = _repo(tmp_path, [{"P": ["spec/a.md", "bad.md"]}], _PAGES)
        (root / "docs/bad.md").write_text("---\ntitle: a: b\n---\n# T\n")
        nav = [{"P": ["spec/a.md", "bad.md"]}, {"Q": ["bad.md", "spec/b.md"]}]
        (root / "mkdocs.yml").write_text(yaml.safe_dump({"nav": nav}))

        result = check_nav_subjects(root)

        assert result.pages == 3

    def test_every_page_missing_reports_them_with_the_empty_set(
        self, tmp_path
    ):
        root = _repo(tmp_path, [{"P": ["gone.md"]}], {})

        locations = sorted(str(f.location) for f in _failures(root))

        assert locations == ["docs/gone.md", "mkdocs.yml"]

    def test_a_missing_nav_page_is_reported(self, tmp_path):
        nav = [{"P": ["spec/a.md", "spec/gone.md"]}, {"Q": ["spec/gone.md"]}]

        [failure] = _failures(_repo(tmp_path, nav, _PAGES))

        assert failure.path == "docs/spec/gone.md"
        assert "does not exist" in str(failure)

    def test_an_unreadable_nav_item_is_reported(self, tmp_path):
        nav = [{"P": ["spec/a.md", {"a": "x.md", "b": "y.md"}]}]

        [failure] = _failures(_repo(tmp_path, nav, _PAGES))

        assert "cannot read" in str(failure)

    def test_a_top_level_page_is_in_no_section(self, tmp_path):
        nav = ["spec/a.md", "impl/x.md", {"Home": ["index.md"]}]

        result = check_nav_subjects(_repo(tmp_path, nav, _PAGES))

        assert (result.sections, result.pages) == (1, 3)


@pytest.mark.spec("DF-09-009")
class TestEmptyTargetSet:
    def test_no_nav_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="empty target set"):
            check_nav_subjects(_repo(tmp_path, None, {}))

    def test_nav_with_no_section_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="no sections"):
            check_nav_subjects(_repo(tmp_path, ["index.md"], _PAGES))

    def test_sections_with_no_page_fail(self, tmp_path):
        nav = [{"Links": ["https://example.org/"]}]

        with pytest.raises(MetadataLoadError, match="no pages"):
            check_nav_subjects(_repo(tmp_path, nav, {}))


def test_cli_reports_failures_without_a_traceback(
    tmp_path, monkeypatch, capsys
):
    root = _repo(tmp_path, [{"M": ["spec/a.md", "impl/x.md"]}], _PAGES)
    monkeypatch.setattr(nav_subjects, "_find_repo_root", lambda: root)

    with pytest.raises(SystemExit) as info:
        main([])

    assert info.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("[ERROR] 1 nav subject finding(s) (DF-11-020):")
    assert "'M'" in err


def test_cli_summarizes_a_passing_nav(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, _NAV, _PAGES)
    monkeypatch.setattr(nav_subjects, "_find_repo_root", lambda: root)

    main([])

    assert capsys.readouterr().out == (
        "Checked 4 nav section(s) over 7 page(s); none mixes protocol and "
        "implementation pages.\n"
    )


@pytest.mark.spec("DF-11-020")
def test_the_committed_nav_passes():
    """The gate CI enforces, independent of whether the hook ran locally."""
    result = check_nav_subjects()

    assert result.sections > 0
    assert result.pages > 0


@pytest.mark.parametrize(
    "changed",
    [
        "mkdocs.yml",
        "docs/reference/trigger-api.md",
        "vultron/metadata/docs/nav_subjects.py",
        "vultron/metadata/docs/landing_pages.py",
        "vultron/metadata/docs/page_schema.py",
        "vultron/metadata/base.py",
        "vultron/metadata/file_loading.py",
    ],
)
def test_pre_commit_hook_runs_on_every_input(changed):
    config = yaml.safe_load(
        (repo_root() / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hooks = {
        hook["id"]: hook
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
    }
    hook = hooks["docs-nav-subjects"]

    assert hook["entry"] == "uv run docs-nav-subjects"
    assert hook["pass_filenames"] is False
    assert re.search(hook["files"], changed)
