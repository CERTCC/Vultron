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
    NORMATIVE_PAGES,
    check_normative_banner,
    main,
)
from vultron.metadata.docs.page_frontmatter import include_directives
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors

_NORMATIVE = ("spec/part.md",)
_EXAMPLES = ("conventions.md",)
_INCLUDE = '{% include-markdown "includes/normative.md" %}\n'


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _tree(**overrides: str) -> dict[str, str]:
    files = {
        BANNER: "!!! success\n",
        "spec/part.md": '# Part\n\n{% include-markdown "../includes/normative.md" %}\n',
        "conventions.md": '# C\n\n    {% include-markdown "includes/normative.md" %}\n',
        "other.md": "# Other\n",
    }
    files.update(overrides)
    return files


def _check(root: Path, normative: tuple[str, ...] = _NORMATIVE):
    return check_normative_banner(
        root, normative_pages=normative, example_pages=_EXAMPLES
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
        assert result.scanned_files == 4

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
                root, normative_pages=_NORMATIVE, example_pages=()
            )

        [failure] = info.value.failures
        assert failure.location == "docs/conventions.md:3"

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


@pytest.mark.parametrize(
    "changed",
    [
        "docs/includes/normative.md",
        "docs/reference/vultron-spec/_introduction.md",
        "vultron/metadata/docs/normative_banner.py",
        "vultron/metadata/docs/page_frontmatter.py",
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


#: The Formal Protocol and process-model pages that explain the protocol's
#: design (DF-12-007).
_PROTOCOL_DESIGN_PAGES = [
    "reference/formal_protocol/conclusion.md",
    "reference/formal_protocol/index.md",
    "reference/formal_protocol/messages.md",
    "reference/formal_protocol/protocol_definition.md",
    "reference/formal_protocol/states.md",
    "reference/formal_protocol/transitions.md",
    "topics/process_models/cs/cs_model.md",
    "topics/process_models/cs/index.md",
    "topics/process_models/cs/transitions.md",
    "topics/process_models/em/defaults.md",
    "topics/process_models/em/early_termination.md",
    "topics/process_models/em/index.md",
    "topics/process_models/em/negotiating.md",
    "topics/process_models/em/principles.md",
    "topics/process_models/em/split_merge.md",
    "topics/process_models/em/working_with_others.md",
    "topics/process_models/model_interactions/rm_em.md",
    "topics/process_models/model_interactions/rm_em_cs.md",
    "topics/process_models/rm/index.md",
]

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

    @pytest.mark.parametrize("page", _PROTOCOL_DESIGN_PAGES)
    def test_protocol_design_pages_include_it(self, page):
        docs = repo_root() / "docs"

        targets = {
            target for _, target, _ in include_directives(docs / page, docs)
        }

        assert "includes/specification_governs.md" in targets
