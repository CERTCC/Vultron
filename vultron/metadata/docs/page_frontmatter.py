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
  declares ``[project-contributor]`` and no ``level`` (DF-11-012).
* a **reader-facing page** — everything else. It declares both keys
  (DF-11-001).

A page included only between ``start=``/``end=`` markers (a user story on its
traceability page, a worked example quoted by the specification's annexes) is
still a page: it has a URL and readers of its own. A page included *whole* has
its frontmatter copied into its host, which would render its declarations
there (DF-11-004), so such a page that declares either key is reported too.

Pages that declare nothing yet are listed in :data:`BASELINE_PATH`. A page in
the baseline is tolerated; an undeclared page that is not is a failure, and so
is a baseline entry that no longer names an undeclared page. The baseline can
therefore only shrink, which lets this check land before the content audit
(#3526) assigns values to the whole tree.

Usage::

    uv run docs-frontmatter                   # check (pre-commit, CI)
    uv run docs-frontmatter --prune-baseline  # drop entries that now declare
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.base import mkdocs_config, nav_paths
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

#: Pages that declare neither key yet. Kept outside ``docs/`` so it is never
#: published; one ``docs/``-relative path per line, ``#`` starts a comment.
BASELINE_PATH = Path(__file__).with_name("page_frontmatter_baseline.txt")

_BASELINE_HEADER = """\
# Pages under docs/ that declare neither stakeholder_type nor level yet.
#
# Maintained by vultron.metadata.docs.page_frontmatter (DF-11-001). This list
# may only shrink: a page not listed here must declare both keys, and a listed
# page that now declares them must be removed — run
# `uv run docs-frontmatter --prune-baseline`. Do not add entries by hand.
"""

# ``{% include-markdown "path" ... %}`` and the plugin's plain ``include``.
_INCLUDE_RE = re.compile(
    r"\{%-?\s*include(?:-markdown)?\s+(?:\"(?P<dq>[^\"]+)\"|'(?P<sq>[^']+)')"
    r"(?P<opts>.*?)-?%\}",
    re.DOTALL,
)
_MARKER_OPTION_RE = re.compile(r"\b(?:start|end)\s*=")
_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:")


@dataclass(frozen=True)
class DocsTree:
    """How each ``docs/**/*.md`` file is classified.

    Attributes:
        pages: ``docs/``-relative paths in the target set.
        fragments: Excluded fragments, each mapped to the pages hosting it.
        whole_includes: Every file included whole, mapped to its hosts.
    """

    pages: tuple[str, ...]
    fragments: Mapping[str, tuple[str, ...]]
    whole_includes: Mapping[str, tuple[str, ...]]


@dataclass
class CheckResult:
    """What a passing check saw, for its summary line."""

    reader_pages: int = 0
    working_record_pages: int = 0
    fragments: int = 0
    undeclared: list[str] = field(default_factory=list)


def _include_targets(docs_dir: Path) -> dict[str, dict[str, bool]]:
    """Map each included ``.md`` file to ``{host: included_whole}``.

    A target opening ``./`` or ``../`` resolves against the including file;
    any other resolves against ``docs/``, matching the include-markdown
    plugin. Globs expand. Targets outside ``docs/`` and non-Markdown targets
    are not pages and are ignored.
    """
    docs_resolved = docs_dir.resolve()
    targets: dict[str, dict[str, bool]] = defaultdict(dict)
    for host_path in sorted(docs_dir.rglob("*.md")):
        host = host_path.relative_to(docs_dir).as_posix()
        text = host_path.read_text(encoding="utf-8", errors="replace")
        for match in _INCLUDE_RE.finditer(text):
            spec = match.group("dq") or match.group("sq")
            if "://" in spec:
                continue
            base = (
                host_path.parent
                if spec.startswith(("./", "../"))
                else docs_dir
            )
            candidates = (
                sorted(base.glob(spec))
                if any(c in spec for c in "*?[")
                else [base / spec]
            )
            whole = not _MARKER_OPTION_RE.search(match.group("opts"))
            for candidate in candidates:
                resolved = candidate.resolve()
                if (
                    resolved.suffix != ".md"
                    or not resolved.is_file()
                    or not resolved.is_relative_to(docs_resolved)
                ):
                    continue
                target = resolved.relative_to(docs_resolved).as_posix()
                targets[target][host] = targets[target].get(host, False) or (
                    whole
                )
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
    )


def _key_lines(path: Path) -> dict[str, int]:
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


def read_baseline(path: Path | None = None) -> set[str]:
    """Return the baselined page paths, ignoring comments and blank lines."""
    path = path or BASELINE_PATH
    if not path.exists():
        return set()
    entries = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            entries.add(entry)
    return entries


def write_baseline(entries: set[str], path: Path | None = None) -> None:
    """Write *entries* sorted, under the explanatory header."""
    path = path or BASELINE_PATH
    body = "".join(f"{entry}\n" for entry in sorted(entries))
    path.write_text(_BASELINE_HEADER + "\n" + body, encoding="utf-8")


def _declarations(metadata: Mapping[str, object]) -> dict[str, object]:
    return {k: metadata[k] for k in DECLARATION_KEYS if k in metadata}


def check_docs_frontmatter(
    repo_root: Path | None = None, baseline: set[str] | None = None
) -> CheckResult:
    """Validate every page's declarations and every fragment's absence of them.

    Args:
        repo_root: Repository root. Defaults to the enclosing checkout.
        baseline: Pages tolerated without declarations. Defaults to the
            contents of :data:`BASELINE_PATH`.

    Returns:
        Counts for a summary line, and the undeclared pages still baselined.

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

    allowed = read_baseline() if baseline is None else baseline
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
                    line=_key_lines(path).get(key),
                )

    for rel in tree.pages:
        with collector.attempt():
            path = docs_dir / rel
            working = is_working_record(rel)
            if working:
                result.working_record_pages += 1
            else:
                result.reader_pages += 1

            declared = _declarations(
                load_frontmatter(path, root=root).metadata
            )
            if not declared:
                if rel in allowed:
                    result.undeclared.append(rel)
                    continue
                wanted = (
                    "stakeholder_type: [project-contributor] (working record, "
                    "no level; DF-11-012)"
                    if working
                    else "stakeholder_type and level (DF-11-001)"
                )
                raise MetadataLoadError(
                    f"declares neither key; add {wanted}", path=shown(rel)
                )

            key_lines = _key_lines(path)
            if rel in allowed:
                raise MetadataLoadError(
                    f"now declares its keys but is still listed in "
                    f"{BASELINE_PATH.name}; run `uv run docs-frontmatter "
                    f"--prune-baseline`",
                    path=shown(rel),
                )
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

    page_set = set(tree.pages)
    for rel in sorted(allowed - page_set):
        with collector.attempt():
            raise MetadataLoadError(
                f"listed in {BASELINE_PATH.name} but is no longer a page "
                f"under docs/; run `uv run docs-frontmatter --prune-baseline`",
                path=shown(rel),
            )

    collector.raise_if_any(
        summary=(
            f"{len(collector.failures)} docs frontmatter finding(s) "
            f"(DF-11):"
        )
    )
    return result


def prune_baseline(
    repo_root: Path | None = None, baseline_path: Path | None = None
) -> int:
    """Drop baseline entries that no longer name an undeclared page.

    Never adds an entry, so it cannot be used to grow the baseline.

    Args:
        repo_root: Repository root. Defaults to the enclosing checkout.
        baseline_path: Baseline file. Defaults to :data:`BASELINE_PATH`.

    Returns:
        How many entries were removed.
    """
    root = repo_root or _find_repo_root()
    docs_dir = root / "docs"
    tree = classify_docs_tree(root)
    current = read_baseline(baseline_path)
    keep = set()
    for rel in current & set(tree.pages):
        try:
            metadata = load_frontmatter(docs_dir / rel, root=root).metadata
        except MetadataLoadError:
            # Unparseable: it is not declaring anything yet, so keep it; the
            # check reports the parse fault on its own.
            keep.add(rel)
            continue
        if not _declarations(metadata):
            keep.add(rel)
    write_baseline(keep, baseline_path)
    return len(current) - len(keep)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-frontmatter`` command."""
    parser = argparse.ArgumentParser(
        description="Validate stakeholder_type and level in docs/ frontmatter."
    )
    parser.add_argument(
        "--prune-baseline",
        action="store_true",
        help="Remove baseline entries for pages that now declare their keys.",
    )
    args = parser.parse_args(argv)

    if args.prune_baseline:
        removed = prune_baseline()
        print(f"Removed {removed} entry(ies) from {BASELINE_PATH.name}.")
        return

    try:
        result = check_docs_frontmatter()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Checked {result.reader_pages} reader-facing and "
        f"{result.working_record_pages} working-record page(s); "
        f"{result.fragments} include fragment(s) excluded; "
        f"{len(result.undeclared)} baselined page(s) still undeclared."
    )


if __name__ == "__main__":
    main()
