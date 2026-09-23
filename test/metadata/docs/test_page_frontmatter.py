"""Tests for the ``docs/`` page ``stakeholder_type`` / ``level`` validator.

Requirements: DF-11-001, DF-11-003, DF-11-010, DF-11-012, DF-09-009; the
failures are attributed per MS-17-001.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import repo_root
from vultron.metadata.docs import page_frontmatter
from vultron.metadata.docs.page_frontmatter import (
    check_docs_frontmatter,
    classify_docs_tree,
    main,
    prune_baseline,
    read_baseline,
    write_baseline,
)
from vultron.metadata.docs.page_schema import (
    ALL_STAKEHOLDERS,
    LEVELS,
    PageFrontmatter,
    StakeholderType,
    WorkingRecordFrontmatter,
    is_working_record,
)
from vultron.metadata.file_loading import (
    MetadataLoadError,
    MetadataLoadErrors,
    validate,
)

_EVERY_TYPE = [member.value for member in StakeholderType]


def _page(stakeholder_type: str | None = None, level: str | None = None):
    lines = ["title: T"]
    if stakeholder_type is not None:
        lines.append(f"stakeholder_type: {stakeholder_type}")
    if level is not None:
        lines.append(f"level: {level}")
    return "---\n" + "\n".join(lines) + "\n---\n# T\n"


# ---------------------------------------------------------------------------
# Schema (AC-1, AC-1a, AC-1b, AC-3, AC-6)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-001")
class TestPageSchema:
    def test_valid_page(self):
        page = validate(
            PageFrontmatter,
            {"stakeholder_type": ["cvd-practitioner"], "level": 200},
        )
        assert page.stakeholder_type == [StakeholderType.CVD_PRACTITIONER]
        assert page.level == 200

    def test_bare_all(self):
        page = validate(
            PageFrontmatter, {"stakeholder_type": "ALL", "level": 100}
        )
        assert page.stakeholder_type == ALL_STAKEHOLDERS

    def test_two_member_list(self):
        page = validate(
            PageFrontmatter,
            {
                "stakeholder_type": [
                    "platform-developer",
                    "project-contributor",
                ],
                "level": 300,
            },
        )
        assert len(page.stakeholder_type) == 2

    @pytest.mark.parametrize("level", [150, 0, 600, "100", 100.0, True])
    def test_level_off_the_ladder(self, level):
        with pytest.raises(MetadataLoadError, match="level: .*must be one of"):
            validate(
                PageFrontmatter,
                {"stakeholder_type": ["cvd-practitioner"], "level": level},
            )

    def test_unknown_member(self):
        with pytest.raises(
            MetadataLoadError, match="unknown stakeholder type vendor"
        ):
            validate(
                PageFrontmatter, {"stakeholder_type": ["vendor"], "level": 100}
            )

    def test_list_naming_every_type_is_rejected(self):
        """``ALL`` is the only spelling of every type (AC-1a)."""
        with pytest.raises(MetadataLoadError, match="bare scalar ALL instead"):
            validate(
                PageFrontmatter,
                {"stakeholder_type": _EVERY_TYPE, "level": 100},
            )

    def test_bracketed_all_is_rejected(self):
        with pytest.raises(MetadataLoadError, match="not a list containing"):
            validate(
                PageFrontmatter, {"stakeholder_type": ["ALL"], "level": 100}
            )

    @pytest.mark.parametrize(
        "value",
        ["cvd-practitioner", [], ["cvd-practitioner", "cvd-practitioner"], 3],
        ids=["scalar-member", "empty", "duplicate", "number"],
    )
    def test_other_malformed_stakeholder_types(self, value):
        with pytest.raises(MetadataLoadError, match="stakeholder_type: "):
            validate(
                PageFrontmatter, {"stakeholder_type": value, "level": 100}
            )

    @pytest.mark.parametrize("missing", ["stakeholder_type", "level"])
    def test_missing_key(self, missing):
        data = {"stakeholder_type": ["cvd-practitioner"], "level": 100}
        del data[missing]
        with pytest.raises(MetadataLoadError, match=f"{missing}: Field"):
            validate(PageFrontmatter, data)

    def test_members_are_importable_for_the_fragment_generator(self):
        """AC-1b: #3527 reads the vocabulary from here, not a second copy."""
        assert set(_EVERY_TYPE) == {
            "cvd-practitioner",
            "platform-developer",
            "process-researcher",
            "project-contributor",
        }
        assert LEVELS == (100, 200, 300, 400, 500)


