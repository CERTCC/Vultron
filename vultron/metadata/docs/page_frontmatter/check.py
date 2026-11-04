"""Check every page's frontmatter declarations and ``thread:`` (``docs-frontmatter``)."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import (
    nav_exclusion_fault,
    repo_root as _find_repo_root,
)
from vultron.metadata.docs.page_frontmatter.tree import (
    DocsTree,
    classify_docs_tree,
)
from vultron.metadata.docs.page_schema import (
    START_DIR,
    THREAD_KEY,
    PageFrontmatter,
    ThreadDeclaration,
    WorkingRecordFrontmatter,
    is_start_page,
    is_working_record,
)
from vultron.metadata.file_loading import (
    FailureCollector,
    MetadataLoadError,
    load_frontmatter,
    validate,
)

#: The four keys this check owns. Any other frontmatter key belongs to another
#: schema and is ignored here.
DECLARATION_KEYS: tuple[str, ...] = (
    "stakeholder_type",
    "level",
    "page_type",
    "subject",
)


_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:")


@dataclass
class CheckResult:
    """What a passing check saw, for its summary line."""

    reader_pages: int = 0
    working_record_pages: int = 0
    fragments: int = 0


def frontmatter_key_lines(path: Path) -> dict[str, int]:
    """1-based line of each top-level key in *path*'s frontmatter block."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    found: dict[str, int] = {}
    if not lines or lines[0].strip() != "---":
        return found
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            break
        match = _TOP_LEVEL_KEY_RE.match(line)
        if match:
            found.setdefault(match.group(1), number)
    return found


def _declarations(metadata: Mapping[str, object]) -> dict[str, object]:
    return {k: metadata[k] for k in DECLARATION_KEYS if k in metadata}


def _check_declarations(
    path: Path,
    rel: str,
    metadata: Mapping[str, object],
    working: bool,
    tree: DocsTree,
    root: Path,
) -> None:
    """Validate the declarations a page makes (DF-11-001, DF-11-012,
    DF-11-018, DF-11-025).

    Raises:
        MetadataLoadError: If the page declares none of the keys, is included
            whole by another page, or its declarations do not validate.
    """
    declared = _declarations(metadata)
    if not declared:
        wanted = (
            "stakeholder_type: [project-contributor] (working record, "
            "no level, page_type or subject; DF-11-033, DF-11-036, "
            "DF-11-026)"
            if working
            else "stakeholder_type, level (DF-11-001), page_type "
            "(DF-11-018) and subject (DF-11-025)"
        )
        raise MetadataLoadError(
            f"declares none of the keys; add {wanted}",
            path=f"docs/{rel}",
        )

    key_lines = frontmatter_key_lines(path)
    including = tree.whole_includes.get(rel)
    if including:
        key = next(iter(declared))
        raise MetadataLoadError(
            f"is included whole by {', '.join(including)}, which would "
            f"render its {key} into that page (DF-11-004); include "
            f"it between start=/end= markers instead",
            path=f"docs/{rel}",
            line=key_lines.get(key),
        )
    model = WorkingRecordFrontmatter if working else PageFrontmatter
    validate(
        model,
        declared,
        path=path,
        root=root,
        key_lines=key_lines,
    )


def validate_thread(
    path: Path, metadata: Mapping[str, object], root: Path
) -> ThreadDeclaration:
    """Validate the ``thread:`` in a start page's *metadata* (DF-11-013).

    The one validation both ``docs-frontmatter`` and the thread loader
    (:func:`~vultron.metadata.docs.threads.load_threads`) run, so the two
    cannot read a thread two ways; each needs it, because neither can work
    from a thread that does not validate.

    Raises:
        MetadataLoadError: If the thread does not validate, located at the
            ``thread:`` key's line.
    """
    return validate(
        ThreadDeclaration,
        {THREAD_KEY: metadata.get(THREAD_KEY)},
        path=path,
        root=root,
        key_lines=frontmatter_key_lines(path),
    )


