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
"""Architecture invariant: received-side BTs run as the resolved receiving actor.

Spec BT-17-006 (MUST): a received-side use case that executes a guarded-commit
tree MUST call ``execute_with_setup`` with the *receiving* actor, never the
sender.  BT-17-009 and BT-17-010 make ``resolve_receiving_actor_id`` the one
source of that identity: it prefers ``request.receiving_actor_id``, falls back
to the store's owner, and raises when neither yields one.

The check is an allow-list, not a deny-list (#5847).  Every
``execute_with_setup`` call under ``vultron/core/use_cases/received/`` must pass,
as ``actor_id`` (keyword or second positional argument), one of:

(a) a call ``resolve_receiving_actor_id(<dl>, <x>.receiving_actor_id)``;
(b) a local name whose every binding in its function is a plain assignment of
    (a);
(c) a parameter of a module-level function, never rebound inside it, where
    every call to that function in the same module passes (a) or (b) for it.

Anything else fails: the sender under any binding, a literal, another request
attribute, a bare ``request.receiving_actor_id`` (it may be ``None`` and skips
the BT-17-009 fallback), or a conditional that falls back to the sender.  The
scan covers every received-side call, a superset of the guarded-commit ones,
because telling statically which trees hold a guarded commit is fragile and
BT-17-005/009 already make the receiving actor the rule for all of them.

Issues: #2338, #5847.
"""

import ast
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from test.architecture import _corpus

_RECEIVED_ROOT = (
    _corpus.REPO_ROOT / "vultron" / "core" / "use_cases" / "received"
)

_RESOLVER = "resolve_receiving_actor_id"
_CALL_FRAGMENT = "execute_with_setup("

_Scope = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef
_NESTED_SCOPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
)


def _own_scope(scope: _Scope) -> Iterator[ast.AST]:
    """Yield the nodes of *scope*, not descending into nested scopes."""
    stack: list[ast.AST] = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, _NESTED_SCOPES):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _scopes(module: ast.Module) -> Iterator[_Scope]:
    yield module
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _is_execute_with_setup_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and _corpus.callee_name(node.func) == "execute_with_setup"
    )


def _is_resolver_call(node: ast.expr) -> bool:
    """``resolve_receiving_actor_id(<dl>, <x>.receiving_actor_id)``."""
    return (
        isinstance(node, ast.Call)
        and _corpus.callee_name(node.func) == _RESOLVER
        and len(node.args) == 2
        and not node.keywords
        and isinstance(node.args[1], ast.Attribute)
        and node.args[1].attr == "receiving_actor_id"
    )


def _positional_params(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    return [a.arg for a in func.args.posonlyargs + func.args.args]


def _all_params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names = set(_positional_params(func))
    names.update(a.arg for a in func.args.kwonlyargs)
    for star in (func.args.vararg, func.args.kwarg):
        if star is not None:
            names.add(star.arg)
    return names


def _resolver_assign_target(node: ast.AST, name: str) -> ast.Name | None:
    """The target of ``name = resolve_receiving_actor_id(...)``, else ``None``."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target: ast.expr = node.targets[0]
        value: ast.expr | None = node.value
    elif isinstance(node, ast.AnnAssign):
        target, value = node.target, node.value
    else:
        return None
    if (
        isinstance(target, ast.Name)
        and target.id == name
        and value is not None
        and _is_resolver_call(value)
    ):
        return target
    return None


def _non_name_binding(node: ast.AST, name: str) -> bool:
    """Whether *node* binds *name* other than through an ``ast.Name`` store."""
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return name in node.names
    if isinstance(node, ast.alias):
        return (node.asname or node.name.split(".")[0]) == name
    if isinstance(node, ast.MatchMapping):
        return node.rest == name
    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        return node.name == name
    return False


def _bindings(scope: _Scope, name: str) -> tuple[int, bool]:
    """Count *name*'s bindings in *scope*; report whether all are resolver assigns.

    Returns ``(count, all_resolver_assigns)``.  Parameters are not counted
    here.  A binding is any store, delete, ``global``/``nonlocal``,
    ``except ... as``, import alias or ``match`` capture of *name*.
    """
    nodes = list(_own_scope(scope))
    accepted = {
        id(target)
        for node in nodes
        if (target := _resolver_assign_target(node, name)) is not None
    }
    count = 0
    ok = True
    for node in nodes:
        if isinstance(node, ast.Name) and node.id == name:
            if isinstance(node.ctx, ast.Load):
                continue
            count += 1
            ok = ok and id(node) in accepted
        elif _non_name_binding(node, name):
            count += 1
            ok = False
    return count, ok


@dataclass
class _Module:
    """One parsed module and the lookups the allow-list needs."""

    tree: ast.Module
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(
        default_factory=dict
    )
    calls: list[tuple[_Scope, ast.Call]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for stmt in self.tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[stmt.name] = stmt
        for scope in _scopes(self.tree):
            for node in _own_scope(scope):
                if isinstance(node, ast.Call):
                    self.calls.append((scope, node))

    def _argument_for(
        self,
        call: ast.Call,
        func: ast.FunctionDef | ast.AsyncFunctionDef,
        param: str,
    ) -> ast.expr | None:
        """The expression *call* passes for *param*, ``None`` if not plainly passed."""
        if any(isinstance(a, ast.Starred) for a in call.args) or any(
            kw.arg is None for kw in call.keywords
        ):
            return None
        for kw in call.keywords:
            if kw.arg == param:
                return kw.value
        positional = _positional_params(func)
        if param in positional:
            index = positional.index(param)
            if index < len(call.args):
                return call.args[index]
        return None

    def _is_fed_parameter(self, scope: _Scope, name: str) -> bool:
        """Rule (c): a module-level function's parameter fed only by (a)/(b)."""
        if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        if self.functions.get(scope.name) is not scope:
            return False
        if name not in _positional_params(scope) + [
            a.arg for a in scope.args.kwonlyargs
        ]:
            return False
        if _bindings(scope, name)[0]:
            return False
        callers = [
            (caller_scope, call)
            for caller_scope, call in self.calls
            if isinstance(call.func, ast.Name) and call.func.id == scope.name
        ]
        if not callers:
            return False
        for caller_scope, call in callers:
            arg = self._argument_for(call, scope, name)
            if arg is None or not self.is_receiving_actor(
                caller_scope, arg, follow_params=False
            ):
                return False
        return True

    def is_receiving_actor(
        self, scope: _Scope, expr: ast.expr, *, follow_params: bool = True
    ) -> bool:
        if _is_resolver_call(expr):
            return True
        if not isinstance(expr, ast.Name):
            return False
        name = expr.id
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            name in _all_params(scope)
        ):
            return follow_params and self._is_fed_parameter(scope, name)
        count, all_resolver = _bindings(scope, name)
        return count > 0 and all_resolver