@pytest.mark.spec("DF-11-012")
class TestWorkingRecordSchema:
    def test_project_contributor_with_no_level(self):
        record = validate(
            WorkingRecordFrontmatter,
            {"stakeholder_type": ["project-contributor"]},
        )
        assert record.level is None

    @pytest.mark.parametrize("level", [100, None], ids=["value", "null"])
    def test_any_declared_level_is_rejected(self, level):
        with pytest.raises(
            MetadataLoadError, match="must not declare a level"
        ):
            validate(
                WorkingRecordFrontmatter,
                {"stakeholder_type": ["project-contributor"], "level": level},
            )

    @pytest.mark.parametrize(
        "value", [["cvd-practitioner"], "ALL"], ids=["other", "all"]
    )
    def test_other_audiences_are_rejected(self, value):
        with pytest.raises(MetadataLoadError, match="must declare"):
            validate(WorkingRecordFrontmatter, {"stakeholder_type": value})

    def test_missing_stakeholder_type_is_still_a_finding(self):
        with pytest.raises(MetadataLoadError, match="stakeholder_type: Field"):
            validate(WorkingRecordFrontmatter, {})


@pytest.mark.spec("DF-11-003")
@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("adr/0001-x.md", True),
        ("adr/archived/0015-x.md", True),
        ("developer/a/b.md", True),
        ("reference/case_states/state_x.md", True),
        ("reference/code/api/x.md", True),
        ("topics/behavior_logic/rm_bt.md", True),
        ("topics/behavior_logic/index.md", False),
        ("topics/behavior_logic/use-cases/x_bt.md", False),
        ("reference/codebase_notes.md", False),
        ("tutorials/index.md", False),
    ],
)
def test_working_record_patterns(path, expected):
    assert is_working_record(path) is expected


# ---------------------------------------------------------------------------
# Loader (AC-2, AC-3, AC-3a, AC-3b, AC-5)
# ---------------------------------------------------------------------------


def _repo(tmp_path: Path, files: dict[str, str], nav=None, auto_append=None):
    """Build a minimal checkout: ``mkdocs.yml`` plus ``docs/`` files."""
    config: dict[str, object] = {"nav": nav or []}
    if auto_append:
        config["markdown_extensions"] = [
            {"pymdownx.snippets": {"auto_append": auto_append}}
        ]
    (tmp_path / "mkdocs.yml").write_text(yaml.safe_dump(config))
    for rel, text in files.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


#: The committed baseline's entry count may only fall. Lower this when
#: ``--prune-baseline`` shrinks the file; raising it defeats AC-3a of #3525.
_BASELINE_CEILING = 468

_READER = _page("[cvd-practitioner]", "100")
_RECORD = _page("[project-contributor]")


@pytest.mark.spec("DF-11-001")
class TestCheck:
    def test_valid_tree_passes(self, tmp_path):
        root = _repo(
            tmp_path,
            {"index.md": _READER, "adr/0001-x.md": _RECORD},
            nav=["index.md", "adr/0001-x.md"],
        )

        result = check_docs_frontmatter(root, baseline=set())

        assert (result.reader_pages, result.working_record_pages) == (1, 1)

    @pytest.mark.spec("MS-17-001")
    def test_yaml_fault_names_path_line_and_column(self, tmp_path):
        root = _repo(
            tmp_path, {"index.md": "---\ntitle: a: b\n---\n"}, nav=["index.md"]
        )

        with pytest.raises(MetadataLoadErrors) as info:
            check_docs_frontmatter(root, baseline=set())

        (failure,) = info.value.failures
        assert failure.location == "docs/index.md:2:9"

    @pytest.mark.spec("MS-17-001")
    def test_schema_fault_names_the_key_line(self, tmp_path):
        root = _repo(
            tmp_path,
            {"index.md": _page("[cvd-practitioner]", "150")},
            nav=["index.md"],
        )

        with pytest.raises(MetadataLoadErrors) as info:
            check_docs_frontmatter(root, baseline=set())

        assert str(info.value.failures[0]).startswith(
            "docs/index.md:4 — level"
        )

    def test_every_failure_is_reported(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a.md": _page("[vendor]", "100"),
                "b.md": _page("[cvd-practitioner]"),
            },
        )

        with pytest.raises(MetadataLoadErrors) as info:
            check_docs_frontmatter(root, baseline=set())

        assert [f.path for f in info.value.failures] == [
            "docs/a.md",
            "docs/b.md",
        ]

    @pytest.mark.spec("DF-11-012")
    def test_working_record_page_with_a_level_fails(self, tmp_path):
        root = _repo(
            tmp_path, {"adr/0001-x.md": _page("[project-contributor]", "100")}
        )

        with pytest.raises(
            MetadataLoadErrors, match="must not declare a level"
        ):
            check_docs_frontmatter(root, baseline=set())

    @pytest.mark.spec("DF-09-009")
    @pytest.mark.parametrize("docs", [True, False], ids=["empty", "absent"])
    def test_empty_target_set_fails(self, tmp_path, docs):
        _repo(tmp_path, {})
        if docs:
            (tmp_path / "docs").mkdir()

        with pytest.raises(MetadataLoadError, match="empty target set"):
            check_docs_frontmatter(tmp_path, baseline=set())


