#!/usr/bin/env python3
"""Decide whether a run of the publish workflow publishes, and tag what it did.

The publish workflow (``deploy_site.yml``, ADR-0171, DOCBW-06) deploys the
site from ``publish-YYYY-MM-DD.N`` tags. This script holds its logic, so the
workflow only wires jobs together. Every run starts from ``main``, so the
workflow and this script are always ``main``'s reviewed copies:

- ``gate`` classifies the run (scheduled, manual, manual with the CI gate
  skipped, rollback, release), picks the commit to publish, applies the skip
  rule and the CI gate, and writes ``publish``, ``trigger``, ``commit`` and
  ``tag-message`` to ``$GITHUB_OUTPUT`` and its reason to
  ``$GITHUB_STEP_SUMMARY``. A run that publishes also decides the name of its
  ``publish-*`` tag and writes it, its date and the commit's newest ``v*``
  release tag as ``publish-tag``, ``publish-date`` and ``release-tag``, so the
  build can print them in every page's footer (DOCBW-06-031). A skip is a
  green run, never a failure; a run it cannot serve (an unknown rollback
  target, a manual run off ``main``, a ``release`` input that the dispatcher
  did not set or that names no published release) fails.
- ``tag`` creates the annotated ``publish-*`` tag the gate named on the
  deployed commit and pushes it. It never renumbers: a name taken in between
  fails the job, since the deployed footer names the gate's tag. It only ever
  creates a tag: nothing here moves or deletes one, which the tag ruleset
  would refuse (#5545). A re-run of the same workflow run finds the tag it
  already pushed instead of making a second.

The decisions (``classify_trigger``, ``resolve_rollback``,
``blocking_issues``, ``pending_runs``, ``tag_message``, ``wait_for_runs``,
``decide``) are pure or take their I/O as arguments, so the test suite pins
them without GitHub; the rest is thin ``gh`` and ``git`` plumbing. Every tag
query (which ``publish-*`` tags count, the next tag name) comes from
``release_tags``, the helper the promote workflow, the release tag check and
the staleness alarm share.

Usage:
  publish_gate.py gate --repo OWNER/NAME --sha SHA --event EVENT --ref REF
      --actor LOGIN --run-id ID [--skip-ci-gate true|false] [--rollback-to TAG]
      [--release TAG]
  publish_gate.py tag --sha SHA --name TAG --message TEXT --run-url URL
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gh_cli import (  # see gh_cli
    CALL_TIMEOUT_SECONDS,
    gh,
    run,
    write_github_file,
)
from github_releases import ReleaseState, release_state
from release_tags import (
    BOT_GIT_IDENTITY,
    BOT_NAME,
    PUBLISH_PREFIX,
    PUBLISH_TAG_RE,
    Tag,
    latest_release,
    next_publish_name,
    publish_tags,
    publish_tags_on,
    read_tag_message,
    release_tags_on,
    release_version,
    split_publish_tags,
    tag_commit,
    tag_object,
    workflow_publish_tags_on,
)

MAIN_REF = "refs/heads/main"
# When the workflow's schedule starts a publish: 06:07 UTC, Monday to Friday
# (DOCBW-06-007). A test holds ``deploy_site.yml``'s cron to SCHEDULE_CRON,
# so the workflow and ``next_scheduled_publish`` agree on the time.
SCHEDULE_HOUR_UTC = 6
SCHEDULE_MINUTE_UTC = 7
# Monday to Friday: Python counts Monday as 0, cron as 1.
SCHEDULE_WEEKDAYS = frozenset(range(5))
SCHEDULE_CRON = f"{SCHEDULE_MINUTE_UTC} {SCHEDULE_HOUR_UTC} * * 1-5"
FAILURE_LABEL = "ci:main-failure"
# Wait this long for unfinished blocking runs, then skip.
WAIT_SECONDS = 3600
POLL_SECONDS = 60
# Workflow-run statuses that mean "not finished yet".
PENDING_STATUSES = frozenset(
    {"queued", "in_progress", "waiting", "requested", "pending"}
)

# What a rollback may name: a publish tag, or a release tag (ADR-0006).
_ROLLBACK_TAG_RE = re.compile(r"^(publish-\d{4}-\d{2}-\d{2}\.\d+|v\d\S*)$")
# The local actions the build job loads from the commit it builds, not from
# main: a commit without them cannot be built the way every publish is built
# (DOCBW-06-004), so a rollback to it is refused before anything runs
# (DOCBW-06-030). The frozen-draft serving step is one of them: a commit
# older than it cannot serve the released drafts (DOCBW-08-038).
BUILD_ACTIONS = (
    ".github/actions/setup-python-uv/action.yml",
    ".github/actions/check-site-publication/action.yml",
    ".github/actions/serve-frozen-drafts/action.yml",
)


def next_scheduled_publish(now: datetime) -> datetime:
    """When, in UTC, the first scheduled publish after *now* starts.

    A weekday before 06:07 UTC is that day's publish; any later time, and a
    weekend, is the next weekday's. The draft release command predicts a
    released draft's date with it (DOCBW-08-043): the publish of the commit
    that marks the draft released is the next scheduled one after that
    commit merges, so the merge must land before this time.

    Raises:
        ValueError: If *now* has no time zone, so it names no UTC instant.
    """
    if now.tzinfo is None:
        raise ValueError(f"{now!r} has no time zone")
    utc = now.astimezone(UTC)
    start = utc.replace(
        hour=SCHEDULE_HOUR_UTC,
        minute=SCHEDULE_MINUTE_UTC,
        second=0,
        microsecond=0,
    )
    if start <= utc:
        start += timedelta(days=1)
    while start.weekday() not in SCHEDULE_WEEKDAYS:
        start += timedelta(days=1)
    return start


class Trigger(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    MANUAL_UNGATED = "manual-ungated"
    ROLLBACK = "rollback"
    # Dispatched by publish_after_release.yml once a release is published
    # (DOCBW-06-032).
    RELEASE = "release"


class UnsupportedRunError(ValueError):
    """The run asks for something the publish workflow does not serve."""


class TagNameTakenError(RuntimeError):
    """The ``publish-*`` name the gate chose was taken before the tag job ran."""


@dataclass(frozen=True)
class BlockingWorkflow:
    """A workflow whose red state on ``main`` blocks a publish."""

    path: str
    label: str


@dataclass(frozen=True)
class RunContext:
    """What one run of the publish workflow was asked to do.

    ``sha`` is the commit to publish: the tip of ``main`` the run started on,
    or a rollback's target. ``source_tag`` is a rollback's target tag, or the
    release a release run publishes after.
    """

    trigger: Trigger
    sha: str
    actor: str
    source_tag: str = ""


@dataclass
class Decision:
    """The gate's verdict, and the lines it writes to the run summary."""

    publish: bool
    reason: str
    notes: list[str] = field(default_factory=list)


