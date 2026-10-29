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
"""Tests of the closed-owner report for ratchet baselines (ARCH-18-004).

Every lookup goes through a stubbed issue-state client, so no test reaches
GitHub.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import pytest

from vultron.metadata import ratchet_owners
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.ratchet_markers import Baseline
from vultron.metadata.ratchet_owners import (
    baselines_under_test,
    main,
    owner_findings,
    report_markdown,
)

#: What ``gh issue view`` raises for a number that names no issue.
_MISSING = subprocess.CalledProcessError(
    1,
    ["gh", "issue", "view", "9"],
    stderr=(
        "GraphQL: Could not resolve to an issue or pull request with the"
        " number of 9. (repository.issue)\n"
    ),
)
#: What it raises when the token cannot read the repository.
_FORBIDDEN = subprocess.CalledProcessError(
    1, ["gh"], stderr="HTTP 403: Resource not accessible by integration\n"
)


def _baseline(name: str, *owners: int, line: int = 10) -> Baseline:
    return Baseline(
        path=Path("test/architecture/test_x.py"),
        name=name,
        line=line,
        terminal=False,
        owners=owners,
    )


def _client(
    states: dict[str, str | Exception], calls: list[str] | None = None
) -> Callable[[str], str]:
    """A stubbed issue-state lookup answering from *states* by ``#N``."""

    def lookup(ref: str) -> str:
        if calls is not None:
            calls.append(ref)
        answer = states[ref]
        if isinstance(answer, Exception):
            raise answer
        return answer

    return lookup


@pytest.mark.spec("ARCH-18-004")
def test_open_owners_are_not_reported() -> None:
    baselines = [_baseline("KNOWN_A", 1), _baseline("KNOWN_B", 2)]
    client = _client({"#1": "OPEN", "#2": "open"})
    assert owner_findings(baselines, client) == []


@pytest.mark.spec("ARCH-18-004")
def test_closed_owner_lists_every_baseline_citing_it() -> None:
    a, b, c = (
        _baseline("KNOWN_A", 1),
        _baseline("KNOWN_B", 1, 2),
        _baseline("KNOWN_C", 2),
    )
    (finding,) = owner_findings(
        [a, b, c], _client({"#1": "CLOSED", "#2": "OPEN"})
    )
    assert finding.owner == 1
    assert finding.reason == "is CLOSED"
    assert finding.baselines == (a, b)


@pytest.mark.spec("ARCH-18-004")
def test_missing_owner_is_reported_as_not_existing() -> None:
    (finding,) = owner_findings(
        [_baseline("KNOWN_A", 9)], _client({"#9": _MISSING})
    )
    assert finding.reason == "does not exist"


@pytest.mark.spec("ARCH-18-004")
@pytest.mark.parametrize(
    "exc",
    [
        _FORBIDDEN,
        FileNotFoundError("gh"),
        KeyError("state"),
        ValueError("json"),
        TypeError("list indices must be integers"),
    ],
)
def test_unreadable_owner_is_reported_not_passed(exc: Exception) -> None:
    """A lookup that fails has not shown the owner open."""
    (finding,) = owner_findings(
        [_baseline("KNOWN_A", 4)], _client({"#4": exc})
    )
    assert finding.reason.startswith("could not be read (")


def test_unreadable_reason_names_gh_stderr() -> None:
    (finding,) = owner_findings(
        [_baseline("KNOWN_A", 4)], _client({"#4": _FORBIDDEN})
    )
    assert "HTTP 403: Resource not accessible by integration" in finding.reason


def test_a_pull_request_number_is_not_an_open_owner() -> None:
    """``gh issue view`` answers a merged PR's number with ``MERGED``."""
    (finding,) = owner_findings(
        [_baseline("KNOWN_A", 5)], _client({"#5": "MERGED"})
    )
    assert finding.reason == "is MERGED"


def test_each_owner_is_looked_up_once_in_issue_order() -> None:
    calls: list[str] = []
    baselines = [
        _baseline("KNOWN_A", 30, 30),
        _baseline("KNOWN_B", 4),
        _baseline("KNOWN_C", 30),
    ]
    findings = owner_findings(
        baselines, _client({"#4": "CLOSED", "#30": "CLOSED"}, calls)
    )
    assert calls == ["#4", "#30"]
    assert [f.owner for f in findings] == [4, 30]
    assert findings[1].baselines == (baselines[0], baselines[2])


def test_baselines_without_an_owner_need_no_lookup() -> None:
    permanent = Baseline(
        path=Path("test/x.py"),
        name="KNOWN_P",
        line=1,
        terminal=False,
        permanent=("ADR-0001",),
    )
    assert owner_findings([permanent], _client({})) == []


