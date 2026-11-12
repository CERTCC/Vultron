#!/usr/bin/env python3
"""Promote a publish to a release, check a release tag, and alarm on a stale site.

Three workflows run this script, each on ``main``'s copy (DOCBW-07):

- ``plan`` and ``promote`` (``promote_release.yml``) turn a ``publish-*`` tag
  into the next ``vYYYY.M.P`` release tag (ADR-0006) on the same commit, then
  open a draft GitHub Release whose notes are generated since the previous
  release. ``plan`` names the release and the draft it carries, in a job that
  cannot write, so the next job can build that draft's frozen archive
  (``frozen_draft.py``); ``promote`` decides again, checks the archive, pushes
  the tag and creates the draft release with the archive attached (ADR-0188,
  DOCBW-08). A tag the workflow's ``GITHUB_TOKEN`` pushes starts no other
  workflow, so the release tag check never sees it: promote checks its own
  input.
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
  release.py plan --ref REF [--publish-tag TAG]
  release.py promote --repo OWNER/NAME --ref REF --actor LOGIN --run-url URL
      [--publish-tag TAG] [--planned-release TAG] [--planned-draft draft-N]
      [--frozen-dir DIR]
  release.py check --tag TAG [--details-file PATH]
  release.py staleness [--details-file PATH]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frozen_draft import (
    FrozenDraftError,
    archive_name,
    manifest_name,
    verify_archive,
)
from gh_cli import gh, run, write_github_file  # see gh_cli
from publish_gate import MAIN_REF
from release_tags import (
    BOT_GIT_IDENTITY,
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
    tag_commit,
    workflow_publish_tags_on,
)

# The site is stale past this many weekdays behind main (DOCBW-07-008).
STALE_AFTER_WEEKDAYS = 4
# The statement every release's notes carry (CONTRIBUTING.md).
EXPERIMENTAL_NOTICE = "All interfaces in this release are experimental."


class PromotionRefusedError(ValueError):
    """The promote workflow was asked for something it does not do."""


class IncompleteDraftReleaseError(RuntimeError):
    """A failed run could not delete the draft release it created."""


@dataclass(frozen=True)
class Promotion:
    """What one promote run does.

    ``create_tag`` is false when the commit already carries the latest
    release tag, made by this workflow: a run that failed after pushing it
    left it, and this run drafts its release instead of tagging the commit
    twice, if :func:`resume_action` allows.
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
    source: Tag, releases: Iterable[Tag], today: date
) -> Promotion:
    """Name the release that promotes *source*, by promotion date.

    A commit that already carries a release tag is not tagged again. If that
    tag is the latest release and was made by this workflow, a run that
    failed after pushing it left it, so the run drafts its release, as far
    as :func:`resume_action` allows once the release is looked up. In every
    other case the run is refused.
    """
    known = list(releases)
    names = [t.name for t in known]
    on_commit = {
        t.name: t
        for t in known
        if t.commit == source.commit and RELEASE_TAG_RE.match(t.name)
    }
    if on_commit:
        tagged = latest_release(on_commit)
        assert tagged is not None
        why = _no_resume(on_commit[tagged], latest_release(names))
        if why:
            raise PromotionRefusedError(
                f"{source.name} names {source.commit}, which is already "
                f"tagged {tagged}: {why}"
            )
        return Promotion(
            source, tagged, _previous_release(names, tagged), create_tag=False
        )
    release = next_release_name(today, names)
    return Promotion(
        source, release, _previous_release(names, release), create_tag=True
    )


def _no_resume(tag: Tag, latest: str | None) -> str:
    """Why a run must not draft the release of *tag*, or ``""``."""
    if tag.name != latest:
        return f"a later release, {latest}, exists"
    if not tag.made_by_workflow:
        return "that tag was not made by this workflow"
    return ""


# --- the draft a release carries (ADR-0188, DOCBW-08) --------------------------


