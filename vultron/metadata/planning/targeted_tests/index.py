"""Map each source module to the test files that import it (PAD-18-002)."""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path, PurePosixPath

from vultron.metadata.specs.backstop import (
    SOURCE_PREFIX,
    TEST_PREFIX,
    FileChange,
    TestFile,
    build_test_index,
    changed_nodes,
    changed_symbols,
    imported_symbols,
    index_test_file,
    mirror_tests,
    module_name,
    owner_modules,
    symbol_names,
)


def _is_test_file(path: str) -> bool:
    return PurePosixPath(path).name.startswith("test_") and path.endswith(
        ".py"
    )


def _parse(source: str | None) -> ast.Module | None:
    try:
        return ast.parse(source or "")
    except SyntaxError:
        return None


def _no_history(path: str) -> str | None:
    return None


def _imports_whole_module(test: TestFile, module: str) -> bool:
    """Whether *test* reaches every name of *module*, not just some.

    ``import vultron.a.mod``, ``from vultron.a import mod`` and
    ``from vultron import a`` all reach a change to ``vultron.a.mod`` by
    attribute access, which no imported name records; a star import from
    the module or a re-exporting package binds names no import lists.
    ``vultron`` itself is not a package that counts (:func:`owner_modules`).
    """
    owners = owner_modules(module)
    for owner in owners:
        parent, _, leaf = owner.rpartition(".")
        if (parent, leaf) in test.names or owner in test.plain_imports:
            return True
    return any(name == "*" and m in owners for m, name in test.names)


def _imports_anything_from(test: TestFile, module: str, package: bool) -> bool:
    """Whether *test* imports any name from *module* or a re-exporting package.

    For a *package* (an ``__init__.py``), importing any submodule counts
    too: importing ``vultron.a.sub`` executes ``vultron/a/__init__.py``.
    """
    owners = owner_modules(module)
    return (
        _imports_whole_module(test, module)
        or any(m in owners for m, _ in test.names)
        or (package and any(m.startswith(f"{module}.") for m in test.modules))
    )


def _module_level_change(
    tree: ast.Module, lines: Iterable[int] | None
) -> bool:
    """Whether *lines* touch a top-level statement that defines no symbol.

    An import, a re-export, a registration call or an ``if TYPE_CHECKING:``
    block can break or change every importer of the module, not just the
    importers of one name. The module docstring is not such a statement.
    """
    if lines is None:
        return True
    symbols = {id(n) for n in changed_nodes(tree, None)}
    spans = [
        range(node.lineno, (node.end_lineno or node.lineno) + 1)
        for i, node in enumerate(tree.body)
        if id(node) not in symbols and not (i == 0 and _is_docstring(node))
    ]
    return any(n in span for n in lines for span in spans)


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _top_level(tree: ast.Module) -> tuple[dict[str, str], list[str]]:
    """Each top-level symbol's AST, and the statements that define none."""
    symbols: dict[str, str] = {}
    statements: list[str] = []
    for i, node in enumerate(tree.body):
        names = symbol_names(node)
        for name in names:
            symbols[name] = ast.dump(node)
        if not names and not (i == 0 and _is_docstring(node)):
            statements.append(ast.dump(node))
    return symbols, statements


def _rewritten(old: ast.Module, new: ast.Module) -> tuple[set[str], bool]:
    """Symbols added, removed or rewritten, and whether module code changed.

    A ``-U0`` hunk names only new-side lines, so a deleted function, a
    renamed one's old name, or a removed import line leaves no changed line
    inside any symbol. Comparing the two trees catches them.
    """
    old_symbols, old_statements = _top_level(old)
    new_symbols, new_statements = _top_level(new)
    changed = {
        name
        for name in old_symbols.keys() | new_symbols.keys()
        if old_symbols.get(name) != new_symbols.get(name)
    }
    return changed, old_statements != new_statements


