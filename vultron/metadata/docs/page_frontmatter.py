"""Validate the ``stakeholder_type`` and ``level`` every ``docs/`` page declares.

Requirements: specs/diataxis-requirements.yaml DF-11-001, DF-11-003,
DF-11-010, DF-11-012, DF-09-009; attribution per MS-17 via
:mod:`vultron.metadata.file_loading`. Schema:
:mod:`vultron.metadata.docs.page_schema`.

Every ``docs/**/*.md`` file is one of three things:

* an **include fragment** — a file some page pulls in whole with
  ``{% include-markdown %}`` and that is not itself in the nav, or a
  ``pymdownx.snippets`` ``auto_append`` file. It has no reader of its own, so it
  is excluded from the target set and reported if it declares either key
  (DF-11-010); its hosts' declarations govern it.
* a **working-record page** — matched by
  :data:`~vultron.metadata.docs.page_schema.WORKING_RECORD_PATTERNS`. It
  declares ``[project-contributor]`` and no ``level`` (DF-11-012), and it is
  absent from the ``mkdocs.yml`` nav and matched by ``not_in_nav``
  (DF-11-003).
* a **reader-facing page** — everything else. It declares both keys
  (DF-11-001).

A page included only from a ``start=`` marker (a user story on its
traceability page, a worked example quoted by the specification's annexes) is
still a page: it has a URL and readers of its own. A page included *whole* has
its frontmatter copied into its host, which would render its declarations
there (DF-11-004), so such a page that declares either key is reported too.

Every page declares: an undeclared page is a failure. The shrink-only
baseline that let this check land before the content audit (#3526) reached
zero and was retired.

Usage::

    uv run docs-frontmatter   # check (pre-commit, CI)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pathspec.gitignore import GitIgnoreSpec

from vultron.metadata.base import (
    mkdocs_config,
    nav_exclusion_fault,
    nav_paths,
    not_in_nav_spec,
)
from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.docs.page_schema import (
    PageFrontmatter,
    WorkingRecordFrontmatter,
    is_working_record,
)
from vultron.metadata.file_loading import (
    FailureCollector,
    MetadataLoadError,
    load_frontmatter,
    validate,
)

#: The two keys this check owns. Any other frontmatter key belongs to another
#: schema and is ignored here.
DECLARATION_KEYS: tuple[str, ...] = ("stakeholder_type", "level")

# ``{% include-markdown "path" ... %}`` and the plugin's plain ``include``.
_INCLUDE_RE = re.compile(
    r"\{%-?\s*include(?:-markdown)?\s+(?:\"(?P<dq>[^\"]+)\"|'(?P<sq>[^']+)')"
    r"(?P<opts>.*?)-?%\}",
    re.DOTALL,
)
# Only ``start=`` skips the top of the file. An include with just ``end=``
# copies from line 1, frontmatter included, so it is still a whole include.
_START_OPTION_RE = re.compile(r"\bstart\s*=")
_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:")


@dataclass(frozen=True)
class DocsTree:
    """How each ``docs/**/*.md`` file is classified.

    Attributes:
        pages: ``docs/``-relative paths in the target set.
        fragments: Excluded fragments, each mapped to the pages hosting it.
        whole_includes: Every file included whole, mapped to its hosts.
        navved: Every path the ``mkdocs.yml`` nav references.
        not_in_nav: The ``mkdocs.yml`` ``not_in_nav`` patterns.
    """

    pages: tuple[str, ...]
    fragments: Mapping[str, tuple[str, ...]]
    whole_includes: Mapping[str, tuple[str, ...]]
    navved: frozenset[str] = frozenset()
    not_in_nav: GitIgnoreSpec = field(
        default_factory=lambda: GitIgnoreSpec.from_lines([])
    )


@dataclass
class CheckResult:
    """What a passing check saw, for its summary line."""

    reader_pages: int = 0
    working_record_pages: int = 0
    fragments: int = 0


def include_directives(
    host_path: Path, docs_dir: Path
) -> Iterator[tuple[int, str, bool]]:
    """Yield ``(offset, target, whole)`` for each ``.md`` file *host_path* includes.

    A target opening ``./`` or ``../`` resolves against the including file;
    any other resolves against ``docs/``, matching the include-markdown
    plugin. Globs expand. Targets outside ``docs/`` and non-Markdown targets
    are not pages and are skipped. *offset* is where the directive starts in
    the host's source, and *target* is ``docs/``-relative.
    """
    docs_resolved = docs_dir.resolve()
    text = host_path.read_text(encoding="utf-8", errors="replace")
    for match in _INCLUDE_RE.finditer(text):
        spec = match.group("dq") or match.group("sq")
        if "://" in spec:
            continue
        base = host_path.parent if spec.startswith(("./", "../")) else docs_dir
        candidates = (
            sorted(base.glob(spec))
            if any(c in spec for c in "*?[")
            else [base / spec]
        )
        whole = not _START_OPTION_RE.search(match.group("opts"))
        for candidate in candidates:
            resolved = candidate.resolve()
            if (
                resolved.suffix == ".md"
                and resolved.is_file()
                and resolved.is_relative_to(docs_resolved)
            ):
                target = resolved.relative_to(docs_resolved).as_posix()
                yield match.start(), target, whole


def _include_targets(docs_dir: Path) -> dict[str, dict[str, bool]]:
    """Map each included ``.md`` file to ``{host: included_whole}``."""
    targets: dict[str, dict[str, bool]] = defaultdict(dict)
    for host_path in sorted(docs_dir.rglob("*.md")):
        host = host_path.relative_to(docs_dir).as_posix()
        for _, target, whole in include_directives(host_path, docs_dir):
            targets[target][host] = targets[target].get(host, False) or whole
    return targets


def _auto_appended(root: Path, docs_dir: Path) -> set[str]:
    """``docs/``-relative files ``pymdownx.snippets`` appends to every page."""
    found: set[str] = set()
    extensions = mkdocs_config(root).get("markdown_extensions") or []
    if not isinstance(extensions, list):
        return found
    for entry in extensions:
        if not isinstance(entry, dict):
            continue
        options = entry.get("pymdownx.snippets")
        if not isinstance(options, dict):
            continue
        for item in options.get("auto_append") or []:
            path = (root / str(item)).resolve()
            if path.is_relative_to(docs_dir.resolve()):
                found.add(path.relative_to(docs_dir.resolve()).as_posix())
    return found


def classify_docs_tree(root: Path) -> DocsTree:
    """Split ``docs/**/*.md`` into target pages and excluded fragments."""
    docs_dir = root / "docs"
    every = sorted(
        p.relative_to(docs_dir).as_posix() for p in docs_dir.rglob("*.md")
    )
    navved = nav_paths(root)
    includes = _include_targets(docs_dir)
    whole_includes = {
        target: tuple(sorted(h for h, whole in hosts.items() if whole))
        for target, hosts in includes.items()
        if any(hosts.values())
    }
    fragments: dict[str, tuple[str, ...]] = {
        target: hosts
        for target, hosts in whole_includes.items()
        if target not in navved
    }
    for appended in _auto_appended(root, docs_dir):
        fragments.setdefault(appended, ("every page (snippets auto_append)",))
    return DocsTree(
        pages=tuple(p for p in every if p not in fragments),
        fragments=fragments,
        whole_includes=whole_includes,
        navved=navved,
        not_in_nav=not_in_nav_spec(root),
    )


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
                    f"both keys from the pages hosting it ({', '.join(hosts)})"
                    f" (DF-11-010)",
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
        with collector.attempt():
            path = docs_dir / rel
            if working:
                result.working_record_pages += 1
            else:
                result.reader_pages += 1

            declared = _declarations(
                load_frontmatter(path, root=root).metadata
            )
            if not declared:
                wanted = (
                    "stakeholder_type: [project-contributor] (working record, "
                    "no level; DF-11-012)"
                    if working
                    else "stakeholder_type and level (DF-11-001)"
                )
                raise MetadataLoadError(
                    f"declares neither key; add {wanted}", path=shown(rel)
                )

            key_lines = frontmatter_key_lines(path)
            including = tree.whole_includes.get(rel)
            if including:
                key = next(iter(declared))
                raise MetadataLoadError(
                    f"is included whole by {', '.join(including)}, which would "
                    f"render its {key} into that page (DF-11-004); include "
                    f"it between start=/end= markers instead",
                    path=shown(rel),
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

    collector.raise_if_any(
        summary=(
            f"{len(collector.failures)} docs frontmatter finding(s) "
            f"(DF-11):"
        )
    )
    return result


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-frontmatter`` command."""
    parser = argparse.ArgumentParser(
        description="Validate stakeholder_type and level in docs/ frontmatter."
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


if __name__ == "__main__":
    main()
