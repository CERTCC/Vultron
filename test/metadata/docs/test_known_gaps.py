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
"""Tests for the Protocol Specification's known-gaps fragment (DF-12-019/020)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import nav_paths, repo_root
from vultron.metadata.docs.known_gaps import (
    FRAGMENT_PATH,
    ISSUE_URL,
    PAGE,
    UNTESTED_HEADING,
    UNTESTED_LABEL,
    XFAIL_ONLY_HEADING,
    known_gaps_fragment,
    render_fragment,
)
from vultron.metadata.docs.requirement_catalog import NotInCatalogError
from vultron.metadata.docs.rfc2119_keywords import fragment_keyword_faults
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.generated_files import read_committed
from vultron.metadata.specs.coverage import ImplementerCoverageReport
from vultron.metadata.specs.registry import load_registry

_CALLOUT_RE = re.compile(r"requirement_callout\(([^)]*)\)")

#: Built, not written out: a literal marker in this file's text would mark the
#: test requirements below for ``spec-coverage``'s scan of ``test/``.
_SPEC = "pytest.mark." + "spec"


def _gap(n: int) -> str:
    """Test requirement *n*'s ID, built so that no ID that the registry lacks
    is written out in this file (``spec-lint`` rejects a phantom citation,
    SR-04-008)."""
    return f"VP-01-{n:03d}"


_SPEC_FILE = {
    "id": "VP",
    "title": "Vultron Protocol",
    "description": "Known-gaps test requirements.",
    "scope": ["prototype"],
    "tags": ["protocol"],
    "groups": [
        {
            "id": "VP-01",
            "title": "Gaps",
            "specs": [
                {
                    "id": _gap(n),
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": f"A participant MUST do thing {n}.",
                    "rationale": "A test requirement.",
                }
                for n in range(1, 7)
            ],
        }
    ],
}

#: Requirement 1 verified; 2 and 3 held, citing #11; 4 held, citing #11
#: and #12; 5 held by a skip citing no issue; 6 untested.
_TESTS = f"""\
import pytest


@{_SPEC}("{_gap(1)}")
def test_one():
    pass


@{_SPEC}("{_gap(2)}", "{_gap(3)}")
@pytest.mark.xfail(strict=True, reason="{_gap(2)}: not built. Tracked by #11.")
def test_two_and_three():
    pass


@{_SPEC}("{_gap(4)}")
@pytest.mark.xfail(strict=True, reason="{_gap(4)}: needs #12 and #11.")
def test_four():
    pass


@{_SPEC}("{_gap(5)}")
@pytest.mark.skip(reason="no harness yet")
def test_five():
    pass
