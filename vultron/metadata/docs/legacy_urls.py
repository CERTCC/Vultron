#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Enforce the continuity axis: a URL the site once published still answers.

A page that moves between two publishes takes its old URL with it, and whoever
cited that URL — in a paper, a standards comment, a partner's tracker — gets a
404 on publish day. #3556 found 162 such URLs between the ``publish`` branch
and ``main``. Every one had moved, been renamed, or been withdrawn, and nothing
in the build said so.

The evidence of what was live lives on the ``publish`` branch, and it is gone
the moment ``publish`` advances. So the evidence is committed:
:data:`BASELINE` lists every ``docs/`` page any publish has built, and it only
grows. ``--snapshot <ref>`` adds a ref's pages before that ref is replaced.

:func:`unmapped_pages` checks a built ``site/`` against that list. A published
page is accounted for when one of these holds:

* the build produced a page at its URL;
* the build produced a redirect there (``mkdocs-redirects``, configured in
  ``mkdocs.yml``) whose chain ends at a page the build produced; or
* a :data:`~vultron.metadata.docs.withheld.WITHHELD_ARTIFACTS` declaration
  covers the URL — the project decided to withdraw it, and ``docs-withheld``
  verifies that it really is absent.

Everything else is a 404 the publish would introduce, and fails.

A missing or empty ``site/`` and an empty baseline are hard failures, not
passes: a check that resolves no targets and reports success is worse than no
check (DF-09-009).

CLI (``uv run docs-legacy-urls``)::

    uv run mkdocs build
    uv run docs-legacy-urls                       # exit 1 on an unmapped URL
    uv run docs-legacy-urls --snapshot origin/publish   # extend the baseline
"""

from __future__ import annotations

import argparse
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.docs.baseline_file import entry_lines, write_entries
from vultron.metadata.docs.withheld import (
    WITHHELD_ARTIFACTS,
    WithheldArtifact,
    site_dir,
)

BASELINE = Path(__file__).with_name("legacy_urls_baseline.txt")

_HEADER = """\
# Every docs/ page a publish of the site has built, relative to docs/.
#
# `uv run docs-legacy-urls` fails when the built site/ neither serves nor
# redirects one of these URLs, unless a withheld declaration covers it. The list
# only grows: a URL that was once published stays accounted for. Before
# `publish` advances, run `uv run docs-legacy-urls --snapshot origin/publish` so
# the pages it is about to replace are recorded while the evidence exists.
#
# Seeded from origin/publish at ee5d96d3d (#3556)."""

# ``mkdocs-redirects`` writes each stub with a meta refresh; its ``url=`` is the
# target, relative to the stub's own directory.
_REFRESH = re.compile(
    r"""<meta\s+http-equiv=["']refresh["']\s+content=["']\d+;\s*url=([^"']+)["']""",
    re.IGNORECASE,
)

# A redirect chain longer than this is a loop, not a chain.
_MAX_HOPS = 10


@dataclass(frozen=True)
class UnmappedPage:
    """A published page whose URL the built site no longer answers.

    Attributes:
        source: The page path relative to ``docs/``, as the baseline lists it.
        url: The page's URL path relative to the site root.
        problem: Why the URL does not resolve, in one sentence.
    """

    source: str
    url: str
    problem: str


def page_url(source: str) -> str:
    """Return the directory URL a ``docs/`` page builds to.

    Under ``use_directory_urls`` (the MkDocs default, which this site keeps),
    ``x/y.md`` builds to ``x/y/`` and ``x/index.md`` or ``x/README.md`` to
    ``x/``. The site root is the empty string.
    """
    stem = source.removesuffix(".md")
    head, _, name = stem.rpartition("/")
    return head if name in ("index", "README") else stem


def _built_file(site: Path, url: str) -> Path:
    return site / url / "index.html" if url else site / "index.html"


def redirect_target(html: str) -> str | None:
    """Return the meta-refresh target of a redirect stub, or ``None``."""
    match = _REFRESH.search(html)
    return match.group(1).strip() if match else None


def _resolve(url: str, target: str) -> str | None:
    """Resolve a stub's relative *target* against the stub's directory *url*.

    Returns ``None`` for a target outside the site — an absolute URL, or a path
    that climbs above the site root — because the build cannot evidence it.
    """
    if "://" in target or target.startswith(("/", "//")):
        return None
    path = target.split("#", 1)[0]
    joined = posixpath.normpath(posixpath.join(url or ".", path))
    if joined == ".":
        return ""
    if joined.startswith(".."):
        return None
    return joined.removesuffix("/index.html").removesuffix("/")


