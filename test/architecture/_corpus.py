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
import contextlib
import functools
import gc
import inspect
import os
import re
from collections.abc import Iterator
from pathlib import Path

#: Repository root (two levels above ``test/architecture/``).
REPO_ROOT = Path(__file__).parents[2]

_SCAN_ROOTS = [REPO_ROOT / "vultron", REPO_ROOT / "test"]

_DOCS_ROOT = REPO_ROOT / "docs"

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
# step, so there is no lazy tier: ~556 files / 2.8 MB read in ~0.03 s.
#
# No directory is excluded.  The ``*.md`` glob already skips the only
# non-authored content under ``docs/`` — the gitignored ``.codebase-scan.txt``
# artifacts — while ``docs/reference/codebase/`` holds eight tracked, authored
# reference pages that docs ratchets must be able to see.
#
# ``UnicodeDecodeError`` is not an ``OSError``, and this loop runs at import
# time, so letting one escape would error out every ratchet module at
# collection rather than skipping a single file.
# ---------------------------------------------------------------------------
_docs_cache: dict[Path, str] = {}

for _md_file in sorted(_DOCS_ROOT.rglob("*.md")):
    try:
        _docs_cache[_md_file] = _md_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        pass

#: The cached paths in ``Path`` order with their strings, computed once: sorting ``Path`` objects
#: and calling ``Path.relative_to`` per file on every query cost ~0.1 s per
#: call, which a ratchet with several queries pays inside its time budget.
_sorted_paths: list[tuple[str, Path]] = [
    (str(path), path) for path in sorted(_source_cache)
]


def _paths_under(under: Path) -> Iterator[Path]:
    """Cached paths at or below *under*, in sorted order (string prefix test)."""
    root = str(under)
    prefix = root.rstrip(os.sep) + os.sep
    for text, path in _sorted_paths:
        if text == root or text.startswith(prefix):
            yield path


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
    for path in _paths_under(under):
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
    for path in _paths_under(under):
        tree = _get_tree(path)
        if tree is not None:
            yield path, tree


def sources_mentioning(
    *fragments: str, under: Path
) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, source)`` for files under *under* containing any fragment.

    For ratchets that scan source lines rather than AST nodes.
    """
    for path in _paths_under(under):
        source = _source_cache[path]
        if any(fragment in source for fragment in fragments):
            yield path, source


def all_sources(under: Path) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, source)`` for every cached ``.py`` file under *under*."""
    for path in _paths_under(under):
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


@contextlib.contextmanager
def gc_paused() -> Iterator[None]:
    """Pause the cyclic garbage collector for a burst of AST allocation.

    A scan that parses and walks a few hundred modules allocates hundreds of
    thousands of nodes, and each allocation threshold triggers a collection
    whose cost grows with the whole pytest heap rather than with the scan:
    inside a full suite run that doubled the commit-inventory derivation.
    Nothing the scan allocates is cyclic garbage, so pausing loses nothing;
    the previous state is restored on exit, so nesting is safe.  Use as a
    decorator (``@gc_paused()``) or a ``with`` block around a derivation,
    never around a test body.
    """
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def source_of(path: Path) -> str:
    """The cached source text of a corpus file *path* (``KeyError`` if absent).

    For a ratchet that holds a ``(path, tree)`` pair from
    :func:`files_mentioning` and needs the text too — to find the lines a
    fragment sits on, say — without reading the file again (TB-13-001).
    """
    return _source_cache[path]


def parse_inline(source: str, filename: str = "<inline>") -> ast.AST:
    """Parse a short inline source string.

    Provided so test siblings can avoid importing ``ast`` directly, keeping
    the hygiene ratchet (TB-13-003) unambiguous.
    """
    return ast.parse(source, filename=filename)


def node_line(node: ast.AST) -> int:
    """Source line of *node*, ``0`` when the node type carries none.

    ``ast.AST`` itself does not declare ``lineno``, so ratchets that report a
    site per matched node go through this rather than reaching for the
    attribute directly.
    """
    return getattr(node, "lineno", 0)


# ---------------------------------------------------------------------------
# Definition lookup — the cached AST node for a live function object.
# ---------------------------------------------------------------------------
_paths_by_text: dict[str, Path] = {text: path for text, path in _sorted_paths}
_definitions: dict[
    Path, dict[int, ast.FunctionDef | ast.AsyncFunctionDef]
] = {}


@functools.cache
def _cached_path(source_file: str) -> Path | None:
    """The corpus key for *source_file*, resolving symlinks only on a miss.

    Cached: a miss resolves every corpus path, and the corpus never changes
    after import.
    """
    found = _paths_by_text.get(source_file)
    if found is not None:
        return found
    resolved = Path(source_file).resolve()
    return next(
        (path for path in _source_cache if path.resolve() == resolved), None
    )


