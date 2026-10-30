"""Reading-path threads: load, check, and render them at both ends.

Requirements: specs/diataxis-requirements.yaml DF-11-013 (a thread is staged
data on its start page), DF-11-014 (the start page's listing is generated and
check gated), DF-11-015 (each member page and start page shows a start,
previous, current and next table per thread), DF-11-016 (the thread check),
DF-11-022 (a section member's box names the section), DF-11-023 (each box is a
committed fragment), DF-11-044 (placed by hand), DF-11-034 (the table's cells),
DF-11-009 (titled by situation, never by ``stakeholder_type``), DF-09-009 (an
empty target set fails). Design rationale:
``notes/site-information-architecture.md`` § "Threads: staged data, rendered at
both ends" (ADR-0150).

A thread is a partial order, not a sequence. It lives in one place, the
``thread:`` frontmatter of the start page that opens it
(:class:`~vultron.metadata.docs.page_schema.ThreadDeclaration`), and is shown
in two:

* on the **start page**, as the listing between :data:`LISTING_BEGIN` and
  :data:`LISTING_END`, which ``uv run docs-site --write`` splices in
  (:mod:`~vultron.metadata.docs.site_sync`) — a stage is a section, a chain a
  numbered list, a set a bulleted one;
* on the start page and each **member page**, as a box per thread: a
  committed fragment under :data:`BOX_DIR` that ``docs-site --write``
  generates (:func:`render_boxes`) and the page's author places with an
  ``include-markdown`` line. Its table holds the start page, the pages before
  and after the page, both as sets (:func:`position`), and the page itself.
  That every page renders its boxes is the built-site check
  (:mod:`~vultron.metadata.docs.path_boxes`).

``uv run docs-threads`` is the thread check (DF-11-016), a pre-commit hook
with ``test_the_committed_threads_pass`` as its CI backstop. That no member
runs ahead of its thread is ``docs-thread-order``'s check
(:mod:`~vultron.metadata.docs.thread_order`, DF-11-024).
"""

from __future__ import annotations

