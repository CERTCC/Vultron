#!/usr/bin/env python3
"""Promote a publish to a release, check a release tag, and alarm on a stale site.

Three workflows run this script, each on ``main``'s copy (DOCBW-07):

- ``promote`` (``promote_release.yml``) turns a ``publish-*`` tag into the
  next ``vYYYY.M.P`` release tag (ADR-0006) on the same commit, then opens a
  draft GitHub Release whose notes are generated since the previous release.
  A tag the workflow's ``GITHUB_TOKEN`` pushes starts no other workflow, so
  the release tag check never sees it: promote checks its own input.
- ``check`` (``release_tag_check.yml``) fails when a ``v*`` tag pushed by
  hand names a commit with no publish, so ``notify-failure`` reports it. It
  only reports: it never blocks the tag and never deletes it.
- ``staleness`` (``site_staleness.yml``) fails when the newest publish is more
  than ``STALE_AFTER_WEEKDAYS`` weekdays older than the newest commit on
  ``main`` and ``main`` has commits the site does not show.

Every tag question goes through ``release_tags``, so each honours the publish
gate's tagger check. Tags are append-only (#5545): this script creates a
release tag and nothing else; it never moves or deletes one.

Usage:
  release.py promote --repo OWNER/NAME --ref REF --actor LOGIN --run-url URL
      [--publish-tag TAG]
  release.py check --tag TAG [--details-file PATH]
  release.py staleness [--details-file PATH]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gh_cli import gh, run, write_github_file  # see gh_cli
from publish_gate import MAIN_REF
from release_tags import (
    BOT_EMAIL,
    BOT_NAME,
    PUBLISH_PREFIX,
    PUBLISH_TAG_RE,
    RELEASE_TAG_RE,
    Tag,
    latest_release,
    newest_publish_tag,
    next_release_name,
    publish_tags,
    release_tags,
    release_version,
    workflow_publish_tags_on,
)

# The site is stale past this many weekdays behind main (DOCBW-07-008).
STALE_AFTER_WEEKDAYS = 4
# The statement every release's notes carry (CONTRIBUTING.md).
EXPERIMENTAL_NOTICE = "All interfaces in this release are experimental."


class PromotionRefusedError(ValueError):
    """The promote workflow was asked for something it does not do."""


@dataclass(frozen=True)
class Promotion:
    """What one promote run does.

    ``create_tag`` is false when the commit already carries the latest
    release tag but no release: a run whose release step failed left it,
    and this run drafts its release instead of tagging the commit twice.
    """

    source: Tag
    release: str
    previous: str | None
    create_tag: bool


# --- pure decisions -----------------------------------------------------------


def choose_publish_tag(requested: str, tags: Iterable[Tag]) -> Tag:
    """The publish to promote: *requested*, or the newest when it is empty.

    Refuses a name that is not an existing ``publish-*`` tag the publish
    workflow made, since anyone who can push can create one (#5545).
    """
    all_tags = list(tags)
    if not requested:
        newest = newest_publish_tag(all_tags)
        if newest is None:
            raise PromotionRefusedError(
                f"there is no {PUBLISH_PREFIX}* tag made by {BOT_NAME} to promote"
            )
        return newest
    if not PUBLISH_TAG_RE.match(requested):
        raise PromotionRefusedError(
            f"{requested!r} is not a {PUBLISH_PREFIX}YYYY-MM-DD.N tag name"
        )
    found = next((t for t in all_tags if t.name == requested), None)
    if found is None:
        raise PromotionRefusedError(f"there is no tag {requested!r}")
    if not found.is_publish:
        who = (
            f"tagged by {found.tagger_name or 'nobody'}"
            if found.annotated
            else "a lightweight tag"
        )
        raise PromotionRefusedError(
            f"{requested!r} is {who}, not a tag {BOT_NAME} made, "
            "so it does not name a publish"
        )
    return found


def _previous_release(names: Iterable[str], before: str) -> str | None:
    """The highest ``v*`` tag lower than *before*, for the notes' start."""
    limit = release_version(before)
    assert limit is not None
    return latest_release(
        name
        for name in names
        if (version := release_version(name)) is not None and version < limit
    )


def plan_promotion(
    source: Tag,
    releases: Iterable[Tag],
    today: date,
    *,
    has_release: Callable[[str], bool],
) -> Promotion:
    """Name the release that promotes *source*, by promotion date.

    A commit that already carries a release tag is not tagged again. If that
    tag is the latest release and has no GitHub Release, a run whose release
    step failed left it, so the run drafts its release; otherwise the commit
    is released already and the run is refused.
    """
    known = list(releases)
    names = [t.name for t in known]
    on_commit = [
        t.name
        for t in known
        if t.commit == source.commit and RELEASE_TAG_RE.match(t.name)
    ]
    if on_commit:
        tagged = latest_release(on_commit)
        assert tagged is not None
        if tagged != latest_release(names) or has_release(tagged):
            raise PromotionRefusedError(
                f"{source.name} names {source.commit}, which is already "
                f"released as {tagged}"
            )
        return Promotion(
            source, tagged, _previous_release(names, tagged), create_tag=False
        )
    release = next_release_name(today, names)
    return Promotion(
        source, release, _previous_release(names, release), create_tag=True
    )


def release_tag_message(promotion: Promotion, actor: str, run_url: str) -> str:
    """The annotated release tag's message: what it promotes, and who asked."""
    return (
        f"Release {promotion.release}, promoted from {promotion.source.name} "
        f"by @{actor}.\n\nCommit: {promotion.source.commit}\nRun: {run_url}\n"
    )


def unpublished_release(tag: str, commit: str, publishes: list[Tag]) -> str:
    """Why release *tag* names no publish, or ``""`` when it names one."""
    if publishes:
        return ""
    return (
        f"The release tag `{tag}` names `{commit}`, which carries no "
        f"`{PUBLISH_PREFIX}*` tag made by {BOT_NAME}: this release was never "
        "on the site, so nothing showed it passed CI and the site checks.\n\n"
        "Tags are append-only, so this tag stays. Review the release; to "
        "release a published commit instead, run the **Promote a publish to "
        "a release** workflow. Close this issue once the release is reviewed."
    )


def weekdays_between(start: date, end: date) -> int:
    """The weekdays after *start*, up to and including *end*."""
    if end <= start:
        return 0
    days = (end - start).days
    weeks, rest = divmod(days, 7)
    extra = sum(
        1 for i in range(1, rest + 1) if (start + timedelta(i)).weekday() < 5
    )
    return weeks * 5 + extra


def stale_site(
    newest: Tag | None, main_committed: datetime, unpublished: int
) -> str:
    """Why the site is stale (DOCBW-07-008), or ``""`` when it is not.

    The site is stale when ``main`` has commits it does not show and the
    newest publish is more than ``STALE_AFTER_WEEKDAYS`` weekdays older than
    the newest commit on ``main``. Weekends do not count, so a site that
    stopped on a Friday is not stale on Monday.
    """
    if unpublished == 0:
        return ""
    if newest is None:
        return (
            f"`main` has {unpublished} commits and there is no "
            f"`{PUBLISH_PREFIX}*` tag made by {BOT_NAME}, so nothing names "
            "what the site shows."
        )
    assert newest.created is not None
    behind = weekdays_between(
        newest.created.astimezone(UTC).date(),
        main_committed.astimezone(UTC).date(),
    )
    if behind <= STALE_AFTER_WEEKDAYS:
        return ""
    return (
        f"The newest publish, `{newest.name}`, is {behind} weekdays older than "
        f"the newest commit on `main`, which has {unpublished} commits the "
        "site does not show. The site is stale past "
        f"{STALE_AFTER_WEEKDAYS} weekdays.\n\n"
        "Look at the latest runs of the **Publish site to Pages** workflow: "
        "their summary names what blocked or skipped each publish. This "
        "issue closes on the first check after the next publish."
    )


# --- plumbing -----------------------------------------------------------------


def release_exists(repo: str, name: str) -> bool:
    """Whether a GitHub Release, draft or not, exists for tag *name*."""
    try:
        gh("release", "view", name, "--repo", repo, "--json", "tagName")
    except subprocess.CalledProcessError:
        return False
    return True


def push_release_tag(promotion: Promotion, message: str) -> None:
    """Create and push the annotated release tag, as the bot.

    Promote runs one at a time, so the name is free unless someone pushed it
    by hand meanwhile; then the push fails, and the run with it. A tag is
    never moved or deleted.
    """
    as_bot = ("-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}")
    run(
        "git",
        *as_bot,
        "tag",
        "--annotate",
        promotion.release,
        "--message",
        message,
        promotion.source.commit,
    )
    run("git", "push", "origin", f"refs/tags/{promotion.release}")


def draft_release(repo: str, promotion: Promotion) -> str:
    """Open the draft GitHub Release for the release tag; return its URL.

    Not retried: a retried create whose first attempt landed would open a
    second draft.
    """
    argv = [
        "release",
        "create",
        promotion.release,
        "--repo",
        repo,
        "--draft",
        "--verify-tag",
        "--title",
        promotion.release,
        "--generate-notes",
        "--notes",
        EXPERIMENTAL_NOTICE,
    ]
    if promotion.previous:
        argv += ["--notes-start-tag", promotion.previous]
    return gh(*argv, retry=False).strip()


def _report(title: str, text: str) -> None:
    print(text)
    write_github_file("GITHUB_STEP_SUMMARY", f"### {title}\n\n{text}\n")


def _details(path: str, text: str) -> None:
    if path:
        Path(path).write_text(text + "\n", encoding="utf-8")


def _today() -> date:
    """The promotion date, in UTC: it names the release's month."""
    return datetime.now(UTC).date()


def cmd_promote(args: argparse.Namespace) -> int:
    try:
        if args.ref != MAIN_REF:
            raise PromotionRefusedError(
                f"a promotion starts from main, not {args.ref!r}"
            )
        source = choose_publish_tag(args.publish_tag, publish_tags())
        promotion = plan_promotion(
            source,
            release_tags(),
            _today(),
            has_release=lambda name: release_exists(args.repo, name),
        )
    except ValueError as error:
        print(f"::error::{error}", file=sys.stderr)
        _report("Promotion refused", str(error))
        return 1
    if promotion.create_tag:
        message = release_tag_message(promotion, args.actor, args.run_url)
        push_release_tag(promotion, message)
    url = draft_release(args.repo, promotion)
    _report(
        "Promoted",
        f"`{promotion.source.name}` ({promotion.source.commit}) is release "
        f"`{promotion.release}`. Edit and publish the draft: {url}",
    )
    write_github_file("GITHUB_OUTPUT", f"release={promotion.release}\n")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    commit = run(
        "git", "rev-parse", f"refs/tags/{args.tag}^{{commit}}"
    ).strip()
    problem = unpublished_release(
        args.tag, commit, workflow_publish_tags_on(commit)
    )
    if not problem:
        _report("Release tag check", f"`{args.tag}` names a published commit.")
        return 0
    _details(args.details_file, problem)
    print(
        f"::error::{args.tag} names a commit with no publish", file=sys.stderr
    )
    _report("Release tag check", problem)
    return 1


def _unpublished_count(newest: Tag | None, tip: str) -> int:
    span = f"{newest.commit}..{tip}" if newest else tip
    return int(run("git", "rev-list", "--count", span).strip())


def cmd_staleness(args: argparse.Namespace) -> int:
    tip = run("git", "rev-parse", "HEAD").strip()
    committed = datetime.fromisoformat(
        run("git", "log", "-1", "--format=%cI", tip).strip()
    )
    newest = newest_publish_tag(publish_tags())
    problem = stale_site(newest, committed, _unpublished_count(newest, tip))
    if not problem:
        live = f"`{newest.name}`" if newest else "no publish"
        _report("Site staleness", f"The site is current enough: {live}.")
        return 0
    _details(args.details_file, problem)
    print("::error::the site is stale", file=sys.stderr)
    _report("Site staleness", problem)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Promote a publish, check a release tag, or check staleness."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    promote = sub.add_parser("promote")
    promote.add_argument("--repo", required=True)
    promote.add_argument("--ref", required=True)
    promote.add_argument("--actor", required=True)
    promote.add_argument("--run-url", required=True)
    promote.add_argument("--publish-tag", default="")
    promote.set_defaults(func=cmd_promote)
    check = sub.add_parser("check")
    check.add_argument("--tag", required=True)
    check.add_argument("--details-file", default="")
    check.set_defaults(func=cmd_check)
    staleness = sub.add_parser("staleness")
    staleness.add_argument("--details-file", default="")
    staleness.set_defaults(func=cmd_staleness)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
