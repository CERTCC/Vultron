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
"""Built-site URLs for ``docs/`` source pages, for links a renderer prints.

A link printed from a ``markdown-exec`` block reaches the built HTML as
written: MkDocs neither rewrites a ``.md`` target in it nor validates it
(``vultron/metadata/AGENTS.md``). A renderer therefore prints the URL MkDocs
serves the target page at, relative to the page it prints on. Under
``use_directory_urls`` (the default), ``docs/x/y.md`` is served at ``x/y/``.
A directory-style *relative* URL works both on the deployed ``/Vultron/``
sub-path and under ``mkdocs serve`` at the domain root; a root-absolute link
drops the base path (#3144).
"""

from __future__ import annotations

import posixpath


def url_path(md_path: str) -> str:
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


def relative_url(target: str, *, page_path: str) -> str:
    """Directory-style relative URL from ``page_path`` to ``target`` (both docs paths).

    e.g. ``docs/reference/quick_reference.md`` from ``docs/about/whats_new.md``
    -> ``../../reference/quick_reference/``.
    """
    # The docs-root index collapses to "" (see url_path); posixpath.relpath
    # raises on an empty path, so substitute "." for the repo-root directory.
    page_url = url_path(page_path) or "."
    target_url = url_path(target) or "."
    rel = posixpath.relpath(target_url, page_url)
    return rel + "/" if rel != "." else "./"


__all__ = ["relative_url", "url_path"]
