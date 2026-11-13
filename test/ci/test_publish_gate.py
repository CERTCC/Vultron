"""CI verification test — the scheduled publish from tags (DOCBW-06, ADR-0171).

The decisions are functions in ``.github/scripts/publish_gate.py``, tested here
without GitHub; the skip rule, the rollback target check and the tagging run
against real commits and tags in a scratch repository with a bare ``origin``.
The workflow that wires them together, ``deploy_site.yml``, is pinned here
too: its triggers, its blocking list, the order and permissions of its jobs,
its concurrency group and its report.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from test.ci._fake_gh import install_fake_gh
from test.ci._scratch_git import (
    BOT_EMAIL,
    BOT_NAME,
    commit as _commit,
    git as _git,
    head as _head,
    isolate_git_config,
    scratch_clone,
    tag_as_bot as _tag_as_bot,
)
from test.ci._scripts import SCRIPTS_DIR, load_script
from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    index_of,
    job_needs,
    load_workflow,
    steps,
    triggers,
)
from vultron.metadata.docs.build_version import (
    PUBLISH_DATE_ENV,
    PUBLISH_TAG_ENV,
    RELEASE_TAG_ENV,
    Publish,
    describe_build,
)

_SCRIPT = SCRIPTS_DIR / "publish_gate.py"
_WORKFLOW = WORKFLOWS_DIR / "deploy_site.yml"
_AFTER_RELEASE = WORKFLOWS_DIR / "publish_after_release.yml"
_MAIN_CI = {
    "python-app.yml",
    "demo-integration.yml",
    "spec-check.yml",
    "ui.yml",
    "lint_md_all.yml",
    "actions-lint.yml",
}
DAY = "2026-11-02"
MAIN = "refs/heads/main"
RUN_URL = "https://github.com/O/R/actions/runs/5"
RELEASE = "v2026.11.0"


_gate = load_script("publish_gate")
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
    return _gate.Tag(name, True, BOT_NAME, BOT_EMAIL)


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
    ("event", "skip", "rollback_to", "expected"),
    [
        ("schedule", False, "", "scheduled"),
        # The inputs exist only on a manual run; a schedule ignores them.
        ("schedule", True, f"publish-{DAY}.1", "scheduled"),
        ("workflow_dispatch", False, "", "manual"),
        ("workflow_dispatch", True, "", "manual-ungated"),
        ("workflow_dispatch", False, f"publish-{DAY}.1", "rollback"),
        # A rollback never checks CI, whatever the other input says.
        ("workflow_dispatch", True, "v2026.10.0", "rollback"),
    ],
)
def test_classify_trigger(
    event: str, skip: bool, rollback_to: str, expected: str
) -> None:
    assert _gate.classify_trigger(event, MAIN, skip, rollback_to) == expected


@pytest.mark.spec("DOCBW-06-029")
@pytest.mark.parametrize(
    ("event", "ref", "rollback_to"),
    [
        ("push", MAIN, ""),
        ("push", "refs/heads/publish", ""),
        ("workflow_dispatch", "refs/heads/feature", ""),
        # A run from a tag would execute that tag's copy of the workflow.
        ("workflow_dispatch", f"refs/tags/publish-{DAY}.1", ""),
        ("workflow_dispatch", "refs/tags/v2026.10.0", ""),
        ("workflow_dispatch", "refs/tags/v2026.10.0", "v2026.10.0"),
        # Only a publish or release tag can be a rollback target.
        ("workflow_dispatch", MAIN, "snapshot-2026Q4"),
        ("workflow_dispatch", MAIN, "main"),
        ("workflow_dispatch", MAIN, f"publish-{DAY}"),
        ("workflow_dispatch", MAIN, "vNext"),
    ],
)
def test_an_unsupported_run_is_refused(
    event: str, ref: str, rollback_to: str
) -> None:
    with pytest.raises(_gate.UnsupportedRunError):
        _gate.classify_trigger(event, ref, False, rollback_to)


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


@pytest.mark.spec("DOCBW-06-010", "DOCBW-06-028")
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


def _run(
    run_id: int, path: str, status: str, head: str = "old", name: str = "W"
) -> dict[str, object]:
    return {
        "id": run_id,
        "name": name,
        "path": path,
        "status": status,
        "head_sha": head,
    }


@pytest.mark.spec("DOCBW-06-010")
def test_pending_runs_waits_only_for_blocking_runs_in_history() -> None:
    py, ui = ".github/workflows/python-app.yml", ".github/workflows/ui.yml"
    runs = [
        _run(1, py, "in_progress", name="Python application"),
        _run(2, f"{ui}@refs/heads/main", "queued", name="UI"),
        _run(3, ".github/workflows/adr-status-drift.yml", "in_progress"),
        _run(4, py, "completed"),
        # A run for a later commit cannot judge the candidate's code.
        _run(5, py, "in_progress", head="newer"),
        # This run itself.
        _run(99, ui, "in_progress"),
        # A run with no name is reported by its workflow file.
        _run(6, ui, "waiting", name=""),
    ]
    assert _gate.pending_runs(
        runs, BLOCKING, 99, lambda head: head == "old"
    ) == [".github/workflows/ui.yml", "Python application", "UI"]


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.mark.spec("DOCBW-06-010", "DOCBW-06-028")
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


# --- real repositories --------------------------------------------------------------


@pytest.fixture
def git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_git_config(monkeypatch)


@pytest.fixture
def repo(
    tmp_path: Path, git_env: None, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """A clone of a bare ``origin``, with one commit, as the current directory.

    The commit carries the ``BUILD_ACTIONS``, as every buildable commit does.
    """
    work = scratch_clone(tmp_path)
    for action in _gate.BUILD_ACTIONS:
        (work / action).parent.mkdir(parents=True)
        (work / action).write_text("name: stub\n")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "first")
    _git(work, "push", "-q", "origin", "HEAD")
    monkeypatch.chdir(work)
    return work


@pytest.mark.spec("DOCBW-06-010")
def test_is_in_history(repo: Path) -> None:
    first = _head(repo)
    second = _commit(repo, "second")
    assert _gate.is_in_history(first, second)
    assert _gate.is_in_history(second, second)
    assert not _gate.is_in_history(second, first)
    # A commit this clone has never seen is not in the tip's history.
    assert not _gate.is_in_history("0" * 40, second)
    assert not _gate.is_in_history("", second)


# --- the skip rule -------------------------------------------------------------------


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
    _git(repo, "tag", "-a", f"publish-{DAY}.3", "-m", "x", name=BOT_NAME)
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


@pytest.mark.spec("DOCBW-07-013")
def test_a_bot_tag_with_a_malformed_name_is_ignored(repo: Path) -> None:
    """Only a ``publish-YYYY-MM-DD.N`` name counts, whoever tagged it."""
    _tag_as_bot(repo, "publish-not-a-date")
    decision = _Calls(tags=_gate.publish_tags_on(_head(repo))).decide(
        _ctx(Trigger.SCHEDULED)
    )
    assert decision.publish
    assert decision.notes == [
        "Ignored `publish-not-a-date`: not a publish-YYYY-MM-DD.N name."
    ]


def test_publish_tags_on_reads_only_publish_tags_on_the_commit(
    repo: Path,
) -> None:
    _tag_as_bot(repo, "v2026.10.0")
    _tag_as_bot(repo, f"publish-{DAY}.1")
    first = _head(repo)
    _commit(repo, "second")
    assert [t.name for t in _gate.publish_tags_on(first)] == [
        f"publish-{DAY}.1"
    ]
    assert _gate.publish_tags_on(_head(repo)) == []


# --- a publish after a release ---------------------------------------------------


@pytest.mark.spec("DOCBW-06-032", "DOCBW-06-034")
def test_a_bot_dispatched_release_run_is_a_release_run() -> None:
    trigger = _gate.classify_trigger(
        "workflow_dispatch", MAIN, False, release=RELEASE, actor=BOT_NAME
    )
    assert trigger == Trigger.RELEASE


@pytest.mark.spec("DOCBW-06-029", "DOCBW-06-034")
@pytest.mark.parametrize(
    ("ref", "skip", "rollback_to", "release", "actor", "why"),
    [
        # A person cannot label a publish as a release's.
        (MAIN, False, "", RELEASE, "octocat", "github-actions"),
        # A release run is always a gated publish of main's tip.
        (MAIN, True, "", RELEASE, BOT_NAME, "skip-ci-gate"),
        (MAIN, False, f"publish-{DAY}.1", RELEASE, BOT_NAME, "rollback-to"),
        # Only a version-shaped v* tag names a release.
        (MAIN, False, "", "main", BOT_NAME, "not a v"),
        (MAIN, False, "", "vNext", BOT_NAME, "not a v"),
        # A run from the tag would execute the tag's copy of the workflow.
        (f"refs/tags/{RELEASE}", False, "", RELEASE, BOT_NAME, "from main"),
    ],
    ids=["person", "ungated", "rollback", "branch", "unversioned", "from-tag"],
)
def test_a_release_run_is_refused_unless_the_bot_dispatched_it_alone(
    ref: str, skip: bool, rollback_to: str, release: str, actor: str, why: str
) -> None:
    with pytest.raises(_gate.UnsupportedRunError, match=why):
        _gate.classify_trigger(
            "workflow_dispatch",
            ref,
            skip,
            rollback_to,
            release=release,
            actor=actor,
        )


@pytest.mark.spec("DOCBW-06-034")
@pytest.mark.parametrize(
    ("state", "why"),
    [
        (None, "no published release"),
        # A token that can push sees a draft; a read-only one gets None.
        (_gate.ReleaseState(True, ()), "still a draft"),
    ],
    ids=["missing", "draft"],
)
def test_a_release_run_needs_a_published_release(
    state: object, why: str
) -> None:
    with pytest.raises(_gate.UnsupportedRunError, match=why):
        _gate.require_published_release(RELEASE, lambda name: state)


@pytest.mark.spec("DOCBW-06-034")
def test_a_published_release_passes() -> None:
    asked: list[str] = []

    def state(name: str) -> object:
        asked.append(name)
        return _gate.ReleaseState(False, ("a.tar.gz",))

    _gate.require_published_release(RELEASE, state)
    assert asked == [RELEASE]


@pytest.mark.spec("DOCBW-06-033", "DOCBW-06-035")
def test_a_release_run_keeps_the_ci_gate_and_ignores_the_skip_rule() -> None:
    """The release often lands on a commit already published that morning."""
    blocked = _Calls(tags=[_bot_tag()], issues=[[(41, "ci:workflow-ui")]])
    decision = blocked.decide(_ctx(Trigger.RELEASE, RELEASE))
    assert not decision.publish
    assert "blocked by #41 (ci:workflow-ui)" in decision.reason
    green = _Calls(tags=[_bot_tag()])
    decision = green.decide(_ctx(Trigger.RELEASE, RELEASE))
    assert decision.publish
    assert green.issue_reads == 2 and green.waits == 1
    assert any(f"publish-{DAY}.1" in note for note in decision.notes)


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


@pytest.mark.spec("DOCBW-06-026")
def test_a_rollback_target_must_be_on_main(repo: Path) -> None:
    """Only a commit in main's history is redeployed: any account that can
    push can create a tag, on any commit."""
    old = _head(repo)
    _tag_as_bot(repo, f"publish-{DAY}.1")
    tip = _commit(repo, "tip")
    _git(repo, "checkout", "-q", "-b", "unreviewed", old)
    stray = _commit(repo, "never merged")
    _git(repo, "tag", "v9.9.9")
    _git(repo, "checkout", "-q", "-")

    def resolve(tag: str) -> str:
        return str(
            _gate.resolve_rollback(
                tag,
                tip,
                tag_commit=_gate.tag_commit,
                on_main=_gate.is_in_history,
                missing_actions=_gate.missing_build_actions,
            )
        )

    assert resolve(f"publish-{DAY}.1") == old
    with pytest.raises(_gate.UnsupportedRunError, match="not on main"):
        resolve("v9.9.9")
    with pytest.raises(_gate.UnsupportedRunError, match="names no tag"):
        resolve("v1.0.0")
    assert _gate.tag_commit("v9.9.9") == stray


@pytest.mark.spec("DOCBW-06-030", "DOCBW-06-011")
def test_a_rollback_target_must_carry_the_build_actions(
    repo: Path, outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A release older than the local build actions (v2024.4.3 and before)
    is refused by the gate, with its reason, instead of failing the build."""
    _git(repo, "rm", "-q", "-r", ".github")
    _git(repo, "commit", "-q", "-m", "before the build actions")
    _git(repo, "tag", "v2024.4.3")
    old = _head(repo)
    _git(repo, "checkout", "-q", "HEAD~1", "--", ".github")
    tip = _commit(repo, "the build actions again")
    assert _gate.missing_build_actions(old) == list(_gate.BUILD_ACTIONS)
    assert _gate.missing_build_actions(tip) == []
    _no_github(monkeypatch)
    assert _gate_main(sha=tip, rollback_to="v2024.4.3") == 1
    summary = outputs["summary"].read_text()
    assert "refused" in summary and "predates the build" in summary
    assert not outputs["out"].exists()