@dataclass(frozen=True)
class DraftEntry:
    """One entry of the drafts register, as ``drafts-register show`` prints it."""

    version: str
    date: str
    release: str | None = None


@dataclass(frozen=True)
class Register:
    """The drafts register at one ref: its open draft and its released ones."""

    current: DraftEntry | None
    released: tuple[DraftEntry, ...]

    @classmethod
    def from_json(cls, data: dict[str, object]) -> Register:
        current = data.get("current")
        released = data.get("released") or []
        assert isinstance(released, list)
        return cls(
            None
            if not isinstance(current, dict)
            else DraftEntry(str(current["version"]), str(current["date"])),
            tuple(
                DraftEntry(
                    str(entry["version"]),
                    str(entry["date"]),
                    str(entry["release"]),
                )
                for entry in released
            ),
        )

    def entry(self, version: str) -> DraftEntry | None:
        """The entry for *version*, released or not, or ``None``."""
        for entry in (*self.released, self.current):
            if entry is not None and entry.version == version:
                return entry
        return None

    def released_by(self, tag: str) -> DraftEntry | None:
        """The draft whose release is *tag*, or ``None``."""
        return next((e for e in self.released if e.release == tag), None)


def carried_draft(
    promotion: Promotion,
    existing: Iterable[str],
    register_at: Callable[[str], Register | None],
) -> str | None:
    """The draft the release carries, ``draft-N``, or ``None`` for none.

    Read from the drafts register at the promoted commit. The run is refused
    when that register names, as a draft's release, a tag that is neither
    the run's release nor an existing release whose own register holds the
    same entry (DOCBW-08-011), and when it names the run's release for a
    draft while it still holds an open draft (DOCBW-08-012). Every such
    fault is named.
    """
    register = register_at(promotion.source.commit)
    if register is None:
        return None
    tags = set(existing)
    faults = []
    for entry in register.released:
        assert entry.release is not None
        if entry.release == promotion.release:
            continue
        if entry.release not in tags:
            faults.append(
                f"{entry.version} names release {entry.release}, which does "
                f"not exist and is not this run's release, {promotion.release}"
            )
            continue
        theirs = register_at(entry.release)
        if theirs is None or theirs.entry(entry.version) != entry:
            faults.append(
                f"{entry.version} names release {entry.release}, whose own "
                "drafts register does not hold the same entry: that release "
                "never carried it"
            )
    carried = register.released_by(promotion.release)
    if carried is not None and register.current is not None:
        faults.append(
            f"{carried.version} names this run's release, "
            f"{promotion.release}, but {register.current.version} is still "
            "open: mark it released or remove it before promoting"
        )
    if faults:
        raise PromotionRefusedError(
            f"the drafts register at {promotion.source.name} cannot be "
            "promoted: " + "; ".join(faults)
        )
    return None if carried is None else carried.version


@dataclass(frozen=True)
class ReleaseState:
    """A GitHub Release as the promote sees it: draft or not, and its assets."""

    is_draft: bool
    assets: tuple[str, ...]


def frozen_pair(version: str) -> tuple[str, str]:
    """The names of the archive and the manifest of draft *version*."""
    return archive_name(version), manifest_name(version)


def resume_action(
    promotion: Promotion,
    draft: str | None,
    state: ReleaseState | None,
    pair_matches: Callable[[], bool],
) -> str:
    """``"create"``, ``"replace"`` (delete the release first), or refuse.

    No release: create it. A release this run cannot finish is refused
    (DOCBW-07-016): any release of a tag this run makes, any release of a
    release that carries no draft, and a release that carries its matching
    archive and manifest. A draft release that lacks them, left by a run
    stopped from outside, is replaced (DOCBW-08-025); a published one cannot
    take them (DOCBW-08-026).
    """
    name = promotion.release
    if state is None:
        return "create"
    prefix = f"{promotion.source.name} names {promotion.source.commit}, "
    if promotion.create_tag:
        raise PromotionRefusedError(
            f"{prefix}but a release named {name} exists without its tag"
        )
    released = f"{prefix}which is already tagged {name}: "
    if draft is None:
        raise PromotionRefusedError(released + "it is released already")
    matches = set(state.assets) == set(frozen_pair(draft)) and pair_matches()
    if state.is_draft and matches:
        raise PromotionRefusedError(
            released + f"the draft release {name} is complete, with the "
            f"archive and manifest of {draft}, and is waiting for the "
            "maintainer to publish it"
        )
    if state.is_draft:
        return "replace"
    if not matches:
        raise PromotionRefusedError(
            released + f"the published release {name} lacks a matching "
            f"archive and manifest of {draft}, and a published release "
            "cannot take the archive: a re-run cannot help"
        )
    raise PromotionRefusedError(released + "it is released already")


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
        "a release** workflow. The next release tag pushed by hand that "
        "names a publish closes this issue."
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


