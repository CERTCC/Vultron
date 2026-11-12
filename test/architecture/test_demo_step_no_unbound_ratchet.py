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

"""Architecture ratchet: no demo_step/demo_check block may leave a variable
unbound — or holding a placeholder sentinel — for a later read (#2308, #3038).

``demo_step``, ``demo_check`` and ``demo_gate`` swallow all exceptions by
design: they record the failure on ``_demo_failures`` and continue.  When a block's body raises,
any variable assigned *only* inside that block is left unbound — the next read
causes ``UnboundLocalError``, which propagates out of the demo function and
prevents ``assert_demo_success()`` from being reached.

The preferred fix is the nested-block model (ADR-0058, ``demo_gate``
docstring): put every step that reads the value *inside* the block that
produces it, so a failed block skips its dependents instead of handing them a
missing value.  Pre-initialising the variable to a sentinel (typically
``None``) *before* the block is legitimate only when every later read is
guarded — an unguarded sentinel merely turns ``UnboundLocalError`` into a
downstream step that posts ``None`` and blames the wrong step (#3038, #3887).

This module walks every ``*.py`` file under ``vultron/demo/`` with the Python
AST and runs two checks over it.

**The unbound check** fails if any function contains a variable that is:

1. Assigned for the first time inside a ``demo_step``, ``demo_check`` or
   ``demo_gate`` block body (at the shallow / direct-child level of that block), AND
2. Used (read) after the block closes in the same function scope.

**The sentinel check** covers the shape the unbound check is structurally
unable to see (#3038): a name pre-initialised to a placeholder is already
bound, so an undefended read of it raises nothing — it hands the next step
``None`` or ``""``, which then fails for the wrong reason and blames the wrong
step.  It fails if any name is:

1. Pre-initialised to a placeholder literal — ``None`` or ``""`` — at the
   statement level of a block, AND
2. Assigned anywhere inside a later ``demo_step``, ``demo_check`` or
   ``demo_gate`` body — nested assignments included, since a block that
   raises early never reaches them either, and a producing block one level
   in, inside an ``if``, ``for``, ``try``, ``match`` or another guarded
   block, counts too.  The innermost guarded block that writes the name owns
   the record, AND
3. Read after that block closes, before any guard on it — in the rest of an
   enclosing block, a ``try``'s ``else``, handlers or ``finally``, the test
   and body of an enclosing loop on its next pass, or after all of them
   (#5904).

A **read** is the name passed to a call — directly, or inside a ``dict``,
``list``, ``tuple``, ``set``, star-unpack or f-string argument, because
#3038's own line is ``post_to_trigger(..., body={"invite_id": invite_id})`` —
or an attribute or subscript of it.  A bare ``return name`` is not a read:
that is the ``Optional[T]`` contract, and the caller carries the guard.

A **guard** is a comparison of the name against a placeholder (``is None``,
``is not None``, ``== ""``), a truthiness test (``if x:``, ``assert x``,
``if not x:``), or a rebinding of the name to something that is not a
placeholder.  The first guard, rebinding or read in evaluation order decides,
so a guard beside the later reads defends them as an enclosing one would —
deliberate, because ``if x is None: raise`` is the shape the authoring note
asks for.  That holds at the statement level only: a guard or rebinding inside
a branch that may not run — an ``if`` or loop body, a ``try`` arm other than
``finally``, a ``match`` case, a guarded block's body — decides nothing past
the branch, though a read inside it still counts (#5904).  Two exceptions: a
statement whose arms are exhaustive — an ``if``/``else``, a ``match`` ending
in an irrefutable case, a ``try`` and its handlers — decides the name when
every arm either decides it or leaves by ``raise``, ``return``, ``break`` or
``continue``; and a loop decides it when every ``break`` follows a guard or
rebinding and its ``else`` arm decides it too, which ``while True:`` never
reaches.  The arm a guard proves holds the placeholder — the ``else`` of
``if x:``, the body of ``if x is None:`` — is not defended by it, and a
comparison proves only what the test it sits in acts on: ``assert x is None``
and ``if x is None and flag:`` defend nothing, while in
``x is not None and x.ready`` the later operand is defended.  A ``for`` target
counts as a rebinding although the loop may run zero times: a deliberate
leniency, since every demo loop over a sentinel name binds it as its target.
Nested function and class bodies are a separate scope and are not followed,
nor is a ``lambda`` or a comprehension that binds the name itself: there the
name is a different variable, and a rebinding — ``:=`` included — ends the
sentinel rather than reading it.

Both checks key on the act — the pre-initialisation, the guarded ``with``, the
read — and not on the name of the function that performs it, so neither loses
subjects to a rename (#5535).  Neither carries a baseline: the terminal value
of both is the empty set, and it is reached (ARCH-18-005).

So this is a zero-tolerance invariant, not a ratchet counting down to one: the
93 sites #2308 found were all fixed in the commit that added this module, and
either check failing means a new undefended site was just introduced.
"""

import ast
import functools
import pathlib
from collections.abc import Iterator, Sequence
from typing import NamedTuple, TypeGuard

import pytest

from test.architecture import _corpus

DEMO_DIR = _corpus.REPO_ROOT / "vultron" / "demo"

_GUARDED_CMS = {"demo_step", "demo_check", "demo_gate"}

#: Node types that open a new name scope; neither check follows them.
_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _cm_name(with_stmt: ast.With) -> str | None:
    """Return the guarded CM name if any with-item is a guarded CM, else None."""
    for item in with_stmt.items:
        ctx = item.context_expr
        if isinstance(ctx, ast.Call):
            fn = ctx.func
            name = (
                fn.id
                if isinstance(fn, ast.Name)
                else fn.attr
                if isinstance(fn, ast.Attribute)
                else None
            )
            if name in _GUARDED_CMS:
                return name
    return None


def _store_names(node: ast.expr) -> set:
    """All names in Store context inside an assignment target."""
    names: set = set()
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            names.update(_store_names(elt))
    elif isinstance(node, ast.Starred):
        names.update(_store_names(node.value))
    return names


def _assigned_shallow(stmts: list) -> set:
    """Names directly assigned (not nested) in a flat statement list."""
    names: set = set()
    for stmt in stmts:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                names.update(_store_names(target))
        elif (
            isinstance(stmt, ast.AugAssign)
            or (isinstance(stmt, ast.AnnAssign) and stmt.value is not None)
            or isinstance(stmt, (ast.For, ast.AsyncFor))
        ):
            names.update(_store_names(stmt.target))
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                if item.optional_vars:
                    names.update(_store_names(item.optional_vars))
    return names


def _load_names(stmts: list) -> set:
    """Load-context Name ids within stmts, not crossing nested scope boundaries."""
    names: set = set()

    def _collect(node: ast.AST) -> None:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
        if isinstance(node, _SCOPE_TYPES):
            return  # stop at scope boundary
        for child in ast.iter_child_nodes(node):
            _collect(child)

    for stmt in stmts:
        _collect(stmt)
    return names


def _undefended_in_stmts(stmts: list) -> list:
    """Return ``(lineno, varname)`` pairs for every undefended site.

    Scans a flat list of statements (a function body) left-to-right,
    tracking which names have been assigned before each ``with`` block.
    """
    results = []
    pre: set = set()

    for i, stmt in enumerate(stmts):
        if not isinstance(stmt, ast.With):
            pre.update(_assigned_shallow([stmt]))
            continue

        cm = _cm_name(stmt)
        if cm not in _GUARDED_CMS:
            pre.update(_assigned_shallow([stmt]))
            continue

        # optional_vars (the "as x" binding) are bound by __enter__ before the
        # body runs; add them to pre so a body re-assignment is not flagged.
        for item in stmt.items:
            if item.optional_vars:
                pre.update(_store_names(item.optional_vars))

        block_assigned = _assigned_shallow(stmt.body)
        undefended = block_assigned - pre

        if undefended:
            post_used = _load_names(stmts[i + 1 :])
            for var in sorted(undefended & post_used):
                results.append((stmt.lineno, var))

        # After the block the var *might* exist; track it to avoid
        # double-reporting on a subsequent block that re-uses the same name.
        pre.update(block_assigned)

    return results