@pytest.mark.spec("DOCBW-08-038")
def test_a_rollback_target_must_carry_the_frozen_draft_serving_step(
    repo: Path, outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit that has the other build actions but predates the step that
    serves the frozen drafts is refused with its reason in the run summary;
    one that has the step passes the gate."""
    serving = ".github/actions/serve-frozen-drafts/action.yml"
    assert serving in _gate.BUILD_ACTIONS
    _git(repo, "rm", "-q", serving)
    _git(repo, "commit", "-q", "-m", "before the serving step")
    _git(repo, "tag", "v2026.10.0")
    old = _head(repo)
    _git(repo, "checkout", "-q", "HEAD~1", "--", serving)
    tip = _commit(repo, "the serving step")
    _git(repo, "tag", "v2026.11.0")
    _git(repo, "push", "-q", "origin", "HEAD")
    assert _gate.missing_build_actions(old) == [serving]
    _no_github(monkeypatch)
    assert _gate_main(sha=tip, rollback_to="v2026.10.0") == 1
    summary = outputs["summary"].read_text()
    assert "refused" in summary and serving in summary
    assert not outputs["out"].exists()
    assert _gate_main(sha=tip, rollback_to="v2026.11.0") == 0
    out = outputs["out"].read_text()
    assert "publish=true\n" in out and f"commit={tip}\n" in out


@pytest.mark.spec("DOCBW-06-020", "DOCBW-06-013")
def test_a_rolled_back_commit_is_not_republished(repo: Path) -> None:
    """Main's tip X was published, then the site rolled back to W.

    The rollback tag lands on W, so it is the newest tag and names what is
    live. X keeps its own tag, so the next scheduled run, which finds X still
    at the tip of main, skips it instead of undoing the rollback.
    """
    w = _head(repo)
    _tag_as_bot(repo, f"publish-{DAY}.1")
    x = _commit(repo, "X")
    _tag_as_bot(repo, f"publish-{DAY}.2")
    _tag_as_bot(repo, f"publish-{DAY}.3", target=w)  # the rollback
    newest = _gate.next_publish_name(DAY, _git(repo, "tag").split())
    assert newest == f"publish-{DAY}.4"
    assert _gate.tag_commit(f"publish-{DAY}.3") == w
    decision = _Calls(tags=_gate.publish_tags_on(x)).decide(
        _ctx(Trigger.SCHEDULED)
    )
    assert not decision.publish
    assert f"`publish-{DAY}.2`" in decision.reason


@pytest.mark.spec("DOCBW-06-017", "DOCBW-06-020")
@pytest.mark.parametrize(
    ("trigger", "source_tag", "first_line"),
    [
        (Trigger.SCHEDULED, "", "scheduled publish, by github-actions[bot]."),
        (Trigger.MANUAL, "", "manual publish, by @octocat."),
        (
            Trigger.MANUAL_UNGATED,
            "",
            "manual publish with the CI gate skipped, by @octocat.",
        ),
        (
            Trigger.ROLLBACK,
            f"publish-{DAY}.1",
            f"rollback to publish-{DAY}.1, by @octocat.",
        ),
        # Only the bot starts a release run, and it names a v* tag.
        (
            Trigger.RELEASE,
            RELEASE,
            f"publish after release {RELEASE}, by github-actions[bot].",
        ),
    ],
)
def test_tag_message_records_trigger_and_actor(
    trigger: Any, source_tag: str, first_line: str
) -> None:
    message = _gate.tag_message(_ctx(trigger, source_tag), RUN_URL)
    assert message.splitlines()[0] == first_line
    assert "Commit: abc123" in message and f"Run: {RUN_URL}" in message


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
def test_next_publish_name(existing: list[str], expected: str) -> None:
    assert _gate.next_publish_name(DAY, existing) == expected


def _remote_tags(repo: Path) -> dict[str, str]:
    out = _git(repo, "ls-remote", "--tags", "origin")
    return {
        ref.removeprefix("refs/tags/"): oid
        for oid, ref in (line.split("\t") for line in out.splitlines())
        if not ref.endswith("^{}")
    }


NAME = f"publish-{DAY}.1"


@pytest.mark.spec("DOCBW-06-016", "DOCBW-06-017", "DOCBW-06-031")
def test_create_tag_pushes_the_named_annotated_tag(repo: Path) -> None:
    sha = _head(repo)
    name = _gate.create_tag(
        sha, NAME, f"scheduled publish.\n\nRun: {RUN_URL}\n", RUN_URL
    )
    assert name == NAME
    assert list(_remote_tags(repo)) == [NAME]
    tag = _gate.publish_tags_on(sha)
    assert len(tag) == 1 and tag[0].made_by_workflow
    contents = _git(repo, "tag", "-l", "--format=%(contents)", NAME)
    assert contents.splitlines()[0] == "scheduled publish."


@pytest.mark.spec("DOCBW-06-031")
@pytest.mark.parametrize("name", ["", "publish-2026-11-02", "v2026.11.0"])
def test_create_tag_refuses_a_name_that_is_no_publish_tag(
    repo: Path, name: str
) -> None:
    with pytest.raises(ValueError, match="is not a publish-"):
        _gate.create_tag(_head(repo), name, "x\n", RUN_URL)
    assert _remote_tags(repo) == {}


@pytest.mark.spec("DOCBW-06-016", "DOCBW-06-025")
def test_a_rerun_finds_the_tag_it_pushed(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running a failed tag job makes no second tag for the same run.

    A re-run checks the repository out afresh, so it starts from a clone
    that already holds the tag the first attempt pushed.
    """
    sha = _head(repo)
    message = _gate.tag_message(
        _gate.RunContext(Trigger.MANUAL, sha, "octocat"), RUN_URL
    )
    first = _gate.create_tag(sha, NAME, message, RUN_URL)
    rerun = tmp_path / "rerun"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "origin.git"), str(rerun)],
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(rerun)
    assert _gate.create_tag(sha, NAME, message, RUN_URL) == first
    assert list(_remote_tags(repo)) == [first]


