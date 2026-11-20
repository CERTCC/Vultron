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
"""A received use case only builds its tree and hands it to the runner.

The rule (HP-01-044, ADR-0195, BT-25-009): no code under
``vultron/core/use_cases/received/`` calls the DataLayer, passes it to
anything but the runner, or touches ``BTBridge``.  A value only the store
holds is found by a lookup node in the tree; the runner is the one place a
received run reaches the store and the bridge.

A *store* here is a parameter annotated with a persistence port
(``...Persistence``, ``DataLayer``) or named ``dl`` / ``datalayer``, and any
``self`` attribute assigned one.  Each use of a store must be one of:

- the value of a ``self.<attr> = <store>`` assignment (the constructor
  keeping it);
- an argument of ``run_received_tree``, of ``super().__init__``, or of a
  function or class defined under ``received/`` (a sibling use case or a
  shared runner helper, whose own parameters this scan checks in turn).

Every other use is a violation: a method call or attribute read on the
store (``self._dl.read(...)``), or the store passed to any other callable
(a reader such as ``announced_ledger_entry(self._dl, ...)``).  Any
reference to ``BTBridge`` is a violation too.  The set is empty, so there
is no exemption list.
"""

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from test.architecture import _corpus
from test.architecture._use_case_call_graph import RECEIVED_ROOT

#: The package every allowed store-taking callee is defined in.
_RECEIVED_PACKAGE = "vultron.core.use_cases.received"

#: The runner a received use case hands its tree and store to (ADR-0195).
_RUNNER = "run_received_tree"

#: The bridge no received use case may reach (BT-17-005, ADR-0195).
_BRIDGE = "BTBridge"

#: Parameter names that carry the store whatever their annotation.
_STORE_NAMES = frozenset({"dl", "datalayer"})

_Function = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda


def _is_store_annotation(annotation: ast.expr | None) -> bool:
    if annotation is None:
        return False
    text = ast.unparse(annotation)
    return "Persistence" in text or "DataLayer" in text


def _store_parameters(fn: _Function) -> frozenset[str]:
    args = fn.args
    params = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    return frozenset(
        p.arg
        for p in params
        if p.arg in _STORE_NAMES or _is_store_annotation(p.annotation)
    )


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: node
        for node in ast.walk(tree)
        for child in ast.iter_child_nodes(node)
    }


