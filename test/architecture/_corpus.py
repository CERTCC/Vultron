"""Shared module-level source + AST corpus for test/architecture/ ratchet tests.

Reads all ``*.py`` source strings from ``vultron/`` and ``test/`` at import
time (module-level — outside the 5-second per-test timeout window).  ASTs are
cached lazily on first demand so only the files actually needed by each ratchet
are ever parsed.

Also caches ``docs/**/*.md`` text for ratchets that assert documentation prose
against code (:func:`docs_mentioning`, :func:`all_docs`).  Markdown has no
parse tier because these ratchets match on text.

See ``notes/architecture-ratchet-corpus.md`` for the full design rationale and
performance measurements.

Spec: ``specs/testability.yaml`` TB-13-001 through TB-13-003.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

#: Repository root (two levels above ``test/architecture/``).
REPO_ROOT = Path(__file__).parents[2]

_SCAN_ROOTS = [REPO_ROOT / "vultron", REPO_ROOT / "test"]

_DOCS_ROOT = REPO_ROOT / "docs"

#: Directory names under ``docs/`` excluded from the markdown cache.
#: ``codebase`` holds a gitignored local scan artifact, not authored prose.
_DOCS_SKIP_DIRS = frozenset({"codebase"})

# ---------------------------------------------------------------------------
# Module-level source cache — populated at import time.
# Import-time I/O is not subject to the pytest-timeout 5 s per-test budget
# (verified experimentally; see notes/architecture-ratchet-corpus.md).
# ---------------------------------------------------------------------------
_source_cache: dict[Path, str] = {}

for _root in _SCAN_ROOTS:
    for _py_file in sorted(_root.rglob("*.py")):
        if "__pycache__" in _py_file.parts:
            continue
        try:
            _source_cache[_py_file] = _py_file.read_text(encoding="utf-8")
        except OSError:
            pass

# ---------------------------------------------------------------------------
# Module-level markdown cache for ``docs/`` — also populated at import time,
# for ratchets that assert docs prose against code. Markdown needs no parse
# step, so there is no lazy tier: ~555 files / 2.7 MB read in ~0.1 s.
# ---------------------------------------------------------------------------
_docs_cache: dict[Path, str] = {}

for _md_file in sorted(_DOCS_ROOT.rglob("*.md")):
    if _DOCS_SKIP_DIRS.intersection(_md_file.parts):
        continue
    try:
        _docs_cache[_md_file] = _md_file.read_text(encoding="utf-8")
    except OSError:
        pass

# ---------------------------------------------------------------------------
# Lazy AST cache — trees are parsed and stored on first demand.
# ---------------------------------------------------------------------------
_ast_cache: dict[Path, ast.AST] = {}


def _get_tree(path: Path) -> ast.AST | None:
    """Return the cached AST for *path*, parsing on first access."""
    if path not in _ast_cache:
        source = _source_cache.get(path)
        if source is None:
            return None
        try:
            _ast_cache[path] = ast.parse(source, filename=str(path))
        except SyntaxError:
            return None
    return _ast_cache[path]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def files_mentioning(
    *fragments: str, under: Path
) -> Iterator[tuple[Path, ast.AST]]:
    """Yield ``(path, tree)`` for cached files under *under* containing any fragment.

    Applies a plain substring prefilter before parsing — O(n) over source
    bytes, keeping per-ratchet cost proportional to match count rather than
    total file count (TB-13-001, TB-13-002, TB-13-007, TB-13-008).
    """
    for path in sorted(_source_cache.keys()):
        try:
            path.relative_to(under)
        except ValueError:
            continue
        source = _source_cache[path]
        if not any(fragment in source for fragment in fragments):
            continue
        tree = _get_tree(path)
        if tree is not None:
            yield path, tree


def all_trees(under: Path) -> Iterator[tuple[Path, ast.AST]]:
    """Yield ``(path, tree)`` for every cached ``.py`` file under *under*.

    Escape hatch for ratchets that have no useful prefilter fragment.
    TB-13-002.
    """
    for path in sorted(_source_cache.keys()):
        try:
            path.relative_to(under)
        except ValueError:
            continue
        tree = _get_tree(path)
        if tree is not None:
            yield path, tree


def sources_mentioning(
    *fragments: str, under: Path
) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, source)`` for files under *under* containing any fragment.

    For ratchets that scan source lines rather than AST nodes.
    """
    for path in sorted(_source_cache.keys()):
        try:
            path.relative_to(under)
        except ValueError:
            continue
        source = _source_cache[path]
        if any(fragment in source for fragment in fragments):
            yield path, source


def all_sources(under: Path) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, source)`` for every cached ``.py`` file under *under*."""
    for path in sorted(_source_cache.keys()):
        try:
            path.relative_to(under)
        except ValueError:
            continue
        yield path, _source_cache[path]


def docs_mentioning(*fragments: str) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, text)`` for cached ``docs/**/*.md`` containing any fragment.

    The markdown counterpart to :func:`sources_mentioning`. Use this rather than
    globbing ``docs/`` directly, so docs ratchets route through the shared
    import-time cache like their Python siblings (TB-13-003).
    """
    for path in sorted(_docs_cache.keys()):
        text = _docs_cache[path]
        if any(fragment in text for fragment in fragments):
            yield path, text


def all_docs() -> Iterator[tuple[Path, str]]:
    """Yield ``(path, text)`` for every cached ``docs/**/*.md`` file."""
    for path in sorted(_docs_cache.keys()):
        yield path, _docs_cache[path]


def parse_inline(source: str, filename: str = "<inline>") -> ast.AST:
    """Parse a short inline source string.

    Provided so test siblings can avoid importing ``ast`` directly, keeping
    the hygiene ratchet (TB-13-003) unambiguous.
    """
    return ast.parse(source, filename=filename)
