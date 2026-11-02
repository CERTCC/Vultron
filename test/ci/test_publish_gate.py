"""CI verification test — the scheduled publish from tags (DOCBW-06, ADR-0169).

The decisions are functions in ``.github/scripts/publish_gate.py``, tested here
without GitHub; the skip rule and the tagging run against real tags in a
scratch repository. The workflow that wires them together,
``deploy_site.yml``, is pinned here too: its triggers, its blocking list, the
order of its jobs and steps, its concurrency group and its report.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from test.ci._fake_gh import install_fake_gh
from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    index_of,
    load_workflow,
    triggers,
)

_SCRIPT = REPO_ROOT / ".github" / "scripts" / "publish_gate.py"
_WORKFLOW = WORKFLOWS_DIR / "deploy_site.yml"
_MAIN_CI = {
    "python-app.yml",
    "demo-integration.yml",
    "spec-check.yml",
    "ui.yml",
    "lint_md_all.yml",
    "actions-lint.yml",
}
DAY = "2026-11-02"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("publish_gate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look their module up in sys.modules while being defined.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_gate = _load_script()
Trigger = _gate.Trigger
BLOCKING = [
    _gate.BlockingWorkflow(
        ".github/workflows/python-app.yml", "ci:workflow-python-app"
    ),
    _gate.BlockingWorkflow(".github/workflows/ui.yml", "ci:workflow-ui"),
]


def _ctx(trigger: Any, source_tag: str = "") -> Any:
    return _gate.RunContext(
        trigger=trigger, sha="abc123", actor="octocat", source_tag=source_tag
    )


def _bot_tag(name: str = f"publish-{DAY}.1") -> Any:
    return _gate.PublishTag(name, True, _gate.BOT_NAME, _gate.BOT_EMAIL)


class _Calls:
    """Fake I/O for ``decide``: canned answers, and a count of each read."""

    def __init__(
        self,
        *,
        tags: list[Any] | None = None,
        issues: list[list[tuple[int, str]]] | None = None,
        pending: list[str] | None = None,
    ) -> None:
        self.tags = tags or []
        self.issues = issues or [[]]
        self.pending = pending or []
        self.issue_reads = 0
        self.waits = 0

    def tags_on_commit(self) -> list[Any]:
        return self.tags

    def open_blocking_issues(self) -> list[tuple[int, str]]:
        answer = self.issues[min(self.issue_reads, len(self.issues) - 1)]
        self.issue_reads += 1
        return answer

    def still_pending(self) -> list[str]:
        self.waits += 1
        return self.pending

    def decide(self, ctx: Any) -> Any:
        return _gate.decide(
            ctx,
            tags_on_commit=self.tags_on_commit,
            open_blocking_issues=self.open_blocking_issues,
            still_pending=self.still_pending,
        )


# --- classifying a run ---------------------------------------------------------


@pytest.mark.spec("DOCBW-06-007", "DOCBW-06-018", "DOCBW-06-020")
@pytest.mark.parametrize(
    ("event", "ref", "skip", "expected"),
    [
        ("schedule", "refs/heads/main", False, "scheduled"),
        # The input exists only on a manual run; a schedule never skips.
        ("schedule", "refs/heads/main", True, "scheduled"),
        ("workflow_dispatch", "refs/heads/main", False, "manual"),
        ("workflow_dispatch", "refs/heads/main", True, "manual-ungated"),
        ("workflow_dispatch", f"refs/tags/publish-{DAY}.1", False, "rollback"),
        ("workflow_dispatch", "refs/tags/v2026.10.0", True, "rollback"),
    ],
)
def test_classify_trigger(
    event: str, ref: str, skip: bool, expected: str
) -> None:
    assert _gate.classify_trigger(event, ref, skip) == expected


@pytest.mark.parametrize(
    ("event", "ref"),
    [
        ("push", "refs/heads/main"),
        ("push", "refs/heads/publish"),
        ("workflow_dispatch", "refs/heads/feature"),
        ("workflow_dispatch", "refs/tags/snapshot-2026Q4"),
        # A branch named like a tag is still a branch.
        ("workflow_dispatch", "refs/heads/publish-2026-11-02.1"),
    ],
)
def test_an_unsupported_run_is_refused(event: str, ref: str) -> None:
    with pytest.raises(_gate.UnsupportedRunError):
        _gate.classify_trigger(event, ref, False)


# --- the CI gate ---------------------------------------------------------------


@pytest.mark.spec("DOCBW-06-008")
def test_an_open_blocking_issue_blocks() -> None:
    calls = _Calls(issues=[[(41, "ci:workflow-python-app")]])
    decision = calls.decide(_ctx(Trigger.SCHEDULED))
    assert not decision.publish
    assert "blocked by #41 (ci:workflow-python-app)" in decision.reason
    # Already red: no point waiting for runs.
    assert calls.waits == 0


@pytest.mark.spec("DOCBW-06-008")
def test_a_non_blocking_issue_does_not_block() -> None:
    issues = [
        {
            "number": 7,
            "labels": ["ci:main-failure", "ci:workflow-adr-status-drift"],
        },
        # A workflow label without ci:main-failure is not a failure issue.
        {"number": 8, "labels": ["ci:workflow-python-app"]},
        # The list-issues endpoint also returns pull requests.
        {
            "number": 9,
            "labels": ["ci:main-failure", "ci:workflow-python-app"],
            "pull_request": {"url": "x"},
        },
    ]
    assert _gate.blocking_issues(issues, BLOCKING) == []


def test_blocking_issues_reads_both_label_shapes() -> None:
    issues = [
        {
            "number": 3,
            "labels": [
                {"name": "ci:main-failure"},
                {"name": "ci:workflow-ui"},
            ],
        },
        {"number": 2, "labels": ["ci:main-failure", "ci:workflow-python-app"]},
    ]
    assert _gate.blocking_issues(issues, BLOCKING) == [
        (2, "ci:workflow-python-app"),
        (3, "ci:workflow-ui"),
    ]


@pytest.mark.spec("DOCBW-06-010")
def test_unfinished_runs_are_waited_for_then_skip() -> None:
    calls = _Calls(pending=["Python application"])
    decision = calls.decide(_ctx(Trigger.MANUAL))
    assert not decision.publish
    assert calls.waits == 1
    assert "Python application" in decision.reason


@pytest.mark.spec("DOCBW-06-010")
def test_issues_are_read_again_after_the_wait() -> None:
    """A run that finishes red during the wait files its issue then."""
    calls = _Calls(issues=[[], [(52, "ci:workflow-ui")]])
    decision = calls.decide(_ctx(Trigger.SCHEDULED))
    assert not decision.publish
    assert "#52" in decision.reason
    assert calls.issue_reads == 2


def test_green_main_publishes() -> None:
    calls = _Calls()
    decision = calls.decide(_ctx(Trigger.SCHEDULED))
    assert decision.publish
    assert calls.issue_reads == 2 and calls.waits == 1


@pytest.mark.spec("DOCBW-06-010")
def test_pending_runs_waits_only_for_blocking_workflows() -> None:
    runs = [
        {
            "id": 1,
            "name": "Python application",
            "path": ".github/workflows/python-app.yml",
            "status": "in_progress",
        },
        {
            "id": 2,
            "name": "UI",
            "path": ".github/workflows/ui.yml@refs/heads/main",
            "status": "queued",
        },
        {
            "id": 3,
            "name": "ADR Status Drift",
            "path": ".github/workflows/adr-status-drift.yml",
            "status": "in_progress",
        },
        {
            "id": 4,
            "name": "Python application",
            "path": ".github/workflows/python-app.yml",
            "status": "completed",
        },
        # This run itself.
        {
            "id": 99,
            "name": "UI",
            "path": ".github/workflows/ui.yml",
            "status": "in_progress",
        },
    ]
    assert _gate.pending_runs(runs, BLOCKING, 99) == [
        "Python application",
        "UI",
    ]


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.mark.spec("DOCBW-06-010")
def test_wait_for_runs_gives_up_after_the_wait() -> None:
    clock = _FakeClock()
    left = _gate.wait_for_runs(
        lambda: ["Demo Integration"], clock=clock, sleep=clock.sleep
    )
    assert left == ["Demo Integration"]
    assert clock.now == _gate.WAIT_SECONDS
    assert max(clock.slept) <= _gate.POLL_SECONDS


@pytest.mark.spec("DOCBW-06-010")
def test_wait_for_runs_stops_when_the_runs_finish() -> None:
    clock = _FakeClock()
    answers: Iterator[list[str]] = iter([["UI"], ["UI"], []])
    left = _gate.wait_for_runs(
        lambda: next(answers), clock=clock, sleep=clock.sleep
    )
    assert left == []
    assert clock.now == 2 * _gate.POLL_SECONDS


# --- the skip rule, against real tags ------------------------------------------


@pytest.fixture
def git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's git config (signing, identity) out of the tests."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(
    repo: Path,
    *args: str,
    name: str = "Some Person",
    email: str = "p@example.org",
) -> str:
    return subprocess.run(
        ["git", "-c", f"user.name={name}", "-c", f"user.email={email}", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(
    tmp_path: Path, git_env: None, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """A clone of a bare ``origin``, with one commit, as the current directory."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(
        ["git", "clone", "-q", str(origin), str(work)],
        check=True,
        capture_output=True,
    )
    _git(work, "commit", "--allow-empty", "-q", "-m", "first")
    _git(work, "push", "-q", "origin", "HEAD")
    monkeypatch.chdir(work)
    return work


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def _tag_as_bot(repo: Path, name: str) -> None:
    _git(
        repo,
        "tag",
        "-a",
        name,
        "-m",
        "scheduled publish.",
        name=_gate.BOT_NAME,
        email=_gate.BOT_EMAIL,
    )


