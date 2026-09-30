#!/usr/bin/env python

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
"""Call-graph resolution through the use-case package for the mutation ratchet.

Companion to ``test_no_dl_mutations_in_execute.py`` (CLP-10-020): the classes
here index every module of ``vultron/core/use_cases/`` and follow a call from an
``execute()`` body to the function or method it names — a module-level helper,
a ``self._method()``, a name imported absolutely, relatively, or through a
package ``__init__`` re-export — until the search leaves the package.  The test
module owns the rule and the ``KNOWN_VIOLATIONS`` set; this module owns the
walk.  No ``ast.parse`` or ``rglob`` here (TB-13-003): trees come from
``_corpus`` or from the test's ``parse_inline`` calls.

Not resolved, by design: a call on an instance built inline
(``Helper().store(...)``), a method inherited from a base class in another
module, a lambda or nested function passed to a helper, and a write whose
receiver is not spelled ``dl``/``_dl``/``datalayer``/``_datalayer`` (a helper
parameter named ``persistence``, say — ``_is_dl_mutation_call`` matches the
receiver by name, so the write is invisible whatever the parameter's type).
None occurs in the use-case package today; the ratchet's exact set would
surface one that started to matter.
"""

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path

from test.architecture import _corpus

_DL_MUTATION_METHODS: frozenset[str] = frozenset(
    {"save", "create", "update", "delete"}
)
_DL_RECEIVER_ATTRS: frozenset[str] = frozenset(
    {"_dl", "dl", "_datalayer", "datalayer"}
)

_FunctionDef = ast.FunctionDef | ast.AsyncFunctionDef

#: A resolved callee: (module name, enclosing class name or None, def name).
_Callee = tuple[str, str | None, str]


def _is_dl_mutation_call(node: ast.AST) -> bool:
    """Return True if *node* is a DataLayer mutation call expression.

    Detects:
    - ``self._dl.METHOD(...)`` / ``self._datalayer.METHOD(...)``
    - ``self.dl.METHOD(...)`` / ``self.datalayer.METHOD(...)``
    - ``dl.METHOD(...)``  (local variable or parameter named ``dl`` or
      ``datalayer``, with or without the leading underscore)

    where METHOD is one of ``save``, ``create``, ``update``, ``delete``.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in _DL_MUTATION_METHODS:
        return False
    recv = func.value
    # self._dl.METHOD or self.dl.METHOD
    if (
        isinstance(recv, ast.Attribute)
        and recv.attr in _DL_RECEIVER_ATTRS
        and isinstance(recv.value, ast.Name)
        and recv.value.id == "self"
    ):
        return True
    # dl.METHOD (local variable)
    return bool(isinstance(recv, ast.Name) and recv.id in _DL_RECEIVER_ATTRS)


def _walk_own_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Yield all descendants of *node* without crossing nested function scopes.

    Unlike ``ast.walk``, this generator stops descending when it encounters a
    ``FunctionDef``, ``AsyncFunctionDef``, or ``Lambda`` that is not the root
    *node* itself.  This prevents mutation calls inside inner helper functions
    or lambda bodies defined inside ``execute()`` from being counted as direct
    violations of ``execute()``.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
        ):
            continue
        yield from _walk_own_scope(child)


def _has_dl_mutation_in_execute_tree(tree: ast.AST) -> bool:
    """Return True if *tree* contains an execute() method with a direct DL mutation."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "execute":
            continue
        for child in _walk_own_scope(node):
            if _is_dl_mutation_call(child):
                return True
    return False


def _has_dl_mutation_in_execute(source_path: Path) -> bool:
    """Return True if *source_path* contains an execute() method with a direct
    DataLayer mutation call in its own scope (excluding inner functions).
    """
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = _corpus.parse_inline(source, filename=str(source_path))
    except (OSError, SyntaxError):
        return False
    return _has_dl_mutation_in_execute_tree(tree)


# ---------------------------------------------------------------------------
# Transitive resolution through the use-case package (CLP-10-020)
# ---------------------------------------------------------------------------