# --- pure decisions -----------------------------------------------------------


def classify_trigger(
    event: str,
    ref: str,
    skip_ci_gate: bool,
    rollback_to: str = "",
    *,
    release: str = "",
    actor: str = "",
) -> Trigger:
    """What kind of run this is, from its event, ref, inputs and actor.

    A scheduled run publishes ``main``. A manual run must start from ``main``,
    so the workflow that runs is ``main``'s reviewed copy, never one stored at
    a tag (ADR-0171); it rolls back when it names a ``rollback-to`` tag, and
    publishes ``main`` otherwise. Anything else is refused.

    A ``release`` input marks the publish that ``publish_after_release.yml``
    dispatches once a release is published. It only labels the run, but a
    false label is a false record in the tag message, so only that workflow's
    token (``github-actions[bot]``) may set it, never with another input
    (DOCBW-06-034). Whether the release is published is checked separately,
    by ``require_published_release``.
    """
    if event == "schedule":
        return Trigger.SCHEDULED
    if event != "workflow_dispatch":
        raise UnsupportedRunError(f"event {event!r} does not publish")
    if ref != MAIN_REF:
        raise UnsupportedRunError(
            f"a manual run starts from main, not {ref!r}; to roll back, "
            "start from main and name the tag in rollback-to"
        )
    if release:
        return _release_trigger(release, actor, skip_ci_gate, rollback_to)
    if rollback_to:
        if not _ROLLBACK_TAG_RE.match(rollback_to):
            raise UnsupportedRunError(
                f"rollback-to {rollback_to!r} is not a {PUBLISH_PREFIX}* or v* tag"
            )
        return Trigger.ROLLBACK
    return Trigger.MANUAL_UNGATED if skip_ci_gate else Trigger.MANUAL


