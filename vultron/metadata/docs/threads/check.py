"""Load each ``docs/start/`` page's ``thread:`` and check the threads (``docs-threads``)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.docs.landing_pages import page_title
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