def _received_imports(tree: ast.AST, package: str) -> frozenset[str]:
    """The names *tree* imports from a module under ``received/``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = _corpus.resolve_import(
                node.module or "", node.level, package
            )
            if module == _RECEIVED_PACKAGE or module.startswith(
                f"{_RECEIVED_PACKAGE}."
            ):
                names |= {a.asname or a.name for a in node.names}
    return frozenset(names)


def _local_definitions(tree: ast.AST) -> frozenset[str]:
    """The functions and classes *tree* defines, at any depth."""
    return frozenset(
        node.name
        for node in ast.walk(tree)
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )
    )


def _is_self_attr(node: ast.AST, attrs: frozenset[str] | None = None) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and (attrs is None or node.attr in attrs)
    )


def _enclosing_function(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> _Function | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
        ):
            return current
        current = parents.get(current)
    return None


def _store_names_in_scope(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> frozenset[str]:
    """The store parameters of every function *node* is nested in."""
    names: set[str] = set()
    fn = _enclosing_function(node, parents)
    while fn is not None:
        names |= _store_parameters(fn)
        fn = _enclosing_function(fn, parents)
    return frozenset(names)


def _store_attributes(
    tree: ast.AST, parents: dict[ast.AST, ast.AST]
) -> frozenset[str]:
    """The ``self`` attributes *tree* assigns a store parameter to."""
    attrs: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id in _store_names_in_scope(node, parents)
        ):
            attrs |= {
                t.attr
                for t in node.targets
                if isinstance(t, ast.Attribute) and _is_self_attr(t)
            }
    return frozenset(attrs)


def _is_super_init(func: ast.expr) -> bool:
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "__init__"
        and isinstance(func.value, ast.Call)
        and isinstance(func.value.func, ast.Name)
        and func.value.func.id == "super"
    )


#: Each function or class under ``received/``, by name: the function, or
#: the class's ``__init__`` (``None`` when it has none) with its base names.
type _Definitions = dict[
    str, list[tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, list[str]]]
]


def definitions_in(trees: Iterable[ast.AST]) -> _Definitions:
    """The callables a store may be handed to, from *trees*."""
    found: _Definitions = {}
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.setdefault(node.name, []).append((node, []))
            elif isinstance(node, ast.ClassDef):
                init = next(
                    (
                        n
                        for n in node.body
                        if isinstance(
                            n, (ast.FunctionDef, ast.AsyncFunctionDef)
                        )
                        and n.name == "__init__"
                    ),
                    None,
                )
                bases = [
                    b.id if isinstance(b, ast.Name) else ast.unparse(b)
                    for b in node.bases
                ]
                found.setdefault(node.name, []).append((init, bases))
    return found


def _initialisers(
    name: str, definitions: _Definitions, depth: int = 0
) -> list[ast.FunctionDef | ast.AsyncFunctionDef] | None:
    """The functions a call of *name* runs with its arguments, or ``None``
    when one cannot be found (a class whose ``__init__`` lies outside
    ``received/``)."""
    candidates = definitions.get(name)
    if not candidates or depth > 8:
        return None
    found: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for fn, bases in candidates:
        if fn is not None:
            found.append(fn)
            continue
        inherited = [
            _initialisers(base.partition("[")[0], definitions, depth + 1)
            for base in bases
        ]
        resolved = [fns for fns in inherited if fns is not None]
        if not resolved:
            return None
        found.extend(resolved[0])
    return found


def _receives_a_store(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    position: int | None,
    keyword: str | None,
) -> bool:
    """Whether *fn*'s parameter at *position* (or named *keyword*) is one
    this scan checks as a store."""
    params = [*fn.args.posonlyargs, *fn.args.args]
    if params and params[0].arg in ("self", "cls"):
        params = params[1:]
    if keyword is not None:
        name = keyword
    elif position is not None and position < len(params):
        name = params[position].arg
    else:
        return False
    return name in _store_parameters(fn)


def _allowed_use(
    node: ast.expr,
    parents: dict[ast.AST, ast.AST],
    allowed_callees: frozenset[str],
    definitions: _Definitions,
) -> bool:
    """Whether the store reference *node* is kept or handed on, not used.

    A store handed to a callable under ``received/`` must land in a
    parameter this scan checks as a store, so the callee's own uses are
    checked in turn.
    """
    parent = parents.get(node)
    if isinstance(parent, ast.Assign) and all(
        _is_self_attr(t) for t in parent.targets
    ):
        return True
    call = parents.get(parent) if isinstance(parent, ast.keyword) else parent
    if not isinstance(call, ast.Call) or node is call.func:
        return False
    position = next((i for i, a in enumerate(call.args) if a is node), None)
    keyword = next((kw.arg for kw in call.keywords if kw.value is node), None)
    if position is None and keyword is None:
        return False
    func = call.func
    if _is_super_init(func):
        return True
    if not isinstance(func, ast.Name):
        return False
    if func.id == _RUNNER:
        return True
    if func.id not in allowed_callees:
        return False
    callees = _initialisers(func.id, definitions)
    return bool(callees) and all(
        _receives_a_store(fn, position, keyword) for fn in callees or ()
    )


def _is_store_reference(
    node: ast.AST, parents: dict[ast.AST, ast.AST], attrs: frozenset[str]
) -> bool:
    """Whether *node* reads a store parameter or a ``self`` store attribute."""
    if isinstance(node, ast.Name):
        return isinstance(node.ctx, ast.Load) and node.id in (
            _store_names_in_scope(node, parents)
        )
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Load)
        and _is_self_attr(node, attrs)
    )


def store_violations(
    tree: ast.AST,
    rel: str,
    package: str,
    *,
    definitions: _Definitions | None = None,
    store_attributes: frozenset[str] = frozenset(),
) -> list[str]:
    """Each store use or ``BTBridge`` reference in module *rel* the rule
    forbids, as ``rel:line: what``.

    *definitions* are the callables under ``received/`` (this module's
    alone by default) and *store_attributes* the ``self`` attributes any
    module there keeps a store in, so a subclass reading a base's store
    attribute is checked too.
    """
    parents = _parents(tree)
    allowed = _local_definitions(tree) | _received_imports(tree, package)
    attrs = _store_attributes(tree, parents) | store_attributes
    defs = definitions if definitions is not None else definitions_in([tree])
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.alias) and _BRIDGE in (node.name, node.asname):
            found.append(f"{rel}:{node.lineno}: imports {_BRIDGE}")
            continue
        if isinstance(node, ast.Name) and node.id == _BRIDGE:
            found.append(f"{rel}:{node.lineno}: names {_BRIDGE}")
            continue
        if isinstance(node, ast.Attribute) and node.attr == _BRIDGE:
            found.append(f"{rel}:{node.lineno}: names {_BRIDGE}")
            continue
        if _is_store_reference(node, parents, attrs) and not _allowed_use(
            node,  # type: ignore[arg-type]
            parents,
            allowed,
            defs,
        ):
            context = parents.get(node)
            shown = ast.unparse(context if context is not None else node)
            line = getattr(node, "lineno", 0)
            found.append(f"{rel}:{line}: {shown.splitlines()[0]}")
    return sorted(found)


def _received_modules() -> Iterator[tuple[Path, ast.AST]]:
    return _corpus.all_trees(RECEIVED_ROOT)


@pytest.mark.spec("HP-01-044")
@pytest.mark.spec("HP-01-045")
@pytest.mark.spec("BT-25-009")
def test_no_received_use_case_reaches_the_store_or_the_bridge() -> None:
    """Under ``received/`` the store is only kept and handed to the runner."""
    modules = list(_received_modules())
    assert modules, f"corpus drifted: no module under {RECEIVED_ROOT}"
    hands_on = [
        path
        for path, tree in modules
        if any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == _RUNNER
            for n in ast.walk(tree)
        )
    ]
    assert hands_on, f"corpus drifted: nothing under received/ calls {_RUNNER}"
    kept = [
        path
        for path, tree in modules
        if _store_attributes(tree, _parents(tree))
    ]
    assert kept, "corpus drifted: no received use case keeps a store"
    definitions = definitions_in(tree for _, tree in modules)
    attributes = frozenset().union(
        *(_store_attributes(tree, _parents(tree)) for _, tree in modules)
    )
    violations = [
        line
        for path, tree in modules
        for line in store_violations(
            tree,
            path.relative_to(_corpus.REPO_ROOT).as_posix(),
            _corpus.package_of(path),
            definitions=definitions,
            store_attributes=attributes,
        )
    ]
    assert not violations, (
        "received use cases reaching the DataLayer or BTBridge: find the"
        " value with a lookup node in the tree (BT-25-009) and read the"
        " verdict from the nodes' declarations (HP-01-045, ADR-0195):\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# Detector self-tests on synthetic sources
# ---------------------------------------------------------------------------

_PKG = f"{_RECEIVED_PACKAGE}.fault"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "class UC:\n"
            "    def __init__(self, dl: CasePersistence, request):\n"
            "        self._dl = dl\n"
            "    def execute(self):\n"
            "        return run_received_tree(t, dl=self._dl, request=r)\n",
            [],
            id="kept-and-handed-to-the-runner",
        ),
        pytest.param(
            "class UC:\n"
            "    def __init__(self, dl, request):\n"
            "        self._dl = dl\n"
            "    def execute(self):\n"
            "        case = self._dl.read(self._request.case_id)\n",
            ["m.py:5: self._dl.read"],
            id="method-call-on-the-store",
        ),
        pytest.param(
            "from vultron.core.behaviors.sync.nodes.reseed import (\n"
            "    announced_ledger_entry,\n"
            ")\n"
            "class UC:\n"
            "    def __init__(self, dl: CasePersistence, request):\n"
            "        self._dl = dl\n"
            "    def execute(self):\n"
            "        return announced_ledger_entry(self._dl, 'a', 'b')\n",
            ["m.py:8: announced_ledger_entry(self._dl, 'a', 'b')"],
            id="store-passed-to-a-reader",
        ),
        pytest.param(
            "def helper(*, store: CaseOutboxPersistence):\n"
            "    return store.find_case_by_report_id('r')\n",
            ["m.py:2: store.find_case_by_report_id"],
            id="annotated-helper-parameter",
        ),
        pytest.param(
            "from vultron.core.use_cases.received._offer_reply import (\n"
            "    run_offer_reply_tree,\n"
            ")\n"
            "class Sub(Base):\n"
            "    def __init__(self, dl: CasePersistence, request):\n"
            "        super().__init__(dl, request)\n"
            "        self._inner = Other(dl, request)\n"
            "    def execute(self):\n"
            "        return run_offer_reply_tree(dl=self._dl, request=r)\n"
            "class Other:\n"
            "    def __init__(self, dl: CasePersistence, request):\n"
            "        self._dl = dl\n"
            "# the imported helper, as the corpus-wide index finds it\n"
            "def run_offer_reply_tree(*, dl: CaseOutboxPersistence, request):\n"
            "    return run_received_tree(t, dl=dl, request=request)\n",
            [],
            id="handed-to-super-a-sibling-and-a-received-helper",
        ),
        pytest.param(
            "def _peek(thing):\n"
            "    return thing.read('x')\n"
            "class UC:\n"
            "    def __init__(self, dl: CasePersistence, request):\n"
            "        self._dl = dl\n"
            "    def execute(self):\n"
            "        return _peek(self._dl)\n",
            ["m.py:7: _peek(self._dl)"],
            id="store-into-an-unchecked-local-parameter",
        ),
        pytest.param(
            "class Helper:\n"
            "    def __init__(self, store: CasePersistence):\n"
            "        self._store = store\n"
            "class UC:\n"
            "    def __init__(self, dl: CasePersistence, request):\n"
            "        self._helper = Helper(dl)\n",
            [],
            id="store-into-a-checked-constructor-parameter",
        ),
        pytest.param(
            "class Opaque:\n"
            "    pass\n"
            "class UC:\n"
            "    def __init__(self, dl: CasePersistence, request):\n"
            "        self._x = Opaque(dl)\n",
            ["m.py:5: Opaque(dl)"],
            id="store-into-a-class-whose-init-is-not-found",
        ),
        pytest.param(
            "class UC:\n"
            "    def __init__(self, dl, request):\n"
            "        self._dl = dl\n"
            "    def execute(self):\n"
            "        store = self._dl\n",
            ["m.py:5: store = self._dl"],
            id="store-aliased",
        ),
        pytest.param(
            "from vultron.core.behaviors.bridge import BTBridge\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        return BTBridge(datalayer=x).execute_with_setup(t)\n",
            ["m.py:1: imports BTBridge", "m.py:4: names BTBridge"],
            id="bridge",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        def build(actor):\n"
            "            return make_tree(self._dl)\n"
            "        return run_received_tree(build, dl=self._dl)\n"
            "    def __init__(self, dl):\n"
            "        self._dl = dl\n",
            ["m.py:4: make_tree(self._dl)"],
            id="store-read-in-a-builder",
        ),
    ],
)
def test_detector(source: str, expected: list[str]) -> None:
    assert (
        store_violations(_corpus.parse_inline(source), "m.py", _PKG)
        == expected
    )


@pytest.mark.spec("HP-01-044")
def test_a_store_attribute_kept_by_a_base_is_checked_in_a_subclass() -> None:
    """A subclass in another module reads the store its base kept."""
    sub = _corpus.parse_inline(
        "class Sub(Base):\n"
        "    def execute(self):\n"
        "        return self._dl.read('x')\n"
    )
    assert store_violations(
        sub, "m.py", _PKG, store_attributes=frozenset({"_dl"})
    ) == ["m.py:3: self._dl.read"]