@pytest.mark.spec("DOCBW-06-013")
def test_a_bot_tag_skips_a_scheduled_run(repo: Path) -> None:
    _tag_as_bot(repo, f"publish-{DAY}.1")
    calls = _Calls(tags=_gate.publish_tags_on(_head(repo)))
    decision = calls.decide(_ctx(Trigger.SCHEDULED))
    assert not decision.publish
    assert f"`publish-{DAY}.1`" in decision.reason
    assert calls.issue_reads == 0


@pytest.mark.spec("DOCBW-06-013")
def test_a_bot_tag_does_not_skip_a_manual_run(repo: Path) -> None:
    _tag_as_bot(repo, f"publish-{DAY}.1")
    calls = _Calls(tags=_gate.publish_tags_on(_head(repo)))
    decision = calls.decide(_ctx(Trigger.MANUAL))
    assert decision.publish
    assert any("already published" in note for note in decision.notes)


@pytest.mark.spec("DOCBW-06-014", "DOCBW-06-015")
def test_a_foreign_tag_is_ignored(repo: Path) -> None:
    """A human-made annotated tag and a lightweight tag neither one skips."""
    _git(repo, "tag", "-a", f"publish-{DAY}.1", "-m", "by hand")
    _git(repo, "tag", f"publish-{DAY}.2")
    # A tag that only claims the bot's name, with someone else's address.
    _git(repo, "tag", "-a", f"publish-{DAY}.3", "-m", "x", name=_gate.BOT_NAME)
    tags = _gate.publish_tags_on(_head(repo))
    assert {t.name: t.annotated for t in tags} == {
        f"publish-{DAY}.1": True,
        f"publish-{DAY}.2": False,
        f"publish-{DAY}.3": True,
    }
    decision = _Calls(tags=tags).decide(_ctx(Trigger.SCHEDULED))
    assert decision.publish
    notes = "\n".join(decision.notes)
    assert f"Ignored `publish-{DAY}.1`: tagged by Some Person" in notes
    assert f"Ignored `publish-{DAY}.2`: a lightweight tag" in notes
    assert f"Ignored `publish-{DAY}.3`" in notes