def _release_trigger(
    release: str, actor: str, skip_ci_gate: bool, rollback_to: str
) -> Trigger:
    if actor != BOT_NAME:
        raise UnsupportedRunError(
            f"only {BOT_NAME}, for publish_after_release.yml, sets the release "
            f"input, not @{actor}; start a manual publish without it"
        )
    if rollback_to or skip_ci_gate:
        raise UnsupportedRunError(
            "a release run publishes main's tip through the CI gate, so it "
            "takes neither rollback-to nor skip-ci-gate"
        )
    if release_version(release) is None:
        raise UnsupportedRunError(f"release {release!r} is not a v* tag")
    return Trigger.RELEASE


def require_published_release(
    release: str, state: Callable[[str], ReleaseState | None]
) -> None:
    """Refuse a release run whose *release* is not a published GitHub Release.

    The gate's token can read only published releases, so a draft arrives
    as ``None``; a token that can push sees ``is_draft`` (DOCBW-06-034).
    """
    found = state(release)
    if found is None:
        raise UnsupportedRunError(
            f"{release} names no published release, so this is no publish "
            "after a release"
        )
    if found.is_draft:
        raise UnsupportedRunError(
            f"the release {release} is still a draft, so this is no publish "
            "after a release"
        )


def resolve_rollback(
    tag: str,
    main_sha: str,
    *,
    tag_commit: Callable[[str], str | None],
    on_main: Callable[[str, str], bool],
    missing_actions: Callable[[str], list[str]],
) -> str:
    """The commit a rollback to *tag* redeploys.

    Anyone who can push can create a tag (#5545), so a tag alone is no sign
    of review. Only a commit already in ``main``'s history is redeployed, and
    only one that carries the ``BUILD_ACTIONS`` its build loads: an older
    release would pass the gate and then fail in the build.
    """
    commit = tag_commit(tag)
    if commit is None:
        raise UnsupportedRunError(f"rollback-to names no tag {tag!r}")
    if not on_main(commit, main_sha):
        raise UnsupportedRunError(
            f"{tag!r} points at {commit}, which is not on main"
        )
    if missing := missing_actions(commit):
        raise UnsupportedRunError(
            f"{tag!r} points at {commit}, which predates the build this "
            f"workflow runs: it has no {', '.join(missing)}"
        )
    return commit


def _why_ignored(tag: Tag) -> str:
    if not tag.annotated:
        return "a lightweight tag, with no tagger."
    if not tag.made_by_workflow:
        return f"tagged by {tag.tagger_name or 'nobody'}, not {BOT_NAME}."
    return f"not a {PUBLISH_PREFIX}YYYY-MM-DD.N name."


