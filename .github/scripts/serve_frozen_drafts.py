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
  changed asset: the download is tried once more before the step fails, and
  the release is never touched.
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
from frozen_draft import FrozenDraftError, unpack_matching
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


def fetch_tree(repo: str, entry: DraftEntry, work: Path) -> Path:
    """Download *entry*'s pair and unpack the archive below *work*.

    The pair is downloaded again once when the tree fails its checks.

    Returns:
        The unpacked tree, which matches its manifest.

    Raises:
        FrozenDraftError: The faults of the last attempt.
    """
    archive, manifest = frozen_pair(entry.version)
    faults: list[str] = []
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        folder = work / entry.version / f"attempt-{attempt}"
        assets = folder / "assets"
        tree = folder / "tree"
        try:
            download_assets(
                repo, str(entry.release), (archive, manifest), assets
            )
        except subprocess.CalledProcessError as error:
            faults = [f"the download failed: {error}"]
            continue
        try:
            faults = unpack_matching(assets / archive, assets / manifest, tree)
        except FrozenDraftError as error:
            faults = error.faults
        if not faults:
            return tree
        if attempt < DOWNLOAD_ATTEMPTS:
            print(
                f"::warning::{entry.version}: the archive of {entry.release} "
                "failed its checks; downloading it again."
            )
    raise FrozenDraftError(faults)


def serve_one(
    entry: DraftEntry, site: Path, repo: str, work: Path
) -> tuple[str, list[str]]:
    """Serve *entry*; return its summary line and its faults."""
    target = site / SERVE_DIR / entry.version
    state = release_state(repo, str(entry.release))
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
    shown = f"{entry.version} (release {entry.release})"
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
    except FrozenDraftError as error:
        return (
            f"- `{entry.version}`: **failed**, the archive of release "
            f"`{entry.release}` does not match its manifest.",
            [f"{shown}: {fault}" for fault in error.faults],
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tree), str(target))
    return (
        f"- `{entry.version}`: served from release `{entry.release}`.",
        [],
    )


def serve(register: Register | None, site: Path, repo: str) -> list[str]:
    """Serve every released draft of *register* into *site*.

    Returns:
        The run summary's lines, one per released draft.

    Raises:
        FrozenDraftError: When the build wrote below ``site/spec/``, before
            anything is served; or, after every draft was tried, naming each
            draft that could not be served and its release.
    """
    if reserved := reserved_faults(site):
        raise FrozenDraftError(reserved)
    released = () if register is None else register.released
    lines: list[str] = []
    faults: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for entry in released:
            line, found = serve_one(entry, site, repo, Path(tmp))
            lines.append(line)
            faults += found
    if faults:
        raise FrozenDraftError(faults)
    return lines


def read_register(path: Path) -> Register | None:
    """The register in the ``drafts-register show`` JSON at *path*."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data is None:
        return None
    if not isinstance(data, dict):
        raise FrozenDraftError([f"{path}: not a drafts register"])
    return Register.from_json(data)


def _summary(lines: Sequence[str]) -> str:
    body = "\n".join(lines) if lines else "No draft is released yet."
    return f"### Frozen drafts\n\n{body}\n"


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
        lines = serve(register, Path(args.site), args.repo)
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
            "GITHUB_STEP_SUMMARY",
            "### Frozen drafts: failed\n\n"
            + "".join(f"- {fault}\n" for fault in faults),
        )
        return 1
    print(_summary(lines))
    write_github_file("GITHUB_STEP_SUMMARY", _summary(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