def register_at(ref: str) -> Register | None:
    """The drafts register as *ref* holds it, or ``None`` when it holds none.

    Read by main's ``drafts-register`` (``vultron/metadata/docs/
    drafts_register.py``), which refuses a malformed register; the file at
    *ref* is read as data, never run.
    """
    out = run(
        "uv", "run", "--no-sync", "drafts-register", "show", "--ref", ref,
        "--absent-ok",
    )  # fmt: skip
    data = json.loads(out)
    return None if data is None else Register.from_json(data)


def release_state(repo: str, name: str) -> ReleaseState | None:
    """The GitHub Release, draft or not, for tag *name*, or ``None``.

    Only ``gh``'s "release not found" reads as no release; any other error
    raises, so a failed lookup never leads to a second draft.
    """
    try:
        out = gh(
            "release", "view", name, "--repo", repo, "--json",
            "isDraft,assets", retry=False,
        )  # fmt: skip
    except subprocess.CalledProcessError as error:
        if "not found" in str(error.stderr or "").lower():
            return None
        raise
    data = json.loads(out)
    return ReleaseState(
        bool(data["isDraft"]),
        tuple(str(asset["name"]) for asset in data.get("assets") or []),
    )


def download_assets(
    repo: str, name: str, assets: Sequence[str], into: Path
) -> None:
    """Download the assets *assets* of release *name* into *into*."""
    patterns = [arg for asset in assets for arg in ("--pattern", asset)]
    gh(
        "release", "download", name, "--repo", repo, "--dir", str(into),
        *patterns,
    )  # fmt: skip


def attached_pair_matches(repo: str, name: str, draft: str) -> bool:
    """Whether release *name*'s archive matches its manifest (DOCBW-08-021)."""
    archive, manifest = frozen_pair(draft)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        download_assets(repo, name, (archive, manifest), folder / "assets")
        try:
            verify_archive(
                folder / "assets" / archive,
                folder / "assets" / manifest,
                folder / "tree",
            )
        except FrozenDraftError as error:
            print(f"{name}'s attached archive fails its checks:\n{error}")
            return False
    return True


def check_attached(repo: str, name: str, built: Sequence[Path]) -> None:
    """Fail unless the assets of release *name* are the *built* files' bytes.

    Raises:
        PromotionRefusedError: When an attached asset differs (DOCBW-08-022).
    """
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        download_assets(repo, name, [path.name for path in built], folder)
        differ = [
            path.name
            for path in built
            if not (folder / path.name).is_file()
            or (folder / path.name).read_bytes() != path.read_bytes()
        ]
    if differ:
        raise PromotionRefusedError(
            f"the draft release {name} holds {', '.join(differ)}, which "
            "differ from the files this run built"
        )