def blocking_issues(
    issues: Iterable[dict[str, object]],
    blocking: Sequence[BlockingWorkflow],
) -> list[tuple[int, str]]:
    """Open failure issues of blocking workflows, as ``(number, label)``.

    *issues* are open ``ci:main-failure`` issues from the list-issues REST
    endpoint. A pull request on that endpoint, or an issue whose workflow is
    not in the blocking list, does not block.
    """
    labels = {w.label for w in blocking}
    found: list[tuple[int, str]] = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        names = _label_names(issue.get("labels"))
        if FAILURE_LABEL not in names:
            continue
        found.extend(
            (int(str(issue["number"])), label)
            for label in sorted(names & labels)
        )
    return sorted(found)


def _label_names(labels: object) -> set[str]:
    if not isinstance(labels, list):
        return set()
    return {
        str(label["name"]) if isinstance(label, dict) else str(label)
        for label in labels
        if isinstance(label, (dict, str))
    }


def _workflow_path(run_: dict[str, object]) -> str:
    """A run's workflow file path, without any ``@ref`` suffix."""
    return str(run_.get("path", "")).split("@", 1)[0]


def pending_runs(
    runs: Iterable[dict[str, object]],
    blocking: Sequence[BlockingWorkflow],
    own_run_id: int,
    in_history: Callable[[str], bool],
) -> list[str]:
    """Unfinished blocking-workflow runs on the candidate or an earlier commit.

    A run that has not finished may yet turn its workflow red, so the gate
    cannot read its verdict. Push CI is path-filtered, so the run that judges
    the candidate's code may be on an earlier commit than the candidate
    itself; *in_history* says whether a run's commit is the candidate or one
    of its ancestors. Runs of non-blocking workflows, runs on later commits,
    and this run itself cannot change the verdict and are not waited for.
    """
    paths = {w.path for w in blocking}
    return sorted(
        str(run_.get("name") or _workflow_path(run_))
        for run_ in runs
        if run_.get("id") != own_run_id
        and _workflow_path(run_) in paths
        and run_.get("status") in PENDING_STATUSES
        and in_history(str(run_.get("head_sha", "")))
    )


def tag_message(ctx: RunContext, run_url: str) -> str:
    """The annotated tag's message: what started the publish, and who.

    The ``Run:`` line also lets a re-run of the tag job find the tag its
    first attempt pushed.
    """
    first = {
        Trigger.SCHEDULED: f"scheduled publish, by {BOT_NAME}.",
        Trigger.MANUAL: f"manual publish, by @{ctx.actor}.",
        Trigger.MANUAL_UNGATED: (
            f"manual publish with the CI gate skipped, by @{ctx.actor}."
        ),
        Trigger.ROLLBACK: f"rollback to {ctx.source_tag}, by @{ctx.actor}.",
        # Only the bot starts a release run (DOCBW-06-034).
        Trigger.RELEASE: (
            f"publish after release {ctx.source_tag}, by {BOT_NAME}."
        ),
    }[ctx.trigger]
    return f"{first}\n\nCommit: {ctx.sha}\n{_run_line(run_url)}\n"


def _run_line(run_url: str) -> str:
    return f"Run: {run_url}"