@pytest.mark.spec("DF-11-001")
class TestBaseline:
    def test_undeclared_page_outside_the_baseline_fails(self, tmp_path):
        root = _repo(tmp_path, {"index.md": "# no frontmatter\n"})

        with pytest.raises(MetadataLoadErrors, match="declares neither key"):
            check_docs_frontmatter(root, baseline=set())

    def test_baselined_undeclared_page_is_tolerated(self, tmp_path):
        root = _repo(
            tmp_path, {"index.md": "# none\n", "adr/0001-x.md": "# none\n"}
        )

        result = check_docs_frontmatter(
            root, baseline={"index.md", "adr/0001-x.md"}
        )

        assert sorted(result.undeclared) == ["adr/0001-x.md", "index.md"]

    def test_entry_for_a_page_that_now_declares_is_stale(self, tmp_path):
        """The baseline cannot keep an entry once its page is done."""
        root = _repo(tmp_path, {"index.md": _READER})

        with pytest.raises(MetadataLoadErrors, match="--prune-baseline"):
            check_docs_frontmatter(root, baseline={"index.md"})

    def test_entry_for_a_missing_page_is_stale(self, tmp_path):
        root = _repo(tmp_path, {"index.md": _READER})

        with pytest.raises(MetadataLoadErrors, match="no longer a page"):
            check_docs_frontmatter(root, baseline={"gone.md"})

    def test_prune_only_removes(self, tmp_path):
        root = _repo(tmp_path, {"done.md": _READER, "todo.md": "# none\n"})
        baseline = tmp_path / "baseline.txt"
        write_baseline({"done.md", "todo.md", "gone.md"}, baseline)

        removed = prune_baseline(root, baseline)

        assert removed == 2
        assert read_baseline(baseline) == {"todo.md"}

    def test_committed_baseline_never_grows(self):
        """AC-3a: the baseline only shrinks.

        Nothing else stops a new undeclared page from being tolerated by
        adding its path to the file. When pages gain declarations and the
        baseline is pruned, lower the ceiling to the new count; never raise it.
        """
        count = len(read_baseline())

        assert count <= _BASELINE_CEILING, (
            f"{page_frontmatter.BASELINE_PATH.name} has {count} entries, above "
            f"its ceiling of {_BASELINE_CEILING}. Declare stakeholder_type and "
            f"level on the new page instead of baselining it (DF-11-001)."
        )

    def test_committed_baseline_is_sorted_and_has_its_header(self):
        text = page_frontmatter.BASELINE_PATH.read_text(encoding="utf-8")
        entries = [
            line
            for line in text.splitlines()
            if line and not line.startswith("#")
        ]
        assert entries == sorted(entries)
        assert "may only shrink" in text


