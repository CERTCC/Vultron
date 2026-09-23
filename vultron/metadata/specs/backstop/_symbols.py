#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Changed symbols, spec markers, and the test index (SR-12-002, SR-12-003)."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath

from vultron.metadata.specs.backstop._model import (
    TestFile,
)

_BLOCK_FIELDS = ("body", "orelse", "finalbody", "handlers", "cases")


#: Module-level boilerplate that is not part of any module's API.  ``logger``
#: is assigned in nearly every module here, so treating it as a changed symbol
#: matches every requirement that says ``logger.info`` and flags its group on
#: any diff that touches a logging line (observed: CLP-13 on a bridge change).
BOILERPLATE_SYMBOLS = frozenset({"logger", "log", "LOGGER", "LOG"})


def _symbol_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names = [node.name]
    elif isinstance(node, ast.Assign):
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        names = [node.target.id]
    else:
        return []
    return [
        n
        for n in names
        if not (n.startswith("__") and n.endswith("__"))
        and n not in BOILERPLATE_SYMBOLS
    ]


def _span(node: ast.stmt) -> range:
    decorators = getattr(node, "decorator_list", [])
    start = min([node.lineno] + [d.lineno for d in decorators])
    return range(start, (node.end_lineno or node.lineno) + 1)


def changed_nodes(
    tree: ast.Module, lines: frozenset[int] | set[int] | None
) -> list[ast.stmt]:
    """Top-level symbol nodes whose span intersects *lines* (all if None)."""
    return [
        node
        for node in tree.body
        if _symbol_names(node)
        and (lines is None or any(n in lines for n in _span(node)))
    ]


def changed_symbols(
    tree: ast.Module, lines: frozenset[int] | set[int] | None
) -> set[str]:
    """Names of the top-level symbols changed by *lines* (SR-12-002)."""
    return {
        n for node in changed_nodes(tree, lines) for n in _symbol_names(node)
    }


def _dotted(node: ast.expr) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _statements(body: Iterable[ast.AST]) -> Iterator[ast.AST]:
    """Yield statements in *body* and every nested block, expressions skipped.

    Walking statements only is several times faster than ``ast.walk`` over
    the whole test tree, and imports and markers only occur at this level.
    """
    for node in body:
        yield node
        for attr in _BLOCK_FIELDS:
            child = getattr(node, attr, None)
            if isinstance(child, list):
                yield from _statements(child)


def _marker_exprs(node: ast.AST) -> list[ast.expr]:
    """Decorators, and the value of a ``pytestmark = ...`` assignment."""
    exprs = list(getattr(node, "decorator_list", []))
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
    ):
        exprs.append(node.value)
    return exprs


def _call_spec_ids(expr: ast.expr) -> set[str]:
    return {
        arg.value
        for sub in ast.walk(expr)
        if isinstance(sub, ast.Call)
        and _dotted(sub.func).endswith("mark.spec")
        for arg in sub.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    }


def spec_ids_in(nodes: Iterable[ast.AST]) -> set[str]:
    """IDs in ``pytest.mark.spec(...)`` markers on or within *nodes*."""
    return {
        spec_id
        for node in _statements(nodes)
        for expr in _marker_exprs(node)
        for spec_id in _call_spec_ids(expr)
    }


def _is_vultron(module: str | None) -> bool:
    return module is not None and (
        module == "vultron" or module.startswith("vultron.")
    )


def _vultron_imports(
    tree: ast.Module,
) -> tuple[set[str], set[tuple[str, str]]]:
    modules: set[str] = set()
    names: set[tuple[str, str]] = set()
    for node in _statements(tree.body):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names if _is_vultron(a.name))
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
            and _is_vultron(node.module)
        ):
            modules.add(node.module)
            for alias in node.names:
                names.add((node.module, alias.name))
                modules.add(f"{node.module}.{alias.name}")
    return modules, names


def index_test_file(path: str, source: str) -> TestFile | None:
    """Index one test file; ``None`` when it does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    modules, names = _vultron_imports(tree)
    return TestFile(
        path,
        frozenset(modules),
        frozenset(names),
        frozenset(spec_ids_in(tree.body)),
    )


def build_test_index(root: Path) -> dict[str, TestFile]:
    """Index every ``test/**/test_*.py`` file under *root*."""
    index = {}
    for file in sorted((root / "test").rglob("test_*.py")):
        rel = file.relative_to(root).as_posix()
        info = index_test_file(rel, file.read_text(encoding="utf-8"))
        if info is not None:
            index[rel] = info
    return index


def module_name(path: str) -> str:
    """Dotted module name for a repo-relative ``.py`` path."""
    parts = PurePosixPath(path).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _module_dir(path: str) -> PurePosixPath:
    """``a/b/c`` for ``vultron/a/b/c.py`` and ``vultron/a/b/c/__init__.py``."""
    rel = PurePosixPath(path).relative_to("vultron")
    return rel.parent if rel.name == "__init__.py" else rel.with_suffix("")


def mirror_tests(path: str, test_paths: Iterable[str]) -> list[str]:
    """Tests at the mirror path of a ``vultron/`` source file."""
    stem = _module_dir(path)
    if str(stem) == ".":
        return []
    flat = PurePosixPath("test") / stem.parent / f"test_{stem.name}.py"
    prefix = f"test/{stem}/"
    return sorted(
        t
        for t in test_paths
        if t == flat.as_posix()
        or (t.startswith(prefix) and "/" not in t[len(prefix) :])
    )


def _owner_modules(module: str) -> set[str]:
    """*module* and its ancestor packages below ``vultron`` (re-exports)."""
    parts = module.split(".")
    return {".".join(parts[:i]) for i in range(2, len(parts) + 1)}


def imported_symbols(
    test: TestFile, module: str, symbols: set[str]
) -> set[str]:
    """Changed *symbols* that *test* imports by name from *module*."""
    owners = _owner_modules(module)
    return {n for m, n in test.names if n in symbols and m in owners}