def test_publish_tags_on_reads_only_publish_tags_on_the_commit(
    repo: Path,
) -> None:
    _tag_as_bot(repo, "v2026.10.0")
    _tag_as_bot(repo, f"publish-{DAY}.1")
    first = _head(repo)
    _git(repo, "commit", "--allow-empty", "-q", "-m", "second")
    assert [t.name for t in _gate.publish_tags_on(first)] == [
        f"publish-{DAY}.1"
    ]
    assert _gate.publish_tags_on(_head(repo)) == []


# --- manual publish and rollback ------------------------------------------------


@pytest.mark.spec("DOCBW-06-018")
def test_a_manual_ungated_run_skips_the_gate() -> None:
    calls = _Calls(issues=[[(41, "ci:workflow-python-app")]], pending=["UI"])
    decision = calls.decide(_ctx(Trigger.MANUAL_UNGATED))
    assert decision.publish
    assert calls.issue_reads == 0 and calls.waits == 0


@pytest.mark.spec("DOCBW-06-020")
def test_a_rollback_skips_the_gate() -> None:
    calls = _Calls(
        tags=[_bot_tag()],
        issues=[[(41, "ci:workflow-python-app")]],
        pending=["UI"],
    )
    decision = calls.decide(_ctx(Trigger.ROLLBACK, f"publish-{DAY}.1"))
    assert decision.publish
    assert calls.issue_reads == 0 and calls.waits == 0