def wait_for_runs(
    poll: Callable[[], list[str]],
    *,
    wait_seconds: int = WAIT_SECONDS,
    poll_seconds: int = POLL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[str]:
    """Poll until no blocking run is pending or *wait_seconds* pass.

    Returns the runs still pending when the wait ran out, or ``[]``.
    """
    deadline = clock() + wait_seconds
    while pending := poll():
        remaining = deadline - clock()
        if remaining <= 0:
            return pending
        sleep(min(poll_seconds, remaining))
    return []


def decide(
    ctx: RunContext,
    *,
    tags_on_commit: Callable[[], list[Tag]],
    open_blocking_issues: Callable[[], list[tuple[int, str]]],
    still_pending: Callable[[], list[str]],
) -> Decision:
    """Apply the skip rule and the CI gate to one run (ADR-0171, DOCBW-06).

    A rollback skips both. Only a scheduled run applies the skip rule; a
    manual run is a deliberate request to publish, and a release run must
    publish even when the morning's publish already took ``main``'s tip,
    because only now is the release's frozen draft served (DOCBW-06-035).
    The CI gate runs for scheduled, manual and release runs unless a manual
    run asked to skip it. Issues are read
    before and after the wait, since a run that finishes during the wait may
    file one.
    """
    if ctx.trigger is Trigger.ROLLBACK:
        return Decision(
            True,
            f"rollback to `{ctx.source_tag}` ({ctx.sha}); "
            "the CI gate is skipped.",
        )
    notes: list[str] = []
    own, ignored = split_publish_tags(tags_on_commit())
    notes.extend(f"Ignored `{t.name}`: {_why_ignored(t)}" for t in ignored)
    if own:
        names = ", ".join(f"`{t.name}`" for t in own)
        if ctx.trigger is Trigger.SCHEDULED:
            return Decision(
                False, f"{ctx.sha} is already published as {names}.", notes
            )
        notes.append(f"{ctx.sha} was already published as {names}.")
    if ctx.trigger is Trigger.MANUAL_UNGATED:
        return Decision(True, "manual publish; the CI gate is skipped.", notes)
    blocked = open_blocking_issues()
    if not blocked:
        stuck = still_pending()
        if stuck:
            return Decision(
                False,
                "runs still unfinished after the wait: "
                + ", ".join(stuck)
                + ".",
                notes,
            )
        blocked = open_blocking_issues()
    if blocked:
        return Decision(
            False,
            "blocked by "
            + ", ".join(f"#{n} ({label})" for n, label in blocked)
            + ".",
            notes,
        )
    return Decision(True, f"{ctx.trigger} publish; main CI is green.", notes)


def parse_blocking(text: str) -> list[BlockingWorkflow]:
    """Parse the blocking list: one ``<workflow path> <label>`` per line."""
    blocking: list[BlockingWorkflow] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        path, _, label = line.strip().partition(" ")
        if not path or not label.strip():
            raise ValueError(
                f"blocking list line {line!r} is not 'path label'"
            )
        blocking.append(BlockingWorkflow(path, label.strip()))
    if not blocking:
        raise ValueError("the blocking list is empty")
    return blocking


# --- plumbing -----------------------------------------------------------------


def _json_stream(text: str) -> list[dict[str, object]]:
    """Every JSON value in *text*, whether one per line or pretty-printed."""
    decoder = json.JSONDecoder()
    values: list[dict[str, object]] = []
    index = 0
    while (index := _skip_space(text, index)) < len(text):
        value, index = decoder.raw_decode(text, index)
        values.append(value)
    return values


def _skip_space(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def list_failure_issues(repo: str) -> list[dict[str, object]]:
    # The list endpoint, never the search index, which lags (#5105).
    return _json_stream(
        gh(
            "api",
            "--paginate",
            f"repos/{repo}/issues?labels={FAILURE_LABEL}&state=open&per_page=100",
            "--jq",
            ".[] | {number, labels: [.labels[].name], pull_request}"
            " | with_entries(select(.value != null))",
        )
    )


def list_main_runs(repo: str) -> list[dict[str, object]]:
    """The newest runs on ``main``: every unfinished run is among them."""
    return _json_stream(
        gh(
            "api",
            f"repos/{repo}/actions/runs?branch=main&per_page=100",
            "--jq",
            ".workflow_runs[] | {id, name, path, status, head_sha}",
        )
    )


def is_in_history(commit: str, tip: str) -> bool:
    """Whether *commit* is *tip* or one of its ancestors in this clone.

    The clone holds *tip*'s whole history, so a commit it does not know is
    not in that history.
    """
    if not commit:
        return False
    return (
        subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "merge-base", "--is-ancestor", commit, tip],  # noqa: S607
            capture_output=True,
            check=False,
            timeout=CALL_TIMEOUT_SECONDS,
        ).returncode
        == 0
    )


