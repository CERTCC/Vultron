"""CI verification test — promotion, the release tag check and the staleness alarm.

The decisions are functions in ``.github/scripts/release.py``, tested here
without GitHub; the promote, check and staleness commands run against real
commits and tags in a scratch repository with a bare ``origin``, with ``gh``
replaced. The three workflows that run them (``promote_release.yml``,
``release_tag_check.yml``, ``site_staleness.yml``) are pinned here too: their
triggers, permissions, SHA pins and notify steps (DOCBW-07).
"""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from test.ci._scratch_git import (
    commit,
    git,
    isolate_git_config,
    scratch_clone,
    tag_as_bot,
)
from test.ci._scripts import load_script
from test.ci._workflows import WORKFLOWS_DIR, load_workflow, steps, triggers
from test.ci.test_workflow_failure_notification import (
    _qualifying_workflow_files,
    _reporting_violations,
)
from test.ci.test_workflow_sha_pinning import (
    _SHA_RE,
    _VERSION_COMMENT_RE,
    _uses_lines,
)

_rel = load_script("release")
_tags = load_script("release_tags")
_releases = load_script("github_releases")
Tag = _tags.Tag
BOT = (_tags.BOT_NAME, _tags.BOT_EMAIL)
TODAY = date(2026, 11, 2)  # a Monday
RUN_URL = "https://github.com/O/R/actions/runs/7"
MAIN = "refs/heads/main"

PROMOTE = WORKFLOWS_DIR / "promote_release.yml"
CHECK = WORKFLOWS_DIR / "release_tag_check.yml"
STALENESS = WORKFLOWS_DIR / "site_staleness.yml"
PUBLISH = WORKFLOWS_DIR / "deploy_site.yml"
NEW_WORKFLOWS = (PROMOTE, CHECK, STALENESS)


def _bot(name: str, commit_id: str = "c1", when: str = "") -> Any:
    created = datetime.fromisoformat(when) if when else None
    return Tag(name, True, *BOT, commit_id, created)


def _hand(name: str, commit_id: str = "c1") -> Any:
    return Tag(name, True, "Some Person", "p@example.org", commit_id)


# --- choosing what to promote --------------------------------------------------


@pytest.mark.spec("DOCBW-07-012")
def test_an_empty_input_promotes_the_newest_publish() -> None:
    tags = [
        _bot("publish-2026-10-30.1"),
        _bot("publish-2026-11-02.1", "c2"),
        _hand("publish-2026-11-03.1", "c3"),
    ]
    chosen = _rel.choose_publish_tag("", tags)
    assert chosen.name == "publish-2026-11-02.1"
    assert _rel.choose_publish_tag("publish-2026-10-30.1", tags).commit == "c1"


@pytest.mark.spec("DOCBW-07-002")
@pytest.mark.parametrize(
    ("requested", "tags", "why"),
    [
        ("v2026.10.0", [_bot("v2026.10.0")], "is not a publish-YYYY-MM-DD.N"),
        ("main", [], "is not a publish-YYYY-MM-DD.N"),
        ("publish-2026-11-02.9", [], "there is no tag"),
        (
            "publish-2026-11-02.1",
            [_hand("publish-2026-11-02.1")],
            "is tagged by Some Person",
        ),
        (
            "publish-2026-11-02.1",
            [Tag("publish-2026-11-02.1", False, commit="c1")],
            "is a lightweight tag",
        ),
        ("", [_hand("publish-2026-11-02.1")], "there is no publish-* tag"),
    ],
    ids=["release-tag", "branch", "missing", "by-hand", "lightweight", "none"],
)
def test_promote_refuses_an_input_that_is_no_publish(
    requested: str, tags: list[Any], why: str
) -> None:
    with pytest.raises(
        _rel.PromotionRefusedError, match=why.replace("*", r"\*")
    ):
        _rel.choose_publish_tag(requested, tags)


# --- naming the release ---------------------------------------------------------