def _violations_in_tree(tree: ast.AST, path: pathlib.Path) -> list:
    """Return violations found in an already-parsed tree."""
    found = []

    class _V(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            for lineno, var in _undefended_in_stmts(node.body):
                found.append((path, lineno, var))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            for lineno, var in _undefended_in_stmts(node.body):
                found.append((path, lineno, var))
            self.generic_visit(node)

    _V().visit(tree)
    return found


def _violations_in_file(path: pathlib.Path) -> list:
    source = path.read_text()
    try:
        tree = _corpus.parse_inline(source, filename=str(path))
    except SyntaxError:
        return []
    return _violations_in_tree(tree, path)


# ---------------------------------------------------------------------------
# AST helpers — the placeholder-sentinel check (#3038)
# ---------------------------------------------------------------------------


class SentinelSite(NamedTuple):
    """One placeholder pre-initialisation that a guarded block then assigns.

    *block* is the line of the guarded ``with``, so two blocks writing the
    same sentinel are told apart rather than producing identical records.
    *read* is the line of the first read of *name* that the block's failure
    can reach and no guard defends — after the block, in the rest of an
    enclosing block, a later ``try`` arm or the next pass of a loop — or
    ``None`` when every such read is defended.  A site with
    no unguarded read is the legitimate ``Optional[T]`` shape
    (``notes/demo-scenario-authoring.md``); a site with one is a #3038 defect.
    """

    preinit: int
    name: str
    block: int
    read: int | None


def _is_placeholder(node: ast.expr | None) -> bool:
    """True for a placeholder literal: ``None`` or ``""``.

    These are the literals a demo author writes to stand in for a value a
    later step needs, and which that step can never legitimately act on — an
    id or an activity reference is never ``""``.  ``0`` and the empty
    collections stay out: a count of zero and an empty accumulator are values
    a later step may legitimately read (#3038, #3887).
    """
    if not isinstance(node, ast.Constant):
        return False
    return node.value is None or node.value == ""


def _placeholder_preinit_names(stmt: ast.stmt) -> set[str]:
    """Names *stmt* pre-initialises to a placeholder literal."""
    if isinstance(stmt, ast.Assign) and _is_placeholder(stmt.value):
        names: set[str] = set()
        for target in stmt.targets:
            names |= _store_names(target)
        return names
    if isinstance(stmt, ast.AnnAssign) and _is_placeholder(stmt.value):
        return _store_names(stmt.target)
    return set()


def _rebound_targets(node: ast.AST) -> list[ast.expr]:
    """The assignment targets *node* binds to a non-placeholder value.

    Empty for a node that binds nothing, and for one whose value is a
    placeholder literal: re-writing the sentinel does not end it.  A bare
    annotation (``x: int``) has no value and so binds nothing either.
    """
    if isinstance(node, ast.Assign):
        return [] if _is_placeholder(node.value) else list(node.targets)
    if isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
        if node.value is None or _is_placeholder(node.value):
            return []
        return [node.target]
    if isinstance(node, (ast.AugAssign, ast.For, ast.AsyncFor)):
        return [node.target]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [i.optional_vars for i in node.items if i.optional_vars]
    return []


def _rebound_names(node: ast.AST) -> set[str]:
    """Names *node* binds to something other than a placeholder literal."""
    names: set[str] = set()
    for target in _rebound_targets(node):
        names |= _store_names(target)
    # ``except E as x`` and a capture pattern bind a bare identifier, not a
    # target expression.
    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        names |= {node.name} if node.name else set()
    if isinstance(node, ast.MatchMapping) and node.rest:
        names.add(node.rest)
    return names


def _is_guarded_block(node: ast.AST) -> TypeGuard[ast.With]:
    """True for a ``with`` over ``demo_step``, ``demo_check`` or ``demo_gate``."""
    return isinstance(node, ast.With) and _cm_name(node) in _GUARDED_CMS


def _assigned_by_block_itself(stmts: list[ast.stmt]) -> set[str]:
    """Names *stmts* assign anywhere outside a nested guarded block.

    Wider than :func:`_assigned_shallow`, which the unbound check needs: a
    sentinel written inside a nested ``if`` or ``for`` is just as unwritten
    when the enclosing block raises before reaching it.  A nested guarded
    block's body is left out — that block is the innermost producer of what
    it writes and owns the record, with a read window that starts inside this
    block (#5904) — but its ``as`` binding is this block's own write.
    """
    names: set[str] = set()

    def _collect(node: ast.AST) -> None:
        if isinstance(node, _SCOPE_TYPES):
            return
        if _is_guarded_block(node):
            names.update(_rebound_names(node))
            return
        if isinstance(node, ast.stmt):
            names.update(_assigned_shallow([node]))
        for child in ast.iter_child_nodes(node):
            _collect(child)

    for stmt in stmts:
        _collect(stmt)
    return names


#: ``is``/``==`` against a non-placeholder constant, and ``is not``/``!=``
#: against a placeholder, are true only for a real value; ``is``/``==``
#: against a placeholder is false only for one.  ``name != "ok"`` holds for
#: ``None`` too and proves nothing either way.
_EQUALITY_OPS = (ast.Is, ast.Eq)
_INEQUALITY_OPS = (ast.IsNot, ast.NotEq)


def _comparison_polarity(node: ast.AST, name: str) -> bool | None:
    """What a comparison of *name* against constants proves about it.

    ``True`` when the comparison being true proves *name* is not a
    placeholder (``name is not None``, ``name != ""``, ``name == "ok"``,
    ``name is True``), ``False`` when its being false proves it
    (``name is None``, ``name == ""``), ``None`` for any other node.
    """
    if not (
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == name
        and all(isinstance(c, ast.Constant) for c in node.comparators)
    ):
        return None
    if not all(_is_placeholder(right) for right in node.comparators):
        if all(isinstance(op, _EQUALITY_OPS) for op in node.ops):
            return True
        return None
    if all(isinstance(op, _INEQUALITY_OPS) for op in node.ops):
        return True
    if all(isinstance(op, _EQUALITY_OPS) for op in node.ops):
        return False
    return None


def _truth_proves_real(test: ast.expr, name: str) -> bool:
    """True when *test* can be true only if *name* is not a placeholder."""
    if isinstance(test, ast.Name):
        return test.id == name
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _falsity_proves_real(test.operand, name)
    if isinstance(test, ast.BoolOp):
        proved = [_truth_proves_real(value, name) for value in test.values]
        # ``a and x`` is true only when ``x`` is, so one operand testing the
        # name is enough; ``a or x`` is true when ``a`` alone is, so every
        # operand must test it or the body can still see the placeholder.
        return any(proved) if isinstance(test.op, ast.And) else all(proved)
    return _comparison_polarity(test, name) is True


def _falsity_proves_real(test: ast.expr, name: str) -> bool:
    """True when *test* can be false only if *name* is not a placeholder."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _truth_proves_real(test.operand, name)
    if isinstance(test, ast.BoolOp):
        proved = [_falsity_proves_real(value, name) for value in test.values]
        # ``a or x`` is false only when ``x`` is; ``a and x`` is false when
        # ``a`` alone is.
        return any(proved) if isinstance(test.op, ast.Or) else all(proved)
    return _comparison_polarity(test, name) is False


def _guards_name(node: ast.AST, name: str) -> bool:
    """True when *node* defends every read of *name* that follows it.

    ``if``, ``while`` and the conditional expression are decided by
    :func:`_guarded_arms` instead, since one of their arms is not defended,
    and a boolean operator by :func:`_first_event_in_operands`.  A bare
    comparison is not a guard on its own: what it proves depends on the
    outcome the enclosing test acts on, so ``assert x is None`` and
    ``if x is None and flag:`` defend nothing.
    """
    if isinstance(node, ast.Assert):
        return _truth_proves_real(node.test, name)
    if isinstance(node, ast.comprehension):
        return any(_truth_proves_real(test, name) for test in node.ifs)
    if isinstance(node, ast.match_case) and node.guard is not None:
        return _truth_proves_real(node.guard, name)
    return False


def _guarded_arms(node: ast.AST, name: str) -> Sequence[ast.AST] | None:
    """The arm a guarding ``if``/``while``/ternary leaves undefended.

    ``None`` when *node* is not one of them or its test does not guard
    *name*.  ``if x:`` defends its body and leaves the ``else`` — where *x*
    is falsy, maybe the placeholder — undefended; ``if x is None:`` the
    reverse.  Either way the statement guards the reads after it.
    """
    if not isinstance(node, (ast.If, ast.While, ast.IfExp)):
        return None
    body = node.body if isinstance(node.body, list) else [node.body]
    orelse = node.orelse if isinstance(node.orelse, list) else [node.orelse]
    if _truth_proves_real(node.test, name):
        return orelse
    if _falsity_proves_real(node.test, name):
        return body
    return None


#: Expressions that carry a name into a call argument without being one.
#: #3038's own code is ``post_to_trigger(..., body={"invite_id": invite_id})``,
#: so a dict, a list, a tuple, a set, a star-unpack or an f-string argument is
#: descended into rather than skipped.
_ARGUMENT_CONTAINERS = (
    ast.Dict,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Starred,
    ast.JoinedStr,
    ast.FormattedValue,
)


def _passed_names(argument: ast.expr) -> set[str]:
    """Names *argument* carries into the call, inside a container or not.

    A nested call is not descended into: the walk visits it on its own, and
    its arguments are read as that call's, not this one's.
    """
    if isinstance(argument, ast.Name):
        return {argument.id}
    if not isinstance(argument, _ARGUMENT_CONTAINERS):
        return set()
    names: set[str] = set()
    for child in ast.iter_child_nodes(argument):
        if isinstance(child, ast.expr):
            names |= _passed_names(child)
    return names


def _call_argument_names(call: ast.Call) -> set[str]:
    """Names *call* receives as a positional, starred or keyword argument."""
    names: set[str] = set()
    for argument in (*call.args, *(kw.value for kw in call.keywords)):
        names |= _passed_names(argument)
    return names


def _reads_name(node: ast.AST, name: str) -> bool:
    """True when *node* passes *name* to a call, or indexes into it.

    These are the shapes that turn a placeholder into a failure blamed on the
    wrong step: the step posts the placeholder as a trigger body, iterates or
    calls it, or it raises ``AttributeError`` / ``TypeError`` on ``None``.  A
    bare ``return name`` is not one of them — that is the documented
    ``Optional[T]`` contract, and the caller carries the guard.
    """
    if isinstance(node, (ast.Attribute, ast.Subscript)):
        return isinstance(node.value, ast.Name) and node.value.id == name
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return isinstance(node.iter, ast.Name) and node.iter.id == name
    if isinstance(node, _COMPREHENSIONS):
        # Keyed on the comprehension expression, not its ``for`` clause: the
        # clause carries no line number, so a site built from it would report
        # "line 0".  The outermost iterable runs in the enclosing scope and
        # before every ``if`` clause, so a guard there cannot defend it.
        return any(
            isinstance(gen.iter, ast.Name) and gen.iter.id == name
            for gen in node.generators
        )
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == name:
            return True
        return name in _call_argument_names(node)
    return False


def _evaluated_before_binding(node: ast.AST) -> list[ast.AST]:
    """Sub-expressions *node* evaluates before it rebinds its target.

    A loop body runs *after* the loop variable is rebound, so a read in it is
    not a read of the sentinel; the iterable is evaluated before, so one there
    is.
    """
    if isinstance(
        node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)
    ):
        return [node.value] if node.value is not None else []
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.iter]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [item.context_expr for item in node.items]
    return []


#: Comprehension nodes, whose ``for``/``if`` clauses run before the element
#: expression although the element comes first in field order.
_COMPREHENSIONS = (
    ast.ListComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.DictComp,
)


def _binds_in_own_scope(node: ast.AST, name: str) -> bool:
    """True when *node* is an expression scope that binds *name* itself.

    A ``lambda`` parameter and a comprehension's ``for`` target are local to
    that expression, so a mention of *name* inside it is a different variable
    and neither reads nor guards the sentinel.  Treated like the nested
    ``def`` in :data:`_SCOPE_TYPES`: not followed.  Kept out of that tuple so
    the unbound check's own scope rule is unchanged.
    """
    if isinstance(node, ast.Lambda):
        return any(arg.arg == name for arg in _corpus.parameters_of(node))
    if isinstance(node, _COMPREHENSIONS):
        return any(name in _store_names(gen.target) for gen in node.generators)
    return False


def _in_evaluation_order(node: ast.AST) -> list[ast.AST]:
    """*node*'s children in evaluation order.

    Field order is evaluation order for every statement and expression the
    demo tree writes, except a comprehension: its generators and their ``if``
    clauses run before the element it yields.
    """
    children = list(ast.iter_child_nodes(node))
    if not isinstance(node, _COMPREHENSIONS):
        return children
    clauses = [c for c in children if isinstance(c, ast.comprehension)]
    return [*clauses, *[c for c in children if c not in clauses]]


def _first_event(node: ast.AST, name: str) -> tuple[str, int] | None:
    """The first guard, rebinding or unguarded read of *name* in *node*.

    A depth-first walk in evaluation order.  ``("safe", line)`` for a guard or
    a rebinding, ``("read", line)`` for an unguarded read, ``None`` when
    *node* neither guards nor reads *name*.
    """
    if isinstance(node, _SCOPE_TYPES) or _binds_in_own_scope(node, name):
        return None
    if _guards_name(node, name):
        return "safe", _corpus.node_line(node)
    undefended = _guarded_arms(node, name)
    if undefended is not None:
        event = _first_event_in(undefended, name)
        if event is not None and event[0] == "read":
            return event
        return "safe", _corpus.node_line(node)
    if name in _rebound_names(node):
        # What the statement evaluates before binding still reads the old
        # value; everything after the binding reads the new one.
        for child in _evaluated_before_binding(node):
            event = _first_event(child, name)
            if event is not None and event[0] == "read":
                return event
        return "safe", _corpus.node_line(node)
    if _reads_name(node, name):
        return "read", _corpus.node_line(node)
    return _first_event_in_parts(node, name)


def _first_event_in_parts(node: ast.AST, name: str) -> tuple[str, int] | None:
    """:func:`_first_event` for a node that is not itself an event: its
    parts, in the order and on the paths they run."""
    if isinstance(node, ast.BoolOp):
        return _first_event_in_operands(node, name)
    split = _control_flow_split(node)
    if split is not None:
        return _first_event_across_branches(split, name)
    return _first_event_in(_in_evaluation_order(node), name)


def _first_event_in_operands(
    node: ast.BoolOp, name: str
) -> tuple[str, int] | None:
    """:func:`_first_event` for a boolean operator, which short-circuits.

    Only the first operand always runs, so only its rebinding decides for
    what follows the expression; a later operand's read still counts.  An
    operand that proves *name* real on the way to the next one — true in an
    ``and`` chain, false in an ``or`` chain — defends the operands after it,
    but nothing past the expression, which may have stopped at either outcome.
    """
    proves_real = (
        _truth_proves_real
        if isinstance(node.op, ast.And)
        else _falsity_proves_real
    )
    for index, value in enumerate(node.values):
        event = _first_event(value, name)
        if event is not None and (event[0] == "read" or index == 0):
            return event
        if event is not None or proves_real(value, name):
            return None
    return None


def _first_event_across_branches(
    split: "_Split", name: str
) -> tuple[str, int] | None:
    """:func:`_first_event` for a statement split by
    :func:`_control_flow_split`.

    A branch may not run: its read counts, but its guard or rebinding cannot
    decide for what follows the statement — unless the branches are
    exhaustive and every one of them either decides it or leaves the
    statement (:func:`_leaves`), or the statement is a loop every exit of
    which decides it (:func:`_loop_decides`).
    """
    event = _first_event_in(split.head, name)
    if event is not None:
        return event
    decided: list[tuple[str, int]] = []
    open_branches = 0
    for branch in split.branches:
        event = _first_event_in(branch, name)
        if event is not None and event[0] == "read":
            return event
        if event is not None:
            decided.append(event)
        elif not _leaves(branch):
            open_branches += 1
    if split.exhaustive and decided and not open_branches:
        return decided[0]
    if split.loop is not None and _loop_decides(split.loop, name):
        return "safe", _corpus.node_line(split.loop)
    return _first_event_in(split.tail, name)


#: Statements after which nothing more of their statement list runs.
_EXITS = (ast.Raise, ast.Return, ast.Break, ast.Continue)


def _leaves(branch: Sequence[ast.AST]) -> bool:
    """True when *branch* never runs on past the statement it belongs to.

    It ends in ``raise``, ``return``, ``break`` or ``continue``, or in an
    ``if``/``else`` both of whose arms do.  An ``except`` arm or a ``match``
    case is judged by its body.
    """
    if not branch:
        return False
    last = branch[-1]
    if isinstance(last, (ast.ExceptHandler, ast.match_case)):
        return _leaves(last.body)
    if isinstance(last, ast.If):
        return _leaves(last.body) and _leaves(last.orelse)
    return isinstance(last, _EXITS)


def _is_endless(loop: ast.While | ast.For | ast.AsyncFor) -> bool:
    """True for ``while True:``, which ends only through a ``break``."""
    return (
        isinstance(loop, ast.While)
        and isinstance(loop.test, ast.Constant)
        and bool(loop.test.value)
    )


def _loop_decides(loop: ast.While | ast.For | ast.AsyncFor, name: str) -> bool:
    """True when every way out of *loop* guards or rebinds *name*.

    A loop ends through a ``break``, after which its ``else`` arm is skipped,
    or by running out, after which the ``else`` arm runs; ``while True:``
    never runs out.  So each ``break`` must follow a guard or rebinding on its
    path, and the ``else`` arm must decide the name or leave, unless the loop
    is endless.
    """
    if not _is_endless(loop):
        event = _first_event_in(loop.orelse, name)
        decided = event is not None and event[0] == "safe"
        if not (decided or _leaves(loop.orelse)):
            return False
    return _breaks_are_decided(loop.body, name, False)


def _breaks_are_decided(
    stmts: Sequence[ast.stmt], name: str, decided: bool
) -> bool:
    """True when each ``break`` in *stmts* that leaves the enclosing loop is
    reached only after a guard or rebinding of *name*.

    *decided* says whether one already ran on the way into *stmts*.  A
    ``break`` inside a nested loop's body leaves that loop instead, so only
    the nested loop's ``else`` arm is followed.
    """
    for stmt in stmts:
        if isinstance(stmt, ast.Break):
            return decided
        for body, entering in _break_paths(stmt, name, decided):
            if not _breaks_are_decided(body, name, entering):
                return False
        if not decided:
            event = _first_event(stmt, name)
            decided = event is not None and event[0] == "safe"
    return True


def _break_paths(
    stmt: ast.stmt, name: str, decided: bool
) -> list[tuple[list[ast.stmt], bool]]:
    """Statement lists in *stmt* whose ``break`` leaves the enclosing loop,
    each with whether *name* is decided on entering it.

    An ``if`` whose test proves the name real on entering an arm decides it
    there, as ``if offer: break`` does.
    """
    if isinstance(stmt, (ast.While, ast.For, ast.AsyncFor)):
        return [(stmt.orelse, decided)]
    if isinstance(stmt, ast.If):
        return [
            (stmt.body, decided or _truth_proves_real(stmt.test, name)),
            (stmt.orelse, decided or _falsity_proves_real(stmt.test, name)),
        ]
    return [(nested.body, decided) for nested in _nested_blocks(stmt)]


def _first_event_in(
    nodes: Sequence[ast.AST], name: str
) -> tuple[str, int] | None:
    """The first deciding event of :func:`_first_event` across *nodes*."""
    for node in nodes:
        event = _first_event(node, name)
        if event is not None:
            return event
    return None


class _Split(NamedTuple):
    """A compound statement split by :func:`_control_flow_split`.

    *head* is evaluated before any branch and *tail* after every one — both
    always run — while each *branch* may not run at all.  *exhaustive* holds
    when one branch always runs to its end or nothing after the statement
    runs: an ``if`` with an ``else``, a ``match`` ending in an irrefutable
    case, a ``try`` and its handlers.  *loop* is the statement itself when it
    is a loop, whose exits :func:`_loop_decides` judges instead.
    """

    head: Sequence[ast.AST]
    branches: Sequence[Sequence[ast.AST]]
    tail: Sequence[ast.AST] = ()
    exhaustive: bool = False
    loop: ast.While | ast.For | ast.AsyncFor | None = None


def _is_irrefutable(case: ast.match_case) -> bool:
    """True for ``case _:`` or a bare capture, with no guard."""
    pattern = case.pattern
    return (
        case.guard is None
        and isinstance(pattern, ast.MatchAs)
        and pattern.pattern is None
    )


def _control_flow_split(node: ast.AST) -> _Split | None:
    """Split a compound statement into what always runs and what may not.

    ``None`` for a node whose children all run, such as an unguarded
    ``with``, whose body's exception propagates past every later read anyway.
    A guarded block's body is a branch: the block swallows the failure that
    skips the rest of it (#5904).  So is a ``try`` body with a handler, which
    may catch a failure halfway through it; with only a ``finally`` the
    failure propagates, so the body always runs to its end or past every
    later read.  An ``except`` arm and a ``match`` case are split whole, so
    their ``as`` binding, capture pattern and case guard are seen.
    """
    if isinstance(node, ast.If):
        return _Split(
            [node.test], [node.body, node.orelse], (), bool(node.orelse)
        )
    if isinstance(node, ast.While):
        return _Split([node.test], [node.body, node.orelse], loop=node)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return _Split(
            [node.iter, node.target], [node.body, node.orelse], loop=node
        )
    if _is_guarded_block(node):
        return _Split(node.items, [node.body])
    if isinstance(node, (ast.Try, ast.TryStar)):
        if not node.handlers:
            return _Split([*node.body, *node.orelse], [], node.finalbody)
        # ``else`` runs only after the body completes, so the two are one
        # path; a failure partway through takes a handler's path instead, or
        # propagates past every later read.
        handlers = [[handler] for handler in node.handlers]
        happy_path = [*node.body, *node.orelse]
        return _Split([], [happy_path, *handlers], node.finalbody, True)
    if isinstance(node, ast.Match):
        cases = [[case] for case in node.cases]
        exhaustive = bool(node.cases) and _is_irrefutable(node.cases[-1])
        return _Split([node.subject], cases, (), exhaustive)
    return None


def _first_unguarded_read(stmts: Sequence[ast.AST], name: str) -> int | None:
    """Line of the first unguarded read of *name* in *stmts*, else ``None``.

    The first guard, rebinding or read in evaluation order decides: a guard
    that does not itself enclose a later read still defends it.  That leniency is
    deliberate — it keeps the check free of false positives on the
    early-return shape ``if x is None: return`` — and
    :func:`test_a_guard_defends_reads_it_does_not_enclose` pins it.  It holds
    only at the statement level of *stmts*: a guard or rebinding inside a
    branch that may not run decides nothing past that branch (#5904).
    """
    event = _first_event_in(stmts, name)
    if event is None or event[0] != "read":
        return None
    return event[1]


class _NestedBlock(NamedTuple):
    """A statement list nested in a compound statement.

    *then* is what runs after *body* before the statement's own successors:
    the ``else`` and ``finally`` arms of a ``try`` — or, when it has
    handlers, the ``try``'s other arms, since a later failure in the body
    takes a handler's path — and for a loop its test and body again, whose
    next pass reads what this one left (#5904).  *rebinds* names the
    statement binds before *body* runs, such as a ``for`` target, so none of
    them holds a placeholder inside it.
    """

    body: list[ast.stmt]
    then: Sequence[ast.AST]
    rebinds: frozenset[str] = frozenset()


def _after_try_body(stmt: ast.Try | ast.TryStar) -> list[ast.AST]:
    """What runs after a statement in *stmt*'s body: the rest of the body
    is the caller's, then the ``else`` arm or a handler, then ``finally``.

    With handlers, the choice between ``else`` and a handler is kept as one
    ``try`` with an empty body, so :func:`_control_flow_split` treats them as
    the alternative paths they are.
    """
    if not stmt.handlers:
        return [*stmt.orelse, *stmt.finalbody]
    alternatives = type(stmt)(
        body=[],
        handlers=stmt.handlers,
        orelse=stmt.orelse,
        finalbody=stmt.finalbody,
    )
    return [ast.copy_location(alternatives, stmt)]


def _nested_blocks(stmt: ast.stmt) -> Iterator[_NestedBlock]:
    """Statement lists nested directly in *stmt*, within the same scope."""
    if isinstance(stmt, _SCOPE_TYPES):
        return
    if isinstance(stmt, ast.If):
        yield _NestedBlock(stmt.body, [])
        yield _NestedBlock(stmt.orelse, [])
    elif isinstance(stmt, ast.While):
        again = [stmt.test, *stmt.body, *stmt.orelse]
        yield _NestedBlock(stmt.body, again)
        yield _NestedBlock(stmt.orelse, [])
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        target = frozenset(_store_names(stmt.target))
        yield _NestedBlock(stmt.body, [*stmt.body, *stmt.orelse], target)
        yield _NestedBlock(stmt.orelse, [])
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        yield _NestedBlock(stmt.body, [], frozenset(_rebound_names(stmt)))
    elif isinstance(stmt, (ast.Try, ast.TryStar)):
        yield _NestedBlock(stmt.body, _after_try_body(stmt))
        for handler in stmt.handlers:
            yield _NestedBlock(handler.body, stmt.finalbody)
        yield _NestedBlock(stmt.orelse, stmt.finalbody)
        yield _NestedBlock(stmt.finalbody, [])
    elif isinstance(stmt, ast.Match):
        for case in stmt.cases:
            yield _NestedBlock(case.body, [])


def _sites_for_block(
    block: ast.With,
    sentinels: dict[str, int],
    following: Sequence[ast.AST],
) -> list[SentinelSite]:
    """A site per tracked sentinel the guarded *block* itself assigns."""
    written = _assigned_by_block_itself(block.body) & set(sentinels)
    return [
        SentinelSite(
            sentinels[name],
            name,
            block.lineno,
            _first_unguarded_read(following, name),
        )
        for name in sorted(written)
    ]


def _sentinel_sites_in_stmts(stmts: list[ast.stmt]) -> list[SentinelSite]:
    """Every placeholder sentinel a guarded block in *stmts* assigns."""
    return _scan_for_sentinels(stmts, {}, ())[0]


def _scan_for_sentinels(
    stmts: list[ast.stmt],
    inherited: dict[str, int],
    trailing: Sequence[ast.AST],
) -> tuple[list[SentinelSite], dict[str, int]]:
    """Sites in *stmts*, and the sentinels still held once *stmts* end.

    Walks the statement list left to right, tracking which names currently
    hold a placeholder pre-initialisation, and records a site for each one a
    guarded block then assigns.  *inherited* carries the names an enclosing
    statement left holding a placeholder and *trailing* the statements that
    run after *stmts*, so a producing block nested in an ``if``, ``for``,
    ``try`` or another guarded block is seen, and a read after the enclosing
    statement counts (#3038).  A pre-initialisation inside a nested statement
    list still holds after it, so it is carried out to this level (#5904).
    """
    sites: list[SentinelSite] = []
    sentinels = dict(inherited)

    for index, stmt in enumerate(stmts):
        following: list[ast.AST] = [*stmts[index + 1 :], *trailing]

        preinit = _placeholder_preinit_names(stmt)
        if preinit:
            sentinels.update(dict.fromkeys(preinit, stmt.lineno))
            continue

        if _is_guarded_block(stmt):
            # ``__enter__`` binds the ``as`` target before the body runs.
            for name in _rebound_names(stmt):
                sentinels.pop(name, None)
            sites += _sites_for_block(stmt, sentinels, following)

        carried: dict[str, int] = {}
        for nested in _nested_blocks(stmt):
            entering = {
                name: line
                for name, line in sentinels.items()
                if name not in nested.rebinds
            }
            nested_sites, leaving = _scan_for_sentinels(
                nested.body, entering, [*nested.then, *following]
            )
            sites += nested_sites
            carried.update(
                (name, line)
                for name, line in leaving.items()
                if entering.get(name) != line
            )

        for name in _rebound_names(stmt):
            sentinels.pop(name, None)
        sentinels.update(carried)

    return sites, sentinels


def _sentinel_sites_in_tree(
    tree: ast.AST, path: pathlib.Path
) -> list[tuple[pathlib.Path, SentinelSite]]:
    """Sentinel sites in every function defined in an already-parsed tree."""
    found: list[tuple[pathlib.Path, SentinelSite]] = []

    class _V(ast.NodeVisitor):
        def _scan(self, body: list[ast.stmt]) -> None:
            found.extend(
                (path, site) for site in _sentinel_sites_in_stmts(body)
            )

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._scan(node.body)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._scan(node.body)
            self.generic_visit(node)

    _V().visit(tree)
    return found


@functools.cache
def _demo_modules() -> tuple[tuple[pathlib.Path, ast.AST], ...]:
    """Every cached demo module mentioning a guarded context manager.

    The one subject set both checks scan, so the non-empty guard below covers
    both and neither can narrow without the other noticing (TB-13-002).
    """
    return tuple(
        _corpus.files_mentioning(*sorted(_GUARDED_CMS), under=DEMO_DIR)
    )


@functools.cache
def _demo_sentinel_sites() -> tuple[tuple[pathlib.Path, SentinelSite], ...]:
    """Every sentinel site in the demo tree, derived once per process."""
    sites: list[tuple[pathlib.Path, SentinelSite]] = []
    with _corpus.gc_paused():
        for py_file, tree in _demo_modules():
            sites.extend(_sentinel_sites_in_tree(tree, py_file))
    return tuple(sites)


def _sentinel_sites(src: str) -> list[SentinelSite]:
    """Sentinel sites in every function defined in the inline source *src*."""
    tree = _corpus.parse_inline(src)
    inline = pathlib.Path("<inline>")
    return [site for _, site in _sentinel_sites_in_tree(tree, inline)]


def _sentinel_leaks(src: str) -> list[tuple[str, int | None]]:
    """``(name, read line)`` for each #3038 leak in the inline source *src*."""
    return [
        (site.name, site.read)
        for site in _sentinel_sites(src)
        if site.read is not None
    ]


# ---------------------------------------------------------------------------
# The ratchet test
# ---------------------------------------------------------------------------


def _parse_function_body(src: str) -> list:
    """Return the body of the first function defined in *src*."""
    tree = _corpus.parse_inline(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.body
    raise ValueError("no function found")


# ---------------------------------------------------------------------------
# Unit tests for helpers (#2386 and #2387)
# ---------------------------------------------------------------------------


def test_load_names_does_not_cross_nested_functiondef():
    """_load_names must not collect names from nested FunctionDef bodies.

    A variable assigned only in a nested function is a distinct binding;
    it must not cause a false positive for the enclosing scope (#2386).
    """
    stmts = _parse_function_body("""
def outer():
    def inner():
        report = make_inner_report()
        use(report)

    outer_call(other)
""")
    # 'report' appears only inside the nested def body — must not be returned
    names = _load_names(stmts)
    assert "report" not in names, (
        "_load_names crossed into nested FunctionDef and found 'report'"
    )
    # 'other' is in the outer scope and must be returned
    assert "other" in names


def test_load_names_does_not_cross_nested_asyncfunctiondef():
    """_load_names must not collect names from nested AsyncFunctionDef bodies (#2386)."""
    stmts = _parse_function_body("""
def outer():
    async def inner():
        result = compute()
        use(result)

    outer_call(x)
""")
    names = _load_names(stmts)
    assert "result" not in names
    assert "x" in names


def test_load_names_does_not_cross_nested_classdef():
    """_load_names must not collect names from nested ClassDef bodies (#2386)."""
    stmts = _parse_function_body("""
def outer():
    class Inner:
        value = compute()

    outer_call(y)
""")
    names = _load_names(stmts)
    assert "value" not in names
    assert "y" in names


def test_undefended_no_false_positive_nested_def_same_name(tmp_path):
    """Nested function with same-named local must not produce false positive (#2386).

    'report' is assigned in the demo_step block and also in a nested function's
    body. Because the nested function is a separate scope, the outer function
    should NOT be flagged.
    """
    src = """\
def outer():
    with demo_step("Step"):
        report = get_report()

    def inner():
        report = make_inner_report()
        use(report)
"""
    path = tmp_path / "demo_outer.py"
    path.write_text(src)
    found = _violations_in_file(path)
    assert found == [], f"False positive for nested-def same-name: {found}"


def test_undefended_no_false_positive_optional_vars_also_in_body(tmp_path):
    """as-binding plus body re-assignment must not produce false positive (#2387).

    'ctx' is bound by demo_step.__enter__ AND reassigned in the block body.
    Because __enter__ fires before the body, 'ctx' is always bound; the ratchet
    must not flag it.
    """
    src = """\
def example():
    with demo_step("Step") as ctx:
        ctx = transform(ctx)
    use(ctx)
"""
    path = tmp_path / "demo_example.py"
    path.write_text(src)
    found = _violations_in_file(path)
    assert found == [], (
        f"False positive for optional_vars re-assignment in body: {found}"
    )


def test_undefended_still_catches_real_undefended_after_fixes(tmp_path):
    """After both fixes, genuine undefended variables must still be flagged."""
    src = """\
def bad():
    with demo_step("Step"):
        result = compute()
    use(result)
"""
    path = tmp_path / "demo_bad.py"
    path.write_text(src)
    found = _violations_in_file(path)
    vars_found = [v for _, _, v in found]
    assert "result" in vars_found, (
        "Real undefended 'result' was not detected after fixes"
    )


def test_no_undefended_demo_step_vars():
    """No demo_step/demo_check/demo_gate block may leave a variable unbound (#2308).

    Every variable whose first assignment lives inside a ``demo_step``,
    ``demo_check`` or ``demo_gate`` block body *and* is read after the block
    closes is a defect: nest the reader inside the block (preferred), or
    pre-initialize the name to a sentinel and ``None``-guard every later read.
    """
    violations = []
    for py_file, tree in _demo_modules():
        for fpath, lineno, var in _violations_in_tree(tree, py_file):
            rel = fpath.relative_to(_corpus.REPO_ROOT)
            violations.append(f"{rel}:{lineno}: undefended var '{var}'")

    assert violations == [], (
        "Variables assigned only inside demo_step/demo_check/demo_gate blocks "
        "and read afterward without prior initialization (issue #2308):\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Unit tests for the placeholder-sentinel check (#3038)
# ---------------------------------------------------------------------------


def test_sentinel_passed_to_a_later_call_is_a_leak():
    """The #3038 shape: a sentinel posted by a later step (#3038)."""
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    with demo_step("Step 2: consume"):
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 7)]


def test_sentinel_attribute_read_after_the_block_is_a_leak():
    """An attribute read of the sentinel raises on ``None``."""
    src = """\
def example():
    case = None
    with demo_gate("the case exists"):
        case = find_case()

    log(case.id_)
"""
    assert _sentinel_leaks(src) == [("case", 6)]


def test_sentinel_written_in_a_nested_block_is_a_leak():
    """A sentinel assigned inside a nested ``demo_check`` is still unwritten.

    The enclosing block can raise before the nested one runs, so the shallow
    test the unbound check uses is too narrow here.
    """
    src = """\
def example():
    report = None
    with demo_step("Step 1: produce"):
        with demo_check("the report landed"):
            report = find_report()

    with demo_step("Step 2: consume"):
        validate(report)
"""
    assert _sentinel_leaks(src) == [("report", 8)]


def test_chained_none_preinit_reports_each_name():
    """``a = b = None`` pre-initialises both names."""
    src = """\
def example():
    report = offer = None
    with demo_step("Step 1: produce"):
        report, offer = submit_report()

    consume(offer)
    consume(report)
"""
    assert _sentinel_leaks(src) == [("offer", 6), ("report", 7)]


def test_annotated_none_preinit_is_a_sentinel():
    """``x: T | None = None`` is the same sentinel as ``x = None``."""
    src = """\
def example():
    invite_id: str | None = None
    with demo_gate("the invite arrived"):
        invite_id = find_invite()

    answer(invite_id)
"""
    assert _sentinel_leaks(src) == [("invite_id", 6)]


def test_is_none_guard_before_the_read_defends_it():
    """The ``Optional[T]`` contract: an ``is None`` guard makes the read safe."""
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    with demo_gate("Step 1 produced the offer"):
        if offer is None:
            raise AssertionError("no offer; recorded above")
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_is_not_none_test_around_the_read_defends_it():
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    if offer is not None:
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_truthiness_test_around_the_read_defends_it():
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    if offer:
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_assert_before_the_read_defends_it():
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    with demo_gate("Step 1 produced the offer"):
        assert offer, "no offer; recorded above"
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_nested_reader_is_the_preferred_fix_and_is_not_a_leak():
    """The nested-block model (ADR-0058) leaves nothing to read after."""
    src = """\
def example():
    with demo_step("Step 1: produce"):
        offer = submit_report()

        with demo_step("Step 2: consume"):
            acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []
    assert _sentinel_sites(src) == []


def test_rebinding_after_the_block_ends_the_sentinel():
    """A name reassigned outside the block no longer holds the sentinel."""
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    offer = fallback_offer()
    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_read_in_a_nested_function_is_a_separate_scope():
    """A nested ``def`` binds its own name, so it is not this scope's read."""
    src = """\
def outer():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    def inner(offer):
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_empty_string_preinit_is_a_sentinel():
    """``invite_id = ""`` is the same defect as ``invite_id = None`` (#3038).

    An id or activity reference is never legitimately the empty string, so the
    next step posts ``invite_id: ""`` and fails for the wrong reason.
    """
    src = """\
def example():
    invite_id = ""
    with demo_step("Step 1: invite"):
        invite_id = invite_actor()

    with demo_step("Step 2: accept"):
        accept_invite(invite_id=invite_id)
"""
    assert _sentinel_leaks(src) == [("invite_id", 7)]


def test_empty_string_comparison_guard_defends_the_read():
    src = """\
def example():
    invite_id = ""
    with demo_step("Step 1: invite"):
        invite_id = invite_actor()

    if invite_id == "":
        raise AssertionError("no invite; recorded above")
    accept_invite(invite_id=invite_id)
"""
    assert _sentinel_leaks(src) == []


def test_preinit_to_zero_or_an_empty_collection_is_not_a_sentinel():
    """Only ``None`` and ``""`` are placeholders.

    A count of zero and an empty accumulator are values a later step may
    legitimately read, so flagging them would report working code.
    """
    for preinit in ("[]", "0", "{}", "set()"):
        src = f"""\
def example():
    offers = {preinit}
    with demo_step("Step 1: produce"):
        offers = submit_reports()

    acknowledge(offers)
"""
        assert _sentinel_sites(src) == [], preinit


def test_loop_variable_rebound_by_a_later_for_is_not_a_leak():
    """A loop body runs after the loop variable is rebound.

    ``label = client = None`` before a block that loops over the same names is
    the shape ``helpers/seeding/reset.py`` uses; a read inside a later loop's
    body reads that loop's value, not the placeholder.
    """
    src = """\
def example():
    label = client = None
    with demo_step("Reset the containers"):
        for label, client in targets:
            reset(client=client)

    with demo_check("Containers are clean"):
        for label, client in targets:
            verify(label, client)
"""
    assert _sentinel_leaks(src) == []


@pytest.mark.parametrize(
    "iterable",
    [
        pytest.param("targets", id="bare-name"),
        pytest.param("sorted(targets)", id="inside-a-call"),
    ],
)
def test_read_in_the_iterable_of_a_later_for_is_a_leak(iterable: str):
    """The iterable *is* evaluated before the loop variable is rebound.

    Both forms must count.  A bare name is reached only by the ``For.iter``
    arm of :func:`_reads_name`; wrapping it in a call would otherwise be the
    only shape the check saw, and iterating ``None`` raises just the same.
    """
    src = f"""\
def example():
    targets = None
    with demo_step("Resolve the targets"):
        targets = resolve()

    for client in {iterable}:
        reset(client)
"""
    assert _sentinel_leaks(src) == [("targets", 6)]


def test_sentinel_inside_a_nested_statement_block_is_found():
    """A site inside an ``if`` or ``for`` body is scanned too."""
    src = """\
def example(flag):
    if flag:
        offer = None
        with demo_step("Step 1: produce"):
            offer = submit_report()

        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 7)]


def test_unguarded_block_is_not_the_sentinel_check_business():
    """A ``with`` that is not a demo context manager gates nothing."""
    src = """\
def example():
    offer = None
    with open("x") as handle:
        offer = read_offer(handle)

    acknowledge(offer)
"""
    assert _sentinel_sites(src) == []


def test_guarded_site_is_still_a_subject():
    """A defended sentinel is recorded, so the subject arm can count it."""
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    if offer is not None:
        acknowledge(offer)
"""
    assert _sentinel_sites(src) == [SentinelSite(2, "offer", 3, None)]


def test_sentinel_in_a_trigger_body_dict_is_a_leak():
    """#3038's own shape: the placeholder inside the posted body.

    ``post_to_trigger(..., body={"invite_id": invite_id})`` is the line the
    issue quotes, so a container argument is descended into.
    """
    src = """\
def example():
    invite_id = None
    with demo_gate("the invite arrived"):
        invite_id = find_invite()

    post_to_trigger(session, body={"invite_id": invite_id})
"""
    assert _sentinel_leaks(src) == [("invite_id", 6)]


def test_sentinel_in_an_fstring_argument_is_a_leak():
    src = """\
def example():
    case_id = None
    with demo_step("Step 1: create the case"):
        case_id = create_case()

    get(f"/api/v2/cases/{case_id}")
"""
    assert _sentinel_leaks(src) == [("case_id", 6)]


def test_sentinel_in_a_list_argument_is_a_leak():
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    announce(to=[offer])
"""
    assert _sentinel_leaks(src) == [("offer", 6)]


def test_sentinel_subscripted_after_the_block_is_a_leak():
    """``offer["id"]`` raises ``TypeError`` on ``None`` just as an attribute
    read does."""
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    log(offer["id"])
"""
    assert _sentinel_leaks(src) == [("offer", 6)]


def test_bare_return_of_the_sentinel_is_not_a_leak():
    """Returning the sentinel is the ``Optional[T]`` contract, not a read.

    The caller carries the guard, as ``invite_and_await_delivery`` in
    ``vultron/demo/helpers/invite_chain/chain.py`` does.
    """
    src = """\
def example():
    delivered = None
    with demo_gate("the invite was delivered"):
        delivered = find_invite()

    return delivered
"""
    assert _sentinel_leaks(src) == []


def test_name_inside_a_nested_call_counts_for_that_call():
    """A name in an inner call is that call's argument, and still a read.

    The outer call is split across lines so the two ``ast.Call`` nodes have
    different ``lineno``s: on one line the assertion would hold whether or not
    :func:`_passed_names` declined to descend into the nested call, which is
    the behaviour this pins.
    """
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    logger.info(
        "offer: %s",
        logfmt(offer),
    )
"""
    assert _sentinel_leaks(src) == [("offer", 8)]


def test_producer_nested_in_an_if_with_an_outer_read_is_a_leak():
    """A producing block one level in still feeds the read after it.

    The pre-initialisation is tracked into the nested block and the
    statements after the enclosing ``if`` count as following it.
    """
    src = """\
def example(flag):
    offer = None
    if flag:
        with demo_step("Step 1: produce"):
            offer = submit_report()

    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 7)]


#: A guarded block producing ``offer``, indented to sit in a ``try`` arm.
_TRY_ARM_PRODUCER = (
    '        with demo_step("Step 1: produce"):\n'
    "            offer = submit_report()\n"
)


def _try_with_producer_in(arm: str) -> str:
    """A ``try`` statement with :data:`_TRY_ARM_PRODUCER` in *arm*.

    *arm* is ``try``, ``except`` or ``else``; the statement has no
    ``finally``, so a caller may append one.
    """
    empty_arm = "        pass\n"
    body = _TRY_ARM_PRODUCER if arm == "try" else empty_arm
    handler = _TRY_ARM_PRODUCER if arm == "except" else empty_arm
    src = f"    try:\n{body}    except ValueError:\n{handler}"
    if arm == "else":
        src += "    else:\n" + _TRY_ARM_PRODUCER
    return src


@pytest.mark.parametrize("arm", ["try", "except", "else", "finally"])
def test_producer_nested_in_try_except_else_finally_is_found(arm: str):
    """Each of the four arms is its own statement list in ``_nested_blocks``.

    Parametrised because a producer in ``try`` alone leaves the other three
    yields unexercised: deleting them would keep such a test green.
    """
    statement = (
        "    try:\n        pass\n    finally:\n" + _TRY_ARM_PRODUCER
        if arm == "finally"
        else _try_with_producer_in(arm)
    )
    src = (
        "def example():\n    offer = None\n"
        + statement
        + "\n    acknowledge(offer)\n"
    )
    leaks = _sentinel_leaks(src)
    assert [name for name, _ in leaks] == ["offer"], (arm, src)


def test_producer_nested_in_a_match_case_is_found():
    src = """\
def example(kind):
    offer = None
    match kind:
        case "report":
            with demo_step("Step 1: produce"):
                offer = submit_report()

    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 8)]


def test_producer_nested_in_a_while_orelse_arm_is_found():
    src = """\
def example(pending):
    offer = None
    while pending:
        pass
    else:
        with demo_step("Step 1: produce"):
            offer = submit_report()

    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 9)]


def test_sentinel_declared_inside_a_guarded_block_is_its_own_subject():
    src = """\
def example():
    with demo_step("Step 1: open"):
        offer = None
        with demo_check("the offer landed"):
            offer = find_offer()

        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 7)]


def test_while_guard_defends_the_read():
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    while offer:
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_conditional_expression_guard_defends_the_read():
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    acknowledge(offer.id_ if offer else None)
"""
    assert _sentinel_leaks(src) == []


def test_comprehension_guard_defends_the_read():
    src = """\
def example(cases):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    announce([link(case, offer) for case in cases if offer])
"""
    assert _sentinel_leaks(src) == []


def test_boolean_operator_truthiness_guard_defends_the_read():
    src = """\
def example(flag):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    if flag and offer:
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_augmented_assignment_ends_the_sentinel():
    src = """\
def example(extra):
    note = ""
    with demo_step("Step 1: produce"):
        note = compose_note()

    note += extra
    publish(note)
"""
    assert _sentinel_leaks(src) == []


def test_with_as_binding_after_the_block_ends_the_sentinel():
    src = """\
def example():
    handle = None
    with demo_step("Step 1: produce"):
        handle = open_handle()

    with open("x") as handle:
        read(handle)
"""
    assert _sentinel_leaks(src) == []


def test_a_guard_defends_reads_it_does_not_enclose():
    """The first guard in source order defends every read after it.

    Deliberate leniency: the ``if x is None: raise`` early-exit shape puts the
    guard beside the reads rather than around them, and treating only
    enclosed reads as defended would report that shape as a defect.
    """
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    if offer:
        log("the offer landed")
    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


@pytest.mark.parametrize(
    ("test", "leaks"),
    [
        pytest.param('offer == "ok"', False, id="eq-constant-guards"),
        pytest.param("offer is True", False, id="is-constant-guards"),
        pytest.param('offer != "ok"', True, id="ne-constant-does-not"),
        pytest.param("offer is not None", False, id="is-not-placeholder"),
        pytest.param("flag and offer", False, id="and-chain-guards"),
        pytest.param("flag or offer", True, id="or-chain-does-not"),
        pytest.param("offer or flag", True, id="or-chain-reversed"),
    ],
)
def test_comparison_and_boolean_guard_forms(test: str, leaks: bool):
    """Only a test that is false for the placeholder defends the read.

    ``offer == "ok"`` proves the name is neither ``None`` nor ``""``, so it is
    a guard; ``offer != "ok"`` holds for ``None`` too, so it is not.  In
    ``flag or offer`` the body runs on ``flag`` alone, so the placeholder
    still reaches the read; in ``flag and offer`` it cannot.
    """
    src = f"""\
def example(flag):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    if {test}:
        acknowledge(offer)
"""
    assert bool(_sentinel_leaks(src)) is leaks


@pytest.mark.parametrize(
    "read",
    [
        pytest.param(
            "for item in offer:\n        use(item)", id="for-iterable"
        ),
        pytest.param("offer()", id="called-as-a-function"),
        pytest.param("xs = [i for i in offer]", id="comprehension-iterable"),
        pytest.param("xs = {i for i in offer}", id="setcomp-iterable"),
        pytest.param("total = sum(i for i in offer)", id="genexp-iterable"),
    ],
)
def test_iterating_or_calling_the_sentinel_is_a_read(read: str):
    """Iterating or calling a placeholder raises just as posting it does.

    The outermost iterable of a comprehension runs in the enclosing scope and
    before every ``if`` clause, so no guard inside the comprehension can
    defend it.
    """
    src = f"""\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    {read}
"""
    assert [name for name, _ in _sentinel_leaks(src)] == ["offer"]


def test_comprehension_rebinding_the_name_is_its_own_scope():
    """A comprehension target is comprehension-local, not the sentinel.

    ``[use(offer) for offer in items]`` reads the comprehension's own
    ``offer``, so reporting it would fail correct code.
    """
    src = """\
def example(items):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    picked = [use(offer) for offer in items]
"""
    assert _sentinel_leaks(src) == []


def test_walrus_rebinding_ends_the_sentinel():
    """``:=`` binds the name to a real value, so later reads are not leaks."""
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    if (offer := fetch_offer()):
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


def test_lambda_parameter_shadowing_the_name_is_its_own_scope():
    """A ``lambda`` parameter is lambda-local, not the sentinel."""
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    render = lambda offer: acknowledge(offer)
    return render
"""
    assert _sentinel_leaks(src) == []


def test_two_blocks_writing_one_sentinel_are_told_apart():
    """Each guarded block gets its own record, keyed on its own line.

    ``vultron/demo/helpers/seeding/reset.py`` pre-initialises two loop
    variables that two sibling blocks then write; without the block line the
    two records would be identical.
    """
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    with demo_step("Step 2: re-produce"):
        offer = submit_report()
"""
    assert _sentinel_sites(src) == [
        SentinelSite(2, "offer", 3, None),
        SentinelSite(2, "offer", 6, None),
    ]


# ---------------------------------------------------------------------------
# Read-window and control-flow gaps (#5904)
# ---------------------------------------------------------------------------


def test_read_inside_the_producer_after_a_nested_block_is_a_leak():
    """The nested-block fix's own shape must stay covered (#5904 gap 1).

    The inner ``demo_check`` swallows its failure, so the rest of the outer
    block runs with the placeholder.
    """
    src = """\
def example():
    offer = None
    with demo_step("outer"):
        with demo_check("inner"):
            offer = submit_report()
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 6)]


def test_read_inside_and_after_the_producer_reports_the_first_one():
    """With a read both inside the outer block and after it, the earlier
    line is the one reported, once (#5904 gap 1)."""
    src = """\
def example():
    offer = None
    with demo_step("outer"):
        with demo_check("inner"):
            offer = submit_report()
        acknowledge(offer)

    publish(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 6)]


def test_inner_block_owns_the_record_for_a_name_only_it_writes():
    """One record per producing block: the outer block writes nothing itself
    for that name, so it adds none (#5904 gap 1)."""
    src = """\
def example():
    offer = None
    with demo_step("outer"):
        with demo_check("inner"):
            offer = submit_report()
"""
    assert _sentinel_sites(src) == [SentinelSite(2, "offer", 4, None)]


def test_outer_block_writing_the_name_itself_keeps_its_record():
    """A rebinding in the outer body can raise too, so the outer block is a
    producer of its own beside the inner one."""
    src = """\
def example():
    offer = None
    with demo_step("outer"):
        with demo_check("inner"):
            offer = submit_report()
        offer = fallback_offer()

    acknowledge(offer)
"""
    assert _sentinel_sites(src) == [
        SentinelSite(2, "offer", 3, 8),
        SentinelSite(2, "offer", 4, None),
    ]


@pytest.mark.parametrize(
    "branch",
    [
        pytest.param(
            "if flag:\n        offer = fallback()", id="if-rebinding"
        ),
        pytest.param(
            "if flag:\n        if offer is None:\n            raise SystemExit",
            id="if-nested-guard",
        ),
        pytest.param(
            "for _ in pending:\n        offer = fallback()", id="for-body"
        ),
        pytest.param(
            "while flag:\n        offer = fallback()", id="while-body"
        ),
        pytest.param(
            "try:\n        offer = fallback()\n    except ValueError:\n"
            "        pass",
            id="try-body",
        ),
        pytest.param(
            "match flag:\n        case 1:\n            offer = fallback()",
            id="match-case",
        ),
        pytest.param(
            'with demo_step("retry"):\n        offer = fallback()',
            id="guarded-block-body",
        ),
    ],
)
def test_a_guard_or_rebinding_in_a_branch_does_not_end_the_scan(branch: str):
    """A branch that may not run cannot decide for the reads after it
    (#5904 gap 2)."""
    src = f"""\
def example(flag, pending):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    {branch}
    acknowledge(offer)
"""
    read = src.splitlines().index("    acknowledge(offer)") + 1
    first = [site for site in _sentinel_sites(src) if site.block == 3]
    assert first == [SentinelSite(2, "offer", 3, read)], src


def test_a_read_inside_a_branch_is_still_a_leak():
    """The branch may run, so its read counts even though its guard does not
    reach past it."""
    src = """\
def example(flag):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    if flag:
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 7)]


def test_a_rebinding_in_finally_ends_the_sentinel():
    """``finally`` always runs, so its rebinding decides like a statement's."""
    src = """\
def example():
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    try:
        pass
    finally:
        offer = fallback()
    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


@pytest.mark.parametrize("arm", ["try", "except", "else"])
def test_read_in_a_sibling_finally_is_a_leak(arm: str):
    """``finally`` runs after every other arm (#5904 gap 3)."""
    src = (
        "def example():\n    offer = None\n"
        + _try_with_producer_in(arm)
        + "    finally:\n        acknowledge(offer)\n"
    )
    line = src.splitlines().index("        acknowledge(offer)") + 1
    assert _sentinel_leaks(src) == [("offer", line)], src


def test_read_in_try_else_after_a_producer_in_try_is_a_leak():
    """The block swallows its failure, so the ``try`` completes and ``else``
    runs with the placeholder."""
    src = """\
def example():
    offer = None
    try:
        with demo_step("Step 1: produce"):
            offer = submit_report()
    except ValueError:
        pass
    else:
        acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 9)]


@pytest.mark.parametrize("loop", ["for item in items:", "while items:"])
def test_read_earlier_in_a_loop_body_than_the_producer_is_a_leak(loop: str):
    """The next iteration reads what this one's block left (#5904 gap 4)."""
    src = f"""\
def example(items):
    offer = None
    {loop}
        acknowledge(offer)
        with demo_step("Step 1: produce"):
            offer = submit_report()
"""
    assert _sentinel_leaks(src) == [("offer", 4)]


def test_loop_target_is_not_a_sentinel_inside_the_loop_body():
    """The ``for`` rebinds its target before every iteration, so a block in
    the body writing it holds no placeholder."""
    src = """\
def example(items):
    offer = None
    for offer in items:
        acknowledge(offer)
        with demo_step("Step 1: refresh"):
            offer = refresh(offer)
"""
    assert _sentinel_sites(src) == []


@pytest.mark.parametrize(
    "producer",
    [
        pytest.param(
            "async for offer in stream():\n            pass", id="async-for"
        ),
        pytest.param(
            "async with open_offer() as offer:\n            pass",
            id="async-with",
        ),
    ],
)
def test_async_for_and_async_with_are_producers(producer: str):
    """``async for`` and ``async with`` bind like their sync forms
    (#5904 gap 5)."""
    src = f"""\
async def example():
    offer = None
    with demo_step("Step 1: produce"):
        {producer}

    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 7)]


@pytest.mark.parametrize(
    "producer",
    [
        pytest.param(
            "async for result in stream():\n            pass", id="async-for"
        ),
        pytest.param(
            "async with open_result() as result:\n            pass",
            id="async-with",
        ),
    ],
)
def test_unbound_check_sees_async_producers(tmp_path, producer: str):
    """The unbound check shares :func:`_assigned_shallow`, so the async forms
    are producers there too (#5904 gap 5)."""
    src = f"""\
async def example():
    with demo_step("Step"):
        {producer}
    use(result)
"""
    path = tmp_path / "demo_async.py"
    path.write_text(src)
    assert [v for _, _, v in _violations_in_file(path)] == ["result"]


def test_as_binding_of_a_guarded_block_ends_the_sentinel():
    """``__enter__`` binds the name before the body runs (#5904 gap 6)."""
    src = """\
def example():
    step = None
    with demo_step("Step 1: open") as step:
        pass

    with demo_step("Step 2: produce"):
        step = submit_report()

    acknowledge(step)
"""
    assert _sentinel_sites(src) == []


def test_preinit_in_a_nested_statement_list_is_tracked_outside_it():
    """A placeholder written inside an ``if`` still holds after it
    (#5904 gap 7)."""
    src = """\
def example(flag):
    if flag:
        offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [("offer", 7)]


def test_rebinding_later_in_the_branch_drops_its_preinit():
    """The branch's own last binding is what leaves it."""
    src = """\
def example(flag):
    if flag:
        offer = None
        offer = fallback()
    with demo_step("Step 1: produce"):
        offer = submit_report()

    acknowledge(offer)
"""
    assert _sentinel_sites(src) == []


@pytest.mark.parametrize(
    "arms",
    [
        pytest.param(
            "if flag:\n        offer = a()\n    else:\n        offer = b()",
            id="if-else",
        ),
        pytest.param(
            "if flag:\n        offer = a()\n    elif other:\n"
            "        offer = b()\n    else:\n        offer = c()",
            id="if-elif-else",
        ),
        pytest.param(
            "match flag:\n        case 1:\n            offer = a()\n"
            "        case _:\n            offer = b()",
            id="match-with-wildcard",
        ),
        pytest.param(
            "try:\n        offer = a()\n    except ValueError:\n"
            "        offer = b()",
            id="try-and-every-handler",
        ),
        pytest.param(
            "try:\n        offer = a()\n    finally:\n        pass",
            id="try-finally-no-handler",
        ),
        pytest.param(
            "if flag:\n        offer = a()\n    else:\n"
            "        if offer is None:\n            raise SystemExit",
            id="rebinding-and-guard",
        ),
        pytest.param(
            "if flag:\n        offer = a()\n    else:\n"
            "        raise RuntimeError(flag)",
            id="else-raises",
        ),
        pytest.param(
            "try:\n        offer = a()\n    except ValueError:\n        raise",
            id="handler-re-raises",
        ),
        pytest.param(
            "try:\n        offer = a()\n    except ValueError:\n"
            "        return None",
            id="handler-returns",
        ),
        pytest.param(
            "if flag:\n        offer = a()\n    elif other:\n"
            "        raise RuntimeError(flag)\n    else:\n        return None",
            id="every-other-arm-leaves",
        ),
    ],
)
def test_every_arm_deciding_the_name_ends_the_sentinel(arms: str):
    """A statement whose every path rebinds or guards the name decides it,
    as one statement-level rebinding would; an arm that raises or returns
    reaches nothing after the statement, so it need not decide it."""
    src = f"""\
def example(flag, other):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    {arms}
    acknowledge(offer)
"""
    assert _sentinel_leaks(src) == [], src


@pytest.mark.parametrize(
    "arms",
    [
        pytest.param(
            "if flag:\n        offer = a()\n    elif other:\n        offer = b()",
            id="if-elif-no-else",
        ),
        pytest.param(
            "match flag:\n        case 1:\n            offer = a()\n"
            "        case 2:\n            offer = b()",
            id="match-without-wildcard",
        ),
        pytest.param(
            "match flag:\n        case 1:\n            offer = a()\n"
            "        case _ if other:\n            offer = b()",
            id="match-guarded-wildcard",
        ),
        pytest.param(
            "if flag:\n        offer = a()\n    else:\n        log(flag)",
            id="other-arm-runs-on",
        ),
        pytest.param(
            "if flag:\n        raise RuntimeError(flag)\n"
            "    else:\n        return None",
            id="no-arm-decides",
        ),
    ],
)
def test_arms_that_can_all_be_skipped_do_not_end_the_sentinel(arms: str):
    src = f"""\
def example(flag, other):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    {arms}
    acknowledge(offer)
"""
    assert [name for name, _ in _sentinel_leaks(src)] == ["offer"], src


@pytest.mark.parametrize(
    ("statement", "leaks"),
    [
        pytest.param(
            "if offer:\n        pass\n    else:\n        acknowledge(offer)",
            True,
            id="else-of-a-truthiness-test",
        ),
        pytest.param(
            "if offer is None:\n        log(offer)", True, id="body-of-is-none"
        ),
        pytest.param(
            "if not offer:\n        log(offer)", True, id="body-of-not"
        ),
        pytest.param(
            "if offer is None:\n        log(flag)\n    else:\n"
            "        acknowledge(offer)",
            False,
            id="else-of-is-none",
        ),
        pytest.param(
            "while not offer:\n        offer = poll()", False, id="while-not"
        ),
        pytest.param(
            "ident = offer.id_ if not offer else None",
            True,
            id="ternary-else",
        ),
        pytest.param(
            "if offer is None and flag:\n        log(offer)",
            True,
            id="comparison-inside-an-and-test",
        ),
        pytest.param(
            "assert offer is None\n    log(offer)",
            True,
            id="assert-is-none",
        ),
        pytest.param(
            "ready = offer is not None and flag\n    log(offer)",
            True,
            id="comparison-outside-a-test",
        ),
        pytest.param(
            "ready = offer is not None and offer.ready",
            False,
            id="and-chain-defends-its-later-operand",
        ),
        pytest.param(
            "ready = offer is None or offer.ready",
            False,
            id="or-chain-defends-its-later-operand",
        ),
        pytest.param(
            "match flag:\n        case 1 if offer is None:\n"
            "            log(offer)",
            True,
            id="case-guard-is-none",
        ),
    ],
)
def test_the_arm_a_guard_proves_placeholder_is_undefended(
    statement: str, leaks: bool
):
    """``if x:`` leaves *x* falsy — maybe the placeholder — in its ``else``,
    and ``if x is None:`` leaves it so in its body."""
    src = f"""\
def example(flag):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    {statement}
"""
    assert bool(_sentinel_leaks(src)) is leaks, src


def test_a_match_case_guard_defends_its_own_body():
    src = """\
def example(kind):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    match kind:
        case 1 if offer:
            acknowledge(offer)
"""
    assert _sentinel_leaks(src) == []


@pytest.mark.parametrize(
    ("loop", "leaks"),
    [
        pytest.param(
            "for item in items:\n        if item:\n            offer = item\n"
            "            break\n    else:\n        offer = default()",
            False,
            id="for-else-every-break-after-a-rebinding",
        ),
        pytest.param(
            "while True:\n        offer = poll()\n        if offer:\n"
            "            break",
            False,
            id="endless-poll-loop",
        ),
        pytest.param(
            "while True:\n        if offer:\n            break\n"
            "        offer = poll()",
            False,
            id="break-under-a-guard",
        ),
        pytest.param(
            "for item in items:\n        if item:\n            break\n"
            "        offer = item\n    else:\n        offer = default()",
            True,
            id="break-before-the-rebinding",
        ),
        pytest.param(
            "for item in items:\n        offer = item",
            True,
            id="loop-that-can-run-zero-times",
        ),
        pytest.param(
            "while flag:\n        offer = poll()\n        if offer:\n"
            "            break",
            True,
            id="loop-that-can-run-out",
        ),
    ],
)
def test_a_loop_decides_the_name_only_if_every_exit_does(
    loop: str, leaks: bool
):
    """A loop is left through a ``break`` or by running out into its
    ``else`` arm; ``while True:`` never runs out.  Only when every one of
    those exits rebinds or guards the name does the loop decide it."""
    src = f"""\
def example(flag, items):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    {loop}
    acknowledge(offer)
"""
    assert bool(_sentinel_leaks(src)) is leaks, src


@pytest.mark.parametrize(
    "shape",
    [
        pytest.param(
            "while not done(offer):\n"
            '        with demo_step("Step 1: produce"):\n'
            "            offer = submit_report()",
            id="while-test-on-the-next-pass",
        ),
        pytest.param(
            'try:\n        with demo_step("Step 1: produce"):\n'
            "            offer = submit_report()\n        follow_up()\n"
            "    except ValueError:\n        acknowledge(offer)",
            id="handler-after-a-later-failure",
        ),
    ],
)
def test_read_the_producers_failure_reaches_later_in_the_statement(
    shape: str,
):
    """A ``while`` test runs again after its body, and a failure later in a
    ``try`` body hands the placeholder to a handler."""
    src = f"""\
def example():
    offer = None
    {shape}
"""
    assert [name for name, _ in _sentinel_leaks(src)] == ["offer"], src


def test_else_and_a_handler_are_alternatives_after_a_try_body():
    """After a producer in a ``try`` body, ``else`` and each handler are
    alternative paths: a handler's rebinding does not defend ``else``."""
    src = """\
def example():
    offer = None
    try:
        with demo_step("Step 1: produce"):
            offer = submit_report()
    except ValueError:
        offer = fallback()
    else:
        offer = confirmed(offer.id_)
    acknowledge(offer)
"""
    assert [read for _, read in _sentinel_leaks(src)] == [9]


@pytest.mark.parametrize(
    "binding",
    [
        pytest.param(
            "try:\n        pass\n    except ValueError as offer:\n"
            "        acknowledge(offer)",
            id="except-as",
        ),
        pytest.param(
            "match kind:\n        case Offer() as offer:\n"
            "            acknowledge(offer)",
            id="case-as",
        ),
        pytest.param(
            "match kind:\n        case [*offer]:\n            acknowledge(offer)",
            id="case-star",
        ),
        pytest.param(
            "match kind:\n        case {**offer}:\n            acknowledge(offer)",
            id="case-mapping-rest",
        ),
    ],
)
def test_except_and_capture_bindings_are_rebindings(binding: str):
    """``except E as x`` and a capture pattern bind *x* before the arm runs."""
    src = f"""\
def example(kind):
    offer = None
    with demo_step("Step 1: produce"):
        offer = submit_report()

    {binding}
"""
    assert _sentinel_leaks(src) == [], src


@pytest.mark.spec("EDF-06-005")
def test_no_placeholder_sentinel_read_after_demo_block():
    """No demo block may hand a placeholder sentinel to a later read (#3038).

    Nest the dependent steps inside the block that produces the value
    (preferred, ADR-0058), or guard every later read — an unguarded sentinel
    posts ``None`` and blames the wrong step (EDF-06-005, DEMOCI-01-009).
    """
    leaks = [
        f"{path.relative_to(_corpus.REPO_ROOT)}:{site.preinit}:"
        f" '{site.name}' holds its placeholder until the block on line"
        f" {site.block} assigns it, then is read unguarded at line"
        f" {site.read}"
        for path, site in _demo_sentinel_sites()
        if site.read is not None
    ]

    assert leaks == [], (
        'Names pre-initialized to None or "", assigned inside a'
        " demo_step/demo_check/demo_gate block, and read afterward with no"
        " guard (#3038, #3887):\n" + "\n".join(leaks)
    )


def test_both_checks_have_subjects_to_examine():
    """A scan that examined nothing would pass however broken it was (#5535).

    Both checks share one corpus query, so one guard covers both: an empty
    file set means the query stopped matching, not that the demo tree is
    clean.  The sentinel arm goes further and requires at least one live
    placeholder pre-initialisation feeding a guarded block, because that shape
    is legitimate when every later read is guarded
    (``notes/demo-scenario-authoring.md``) and so is never driven to zero by
    this ratchet.  If it does reach zero, retire this arm in the commit that
    removes the last one rather than loosening the guard.
    """
    assert len(_demo_modules()) > 1, (
        "No file under vultron/demo/ mentions demo_step, demo_check or"
        " demo_gate, so both checks above examined nothing."
    )
    assert _demo_sentinel_sites(), (
        "No placeholder pre-initialization under vultron/demo/ reaches a"
        " demo_step/demo_check/demo_gate block, so the sentinel check above"
        " examined no subject."
    )