def missing_build_actions(commit: str) -> list[str]:
    """The ``BUILD_ACTIONS`` that *commit*'s tree does not have."""
    return [
        path
        for path in BUILD_ACTIONS
        if subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "cat-file", "-e", f"{commit}:{path}"],  # noqa: S607
            capture_output=True,
            check=False,
            timeout=CALL_TIMEOUT_SECONDS,
        ).returncode
        != 0
    ]


def _remote_tags() -> dict[str, str]:
    """The remote's ``publish-*`` tags, by name, with their object ids."""
    out = run(
        "git", "ls-remote", "--tags", "origin", f"refs/tags/{PUBLISH_PREFIX}*"
    )
    tags: dict[str, str] = {}
    for line in out.splitlines():
        oid, _, ref = line.partition("\t")
        if ref and not ref.endswith("^{}"):
            tags[ref.removeprefix("refs/tags/")] = oid
    return tags


def next_publish_tag(day: str) -> str:
    """The name the next publish on *day* takes, from local and remote tags.

    The remote is read too because the gate may wait an hour for CI after
    its checkout, and a tag pushed meanwhile must not be reused.
    """
    local = [t.name for t in publish_tags()]
    return next_publish_name(day, [*local, *_remote_tags()])


def release_tag_on(sha: str) -> str:
    """The newest version-shaped ``v*`` tag on *sha*, or ``""``."""
    return latest_release(t.name for t in release_tags_on(sha)) or ""


def _pushed_by_this_run(name: str, sha: str, run_url: str, oid: str) -> bool:
    """Whether the remote's *name*, object *oid*, is this run's tag on *sha*."""
    if tag_object(name) != oid:
        return False
    return (
        any(tag.name == name for tag in workflow_publish_tags_on(sha))
        and _run_line(run_url) in read_tag_message(name).splitlines()
    )


def create_tag(sha: str, name: str, message: str, run_url: str) -> str:
    """Create and push the annotated ``publish-*`` tag *name* on *sha*.

    *name* is the one the gate chose and the build printed in every page's
    footer (DOCBW-06-031), so it is created exactly or not at all. A re-run
    of the same workflow run returns the tag the first attempt pushed. The
    concurrency group keeps two runs of this workflow apart, but anyone can
    create a ``publish-*`` tag: a name taken by anything else raises
    ``TagNameTakenError`` instead of renumbering to a name the deployed site
    does not show. A push that reports failure but landed is recognised by
    its object id, so it is never pushed twice. Any other push failure
    raises. No tag is ever moved or deleted, here or on the remote.
    """
    if not PUBLISH_TAG_RE.match(name):
        raise ValueError(
            f"{name!r} is not a {PUBLISH_PREFIX}YYYY-MM-DD.N name"
        )
    if (oid := _remote_tags().get(name)) is not None:
        if _pushed_by_this_run(name, sha, run_url, oid):
            return name
        raise TagNameTakenError(
            f"{name} was taken on the remote after the gate chose it, so the "
            "deployed site's footer names a tag this publish did not make"
        )
    run(
        "git",
        *BOT_GIT_IDENTITY,
        "tag",
        "--annotate",
        name,
        "--message",
        message,
        sha,
    )
    try:
        run("git", "push", "origin", f"refs/tags/{name}")
    except subprocess.CalledProcessError:
        remote = _remote_tags().get(name)
        if remote is not None and remote == tag_object(name):
            return name
        if remote is not None:
            raise TagNameTakenError(
                f"{name} was taken on the remote while this run pushed it"
            ) from None
        raise
    return name


def _summary(decision: Decision) -> str:
    verdict = "Publishing" if decision.publish else "Skipped"
    lines = [f"### Publish gate: {verdict}", "", decision.reason, ""]
    lines += [f"- {note}" for note in decision.notes]
    return "\n".join(lines) + "\n"


def _run_url(repo: str, run_id: int) -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server}/{repo}/actions/runs/{run_id}"


