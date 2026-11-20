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
from collections.abc import Iterator
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


def _allowed_use(
    node: ast.expr,
    parents: dict[ast.AST, ast.AST],
    allowed_callees: frozenset[str],
) -> bool:
    """Whether the store reference *node* is kept or handed on, not used."""
    parent = parents.get(node)
    if isinstance(parent, ast.Assign) and all(
        _is_self_attr(t) for t in parent.targets
    ):
        return True
    call = parents.get(parent) if isinstance(parent, ast.keyword) else parent
    if not isinstance(call, ast.Call) or node is call.func:
        return False
    if not (
        node in call.args or any(kw.value is node for kw in call.keywords)
    ):
        return False
    func = call.func
    if _is_super_init(func):
        return True
    return isinstance(func, ast.Name) and (
        func.id == _RUNNER or func.id in allowed_callees
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


def store_violations(tree: ast.AST, rel: str, package: str) -> list[str]:
    """Each store use or ``BTBridge`` reference in module *rel* the rule
    forbids, as ``rel:line: what``."""
    parents = _parents(tree)
    allowed = _local_definitions(tree) | _received_imports(tree, package)
    attrs = _store_attributes(tree, parents)
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
    violations = [
        line
        for path, tree in modules
        for line in store_violations(
            tree,
            path.relative_to(_corpus.REPO_ROOT).as_posix(),
            _corpus.package_of(path),
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
            "    pass\n",
            [],
            id="handed-to-super-a-sibling-and-a-received-helper",
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
