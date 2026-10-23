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
"""Call-graph resolution through the use-case package for the use-case ratchets.

Companion to ``test_no_dl_mutations_in_execute.py`` (CLP-10-020) and
``test_single_bt_execution_received_side.py`` (CLP-10-005): the classes
here index every module of ``vultron/core/use_cases/`` — and of
``vultron/core/services/``, the neutral home of helpers a use case shares with
a BT node (BT-22-005), so moving a helper there hides neither its writes nor
its tree runs — and follow a call from an ``execute()`` body to the function
or method it names, until the search leaves the indexed packages.  Followed:
a module-level helper; a name imported absolutely, relatively, or through a
package ``__init__`` re-export (top-level or deferred into a function body);
a function of a module imported whole (``import m as h; h.f()``) or bound by
``from pkg import submodule``; a nested function ``execute()`` defines and
calls; a ``self._method()``, looked up in ``self``'s concrete class's C3
method resolution order over its indexed bases, so a subclass override is the
one walked and an inherited ``execute()`` is walked once per class that
inherits it; and a ``super()._method()``, looked up in the same order after
the class that makes the call.  The test modules own the rules and their exact
sets; this module owns the walk.  No ``ast.parse`` or ``rglob`` here
(TB-13-003): trees come from ``_corpus`` or from the test's ``parse_inline``
calls.

Every call shape not listed above is not followed.  In particular, not
resolved: a call on an instance built inline (``Helper().store(...)``) —
which is also how a BT node's ``update()`` stays out of the walk — or held on
an attribute (``self._h.store(...)``); a ``ClassName.method()`` call; a call
through a local alias (``_d = door; _d()``) or a lambda; a nested function
called by another nested function or passed to a helper; a helper that takes
``self`` and calls a method on it; a base class outside the indexed packages;
and a write whose receiver is not spelled ``dl``/``_dl``/``datalayer``/
``_datalayer`` (a helper parameter named ``persistence``, say —
``_is_dl_mutation_call`` matches the receiver by name, so the write is
invisible whatever the parameter's type).  None of these shapes reaches a
tree run or a DataLayer write from a use case today.
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

USE_CASES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "use_cases"
RECEIVED_ROOT = USE_CASES_ROOT / "received"
SERVICES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "services"

#: The indexed packages: each directory and its dotted name.
INDEXED_ROOTS: Mapping[Path, str] = {
    USE_CASES_ROOT: "vultron.core.use_cases",
    SERVICES_ROOT: "vultron.core.services",
}

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


def _is_execute_with_setup_call(node: ast.Call) -> bool:
    """True for a call of ``execute_with_setup``, bare or as a method."""
    func = node.func
    return (
        isinstance(func, ast.Attribute) and func.attr == "execute_with_setup"
    ) or (isinstance(func, ast.Name) and func.id == "execute_with_setup")


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
# Transitive resolution through the use-case package (CLP-10-005, CLP-10-020)
# ---------------------------------------------------------------------------

#: A concrete class ``self`` is bound to: (module name, class name).
_SelfType = tuple[str, str]

#: A walk step: a definition, the module it lives in, and ``self``'s class.
#: The key (callee plus ``self``'s class) stops a cycle being followed twice.
_Step = tuple[str, _SelfType | None, _FunctionDef, tuple[object, ...]]


class _ModuleIndex:
    """What one use-case module defines and imports, by name."""

    def __init__(
        self, module: str, tree: ast.AST, *, is_package: bool = False
    ) -> None:
        self._is_package = is_package
        self.functions: dict[str, _FunctionDef] = {}
        self.methods: dict[str, dict[str, _FunctionDef]] = {}
        #: class name → its base-class expressions, in declaration order.
        self.bases: dict[str, list[ast.expr]] = {}
        #: local name → (defining module, name there) for ``from m import n``.
        self.imported_names: dict[str, tuple[str, str]] = {}
        #: local alias → module for ``import m [as alias]``.
        self.imported_modules: dict[str, str] = {}
        if not isinstance(tree, ast.Module):
            return
        for node in tree.body:
            self._index_top_level(module, node)
        # An import inside a function body (deferred import) binds a name the
        # same way; index those too so a lazily imported helper is still
        # followed.
        for nested in ast.walk(tree):
            if nested in tree.body:
                continue
            if isinstance(nested, ast.ImportFrom):
                self._index_import_from(module, nested)
            elif isinstance(nested, ast.Import):
                self._index_import(nested)

    def _index_top_level(self, module: str, node: ast.stmt) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            self.methods[node.name] = {
                item.name: item
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            self.bases[node.name] = list(node.bases)
        elif isinstance(node, ast.ImportFrom):
            self._index_import_from(module, node)
        elif isinstance(node, ast.Import):
            self._index_import(node)

    def _index_import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imported_modules[alias.asname or alias.name] = alias.name

    def _index_import_from(self, module: str, node: ast.ImportFrom) -> None:
        target = _absolute_module(module, node, is_package=self._is_package)
        if target is None:
            return
        for alias in node.names:
            self.imported_names[alias.asname or alias.name] = (
                target,
                alias.name,
            )


def _absolute_module(
    module: str, node: ast.ImportFrom, *, is_package: bool
) -> str | None:
    """Resolve the module a ``from … import`` statement names, absolutely."""
    if node.level == 0:
        return node.module
    # Relative import: ``module`` is the importing module's dotted name.  One
    # level up from module ``pkg.mod`` is ``pkg``; a package ``__init__`` is
    # indexed under the package name itself, so its one level up is the
    # package (``from .doors`` in ``pkg/__init__.py`` names ``pkg.doors``).
    levels = node.level - 1 if is_package else node.level
    base = module.rsplit(".", levels)[0] if levels else module
    if node.module:
        return f"{base}.{node.module}"
    return base


def _local_functions(func: _FunctionDef) -> dict[str, _FunctionDef]:
    """Functions *func* defines in its own scope, by name."""
    return {
        child.name: child
        for node in _walk_own_scope(func)
        for child in ast.iter_child_nodes(node)
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


class _UseCaseCorpus:
    """Resolve calls from an ``execute()`` body through the indexed packages.

    *trees* maps each module file to its parsed AST; *roots* maps each
    indexed package directory to its dotted name, and every file in *trees*
    lies under one of them.  Resolution never leaves the indexed packages: a
    callee that lives anywhere else is where the search stops.
    """

    def __init__(
        self, trees: Mapping[Path, ast.AST], *, roots: Mapping[Path, str]
    ) -> None:
        self._roots = dict(roots)
        self._modules: dict[str, _ModuleIndex] = {}
        self._paths: dict[str, Path] = {}
        for path, tree in trees.items():
            name = self._module_name(path)
            self._modules[name] = _ModuleIndex(
                name, tree, is_package=path.name == "__init__.py"
            )
            self._paths[name] = path

    def _module_name(self, path: Path) -> str:
        for root, package in self._roots.items():
            if path.is_relative_to(root):
                parts = list(path.relative_to(root).with_suffix("").parts)
                if parts and parts[-1] == "__init__":
                    parts.pop()
                return ".".join([package, *parts])
        raise ValueError(f"{path} lies under none of {sorted(self._roots)}")

    def modules_under(self, sub_root: Path) -> Iterator[tuple[str, Path]]:
        """Yield ``(module, path)`` for every indexed module under *sub_root*."""
        for name, path in self._paths.items():
            try:
                path.relative_to(sub_root)
            except ValueError:
                continue
            yield name, path

    # -- the two rules --------------------------------------------------------

    def execute_reaches_mutation(self, module: str) -> bool:
        """True if any ``execute()`` in *module* reaches an indexed DL write."""
        return any(
            self._reaches_mutation(step, set())
            for _, step in self._executes(module)
        )

    def tree_runs_per_execute(
        self, module: str, *, transitive: bool = True
    ) -> dict[str, int]:
        """``execute_with_setup()`` calls each ``execute()`` in *module* reaches.

        Keyed by class, including a class that inherits its ``execute()``
        from an indexed base.  Calls are summed along every path through the
        indexed packages, so a helper called twice counts twice and two
        calls on alternative branches count as two (CLP-10-005).  A cycle is
        not followed a second time: a definition already on the current path,
        itself included, is not entered again.  With ``transitive=False`` only the calls
        written in ``execute()``'s own body count.
        """
        return {
            cls: self._count_tree_runs(step, (), transitive=transitive)
            for cls, step in self._executes(module)
        }

    def _executes(self, module: str) -> Iterator[tuple[str, _Step]]:
        """``(class, step)`` for each class in *module* with an ``execute()``."""
        for cls in self._modules[module].methods:
            self_type = (module, cls)
            found = self._lookup_method(self_type, "execute")
            if found is not None:
                def_module, def_cls, func = found
                key = (def_module, def_cls, "execute", self_type)
                yield cls, (def_module, self_type, func, key)

    def _count_tree_runs(
        self, step: _Step, stack: tuple[object, ...], *, transitive: bool
    ) -> int:
        total = 0
        path = (*stack, step[3])
        for call, callee in self._calls(step):
            if _is_execute_with_setup_call(call):
                total += 1
            elif transitive and callee is not None and callee[3] not in path:
                total += self._count_tree_runs(callee, path, transitive=True)
        return total

    def _reaches_mutation(self, step: _Step, seen: set[object]) -> bool:
        seen.add(step[3])
        for call, callee in self._calls(step):
            if _is_dl_mutation_call(call):
                return True
            if (
                callee is not None
                and callee[3] not in seen
                and self._reaches_mutation(callee, seen)
            ):
                return True
        return False

    # -- resolution -----------------------------------------------------------

    def _calls(self, step: _Step) -> Iterator[tuple[ast.Call, _Step | None]]:
        """Each call in *step*'s own scope, with the indexed step it resolves to."""
        module, self_type, func, key = step
        local = _local_functions(func)
        for node in _walk_own_scope(func):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if isinstance(target, ast.Name) and target.id in local:
                # A nested function execute() defines and calls: its body
                # runs as part of this call, with the same ``self``.
                yield (
                    node,
                    (
                        module,
                        self_type,
                        local[target.id],
                        (*key, target.id),
                    ),
                )
            elif isinstance(target, ast.Attribute) and _is_super_call(target):
                yield node, self._resolve_super(step, target.attr)
            else:
                yield node, self._resolve(module, self_type, target)

    def _resolve(
        self, module: str, self_type: _SelfType | None, func: ast.expr
    ) -> _Step | None:
        """Name the indexed definition *func* calls, or ``None``."""
        index = self._modules[module]
        if isinstance(func, ast.Name):
            if func.id in index.functions:
                return self._function_step(module, func.id)
            if func.id in index.imported_names:
                return self._in_package(*index.imported_names[func.id])
            return None
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
        ):
            return None
        return self._resolve_attribute(
            module, self_type, func.value.id, func.attr
        )

    def _resolve_attribute(
        self,
        module: str,
        self_type: _SelfType | None,
        owner: str,
        attr: str,
    ) -> _Step | None:
        """Resolve ``owner.attr(...)``: a ``self`` method or a module's function."""
        if owner == "self":
            return self._resolve_self(self_type, attr)
        index = self._modules[module]
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

    def _resolve_self(
        self, self_type: _SelfType | None, attr: str
    ) -> _Step | None:
        """``self.attr(...)``: dispatched on ``self``'s concrete class."""
        if self_type is None:
            return None
        found = self._lookup_method(self_type, attr)
        if found is None:
            return None
        return self._method_step(self_type, attr, found)

    def _resolve_super(self, step: _Step, attr: str) -> _Step | None:
        """``super().attr(...)``: the MRO entry after the calling class."""
        _, self_type, _, key = step
        if self_type is None:
            return None
        # A method step's key starts with its defining (module, class).
        def_module, def_cls = key[0], key[1]
        if not (isinstance(def_module, str) and isinstance(def_cls, str)):
            return None
        caller = (def_module, def_cls)
        mro = self._mro(self_type)
        if caller not in mro:
            return None
        found = self._lookup_method_in(mro[mro.index(caller) + 1 :], attr)
        if found is None:
            return None
        return self._method_step(self_type, attr, found)

    @staticmethod
    def _method_step(
        self_type: _SelfType, attr: str, found: tuple[str, str, _FunctionDef]
    ) -> _Step:
        def_module, def_cls, target = found
        return (
            def_module,
            self_type,
            target,
            (def_module, def_cls, attr, self_type),
        )

    def _function_step(self, module: str, name: str) -> _Step:
        func = self._modules[module].functions[name]
        return (module, None, func, (module, None, name))

    def _in_package(self, module: str, name: str) -> _Step | None:
        """A module-level function *name* in *module*, if we index it."""
        index = self._modules.get(module)
        if index is None:
            return None
        if name in index.functions:
            return self._function_step(module, name)
        # A package ``__init__`` that re-exports the name: follow the
        # re-export to its definition.
        if name in index.imported_names:
            return self._in_package(*index.imported_names[name])
        return None

    # -- classes --------------------------------------------------------------

    def _lookup_method(
        self, self_type: _SelfType, name: str
    ) -> tuple[str, str, _FunctionDef] | None:
        """Find method *name* on *self_type*, then its indexed bases (MRO order)."""
        return self._lookup_method_in(self._mro(self_type), name)

    def _lookup_method_in(
        self, classes: list[_SelfType], name: str
    ) -> tuple[str, str, _FunctionDef] | None:
        for module, cls in classes:
            func = self._modules[module].methods[cls].get(name)
            if func is not None:
                return module, cls, func
        return None

    def _mro(
        self, self_type: _SelfType, _active: frozenset[_SelfType] = frozenset()
    ) -> list[_SelfType]:
        """*self_type* and its indexed bases in C3 order, as Python computes.

        A base outside the indexed packages is left out; it defines nothing
        the walk could follow.  A class that names itself as its own
        ancestor contributes nothing further.
        """
        if self_type in _active:
            return []
        active = _active | {self_type}
        module, cls = self_type
        bases = [
            base
            for expr in self._modules[module].bases.get(cls, [])
            if (base := self._resolve_class(module, expr)) is not None
        ]
        return [
            self_type,
            *_c3_merge([*(self._mro(b, active) for b in bases), bases]),
        ]

    def _resolve_class(self, module: str, expr: ast.expr) -> _SelfType | None:
        """The indexed class a base-class expression names, or ``None``."""
        if isinstance(expr, ast.Subscript):  # ``Base[T]``
            expr = expr.value
        index = self._modules[module]
        if isinstance(expr, ast.Name):
            if expr.id in index.methods:
                return (module, expr.id)
            if expr.id in index.imported_names:
                return self._class_in_package(*index.imported_names[expr.id])
            return None
        if not (
            isinstance(expr, ast.Attribute)
            and isinstance(expr.value, ast.Name)
        ):
            return None
        owner = expr.value.id
        if owner in index.imported_modules:
            return self._class_in_package(
                index.imported_modules[owner], expr.attr
            )
        if owner in index.imported_names:
            # ``from pkg import _frame; class UC(_frame.Frame)``: the name
            # binds a *module* when ``pkg._frame`` is one we index.
            submodule = ".".join(index.imported_names[owner])
            if submodule in self._modules:
                return self._class_in_package(submodule, expr.attr)
        return None

    def _class_in_package(self, module: str, name: str) -> _SelfType | None:
        """A class *name* defined in (or re-exported by) *module*, if indexed."""
        index = self._modules.get(module)
        if index is None:
            return None
        if name in index.methods:
            return (module, name)
        if name in index.imported_names:
            return self._class_in_package(*index.imported_names[name])
        return None