def _check_thread(
    path: Path, rel: str, metadata: Mapping[str, object], root: Path
) -> None:
    """Check the ``thread:`` key a page declares, if any (DF-11-013).

    Only a start page opens a thread, so the key anywhere else is a finding.
    Whether each member is an existing reader-facing page is the separate
    ``docs-threads`` check (DF-11-016).

    Raises:
        MetadataLoadError: If a page other than a start page declares a
            thread, or a start page's thread does not validate.
    """
    if THREAD_KEY not in metadata:
        return
    if not is_start_page(rel):
        raise MetadataLoadError(
            f"declares `{THREAD_KEY}:` but is not a start page; a thread is "
            f"declared once, on the docs/{START_DIR}/ page that opens it "
            "(DF-11-013)",
            path=f"docs/{rel}",
            line=frontmatter_key_lines(path).get(THREAD_KEY),
        )
    validate_thread(path, metadata, root)


def check_docs_frontmatter(repo_root: Path | None = None) -> CheckResult:
    """Validate every page's declarations and every fragment's absence of them.

    Args:
        repo_root: Repository root. Defaults to the enclosing checkout.

    Returns:
        Counts for a summary line.

    Raises:
        MetadataLoadError: If no page resolves under ``docs/`` (DF-09-009).
        MetadataLoadErrors: Carrying every finding, each attributed to its
            file as ``path:line:col`` where the fault has a position.
    """
    root = repo_root or _find_repo_root()
    docs_dir = root / "docs"
    tree = (
        classify_docs_tree(root) if docs_dir.is_dir() else DocsTree((), {}, {})
    )
    if not tree.pages:
        raise MetadataLoadError(
            "resolved no pages to check; an empty target set is a failure, "
            "not a pass (DF-09-009)",
            path="docs",
        )

    result = CheckResult(fragments=len(tree.fragments))
    collector = FailureCollector()

    def shown(rel: str) -> str:
        return f"docs/{rel}"

    for rel, hosts in sorted(tree.fragments.items()):
        with collector.attempt():
            path = docs_dir / rel
            declared = _declarations(
                load_frontmatter(path, root=root).metadata
            )
            if declared:
                key = next(iter(declared))
                raise MetadataLoadError(
                    f"an include fragment must not declare {key}; it takes "
                    f"its declarations from the pages hosting it "
                    f"({', '.join(hosts)}) (DF-11-010, DF-11-036, "
                    f"DF-11-026)",
                    path=shown(rel),
                    line=frontmatter_key_lines(path).get(key),
                )

    for rel in tree.pages:
        working = is_working_record(rel)
        misplaced = working and nav_exclusion_fault(
            rel, tree.navved, tree.not_in_nav
        )
        if misplaced:
            # Its own attempt, so a page that is also mis-declared reports both.
            with collector.attempt():
                raise MetadataLoadError(
                    f"is project working record but {misplaced}, and link it "
                    f"from the routing page for its group (DF-11-003)",
                    path=shown(rel),
                )
        metadata: Mapping[str, object] | None = None
        with collector.attempt():
            path = docs_dir / rel
            if working:
                result.working_record_pages += 1
            else:
                result.reader_pages += 1

            metadata = load_frontmatter(path, root=root).metadata
            _check_declarations(path, rel, metadata, working, tree, root)
        if metadata is not None:
            # Its own attempt, so a page that is also mis-declared reports
            # both; a page whose frontmatter did not parse was reported once.
            with collector.attempt():
                _check_thread(docs_dir / rel, rel, metadata, root)

    collector.raise_if_any(
        summary=(
            f"{len(collector.failures)} docs frontmatter finding(s) (DF-11):"
        )
    )
    return result


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-frontmatter`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate stakeholder_type, level, page_type and subject in "
            "docs/ frontmatter."
        )
    )
    parser.parse_args(argv)

    try:
        result = check_docs_frontmatter()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Checked {result.reader_pages} reader-facing and "
        f"{result.working_record_pages} working-record page(s); "
        f"{result.fragments} include fragment(s) excluded."
    )