@pytest.mark.spec("DOCBW-06-020", "DOCBW-06-013")
def test_a_rolled_back_commit_is_not_republished(repo: Path) -> None:
    """Main's tip X was published, then the site rolled back to W.

    The next scheduled run still finds the tip X tagged by the workflow, so it
    does not undo the rollback.
    """
    _tag_as_bot(repo, f"publish-{DAY}.1")  # W
    _git(repo, "commit", "--allow-empty", "-q", "-m", "X")
    _tag_as_bot(repo, f"publish-{DAY}.2")  # X, the tip
    _git(
        repo,
        "tag",
        "-a",
        f"publish-{DAY}.3",
        f"publish-{DAY}.1^{{}}",
        "-m",
        "rollback",
        name=_gate.BOT_NAME,
        email=_gate.BOT_EMAIL,
    )
    decision = _Calls(tags=_gate.publish_tags_on(_head(repo))).decide(
        _ctx(Trigger.SCHEDULED)
    )
    assert not decision.publish


@pytest.mark.spec("DOCBW-06-017", "DOCBW-06-020")
@pytest.mark.parametrize(
    ("trigger", "first_line"),
    [
        (Trigger.SCHEDULED, "scheduled publish, by github-actions[bot]."),
        (Trigger.MANUAL, "manual publish, by @octocat."),
        (
            Trigger.MANUAL_UNGATED,
            "manual publish with the CI gate skipped, by @octocat.",
        ),
        (Trigger.ROLLBACK, f"rollback to publish-{DAY}.1, by @octocat."),
    ],
)
def test_tag_message_records_trigger_and_actor(
    trigger: Any, first_line: str
) -> None:
    message = _gate.tag_message(
        _ctx(trigger, f"publish-{DAY}.1"), "https://run/1"
    )
    assert message.splitlines()[0] == first_line
    assert "Commit: abc123" in message and "Run: https://run/1" in message


# --- tagging -----------------------------------------------------------------------


@pytest.mark.spec("DOCBW-06-016")
@pytest.mark.parametrize(
    ("existing", "expected"),
    [
        ([], f"publish-{DAY}.1"),
        ([f"publish-{DAY}.1", f"publish-{DAY}.2"], f"publish-{DAY}.3"),
        # Numbers compare as numbers, not text.
        ([f"publish-{DAY}.9", f"publish-{DAY}.10"], f"publish-{DAY}.11"),
        # Another day's tags and malformed names do not count.
        (
            ["publish-2026-10-30.4", f"publish-{DAY}", f"publish-{DAY}.x"],
            f"publish-{DAY}.1",
        ),
    ],
)
def test_next_tag_name(existing: list[str], expected: str) -> None:
    assert _gate.next_tag_name(DAY, existing) == expected


def _remote_tags(repo: Path) -> dict[str, str]:
    out = _git(repo, "ls-remote", "--tags", "origin")
    return {
        ref.removeprefix("refs/tags/"): oid
        for oid, ref in (line.split("\t") for line in out.splitlines())
        if not ref.endswith("^{}")
    }


@pytest.mark.spec("DOCBW-06-016", "DOCBW-06-017")
def test_create_tag_pushes_one_annotated_tag(repo: Path) -> None:
    sha = _head(repo)
    name = _gate.create_tag(sha, "scheduled publish.\n", today=DAY)
    assert name == f"publish-{DAY}.1"
    assert list(_remote_tags(repo)) == [name]
    tag = _gate.publish_tags_on(sha)
    assert len(tag) == 1 and tag[0].made_by_workflow
    assert (
        _git(repo, "tag", "-l", "--format=%(contents)", name)
        == "scheduled publish."
    )


