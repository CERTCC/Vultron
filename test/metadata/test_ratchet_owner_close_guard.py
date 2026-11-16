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
"""A pull request cannot close an issue a ratchet still names as owner (ARCH-18-012).

The guard is a pull-request job that reads the body's closing references and
the ``# owner:`` markers at the merge commit through
``vultron.metadata.ratchet_markers`` (#6408). It runs on every body edit as
well as on a push, since a closing reference can be added without a commit.
The tests below run ``ratchet-close-guard``
(:mod:`vultron.metadata.ratchet_close_guard`) over a scratch ``test/`` tree.
"""

import io
from pathlib import Path

import pytest
import yaml

from vultron.metadata.ratchet_close_guard import closed_issues, main

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github/workflows"
_REPO = "CERTCC/Vultron"

#: A ratchet owned by #101 with one entry left.
_OWNED = "# owner: #101\nKNOWN_GAPS = frozenset({'a'})\n"
#: The same ratchet once its last entry is gone, marker left behind.
_EMPTIED = "# owner: #101\nKNOWN_GAPS = frozenset()\n"
#: A pinned exemption set, which no issue owns.
_PINNED = "# permanent: #101\nKNOWN_PINNED = frozenset({'a'})\n"


def _pull_request_types(workflow: dict[object, object]) -> list[str]:
    """The ``pull_request`` activity types a workflow runs on, if any.

    PyYAML reads a bare ``on:`` key as ``True``.
    """
    triggers = workflow.get("on", workflow.get(True)) or {}
    if not isinstance(triggers, dict) or "pull_request" not in triggers:
        return []
    return list((triggers["pull_request"] or {}).get("types", []))


@pytest.mark.spec("ARCH-18-012")
def test_a_pull_request_job_checks_closed_ratchet_owners() -> None:
    guards = [
        path.name
        for path in sorted(_WORKFLOWS.glob("*.yml"))
        if "ratchet_markers" in path.read_text()
        and "edited" in _pull_request_types(yaml.safe_load(path.read_text()))
    ]
    assert guards, "no pull-request workflow checks ratchet owners on edit"


def _run(
    tmp_path: Path,
    source: str,
    body: str,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    """Run the guard on *body* over a ``test/`` tree holding *source*."""
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_x.py").write_text(source)
    body_file = tmp_path / "body.md"
    body_file.write_text(body)
    code = main(["--body-file", str(body_file), "--repo", _REPO], tmp_path)
    captured = capsys.readouterr()
    return code, captured.out + captured.err


@pytest.mark.spec("ARCH-18-012")
def test_a_closed_owner_still_cited_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _run(tmp_path, _OWNED, "- Closes #101\n", capsys)
    assert code == 1
    assert "closes #101" in out
    assert "`test/test_x.py` `KNOWN_GAPS`" in out


@pytest.mark.spec("ARCH-18-012")
def test_an_owner_whose_ratchet_the_pr_empties_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _run(tmp_path, _EMPTIED, "- Closes #101\n", capsys)
    assert code == 0, out


@pytest.mark.spec("ARCH-18-012")
def test_a_permanent_marker_never_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _run(tmp_path, _PINNED, "- Closes #101\n", capsys)
    assert code == 0, out


@pytest.mark.spec("ARCH-18-012")
def test_a_body_with_no_closing_reference_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _run(tmp_path, _OWNED, "Part of #101; see #101.\n", capsys)
    assert code == 0, out


@pytest.mark.spec("ARCH-18-012")
def test_closing_an_issue_no_ratchet_cites_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _run(tmp_path, _OWNED, "- Closes #202\n", capsys)
    assert code == 0, out
    assert "#202" in out


@pytest.mark.spec("ARCH-18-012")
@pytest.mark.parametrize(
    "keyword",
    [
        "close",
        "closes",
        "closed",
        "fix",
        "fixes",
        "fixed",
        "resolve",
        "resolves",
        "resolved",
        "CLOSES",
        "Fixes",
        "rEsOlVeD",
    ],
)
def test_every_closing_keyword_form_closes(keyword: str) -> None:
    assert closed_issues(f"- {keyword} #101", _REPO) == {101}
    assert closed_issues(f"{keyword}: #101", _REPO) == {101}


@pytest.mark.spec("ARCH-18-012")
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Closes CERTCC/Vultron#101", {101}),
        ("Closes certcc/vultron#101", {101}),
        ("Closes https://github.com/CERTCC/Vultron/issues/101", {101}),
        ("Closes Other/Repo#101", set()),
        ("Closes https://github.com/Other/Repo/issues/101", set()),
        ("Not this: `Closes #101`", set()),
        ("<!-- Closes #101 -->", set()),
        ("```text\nCloses #101\n```", set()),
        ("- Closes #101\n- Fixes #102", {101, 102}),
        ("Closes #0", set()),
        ("Closes HTTPS://GitHub.com/CERTCC/Vultron/issues/101", {101}),
        ("Closes #101abc", set()),
        ("Closes CERTCC/Vultron#101abc", set()),
    ],
)
def test_only_references_github_closes_here_count(
    body: str, expected: set[int]
) -> None:
    assert closed_issues(body, _REPO) == expected


@pytest.mark.spec("ARCH-18-012")
def test_each_closed_owner_is_named_with_every_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = (
        _OWNED
        + "\n# owner: #101, #102\nMAX_HOLES = 3\n"
        + "\n# owner: #102\nKNOWN_OTHER = ['b']\n"
    )
    code, out = _run(
        tmp_path, source, "- Closes #101\n- Closes #102\n", capsys
    )
    assert code == 1
    first, second = [ln for ln in out.splitlines() if "this PR closes" in ln]
    assert (
        "#101" in first and "`KNOWN_GAPS`" in first and "`MAX_HOLES`" in first
    )
    assert "#102" in second and "`MAX_HOLES`" in second
    assert "`KNOWN_OTHER`" in second


def test_an_unreadable_test_file_is_a_setup_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file the scan skipped would leave its owners unchecked."""
    code, out = _run(tmp_path, "def broken(:\n", "- Closes #101\n", capsys)
    assert code == 2
    assert "test/test_x.py" in out


def test_a_missing_body_file_is_a_setup_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--body-file", str(tmp_path / "absent.md")], tmp_path)
    assert code == 2
    assert "could not read the PR body" in capsys.readouterr().err


def test_the_body_can_arrive_on_stdin(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_x.py").write_text(_OWNED)
    monkeypatch.setattr("sys.stdin", io.StringIO("- Closes #101\n"))
    assert main(["--body-file", "-", "--repo", _REPO], tmp_path) == 1
