#!/usr/bin/env python3
"""Decide whether a run of the publish workflow publishes, and tag what it did.

The publish workflow (``deploy_site.yml``, ADR-0169, DOCBW-06) deploys the
site from ``publish-YYYY-MM-DD.N`` tags. This script holds its logic, so the
workflow only wires steps together:

- ``gate`` classifies the run (scheduled, manual, manual with the CI gate
  skipped, rollback), applies the skip rule and the CI gate, and writes
  ``publish``, ``trigger`` and ``tag-message`` to ``$GITHUB_OUTPUT`` and its
  reason to ``$GITHUB_STEP_SUMMARY``. A skip is a green run, never a failure.
- ``tag`` creates one annotated ``publish-*`` tag on the deployed commit and
  pushes it. It only ever creates a tag: nothing here moves or deletes one,
  which the tag ruleset would refuse (#5545).

The decisions (``classify_trigger``, ``split_publish_tags``,
``blocking_issues``, ``pending_runs``, ``next_tag_name``, ``tag_message``,
``wait_for_runs``, ``decide``) are pure or take their I/O as arguments, so the
test suite pins them without GitHub; the rest is thin ``gh`` and ``git``
plumbing.

Usage:
  publish_gate.py gate --repo OWNER/NAME --sha SHA --event EVENT --ref REF
      --actor LOGIN --run-id ID [--skip-ci-gate true|false]
  publish_gate.py tag --sha SHA --message TEXT
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

TAG_PREFIX = "publish-"
# The identity this workflow tags as. git records it as the tagger of every
# annotated tag the workflow creates; the skip rule recognises a tag the
# workflow made by it (ADR-0169).
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
FAILURE_LABEL = "ci:main-failure"
# Wait this long for runs still going on the candidate commit, then skip.
WAIT_SECONDS = 3600
POLL_SECONDS = 60
# Workflow-run statuses that mean "not finished yet".
PENDING_STATUSES = frozenset(
    {"queued", "in_progress", "waiting", "requested", "pending"}
)
# A push of a freshly numbered tag can lose to a tag of the same name made in
# between; renumber and try again this many times.
TAG_PUSH_ATTEMPTS = 5
GH_ATTEMPTS = 3

_TAG_NAME_RE = re.compile(r"^publish-(\d{4}-\d{2}-\d{2})\.(\d+)$")


class Trigger(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    MANUAL_UNGATED = "manual-ungated"
    ROLLBACK = "rollback"


class UnsupportedRunError(ValueError):
    """The run's event or ref is not one the publish workflow serves."""


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
    """What one run of the publish workflow was asked to do."""

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


def classify_trigger(event: str, ref: str, skip_ci_gate: bool) -> Trigger:
    """What kind of run this is, from its event and the ref it runs on.

    A scheduled run publishes ``main``. A manual run publishes ``main``, or
    rolls back when started from a ``publish-*`` or ``v*`` tag. Anything else
    (a push, a manual run from another branch) is refused.
    """
    if event == "schedule":
        return Trigger.SCHEDULED
    if event != "workflow_dispatch":
        raise UnsupportedRunError(f"event {event!r} does not publish")
    if ref == "refs/heads/main":
        return Trigger.MANUAL_UNGATED if skip_ci_gate else Trigger.MANUAL
    tag = ref.removeprefix("refs/tags/")
    if tag != ref and (tag.startswith(TAG_PREFIX) or tag.startswith("v")):
        return Trigger.ROLLBACK
    raise UnsupportedRunError(
        f"a manual run publishes from main, or rolls back from a "
        f"{TAG_PREFIX}* or v* tag; {ref!r} is neither"
    )


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


def _workflow_path(run: dict[str, object]) -> str:
    """A run's workflow file path, without any ``@ref`` suffix."""
    return str(run.get("path", "")).split("@", 1)[0]