def discard_draft_release(repo: str, name: str) -> None:
    """Delete the draft release *name*, keeping its tag.

    The release is the one this run created, or an incomplete one a stopped
    run left (DOCBW-08-023, DOCBW-08-025). A draft release is not immutable,
    so deleting it costs nothing, and the tag stays (DOCBW-07-009). Nothing
    to delete is no fault: a failed create may have left none.

    Raises:
        IncompleteDraftReleaseError: When it cannot be deleted, or is no
            longer a draft (DOCBW-08-037).
    """
    try:
        state = release_state(repo, name)
        if state is None:
            return
        if state.is_draft:
            gh("release", "delete", name, "--repo", repo, "--yes", retry=False)
            return
    except subprocess.CalledProcessError:
        pass
    raise IncompleteDraftReleaseError(
        f"The draft release {name} is incomplete and must not be published: "
        "the run could not delete it. Delete the draft release by hand (keep "
        "the tag), then run the promote again."
    )


def push_release_tag(promotion: Promotion, message: str) -> None:
    """Create and push the annotated release tag, as the bot.

    Promote runs one at a time, so the name is free unless someone pushed it
    by hand meanwhile; then the push fails, and the run with it. A tag is
    never moved or deleted.
    """
    run(
        "git",
        *BOT_GIT_IDENTITY,
        "tag",
        "--annotate",
        promotion.release,
        "--message",
        message,
        promotion.source.commit,
    )
    run("git", "push", "origin", f"refs/tags/{promotion.release}")


