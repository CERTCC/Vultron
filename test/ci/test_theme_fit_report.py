"""CI verification test — the daily Theme Fit Report workflow (#5331).

The workflow rewrites one standing "Theme fit report" Issue from a fresh
``theme-fit`` run (PAD-14-004). The decisions live as pure functions in
``.github/scripts/publish_theme_fit_report.py`` and are pinned here, with the
``gh`` plumbing run against a recording fake; the workflow is pinned so it
keeps its triggers, its least-privilege token and its failure notification.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    steps,
    triggers,
)
from vultron.metadata.planning.theme_fit import GITHUB_BODY_LIMIT
from vultron.metadata.planning.theme_fit.analyze import analyze
from vultron.metadata.planning.theme_fit.model import OpenIssue
from vultron.metadata.planning.themes import load_theme_catalog

_SCRIPT = REPO_ROOT / ".github" / "scripts" / "publish_theme_fit_report.py"
_WORKFLOW = WORKFLOWS_DIR / "theme-fit-report.yml"
_CALVE_EPICS = REPO_ROOT / ".agents" / "skills" / "calve-epics" / "SKILL.md"
_REPORT = "# Theme fit report\n\n3 open Issues checked; 1 finding(s).\n"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "publish_theme_fit_report", _SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_script = _load_script()


# ---------------------------------------------------------------------------
# Pure decisions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("returncode", "usable"),
    [(0, True), (1, True), (2, False), (3, False), (-9, False)],
)
def test_a_finding_publishes_and_a_failed_run_does_not(
    returncode: int, usable: bool
) -> None:
    """Exit 1 is findings, the report's content; only 2+ is a broken run."""
    assert _script.report_usable(returncode) is usable


def _item(number: int, state: str, **extra: object) -> dict[str, object]:
    return {"number": number, "state": state, **extra}


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        ([], None),
        ([_item(9, "open")], (9, "open")),
        ([_item(9, "open"), _item(4, "open")], (4, "open")),
        # An open report beats an older closed one.
        ([_item(2, "closed"), _item(7, "open")], (7, "open")),
        # With none open, the oldest closed one is reopened, not replaced.
        ([_item(8, "closed"), _item(3, "closed")], (3, "closed")),
        # A pull request carrying the label is not the report.
        ([_item(1, "open", pull_request={})], None),
        (
            [_item(1, "open", pull_request={}), _item(5, "closed")],
            (5, "closed"),
        ),
    ],
)
@pytest.mark.spec("PAD-14-004")
def test_pick_report_issue(
    items: list[dict[str, object]], expected: tuple[int, str] | None
) -> None:
    assert _script.pick_report_issue(items) == expected


def test_a_new_report_starts_on_the_default_theme() -> None:
    prefix = _script.body_prefix(None, None)
    first = prefix.splitlines()[0]
    assert first == (
        f"Theme: {_script.DEFAULT_THEME} — {_script.DEFAULT_OUTCOME}"
    )
    assert "calve-epics" in prefix
    assert "this run" not in prefix


def test_a_person_s_theme_line_survives_the_rewrite() -> None:
    old = (
        "Theme: theme:test-and-ci — a person re-themed this.\n\n"
        "# Theme fit report\nstale text\n"
    )
    prefix = _script.body_prefix(old, "https://example.test/run/1")
    assert prefix.splitlines()[0] == (
        "Theme: theme:test-and-ci — a person re-themed this."
    )
    assert _script.DEFAULT_THEME not in prefix
    assert "stale text" not in prefix
    assert "[this run](https://example.test/run/1)" in prefix


def test_theme_lines_ignores_lookalikes() -> None:
    body = "Theme: theme:a — x\nNot Theme: theme:b — y\n\n  \nTheme:\n"
    assert _script.theme_lines(body) == ["Theme: theme:a — x", "Theme:"]


def test_compose_body_refuses_an_over_limit_body() -> None:
    prefix = _script.body_prefix(None, None)
    assert _script.compose_body(prefix, _REPORT) == prefix + _REPORT
    with pytest.raises(ValueError, match="GitHub takes"):
        _script.compose_body(prefix, "x" * GITHUB_BODY_LIMIT)


def test_the_body_it_writes_passes_theme_fit_as_untriaged() -> None:
    """The report Issue itself breaks no theme rule (PAD-02-028)."""
    body = _script.compose_body(_script.body_prefix(None, None), _REPORT)
    issue = OpenIssue(
        number=42,
        title=_script.TITLE,
        issue_type=None,
        labels=frozenset({_script.LABEL, _script.DEFAULT_THEME}),
        body=body,
    )
    report = analyze([issue], load_theme_catalog())
    assert [f.kind.value for f in report.findings] == []
    assert [u.number for u in report.untriaged] == [42]


# ---------------------------------------------------------------------------
# The gh plumbing, against a recording fake
# ---------------------------------------------------------------------------


