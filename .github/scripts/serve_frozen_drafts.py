#!/usr/bin/env python3
"""Serve each released Protocol Specification draft's frozen pages in ``site/``.

ADR-0188; DOCBW-08-027 to DOCBW-08-035 in ``specs/docs-build-workflow.yaml``.
The shared ``serve-frozen-drafts`` action runs this script after the shared
site build, in the job that built the site and before the publication checks:
in ``deploy_site.yml`` with the drafts register as ``main`` holds it, and in
``docs-build-check.yml`` with the register of the checked-out commit.

For each released draft of the register:

- whose release is published, the release's archive
  ``vultron-spec-draft-N.tar.gz`` and manifest ``vultron-spec-draft-N.sha256``
  are downloaded, the archive is unpacked into an empty scratch folder,
  refusing any member that could write outside it, and the tree must be
  exactly what the manifest lists. The tree then moves to
  ``site/spec/draft-N/``. A release is immutable once published, so a tree
  that does not match is a corrupt download or a defect here, never a
  changed asset: the pair is downloaded once more before the step fails, and
  the release is never touched. Each download also gets ``gh``'s own bounded
  retry of a transient error (``retry.sh``).
- whose release is not published (no tag yet, no release, or a release still
  a draft), a placeholder page that names the release is written at
  ``site/spec/draft-N/index.html``, so the pages that link the draft never
  link a missing page, and the run summary names the draft.

A published release that lacks either file, or whose archive still fails
after the second download, fails the step, naming the draft and the release.
The step also fails, before it downloads anything, when the shared build
already wrote a file below ``site/spec/``: that folder holds frozen drafts
only (DOCBW-08-034).

Usage:
  serve_frozen_drafts.py --register FILE --site DIR --repo OWNER/NAME

``FILE`` holds the JSON ``uv run drafts-register show`` prints.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frozen_draft import DRAFT_VERSION, FrozenDraftError, unpack_matching
from gh_cli import write_github_file  # see gh_cli
from release import (
    DraftEntry,
    Register,
    download_assets,
    frozen_pair,
    release_state,
)

#: Where the frozen drafts are served, below the site root. The Revision Log
#: links the same folder (``FROZEN_COPY_DIR`` in
#: ``vultron/metadata/docs/drafts_register.py``).
SERVE_DIR = "spec"

#: How often a published release's pair is downloaded before the step fails.
DOWNLOAD_ATTEMPTS = 2


def reserved_faults(site: Path) -> list[str]:
    """Every file the shared build wrote below ``site/spec/`` (DOCBW-08-034)."""
    served = site / SERVE_DIR
    if not served.exists():
        return []
    if not served.is_dir():
        return [f"{SERVE_DIR}: the build wrote a file where frozen drafts go"]
    return [
        f"{path.relative_to(site).as_posix()}: the build wrote it, but "
        f"{SERVE_DIR}/ holds frozen drafts only"
        for path in sorted(served.rglob("*"))
        if not path.is_dir()
    ]


def placeholder_html(entry: DraftEntry, repo: str) -> str:
    """The page served for *entry* until its release is published."""
    version = html.escape(entry.version)
    release = html.escape(str(entry.release))
    url = html.escape(
        f"https://github.com/{repo}/releases/tag/{entry.release}"
    )
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        f"<title>Vultron Protocol Specification {version}</title>\n"
        '<meta name="robots" content="noindex">\n'
        "</head><body>\n"
        f"<h1>Vultron Protocol Specification {version}</h1>\n"
        f'<p>Release <a href="{url}"><code>{release}</code></a> carries '
        f"this draft, but it is not published yet. Its frozen pages appear "
        "here at the first deploy after it is.</p>\n"
        '<p>Until then, read the <a href="../../reference/vultron-spec/">'
        "current specification</a>.</p>\n"
        "</body></html>\n"
    )


class FetchFailed(FrozenDraftError):
    """A published release's pair could not be served.

    *downloaded* says how the last attempt failed: ``True`` when the pair
    was downloaded and its tree failed the checks, ``False`` when the
    download itself failed. The faults list every attempt's, in order.
    """

    def __init__(self, faults: Sequence[str], *, downloaded: bool) -> None:
        super().__init__(faults)
        self.downloaded = downloaded


def fetch_tree(repo: str, entry: DraftEntry, work: Path) -> Path:
    """Download *entry*'s pair and unpack the archive below *work*.

    The pair is downloaded again once when the first attempt fails, whether
    the download failed or the tree failed its checks. Each download also
    gets ``gh``'s own bounded retry of a transient error (``retry.sh``).

    Returns:
        The unpacked tree, which matches its manifest.

    Raises:
        FetchFailed: The faults of every attempt.
    """
    archive, manifest = frozen_pair(entry.version)
    faults: list[str] = []
    downloaded = False
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        folder = work / entry.version / f"attempt-{attempt}"
        assets = folder / "assets"
        tree = folder / "tree"
        found: list[str]
        try:
            download_assets(
                repo, str(entry.release), (archive, manifest), assets
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or "").strip() or str(error)
            found = [f"the download failed: {detail}"]
            downloaded = False
        else:
            downloaded = True
            try:
                found = unpack_matching(
                    assets / archive, assets / manifest, tree
                )
            except FrozenDraftError as error:
                found = error.faults
            except OSError as error:
                found = [f"the downloaded pair could not be read: {error}"]
            if not found:
                return tree
        faults += [f"attempt {attempt}: {fault}" for fault in found]
        if attempt < DOWNLOAD_ATTEMPTS:
            reason = (
                "failed its checks"
                if downloaded
                else "could not be downloaded"
            )
            print(
                f"::warning::{entry.version}: the archive of {entry.release} "
                f"{reason}; downloading it again."
            )
    raise FetchFailed(faults, downloaded=downloaded)


def serve_one(
    entry: DraftEntry, site: Path, repo: str, work: Path
) -> tuple[str, list[str]]:
    """Serve *entry*; return its summary line and its faults."""
    target = site / SERVE_DIR / entry.version
    shown = f"{entry.version} (release {entry.release})"
    try:
        state = release_state(repo, str(entry.release), retry=True)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip() or str(error)
        return (
            f"- `{entry.version}`: **failed**, release `{entry.release}` "
            "could not be looked up.",
            [f"{shown}: the release lookup failed: {detail}"],
        )
    # A contents:read token cannot see a draft release, so in CI gh reports
    # one as "not found" and it arrives here as None; is_draft is True only
    # for a token with push access. Either way the release is unpublished.
    if state is None or state.is_draft:
        target.mkdir(parents=True)
        (target / "index.html").write_text(
            placeholder_html(entry, repo), encoding="utf-8"
        )
        print(
            f"::notice::{entry.version}: release {entry.release} is not "
            "published yet, so a placeholder page is served."
        )
        return (
            f"- `{entry.version}`: release `{entry.release}` is not "
            "published yet; a placeholder page is served.",
            [],
        )
    missing = [
        name for name in frozen_pair(entry.version) if name not in state.assets
    ]
    if missing:
        return (
            f"- `{entry.version}`: **failed**, release `{entry.release}` "
            f"lacks {', '.join(missing)}.",
            [
                f"{shown}: the published release lacks {name}"
                for name in missing
            ],
        )
    try:
        tree = fetch_tree(repo, entry, work)
    except FetchFailed as error:
        how = (
            "does not match its manifest"
            if error.downloaded
            else "could not be downloaded"
        )
        return (
            f"- `{entry.version}`: **failed**, the archive of release "
            f"`{entry.release}` {how}.",
            [f"{shown}: {fault}" for fault in error.faults],
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tree), str(target))
    return (
        f"- `{entry.version}`: served from release `{entry.release}`.",
        [],
    )


def serve(
    register: Register, site: Path, repo: str
) -> tuple[list[str], list[str]]:
    """Serve every released draft of *register* into *site*.

    Every draft is tried, so one that fails does not hide another's state.

    Returns:
        ``(summary lines, faults)``: one line per released draft, and each
        fault naming the draft that could not be served and its release.
        The step fails when there is any fault.

    Raises:
        FrozenDraftError: When the build wrote below ``site/spec/``; nothing
            is then looked up or served.
    """
    if reserved := reserved_faults(site):
        raise FrozenDraftError(reserved)
    lines: list[str] = []
    faults: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for entry in register.released:
            try:
                line, found = serve_one(entry, site, repo, Path(tmp))
            except (OSError, ValueError, KeyError) as error:
                # An unexpected reply or a failed write fails this draft
                # only, so the next draft is still tried (EH-07-001).
                line = (
                    f"- `{entry.version}`: **failed**, release "
                    f"`{entry.release}` could not be served."
                )
                found = [
                    f"{entry.version} (release {entry.release}): "
                    f"{type(error).__name__}: {error}"
                ]
            lines.append(line)
            faults += found
    return lines, faults


def read_register(path: Path) -> Register:
    """The register in the ``drafts-register show`` JSON at *path*.

    Raises:
        FrozenDraftError: When the JSON is not a register's shape.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("released"), list)
        or not all(isinstance(entry, dict) for entry in data["released"])
        or not isinstance(data.get("current"), dict | None)
    ):
        raise FrozenDraftError([f"{path}: not a drafts register"])
    faults: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(data["released"]):
        version = entry.get("version")
        release = entry.get("release")
        # The version names a folder below site/spec/, so it must be a
        # draft-N and appear once; a released entry always names its release.
        if not isinstance(version, str) or not DRAFT_VERSION.match(version):
            faults.append(
                f"{path}: released entry {index}: not a draft-N version"
            )
        elif version in seen:
            faults.append(f"{path}: {version} is released twice")
        else:
            seen.add(version)
        if not isinstance(release, str) or not release.strip():
            faults.append(f"{path}: released entry {index}: no release tag")
    if faults:
        raise FrozenDraftError(faults)
    return Register.from_json(data)