def cmd_gate(args: argparse.Namespace) -> int:
    try:
        trigger = classify_trigger(
            args.event,
            args.ref,
            args.skip_ci_gate == "true",
            args.rollback_to,
            release=args.release,
            actor=args.actor,
        )
        if trigger is Trigger.RELEASE:
            require_published_release(
                args.release,
                lambda name: release_state(args.repo, name, retry=True),
            )
        commit = (
            resolve_rollback(
                args.rollback_to,
                args.sha,
                tag_commit=tag_commit,
                on_main=is_in_history,
                missing_actions=missing_build_actions,
            )
            if trigger is Trigger.ROLLBACK
            else args.sha
        )
    except UnsupportedRunError as error:
        print(f"::error::{error}", file=sys.stderr)
        write_github_file(
            "GITHUB_STEP_SUMMARY", f"### Publish gate: refused\n\n{error}\n"
        )
        return 1
    blocking = parse_blocking(os.environ.get("BLOCKING_WORKFLOWS", ""))
    ctx = RunContext(
        trigger=trigger,
        sha=commit,
        actor=args.actor,
        source_tag={
            Trigger.ROLLBACK: args.rollback_to,
            Trigger.RELEASE: args.release,
        }.get(trigger, ""),
    )
    decision = decide(
        ctx,
        tags_on_commit=lambda: publish_tags_on(commit),
        open_blocking_issues=lambda: blocking_issues(
            list_failure_issues(args.repo), blocking
        ),
        still_pending=lambda: wait_for_runs(
            lambda: pending_runs(
                list_main_runs(args.repo),
                blocking,
                args.run_id,
                lambda head: is_in_history(head, commit),
            )
        ),
    )
    message = tag_message(ctx, _run_url(args.repo, args.run_id))
    day = publish_tag = release_tag = ""
    if decision.publish:
        # Named after the wait, so the counter sees every tag made during it.
        day = _utc_today()
        publish_tag = next_publish_tag(day)
        release_tag = release_tag_on(commit)
        decision.notes.append(f"The publish will be tagged `{publish_tag}`.")
    print(_summary(decision))
    write_github_file("GITHUB_STEP_SUMMARY", _summary(decision))
    write_github_file(
        "GITHUB_OUTPUT",
        f"publish={'true' if decision.publish else 'false'}\n"
        f"trigger={trigger}\n"
        f"commit={commit}\n"
        f"publish-tag={publish_tag}\n"
        f"publish-date={day}\n"
        f"release-tag={release_tag}\n"
        f"tag-message<<EOF_TAG_MESSAGE\n{message}EOF_TAG_MESSAGE\n",
    )
    return 0


def _utc_today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def cmd_tag(args: argparse.Namespace) -> int:
    name = create_tag(args.sha, args.name, args.message, args.run_url)
    print(f"Tagged {args.sha} as {name}")
    write_github_file("GITHUB_STEP_SUMMARY", f"Published as `{name}`.\n")
    write_github_file("GITHUB_OUTPUT", f"tag={name}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decide whether the publish workflow publishes; tag it."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    gate = sub.add_parser("gate")
    gate.add_argument("--repo", required=True)
    gate.add_argument("--sha", required=True)
    gate.add_argument("--event", required=True)
    gate.add_argument("--ref", required=True)
    gate.add_argument("--actor", required=True)
    gate.add_argument("--run-id", required=True, type=int)
    gate.add_argument("--skip-ci-gate", default="false")
    gate.add_argument("--rollback-to", default="")
    gate.add_argument("--release", default="")
    gate.set_defaults(func=cmd_gate)
    tag = sub.add_parser("tag")
    tag.add_argument("--sha", required=True)
    tag.add_argument("--name", required=True)
    tag.add_argument("--message", required=True)
    tag.add_argument("--run-url", required=True)
    tag.set_defaults(func=cmd_tag)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