class _Gh:
    """Answers the script's ``gh`` calls and records them."""

    def __init__(
        self, candidates: list[dict[str, object]], body: str | None = ""
    ) -> None:
        self.candidates = candidates
        self.body = body
        self.calls: list[tuple[str, ...]] = []
        self.written: str | None = None

    def __call__(self, *args: str) -> str:
        self.calls.append(args)
        if "--body-file" in args:
            path = Path(args[args.index("--body-file") + 1])
            self.written = path.read_text(encoding="utf-8")
        if args[:2] == ("api", "--paginate"):
            return json.dumps([self.candidates])
        if args[0] == "api":
            return json.dumps({"body": self.body})
        if args[:2] == ("issue", "create"):
            return "https://github.com/OWNER/REPO/issues/77\n"
        return ""

    def verbs(self) -> list[tuple[str, str]]:
        return [(c[0], c[1]) for c in self.calls]


@pytest.fixture
def run_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Run ``publish`` with a fake ``gh``, theme-fit and triage helper."""

    def go(
        gh: _Gh, dry_run: bool = False
    ) -> tuple[list[tuple[str, int]], list[int]]:
        theme_fit_calls: list[tuple[str, int]] = []
        triaged: list[int] = []

        def fake_theme_fit(repo: str, max_chars: int) -> str:
            theme_fit_calls.append((repo, max_chars))
            return _REPORT

        monkeypatch.setattr(_script, "_gh", gh)
        monkeypatch.setattr(_script, "run_theme_fit", fake_theme_fit)
        monkeypatch.setattr(
            _script, "_triage", lambda _repo, num: triaged.append(num)
        )
        _script.publish("OWNER/REPO", dry_run, "https://example.test/run/2")
        return theme_fit_calls, triaged

    return go


@pytest.mark.spec("PAD-14-004")
def test_an_open_report_is_rewritten_in_place(run_publish: Any) -> None:
    gh = _Gh([_item(12, "open")], body="Theme: theme:dev-workflow — x\n")
    theme_fit_calls, triaged = run_publish(gh)
    assert ("issue", "create") not in gh.verbs()
    assert ("issue", "reopen") not in gh.verbs()
    assert gh.calls[-1][:5] == ("issue", "edit", "12", "--repo", "OWNER/REPO")
    assert gh.written is not None and gh.written.endswith(_REPORT)
    assert triaged == [12]
    # The report is cut to what is left of the body after the prefix.
    ((_, max_chars),) = theme_fit_calls
    assert max_chars + len(gh.written) - len(_REPORT) == GITHUB_BODY_LIMIT


@pytest.mark.spec("PAD-14-004")
def test_a_closed_report_is_reopened_not_replaced(run_publish: Any) -> None:
    gh = _Gh([_item(5, "closed")])
    _, triaged = run_publish(gh)
    assert ("issue", "create") not in gh.verbs()
    assert ("issue", "reopen", "5", "--repo", "OWNER/REPO") in gh.calls
    assert triaged == [5]


@pytest.mark.spec("PAD-14-004")
def test_the_report_is_created_only_when_none_exists(
    run_publish: Any,
) -> None:
    gh = _Gh([])
    _, triaged = run_publish(gh)
    (create,) = [c for c in gh.calls if c[:2] == ("issue", "create")]
    assert create[create.index("--title") + 1] == _script.TITLE
    assert create[create.index("--label") + 1] == _script.LABEL
    label = next(c for c in gh.calls if c[:2] == ("label", "create"))
    assert "--force" in label
    assert gh.verbs().index(("label", "create")) < gh.verbs().index(
        ("issue", "create")
    )
    assert triaged == [77]


def test_the_lookup_uses_the_list_endpoint_any_state(run_publish: Any) -> None:
    """Not the lagging search index, which once let a duplicate in (#5105)."""
    gh = _Gh([_item(12, "open")])
    run_publish(gh)
    (lookup,) = [c for c in gh.calls if c[:2] == ("api", "--paginate")]
    endpoint = lookup[-1]
    assert endpoint.startswith("repos/OWNER/REPO/issues?")
    assert f"labels={_script.LABEL}" in endpoint
    assert "state=all" in endpoint
    assert not any(
        c[:2] in {("issue", "list"), ("search", "issues")} for c in gh.calls
    )


def test_dry_run_writes_nothing(
    run_publish: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    gh = _Gh([_item(12, "closed")])
    _, triaged = run_publish(gh, dry_run=True)
    assert [c for c in gh.calls if c[0] in {"issue", "label"}] == []
    assert triaged == []
    assert "Would write" in capsys.readouterr().out


def test_a_failed_theme_fit_run_fails_the_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit 2 is a broken run, not an empty report: nothing is written."""

    class _Done:
        returncode = 2
        stdout = ""
        stderr = "theme-fit: gh failed\n"

    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_: object) -> _Done:
        calls.append(argv)
        return _Done()

    monkeypatch.setattr(_script.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="exited 2"):
        _script.run_theme_fit("OWNER/REPO", 1000)
    ((*cmd,),) = calls
    # The workflow's GITHUB_TOKEN cannot read Project #24.
    assert cmd[0] == "theme-fit" and "--no-schedule" in cmd


_WRITES = {("issue", "edit"), ("issue", "reopen"), ("issue", "close")}


@pytest.mark.parametrize(
    ("candidates", "report"),
    [
        ([_item(12, "open"), _item(30, "open")], 12),
        ([_item(5, "closed"), _item(6, "closed")], 5),
        ([], 77),
    ],
)
@pytest.mark.spec("PAD-14-004")
def test_it_writes_to_no_issue_but_the_report(
    run_publish: Any, candidates: list[dict[str, object]], report: int
) -> None:
    """It labels, moves or edits no Issue it reports, nor a second report."""
    gh = _Gh(candidates)
    _, triaged = run_publish(gh)
    touched = {c[2] for c in gh.calls if c[:2] in _WRITES}
    assert touched <= {str(report)}
    assert triaged == [report]
    assert not any(
        "--add-label" in c or "--remove-label" in c for c in gh.calls
    )
    assert not any(
        c[0] == "api" and ("-X" in c or "--method" in c) for c in gh.calls
    )
    created = [c for c in gh.calls if c[:2] == ("issue", "create")]
    assert len(created) == (0 if candidates else 1)


def test_triage_runs_the_helper_with_the_report_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        _script.subprocess,
        "run",
        lambda argv, **_k: calls.append(argv),
    )
    _script._triage("OWNER/REPO", 12)
    assert calls == [
        [
            "bash",
            str(_script.TRIAGE_HELPER),
            "OWNER/REPO",
            "12",
            _script.DEFAULT_THEME,
            _script.DEFAULT_OUTCOME,
        ]
    ]
    assert _script.TRIAGE_HELPER.name == "ensure-issue-triage.sh"
    assert _script.TRIAGE_HELPER.is_file()


def test_candidates_are_joined_across_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [[_item(1, "open")], [_item(2, "closed"), _item(3, "open")]]
    monkeypatch.setattr(_script, "_gh", lambda *_a: json.dumps(pages))
    numbers = [c["number"] for c in _script.report_candidates("OWNER/REPO")]
    assert numbers == [1, 2, 3]


def test_a_failed_gh_call_logs_its_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*_a: object, **_k: object) -> None:
        raise _script.subprocess.CalledProcessError(
            1, ["gh"], stderr="HTTP 502: Bad Gateway\n"
        )

    monkeypatch.setattr(_script.subprocess, "run", fail)
    with pytest.raises(_script.subprocess.CalledProcessError):
        _script._gh("api", "repos/OWNER/REPO/issues/1")
    assert "HTTP 502" in capsys.readouterr().err


def test_findings_still_return_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Done:
        returncode = 1
        stdout = _REPORT
        stderr = ""

    seen: list[list[str]] = []

    def fake_run(argv: list[str], **_: object) -> _Done:
        seen.append(argv)
        return _Done()

    monkeypatch.setattr(_script.subprocess, "run", fake_run)
    assert _script.run_theme_fit("OWNER/REPO", 1000) == _REPORT
    ((*cmd,),) = seen
    assert cmd[cmd.index("--max-chars") + 1] == "1000"
    assert cmd[cmd.index("--repo") + 1] == "OWNER/REPO"


def test_a_report_issue_with_no_body_gets_the_default_theme(
    run_publish: Any,
) -> None:
    gh = _Gh([_item(12, "open")], body=None)
    run_publish(gh)
    assert gh.written is not None
    assert gh.written.startswith(f"Theme: {_script.DEFAULT_THEME} — ")


def test_main_needs_a_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    with pytest.raises(SystemExit) as exc:
        _script.main([])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# The workflow
# ---------------------------------------------------------------------------


def test_workflow_runs_daily_and_on_dispatch() -> None:
    on = triggers(load_workflow(_WORKFLOW))
    assert set(on) == {"schedule", "workflow_dispatch"}
    (cron,) = [entry["cron"] for entry in on["schedule"]]
    minute, hour, *rest = cron.split()
    assert minute.isdigit() and hour.isdigit() and rest == ["*", "*", "*"]


def test_workflow_token_is_least_privilege() -> None:
    wf = load_workflow(_WORKFLOW)
    assert wf["permissions"] == {"contents": "read", "issues": "write"}
    assert "secrets." not in _WORKFLOW.read_text().replace(
        "secrets.GITHUB_TOKEN", ""
    )
    assert "vars." not in _WORKFLOW.read_text()


def test_workflow_runs_the_script_and_notifies() -> None:
    wf_steps = steps(load_workflow(_WORKFLOW))
    assert any(
        ".github/scripts/publish_theme_fit_report.py" in s.get("run", "")
        for s in wf_steps
    )
    notify = {
        s["with"]["mode"]: s["if"]
        for s in wf_steps
        if s.get("uses") == "./.github/actions/notify-failure"
    }
    assert notify == {"notify": "failure()", "close": "success()"}


@pytest.mark.spec("PAD-14-004")
def test_calve_epics_names_the_report_issue_by_its_label() -> None:
    text = _CALVE_EPICS.read_text(encoding="utf-8")
    assert f"`{_script.LABEL}`" in text
    assert _script.TITLE in text