def _actor_argument(call: ast.Call) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == "actor_id":
            return kw.value
    if len(call.args) >= 2 and not any(
        isinstance(a, ast.Starred) for a in call.args[:2]
    ):
        return call.args[1]
    return None


def _scan(tree: ast.AST, label: str) -> tuple[int, list[str]]:
    """Return ``(calls_seen, violations)`` for one module."""
    assert isinstance(tree, ast.Module)
    module = _Module(tree)
    seen = 0
    violations: list[str] = []
    for scope, call in module.calls:
        if not _is_execute_with_setup_call(call):
            continue
        seen += 1
        arg = _actor_argument(call)
        if arg is None:
            violations.append(f"{label}:{call.lineno}: no actor_id passed")
        elif not module.is_receiving_actor(scope, arg):
            violations.append(
                f"{label}:{call.lineno}: actor_id={ast.unparse(arg)}"
            )
    return seen, violations


def _label(source_path: Path) -> str:
    return source_path.relative_to(_corpus.REPO_ROOT).as_posix()


def test_received_side_execute_with_setup_runs_as_receiving_actor() -> None:
    """Every received-side execute_with_setup runs as the resolved receiver.

    Spec BT-17-006 (with BT-17-009, BT-17-010). Issues #2338, #5847.
    """
    violations: list[str] = []
    files_with_calls: set[Path] = set()
    for py_file, tree in _corpus.files_mentioning(
        _CALL_FRAGMENT, under=_RECEIVED_ROOT
    ):
        seen, found = _scan(tree, _label(py_file))
        if seen:
            files_with_calls.add(py_file)
        violations.extend(found)

    mentioning = {
        path
        for path, _ in _corpus.sources_mentioning(
            _CALL_FRAGMENT, under=_RECEIVED_ROOT
        )
    }
    assert mentioning, f"no {_CALL_FRAGMENT} call found under {_RECEIVED_ROOT}"
    undetected = sorted(_label(p) for p in mentioning - files_with_calls)
    assert not undetected, (
        f"these files contain {_CALL_FRAGMENT} but the detector saw no call;"
        " extend _is_execute_with_setup_call:\n"
        + "\n".join(f"  {p}" for p in undetected)
    )
    assert not violations, (
        "received-side execute_with_setup calls must pass the receiving actor"
        f" from {_RESOLVER}(<dl>, request.receiving_actor_id), directly or via"
        " a local or helper parameter bound only to it (BT-17-006, #5847):\n"
        + "\n".join(f"  {v}" for v in sorted(violations))
    )


def _fixture_violations(source: str) -> list[str]:
    seen, violations = _scan(_corpus.parse_inline(source), "fixture")
    assert seen, "fixture contains no execute_with_setup call"
    return violations


_RESOLVED = "resolve_receiving_actor_id(self._dl, request.receiving_actor_id)"

