"""Render the start-page listing of every thread."""

from __future__ import annotations

import posixpath
import textwrap
from collections.abc import Mapping
from pathlib import Path

from vultron.metadata.docs.landing_pages import WRITE_COMMAND, page_title
from vultron.metadata.docs.page_schema import (
    THREAD_KEY,
    StageKind,
    ThreadMember,
)
from vultron.metadata.docs.threads.check import StartThread
from vultron.metadata.file_loading import (
    MetadataLoadError,
    MetadataLoadErrors,
    load_frontmatter,
)
from vultron.metadata.generated_block import splice_between

#: Opening marker of a start page's generated listing. Names the input and the
#: command, so a reader who found the listing by grep learns where to change it.
LISTING_BEGIN = (
    "<!-- BEGIN GENERATED READING PATH — do not edit; change this page's "
    f"{THREAD_KEY}: frontmatter, then run `{WRITE_COMMAND}` -->"
)


#: Closing marker of a start page's generated listing.
LISTING_END = "<!-- END GENERATED READING PATH -->"


#: The sentence closing a stage marked as a stopping point.
STOPPING_POINT = "You can stop here if this section answered your question."


def page_titles(
    root: Path, threads: tuple[StartThread, ...]
) -> dict[str, str]:
    """Return ``{docs/-relative path: title}`` for every member of *threads*.

    Raises:
        MetadataLoadErrors: Naming every member page that does not exist, not
            only the first (EH-07-001).
    """
    docs_dir = root / "docs"
    titles: dict[str, str] = {}
    missing: list[MetadataLoadError] = []
    for thread in threads:
        for member in thread.members():
            if member.path in titles:
                continue
            path = docs_dir / member.path
            if not path.is_file():
                missing.append(
                    MetadataLoadError(
                        f"lists {member.path} on its thread, which does not "
                        "exist (DF-11-016)",
                        path=f"docs/{thread.path}",
                    )
                )
                continue
            titles[member.path] = page_title(
                load_frontmatter(path, root=root), member.path
            )
    if missing:
        raise MetadataLoadErrors(
            missing, summary=f"{len(missing)} thread member(s) missing:"
        )
    return titles


def _link_text(text: str) -> str:
    """Escape the backslashes and brackets that would end a link's text."""
    return text.replace("\\", "\\\\").replace("[", r"\[").replace("]", r"\]")


def _link(member: ThreadMember, source: str, titles: Mapping[str, str]) -> str:
    """A markdown link to *member* from the page at *source*."""
    href = posixpath.relpath(member.path, posixpath.dirname(source))
    _path, hash_, fragment = member.page.partition("#")
    label = _link_text(member.label or titles[member.path])
    return f"[{label}]({href}{hash_}{fragment})"


def render_listing(thread: StartThread, titles: Mapping[str, str]) -> str:
    """Render the start page's listing: one section per stage (DF-11-014)."""
    blocks: list[str] = []
    for stage in thread.stages:
        block = [f"## {stage.title}"]
        if stage.framing:
            # Line breaks and indentation are kept: docs prose is one
            # sentence per line, and a nested list needs its indent.
            framing = textwrap.dedent(stage.framing).strip("\n")
            block.append(
                "\n".join(line.rstrip() for line in framing.splitlines())
            )
        items = []
        for number, member in enumerate(stage.members, start=1):
            bullet = f"{number}." if stage.kind is StageKind.CHAIN else "-"
            link = _link(member, thread.path, titles)
            items.append(f"{bullet} {link} — {' '.join(member.blurb.split())}")
        block.append("\n".join(items))
        if stage.stopping_point:
            block.append(STOPPING_POINT)
        blocks.append("\n\n".join(block))
    return "\n\n".join(blocks)


def splice_thread_listing(
    current: str, thread: StartThread, titles: Mapping[str, str]
) -> str:
    """Return *current* with its reading-path listing replaced from *thread*.

    Raises:
        ValueError: If the markers are missing, duplicated, or inverted.
    """
    return splice_between(
        current,
        render_listing(thread, titles),
        f"docs/{thread.path}",
        LISTING_BEGIN,
        LISTING_END,
    )