@pytest.mark.spec("DOCBW-07-011")
def test_the_release_month_is_the_promotion_date() -> None:
    """A publish from October promoted in November is a November release."""
    source = _bot("publish-2026-10-30.1")
    releases = [_bot("v2026.10.0", "c0"), _bot("v2026.10.1", "c0b")]
    plan = _rel.plan_promotion(source, releases, TODAY)
    assert plan.release == "v2026.11.0"
    assert plan.previous == "v2026.10.1"
    assert plan.create_tag


@pytest.mark.spec("DOCBW-07-001")
def test_the_first_release_has_no_previous_release() -> None:
    plan = _rel.plan_promotion(_bot("publish-2026-11-02.1"), [], TODAY)
    assert (plan.release, plan.previous) == ("v2026.11.0", None)


@pytest.mark.spec("DOCBW-07-003")
def test_promote_never_names_a_release_below_the_latest() -> None:
    with pytest.raises(_tags.ReleaseOrderError):
        _rel.plan_promotion(
            _bot("publish-2026-11-02.1"),
            [_hand("v2026.12.0", "c9")],
            TODAY,
        )


@pytest.mark.spec("DOCBW-07-010")
def test_a_tagged_commit_without_a_release_gets_its_draft() -> None:
    """A run whose release step failed left the tag; the re-run reuses it."""
    source = _bot("publish-2026-11-02.1")
    releases = [_bot("v2026.10.0", "c0"), _bot("v2026.11.0", "c1")]
    plan = _rel.plan_promotion(source, releases, TODAY)
    assert (plan.release, plan.previous, plan.create_tag) == (
        "v2026.11.0",
        "v2026.10.0",
        False,
    )
    assert _rel.resume_action(plan, None, None, _never_matched) == "create"


def _never_matched() -> bool:
    raise AssertionError("asked whether a release's archive matches")


@pytest.mark.spec("DOCBW-07-016")
@pytest.mark.parametrize(
    ("releases", "why"),
    [
        (
            [_bot("v2026.11.0", "c1"), _bot("v2026.11.1", "c2")],
            "a later release, v2026.11.1, exists",
        ),
        # A hand-pushed tag is no promote run's leftover.
        ([_hand("v2026.11.0", "c1")], "not made by this workflow"),
    ],
    ids=["superseded", "by-hand"],
)
def test_a_released_commit_is_not_promoted_again(
    releases: list[Any], why: str
) -> None:
    with pytest.raises(_rel.PromotionRefusedError, match=why):
        _rel.plan_promotion(_bot("publish-2026-11-02.1"), releases, TODAY)


@pytest.mark.spec("DOCBW-07-016")
@pytest.mark.parametrize("is_draft", [True, False], ids=["draft", "published"])
def test_a_release_that_carries_no_draft_is_not_promoted_again(
    is_draft: bool,
) -> None:
    """With no draft to attach, any release of the tag ends the promotion."""
    plan = _rel.plan_promotion(
        _bot("publish-2026-11-02.1"), [_bot("v2026.11.0", "c1")], TODAY
    )
    state = _rel.ReleaseState(is_draft, ())
    with pytest.raises(_rel.PromotionRefusedError, match="released already"):
        _rel.resume_action(plan, None, state, _never_matched)


@pytest.mark.spec("DOCBW-07-016")
def test_a_release_of_a_tag_not_made_yet_is_refused() -> None:
    plan = _rel.plan_promotion(_bot("publish-2026-11-02.1"), [], TODAY)
    state = _rel.ReleaseState(True, ())
    with pytest.raises(_rel.PromotionRefusedError, match="without its tag"):
        _rel.resume_action(plan, None, state, _never_matched)


def test_release_tag_message_names_the_publish_and_the_actor() -> None:
    plan = _rel.Promotion(
        _bot("publish-2026-11-02.1"), "v2026.11.0", None, True
    )
    message = _rel.release_tag_message(plan, "octocat", RUN_URL)
    assert message.splitlines()[0] == (
        "Release v2026.11.0, promoted from publish-2026-11-02.1 by @octocat."
    )
    assert "Commit: c1" in message and f"Run: {RUN_URL}" in message


# --- staleness --------------------------------------------------------------------