def _check(site: Path, source: str) -> str | None:
    """Return why *source*'s URL fails to resolve, or ``None`` when it does."""
    url = page_url(source)
    seen = [url]
    for _ in range(_MAX_HOPS):
        built = _built_file(site, url)
        if not built.is_file():
            if url == seen[0]:
                return "the build produced neither a page nor a redirect here"
            return f"its redirect chain ends at '{url}/', which was not built"
        target = redirect_target(built.read_text(encoding="utf-8"))
        if target is None:
            return None
        resolved = _resolve(url, target)
        if resolved is None:
            return (
                f"it redirects to '{target}', outside the built site, which "
                "this check cannot verify"
            )
        if resolved in seen:
            return f"its redirects loop: {' -> '.join(seen + [resolved])}"
        seen.append(resolved)
        url = resolved
    return f"its redirect chain exceeds {_MAX_HOPS} hops"


def load_baseline(path: Path = BASELINE) -> list[str]:
    """Return every page path the baseline at *path* lists."""
    return [line.strip() for _, line in entry_lines(path)]


def unmapped_pages(
    root: Path | None = None,
    pages: list[str] | None = None,
    artifacts: tuple[WithheldArtifact, ...] = WITHHELD_ARTIFACTS,
) -> list[UnmappedPage]:
    """Return every published page whose URL the built site does not answer.

    Args:
        root: Repository root holding ``site/``. Defaults to this checkout.
        pages: Page paths relative to ``docs/``. Defaults to :data:`BASELINE`.
        artifacts: Withheld declarations whose URLs are withdrawn on purpose.

    Returns:
        One entry per unaccounted page, in baseline order.

    Raises:
        FileNotFoundError: If ``site/`` is absent or empty.
        ValueError: If there are no pages to check. Both would otherwise pass
            while checking nothing (DF-09-009).
    """
    site = site_dir(root)
    if not site.is_dir() or not any(site.iterdir()):
        raise FileNotFoundError(
            f"{site} is absent or empty — run 'uv run mkdocs build' first. An "
            "unbuilt site cannot show that a published URL still resolves."
        )
    listed = load_baseline() if pages is None else pages
    if not listed:
        raise ValueError(
            "The published-page baseline is empty, so there is nothing to "
            "check. Seed it with 'uv run docs-legacy-urls --snapshot <ref>'."
        )

    unmapped: list[UnmappedPage] = []
    for source in listed:
        url = page_url(source)
        if any(artifact.covers(url) for artifact in artifacts):
            continue
        problem = _check(site, source)
        if problem is not None:
            unmapped.append(UnmappedPage(source, url, problem))
    return unmapped


def snapshot(ref: str, root: Path | None = None, path: Path = BASELINE) -> int:
    """Add every ``docs/`` page on git *ref* to the baseline at *path*.

    The baseline is extended, never replaced: a page that was published once
    keeps its URL accounted for after later publishes drop it.

    Returns:
        The number of pages the snapshot added.

    Raises:
        subprocess.CalledProcessError: If git cannot list *ref*.
    """
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", "docs/"],
        cwd=root or repo_root(),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    pages = {
        name.removeprefix("docs/") for name in listing if name.endswith(".md")
    }
    existing = set(load_baseline(path))
    write_entries(path, _HEADER, existing | pages)
    return len(pages - existing)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run docs-legacy-urls``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root holding the built site/ (default: this checkout).",
    )
    parser.add_argument(
        "--snapshot",
        metavar="REF",
        default=None,
        help="Add every docs/ page on git REF to the baseline instead of checking.",
    )
    args = parser.parse_args(argv)

    if args.snapshot is not None:
        added = snapshot(args.snapshot, args.root)
        print(
            f"✓ Added {added} page(s) from {args.snapshot} to {BASELINE.name}."
        )
        return

    try:
        unmapped = unmapped_pages(args.root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    total = len(load_baseline())
    if unmapped:
        for page in unmapped:
            print(
                f"[ERROR] {page.url or '(site root)'}/ (from {page.source}): "
                f"{page.problem}.",
                file=sys.stderr,
            )
        print(
            f"\n✗ {len(unmapped)} of {total} published URL(s) would 404. Add a "
            "redirect_maps entry in mkdocs.yml pointing at the page's new home, "
            "or, if the page was withdrawn on purpose, declare it in "
            "vultron/metadata/docs/withheld.py.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"✓ All {total} published URLs resolve in {site_dir(args.root).name}/."
    )


if __name__ == "__main__":
    main()
