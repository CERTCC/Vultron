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
"""Tests for the "not yet in the reference implementation" marker (DF-12-021).

The catalog row and every callout of an xfail-only requirement carry the
marker, generated from ``spec-coverage``'s states (SR-05-017); no other row
does, and the marker leaves a row once a marked test runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from vultron.metadata.docs.requirement_catalog import CatalogPage
from vultron.metadata.specs.coverage import compute_implementer_coverage
from vultron.metadata.specs.docs_render import (
    pages as docs_pages,
    render_catalog_page,
    render_for_kind,
    requirement_callout,
)
from vultron.metadata.specs.docs_render.rows import (
    ISSUE_URL,
    NOT_YET_IMPLEMENTED_LABEL,
)
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import SpecKind


def _req(n: int) -> str:
    """Test requirement *n*'s ID, built so that no ID the registry lacks is
    written out in this file (``spec-lint`` rejects a phantom citation)."""
    return f"VP-01-{n:03d}"


_SPEC_FILE = {
    "id": "VP",
    "title": "Vultron Protocol",
    "description": "Marker test requirements.",
    "scope": ["prototype"],
    "tags": ["protocol"],
    "groups": [
        {
            "id": "VP-01",
            "title": "Markers",
            "specs": [
                {
                    "id": _req(n),
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": f"A participant MUST do thing {n}.",
                    "rationale": "A test requirement.",
                }
                for n in range(1, 6)
            ],
        }
    ],
}

#: 1 verified; 2 xfail-only, citing #11 and #12; 3 partly met, citing #13;
#: 4 untested; 5 xfail-only under a skip citing no issue.
_TESTS = f"""\
import pytest


@pytest.mark.spec("{_req(1)}")
def test_one():
    pass


@pytest.mark.spec("{_req(2)}")
@pytest.mark.xfail(strict=True, reason="{_req(2)}: needs #12 and #11.")
def test_two():
    pass


@pytest.mark.spec("{_req(3)}")
def test_three():
    pass


@pytest.mark.spec("{_req(3)}")
@pytest.mark.xfail(strict=True, reason="{_req(3)}: one edge. Tracked by #13.")
def test_three_edge():
    pass


@pytest.mark.spec("{_req(5)}")
@pytest.mark.skip(reason="no harness yet")
def test_five():
    pass
"""

_PAGES = (CatalogPage("vp", "Vultron Protocol", SpecKind.PROTOCOL, ("VP",)),)
_PAGE = "reference/vultron-spec/considerations.md"


def _checkout(root: Path, tests: str = _TESTS) -> Path:
    (root / "specs").mkdir()
    (root / "specs" / "vultron-protocol-spec.yaml").write_text(
        yaml.safe_dump(_SPEC_FILE, sort_keys=False), encoding="utf-8"
    )
    (root / "test").mkdir()
    (root / "test" / "test_markers.py").write_text(tests, encoding="utf-8")
    return root


def _rows(markdown: str) -> dict[str, str]:
    """Each requirement's table row in *markdown*, by ID."""
    rows = {}
    for line in markdown.splitlines():
        cells = line.strip().split(" | ")
        for n in range(1, 6):
            if _req(n) in cells[0]:
                rows[_req(n)] = line
    return rows


def _without_the_hold_on_two() -> str:
    """:data:`_TESTS` with requirement 2's ``xfail`` removed, so it runs."""
    hold = (
        f'@pytest.mark.xfail(strict=True, reason="{_req(2)}: '
        'needs #12 and #11.")\n'
    )
    assert hold in _TESTS
    return _TESTS.replace(hold, "")


def _link(number: int) -> str:
    return f"[#{number}]({ISSUE_URL.format(number=number)})"


def _all_ids() -> list[str]:
    return [_req(n) for n in range(1, 6)]


@pytest.fixture
def checkout(tmp_path):
    return _checkout(tmp_path)


@pytest.fixture
def repo(checkout, monkeypatch):
    """*checkout* as the repository the docs pages render, with empty caches."""
    monkeypatch.setattr(docs_pages, "repo_root", lambda: checkout)
    monkeypatch.setattr(docs_pages, "_registry_cache", {})
    monkeypatch.setattr(docs_pages, "_not_yet_implemented_cache", {})
    return checkout