@pytest.mark.spec("DOCBW-06-031", "DOCBW-06-022")
def test_another_runs_tag_of_the_same_name_fails_the_job(repo: Path) -> None:
    """The name is the one every deployed page shows: it is never renumbered."""
    sha = _head(repo)
    _gate.create_tag(sha, NAME, "manual publish.\n", RUN_URL)
    before = _remote_tags(repo)
    other = "https://github.com/O/R/actions/runs/6"
    with pytest.raises(_gate.TagNameTakenError):
        _gate.create_tag(sha, NAME, "manual publish.\n", other)
    assert _remote_tags(repo) == before


@pytest.mark.spec("DOCBW-06-031", "DOCBW-06-022")
def test_a_name_taken_by_hand_fails_the_job_and_is_left_alone(
    repo: Path, tmp_path: Path
) -> None:
    """A hand-made tag of the chosen name lands between the gate and the tag job.

    The tag job fails instead of renumbering to a name the deployed footer
    does not show, and the hand-made tag on the remote is left as it was.
    """
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)],
        check=True,
        capture_output=True,
    )
    _git(other, "tag", "-a", NAME, "-m", "by hand")
    _git(other, "push", "-q", "origin", NAME)
    before = _remote_tags(repo)
    with pytest.raises(_gate.TagNameTakenError):
        _gate.create_tag(_head(repo), NAME, "manual publish.\n", RUN_URL)
    assert _remote_tags(repo) == before
    assert _git(repo, "tag", "--list", "publish-*").split() == []


