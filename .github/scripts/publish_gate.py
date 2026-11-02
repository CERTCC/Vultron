#!/usr/bin/env python3
"""Decide whether a run of the publish workflow publishes, and tag what it did.

The publish workflow (``deploy_site.yml``, ADR-0169, DOCBW-06) deploys the
site from ``publish-YYYY-MM-DD.N`` tags. This script holds its logic, so the
workflow only wires jobs together. Every run starts from ``main``, so the
workflow and this script are always ``main``'s reviewed copies:

- ``gate`` classifies the run (scheduled, manual, manual with the CI gate
  skipped, rollback), picks the commit to publish, applies the skip rule and
  the CI gate, and writes ``publish``, ``trigger``, ``commit`` and
  ``tag-message`` to ``$GITHUB_OUTPUT`` and its reason to
  ``$GITHUB_STEP_SUMMARY``. A skip is a green run, never a failure; a run it
  cannot serve (an unknown rollback target, a manual run off ``main``) fails.
- ``tag`` creates one annotated ``publish-*`` tag on the deployed commit and
  pushes it. It only ever creates a tag: nothing here moves or deletes one,
  which the tag ruleset would refuse (#5545). A re-run of the same workflow
  run finds the tag it already pushed instead of making a second.

The decisions (``classify_trigger``, ``resolve_rollback``,
``split_publish_tags``, ``blocking_issues``, ``pending_runs``,
``next_tag_name``, ``tag_message``, ``wait_for_runs``, ``decide``) are pure or
take their I/O as arguments, so the test suite pins them without GitHub; the
rest is thin ``gh`` and ``git`` plumbing.

Usage:
  publish_gate.py gate --repo OWNER/NAME --sha SHA --event EVENT --ref REF
      --actor LOGIN --run-id ID [--skip-ci-gate true|false] [--rollback-to TAG]
  publish_gate.py tag --sha SHA --message TEXT --run-url URL
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
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gh_cli import CALL_TIMEOUT_SECONDS, gh, run  # see gh_cli

TAG_PREFIX = "publish-"
MAIN_REF = "refs/heads/main"
# The identity this workflow tags as. git records it as the tagger of every
# annotated tag the workflow creates; the skip rule recognises a tag the
# workflow made by it (ADR-0169).
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
FAILURE_LABEL = "ci:main-failure"
# Wait this long for unfinished blocking runs, then skip.
WAIT_SECONDS = 3600
POLL_SECONDS = 60
# Workflow-run statuses that mean "not finished yet".
PENDING_STATUSES = frozenset(
    {"queued", "in_progress", "waiting", "requested", "pending"}
)
# A push of a freshly numbered tag can lose to a tag of the same name made in
# between; renumber and try again this many times.
TAG_PUSH_ATTEMPTS = 5

_TAG_NAME_RE = re.compile(r"^publish-(\d{4}-\d{2}-\d{2})\.(\d+)$")
# What a rollback may name: a publish tag, or a release tag (ADR-0006).
_ROLLBACK_TAG_RE = re.compile(r"^(publish-\d{4}-\d{2}-\d{2}\.\d+|v\d\S*)$")


class Trigger(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    MANUAL_UNGATED = "manual-ungated"
    ROLLBACK = "rollback"


class UnsupportedRunError(ValueError):
    """The run asks for something the publish workflow does not serve."""


@dataclass(frozen=True)
class BlockingWorkflow:
    """A workflow whose red state on ``main`` blocks a publish."""

    path: str
    label: str


@dataclass(frozen=True)
class PublishTag:
    """A ``publish-*`` tag on the candidate commit, as git records it."""

    name: str
    annotated: bool
    tagger_name: str = ""
    tagger_email: str = ""

    @property
    def made_by_workflow(self) -> bool:
        return (
            self.annotated
            and self.tagger_name == BOT_NAME
            and self.tagger_email == BOT_EMAIL
        )


@dataclass(frozen=True)
class RunContext:
    """What one run of the publish workflow was asked to do.

    ``sha`` is the commit to publish: the tip of ``main`` the run started on,
    or a rollback's target.
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
    event: str, ref: str, skip_ci_gate: bool, rollback_to: str = ""
) -> Trigger:
    """What kind of run this is, from its event, ref and inputs.

    A scheduled run publishes ``main``. A manual run must start from ``main``,
    so the workflow that runs is ``main``'s reviewed copy, never one stored at
    a tag (ADR-0169); it rolls back when it names a ``rollback-to`` tag, and
    publishes ``main`` otherwise. Anything else is refused.
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
    if rollback_to:
        if not _ROLLBACK_TAG_RE.match(rollback_to):
            raise UnsupportedRunError(
                f"rollback-to {rollback_to!r} is not a {TAG_PREFIX}* or v* tag"
            )
        return Trigger.ROLLBACK
    return Trigger.MANUAL_UNGATED if skip_ci_gate else Trigger.MANUAL


def resolve_rollback(
    tag: str,
    main_sha: str,
    *,
    tag_commit: Callable[[str], str | None],
    on_main: Callable[[str, str], bool],
) -> str:
    """The commit a rollback to *tag* redeploys.

    Anyone who can push can create a tag (#5545), so a tag alone is no sign
    of review. Only a commit already in ``main``'s history is redeployed.
    """
    commit = tag_commit(tag)
    if commit is None:
        raise UnsupportedRunError(f"rollback-to names no tag {tag!r}")
    if not on_main(commit, main_sha):
        raise UnsupportedRunError(
            f"{tag!r} points at {commit}, which is not on main"
        )
    return commit


def split_publish_tags(
    tags: Iterable[PublishTag],
) -> tuple[list[PublishTag], list[PublishTag]]:
    """Split tags into those this workflow made and those the skip rule ignores.

    Tag creation is unrestricted (#5545), so a ``publish-*`` tag anyone pushed
    must not suppress a publish: only an annotated tag whose tagger is
    ``github-actions[bot]`` counts.
    """
    own: list[PublishTag] = []
    ignored: list[PublishTag] = []
    for tag in tags:
        (own if tag.made_by_workflow else ignored).append(tag)
    return own, ignored


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


def next_tag_name(day: str, existing: Iterable[str]) -> str:
    """``publish-<day>.N`` with N one more than the highest for *day*, from 1."""
    taken = [
        int(m.group(2))
        for name in existing
        if (m := _TAG_NAME_RE.match(name)) and m.group(1) == day
    ]
    return f"{TAG_PREFIX}{day}.{max(taken, default=0) + 1}"


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
    tags_on_commit: Callable[[], list[PublishTag]],
    open_blocking_issues: Callable[[], list[tuple[int, str]]],
    still_pending: Callable[[], list[str]],
) -> Decision:
    """Apply the skip rule and the CI gate to one run (ADR-0169, DOCBW-06).

    A rollback skips both. Only a scheduled run applies the skip rule; a
    manual run is a deliberate request to publish. The CI gate runs for
    scheduled and manual runs unless the run asked to skip it. Issues are read
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
    notes.extend(
        f"Ignored `{t.name}`: "
        + (
            f"tagged by {t.tagger_name or 'nobody'}, not {BOT_NAME}."
            if t.annotated
            else "a lightweight tag, with no tagger."
        )
        for t in ignored
    )
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


def tag_commit(tag: str) -> str | None:
    """The commit *tag* points at in this clone, or ``None``."""
    try:
        return run(
            "git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"
        ).strip()
    except subprocess.CalledProcessError:
        return None


def publish_tags_on(sha: str) -> list[PublishTag]:
    """Every ``publish-*`` tag that points at *sha* in the local clone."""
    out = run(
        "git",
        "for-each-ref",
        f"--points-at={sha}",
        "--format=%(refname:strip=2)%09%(objecttype)%09%(taggername)"
        "%09%(taggeremail:trim)",
        f"refs/tags/{TAG_PREFIX}*",
    )
    tags: list[PublishTag] = []
    for line in out.splitlines():
        name, kind, tagger, email = [*line.split("\t"), "", "", ""][:4]
        tags.append(PublishTag(name, kind == "tag", tagger, email))
    return tags


def _remote_tags() -> dict[str, str]:
    """The remote's ``publish-*`` tags, by name, with their object ids."""
    out = run(
        "git", "ls-remote", "--tags", "origin", f"refs/tags/{TAG_PREFIX}*"
    )
    tags: dict[str, str] = {}
    for line in out.splitlines():
        oid, _, ref = line.partition("\t")
        if ref and not ref.endswith("^{}"):
            tags[ref.removeprefix("refs/tags/")] = oid
    return tags


def _tag_from_this_run(
    sha: str, run_url: str, remote: dict[str, str]
) -> str | None:
    """A tag this workflow run already pushed on *sha*, if a re-run finds one."""
    marker = _run_line(run_url)
    for tag in publish_tags_on(sha):
        if not tag.made_by_workflow or tag.name not in remote:
            continue
        message = run("git", "tag", "--list", "--format=%(contents)", tag.name)
        if marker in message.splitlines():
            return tag.name
    return None


def create_tag(
    sha: str, message: str, run_url: str, *, today: str | None = None
) -> str:
    """Create and push one annotated ``publish-*`` tag on *sha*; return it.

    A re-run of the same workflow run returns the tag the first attempt
    pushed. The concurrency group keeps two runs of this workflow apart, but
    anyone can create a ``publish-*`` tag, so a push can still find its name
    taken: then the tag is renumbered and pushed again. A push that reports
    failure but landed is recognised by its object id, so it is never pushed
    twice. Any other push failure raises. No tag is ever moved or deleted,
    here or on the remote.
    """
    day = today or datetime.now(UTC).strftime("%Y-%m-%d")
    if found := _tag_from_this_run(sha, run_url, _remote_tags()):
        return found
    as_bot = ("-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}")
    for attempt in range(1, TAG_PUSH_ATTEMPTS + 1):
        local = run("git", "tag", "--list", f"{TAG_PREFIX}*").split()
        name = next_tag_name(day, [*local, *_remote_tags()])
        run(
            "git",
            *as_bot,
            "tag",
            "--annotate",
            name,
            "--message",
            message,
            sha,
        )
        try:
            run("git", "push", "origin", f"refs/tags/{name}")
            return name
        except subprocess.CalledProcessError:
            remote = _remote_tags().get(name)
            if remote == run("git", "rev-parse", f"refs/tags/{name}").strip():
                return name
            if remote is None or attempt == TAG_PUSH_ATTEMPTS:
                raise
    raise AssertionError("unreachable")  # pragma: no cover


def _write(env_var: str, text: str) -> None:
    path = os.environ.get(env_var)
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)


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
            args.event, args.ref, args.skip_ci_gate == "true", args.rollback_to
        )
        commit = (
            resolve_rollback(
                args.rollback_to,
                args.sha,
                tag_commit=tag_commit,
                on_main=is_in_history,
            )
            if trigger is Trigger.ROLLBACK
            else args.sha
        )
    except UnsupportedRunError as error:
        print(f"::error::{error}", file=sys.stderr)
        _write(
            "GITHUB_STEP_SUMMARY", f"### Publish gate: refused\n\n{error}\n"
        )
        return 1
    blocking = parse_blocking(os.environ.get("BLOCKING_WORKFLOWS", ""))
    ctx = RunContext(
        trigger=trigger,
        sha=commit,
        actor=args.actor,
        source_tag=args.rollback_to if trigger is Trigger.ROLLBACK else "",
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
    print(_summary(decision))
    _write("GITHUB_STEP_SUMMARY", _summary(decision))
    _write(
        "GITHUB_OUTPUT",
        f"publish={'true' if decision.publish else 'false'}\n"
        f"trigger={trigger}\n"
        f"commit={commit}\n"
        f"tag-message<<EOF_TAG_MESSAGE\n{message}EOF_TAG_MESSAGE\n",
    )
    return 0


def cmd_tag(args: argparse.Namespace) -> int:
    name = create_tag(args.sha, args.message, args.run_url)
    print(f"Tagged {args.sha} as {name}")
    _write("GITHUB_STEP_SUMMARY", f"Published as `{name}`.\n")
    _write("GITHUB_OUTPUT", f"tag={name}\n")
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
    gate.set_defaults(func=cmd_gate)
    tag = sub.add_parser("tag")
    tag.add_argument("--sha", required=True)
    tag.add_argument("--message", required=True)
    tag.add_argument("--run-url", required=True)
    tag.set_defaults(func=cmd_tag)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