def _definitions_in(
    path: Path,
) -> dict[int, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every function definition in *path*, keyed by each line it starts on.

    A decorated function's code object starts on its first decorator, an
    undecorated one on ``def``; both lines index the node.  Only statement
    bodies are searched — a definition is always a statement — so no
    expression subtree is visited.
    """
    if path not in _definitions:
        index: dict[int, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        tree = _get_tree(path)
        pending: list[ast.AST] = [tree] if tree is not None else []
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index[node.lineno] = node
                if node.decorator_list:
                    index[node.decorator_list[0].lineno] = node
            for field in ("body", "orelse", "finalbody", "handlers", "cases"):
                children = getattr(node, field, None)
                if isinstance(children, list):
                    pending.extend(children)
        _definitions[path] = index
    return _definitions[path]


def function_definition(
    fn: object, mentioning: tuple[str, ...] = ()
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """The cached AST definition of the live function *fn*, if in the corpus.

    For ratchets that start from a live object (a routed use case, a factory)
    rather than from a file scan: the definition comes from the shared parse,
    so no source is re-read through ``inspect`` and nothing is parsed twice
    (TB-13-001, TB-13-003).  With *mentioning*, a file containing none of the
    fragments is skipped unparsed, as :func:`files_mentioning` does
    (TB-13-002, TB-13-008).  ``None`` for a function outside ``vultron/`` and
    ``test/``, without a code object, or in a file the prefilter skips.
    """
    try:
        fn = inspect.unwrap(fn)  # type: ignore[arg-type]
    except ValueError:
        return None
    code = getattr(fn, "__code__", None)
    if code is None:
        return None
    path = _cached_path(code.co_filename)
    if path is None:
        return None
    if mentioning and not any(f in _source_cache[path] for f in mentioning):
        return None
    return _definitions_in(path).get(code.co_firstlineno)


# ---------------------------------------------------------------------------
# Text-only call graph — a by-name fixed point that parses nothing.
# ---------------------------------------------------------------------------
#: A top-level ``def`` or ``class`` line.
_TOP_LEVEL_DEFINITION = re.compile(
    r"^(?:async\s+def|def|class)\s+(\w+)", re.MULTILINE
)
#: A top-level alias: ``from m import a as b`` (one name per line, as ruff
#: formats a parenthesised import) or ``b = a``.
_IDENTIFIER = r"[A-Za-z_]\w*"
_TOP_LEVEL_ALIAS = re.compile(
    rf"^(?:\s*(?:from\s+\S+\s+import\s+)?({_IDENTIFIER})\s+as\s+"
    rf"({_IDENTIFIER}),?|({_IDENTIFIER})\s*=\s*({_IDENTIFIER}))\s*$",
    re.MULTILINE,
)
_DEFINING_PREFIXES = ("def ", "class ")


def called_names(span: str) -> frozenset[str]:
    """Every identifier written directly before a ``(`` in *span*.

    Splits on ``(`` and takes each chunk's trailing identifier, skipping the
    name a ``def`` or ``class`` line defines — several times faster than a
    regex, which retries at every position of a mostly-prose file.  An
    attribute call counts by its attribute (``dl.save(`` → ``save``).
    """
    names: set[str] = set()
    for chunk in span.split("(")[:-1]:
        end = len(chunk)
        start = end
        while start and (
            chunk[start - 1].isalnum() or chunk[start - 1] == "_"
        ):
            start -= 1
        if start == end or chunk[start].isdigit():
            continue
        if chunk.endswith(_DEFINING_PREFIXES, 0, start):
            continue
        names.add(chunk[start:end])
    return frozenset(names)


def definition_summaries(
    source: str, *, classes: bool = True
) -> Iterator[tuple[str, frozenset[str]]]:
    """``(name, called names)`` for each top-level definition in *source*.

    Text, not AST: a definition's span runs to the next top-level definition,
    and every ``name(`` in it counts as a call.  Both over-approximate (a
    trailing module statement, a name in a string, a class's every method).
    A top-level alias (``import a as b``, ``b = a``) is summarised as a
    definition of ``b`` that calls ``a``, so a call through the alias is
    still followed.  With *classes* ``False`` only functions are summarised:
    a class span holds every method, so one writing method would make every
    caller of the class look like a writer.
    """
    starts = list(_TOP_LEVEL_DEFINITION.finditer(source))
    ends = [match.start() for match in starts[1:]] + [len(source)]
    for match, end in zip(starts, ends[: len(starts)], strict=True):
        if classes or not match.group(0).startswith("class"):
            yield match.group(1), called_names(source[match.end() : end])
    for match in _TOP_LEVEL_ALIAS.finditer(source):
        original, alias = (
            match.group(1) or match.group(4),
            (match.group(2) or match.group(3)),
        )
        if original != alias:
            yield alias, frozenset({original})


def names_reaching(
    seeds: frozenset[str], *, under: Path, classes: bool = True
) -> frozenset[str]:
    """Top-level names under *under* whose definition may call a *seed*.

    A fixed point by name over source text (:func:`definition_summaries`):
    start from *seeds*, then add every definition whose span calls a name
    already in the set.  It reads each module's text once and parses none,
    so it needs no prefilter; its result is meant to *be* the prefilter of a
    precise walk (TB-13-002, TB-13-008).  It over-approximates — by name,
    not by resolution — and the walk decides.  A definition nested in an
    ``if`` or ``try`` block is not top-level here, so it is not followed.
    """
    summaries = [
        summary
        for _, source in all_sources(under=under)
        for summary in definition_summaries(source, classes=classes)
    ]
    names: set[str] = set()
    while found := {
        name
        for name, called in summaries
        if name not in names and called & (seeds | names)
    }:
        names |= found
    return frozenset(names)