@pytest.mark.spec("DOCBW-06-016", "DOCBW-06-022")
def test_create_tag_renumbers_past_a_taken_name(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hand-made tag of the same name lands between numbering and push.

    The push is refused, the tag renumbered and pushed again, and the
    hand-made tag on the remote is left exactly as it was.
    """
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)],
        check=True,
        capture_output=True,
    )
    _git(other, "tag", "-a", f"publish-{DAY}.1", "-m", "by hand")
    _git(other, "push", "-q", "origin", f"publish-{DAY}.1")
    before = _remote_tags(repo)[f"publish-{DAY}.1"]
    real = _gate._remote_tag_names
    reads: list[int] = []

    def stale_then_real() -> list[str]:
        # The first read predates the hand-made tag; later reads see it.
        reads.append(1)
        return [] if len(reads) == 1 else real()

    monkeypatch.setattr(_gate, "_remote_tag_names", stale_then_real)
    name = _gate.create_tag(_head(repo), "manual publish.\n", today=DAY)
    assert name == f"publish-{DAY}.2"
    remote = _remote_tags(repo)
    assert remote[f"publish-{DAY}.1"] == before
    assert set(remote) == {f"publish-{DAY}.1", f"publish-{DAY}.2"}


def test_create_tag_fails_after_its_attempts(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(repo, "remote", "set-url", "origin", str(repo.parent / "missing.git"))
    monkeypatch.setattr(_gate, "_remote_tag_names", lambda: [])
    with pytest.raises(subprocess.CalledProcessError):
        _gate.create_tag(_head(repo), "x\n", today=DAY)


# --- the gate command ---------------------------------------------------------------


@pytest.mark.spec("DOCBW-06-011")
def test_gate_command_writes_its_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out, summary = tmp_path / "out", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("BLOCKING_WORKFLOWS", _blocking_env())
    monkeypatch.setattr(_gate, "publish_tags_on", lambda sha: [])
    monkeypatch.setattr(
        _gate,
        "list_failure_issues",
        lambda repo: [
            {"number": 41, "labels": ["ci:main-failure", "ci:workflow-ui"]}
        ],
    )
    monkeypatch.setattr(_gate, "list_runs", lambda repo, sha: [])
    code = _gate.main(
        [
            "gate",
            "--repo",
            "O/R",
            "--sha",
            "abc123",
            "--event",
            "schedule",
            "--ref",
            "refs/heads/main",
            "--actor",
            "octocat",
            "--run-id",
            "5",
        ]
    )
    assert code == 0
    assert "Skipped" in summary.read_text()
    assert "blocked by #41 (ci:workflow-ui)" in summary.read_text()
    outputs = out.read_text()
    assert "publish=false\n" in outputs and "trigger=scheduled\n" in outputs
    assert "scheduled publish, by github-actions[bot]." in outputs


def test_gate_command_refuses_an_unsupported_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLOCKING_WORKFLOWS", _blocking_env())
    code = _gate.main(
        [
            "gate",
            "--repo",
            "O/R",
            "--sha",
            "a",
            "--event",
            "workflow_dispatch",
            "--ref",
            "refs/heads/feature",
            "--actor",
            "o",
            "--run-id",
            "5",
        ]
    )
    assert code == 1


@pytest.mark.parametrize(
    "text", ["", "# only a comment\n", "path-without-label\n"]
)
def test_parse_blocking_refuses_an_empty_or_malformed_list(text: str) -> None:
    with pytest.raises(ValueError):
        _gate.parse_blocking(text)


# --- the workflow -----------------------------------------------------------------


def _workflow() -> dict[str, Any]:
    return load_workflow(_WORKFLOW)


def _blocking_env() -> str:
    return str(_workflow()["env"]["BLOCKING_WORKFLOWS"])


def _job_steps(job: str) -> list[dict[str, Any]]:
    return list(_workflow()["jobs"][job]["steps"])


@pytest.mark.spec("DOCBW-06-007")
def test_publication_workflow_triggers() -> None:
    on = triggers(_workflow())
    assert set(on) == {"schedule", "workflow_dispatch"}
    assert on["schedule"] == [{"cron": "7 6 * * 1-5"}]


@pytest.mark.spec("DOCBW-06-018")
def test_skip_ci_gate_input_defaults_off() -> None:
    inputs = triggers(_workflow())["workflow_dispatch"]["inputs"]
    assert inputs["skip-ci-gate"]["type"] == "boolean"
    assert inputs["skip-ci-gate"]["default"] is False


@pytest.mark.spec("DOCBW-06-009")
def test_blocking_list_names_the_main_ci_workflows() -> None:
    """Each entry is a real workflow, under the label its notify step files."""
    blocking = _gate.parse_blocking(_blocking_env())
    assert {Path(w.path).name for w in blocking} == _MAIN_CI
    for entry in blocking:
        workflow = REPO_ROOT / entry.path
        assert workflow.is_file(), f"{entry.path} does not exist."
        labels = set(
            re.findall(r"workflow-label:\s*(\S+)", workflow.read_text())
        )
        assert labels == {entry.label}, (
            f"{entry.path} files its failures under {labels}, but the blocking "
            f"list expects {entry.label}."
        )


@pytest.mark.spec("DOCBW-06-023")
def test_blocking_list_omits_the_publication_workflow() -> None:
    blocking = _gate.parse_blocking(_blocking_env())
    assert _WORKFLOW.name not in {Path(w.path).name for w in blocking}
    assert "ci:workflow-deploy-site" not in {w.label for w in blocking}


@pytest.mark.spec("DOCBW-06-012")
def test_deploy_runs_only_on_the_gate_verdict() -> None:
    jobs = _workflow()["jobs"]
    gate_run = " ".join(str(s.get("run", "")) for s in jobs["gate"]["steps"])
    assert "publish_gate.py gate" in gate_run
    assert "github.sha" in str(jobs["gate"]["steps"][-1]["env"]["SHA"])
    deploy = jobs["deploy"]
    assert deploy["needs"] == "gate"
    assert deploy["if"] == "needs.gate.outputs.publish == 'true'"
    # Both checkouts take the run's commit: neither names another ref.
    for step in deploy["steps"]:
        assert "ref" not in step.get("with", {}), step


@pytest.mark.spec("DOCBW-06-016", "DOCBW-06-002")
def test_the_tag_step_follows_the_deploy() -> None:
    steps = _job_steps("deploy")
    build = index_of(steps, "./.github/actions/build-site", "uses")
    check = index_of(steps, "./.github/actions/check-site-publication", "uses")
    upload = index_of(steps, "actions/upload-pages-artifact", "uses")
    deploy = index_of(steps, "actions/deploy-pages", "uses")
    tag = index_of(steps, "publish_gate.py tag", "run")
    assert None not in (build, check, upload, deploy, tag)
    assert build < check < upload < deploy < tag  # type: ignore[operator]
    assert "if" not in steps[tag]  # type: ignore[index]


@pytest.mark.spec("DOCBW-06-021")
def test_one_concurrency_group_never_cancels() -> None:
    wf = _workflow()
    assert wf["concurrency"] == {"group": "pages", "cancel-in-progress": False}
    for name, job in wf["jobs"].items():
        assert "concurrency" not in job, (
            f"job {name} sets its own concurrency."
        )


_TAG_REWRITES = re.compile(
    r"--delete|--force|\s-[df]\b|\"-[df]\"|:refs/tags|\+refs/tags|tag\s+-[a-z]*[df]"
)


@pytest.mark.spec("DOCBW-06-022")
def test_no_step_moves_or_deletes_a_tag() -> None:
    texts = {
        "workflow": "\n".join(
            str(s.get("run", ""))
            for j in _workflow()["jobs"].values()
            for s in j["steps"]
        ),
        "script": _SCRIPT.read_text(),
    }
    for where, text in texts.items():
        found = _TAG_REWRITES.findall(text)
        assert not found, f"The {where} can move or delete a tag: {found}"


@pytest.mark.parametrize(
    "text",
    [
        "git push --delete origin t",
        "git tag -d t",
        "git push origin +refs/tags/t",
        "git tag -f t",
    ],
)
def test_the_tag_rewrite_detector_catches_each_form(text: str) -> None:
    assert _TAG_REWRITES.search(text)


@pytest.mark.spec("DOCBW-06-003", "DOCBW-06-020")
def test_a_rollback_or_skip_does_not_close_a_failure() -> None:
    close = next(
        s
        for s in _job_steps("notify")
        if s.get("with", {}).get("mode") == "close"
    )
    guard = " ".join(str(close["if"]).split())
    assert "needs.deploy.result == 'success'" in guard
    assert "needs.gate.outputs.trigger != 'rollback'" in guard
    notify = next(
        s
        for s in _job_steps("notify")
        if s.get("with", {}).get("mode") == "notify"
    )
    assert notify["with"]["workflow-label"] == "ci:workflow-deploy-site"


# --- GitHub plumbing ---------------------------------------------------------------


def test_list_failure_issues_reads_the_list_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The list endpoint, never search (#5105), through the script's own jq."""
    page = [
        {
            "number": 41,
            "labels": [
                {"name": "ci:main-failure"},
                {"name": "ci:workflow-ui"},
            ],
        },
        {
            "number": 42,
            "labels": [{"name": "ci:main-failure"}],
            "pull_request": {"url": "x"},
        },
    ]
    gh = install_fake_gh(tmp_path, issues_page=page)
    for key, value in gh.env.items():
        monkeypatch.setenv(key, value)
    issues = _gate.list_failure_issues("O/R")
    assert issues == [
        {"number": 41, "labels": ["ci:main-failure", "ci:workflow-ui"]},
        {
            "number": 42,
            "labels": ["ci:main-failure"],
            "pull_request": {"url": "x"},
        },
    ]
    assert _gate.blocking_issues(issues, BLOCKING) == [(41, "ci:workflow-ui")]
    (call,) = gh.calls()
    assert "repos/O/R/issues?labels=ci:main-failure&state=open" in call
    assert "--paginate" in call


def test_list_runs_extracts_each_run(monkeypatch: pytest.MonkeyPatch) -> None:
    page = json.dumps(
        {
            "workflow_runs": [
                {
                    "id": 1,
                    "name": "UI",
                    "path": ".github/workflows/ui.yml",
                    "status": "queued",
                    "extra": 0,
                },
                {
                    "id": 2,
                    "name": "Spec Check",
                    "path": ".github/workflows/spec-check.yml",
                    "status": "completed",
                },
            ]
        }
    )
    seen: list[tuple[str, ...]] = []

    def run_jq(*argv: str) -> str:
        seen.append(argv)
        return subprocess.run(
            ["jq", argv[-1]],
            input=page,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    monkeypatch.setattr(_gate, "_run", run_jq)
    runs = _gate.list_runs("O/R", "abc123")
    assert [r["id"] for r in runs] == [1, 2]
    assert set(runs[0]) == {"id", "name", "path", "status"}
    assert "repos/O/R/actions/runs?head_sha=abc123&per_page=100" in seen[0]


def _failing_then(answers: list[str | None]) -> Callable[..., str]:
    calls = iter(answers)

    def run(*argv: str) -> str:
        answer = next(calls)
        if answer is None:
            raise subprocess.CalledProcessError(1, list(argv))
        return answer

    return run


def test_gh_reads_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _gate, "_run", _failing_then([None, '{"number": 1}\n{"number": 2}\n'])
    )
    monkeypatch.setattr(_gate.time, "sleep", lambda seconds: None)
    assert _gate._gh_lines("repos/O/R/issues", ".[]") == [
        {"number": 1},
        {"number": 2},
    ]


def test_gh_reads_fail_after_their_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An API error fails the gate; it never reads as "no issue open"."""
    monkeypatch.setattr(
        _gate, "_run", _failing_then([None] * _gate.GH_ATTEMPTS)
    )
    monkeypatch.setattr(_gate.time, "sleep", lambda seconds: None)
    with pytest.raises(subprocess.CalledProcessError):
        _gate._gh_lines("repos/O/R/issues", ".[]")


def test_tag_command_writes_the_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    made: list[tuple[str, str]] = []

    def create_tag(sha: str, message: str) -> str:
        made.append((sha, message))
        return f"publish-{DAY}.1"

    monkeypatch.setattr(_gate, "create_tag", create_tag)
    assert _gate.main(["tag", "--sha", "abc123", "--message", "m\n"]) == 0
    assert made == [("abc123", "m\n")]
    assert out.read_text() == f"tag=publish-{DAY}.1\n"
