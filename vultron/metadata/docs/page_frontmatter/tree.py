"""Classify the docs tree: include directives, include targets and which pages declare frontmatter."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pathspec.gitignore import GitIgnoreSpec

from vultron.metadata.base import (
    excluded_docs_spec,
    mkdocs_config,
    nav_paths,
    not_in_nav_spec,
)

# ``{% include-markdown "path" ... %}`` and the plugin's plain ``include``.
_INCLUDE_RE = re.compile(
    r"\{%-?\s*include(?:-markdown)?\s+(?:\"(?P<dq>[^\"]+)\"|'(?P<sq>[^']+)')"
    r"(?P<opts>.*?)-?%\}",
    re.DOTALL,
)


# Only ``start=`` skips the top of the file. An include with just ``end=``
# copies from line 1, frontmatter included, so it is still a whole include.
_START_OPTION_RE = re.compile(r"\bstart\s*=")


# Either marker can cut a link out of what renders.
_CUT_OPTION_RE = re.compile(r"\b(?:start|end)\s*=")


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


def include_directives(
    host_path: Path,
    docs_dir: Path,
    *,
    uncut: bool = False,
    existing: bool = True,
) -> Iterator[tuple[int, str, bool]]:
    """Yield ``(offset, target, whole)`` for each ``.md`` file *host_path* includes.

    A target opening ``./`` or ``../`` resolves against the including file;
    any other resolves against ``docs/``, matching the include-markdown
    plugin. Globs expand. Targets outside ``docs/`` and non-Markdown targets
    are not pages and are skipped. *offset* is where the directive starts in
    the host's source, and *target* is ``docs/``-relative. *whole* means no
    ``start=``, so the target's frontmatter renders; with *uncut* it also
    means no ``end=``, so every link in the target renders. With
    *existing* false, a target that does not exist yet is yielded too, so a
    generator can read the directives naming a file it is about to write.
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
        cut_re = _CUT_OPTION_RE if uncut else _START_OPTION_RE
        whole = not cut_re.search(match.group("opts"))
        for candidate in candidates:
            resolved = candidate.resolve()
            if (
                resolved.suffix == ".md"
                and (resolved.is_file() or not existing)
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
    # An excluded file is never built, so it has no reader of its own; until
    # a page includes it (and it becomes a fragment above) it is neither.
    # This holds for every `exclude_docs` pattern, not only the occasion
    # fragments: a page excluded by mistake also leaves DF-11's scope, so
    # widen `exclude_docs` only for files that are never pages.
    excluded = excluded_docs_spec(mkdocs_config(root))
    return DocsTree(
        pages=tuple(
            p
            for p in every
            if p not in fragments and not excluded.match_file(p)
        ),
        fragments=fragments,
        whole_includes=whole_includes,
        navved=navved,
        not_in_nav=not_in_nav_spec(root),
    )