def _is_super_call(func: ast.Attribute) -> bool:
    """True for ``super().attr`` (with or without ``super``'s arguments)."""
    return (
        isinstance(func.value, ast.Call)
        and isinstance(func.value.func, ast.Name)
        and func.value.func.id == "super"
    )


def _c3_merge(sequences: list[list[_SelfType]]) -> list[_SelfType]:
    """Merge base linearizations by C3 (the order Python's MRO uses).

    Raises ``ValueError`` when no consistent order exists — Python refuses
    to create such a class, so the source could not import.
    """
    pending = [list(seq) for seq in sequences if seq]
    merged: list[_SelfType] = []
    while pending:
        head = next(
            (
                seq[0]
                for seq in pending
                if not any(seq[0] in other[1:] for other in pending)
            ),
            None,
        )
        if head is None:
            raise ValueError(
                f"no consistent method resolution order: {pending}"
            )
        merged.append(head)
        pending = [
            rest for seq in pending if (rest := [c for c in seq if c != head])
        ]
    return merged


def build_use_case_corpus() -> _UseCaseCorpus:
    """Index every module of the real use-case and core-services packages.

    ``vultron/core/services/`` is indexed because it holds the helpers a use
    case shares with a BT node (BT-22-005): a write or a tree run a received
    ``execute()`` reaches through one is still that ``execute()``'s.

    ``all_trees`` rather than a fragment prefilter (TB-13-002's escape
    hatch): a helper chain can pass through a module that never spells the
    fragment itself, and dropping that module would break the chain.
    """
    return _UseCaseCorpus(
        {
            path: tree
            for root in INDEXED_ROOTS
            for path, tree in _corpus.all_trees(under=root)
        },
        roots=INDEXED_ROOTS,
    )