def _summary(
    lines: Sequence[str],
    faults: Sequence[str] = (),
    empty: str = "No draft is released yet.",
) -> str:
    """The run summary: one line per released draft, then every fault."""
    body = "\n".join(lines) if lines else empty
    title = "Frozen drafts: failed" if faults else "Frozen drafts"
    tail = "".join(f"- {fault}\n" for fault in faults)
    return f"### {title}\n\n{body}\n" + (f"\n{tail}" if tail else "")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve the released drafts' frozen pages in site/."
    )
    parser.add_argument("--register", required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args(argv)
    try:
        register = read_register(Path(args.register))
        lines, faults = serve(register, Path(args.site), args.repo)
    except (
        FrozenDraftError,
        subprocess.CalledProcessError,
        OSError,
        ValueError,
        KeyError,
    ) as error:
        faults = (
            error.faults
            if isinstance(error, FrozenDraftError)
            else [str(error)]
        )
        for fault in faults:
            print(f"::error::{fault}", file=sys.stderr)
        write_github_file(
            "GITHUB_STEP_SUMMARY", _summary([], faults, "Nothing was served.")
        )
        return 1
    for fault in faults:
        print(f"::error::{fault}", file=sys.stderr)
    print(_summary(lines, faults))
    write_github_file("GITHUB_STEP_SUMMARY", _summary(lines, faults))
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