def pending_runs(
    runs: Iterable[dict[str, object]],
    blocking: Sequence[BlockingWorkflow],
    own_run_id: int,
) -> list[str]:
    """Names of unfinished blocking-workflow runs on the candidate commit.

    A run that has not finished may yet turn its workflow red, so the gate
    cannot read its verdict. Runs of non-blocking workflows, and this run
    itself, cannot change the verdict and are not waited for.
    """
    paths = {w.path for w in blocking}
    return sorted(
        str(run.get("name", _workflow_path(run)))
        for run in runs
        if run.get("id") != own_run_id
        and _workflow_path(run) in paths
        and run.get("status") in PENDING_STATUSES
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
    """The annotated tag's message: what started the publish, and who."""
    first = {
        Trigger.SCHEDULED: f"scheduled publish, by {BOT_NAME}.",
        Trigger.MANUAL: f"manual publish, by @{ctx.actor}.",
        Trigger.MANUAL_UNGATED: (
            f"manual publish with the CI gate skipped, by @{ctx.actor}."
        ),
        Trigger.ROLLBACK: f"rollback to {ctx.source_tag}, by @{ctx.actor}.",
    }[ctx.trigger]
    return f"{first}\n\nCommit: {ctx.sha}\nRun: {run_url}\n"


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
            True, f"rollback to `{ctx.source_tag}`; the CI gate is skipped."
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


def _run(*argv: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        list(argv), check=True, capture_output=True, text=True
    ).stdout


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


def _gh_lines(endpoint: str, jq: str) -> list[dict[str, object]]:
    """Each item of a paginated REST list, through *jq*, retried (bounded)."""
    for attempt in range(1, GH_ATTEMPTS + 1):
        try:
            return _json_stream(
                _run("gh", "api", "--paginate", endpoint, "--jq", jq)
            )
        except subprocess.CalledProcessError:
            if attempt == GH_ATTEMPTS:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")  # pragma: no cover


def list_failure_issues(repo: str) -> list[dict[str, object]]:
    # The list endpoint, never the search index, which lags (#5105).
    return _gh_lines(
        f"repos/{repo}/issues?labels={FAILURE_LABEL}&state=open&per_page=100",
        ".[] | {number, labels: [.labels[].name], pull_request}"
        " | with_entries(select(.value != null))",
    )


def list_runs(repo: str, sha: str) -> list[dict[str, object]]:
    return _gh_lines(
        f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100",
        ".workflow_runs[] | {id, name, path, status}",
    )


def publish_tags_on(sha: str) -> list[PublishTag]:
    """Every ``publish-*`` tag that points at *sha* in the local clone."""
    out = _run(
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


def _remote_tag_names() -> list[str]:
    out = _run(
        "git", "ls-remote", "--tags", "origin", f"refs/tags/{TAG_PREFIX}*"
    )
    return [
        line.split("\t", 1)[1].removeprefix("refs/tags/").removesuffix("^{}")
        for line in out.splitlines()
        if "\t" in line
    ]


def create_tag(sha: str, message: str, *, today: str | None = None) -> str:
    """Create and push one annotated ``publish-*`` tag on *sha*; return it.

    The concurrency group keeps two runs of this workflow apart, but anyone
    can create a ``publish-*`` tag, so a push can still find its name taken.
    The number is taken from the remote's tags and this clone's, so a push
    refused that way is renumbered and tried again; the refused tag stays in
    this clone only, and the next number skips it. No tag is ever moved or
    deleted, here or on the remote.
    """
    day = today or datetime.now(UTC).strftime("%Y-%m-%d")
    as_bot = ("-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}")
    for attempt in range(1, TAG_PUSH_ATTEMPTS + 1):
        local = _run("git", "tag", "--list", f"{TAG_PREFIX}*").split()
        name = next_tag_name(day, [*local, *_remote_tag_names()])
        _run(
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
            _run("git", "push", "origin", f"refs/tags/{name}")
        except subprocess.CalledProcessError:
            if attempt == TAG_PUSH_ATTEMPTS:
                raise
            continue
        return name
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


def cmd_gate(args: argparse.Namespace) -> int:
    try:
        trigger = classify_trigger(
            args.event, args.ref, args.skip_ci_gate == "true"
        )
    except UnsupportedRunError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    blocking = parse_blocking(os.environ.get("BLOCKING_WORKFLOWS", ""))
    ctx = RunContext(
        trigger=trigger,
        sha=args.sha,
        actor=args.actor,
        source_tag=(
            args.ref.removeprefix("refs/tags/")
            if trigger is Trigger.ROLLBACK
            else ""
        ),
    )
    decision = decide(
        ctx,
        tags_on_commit=lambda: publish_tags_on(args.sha),
        open_blocking_issues=lambda: blocking_issues(
            list_failure_issues(args.repo), blocking
        ),
        still_pending=lambda: wait_for_runs(
            lambda: pending_runs(
                list_runs(args.repo, args.sha), blocking, args.run_id
            )
        ),
    )
    run_url = (
        f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
        f"{args.repo}/actions/runs/{args.run_id}"
    )
    message = tag_message(ctx, run_url)
    print(_summary(decision))
    _write("GITHUB_STEP_SUMMARY", _summary(decision))
    _write(
        "GITHUB_OUTPUT",
        f"publish={'true' if decision.publish else 'false'}\n"
        f"trigger={trigger}\n"
        f"tag-message<<EOF_TAG_MESSAGE\n{message}EOF_TAG_MESSAGE\n",
    )
    return 0


def cmd_tag(args: argparse.Namespace) -> int:
    name = create_tag(args.sha, args.message)
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
    gate.set_defaults(func=cmd_gate)
    tag = sub.add_parser("tag")
    tag.add_argument("--sha", required=True)
    tag.add_argument("--message", required=True)
    tag.set_defaults(func=cmd_tag)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