@pytest.mark.spec("DOCBW-07-008")
@pytest.mark.parametrize(
    ("start", "end", "weekdays"),
    [
        (date(2026, 10, 30), date(2026, 11, 1), 0),  # Friday to Sunday
        (date(2026, 10, 30), date(2026, 11, 2), 1),  # Friday to Monday
        (date(2026, 11, 2), date(2026, 11, 2), 0),
        (date(2026, 11, 2), date(2026, 10, 30), 0),
        (date(2026, 11, 2), date(2026, 11, 9), 5),  # a week, Monday to Monday
        (date(2026, 10, 29), date(2026, 11, 4), 4),  # Thursday to Wednesday
        (date(2026, 10, 1), date(2026, 10, 31), 21),
    ],
)
def test_weekdays_between(start: date, end: date, weekdays: int) -> None:
    assert _rel.weekdays_between(start, end) == weekdays


def _at(when: str) -> datetime:
    return datetime.fromisoformat(when)


@pytest.mark.spec("DOCBW-07-008")
@pytest.mark.parametrize(
    ("published", "main", "unpublished", "stale"),
    [
        # Four weekdays behind is not yet stale; five is.
        ("2026-10-29T06:10:00+00:00", "2026-11-04T15:00:00+00:00", 3, False),
        ("2026-10-29T06:10:00+00:00", "2026-11-05T15:00:00+00:00", 3, True),
        # A weekend alone never triggers it.
        ("2026-10-30T06:10:00+00:00", "2026-11-01T23:00:00+00:00", 9, False),
        # Far behind in time, but main has nothing new: not stale.
        ("2026-10-01T06:10:00+00:00", "2026-11-05T15:00:00+00:00", 0, False),
        # Dates are compared in UTC.
        ("2026-10-29T23:30:00-05:00", "2026-11-05T01:00:00+00:00", 3, False),
    ],
    ids=["four", "five", "weekend", "nothing-new", "utc"],
)
def test_stale_site(
    published: str, main: str, unpublished: int, stale: bool
) -> None:
    newest = _bot("publish-x.1", when=published)
    reason = _rel.stale_site(newest, _at(main), unpublished)
    assert bool(reason) is stale
    if stale:
        assert "5 weekdays older" in reason


@pytest.mark.spec("DOCBW-07-008")
def test_no_publish_at_all_is_stale() -> None:
    reason = _rel.stale_site(None, _at("2026-11-02T00:00:00+00:00"), 4)
    assert "no `publish-*` tag" in reason


# --- the release tag check -----------------------------------------------------------


@pytest.mark.spec("DOCBW-07-007")
def test_unpublished_release_names_the_tag_and_never_deletes() -> None:
    assert _rel.unpublished_release("v2026.11.0", "c1", [_bot("p")]) == ""
    problem = _rel.unpublished_release("v2026.11.0", "c1", [])
    assert "`v2026.11.0` names `c1`" in problem
    assert "append-only, so this tag stays" in problem


# --- real repositories ----------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clone of a bare ``origin``, with one commit, as the current directory."""
    isolate_git_config(monkeypatch)
    work = scratch_clone(tmp_path)
    commit(work, "first", when="2026-10-29T12:00:00+00:00")
    git(work, "push", "-q", "origin", "HEAD")
    monkeypatch.chdir(work)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return work


def _remote_tags(repo: Path) -> set[str]:
    out = git(repo, "ls-remote", "--tags", "origin")
    return {
        ref.removeprefix("refs/tags/")
        for _, ref in (line.split("\t") for line in out.splitlines())
        if not ref.endswith("^{}")
    }


