"""Tests for the normative banner check (DF-12-006, DF-12-007, DF-09-009).

The failures are attributed per MS-17-001.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import repo_root
from vultron.metadata.docs import normative_banner
from vultron.metadata.docs.normative_banner import (
    BANNER,
    GOVERNS_BANNER,
    NORMATIVE_PAGES,
    NOT_NORMATIVE_BANNER,
    SPECIFICATION_GOVERNS_PAGES,
    check_normative_banner,
    main,
)
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors

_NORMATIVE = ("spec/part.md",)
_GOVERNS = ("design/model.md",)
_EXAMPLES = ("conventions.md",)
_INCLUDE = '{% include-markdown "includes/normative.md" %}\n'
_GOVERNS_INCLUDE = (
    '{% include-markdown "includes/specification_governs.md" %}\n'
)
_DESIGN_PAGE = (
    "---\nsubject: protocol\n---\n# Model\n\n"
    '{% include-markdown "../includes/specification_governs.md" %}\n'
)


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _tree(**overrides: str) -> dict[str, str]:
    files = {
        BANNER: "!!! success\n",
        GOVERNS_BANNER: "!!! info\n",
        "spec/part.md": '# Part\n\n{% include-markdown "../includes/normative.md" %}\n',
        "design/model.md": _DESIGN_PAGE,
        "conventions.md": "# C\n\n    "
        + _INCLUDE
        + "\n    "
        + _GOVERNS_INCLUDE,
        "other.md": "# Other\n",
    }
    files.update(overrides)
    return files


def _check(
    root: Path,
    normative: tuple[str, ...] = _NORMATIVE,
    governs: tuple[str, ...] = _GOVERNS,
):
    return check_normative_banner(
        root,
        normative_pages=normative,
        governs_pages=governs,
        example_pages=_EXAMPLES,
    )


def _failures(root: Path, **kwargs) -> tuple[MetadataLoadError, ...]:
    with pytest.raises(MetadataLoadErrors) as info:
        _check(root, **kwargs)
    return info.value.failures


@pytest.mark.spec("DF-12-006")
class TestNormativeSet:
    def test_passing_tree(self, tmp_path):
        result = _check(_repo(tmp_path, _tree()))

        assert result.normative_pages == 1
        assert result.governs_pages == 1
        assert result.scanned_files == 6

    def test_declared_page_without_banner_fails(self, tmp_path):
        root = _repo(tmp_path, _tree(**{"spec/part.md": "# Part\n"}))

        [failure] = _failures(root)

        assert failure.location == "docs/spec/part.md"
        assert "does not include" in str(failure)

    def test_banner_through_a_shared_fragment_does_not_count(self, tmp_path):
        root = _repo(
            tmp_path,
            _tree(
                **{
                    "spec/part.md": '# Part\n\n{% include-markdown "./_f.md" %}\n',
                    "spec/_f.md": "Intro.\n\n" + _INCLUDE,
                }
            ),
        )

        locations = sorted(str(f.location) for f in _failures(root))

        assert locations == ["docs/spec/_f.md:3", "docs/spec/part.md"]

    def test_other_page_including_banner_fails_at_its_line(self, tmp_path):
        root = _repo(
            tmp_path,
            _tree(**{"other.md": "---\nx: 1\n---\n# O\n\n" + _INCLUDE}),
        )

        [failure] = _failures(root)

        assert failure.location == "docs/other.md:6"
        assert "specification_governs.md" in str(failure)

    def test_every_offending_directive_is_reported(self, tmp_path):
        root = _repo(
            tmp_path,
            _tree(
                **{
                    "other.md": "# O\n" + _INCLUDE + _INCLUDE,
                    "deep/x.md": '{% include "../includes/normative.md" %}\n',
                }
            ),
        )

        locations = sorted(str(f.location) for f in _failures(root))

        assert locations == [
            "docs/deep/x.md:1",
            "docs/other.md:2",
            "docs/other.md:3",
        ]

    def test_single_quoted_relative_target_counts(self, tmp_path):
        root = _repo(
            tmp_path,
            _tree(
                **{
                    "a/b/c.md": "# C\n"
                    "{% include-markdown '../../includes/normative.md' %}\n"
                }
            ),
        )

        [failure] = _failures(root)

        assert failure.location == "docs/a/b/c.md:2"

    def test_plain_text_mention_is_not_an_include(self, tmp_path):
        root = _repo(
            tmp_path,
            _tree(
                **{
                    "other.md": "# O\n\nThe banner is `docs/includes/normative.md`.\n"
                }
            ),
        )

        assert _check(root).normative_pages == 1

    def test_example_page_is_not_exempt_without_listing(self, tmp_path):
        root = _repo(tmp_path, _tree())

        with pytest.raises(MetadataLoadErrors) as info:
            check_normative_banner(
                root,
                normative_pages=_NORMATIVE,
                governs_pages=_GOVERNS,
                example_pages=(),
            )

        locations = sorted(str(f.location) for f in info.value.failures)
        assert locations == ["docs/conventions.md:3", "docs/conventions.md:5"]

    def test_missing_declared_page_fails(self, tmp_path):
        root = _repo(tmp_path, _tree())

        [failure] = _failures(root, normative=(*_NORMATIVE, "spec/gone.md"))

        assert failure.location == "docs/spec/gone.md"
        assert "NORMATIVE_PAGES" in str(failure)

    def test_missing_example_page_fails(self, tmp_path):
        files = _tree()
        del files["conventions.md"]

        [failure] = _failures(_repo(tmp_path, files))

        assert failure.location == "docs/conventions.md"
        assert "BANNER_EXAMPLE_PAGES" in str(failure)

    def test_missing_banner_fails(self, tmp_path):
        files = _tree()
        del files[BANNER]

        [failure] = _failures(_repo(tmp_path, files))

        assert failure.location == f"docs/{BANNER}"


@pytest.mark.spec("DF-09-009")
class TestEmptyTargetSet:
    def test_no_docs_tree_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="empty target set"):
            _check(tmp_path)

    def test_empty_normative_set_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="normative-set pages"):
            _check(_repo(tmp_path, _tree()), normative=())

    def test_empty_protocol_design_set_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="protocol-design pages"):
            _check(_repo(tmp_path, _tree()), governs=())


def test_cli_reports_failures_without_a_traceback(
    tmp_path, monkeypatch, capsys
):
    root = _repo(tmp_path, _tree(**{"other.md": "# O\n" + _INCLUDE}))
    monkeypatch.setattr(normative_banner, "_find_repo_root", lambda: root)

    with pytest.raises(SystemExit) as info:
        main([])

    assert info.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("[ERROR] ")
    assert "docs/other.md:2" in err


def test_cli_summarizes_the_committed_tree(capsys):
    main([])

    assert capsys.readouterr().out.startswith("Checked ")


@pytest.mark.spec("DF-12-006")
def test_the_committed_docs_tree_passes():
    """The gate CI enforces, independent of whether the hook ran locally."""
    result = check_normative_banner()

    assert result.normative_pages == len(NORMATIVE_PAGES)
    assert result.governs_pages == len(SPECIFICATION_GOVERNS_PAGES)


@pytest.mark.parametrize(
    "changed",
    [
        "docs/includes/normative.md",
        "docs/reference/vultron-spec/_introduction.md",
        "vultron/metadata/docs/normative_banner.py",
        "vultron/metadata/docs/page_frontmatter.py",
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
    hook = hooks["docs-normative-banner"]

    assert "vultron.metadata.docs.normative_banner" in hook["entry"]
    assert hook["pass_filenames"] is False
    assert re.search(hook["files"], changed)


_RFC_2119 = re.compile(
    r"\b(MUST|SHALL|SHOULD|REQUIRED|RECOMMENDED|MAY|OPTIONAL)\b", re.IGNORECASE
)


@pytest.mark.spec("DF-12-007")
class TestSpecificationGovernsBanner:
    def _text(self) -> str:
        return (
            repo_root() / "docs/includes/specification_governs.md"
        ).read_text(encoding="utf-8")

    def test_states_precedence_without_rfc_2119_keywords(self):
        text = self._text()

        assert "informative" in text
        assert "the specification governs" in text
        assert _RFC_2119.search(text) is None

    def test_the_committed_protocol_design_pages_are_declared(self):
        """The set #4945 moved off the normative banner stays declared."""
        assert "reference/formal_protocol/index.md" in (
            SPECIFICATION_GOVERNS_PAGES
        )
        assert "topics/process_models/rm/index.md" in (
            SPECIFICATION_GOVERNS_PAGES
        )