@pytest.mark.spec("DOCBW-06-031", "DOCBW-06-022")
def test_a_name_taken_during_the_push_fails_the_job(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hand-made tag lands after the job checked the name, before it pushed."""
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)],
        check=True,
        capture_output=True,
    )
    real_run = _gate.run

    def race_then_run(*argv: str) -> str:
        if argv[:2] == ("git", "push"):
            _git(other, "tag", "-a", NAME, "-m", "by hand")
            _git(other, "push", "-q", "origin", NAME)
        return str(real_run(*argv))

    monkeypatch.setattr(_gate, "run", race_then_run)
    with pytest.raises(_gate.TagNameTakenError):
        _gate.create_tag(_head(repo), NAME, "manual publish.\n", RUN_URL)
    contents = _git(other, "tag", "-l", "--format=%(contents)", NAME)
    assert contents.strip() == "by hand"


@pytest.mark.spec("DOCBW-06-016")
def test_create_tag_accepts_a_push_that_landed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A push that reached the remote but reported failure is not repeated."""
    real_run = _gate.run

    def push_then_fail(*argv: str) -> str:
        out = str(real_run(*argv))
        if argv[:2] == ("git", "push"):
            raise subprocess.CalledProcessError(1, list(argv))
        return out

    monkeypatch.setattr(_gate, "run", push_then_fail)
    name = _gate.create_tag(_head(repo), NAME, "x\n", RUN_URL)
    assert name == NAME
    assert list(_remote_tags(repo)) == [NAME]


def test_create_tag_raises_when_the_remote_cannot_be_read(
    repo: Path,
) -> None:
    """An unreachable remote fails before any tag is made."""
    sha = _head(repo)
    _git(repo, "remote", "set-url", "origin", str(repo.parent / "missing.git"))
    with pytest.raises(subprocess.CalledProcessError):
        _gate.create_tag(sha, NAME, "x\n", RUN_URL)
    assert _git(repo, "tag", "--list", "publish-*").split() == []


@pytest.mark.spec("DOCBW-06-031")
def test_create_tag_raises_a_push_failure_that_is_no_collision(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused push whose name nobody took is a real failure, never a taken name."""
    real_run = _gate.run

    def refuse_push(*argv: str) -> str:
        if argv[:2] == ("git", "push"):
            raise subprocess.CalledProcessError(1, list(argv))
        return str(real_run(*argv))

    monkeypatch.setattr(_gate, "run", refuse_push)
    with pytest.raises(subprocess.CalledProcessError):
        _gate.create_tag(_head(repo), NAME, "x\n", RUN_URL)
    assert _remote_tags(repo) == {}


@pytest.mark.spec("DOCBW-06-016", "DOCBW-06-031")
def test_next_publish_tag_counts_local_and_remote_tags(
    repo: Path, tmp_path: Path
) -> None:
    """A tag pushed while the gate waited is on the remote, not in its clone."""
    _tag_as_bot(repo, NAME)
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)],
        check=True,
        capture_output=True,
    )
    _git(other, "tag", "-a", f"publish-{DAY}.2", "-m", "by hand")
    _git(other, "push", "-q", "origin", f"publish-{DAY}.2")
    assert _gate.next_publish_tag(DAY) == f"publish-{DAY}.3"


@pytest.mark.spec("DOCBW-06-031")
def test_release_tag_on_names_the_newest_release_on_the_commit(
    repo: Path,
) -> None:
    sha = _head(repo)
    assert _gate.release_tag_on(sha) == ""
    _git(repo, "tag", "v2026.10.0")
    _git(repo, "tag", "-a", "v2026.11.0", "-m", "release")
    _git(repo, "tag", "vnext")  # not version-shaped
    assert _gate.release_tag_on(sha) == "v2026.11.0"
    _commit(repo, "later")
    assert _gate.release_tag_on(_head(repo)) == ""


# --- the gate and tag commands ------------------------------------------------------


@pytest.fixture
def outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Path]:
    paths = {"out": tmp_path / "out", "summary": tmp_path / "summary"}
    monkeypatch.setenv("GITHUB_OUTPUT", str(paths["out"]))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(paths["summary"]))
    monkeypatch.setenv("BLOCKING_WORKFLOWS", _blocking_env())
    return paths


def _gate_main(
    *, event: str = "workflow_dispatch", sha: str = "abc123", **inputs: str
) -> int:
    argv = [
        "gate", "--repo", "O/R", "--sha", sha, "--event", event,
        "--ref", inputs.pop("ref", MAIN), "--actor", inputs.pop("actor", "octocat"),
        "--run-id", "5",
    ]  # fmt: skip
    for key, value in inputs.items():
        argv += [f"--{key.replace('_', '-')}", value]
    return int(_gate.main(argv))


def _no_github(
    monkeypatch: pytest.MonkeyPatch,
    issues: list[dict[str, object]] | None = None,
) -> None:
    monkeypatch.setattr(
        _gate, "list_failure_issues", lambda repo: issues or []
    )
    monkeypatch.setattr(_gate, "list_main_runs", lambda repo: [])


@pytest.mark.spec("DOCBW-06-011")
def test_gate_command_writes_its_verdict(
    outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_gate, "publish_tags_on", lambda sha: [])
    _no_github(
        monkeypatch,
        [{"number": 41, "labels": ["ci:main-failure", "ci:workflow-ui"]}],
    )
    assert _gate_main(event="schedule") == 0
    summary = outputs["summary"].read_text()
    assert "Skipped" in summary
    assert "blocked by #41 (ci:workflow-ui)" in summary
    out = outputs["out"].read_text()
    assert "publish=false\n" in out and "trigger=scheduled\n" in out
    assert "commit=abc123\n" in out
    assert "scheduled publish, by github-actions[bot]." in out
    # A run that does not publish names no tag for a build to print.
    for key in ("publish-tag", "publish-date", "release-tag"):
        assert f"{key}=\n" in out


@pytest.mark.spec("DOCBW-06-018")
def test_gate_command_skips_the_gate_on_request(
    outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_gate, "publish_tags_on", lambda sha: [])
    _no_github(
        monkeypatch,
        [{"number": 41, "labels": ["ci:main-failure", "ci:workflow-ui"]}],
    )
    monkeypatch.setattr(_gate, "_utc_today", lambda: DAY)
    monkeypatch.setattr(
        _gate, "next_publish_tag", lambda day: f"publish-{day}.4"
    )
    monkeypatch.setattr(_gate, "release_tag_on", lambda sha: "")
    assert _gate_main(skip_ci_gate="true") == 0
    out = outputs["out"].read_text()
    assert "publish=true\n" in out and "trigger=manual-ungated\n" in out
    assert "manual publish with the CI gate skipped, by @octocat." in out
    assert f"publish-tag=publish-{DAY}.4\n" in out
    assert f"publish-date={DAY}\n" in out and "release-tag=\n" in out
    assert f"tagged `publish-{DAY}.4`" in outputs["summary"].read_text()


@pytest.mark.spec("DOCBW-06-020")
def test_gate_command_rolls_back_to_a_commit_on_main(
    repo: Path, outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    old = _head(repo)
    _tag_as_bot(repo, f"publish-{DAY}.1")
    _git(repo, "tag", "-a", "v2026.11.0", "-m", "release")
    tip = _commit(repo, "tip")
    _no_github(
        monkeypatch,
        [{"number": 41, "labels": ["ci:main-failure", "ci:workflow-ui"]}],
    )
    monkeypatch.setattr(_gate, "_utc_today", lambda: DAY)
    assert _gate_main(sha=tip, rollback_to=f"publish-{DAY}.1") == 0
    out = outputs["out"].read_text()
    assert "publish=true\n" in out and "trigger=rollback\n" in out
    assert f"commit={old}\n" in out
    assert f"rollback to publish-{DAY}.1, by @octocat." in out
    # The rollback's build names the new publish of the old commit, and the
    # release that commit carries (DOCBW-06-031).
    assert f"publish-tag=publish-{DAY}.2\n" in out
    assert f"publish-date={DAY}\n" in out
    assert "release-tag=v2026.11.0\n" in out


@pytest.mark.spec("DOCBW-06-026")
def test_gate_command_refuses_a_rollback_off_main(
    repo: Path, outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    tip = _head(repo)
    _git(repo, "checkout", "-q", "-b", "unreviewed")
    _commit(repo, "never merged")
    _git(repo, "tag", "v9.9.9")
    _no_github(monkeypatch)
    assert _gate_main(sha=tip, rollback_to="v9.9.9") == 1
    assert "not on main" in outputs["summary"].read_text()
    assert not outputs["out"].exists()


@pytest.mark.spec("DOCBW-06-029")
def test_gate_command_refuses_a_run_from_a_tag(
    outputs: dict[str, Path],
) -> None:
    assert _gate_main(ref="refs/tags/v2026.10.0") == 1
    assert "refused" in outputs["summary"].read_text()


@pytest.mark.spec(
    "DOCBW-06-032", "DOCBW-06-033", "DOCBW-06-035", "DOCBW-06-017"
)
def test_gate_command_publishes_main_after_a_published_release(
    outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_gate, "publish_tags_on", lambda sha: [_bot_tag()])
    _no_github(monkeypatch)
    looked_up: list[tuple[str, str]] = []

    def release_state(repo: str, name: str, *, retry: bool = False) -> Any:
        looked_up.append((repo, name))
        return _gate.ReleaseState(False, ())

    monkeypatch.setattr(_gate, "release_state", release_state)
    monkeypatch.setattr(_gate, "_utc_today", lambda: DAY)
    monkeypatch.setattr(
        _gate, "next_publish_tag", lambda day: f"publish-{day}.2"
    )
    monkeypatch.setattr(_gate, "release_tag_on", lambda sha: RELEASE)
    assert _gate_main(actor=BOT_NAME, release=RELEASE) == 0
    assert looked_up == [("O/R", RELEASE)]
    out = outputs["out"].read_text()
    assert "publish=true\n" in out and "trigger=release\n" in out
    assert "commit=abc123\n" in out
    assert f"publish after release {RELEASE}, by {BOT_NAME}." in out
    assert f"publish-tag=publish-{DAY}.2\n" in out


@pytest.mark.spec("DOCBW-06-034")
def test_gate_command_refuses_a_release_that_is_not_published(
    outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_github(monkeypatch)
    monkeypatch.setattr(
        _gate, "release_state", lambda repo, name, *, retry=False: None
    )
    assert _gate_main(actor=BOT_NAME, release=RELEASE) == 1
    summary = outputs["summary"].read_text()
    assert "refused" in summary and RELEASE in summary
    assert not outputs["out"].exists()


@pytest.mark.spec("DOCBW-06-034")
def test_gate_command_fails_when_the_release_lookup_fails(
    outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lookup that still fails after retry.sh's retries fails the gate."""
    _no_github(monkeypatch)

    def release_state(repo: str, name: str, *, retry: bool = False) -> Any:
        assert retry, "the gate's release lookup retries"
        raise subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 502")

    monkeypatch.setattr(_gate, "release_state", release_state)
    with pytest.raises(subprocess.CalledProcessError):
        _gate_main(actor=BOT_NAME, release=RELEASE)
    assert not outputs["out"].exists()


@pytest.mark.spec("DOCBW-06-034")
def test_gate_command_refuses_a_release_run_a_person_started(
    outputs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def must_not_look_up(*args: object, **kwargs: object) -> None:
        raise AssertionError("a refused run looks up no release")

    monkeypatch.setattr(_gate, "release_state", must_not_look_up)
    assert _gate_main(release=RELEASE) == 1
    assert "github-actions" in outputs["summary"].read_text()
    assert not outputs["out"].exists()


@pytest.mark.parametrize(
    "text", ["", "# only a comment\n", "path-without-label\n"]
)
def test_parse_blocking_refuses_an_empty_or_malformed_list(text: str) -> None:
    with pytest.raises(ValueError):
        _gate.parse_blocking(text)


def test_tag_command_writes_the_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    made: list[tuple[str, str, str, str]] = []

    def create_tag(sha: str, name: str, message: str, run_url: str) -> str:
        made.append((sha, name, message, run_url))
        return name

    monkeypatch.setattr(_gate, "create_tag", create_tag)
    argv = [
        "tag", "--sha", "abc123", "--name", f"publish-{DAY}.1",
        "--message", "m\n", "--run-url", RUN_URL,
    ]  # fmt: skip
    assert _gate.main(argv) == 0
    assert made == [("abc123", f"publish-{DAY}.1", "m\n", RUN_URL)]
    assert out.read_text() == f"tag=publish-{DAY}.1\n"


# --- GitHub plumbing ---------------------------------------------------------------


@pytest.fixture
def fake_gh_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., Any]:
    def install(**kwargs: Any) -> Any:
        gh = install_fake_gh(tmp_path, **kwargs)
        for key, value in gh.env.items():
            monkeypatch.setenv(key, value)
        return gh

    return install


def test_list_failure_issues_reads_the_list_endpoint(
    fake_gh_env: Callable[..., Any],
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
    gh = fake_gh_env(issues_page=page)
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


@pytest.mark.spec("DOCBW-06-008")
def test_an_api_error_fails_the_gate(fake_gh_env: Callable[..., Any]) -> None:
    """An unreadable issue list never reads as "no issue open"."""
    fake_gh_env(api_fails=True)
    with pytest.raises(subprocess.CalledProcessError):
        _gate.list_failure_issues("O/R")


def test_list_main_runs_extracts_each_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = json.dumps(
        {
            "workflow_runs": [
                {**_run(1, ".github/workflows/ui.yml", "queued"), "extra": 0},
                _run(2, ".github/workflows/spec-check.yml", "completed"),
            ]
        }
    )
    seen: list[tuple[str, ...]] = []

    def run_jq(*args: str) -> str:
        seen.append(args)
        return subprocess.run(
            ["jq", args[-1]],
            input=page,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    monkeypatch.setattr(_gate, "gh", run_jq)
    runs = _gate.list_main_runs("O/R")
    assert [r["id"] for r in runs] == [1, 2]
    assert set(runs[0]) == {"id", "name", "path", "status", "head_sha"}
    assert "repos/O/R/actions/runs?branch=main&per_page=100" in seen[0]


# --- the workflow -----------------------------------------------------------------


def _workflow() -> dict[str, Any]:
    return load_workflow(_WORKFLOW)


def _blocking_env() -> str:
    return str(_workflow()["env"]["BLOCKING_WORKFLOWS"])


def _job(name: str) -> dict[str, Any]:
    return dict(_workflow()["jobs"][name])


def _job_steps(name: str) -> list[dict[str, Any]]:
    return list(_job(name)["steps"])


def _needs(name: str) -> set[str]:
    return job_needs(_job(name))


@pytest.mark.spec("DOCBW-06-007")
def test_publication_workflow_triggers() -> None:
    on = triggers(_workflow())
    assert set(on) == {"schedule", "workflow_dispatch"}
    assert on["schedule"] == [{"cron": "7 6 * * 1-5"}]


@pytest.mark.spec("DOCBW-06-018", "DOCBW-06-020")
def test_skip_ci_gate_input_defaults_off() -> None:
    inputs = triggers(_workflow())["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"skip-ci-gate", "rollback-to", "release"}
    assert inputs["skip-ci-gate"]["type"] == "boolean"
    assert inputs["skip-ci-gate"]["default"] is False
    assert inputs["rollback-to"]["default"] == ""
    assert inputs["release"]["default"] == ""


@pytest.mark.spec("DOCBW-06-032", "DOCBW-06-034")
def test_the_gate_reads_the_release_input_and_the_actor() -> None:
    (gate,) = [s for s in _job_steps("gate") if s.get("id") == "gate"]
    assert gate["env"]["RELEASE"] == "${{ inputs.release }}"
    assert gate["env"]["ACTOR"] == "${{ github.actor }}"
    assert '--release "$RELEASE"' in gate["run"]


def _after_release() -> dict[str, Any]:
    return load_workflow(_AFTER_RELEASE)


@pytest.mark.spec("DOCBW-06-032")
def test_publishing_a_release_dispatches_a_publish_of_main() -> None:
    """A published release starts the publish workflow from main.

    The release event runs from the tag, which the Pages environment does not
    let deploy and whose copy of the workflow is not main's (ADR-0171), so
    this workflow only dispatches; the publish itself runs from main.
    """
    wf = _after_release()
    assert triggers(wf) == {"release": {"types": ["published"]}}
    assert wf["permissions"] == {"contents": "read"}
    (name,) = wf["jobs"]
    job = wf["jobs"][name]
    assert job["permissions"] == {
        "contents": "read",
        "actions": "write",
        "issues": "write",
    }
    assert "timeout-minutes" in job
    job_steps = job["steps"]
    (checkout,) = [
        s for s in job_steps if "actions/checkout" in str(s.get("uses"))
    ]
    # Only main's notify-failure action is loaded; no tag code runs.
    assert checkout["with"] == {"ref": "main"}
    (dispatch,) = [
        s for s in job_steps if "gh workflow run" in str(s.get("run"))
    ]
    command = " ".join(str(dispatch["run"]).split())
    assert f"gh workflow run {_WORKFLOW.name}" in command
    assert "--ref main" in command
    assert '--field release="$RELEASE"' in command
    assert dispatch["env"]["RELEASE"] == "${{ github.event.release.tag_name }}"
    assert dispatch["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"  # noqa: S105 - an expression, not a secret
    assert job_steps.index(checkout) < job_steps.index(dispatch)


@pytest.mark.spec("DOCBW-06-032")
def test_a_failed_dispatch_files_a_failure_issue() -> None:
    (job,) = _after_release()["jobs"].values()
    reports = {
        s["with"]["mode"]: s
        for s in job["steps"]
        if s.get("uses") == "./.github/actions/notify-failure"
    }
    assert set(reports) == {"notify", "close"}
    assert reports["notify"]["if"] == "failure()"
    assert reports["close"]["if"] == "success()"
    labels = {s["with"]["workflow-label"] for s in reports.values()}
    assert labels == {"ci:workflow-publish-after-release"}


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
    """The build runs only when the gate says to, on the commit it chose."""
    gate_run = " ".join(str(s.get("run", "")) for s in _job_steps("gate"))
    assert "publish_gate.py gate" in gate_run
    build = _job("build")
    assert set(build["needs"]) == {"gate", "drafts"}
    assert build["if"] == "needs.gate.outputs.publish == 'true'"
    (shared,) = [
        s
        for s in build["steps"]
        if s.get("uses") == "./.github/actions/build-site"
    ]
    assert shared["with"] == {"ref": "${{ needs.gate.outputs.commit }}"}
    # The other checkouts take the run's own commit, main's tip.
    for name in ("gate", "drafts", "build", "tag"):
        for step in _job_steps(name):
            if step.get("uses") != shared["uses"]:
                assert "ref" not in step.get("with", {}), (name, step)
    assert _needs("deploy") == {"gate", "build"}
    assert _needs("tag") == {"gate", "deploy"}
    tag_env = _job_steps("tag")[-1]["env"]
    assert tag_env["SHA"] == "${{ needs.gate.outputs.commit }}"


@pytest.mark.spec("DOCBW-06-031")
def test_the_build_and_the_tag_job_share_the_gates_tag_name() -> None:
    """The footer the build prints and the tag the tag job makes are one name."""
    outputs = _job("gate")["outputs"]
    for key in ("publish-tag", "publish-date", "release-tag"):
        assert outputs[key] == f"${{{{ steps.gate.outputs.{key} }}}}"
    (shared,) = [
        s
        for s in _job_steps("build")
        if s.get("uses") == "./.github/actions/build-site"
    ]
    # The variables build_version.py reads, each fed by its gate output.
    assert shared["env"] == {
        PUBLISH_TAG_ENV: "${{ needs.gate.outputs.publish-tag }}",
        PUBLISH_DATE_ENV: "${{ needs.gate.outputs.publish-date }}",
        RELEASE_TAG_ENV: "${{ needs.gate.outputs.release-tag }}",
    }
    tag = _job_steps("tag")[-1]
    assert tag["env"]["TAG_NAME"] == "${{ needs.gate.outputs.publish-tag }}"
    assert '--name "$TAG_NAME"' in tag["run"]


@pytest.mark.spec("DOCBW-06-031")
def test_the_footer_and_the_free_name_are_checked_before_the_upload() -> None:
    """A stale name from a re-run, or env that never reached the build, fails
    before anything reaches Pages."""
    build_steps = _job_steps("build")
    check = index_of(
        build_steps, "Check the footer names this publish", "name"
    )
    built = index_of(build_steps, "./.github/actions/build-site", "uses")
    upload = index_of(build_steps, "actions/upload-pages-artifact", "uses")
    assert None not in (check, built, upload)
    assert built < check < upload  # type: ignore[operator]
    step = build_steps[check]  # type: ignore[index]
    assert step["env"] == {"TAG_NAME": "${{ needs.gate.outputs.publish-tag }}"}
    assert "if" not in step and "continue-on-error" not in step
    run = step["run"]
    assert 'git ls-remote --tags origin "refs/tags/$TAG_NAME"' in run
    assert '">$TAG_NAME</a>" site/index.html' in run
    partial = REPO_ROOT / "overrides" / "partials" / "copyright.html"
    assert 'class="build-footer"' in partial.read_text(encoding="utf-8")
    assert 'class="build-footer"' in run


def _footer_check(
    repo: Path, tag_name: str, index_html: str | None
) -> subprocess.CompletedProcess[str]:
    """Run the build job's footer check as GitHub runs it, in *repo*."""
    build_steps = _job_steps("build")
    check = index_of(
        build_steps, "Check the footer names this publish", "name"
    )
    assert check is not None
    step = build_steps[check]
    if index_html is not None:
        (repo / "site").mkdir(exist_ok=True)
        (repo / "site" / "index.html").write_text(index_html, encoding="utf-8")
    # GitHub's default for `run:` without `shell:` (no `defaults:` here).
    return subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-eo",
            "pipefail",
            "-c",
            step["run"],
        ],
        cwd=repo,
        env={**os.environ, "TAG_NAME": tag_name},
        capture_output=True,
        text=True,
        check=False,
    )


def _built_page(name: str) -> str:
    """An index page as the build prints it, footer from build_version.py."""
    line = describe_build(
        "2026.11.0", Publish(name, date.fromisoformat(DAY)), "https://g/O/R"
    )
    return f'<footer><p class="build-footer">{line}</p></footer>'


@pytest.mark.spec("DOCBW-06-031")
def test_the_footer_check_passes_a_free_name_the_footer_prints(
    repo: Path,
) -> None:
    result = _footer_check(repo, NAME, _built_page(NAME))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::error::" not in result.stdout


@pytest.mark.spec("DOCBW-06-031")
@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("no-name", "named no publish tag"),
        ("taken", "already on the remote"),
        ("footer-names-another", "does not name"),
        ("unreadable-remote", ""),
    ],
)
def test_the_footer_check_fails_before_the_upload(
    repo: Path, case: str, message: str
) -> None:
    """Each refusal fails the step, an unreadable remote included."""
    name, page = NAME, _built_page(NAME)
    if case == "no-name":
        name = ""
    elif case == "taken":
        _git(repo, "tag", NAME)
        _git(repo, "push", "-q", "origin", f"refs/tags/{NAME}")
    elif case == "footer-names-another":
        page = _built_page(f"publish-{DAY}.2")
    else:
        _git(
            repo,
            "remote",
            "set-url",
            "origin",
            str(repo.parent / "missing.git"),
        )
    result = _footer_check(repo, name, page)
    assert result.returncode != 0
    assert message in result.stdout


@pytest.mark.spec("DOCBW-06-031")
def test_the_footer_check_only_notes_a_page_without_the_footer(
    repo: Path,
) -> None:
    """A rollback target older than the footer builds pages with none."""
    result = _footer_check(repo, NAME, "<footer><p>old box</p></footer>")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::notice::" in result.stdout


@pytest.mark.spec("DOCBW-06-016", "DOCBW-06-002")
def test_the_tag_job_follows_the_deploy() -> None:
    steps = _job_steps("build")
    build = index_of(steps, "./.github/actions/build-site", "uses")
    check = index_of(steps, "./.github/actions/check-site-publication", "uses")
    upload = index_of(steps, "actions/upload-pages-artifact", "uses")
    assert None not in (build, check, upload)
    assert build < check < upload  # type: ignore[operator]
    assert [s["uses"].split("@")[0] for s in _job_steps("deploy")] == [
        "actions/deploy-pages"
    ]
    tag = _job_steps("tag")[-1]
    assert "publish_gate.py tag" in tag["run"]
    assert "if" not in tag and "if" not in _job("tag")
    assert "continue-on-error" not in tag


@pytest.mark.spec("DOCBW-06-024", "DOCBW-06-027")
def test_each_job_holds_only_its_permissions() -> None:
    wf = _workflow()
    assert wf["permissions"] == {"contents": "read"}
    expected = {
        "gate": {"contents": "read", "issues": "read", "actions": "read"},
        "drafts": {"contents": "read"},
        "build": {"contents": "read", "pages": "read"},
        "deploy": {"pages": "write", "id-token": "write"},
        "tag": {"contents": "write"},
        "notify": {"contents": "read", "issues": "write"},
    }
    assert {n: j.get("permissions") for n, j in wf["jobs"].items()} == expected
    # Only the deploy job may deploy to the Pages environment.
    assert [n for n, j in wf["jobs"].items() if "environment" in j] == [
        "deploy"
    ]


@pytest.mark.spec("DOCBW-06-021")
def test_one_concurrency_group_never_cancels() -> None:
    wf = _workflow()
    assert wf["concurrency"] == {"group": "pages", "cancel-in-progress": False}
    for name, job in wf["jobs"].items():
        assert "concurrency" not in job, (
            f"job {name} sets its own concurrency."
        )


_TAG_REWRITES = re.compile(
    r"--delete|--force|\s-[df]\b|\"-[df]\"|:refs/tags|\+refs/tags"
    r"|tag\s+-[a-z]*[df]"
)


# Every workflow that reads or writes publish-* or v* tags, and the scripts
# they run. Tags are append-only (#5545), so none may move or delete one.
_TAG_WORKFLOWS = (
    _WORKFLOW,
    WORKFLOWS_DIR / "promote_release.yml",
    WORKFLOWS_DIR / "release_tag_check.yml",
    WORKFLOWS_DIR / "site_staleness.yml",
)
_TAG_SCRIPTS = tuple(
    SCRIPTS_DIR / f"{name}.py"
    for name in ("publish_gate", "release", "release_tags")
)


@pytest.mark.spec("DOCBW-06-022", "DOCBW-07-009")
@pytest.mark.parametrize(
    "path", [*_TAG_WORKFLOWS, *_TAG_SCRIPTS], ids=lambda p: p.name
)
def test_no_step_moves_or_deletes_a_tag(path: Path) -> None:
    """No step pushes a tag deletion or a force-updated tag ref."""
    if path.suffix == ".py":
        text = path.read_text()
    else:
        wf_steps = steps(load_workflow(path))
        assert wf_steps, f"{path.name} has no steps, so nothing was checked"
        text = "\n".join(str(s.get("run", "")) for s in wf_steps)
    found = _TAG_REWRITES.findall(text)
    assert not found, f"{path.name} can move or delete a tag: {found}"


@pytest.mark.parametrize(
    "path", [*_TAG_WORKFLOWS, _AFTER_RELEASE], ids=lambda p: p.name
)
def test_no_run_step_expands_an_expression(path: Path) -> None:
    """Inputs, outputs and context values reach a shell only through ``env:``.

    A ``${{ }}`` inside ``run:`` is pasted into the script before the shell
    parses it, so a crafted ``rollback-to`` or ``publish-tag`` would run as
    code in a job that can push a tag.
    """
    inlined = [
        str(s.get("name", s.get("id", "?")))
        for s in steps(load_workflow(path))
        if "${{" in str(s.get("run", ""))
    ]
    assert not inlined, f"{path.name}: run: expands an expression in {inlined}"


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
    steps = _job_steps("notify")
    close = next(s for s in steps if s.get("with", {}).get("mode") == "close")
    guard = " ".join(str(close["if"]).split())
    assert "needs.tag.result == 'success'" in guard
    assert "needs.gate.outputs.trigger != 'rollback'" in guard
    notify = next(
        s for s in steps if s.get("with", {}).get("mode") == "notify"
    )
    assert notify["with"]["workflow-label"] == "ci:workflow-deploy-site"
    assert _needs("notify") == {"gate", "drafts", "build", "deploy", "tag"}


@pytest.mark.spec("DOCBW-06-025")
def test_an_untagged_deploy_is_reported() -> None:
    steps = _job_steps("notify")
    describe = next(
        s for s in steps if "untagged-deploy.md" in str(s.get("run"))
    )
    guard = " ".join(str(describe["if"]).split())
    assert guard == (
        "needs.deploy.result == 'success' && needs.tag.result == 'failure'"
    )
    assert "does not name what is live" in describe["run"]
    notify = next(
        s for s in steps if s.get("with", {}).get("mode") == "notify"
    )
    assert notify["with"]["details-file"] == "untagged-deploy.md"
    assert steps.index(describe) < steps.index(notify)
