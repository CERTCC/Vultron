"""Resolve the relative Markdown links one ``docs/`` page makes to others.

One reader for the ``](target.md)`` form, shared by every check that asks
"which pages does this page link?" (CS-22-001): the routing-page check in
:mod:`~vultron.metadata.docs.landing_pages` and the working-record
reachability test. Anchors, link titles, and absolute URLs are stripped or
skipped so both callers agree on what a link *to a page* is.
"""

from __future__ import annotations

import posixpath
import re

_LINK_RE = re.compile(
    r"\]\((?!https?:|mailto:|#)([^)\s#]+\.md)(?:#[^)\s]*)?(?:\s+\"[^\"]*\")?\)"
)


def link_targets(docs_path: str, text: str) -> set[str]:
    """Return the ``docs/``-relative targets of the relative ``.md`` links in *text*.

    Args:
        docs_path: ``docs/``-relative path of the page *text* came from; link
            targets resolve against its directory.
        text: The page's Markdown source.
    """
    base = posixpath.dirname(docs_path)
    return {
        posixpath.normpath(posixpath.join(base, target))
        for target in _LINK_RE.findall(text)
    }
