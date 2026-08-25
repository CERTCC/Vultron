"""Shared module-level source + AST corpus for test/architecture/ ratchet tests.

Reads all ``*.py`` source strings from ``vultron/`` and ``test/`` at import
time (module-level — outside the 5-second per-test timeout window).  ASTs are
cached lazily on first demand so only the files actually needed by each ratchet
are ever parsed.

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


def parse_inline(source: str, filename: str = "<inline>") -> ast.AST:
    """Parse a short inline source string.

    Provided so test siblings can avoid importing ``ast`` directly, keeping
    the hygiene ratchet (TB-13-003) unambiguous.
    """
    return ast.parse(source, filename=filename)