"""


def _checkout(tmp_path: Path, tests: str | None = _TESTS) -> Path:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "vultron-protocol-spec.yaml").write_text(
        yaml.safe_dump(_SPEC_FILE, sort_keys=False), encoding="utf-8"
    )
    if tests is not None:
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "test_gaps.py").write_text(
            tests, encoding="utf-8"
        )
    return tmp_path


def _fragment(root: Path) -> str:
    return known_gaps_fragment(root, load_registry(root / "specs"))


def _sections(fragment: str) -> tuple[str, str]:
    head, untested = fragment.split(UNTESTED_HEADING)
    return head.split(XFAIL_ONLY_HEADING)[1], untested


def _ids(text: str) -> list[str]:
    return [
        spec_id
        for call in _CALLOUT_RE.findall(text)
        for spec_id in re.findall(r'"([^"]+)"', call)
    ]


def _subsections(section: str) -> dict[str, list[str]]:
    parts = re.split(r"^### (.*)$", section, flags=re.MULTILINE)[1:]
    return {
        title: _ids(body)
        for title, body in zip(parts[::2], parts[1::2], strict=True)
    }


def _link(number: int) -> str:
    return f"[#{number}]({ISSUE_URL.format(number=number)})"


@pytest.mark.spec("DF-12-019")
class TestRenderFragment:
    def test_lists_only_the_gaps_each_in_its_section(self, tmp_path):
        xfail_only, untested = _sections(_fragment(_checkout(tmp_path)))
        assert sorted(_ids(xfail_only)) == [
            _gap(2),
            _gap(3),
            _gap(4),
            _gap(5),
        ]
        assert _ids(untested) == [_gap(6)]

    def test_groups_held_requirements_by_the_issues_cited(self, tmp_path):
        xfail_only, _ = _sections(_fragment(_checkout(tmp_path)))
        assert _subsections(xfail_only) == {
            f"Tracked by {_link(11)}": [_gap(2), _gap(3)],
            f"Tracked by {_link(11)} and {_link(12)}": [_gap(4)],
            "No issue cited": [_gap(5)],
        }

    def test_groups_untested_requirements_by_catalog_page(self, tmp_path):
        _, untested = _sections(_fragment(_checkout(tmp_path)))
        assert _subsections(untested) == {"Vultron Protocol": [_gap(6)]}

    def test_labels_the_untested_section_plainly(self, tmp_path):
        _, untested = _sections(_fragment(_checkout(tmp_path)))
        assert UNTESTED_LABEL == "no test shows `main` does this"
        assert UNTESTED_LABEL in untested
        assert "unbuilt" not in untested.lower()

    def test_an_empty_state_says_so(self, tmp_path):
        xfail_only, untested = _sections(
            _fragment(_checkout(tmp_path, tests=None))
        )
        assert "No requirement is in this state." in xfail_only
        assert len(_ids(untested)) == 6

    def test_three_cited_issues_read_as_a_list(self, tmp_path):
        tests = _TESTS.replace("needs #12 and #11", "needs #13, #12 and #11")
        xfail_only, _ = _sections(_fragment(_checkout(tmp_path, tests)))
        assert f"Tracked by {_link(11)}, {_link(12)}, and {_link(13)}" in (
            _subsections(xfail_only)
        )

    def test_an_empty_registry_is_a_failure_not_no_gaps(self, tmp_path):
        """DF-09-009: no requirement read must not read as no gaps."""
        with pytest.raises(MetadataLoadError, match="DF-09-009"):
            render_fragment(
                ImplementerCoverageReport(requirements=()),
                load_registry(tmp_path / "specs"),
            )

    def test_an_untested_requirement_on_no_catalog_page_raises(self, tmp_path):
        root = _checkout(tmp_path, tests=None)
        spec_file = root / "specs" / "vultron-protocol-spec.yaml"
        spec_file.write_text(
            spec_file.read_text(encoding="utf-8")
            .replace("id: VP\n", "id: ZZ\n")
            .replace("VP-01", "ZZ-01"),
            encoding="utf-8",
        )
        with pytest.raises(NotInCatalogError, match="DF-12-015"):
            _fragment(root)

    def test_prose_holds_no_rfc2119_keyword(self, tmp_path):
        """Statements are rendered by callout, never copied (DF-12-004)."""
        fragment = _fragment(_checkout(tmp_path))
        assert fragment_keyword_faults(FRAGMENT_PATH, fragment) == []
        assert "A participant MUST" not in fragment

    def test_the_same_tree_writes_the_same_fragment(self, tmp_path):
        root = _checkout(tmp_path)
        assert _fragment(root) == _fragment(root)


@pytest.mark.spec("DF-12-020")
class TestDriftCheck:
    @pytest.mark.spec_corpus
    def test_committed_known_gaps_fragment_is_in_sync(self):
        """The CI gate on a ``test/`` change (unit suite) and on a ``specs/``
        change (``spec-check.yml`` runs ``-m spec_corpus``)."""
        root = repo_root()
        assert read_committed(root / FRAGMENT_PATH) == known_gaps_fragment(
            root, load_registry(root / "specs")
        ), "run 'uv run docs-site --write' and commit the result"


@pytest.mark.spec("DF-12-019")
class TestPage:
    def test_page_is_in_the_nav(self):
        assert PAGE in nav_paths()

    def test_page_includes_the_fragment(self):
        text = (repo_root() / "docs" / PAGE).read_text(encoding="utf-8")
        name = Path(FRAGMENT_PATH).name
        assert f'{{% include-markdown "./{name}" %}}' in text

    @pytest.mark.parametrize(
        "host",
        [
            "reference/vultron-spec/index.md",
            "reference/vultron-spec/open-questions.md",
        ],
    )
    def test_page_is_linked_from(self, host):
        text = (repo_root() / "docs" / host).read_text(encoding="utf-8")
        assert f"]({Path(PAGE).name})" in text