import argparse
import html
import posixpath
import sys
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.docs.landing_pages import WRITE_COMMAND, page_title
from vultron.metadata.docs.page_frontmatter import (
    classify_docs_tree,
    validate_thread,
)
from vultron.metadata.docs.page_schema import (
    START_DIR,
    THREAD_KEY,
    StageKind,
    ThreadMember,
    ThreadStage,
    is_start_page,
    is_working_record,
)
from vultron.metadata.file_loading import (
    FailureCollector,
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


@dataclass(frozen=True, slots=True)
class StartThread:
    """The thread one start page opens.

    Attributes:
        path: ``docs/``-relative path of the start page.
        title: The start page's title, which names the reader's situation; a
            member page's box is titled by it (DF-11-009).
        stages: The thread's stages, in reading order.
    """

    path: str
    title: str
    stages: tuple[ThreadStage, ...]

    def members(self) -> list[ThreadMember]:
        """Every member, in reading order."""
        return [member for stage in self.stages for member in stage.members]


@dataclass(frozen=True, slots=True)
class ThreadPosition:
    """Where a page sits on a thread (DF-11-015).

    Attributes:
        stage: The stage the page belongs to.
        before: The thread pages immediately before it.
        after: The thread pages immediately after it.
    """

    stage: ThreadStage
    before: tuple[ThreadMember, ...]
    after: tuple[ThreadMember, ...]


def _entry(stage: ThreadStage) -> tuple[ThreadMember, ...]:
    """A stage's entry pages: all of a set, the first of a chain."""
    if stage.kind is StageKind.SET:
        return tuple(stage.members)
    return (stage.members[0],)


def _exit(stage: ThreadStage) -> tuple[ThreadMember, ...]:
    """A stage's exit pages: all of a set, the last of a chain."""
    if stage.kind is StageKind.SET:
        return tuple(stage.members)
    return (stage.members[-1],)


def position(thread: StartThread, page: str) -> ThreadPosition | None:
    """Return where the ``docs/``-relative *page* sits on *thread*.

    The set before a page is the preceding member of its chain, or else the
    previous stage's exit pages; the set after it is the next member of its
    chain, or else the next stage's entry pages (DF-11-034). ``None`` when
    the page is not on the thread. A page is on a thread at most once
    (DF-11-016), so the first match is the only one.
    """
    stages = thread.stages
    for index, stage in enumerate(stages):
        for offset, member in enumerate(stage.members):
            if member.path != page:
                continue
            chained = stage.kind is StageKind.CHAIN
            if chained and offset > 0:
                before: tuple[ThreadMember, ...] = (stage.members[offset - 1],)
            else:
                before = _exit(stages[index - 1]) if index > 0 else ()
            if chained and offset < len(stage.members) - 1:
                after: tuple[ThreadMember, ...] = (stage.members[offset + 1],)
            else:
                after = (
                    _entry(stages[index + 1])
                    if index + 1 < len(stages)
                    else ()
                )
            return ThreadPosition(stage=stage, before=before, after=after)
    return None


def _start_page_paths(docs_dir: Path) -> list[str]:
    start = docs_dir / START_DIR
    if not start.is_dir():
        return []
    return [
        rel
        for rel in (
            p.relative_to(docs_dir).as_posix()
            for p in sorted(start.glob("*.md"))
        )
        if is_start_page(rel)
    ]


def _duplicate_faults(thread: StartThread) -> list[MetadataLoadError]:
    """One fault per page listed more than once on *thread* (DF-11-016)."""
    seen: set[str] = set()
    reported: set[str] = set()
    faults: list[MetadataLoadError] = []
    for member in thread.members():
        if member.path in seen and member.path not in reported:
            reported.add(member.path)
            faults.append(
                MetadataLoadError(
                    f"lists {member.path} more than once on its thread; a "
                    "page has one place on a thread (DF-11-016)",
                    path=f"docs/{thread.path}",
                )
            )
        seen.add(member.path)
    return faults


def load_threads(root: Path) -> tuple[StartThread, ...]:
    """Return the thread of every start page under ``docs/start/``.

    May be empty; :func:`check_threads` is what refuses an empty set.

    Raises:
        MetadataLoadErrors: Carrying every finding: a start page that declares
            no ``thread:``, one whose thread does not validate (DF-11-013), or
            one listing a page twice (DF-11-016).
    """
    docs_dir = root / "docs"
    collector = FailureCollector()
    threads: list[StartThread] = []
    for rel in _start_page_paths(docs_dir):
        with collector.attempt():
            path = docs_dir / rel
            post = load_frontmatter(path, root=root)
            if THREAD_KEY not in post.metadata:
                raise MetadataLoadError(
                    f"is a start page but declares no `{THREAD_KEY}:`; a start "
                    "page's reading path is its thread, declared as data "
                    "(DF-11-013, DF-11-014)",
                    path=f"docs/{rel}",
                )
            declared = validate_thread(path, post.metadata, root)
            thread = StartThread(
                path=rel,
                title=page_title(post, rel),
                stages=tuple(declared.thread),
            )
            duplicates = _duplicate_faults(thread)
            collector.failures.extend(duplicates)
            if not duplicates:
                threads.append(thread)
    collector.raise_if_any(
        summary=f"{len(collector.failures)} thread finding(s) (DF-11-013):"
    )
    return tuple(threads)


def thread_faults(
    root: Path, threads: tuple[StartThread, ...]
) -> list[MetadataLoadError]:
    """One fault per member that is not an existing reader-facing page.

    A member must exist, must not be project working record (DF-11-003), and
    must be a page rather than an include fragment or an excluded file
    (DF-11-016). Every fault is reported, not only the first (EH-07-001).
    """
    docs_dir = root / "docs"
    pages = frozenset(classify_docs_tree(root).pages)
    faults: list[MetadataLoadError] = []
    for thread in threads:
        for member in thread.members():
            if not (docs_dir / member.path).is_file():
                problem = "does not exist"
            elif is_working_record(member.path):
                problem = (
                    "is project working record, not a reader-facing page "
                    "(DF-11-003)"
                )
            elif member.path not in pages:
                problem = (
                    "is not a page: it is an include fragment or excluded "
                    "from the build"
                )
            else:
                continue
            faults.append(
                MetadataLoadError(
                    f"lists {member.path} on its thread, which {problem} "
                    "(DF-11-016)",
                    path=f"docs/{thread.path}",
                )
            )
    return faults


def check_threads(root: Path) -> tuple[StartThread, ...]:
    """Run the thread check (DF-11-016) and return the threads it read.

    Raises:
        MetadataLoadError: If no start page declares a thread (DF-09-009).
        MetadataLoadErrors: As :func:`load_threads`, or carrying every member
            that is not an existing reader-facing page.
    """
    threads = load_threads(root)
    if not threads:
        raise MetadataLoadError(
            "resolved no reading-path threads; an empty target set is a "
            "failure, not a pass (DF-11-016, DF-09-009)",
            path=f"docs/{START_DIR}",
        )
    faults = thread_faults(root, threads)
    if faults:
        raise MetadataLoadErrors(
            faults, summary=f"{len(faults)} thread member finding(s):"
        )
    return threads


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


#: ``docs/``-relative directory of the committed box fragments, one
#: subdirectory per thread (DF-11-023). Listed in ``exclude_docs``: a fragment
#: reaches a reader only through the ``include-markdown`` line its page's
#: author places.
BOX_DIR = f"{START_DIR}/_paths"

#: Shown in a box cell whose set is empty: the first page has no previous
#: set, the last no next set, and a start page no previous set (DF-11-034).
EMPTY_CELL = "---"

#: The box's column headings, in order (DF-11-015).
BOX_COLUMNS = ("Start", "Previous", "Current", "Next")

#: The class every rendered box carries, beside Material's admonition
#: classes, so the built-site check can find it (DF-11-045).
BOX_CLASS = "reading-path"

#: The attributes naming the thread and the target a rendered box was made
#: for: the start page's stem, and the member's ``page`` (anchor included) or
#: the start page's path (DF-11-023).
THREAD_ATTR = "data-thread"
MEMBER_ATTR = "data-member"

#: Separators of a fragment's file name: a ``/`` of the page path, and the
#: ``#`` before a section member's anchor.
_DIR_SEP = "__"
_ANCHOR_SEP = "--"


def thread_name(thread: StartThread) -> str:
    """The thread's name: its start page's file stem (``coordinate-cases``)."""
    return posixpath.splitext(posixpath.basename(thread.path))[0]


def box_targets(thread: StartThread) -> list[str]:
    """Every page string that carries a box of *thread*, in reading order.

    The start page's path first, then each member's ``page``, with a section
    member's anchor kept: a section's box is not its page's box (DF-11-022).
    """
    return [thread.path, *(member.page for member in thread.members())]


def box_fragment_path(thread: StartThread, target: str) -> str:
    """Return the ``docs/``-relative fragment holding *target*'s box.

    ``topics/a/b.md`` gives ``start/_paths/<thread>/topics__a__b.md``, and
    ``reference/glossary.md#roles`` gives ``…/reference__glossary--roles.md``,
    so two sections of one page do not collide (DF-11-023).
    """
    path, _hash, anchor = target.partition("#")
    stem = path.removesuffix(".md").replace("/", _DIR_SEP)
    if anchor:
        stem = f"{stem}{_ANCHOR_SEP}{anchor}"
    return f"{BOX_DIR}/{thread_name(thread)}/{stem}.md"


def include_line(host: str, fragment: str) -> str:
    """The ``include-markdown`` line that places *fragment* on page *host*.

    Both are ``docs/``-relative; the included path is relative to the host
    page and starts with ``./`` or ``../``, the form ``include-markdown``
    resolves against the host page rather than the working directory.
    """
    rel = posixpath.relpath(fragment, posixpath.dirname(host) or ".")
    if not rel.startswith("../"):
        rel = f"./{rel}"
    return f'{{% include-markdown "{rel}" %}}'


def _box_marker(thread: StartThread) -> str:
    """The comment opening a fragment: where it comes from, and how to change it."""
    return (
        "<!-- GENERATED READING PATH BOX — do not edit; change "
        f"docs/{thread.path}'s {THREAD_KEY}: frontmatter, then run "
        f"`{WRITE_COMMAND}` -->"
    )


def _text_cell(text: str) -> list[str]:
    return ["", f"- {_link_text(text)}", ""]


def _link_cell(links: list[str]) -> list[str]:
    return ["", *(f"- {link}" for link in links), ""]


def _cell(body: list[str] | None) -> str:
    """One ``<td>``: Markdown-processed when it holds a list (``md_in_html``)."""
    if body is None:
        return f"<td>{EMPTY_CELL}</td>"
    return "\n".join(['<td markdown="block">', *body, "</td>"])


def render_box(
    thread: StartThread, target: str, titles: Mapping[str, str]
) -> str:
    """Render *thread*'s box for *target*: its start page or a member's ``page``.

    The box is an admonition titled by the start page's situation, the same
    for every reader: no ``stakeholder_type``, no level, no script, no query
    string (DF-11-009, DF-11-035). A member's box names its stage, as a page
    or, for a ``page.md#anchor`` member, a section (DF-11-022); a start page's
    names none. The table is HTML whose cells ``md_in_html`` processes as
    Markdown, so MkDocs rewrites and validates every link in it; links are
    relative to the fragment, and ``include-markdown`` rewrites them for the
    page that includes it.

    Raises:
        ValueError: If *target* is neither the start page nor a member.
    """
    fragment = box_fragment_path(thread, target)
    start_href = posixpath.relpath(thread.path, posixpath.dirname(fragment))
    start_link = f"[{_link_text(thread.title)}]({start_href})"
    if target == thread.path:
        stage_line: list[str] = []
        start = _text_cell(thread.title)
        before: list[str] | None = None
        current = _text_cell(thread.title)
        after_members = _entry(thread.stages[0]) if thread.stages else ()
    else:
        member = next((m for m in thread.members() if m.page == target), None)
        where = position(thread, member.path) if member else None
        if member is None or where is None:
            raise ValueError(
                f"{target} is not on the thread of docs/{thread.path}"
            )
        unit = "section" if "#" in member.page else "page"
        stage_line = [f"This {unit} is part of *{where.stage.title}*.", ""]
        start = _link_cell([start_link])
        before = (
            _link_cell([_link(m, fragment, titles) for m in where.before])
            if where.before
            else None
        )
        current = _text_cell(member.label or titles[member.path])
        after_members = where.after
    after = (
        _link_cell([_link(m, fragment, titles) for m in after_members])
        if after_members
        else None
    )
    headings = "".join(f"<th>{name}</th>" for name in BOX_COLUMNS)
    lines = [
        _box_marker(thread),
        "",
        f'<div class="admonition abstract {BOX_CLASS}" '
        f'{THREAD_ATTR}="{html.escape(thread_name(thread))}" '
        f'{MEMBER_ATTR}="{html.escape(target)}" markdown>',
        '<p class="admonition-title">Reading path: '
        f"{html.escape(thread.title)}</p>",
        "",
        *stage_line,
        f'<table class="{BOX_CLASS}-table" markdown>',
        f"<thead><tr>{headings}</tr></thead>",
        "<tbody markdown>",
        "<tr markdown>",
        *(_cell(body) for body in (start, before, current, after)),
        "</tr>",
        "</tbody>",
        "</table>",
        "",
        "</div>",
    ]
    return "\n".join(lines) + "\n"


def render_boxes(
    threads: tuple[StartThread, ...], titles: Mapping[str, str]
) -> dict[str, str]:
    """Return ``{docs/-relative fragment path: box}`` for every thread target.

    Raises:
        ValueError: If two targets of one thread would share a fragment name.
    """
    boxes: dict[str, str] = {}
    owner: dict[str, str] = {}
    for thread in threads:
        for target in box_targets(thread):
            fragment = box_fragment_path(thread, target)
            if fragment in owner:
                raise ValueError(
                    f"docs/{thread.path}: {owner[fragment]} and {target} "
                    f"would share the box fragment docs/{fragment}"
                )
            owner[fragment] = target
            boxes[fragment] = render_box(thread, target, titles)
    return boxes


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-threads`` command."""
    parser = argparse.ArgumentParser(
        description="Check every start page's reading-path thread (DF-11-016)."
    )
    parser.parse_args(argv)
    try:
        threads = check_threads(_find_repo_root())
    except (MetadataLoadError, OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    members = sum(len(thread.members()) for thread in threads)
    print(f"Checked {len(threads)} thread(s) with {members} member page(s).")


if __name__ == "__main__":
    main()