@pytest.mark.spec("DF-11-010")
class TestFragments:
    def test_whole_included_unnavved_file_is_a_fragment(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a/index.md": _READER
                + '{% include-markdown "../includes/note.md" %}\n',
                "b.md": _READER
                + '{% include-markdown "includes/note.md" %}\n',
                "includes/note.md": "Note.\n",
            },
            nav=["a/index.md", "b.md"],
        )

        tree = classify_docs_tree(root)

        assert tree.fragments == {"includes/note.md": ("a/index.md", "b.md")}
        assert "includes/note.md" not in tree.pages
        check_docs_frontmatter(root, baseline=set())

    def test_unprefixed_target_resolves_against_docs(self, tmp_path):
        """From a nested host, a target without ``./`` is still docs-relative."""
        root = _repo(
            tmp_path,
            {
                "a/b/page.md": _READER
                + '{% include-markdown "includes/note.md" %}\n',
                "includes/note.md": "Note.\n",
            },
            nav=["a/b/page.md"],
        )

        tree = classify_docs_tree(root)

        assert tree.fragments == {"includes/note.md": ("a/b/page.md",)}

    def test_glob_target_expands(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a/index.md": _READER
                + '{% include-markdown "../includes/*.md" %}\n',
                "includes/one.md": "One.\n",
                "includes/two.md": "Two.\n",
            },
            nav=["a/index.md"],
        )

        tree = classify_docs_tree(root)

        assert set(tree.fragments) == {"includes/one.md", "includes/two.md"}

    def test_fragment_declaring_a_key_is_reported(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "index.md": _READER + '{% include-markdown "./_f.md" %}\n',
                "_f.md": "---\ntitle: F\nlevel: 100\n---\nF\n",
            },
            nav=["index.md"],
        )

        with pytest.raises(MetadataLoadErrors) as info:
            check_docs_frontmatter(root, baseline=set())

        (failure,) = info.value.failures
        assert failure.location == "docs/_f.md:3"
        assert "must not declare level" in failure.detail
        assert "index.md" in failure.detail

    def test_auto_appended_file_is_a_fragment(self, tmp_path):
        root = _repo(
            tmp_path,
            {"index.md": _READER, "_acronyms/index.md": "*[CVD]: x\n"},
            auto_append=["docs/_acronyms/index.md"],
        )

        assert "_acronyms/index.md" in classify_docs_tree(root).fragments

    def test_marker_included_file_is_still_a_page(self, tmp_path):
        """A user story quoted on its traceability page keeps its own URL."""
        root = _repo(
            tmp_path,
            {
                "index.md": _READER
                + '{% include-markdown "./story.md" start="<!-- s -->" '
                'end="<!-- e -->" %}\n',
                "story.md": "# none\n",
            },
        )

        assert "story.md" in classify_docs_tree(root).pages

    def test_end_only_include_is_still_whole(self, tmp_path):
        """Without ``start=`` the include copies from line 1, frontmatter too."""
        root = _repo(
            tmp_path,
            {
                "index.md": _READER
                + '{% include-markdown "./_f.md" end="<!-- e -->" %}\n',
                "_f.md": "Body.\n<!-- e -->\n",
            },
        )

        assert "_f.md" in classify_docs_tree(root).fragments

    def test_declaring_page_included_whole_is_reported(self, tmp_path):
        """Its frontmatter would render into the host (DF-11-004)."""
        root = _repo(
            tmp_path,
            {
                "host.md": _READER + '{% include-markdown "./page.md" %}\n',
                "page.md": _READER,
            },
            nav=["host.md", "page.md"],
        )

        with pytest.raises(MetadataLoadErrors, match="included whole by host"):
            check_docs_frontmatter(root, baseline=set())


# ---------------------------------------------------------------------------
# Entry points (AC-4) and the real tree
# ---------------------------------------------------------------------------


def test_cli_reports_failures_without_a_traceback(
    tmp_path, monkeypatch, capsys
):
    root = _repo(tmp_path, {"index.md": "---\ntitle: a: b\n---\n"})
    monkeypatch.setattr(page_frontmatter, "_find_repo_root", lambda: root)
    monkeypatch.setattr(
        page_frontmatter, "BASELINE_PATH", tmp_path / "baseline.txt"
    )

    with pytest.raises(SystemExit) as info:
        main([])

    assert info.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("[ERROR] 1 docs frontmatter finding(s)")
    assert "docs/index.md:2:9" in err


@pytest.mark.parametrize(
    "changed",
    [
        "docs/tutorials/deep/page.md",
        "mkdocs.yml",
        "vultron/metadata/docs/page_frontmatter_baseline.txt",
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
    hook = hooks["validate-docs-page-frontmatter"]

    assert "vultron.metadata.docs.page_frontmatter" in hook["entry"]
    assert hook["pass_filenames"] is False
    assert re.search(hook["files"], changed)


@pytest.mark.spec("DF-11-001")
def test_the_committed_docs_tree_passes():
    """The gate CI enforces, independent of whether the hook ran locally."""
    result = check_docs_frontmatter()

    assert result.reader_pages > 0
    assert result.working_record_pages > 0