@pytest.mark.spec("DF-12-007")
class TestProtocolDesignPages:
    def test_declared_page_without_the_banner_fails(self, tmp_path):
        root = _repo(
            tmp_path,
            _tree(**{"design/model.md": "---\nsubject: protocol\n---\n# M\n"}),
        )

        [failure] = _failures(root)

        assert failure.location == "docs/design/model.md"
        assert "protocol-design pages but does not include" in str(failure)

    def test_other_page_including_the_banner_fails_at_its_line(self, tmp_path):
        root = _repo(
            tmp_path, _tree(**{"other.md": "# O\n\n" + _GOVERNS_INCLUDE})
        )

        [failure] = _failures(root)

        assert failure.location == "docs/other.md:3"
        assert "SPECIFICATION_GOVERNS_PAGES" in str(failure)

    def test_normative_page_carrying_it_too_fails(self, tmp_path):
        part = (
            '# Part\n\n{% include-markdown "../includes/normative.md" %}\n'
            '{% include-markdown "../includes/specification_governs.md" %}\n'
        )
        root = _repo(tmp_path, _tree(**{"spec/part.md": part}))

        [failure] = _failures(root)

        assert failure.location == "docs/spec/part.md:4"

    def test_declared_page_with_another_subject_fails_at_the_key(
        self, tmp_path
    ):
        page = _DESIGN_PAGE.replace("protocol", "implementation", 1)
        root = _repo(tmp_path, _tree(**{"design/model.md": page}))

        [failure] = _failures(root)

        assert failure.location == "docs/design/model.md:2"
        assert "subject: implementation" in str(failure)

    def test_declared_page_with_no_subject_is_left_to_docs_frontmatter(
        self, tmp_path
    ):
        page = _DESIGN_PAGE.replace("---\nsubject: protocol\n---\n", "")
        root = _repo(tmp_path, _tree(**{"design/model.md": page}))

        assert _check(root).governs_pages == 1

    @pytest.mark.parametrize(
        "frontmatter",
        ["subject: Protocol\n", "title: a: b\n"],
        ids=["invalid-subject", "unparsable"],
    )
    def test_a_fault_docs_frontmatter_reports_is_not_repeated(
        self, tmp_path, frontmatter
    ):
        page = _DESIGN_PAGE.replace("subject: protocol\n", frontmatter, 1)
        root = _repo(tmp_path, _tree(**{"design/model.md": page}))

        assert _check(root).governs_pages == 1

    def test_declared_page_with_the_not_normative_banner_fails(self, tmp_path):
        page = (
            _DESIGN_PAGE
            + '{% include-markdown "../includes/not_normative.md" %}\n'
        )
        root = _repo(tmp_path, _tree(**{"design/model.md": page}))

        [failure] = _failures(root)

        assert failure.location == "docs/design/model.md:7"
        assert NOT_NORMATIVE_BANNER in str(failure)

    def test_page_in_both_sets_fails(self, tmp_path):
        root = _repo(tmp_path, _tree())

        failures = _failures(root, governs=(*_GOVERNS, "spec/part.md"))

        assert str(failures[0].location) == "docs/spec/part.md"
        assert "both NORMATIVE_PAGES and SPECIFICATION_GOVERNS_PAGES" in str(
            failures[0]
        )

    @pytest.mark.parametrize("which", ["normative", "governs"])
    def test_page_listed_twice_fails(self, tmp_path, which):
        root = _repo(tmp_path, _tree())
        sets = {"normative": _NORMATIVE, "governs": _GOVERNS}
        sets[which] = sets[which] * 2

        [failure] = _failures(root, **sets)

        assert "listed more than once" in str(failure)

    def test_missing_declared_page_fails(self, tmp_path):
        root = _repo(tmp_path, _tree())

        [failure] = _failures(root, governs=(*_GOVERNS, "design/gone.md"))

        assert failure.location == "docs/design/gone.md"
        assert "SPECIFICATION_GOVERNS_PAGES" in str(failure)

    def test_missing_banner_fails(self, tmp_path):
        files = _tree()
        del files[GOVERNS_BANNER]

        [failure] = _failures(_repo(tmp_path, files))

        assert failure.location == f"docs/{GOVERNS_BANNER}"