class _FakeGh:
    """Records every ``gh`` call; ``release create`` can fail once."""

    def __init__(self, *, fail_create: bool = False) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_create = fail_create

    def __call__(self, *args: str, retry: bool = True) -> str:
        self.calls.append(args)
        if args[:2] == ("release", "create"):
            assert retry is False, "a release create must not be retried"
            if self.fail_create:
                self.fail_create = False
                raise subprocess.CalledProcessError(1, ["gh", *args])
            return f"https://github.com/O/R/releases/tag/{args[2]}\n"
        if args[:2] == ("release", "view"):
            raise subprocess.CalledProcessError(
                1, ["gh", *args], stderr="release not found\n"
            )
        raise AssertionError(f"unexpected gh call {args}")

    def creates(self) -> list[tuple[str, ...]]:
        return [c for c in self.calls if c[:2] == ("release", "create")]


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch) -> _FakeGh:
    fake = _FakeGh()
    monkeypatch.setattr(_rel, "gh", fake)
    # The promote reads the release through github_releases.
    monkeypatch.setattr(_releases, "gh", fake)
    monkeypatch.setattr(_rel, "_today", lambda: TODAY)
    # These repositories hold no drafts register, so no release carries a
    # draft; test_frozen_drafts.py covers the releases that do.
    monkeypatch.setattr(_rel, "register_at", lambda ref: None)
    return fake


@pytest.mark.spec("DOCBW-08-043")
@pytest.mark.parametrize(
    ("now", "release", "day"),
    [
        # Friday afternoon: Monday's publish, the month's second release.
        ("2026-11-13T15:00:00+00:00", "v2026.11.1", "2026-11-16"),
        # Monday 30 November, late: Tuesday 1 December opens a new month.
        ("2026-11-30T20:00:00+00:00", "v2026.12.0", "2026-12-01"),
    ],
)
def test_next_freeze_names_the_next_publish_and_its_release(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    now: str,
    release: str,
    day: str,
) -> None:
    tag_as_bot(repo, "v2026.11.0")
    assert _rel.main(["next-freeze", "--now", now]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "release": release,
        "date": day,
        "publish_starts": f"{day}T06:07:00+00:00",
    }