#: Each source passes something other than the resolved receiving actor.
_NEGATIVE_FIXTURES: dict[str, str] = {
    "sender_under_other_binding": (
        "def execute(self, req):\n"
        "    b.execute_with_setup(tree=t, actor_id=req.actor_id)\n"
    ),
    "sender_on_self_request": (
        "def execute(self):\n"
        "    b.execute_with_setup(tree=t, actor_id=self._request.actor_id)\n"
    ),
    "literal": (
        "def execute(self):\n"
        "    b.execute_with_setup(\n"
        "        tree=t, actor_id='https://example.org/actors/x'\n"
        "    )\n"
    ),
    "other_request_attribute": (
        "def execute(self):\n"
        "    b.execute_with_setup(tree=t, actor_id=request.object_id)\n"
    ),
    "resolver_fed_the_sender": (
        "def execute(self):\n"
        "    b.execute_with_setup(\n"
        "        tree=t,\n"
        "        actor_id=resolve_receiving_actor_id(self._dl, request.actor_id),\n"
        "    )\n"
    ),
    "local_rebound_to_sender": (
        "def execute(self):\n"
        f"    receiving_actor_id = {_RESOLVED}\n"
        "    receiving_actor_id = request.actor_id\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "loop_target_binding": (
        "def execute(self):\n"
        "    for receiving_actor_id in (request.actor_id,):\n"
        "        b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "positional_sender": (
        "def execute(self):\n    b.execute_with_setup(t, request.actor_id)\n"
    ),
    "missing_actor_id": (
        "def execute(self):\n"
        "    b.execute_with_setup(tree=t, activity=request)\n"
    ),
    "conditional_sender_fallback": (
        "def execute(self):\n"
        "    b.execute_with_setup(\n"
        "        tree=t,\n"
        "        actor_id=request.receiving_actor_id\n"
        "        if request.receiving_actor_id is not None\n"
        "        else request.actor_id,\n"
        "    )\n"
    ),
    "bare_receiving_actor_id": (
        "def execute(self):\n"
        "    b.execute_with_setup(tree=t, actor_id=request.receiving_actor_id)\n"
    ),
    "helper_parameter_fed_the_sender": (
        "def _run(dl, request, receiving_actor_id):\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
        "\n"
        "class UseCase:\n"
        "    def execute(self):\n"
        "        _run(self._dl, request, request.actor_id)\n"
    ),
    # Detector branches: every other way a name can be bound or fed.
    "global_binding": (
        "def execute(self):\n"
        "    global receiving_actor_id\n"
        f"    receiving_actor_id = {_RESOLVED}\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "except_as_binding": (
        "def execute(self):\n"
        f"    receiving_actor_id = {_RESOLVED}\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as receiving_actor_id:\n"
        "        pass\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "import_alias_binding": (
        "def execute(self):\n"
        "    from m import sender as receiving_actor_id\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "match_capture_binding": (
        "def execute(self):\n"
        "    match request.actor_id:\n"
        "        case receiving_actor_id:\n"
        "            b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "helper_parameter_without_callers": (
        "def _run(dl, request, receiving_actor_id):\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "method_parameter": (
        "class UseCase:\n"
        "    def _run(self, receiving_actor_id):\n"
        "        b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "helper_called_with_star_args": (
        "def _run(dl, request, receiving_actor_id):\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
        "\n"
        "def execute(self):\n"
        "    _run(*args)\n"
    ),
    "helper_parameter_two_hops": (
        "def _inner(receiving_actor_id):\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
        "\n"
        "def _outer(receiving_actor_id):\n"
        "    _inner(receiving_actor_id)\n"
        "\n"
        "def execute(self):\n"
        f"    _outer({_RESOLVED})\n"
    ),
}

#: Each source passes the resolved receiving actor in an accepted form.
_POSITIVE_FIXTURES: dict[str, str] = {
    "inline_resolver": (
        "def execute(self):\n"
        f"    b.execute_with_setup(tree=t, actor_id={_RESOLVED})\n"
    ),
    "local_bound_to_resolver": (
        "def execute(self):\n"
        f"    receiving_actor_id = {_RESOLVED}\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "helper_parameter_fed_the_resolver": (
        "def _run(dl, request, receiving_actor_id):\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
        "\n"
        "class UseCase:\n"
        "    def execute(self):\n"
        f"        receiving_actor_id = {_RESOLVED}\n"
        "        _run(self._dl, request, receiving_actor_id)\n"
    ),
    "annotated_local_bound_to_resolver": (
        "def execute(self):\n"
        f"    receiving_actor_id: str = {_RESOLVED}\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "helper_keyword_parameter_fed_the_resolver": (
        "def _run(dl, *, receiving_actor_id):\n"
        "    b.execute_with_setup(t, receiving_actor_id)\n"
        "\n"
        "def execute(self):\n"
        f"    _run(self._dl, receiving_actor_id={_RESOLVED})\n"
    ),
}


def test_detector_flags_every_non_receiver_actor() -> None:
    """Each negative fixture passes a non-receiver actor and must be flagged."""
    missed = [
        name
        for name, source in _NEGATIVE_FIXTURES.items()
        if not _fixture_violations(source)
    ]
    assert not missed, f"detector accepted non-receiver actors: {missed}"


def test_detector_accepts_the_resolved_receiving_actor() -> None:
    """Each positive fixture passes the resolved receiver and must be accepted."""
    flagged = {
        name: found
        for name, source in _POSITIVE_FIXTURES.items()
        if (found := _fixture_violations(source))
    }
    assert not flagged, f"detector rejected the receiving actor: {flagged}"