def test_owner_findings_defaults_to_the_gh_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ratchet_owners, "gh_issue_state", lambda ref: "CLOSED")
    (finding,) = owner_findings([_baseline("KNOWN_A", 7)])
    assert finding.reason == "is CLOSED"


@pytest.mark.spec("ARCH-18-004")
def test_report_lists_each_affected_baseline_under_its_owner() -> None:
    findings = owner_findings(
        [_baseline("KNOWN_A", 1, line=12), _baseline("MAX_B", 9, line=40)],
        _client({"#1": "CLOSED", "#9": _MISSING}),
    )
    report = report_markdown(findings)
    assert (
        "- #1 is CLOSED:\n  - `test/architecture/test_x.py:12` `KNOWN_A`"
        in report
    )
    assert (
        "- #9 does not exist:\n  - `test/architecture/test_x.py:40` `MAX_B`"
        in report
    )


def _write_repo(root: Path) -> None:
    (root / "test" / "pkg").mkdir(parents=True)
    (root / "test" / "pkg" / "test_ratchet.py").write_text(
        dedent(
            """\
            # owner: #11
            KNOWN_VIOLATIONS = {"a"}

            KNOWN_EMPTY = set()

            # permanent: ADR-0001
            PINNED_EXEMPTIONS = {"b"}
            """
        ),
        encoding="utf-8",
    )


def test_baselines_under_test_reads_test_relative_to_root(
    tmp_path: Path,
) -> None:
    _write_repo(tmp_path)
    (tmp_path / "vultron").mkdir()
    (tmp_path / "vultron" / "mod.py").write_text(
        "# owner: #3\nKNOWN_X = {1}\n"
    )
    found = {b.name: b for b in baselines_under_test(tmp_path)}
    assert set(found) == {
        "KNOWN_VIOLATIONS",
        "KNOWN_EMPTY",
        "PINNED_EXEMPTIONS",
    }
    assert found["KNOWN_VIOLATIONS"].path == Path("test/pkg/test_ratchet.py")
    assert found["KNOWN_VIOLATIONS"].owners == (11,)


def test_an_unparsable_test_file_fails_the_scan_naming_it(
    tmp_path: Path,
) -> None:
    """A file skipped silently would leave its owners unchecked (MS-17-001)."""
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "broken.py").write_text("X = 1\nKNOWN_X = (\n")
    with pytest.raises(MetadataLoadError) as raised:
        baselines_under_test(tmp_path)
    assert raised.value.path == "test/broken.py"
    assert raised.value.line == 2
    assert str(raised.value).startswith("test/broken.py:2:")


def test_a_test_file_that_is_not_utf8_fails_the_scan_naming_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "latin.py").write_bytes(b"# \xe9\n")
    with pytest.raises(MetadataLoadError) as raised:
        baselines_under_test(tmp_path)
    assert raised.value.path == "test/latin.py"


@pytest.mark.spec("ARCH-18-004")
def test_main_exits_zero_when_every_owner_is_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_repo(tmp_path)
    monkeypatch.setattr(ratchet_owners, "repo_root", lambda: tmp_path)
    report = tmp_path / "report.md"
    assert main(["--report", str(report)], _client({"#11": "OPEN"})) == 0
    assert (
        "All 1 ratchet baseline owner issue(s) are open."
        in capsys.readouterr().out
    )
    assert not report.exists()


@pytest.mark.spec("ARCH-18-004")
def test_main_writes_the_report_and_exits_one_on_a_closed_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_repo(tmp_path)
    monkeypatch.setattr(ratchet_owners, "repo_root", lambda: tmp_path)
    report = tmp_path / "report.md"
    assert main(["--report", str(report)], _client({"#11": "CLOSED"})) == 1
    text = report.read_text(encoding="utf-8")
    assert "`test/pkg/test_ratchet.py:2` `KNOWN_VIOLATIONS`" in text
    assert capsys.readouterr().out == text


def test_main_reports_a_scan_failure_in_the_tracker_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A broken test file is named in the report, not just a failed run."""
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "broken.py").write_text("KNOWN_X = (\n")
    monkeypatch.setattr(ratchet_owners, "repo_root", lambda: tmp_path)
    report = tmp_path / "report.md"
    assert main(["--report", str(report)], _client({})) == 1
    text = report.read_text(encoding="utf-8")
    assert "no owner was checked" in text
    assert "- test/broken.py:1:" in text
    assert capsys.readouterr().out == text