def importers(
    change: FileChange,
    tests: dict[str, TestFile],
    old_source: str | None = None,
) -> list[str]:
    """Test files that import a symbol *change* touched (PAD-18-002).

    A test that imports the module object is selected for any change to it.
    A change outside every top-level symbol (an import line, a re-export),
    a whole-file change (new or deleted module), or a module that no longer
    parses selects every test importing anything from it. *old_source*, the
    file at the merge base, adds the symbols the diff removed or renamed.
    """
    module = module_name(change.path)
    package = PurePosixPath(change.path).name == "__init__.py"
    tree = _parse(change.source)
    module_level = tree is None or _module_level_change(tree, change.lines)
    symbols: set[str] = set()
    old = None if old_source is None else _parse(old_source)
    if tree is not None:
        symbols = changed_symbols(tree, change.lines)
        if old is not None:
            rewritten, statements_changed = _rewritten(old, tree)
            symbols |= rewritten
            module_level = module_level or statements_changed
    if module_level:
        return sorted(
            p
            for p, t in tests.items()
            if _imports_anything_from(t, module, package)
        )
    return sorted(
        path
        for path, test in tests.items()
        if imported_symbols(test, module, symbols)
        or _imports_whole_module(test, module)
    )


def _test_side_importers(path: str, tests: dict[str, TestFile]) -> list[str]:
    """Test files that import the test-side module at *path*."""
    module = module_name(path)
    return sorted(p for p, t in tests.items() if module in t.test_imports)


def _tests_for(
    change: FileChange,
    tests: dict[str, TestFile],
    exists: Callable[[str], bool],
    old_source: Callable[[str], str | None],
) -> list[str]:
    if change.path.startswith(TEST_PREFIX):
        # A changed test file is selected explicitly: no ``vultron`` symbol
        # changed, and the mirror lookup maps only ``vultron/`` paths. So are
        # the test files importing it (a helper, or another test module).
        keep = _is_test_file(change.path) and exists(change.path)
        own = [change.path] if keep else []
        return own + _test_side_importers(change.path, tests)
    if change.path.startswith(SOURCE_PREFIX):
        return importers(
            change, tests, old_source(change.path)
        ) + mirror_tests(change.path, tests)
    return []


def _widen(
    test: TestFile, helpers: dict[str, TestFile], seen: set[str]
) -> TestFile:
    """*test* with the imports of every test-side module it reaches folded in."""
    modules, names = set(test.modules), set(test.names)
    plain, reached = set(test.plain_imports), set(test.test_imports)
    pending = [m for m in test.test_imports if m in helpers]
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        helper = helpers[module]
        modules |= helper.modules
        names |= helper.names
        plain |= helper.plain_imports
        reached |= helper.test_imports
        pending += [m for m in helper.test_imports if m in helpers]
    return replace(
        test,
        modules=frozenset(modules),
        names=frozenset(names),
        plain_imports=frozenset(plain),
        test_imports=frozenset(reached),
    )


def widen_index(
    tests: dict[str, TestFile], helpers: dict[str, TestFile]
) -> dict[str, TestFile]:
    """Fold each test's test-side imports, transitively, into its entry.

    *helpers* maps a dotted module name (``test.support.ledger``) to the
    index entry of that module, test file or not. A test that reaches
    ``vultron`` only through a helper then counts as importing what the
    helper imports, and its ``test_imports`` lists every test-side module it
    reaches, so a changed helper or test module selects it.
    """
    return {p: _widen(t, helpers, set()) for p, t in tests.items()}


def build_index(root: Path) -> dict[str, TestFile]:
    """The test index with test-side imports followed (:func:`widen_index`)."""
    tests = build_test_index(root)
    helpers = {module_name(p): t for p, t in tests.items()}
    for file in sorted((root / TEST_PREFIX).rglob("*.py")):
        rel = file.relative_to(root).as_posix()
        if rel in tests:
            continue
        indexed = index_test_file(rel, file.read_text(encoding="utf-8"))
        if indexed is not None:
            helpers[module_name(rel)] = indexed
    return widen_index(tests, helpers)