@pytest.mark.spec("DOCBW-08-043")
@pytest.mark.parametrize(
    ("now", "words"),
    [("2026-11-13T15:00:00", "no time zone"), ("Friday", "Invalid isoformat")],
    ids=["naive", "malformed"],
)
def test_next_freeze_refuses_a_bad_time(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    now: str,
    words: str,
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert _rel.main(["next-freeze", "--now", now]) == 1
    assert words in capsys.readouterr().err
    text = summary.read_text(encoding="utf-8")
    assert "No freeze predicted" in text and "Promotion" not in text


def _promote(publish_tag: str = "", ref: str = MAIN) -> int:
    argv = [
        "promote", "--repo", "O/R", "--ref", ref, "--actor", "octocat",
        "--run-url", RUN_URL, "--publish-tag", publish_tag,
    ]  # fmt: skip
    return int(_rel.main(argv))


@pytest.mark.spec("DOCBW-07-001")
def test_promote_tags_the_publish_and_drafts_the_release(
    repo: Path, fake_gh: _FakeGh
) -> None:
    tag_as_bot(repo, "v2026.10.0")
    published = commit(repo, "published")
    tag_as_bot(repo, "publish-2026-10-30.1")
    commit(repo, "after the publish")
    assert _promote() == 0
    assert "v2026.11.0" in _remote_tags(repo)
    assert git(repo, "rev-parse", "v2026.11.0^{commit}") == published
    (release,) = [
        t for t in _tags.release_tags_on(published) if t.name == "v2026.11.0"
    ]
    assert release.made_by_workflow
    (create,) = fake_gh.creates()
    assert create[2] == "v2026.11.0"
    for flag in ("--draft", "--verify-tag", "--generate-notes"):
        assert flag in create
    assert create[create.index("--notes-start-tag") + 1] == "v2026.10.0"
    assert create[create.index("--notes") + 1] == _rel.EXPERIMENTAL_NOTICE


@pytest.mark.spec("DOCBW-07-002", "DOCBW-07-004")
@pytest.mark.parametrize(
    ("publish_tag", "ref"),
    [
        ("publish-2026-11-02.1", MAIN),  # pushed by hand
        ("publish-2026-10-30.1", "refs/heads/feature"),
        ("publish-2026-10-30.1", "refs/tags/v2026.10.0"),
    ],
    ids=["hand-pushed", "branch", "tag"],
)
def test_promote_refuses_and_tags_nothing(
    repo: Path, fake_gh: _FakeGh, publish_tag: str, ref: str
) -> None:
    tag_as_bot(repo, "publish-2026-10-30.1")
    git(repo, "tag", "-a", "publish-2026-11-02.1", "-m", "by hand")
    assert _promote(publish_tag, ref) == 1
    assert _tags.release_tags() == []
    assert fake_gh.calls == []


@pytest.mark.spec("DOCBW-07-010")
def test_a_rerun_after_a_failed_draft_reuses_the_tag(
    repo: Path, fake_gh: _FakeGh
) -> None:
    tag_as_bot(repo, "publish-2026-10-30.1")
    fake_gh.fail_create = True
    with pytest.raises(subprocess.CalledProcessError):
        _promote()
    assert _remote_tags(repo) >= {"v2026.11.0"}
    assert _promote() == 0
    assert [t.name for t in _tags.release_tags()] == ["v2026.11.0"]
    assert [c[2] for c in fake_gh.creates()] == ["v2026.11.0", "v2026.11.0"]
    # The first release has no earlier one to start the notes from.
    assert all("--notes-start-tag" not in c for c in fake_gh.creates())


def _check(tag: str, details: Path) -> int:
    return int(
        _rel.main(["check", "--tag", tag, "--details-file", str(details)])
    )


@pytest.mark.spec("DOCBW-07-007")
def test_check_passes_a_release_of_a_publish(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tag_as_bot(repo, "publish-2026-10-30.1")
    git(repo, "tag", "-a", "v2026.11.0", "-m", "by hand")
    details = tmp_path / "details.md"
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert _check("v2026.11.0", details) == 0
    assert not details.exists()
    assert out.read_text() == "checked=true\n"


@pytest.mark.spec("DOCBW-07-007")
def test_check_skips_a_v_tag_that_is_no_release(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``vendor-drop`` matches the trigger but is no release: no report, no close."""
    git(repo, "tag", "vendor-drop")
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    details = tmp_path / "details.md"
    assert _check("vendor-drop", details) == 0
    assert not details.exists()
    assert out.read_text() == "checked=false\n"


def test_check_fails_on_a_tag_it_cannot_find(
    repo: Path, tmp_path: Path
) -> None:
    with pytest.raises(_rel.PromotionRefusedError, match="no tag"):
        _check("v2026.11.9", tmp_path / "details.md")


@pytest.mark.spec("DOCBW-07-010")
@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("", _rel.ReleaseState(True, ("a.tar.gz",))),
        ("release not found\n", None),
        ("HTTP 502\n", "raises"),
    ],
    ids=["exists", "not-found", "api-error"],
)
def test_release_state_reads_only_not_found_as_no_release(
    monkeypatch: pytest.MonkeyPatch, stderr: str, expected: object
) -> None:
    calls: list[bool] = []

    def gh(*args: str, retry: bool = True) -> str:
        calls.append(retry)
        if stderr:
            raise subprocess.CalledProcessError(1, ["gh"], stderr=stderr)
        return '{"isDraft": true, "assets": [{"name": "a.tar.gz"}]}'

    monkeypatch.setattr(_releases, "gh", gh)
    if expected == "raises":
        with pytest.raises(subprocess.CalledProcessError):
            _releases.release_state("O/R", "v2026.11.0")
    else:
        assert _releases.release_state("O/R", "v2026.11.0") == expected
    assert calls == [False]


def test_release_state_with_retry_retries_an_error_until_it_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lookup error other than "not found" is tried again when the caller
    asks, and the release a later attempt reads is returned."""
    replies: list[str | subprocess.CalledProcessError] = [
        subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 502\n"),
        '{"isDraft": false, "assets": [{"name": "a.tar.gz"}]}',
    ]
    slept: list[float] = []

    def gh(*args: str, retry: bool = True) -> str:
        reply = replies.pop(0)
        if isinstance(reply, subprocess.CalledProcessError):
            raise reply
        return reply

    monkeypatch.setattr(_releases, "gh", gh)
    monkeypatch.setattr(_releases.time, "sleep", slept.append)
    monkeypatch.setenv("GH_RETRY_ATTEMPTS", "3")
    assert _releases.release_state("O/R", "v2026.11.0", retry=True) == (
        _releases.ReleaseState(False, ("a.tar.gz",))
    )
    assert replies == []
    assert len(slept) == 1


@pytest.mark.spec("DOCBW-07-007", "DOCBW-07-013", "DOCBW-07-014")
def test_check_reports_a_release_of_no_publish(
    repo: Path, tmp_path: Path
) -> None:
    """A hand-pushed ``publish-*`` tag does not make the commit published."""
    git(repo, "tag", "-a", "publish-2026-10-30.1", "-m", "by hand")
    git(repo, "tag", "v2026.11.0")
    details = tmp_path / "details.md"
    assert _check("v2026.11.0", details) == 1
    assert "`v2026.11.0` names" in details.read_text()
    # It only reports: the tag is still there.
    assert [t.name for t in _tags.release_tags()] == ["v2026.11.0"]


def _staleness(details: Path) -> int:
    return int(_rel.main(["staleness", "--details-file", str(details)]))


@pytest.mark.spec("DOCBW-07-008", "DOCBW-07-015")
def test_staleness_reads_the_clone(repo: Path, tmp_path: Path) -> None:
    details = tmp_path / "stale.md"
    assert _staleness(details) == 1  # no publish at all
    assert "no `publish-*` tag" in details.read_text()
    tag_as_bot(repo, "publish-2026-10-29.1", when="2026-10-29T06:10:00+00:00")
    # A publish pushed by hand later does not count as one.
    git(
        repo, "tag", "-a", "publish-2026-11-04.1", "-m", "x",
        when="2026-11-04T06:10:00+00:00",
    )  # fmt: skip
    assert _staleness(details) == 0  # main has nothing new
    commit(repo, "Wednesday", when="2026-11-04T15:00:00+00:00")
    assert _staleness(details) == 0  # four weekdays behind
    commit(repo, "Thursday", when="2026-11-05T15:00:00+00:00")
    assert _staleness(details) == 1
    text = details.read_text()
    assert "`publish-2026-10-29.1`, is 5 weekdays older" in text
    assert "2 commits" in text
    # The next publish clears it.
    tag_as_bot(repo, "publish-2026-11-05.1", when="2026-11-05T16:00:00+00:00")
    assert _staleness(tmp_path / "again.md") == 0


# --- the workflows -------------------------------------------------------------------


def _jobs(path: Path) -> dict[str, Any]:
    return dict(load_workflow(path)["jobs"])


def _run_text(path: Path) -> str:
    return "\n".join(str(s.get("run", "")) for s in steps(load_workflow(path)))


def _checkout(path: Path) -> dict[str, Any]:
    (step,) = [
        s
        for s in steps(load_workflow(path))
        if str(s.get("uses", "")).startswith("actions/checkout@")
    ]
    return dict(step.get("with", {}))


def _job_checkouts(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(s.get("with", {}))
        for s in job["steps"]
        if str(s.get("uses", "")).startswith("actions/checkout@")
    ]


@pytest.mark.spec("DOCBW-07-001", "DOCBW-07-004", "DOCBW-07-005")
def test_promote_workflow() -> None:
    wf = load_workflow(PROMOTE)
    on = triggers(wf)
    assert set(on) == {"workflow_dispatch"}
    inputs = on["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"publish-tag"}
    assert inputs["publish-tag"]["default"] == ""
    assert wf["permissions"] == {"contents": "read"}
    assert wf["concurrency"] == {
        "group": "promote-release",
        "cancel-in-progress": False,
    }
    jobs = _jobs(PROMOTE)
    # Only the job that pushes the tag and creates the release can write.
    assert {n: j.get("permissions") for n, j in jobs.items()} == {
        "plan": {"contents": "read"},
        "frozen-draft": {"contents": "read"},
        # It also reads the run's artifact list, to find the archive.
        "promote": {"contents": "write", "actions": "read"},
    }
    # Both deciding jobs read main's full history and every tag.
    for name in ("plan", "promote"):
        assert _job_checkouts(jobs[name]) == [
            {"fetch-depth": 0, "fetch-tags": True}
        ]
    for name, command in (
        ("plan", "release.py plan"),
        ("promote", "release.py promote"),
    ):
        (step,) = [
            s for s in jobs[name]["steps"] if command in str(s.get("run"))
        ]
        assert step["env"]["REF"] == "${{ github.ref }}"
        assert '--ref "$REF"' in step["run"]


@pytest.mark.spec("DOCBW-07-007", "DOCBW-07-014")
def test_release_tag_check_workflow() -> None:
    wf = load_workflow(CHECK)
    assert triggers(wf) == {"push": {"tags": ["v*"]}}
    assert wf["permissions"] == {"contents": "read"}
    assert {n: j.get("permissions") for n, j in _jobs(CHECK).items()} == {
        "check": {"contents": "read", "issues": "write"}
    }
    # main's script, whatever commit the tag names.
    assert _checkout(CHECK) == {
        "ref": "main",
        "fetch-depth": 0,
        "fetch-tags": True,
    }
    assert "release.py check" in _run_text(CHECK)
    _assert_notify_pair(
        CHECK,
        "ci:workflow-release-tag-check",
        "unpublished-release.md",
        close_if="success() && steps.check.outputs.checked == 'true'",
    )
    assert wf["concurrency"] == {
        "group": "release-tag-check",
        "cancel-in-progress": False,
    }


@pytest.mark.spec("DOCBW-07-008", "DOCBW-07-015")
def test_staleness_workflow() -> None:
    wf = load_workflow(STALENESS)
    on = triggers(wf)
    assert set(on) == {"schedule", "workflow_run", "workflow_dispatch"}
    assert on["schedule"] == [{"cron": "37 9 * * 1-5"}]
    # It checks again after every publish, so a publish closes the alarm.
    assert on["workflow_run"] == {
        "workflows": [load_workflow(PUBLISH)["name"]],
        "types": ["completed"],
    }
    assert STALENESS in _qualifying_workflow_files()
    assert wf["permissions"] == {"contents": "read"}
    assert {n: j.get("permissions") for n, j in _jobs(STALENESS).items()} == {
        "check": {"contents": "read", "issues": "write"}
    }
    assert _checkout(STALENESS) == {
        "ref": "main",
        "fetch-depth": 0,
        "fetch-tags": True,
    }
    assert "release.py staleness" in _run_text(STALENESS)
    _assert_notify_pair(
        STALENESS, "ci:workflow-site-staleness", "stale-site.md"
    )


def _assert_notify_pair(
    path: Path, label: str, details: str, close_if: str = "success()"
) -> None:
    """One notify step on failure, with the details, and one close on success."""
    wf = load_workflow(path)
    assert _reporting_violations(wf) == []
    notify_steps = [
        s
        for s in steps(wf)
        if s.get("uses") == "./.github/actions/notify-failure"
    ]
    by_mode = {s["with"]["mode"]: s for s in notify_steps}
    assert set(by_mode) == {"notify", "close"} and len(notify_steps) == 2
    assert by_mode["notify"]["if"] == "failure()"
    assert by_mode["close"]["if"] == close_if
    assert {s["with"]["workflow-label"] for s in notify_steps} == {label}
    assert by_mode["notify"]["with"]["details-file"] == details
    assert f"--details-file {details}" in _run_text(path)


@pytest.mark.spec("CISEC-01-001", "CISEC-01-002")
@pytest.mark.parametrize("wf", NEW_WORKFLOWS, ids=lambda p: p.name)
def test_new_workflows_pin_every_action(wf: Path) -> None:
    lines = _uses_lines(wf)
    assert lines, f"{wf.name} uses no external action, so nothing was checked"
    for _, line in lines:
        assert _SHA_RE.search(line.split("#")[0]), line
        assert _VERSION_COMMENT_RE.search(line), line


@pytest.mark.parametrize("wf", NEW_WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_a_timeout(wf: Path) -> None:
    for name, job in _jobs(wf).items():
        assert job.get("timeout-minutes"), f"{wf.name}: job {name} has no cap"
