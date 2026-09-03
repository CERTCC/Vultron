"""Renderer for the auto-generated list on ``docs/about/whats_new.md``.

The "What's New" page lists docs pages added recently, as a Markdown bullet
list. It is generated at build time by a markdown-exec Python block that calls
into this module (mirroring the ``docs/reference/specs/*.md`` pages, which
delegate to :mod:`vultron.metadata.specs.docs_render`).

Links are emitted as **final, directory-style relative URLs** — e.g. a link
from the What's New page to ``docs/reference/quick_reference.md`` renders as
``../../reference/quick_reference/``. Two facts force this shape:

* markdown-exec output bypasses MkDocs' relative-link treeprocessor, so a
  ``.md`` source link (``../reference/quick_reference.md``) is emitted verbatim
  and never rewritten — it 404s. The link must already be the built URL.
* Under ``use_directory_urls`` (the default), each page ``docs/x/y.md`` is
  served at ``x/y/``, so links must be computed against that URL layout.

A directory-style *relative* URL works both on the deployed ``/Vultron/``
sub-path and under ``mkdocs serve`` at the domain root, because it never
references the site root. A root-absolute link (a leading ``/``) does reference
the root and drops the ``/Vultron/`` base path — the bug in issue #3144. This
mirrors the ``../slug/#anchor`` links :mod:`docs_render` emits for the same
reason.

Usage (in a markdown-exec Python block)::

    from vultron.metadata.docs.whats_new import (
        added_doc_pages,
        render_recent_pages,
    )
    print(render_recent_pages(added_doc_pages(since_days=90)))
"""

from __future__ import annotations

import datetime
import posixpath
import subprocess
from collections.abc import Iterable
from pathlib import Path

# The source path of the page that hosts the generated list. Used as the base
# for computing relative URLs to each listed page.
WHATS_NEW_PAGE = "docs/about/whats_new.md"

# Shown when no docs pages were added in the window. Kept in sync with the
# 90-day default used by the whats_new.md exec block.
NO_PAGES_MESSAGE = "_No pages added in the last 90 days._"


# Draft pages that MkDocs excludes from the production build (``draft_docs`` in
# mkdocs.yml) have no built page, so linking to one 404s. Keep this in sync with
# mkdocs.yml draft_docs, which lists ``draft-*.md`` (with a single un-drafted
# exception) and the ``developer/`` tree (maintainer pages, DOCBW-03-004). Pages
# in ``not_in_nav`` are still built and reachable by URL, so they are NOT excluded.
_DRAFT_EXCEPTIONS = frozenset({"reference/draft-vultron-spec.md"})
_DRAFT_DIRS = ("developer/",)


def _is_published(path: str) -> bool:
    """Whether MkDocs builds a production page for this source path.

    Excludes underscore-prefixed segments and ``includes/`` (never standalone
    pages), ``draft-*`` files, and the ``developer/`` tree — all dropped from the
    production build by mkdocs.yml ``draft_docs``, so a link to any would 404.
    """
    rel = path.removeprefix("docs/")
    parts = rel.split("/")
    if any(p.startswith("_") for p in parts) or "includes" in parts:
        return False
    if rel in _DRAFT_EXCEPTIONS:
        return True
    if rel.startswith(_DRAFT_DIRS):
        return False
    return not posixpath.basename(rel).startswith("draft-")


def _title_for(path: str) -> str:
    """Build a readable title from a docs file path.

    Uses the page's URL path so that index/README pages are titled after their
    directory (``docs/reference/index.md`` -> "Reference") rather than the
    literal "Index"/"Readme"; the docs-root index is titled "Home".
    """
    url = _url_path(path)
    stem = posixpath.basename(url) if url else "Home"
    return stem.replace("-", " ").replace("_", " ").title()


def _url_path(md_path: str) -> str:
    """Return the ``use_directory_urls`` URL path for a docs source file.

    ``docs/x/y.md`` -> ``x/y``; index pages collapse to their parent directory
    (``docs/x/index.md`` -> ``x``, ``docs/index.md`` -> ``""``). ``README.md`` is
    treated as an index page, matching MkDocs. The result has no leading or
    trailing slash; callers add the trailing slash.
    """
    rel = md_path.removeprefix("docs/").removesuffix(".md")
    if posixpath.basename(rel) in ("index", "README"):
        return posixpath.dirname(rel)
    return rel


def _relative_url(target: str, *, page_path: str) -> str:
    """Directory-style relative URL from ``page_path`` to ``target`` (both docs paths).

    e.g. ``docs/reference/quick_reference.md`` from ``docs/about/whats_new.md``
    -> ``../../reference/quick_reference/``.
    """
    # The docs-root index collapses to "" (see _url_path); posixpath.relpath
    # raises on an empty path, so substitute "." for the repo-root directory.
    page_url = _url_path(page_path) or "."
    target_url = _url_path(target) or "."
    rel = posixpath.relpath(target_url, page_url)
    return rel + "/" if rel != "." else "./"


def render_recent_pages(
    files: Iterable[str], *, page_path: str = WHATS_NEW_PAGE
) -> str:
    """Render a Markdown bullet list of docs pages as relative-URL links.

    Args:
        files: Repo-relative docs paths (e.g.
            ``docs/reference/quick_reference.md``), in any order and possibly
            with duplicates.
        page_path: Source path of the hosting page, used as the base for the
            relative URLs (defaults to :data:`WHATS_NEW_PAGE`).

    Returns:
        A newline-joined Markdown bullet list, or :data:`NO_PAGES_MESSAGE` when
        no navigable ``.md`` pages remain after filtering.
    """
    pages = sorted({f.strip() for f in files if f.strip().endswith(".md")})
    pages = [f for f in pages if _is_published(f)]
    if not pages:
        return NO_PAGES_MESSAGE
    lines = [
        f"- [{_title_for(f)}]({_relative_url(f, page_path=page_path)})"
        for f in pages
    ]
    return "\n".join(lines)


def keep_existing_pages(
    paths: Iterable[str], *, repo_root: Path | None = None
) -> list[str]:
    """Drop paths whose file no longer exists under ``repo_root``.

    ``git log --diff-filter=A`` reports the *original* path of a file that was
    later renamed (git records the rename as a separate ``R`` change). That
    original path no longer exists and its built page 404s, so a link to it is
    dead. Filtering to files present on disk keeps only paths that map to a
    real, built page.
    """
    root = repo_root or Path.cwd()
    return [
        stripped
        for p in paths
        if (stripped := p.strip()) and (root / stripped).is_file()
    ]


def added_doc_pages(
    *, since_days: int = 90, repo_root: Path | None = None
) -> list[str]:
    """Return docs files added within the last ``since_days`` days, per git.

    Runs ``git log --diff-filter=A`` scoped to ``docs/``, then drops paths that
    no longer exist on disk (added-then-renamed files, whose original path would
    404 — see :func:`keep_existing_pages`). ``repo_root`` defaults to the process
    working directory, which is the repository root during a MkDocs build.
    """
    since = (
        datetime.date.today() - datetime.timedelta(days=since_days)
    ).isoformat()
    result = subprocess.run(
        [
            "git",
            "log",
            "--diff-filter=A",
            "--name-only",
            "--format=",
            f"--since={since}",
            "--",
            "docs/",
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return keep_existing_pages(result.stdout.splitlines(), repo_root=repo_root)