def draft_release(
    repo: str, promotion: Promotion, assets: Sequence[Path] = ()
) -> str:
    """Open the draft GitHub Release for the release tag; return its URL.

    The *assets* are attached by the same call, so no draft release exists
    without them unless the upload fails, which the caller cleans up
    (DOCBW-08-009, DOCBW-08-023). Never published: the maintainer publishes.
    Not retried: a retried create whose first attempt landed would open a
    second draft.
    """
    argv = [
        "release",
        "create",
        promotion.release,
        *(str(path) for path in assets),
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


def _decide(args: argparse.Namespace) -> tuple[Promotion, str | None]:
    """The promotion and the draft it carries, or a refusal."""
    if args.ref != MAIN_REF:
        raise PromotionRefusedError(
            f"a promotion starts from main, not {args.ref!r}"
        )
    source = choose_publish_tag(args.publish_tag, publish_tags())
    releases = release_tags()
    promotion = plan_promotion(source, releases, _today())
    draft = carried_draft(promotion, (t.name for t in releases), register_at)
    return promotion, draft


def _refused(error: Exception) -> int:
    print(f"::error::{error}", file=sys.stderr)
    _report("Promotion refused", str(error))
    return 1


def cmd_plan(args: argparse.Namespace) -> int:
    """Name the release and its draft for the job that builds the archive.

    The job that can write decides again (``promote``) and refuses a plan
    that has changed.
    """
    try:
        promotion, draft = _decide(args)
    except ValueError as error:
        return _refused(error)
    day = PUBLISH_TAG_RE.match(promotion.source.name)
    assert day is not None
    write_github_file(
        "GITHUB_OUTPUT",
        f"commit={promotion.source.commit}\n"
        f"publish-tag={promotion.source.name}\n"
        f"publish-date={day.group(1)}\n"
        f"release={promotion.release}\n"
        f"draft={draft or ''}\n",
    )
    carries = f"carries {draft}" if draft else "carries no draft"
    _report(
        "Promotion planned",
        f"`{promotion.source.name}` ({promotion.source.commit}) becomes "
        f"`{promotion.release}`, which {carries}.",
    )
    return 0


def _frozen_files(args: argparse.Namespace, draft: str) -> list[Path]:
    """The built archive and manifest, checked before any tag or release.

    Raises:
        PromotionRefusedError: When a file is missing, or the archive fails
            its checks (DOCBW-08-021).
    """
    folder = Path(args.frozen_dir or ".")
    files = [folder / name for name in frozen_pair(draft)]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise PromotionRefusedError(
            f"the release carries {draft}, but its built "
            f"{' and '.join(missing)} is missing"
        )
    with tempfile.TemporaryDirectory() as tmp:
        try:
            verify_archive(files[0], files[1], Path(tmp) / "tree")
        except FrozenDraftError as error:
            raise PromotionRefusedError(
                f"the built archive of {draft} fails its checks: {error}"
            ) from error
    return files


def _check_plan(
    args: argparse.Namespace, promotion: Promotion, draft: str | None
) -> None:
    """Refuse when the plan job named another release or draft."""
    if args.planned_release and args.planned_release != promotion.release:
        raise PromotionRefusedError(
            f"the plan named release {args.planned_release}, but this job "
            f"names {promotion.release}: start a new run"
        )
    if args.planned_release and (args.planned_draft or None) != draft:
        raise PromotionRefusedError(
            f"the plan named draft {args.planned_draft or 'none'}, but this "
            f"job reads {draft or 'none'}: start a new run"
        )


def cmd_promote(args: argparse.Namespace) -> int:
    try:
        promotion, draft = _decide(args)
        _check_plan(args, promotion, draft)
        built = _frozen_files(args, draft) if draft else []
        state = release_state(args.repo, promotion.release)
        action = resume_action(
            promotion,
            draft,
            state,
            lambda: attached_pair_matches(
                args.repo, promotion.release, draft or ""
            ),
        )
    except ValueError as error:
        return _refused(error)
    if action == "replace":
        print(
            f"Deleting the incomplete draft release {promotion.release}, "
            "which lacks a matching archive and manifest (DOCBW-08-025)."
        )
        discard_draft_release(args.repo, promotion.release)
    if promotion.create_tag:
        message = release_tag_message(promotion, args.actor, args.run_url)
        push_release_tag(promotion, message)
    try:
        url = draft_release(args.repo, promotion, built)
        if built:
            check_attached(args.repo, promotion.release, built)
        attached = (
            f" It carries {draft}: {', '.join(p.name for p in built)}."
            if built
            else ""
        )
        _report(
            "Promoted",
            f"`{promotion.source.name}` ({promotion.source.commit}) is "
            f"release `{promotion.release}`.{attached} Edit and publish the "
            f"draft: {url}",
        )
        write_github_file("GITHUB_OUTPUT", f"release={promotion.release}\n")
    except BaseException as error:
        _discard_after(args.repo, promotion.release, error)
        raise
    return 0


def _discard_after(repo: str, name: str, error: BaseException) -> None:
    """Delete this run's draft release after *error* (DOCBW-08-023)."""
    print(
        f"::error::the promote failed after the tag: {error!r}",
        file=sys.stderr,
    )
    try:
        discard_draft_release(repo, name)
    except IncompleteDraftReleaseError as incomplete:
        print(f"::error::{incomplete}", file=sys.stderr)
        _report("Draft release incomplete", str(incomplete))
        raise incomplete from error
    _report(
        "Promotion failed",
        f"The run failed, so it deleted the draft release {name}; the tag "
        "stays. Run the promote again.",
    )


def cmd_check(args: argparse.Namespace) -> int:
    if release_version(args.tag) is None:
        # A ``v*`` name that is no version, such as ``vendor-drop``, is no
        # release: nothing to check, and no report to close.
        _report("Release tag check", f"`{args.tag}` is not a release tag.")
        write_github_file("GITHUB_OUTPUT", "checked=false\n")
        return 0
    write_github_file("GITHUB_OUTPUT", "checked=true\n")
    commit = tag_commit(args.tag)
    if commit is None:
        raise PromotionRefusedError(f"there is no tag {args.tag!r}")
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
    plan = sub.add_parser("plan")
    plan.add_argument("--ref", required=True)
    plan.add_argument("--publish-tag", default="")
    plan.set_defaults(func=cmd_plan)
    promote = sub.add_parser("promote")
    promote.add_argument("--repo", required=True)
    promote.add_argument("--ref", required=True)
    promote.add_argument("--actor", required=True)
    promote.add_argument("--run-url", required=True)
    promote.add_argument("--publish-tag", default="")
    promote.add_argument("--planned-release", default="")
    promote.add_argument("--planned-draft", default="")
    promote.add_argument("--frozen-dir", default="")
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
