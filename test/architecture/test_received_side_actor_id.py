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

A received use case runs its tree through the received-tree runner
(``run_received_tree``, ADR-0194), so the received side has one
``execute_with_setup`` call, in the runner, and none under
``vultron/core/use_cases/received/``.

The check is an allow-list, not a deny-list (#5847).  Every
``execute_with_setup`` call on the received side must pass, as ``actor_id``
(keyword or second positional argument), one of:

(a) a call ``resolve_receiving_actor_id(<dl>, <x>.receiving_actor_id)``, where
    the bare name is imported unaliased from
    ``vultron.core.services.receiving_actor`` and bound nowhere else in the
    module;
(b) a local name whose every binding in its function is a plain assignment of
    (a), with no nested function declaring it ``nonlocal``;
(c) a parameter of a module-level function, never rebound inside it, where
    every call to that function in the same module passes (a) or (b) for it,
    and the function is used only by direct calls in its own module.

Every ``execute_with_setup`` call must also sit in a function body, and the
name may appear only as a direct call's callee: a call in a lambda or class
body, an alias or a ``getattr`` string would escape the check, so each fails.

Anything else fails: the sender under any binding, a literal, another request
attribute, a bare ``request.receiving_actor_id`` (it may be ``None`` and skips
the BT-17-009 fallback), or a conditional that falls back to the sender.  The
scan covers every received-side call, a superset of the guarded-commit ones,
because telling statically which trees hold a guarded commit is fragile and
BT-17-005/009 already make the receiving actor the rule for all of them.

Issues: #2338, #5847.
"""

import ast
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from test.architecture import _corpus

_RECEIVED_ROOT = (
    _corpus.REPO_ROOT / "vultron" / "core" / "use_cases" / "received"
)
#: The received-tree runner, which every received use case calls (ADR-0194).
_RUNNER = (
    _corpus.REPO_ROOT
    / "vultron"
    / "core"
    / "behaviors"
    / "case"
    / "received_run"
    / "runner.py"
)
_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"

_RESOLVER = "resolve_receiving_actor_id"
_RESOLVER_MODULE = "vultron.core.services.receiving_actor"
_CALLEE = "execute_with_setup"
_CALL_FRAGMENT = f"{_CALLEE}("

_Scope = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef
_NESTED_SCOPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
)

#: Whether a module-level helper's name appears in another ``vultron`` module.
_MentionedElsewhere = Callable[[str], bool]


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
        and _corpus.callee_name(node.func) == _CALLEE
    )


def _resolver_is_trusted(tree: ast.Module) -> bool:
    """Whether the bare name ``resolve_receiving_actor_id`` is the real resolver.

    It is when the module imports it, unaliased, from its home module and
    binds the name nowhere else: no ``def``, class, assignment, parameter or
    second import can shadow it.
    """
    imported = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) != _RESOLVER:
                    continue
                if node.module != _RESOLVER_MODULE or alias.asname or imported:
                    return False
                imported = True
        elif isinstance(node, ast.alias):
            continue
        elif _binds(node, _RESOLVER):
            return False
    return imported


def _binds(node: ast.AST, name: str) -> bool:
    """Whether *node* binds *name* (imports excepted)."""
    if isinstance(node, ast.Name):
        return node.id == name and not isinstance(node.ctx, ast.Load)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, ast.arg):
        return node.arg == name
    if isinstance(node, ast.Import):
        return any(
            (a.asname or a.name.split(".")[0]) == name for a in node.names
        )
    return _non_name_binding(node, name)


def _is_resolver_call(node: ast.expr, trusted: bool) -> bool:
    """``resolve_receiving_actor_id(<dl>, <x>.receiving_actor_id)``.

    The callee must be the bare, trusted name: an attribute call such as
    ``self.resolve_receiving_actor_id(...)`` could be any method.
    """
    return (
        trusted
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _RESOLVER
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


def _resolver_assign_target(
    node: ast.AST, name: str, trusted: bool
) -> ast.Name | None:
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
        and _is_resolver_call(value, trusted)
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


def _bindings(scope: _Scope, name: str, trusted: bool) -> tuple[int, bool]:
    """Count *name*'s bindings in *scope*; report whether all are resolver assigns.

    Returns ``(count, all_resolver_assigns)``.  Parameters are not counted
    here.  A binding is any store, delete, ``global``/``nonlocal``,
    ``except ... as``, import alias or ``match`` capture of *name*, and any
    ``nonlocal`` declaration of *name* in a nested function, which lets that
    function rebind it out of sight.
    """
    nodes = list(_own_scope(scope))
    accepted = {
        id(target)
        for node in nodes
        if (target := _resolver_assign_target(node, name, trusted)) is not None
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
    own = {id(node) for node in nodes}
    for node in ast.walk(scope):
        if (
            isinstance(node, ast.Nonlocal)
            and name in node.names
            and id(node) not in own
        ):
            count += 1
            ok = False
    return count, ok


@dataclass
class _Module:
    """One parsed module and the lookups the allow-list needs."""

    tree: ast.Module
    mentioned_elsewhere: _MentionedElsewhere
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(
        default_factory=dict
    )
    calls: list[tuple[_Scope, ast.Call]] = field(default_factory=list)
    trusted: bool = False

    def __post_init__(self) -> None:
        self.trusted = _resolver_is_trusted(self.tree)
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

    def _only_called_directly(self, func_name: str) -> bool:
        """Whether every use of *func_name* is a direct call in this module.

        A helper passed as a value (``submit(_run, ...)``, ``f = _run``) or
        named in another module has callers this scan cannot see.
        """
        direct = {id(call.func) for _, call in self.calls}
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.Name)
                and node.id == func_name
                and id(node) not in direct
            ):
                return False
        return not self.mentioned_elsewhere(func_name)

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
        if _bindings(scope, name, self.trusted)[0]:
            return False
        if not self._only_called_directly(scope.name):
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
        if _is_resolver_call(expr, self.trusted):
            return True
        if not isinstance(expr, ast.Name):
            return False
        name = expr.id
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            name in _all_params(scope)
        ):
            return follow_params and self._is_fed_parameter(scope, name)
        count, all_resolver = _bindings(scope, name, self.trusted)
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


def _unchecked_references(module: _Module, label: str) -> list[str]:
    """Uses of ``execute_with_setup`` the call check cannot see.

    A call outside any function body (in a lambda or a class body) is never
    paired with a scope, and a reference that is not a call's callee (an
    alias, a ``getattr`` string) hides the call that follows.  Both fail.
    """
    scanned = {id(call) for _, call in module.calls}
    callees = {
        id(node.func)
        for node in ast.walk(module.tree)
        if isinstance(node, ast.Call)
    }
    found: list[str] = []
    for node in ast.walk(module.tree):
        if _is_execute_with_setup_call(node) and id(node) not in scanned:
            found.append(
                f"{label}:{_corpus.node_line(node)}: {_CALLEE} call outside"
                " a function body is not checked"
            )
        named = (isinstance(node, ast.Attribute) and node.attr == _CALLEE) or (
            isinstance(node, ast.Name) and node.id == _CALLEE
        )
        if named and id(node) not in callees:
            found.append(
                f"{label}:{_corpus.node_line(node)}: {_CALLEE} referenced"
                " other than as a direct call"
            )
        if isinstance(node, ast.Constant) and node.value == _CALLEE:
            found.append(
                f"{label}:{_corpus.node_line(node)}: {_CALLEE} named in a string"
            )
    return found


def _scan(
    tree: ast.AST,
    label: str,
    mentioned_elsewhere: _MentionedElsewhere = lambda _name: False,
) -> tuple[int, list[str]]:
    """Return ``(calls_seen, violations)`` for one module."""
    assert isinstance(tree, ast.Module)
    module = _Module(tree, mentioned_elsewhere)
    seen = 0
    violations = _unchecked_references(module, label)
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


def _mentioned_outside(path: Path) -> _MentionedElsewhere:
    """Whether a name appears as a word in a ``vultron`` module other than *path*."""

    def mentioned(name: str) -> bool:
        word = re.compile(rf"\b{re.escape(name)}\b")
        return any(
            other != path and word.search(source)
            for other, source in _corpus.sources_mentioning(
                name, under=_VULTRON_ROOT
            )
        )

    return mentioned


def test_received_use_cases_run_no_tree_of_their_own() -> None:
    """No received use case calls ``execute_with_setup``: the runner does.

    Every received tree runs through ``run_received_tree`` (ADR-0194), so the
    receiving actor is resolved in one place, checked below.
    """
    calling = sorted(
        _label(path)
        for path, _ in _corpus.sources_mentioning(
            _CALL_FRAGMENT, under=_RECEIVED_ROOT
        )
    )
    assert not calling, (
        f"received use cases calling {_CALL_FRAGMENT} directly; run the tree"
        " through run_received_tree (ADR-0194):\n"
        + "\n".join(f"  {p}" for p in calling)
    )


def test_received_side_execute_with_setup_runs_as_receiving_actor() -> None:
    """The runner's execute_with_setup runs as the resolved receiver.

    Spec BT-17-006 (with BT-17-009, BT-17-010). Issues #2338, #5847.
    """
    tree = _corpus.tree_of(_RUNNER)
    seen, violations = _scan(
        tree, _label(_RUNNER), _mentioned_outside(_RUNNER)
    )
    assert seen == 1, (
        f"{_label(_RUNNER)}: expected one {_CALL_FRAGMENT} call, saw {seen};"
        " extend _is_execute_with_setup_call"
    )
    assert not violations, (
        "the received-tree runner must pass the receiving actor"
        f" from {_RESOLVER}(<dl>, request.receiving_actor_id), directly or via"
        " a local bound only to it (BT-17-006, #5847):\n"
        + "\n".join(f"  {v}" for v in sorted(violations))
    )


_IMPORT = f"from {_RESOLVER_MODULE} import {_RESOLVER}\n"


def _fixture_violations(
    source: str,
    *,
    import_resolver: bool = True,
    mentioned_elsewhere: _MentionedElsewhere = lambda _name: False,
) -> list[str]:
    """Scan an inline fixture, by default under the canonical resolver import."""
    text = (_IMPORT + source) if import_resolver else source
    seen, violations = _scan(
        _corpus.parse_inline(text), "fixture", mentioned_elsewhere
    )
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
    # Escapes: a sender value reaching the call by a path the scan must see.
    "nonlocal_rebind_from_nested_function": (
        "def execute(self):\n"
        f"    receiving_actor_id = {_RESOLVED}\n"
        "    def rebind():\n"
        "        nonlocal receiving_actor_id\n"
        "        receiving_actor_id = request.actor_id\n"
        "    rebind()\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
    ),
    "helper_parameter_nonlocal_rebind": (
        "def _run(dl, receiving_actor_id):\n"
        "    def rebind():\n"
        "        nonlocal receiving_actor_id\n"
        "        receiving_actor_id = request.actor_id\n"
        "    rebind()\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
        "\n"
        "def execute(self):\n"
        f"    _run(self._dl, {_RESOLVED})\n"
    ),
    "call_in_lambda": (
        "def execute(self):\n"
        f"    b.execute_with_setup(tree=t, actor_id={_RESOLVED})\n"
        "    run = lambda: b.execute_with_setup(tree=t, actor_id=request.actor_id)\n"
    ),
    "call_in_class_body": (
        "def execute(self):\n"
        f"    b.execute_with_setup(tree=t, actor_id={_RESOLVED})\n"
        "\n"
        "class Holder:\n"
        "    result = b.execute_with_setup(tree=t, actor_id=request.actor_id)\n"
    ),
    "aliased_callee": (
        "def execute(self):\n"
        f"    b.execute_with_setup(tree=t, actor_id={_RESOLVED})\n"
        "    run = b.execute_with_setup\n"
        "    run(t, request.actor_id)\n"
    ),
    "getattr_callee": (
        "def execute(self):\n"
        f"    b.execute_with_setup(tree=t, actor_id={_RESOLVED})\n"
        "    getattr(b, 'execute_with_setup')(t, request.actor_id)\n"
    ),
    "helper_also_passed_as_value": (
        "def _run(dl, receiving_actor_id):\n"
        "    b.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n"
        "\n"
        "def execute(self):\n"
        f"    _run(self._dl, {_RESOLVED})\n"
        "    pool.submit(_run, self._dl, request.actor_id)\n"
    ),
    "resolver_shadowed_by_def": (
        "def resolve_receiving_actor_id(dl, actor_id):\n"
        "    return request.actor_id\n"
        "\n"
        "def execute(self):\n"
        f"    b.execute_with_setup(tree=t, actor_id={_RESOLVED})\n"
    ),
    "resolver_reimported_from_elsewhere": (
        "from m import resolve_receiving_actor_id\n"
        "def execute(self):\n"
        f"    b.execute_with_setup(tree=t, actor_id={_RESOLVED})\n"
    ),
    "resolver_called_as_attribute": (
        "def execute(self):\n"
        "    b.execute_with_setup(\n"
        "        tree=t,\n"
        "        actor_id=self.resolve_receiving_actor_id(\n"
        "            self._dl, request.receiving_actor_id\n"
        "        ),\n"
        "    )\n"
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


def test_detector_refuses_an_unimported_resolver() -> None:
    """A resolver name with no canonical import is not trusted."""
    source = (
        "def execute(self):\n"
        f"    b.execute_with_setup(tree=t, actor_id={_RESOLVED})\n"
    )
    assert _fixture_violations(source, import_resolver=False)
    assert not _fixture_violations(source)


def test_detector_refuses_a_helper_named_in_another_module() -> None:
    """Rule (c) cannot vouch for a helper another module may call."""
    source = _POSITIVE_FIXTURES["helper_parameter_fed_the_resolver"]
    assert _fixture_violations(
        source, mentioned_elsewhere=lambda n: n == "_run"
    )
    assert not _fixture_violations(source)