class _ModuleIndex:
    """What one use-case module defines and imports, by name."""

    def __init__(self, module: str, tree: ast.AST) -> None:
        self.functions: dict[str, _FunctionDef] = {}
        self.methods: dict[str, dict[str, _FunctionDef]] = {}
        #: local name → (defining module, name there) for ``from m import n``.
        self.imported_names: dict[str, tuple[str, str]] = {}
        #: local alias → module for ``import m [as alias]``.
        self.imported_modules: dict[str, str] = {}
        if not isinstance(tree, ast.Module):
            return
        for node in tree.body:
            self._index_top_level(module, node)
        # ``from x import y`` inside a function body (deferred import) binds a
        # name the same way; index those too so a lazily imported helper is
        # still followed.
        for nested in ast.walk(tree):
            if isinstance(nested, ast.ImportFrom) and nested not in tree.body:
                self._index_import_from(module, nested)

    def _index_top_level(self, module: str, node: ast.stmt) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            self.methods[node.name] = {
                item.name: item
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
        elif isinstance(node, ast.ImportFrom):
            self._index_import_from(module, node)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                self.imported_modules[alias.asname or alias.name] = alias.name

    def _index_import_from(self, module: str, node: ast.ImportFrom) -> None:
        target = _absolute_module(module, node)
        if target is None:
            return
        for alias in node.names:
            self.imported_names[alias.asname or alias.name] = (
                target,
                alias.name,
            )


def _absolute_module(module: str, node: ast.ImportFrom) -> str | None:
    """Resolve the module a ``from … import`` statement names, absolutely."""
    if node.level == 0:
        return node.module
    # Relative import: ``module`` is the importing module's dotted name; a
    # package's ``__init__`` is indexed under the package name itself, so one
    # level up from ``pkg.mod`` is ``pkg``.
    base = module.rsplit(".", node.level)[0]
    if node.module:
        return f"{base}.{node.module}"
    return base


class _UseCaseCorpus:
    """Resolve calls from an ``execute()`` body through the use-case package.

    *trees* maps each module file under *root* to its parsed AST; *package*
    is the dotted name of *root*.  Resolution never leaves the package: a
    callee that lives anywhere else is where the search stops.
    """

    def __init__(
        self, trees: Mapping[Path, ast.AST], *, root: Path, package: str
    ) -> None:
        self._package = package
        self._modules: dict[str, _ModuleIndex] = {}
        self._paths: dict[str, Path] = {}
        for path, tree in trees.items():
            name = self._module_name(path, root)
            self._modules[name] = _ModuleIndex(name, tree)
            self._paths[name] = path

    def _module_name(self, path: Path, root: Path) -> str:
        parts = list(path.relative_to(root).with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join([self._package, *parts])

    def modules_under(self, sub_root: Path) -> Iterator[tuple[str, Path]]:
        """Yield ``(module, path)`` for every indexed module under *sub_root*."""
        for name, path in self._paths.items():
            try:
                path.relative_to(sub_root)
            except ValueError:
                continue
            yield name, path

    def execute_reaches_mutation(self, module: str) -> bool:
        """True if any ``execute()`` in *module* reaches a DL write in-package."""
        index = self._modules[module]
        for cls, methods in index.methods.items():
            if (execute := methods.get("execute")) is not None:
                if self._reaches_mutation(module, cls, execute, set()):
                    return True
        return False

    def _reaches_mutation(
        self,
        module: str,
        cls: str | None,
        func: _FunctionDef,
        seen: set[_Callee],
    ) -> bool:
        for node in _walk_own_scope(func):
            if _is_dl_mutation_call(node):
                return True
            if not isinstance(node, ast.Call):
                continue
            callee = self._resolve(module, cls, node.func)
            if callee is None or callee in seen:
                continue
            seen.add(callee)
            target_module, target_cls, name = callee
            target = self._definition(target_module, target_cls, name)
            if target is not None and self._reaches_mutation(
                target_module, target_cls, target, seen
            ):
                return True
        return False

    def _definition(
        self, module: str, cls: str | None, name: str
    ) -> _FunctionDef | None:
        index = self._modules.get(module)
        if index is None:
            return None
        if cls is not None:
            return index.methods.get(cls, {}).get(name)
        return index.functions.get(name)

    def _resolve(
        self, module: str, cls: str | None, func: ast.expr
    ) -> _Callee | None:
        """Name the in-package definition *func* calls, or ``None``."""
        index = self._modules[module]
        if isinstance(func, ast.Name):
            if func.id in index.functions:
                return (module, None, func.id)
            if func.id in index.imported_names:
                target_module, name = index.imported_names[func.id]
                return self._in_package(target_module, name)
            return None
        if isinstance(func, ast.Attribute) and isinstance(
            func.value, ast.Name
        ):
            return self._resolve_attribute(
                module, cls, index, func.value.id, func.attr
            )
        return None

    def _resolve_attribute(
        self,
        module: str,
        cls: str | None,
        index: _ModuleIndex,
        owner: str,
        attr: str,
    ) -> _Callee | None:
        """Resolve ``owner.attr(...)``: a ``self`` method or a module's function."""
        if owner == "self":
            if cls is not None and attr in index.methods.get(cls, {}):
                return (module, cls, attr)
            return None
        if owner in index.imported_modules:
            return self._in_package(index.imported_modules[owner], attr)
        if owner in index.imported_names:
            # ``from pkg import helpers; helpers.store(...)``: the name binds
            # a *module* when ``pkg.helpers`` is one we index.
            target_module, name = index.imported_names[owner]
            submodule = f"{target_module}.{name}"
            if submodule in self._modules:
                return self._in_package(submodule, attr)
        return None

    def _in_package(self, module: str, name: str) -> _Callee | None:
        """A module-level function *name* in *module*, if we index it."""
        index = self._modules.get(module)
        if index is None:
            return None
        if name in index.functions:
            return (module, None, name)
        # A package ``__init__`` that re-exports the name: follow the
        # re-export to its definition.
        if name in index.imported_names:
            target_module, original = index.imported_names[name]
            return self._in_package(target_module, original)
        return None