@pytest.mark.spec("DF-12-021")
class TestNotYetImplementedMarker:
    def _catalog(self, root: Path) -> dict[str, str]:
        registry = load_registry(root / "specs")
        coverage = compute_implementer_coverage(registry, root / "test")
        return _rows(
            render_catalog_page(
                "vp", registry, page=_PAGE, pages=_PAGES, coverage=coverage
            )
        )

    def _callout(self, root: Path) -> dict[str, str]:
        registry = load_registry(root / "specs")
        coverage = compute_implementer_coverage(registry, root / "test")
        return _rows(
            requirement_callout(
                *_all_ids(),
                registry=registry,
                page=_PAGE,
                pages=_PAGES,
                coverage=coverage,
            )
        )

    @pytest.mark.parametrize("render", ["_catalog", "_callout"])
    def test_only_xfail_only_rows_carry_the_marker(self, checkout, render):
        rows = getattr(self, render)(checkout)
        assert sorted(rows) == _all_ids()
        marked = sorted(
            spec_id
            for spec_id, row in rows.items()
            if NOT_YET_IMPLEMENTED_LABEL in row
        )
        # Verified (1), partly met (3) and untested (4) carry none.
        assert marked == [_req(2), _req(5)]

    @pytest.mark.parametrize("render", ["_catalog", "_callout"])
    def test_marker_links_each_cited_issue(self, checkout, render):
        rows = getattr(self, render)(checkout)
        assert (
            f"**{NOT_YET_IMPLEMENTED_LABEL}** "
            f"(tracked by {_link(11)} and {_link(12)})<br><br>"
            f"A participant MUST do thing 2." in rows[_req(2)]
        )
        # A hold citing no issue gets the label alone, and the partly-met
        # requirement's issue is shown nowhere on its row.
        assert f"**{NOT_YET_IMPLEMENTED_LABEL}**<br><br>" in rows[_req(5)]
        assert "#13" not in rows[_req(3)]

    def test_statement_keeps_its_keyword(self, checkout):
        row = self._catalog(checkout)[_req(2)]
        assert "| :material-check-all: **MUST** |" in row
        assert "A participant MUST do thing 2." in row

    def test_marker_leaves_the_row_once_a_marked_test_runs(self, checkout):
        (checkout / "test" / "test_markers.py").write_text(
            _without_the_hold_on_two(), encoding="utf-8"
        )
        assert (
            NOT_YET_IMPLEMENTED_LABEL not in self._catalog(checkout)[_req(2)]
        )

    def test_a_registry_without_coverage_gets_no_marker(self, checkout):
        md = render_catalog_page(
            "vp", load_registry(checkout / "specs"), page=_PAGE, pages=_PAGES
        )
        assert NOT_YET_IMPLEMENTED_LABEL not in md

    def test_per_kind_pages_carry_no_marker(self, checkout):
        """Only the two catalog tiers have coverage states (SR-05-017)."""
        data = yaml.safe_load(
            (checkout / "specs" / "vultron-protocol-spec.yaml").read_text()
        )
        for spec in data["groups"][0]["specs"]:
            spec["kind"] = "process"
        (checkout / "specs" / "vultron-protocol-spec.yaml").write_text(
            yaml.safe_dump(data), encoding="utf-8"
        )
        md = render_for_kind("process", load_registry(checkout / "specs"))
        assert NOT_YET_IMPLEMENTED_LABEL not in md


@pytest.mark.spec("DF-12-021")
class TestRepositoryDefault:
    """The docs pages pass no registry, and read the markers from the
    repository's ``specs/`` and ``test/`` trees."""

    def test_catalog_and_callout_read_the_repository_tests(self, repo):
        catalog = _rows(render_catalog_page("vp", page=_PAGE, pages=_PAGES))
        callout = _rows(
            requirement_callout(_req(2), _req(3), page=_PAGE, pages=_PAGES)
        )
        assert NOT_YET_IMPLEMENTED_LABEL in catalog[_req(2)]
        assert NOT_YET_IMPLEMENTED_LABEL not in catalog[_req(3)]
        assert NOT_YET_IMPLEMENTED_LABEL in callout[_req(2)]
        assert NOT_YET_IMPLEMENTED_LABEL not in callout[_req(3)]

    def test_an_edited_test_drops_the_marker_on_the_next_render(self, repo):
        assert NOT_YET_IMPLEMENTED_LABEL in requirement_callout(
            _req(2), page=_PAGE, pages=_PAGES
        )
        path = repo / "test" / "test_markers.py"
        path.write_text(_without_the_hold_on_two(), encoding="utf-8")
        # The cache keys on modification times; move this one on, so a
        # filesystem with a coarse clock still sees the edit.
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
        assert NOT_YET_IMPLEMENTED_LABEL not in requirement_callout(
            _req(2), page=_PAGE, pages=_PAGES
        )

    def test_a_checkout_without_tests_fails_the_build(self, repo):
        (repo / "test" / "test_markers.py").unlink()
        (repo / "test").rmdir()
        with pytest.raises(FileNotFoundError, match="DF-12-021"):
            requirement_callout(_req(2), page=_PAGE, pages=_PAGES)
