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
"""Which tests carry a ``spec`` marker, and which of them a strict xfail holds.

``spec-coverage`` tells a requirement a passing test verifies from one only a
strict ``xfail`` checks (SR-05-017). This module reads one test file's source
and returns a :class:`MarkedCase` for each way its marked tests run: the spec
IDs that case carries and the reasons of the ``xfail`` markers that apply to
it. A case with no xfail reason runs to pass or fail.

A marker applies to a test from four places, and they combine as pytest
combines them: a module ``pytestmark``, a class decorator or class
``pytestmark`` (inherited by nested classes), a function decorator, and a
``pytest.param(..., marks=...)`` entry of a ``parametrize`` decorator, which
applies to that parameter set only. Several ``parametrize`` decorators make
their cross product.

Every ``xfail`` counts as strict. TB-17-001 requires ``strict=True`` on each
one, and ``xfail_strict = true`` in ``pyproject.toml`` makes an omitted
``strict`` strict at run time, so the reader does not inspect ``strict``. An
``xfail`` with a condition counts as holding wherever it applies: the report
errs toward listing a gap. Two things that stop a case running count like an
``xfail`` too, because no passing run comes of them: an unconditional
``mark.skip`` (its reason prefixed ``skip:``) and a ``parametrize`` whose
literal argument list is empty.

As pytest does, only the last ``pytestmark`` assignment of a module or class
counts, and a ``parametrize`` inside it adds an axis like a decorator.

Loose reading, as for the TB-17-001 ratchet: the reader reads names, not
values. It does not see a marker bound to a variable first (``xf =
pytest.mark.xfail`` then ``@xf``), a mark inherited from a base class, or a
``skipif``. A ``parametrize`` argument list it cannot read (a call, a
name) counts as one parameter set with no marks. A comprehension counts as the
parameter sets its element can produce, both branches of a conditional
expression included.
"""

from __future__ import annotations

import ast
import itertools
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field

_ISSUE_REF_RE = re.compile(r"#(\d+)")


@dataclass(frozen=True)
class _Marks:
    """The spec IDs and xfail reasons one mark expression, or several, carry."""

    spec_ids: frozenset[str] = frozenset()
    xfail_reasons: tuple[str | None, ...] = ()
    param_ids: tuple[str, ...] = ()

    def __or__(self, other: _Marks) -> _Marks:
        return _Marks(
            self.spec_ids | other.spec_ids,
            self.xfail_reasons + other.xfail_reasons,
            self.param_ids + other.param_ids,
        )


@dataclass(frozen=True)
class _Scope:
    """The marks a module or class passes down to the tests inside it."""

    marks: _Marks = field(default_factory=_Marks)
    axes: tuple[tuple[_Marks, ...], ...] = ()
    qualname: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarkedCase:
    """One way a marked test runs: its spec IDs and the xfails that hold it.

    Attributes:
        test: ``path::Class::function``, the test as pytest names it. When
            each parameter set of the case has a literal ``id=``, the IDs
            follow in brackets, joined by ``-``, as pytest joins them.
        spec_ids: Spec IDs the case carries.
        xfail_reasons: The ``reason`` of each ``xfail`` marker that applies,
            ``None`` where the reason is not a string the reader can resolve,
            and of each skip the module docstring names. Empty when none
            applies, so the case runs to pass or fail.
    """

    test: str
    spec_ids: frozenset[str]
    xfail_reasons: tuple[str | None, ...]

    @property
    def is_xfail(self) -> bool:
        """Whether a strict ``xfail`` holds this case."""
        return bool(self.xfail_reasons)


def issue_refs(reason: str | None) -> tuple[int, ...]:
    """The issue numbers an xfail reason cites as ``#N``, sorted and unique."""
    if reason is None:
        return ()
    return tuple(sorted({int(n) for n in _ISSUE_REF_RE.findall(reason)}))


def dotted_name(node: ast.expr) -> str:
    """``a.b.c`` for an attribute chain on a name; ``""`` for anything else."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def _is_mark(node: ast.expr, name: str) -> bool:
    return dotted_name(node).endswith(f"mark.{name}")


def spec_call_ids(node: ast.AST) -> frozenset[str]:
    """The string IDs a ``mark.spec(...)`` call names; empty for any other node."""
    if not (isinstance(node, ast.Call) and _is_mark(node.func, "spec")):
        return frozenset()
    return frozenset(
        arg.value
        for arg in node.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    )


def _resolve_str(node: ast.expr, constants: Mapping[str, str]) -> str | None:
    """A string expression's value, from literals and module string constants.

    Resolves a literal, an f-string whose fields are plain module constants,
    a ``+`` of two such strings, and a module constant's name. Anything else
    is ``None``.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_str(node.left, constants)
        right = _resolve_str(node.right, constants)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                if value.conversion != -1 or value.format_spec is not None:
                    return None
                part = _resolve_str(value.value, constants)
            else:
                part = _resolve_str(value, constants)
            if part is None:
                return None
            parts.append(part)
        return "".join(parts)
    return None


def _bindings(body: Iterable[ast.stmt]) -> Iterator[tuple[str, ast.expr]]:
    """Each ``name = value`` (or ``name: T = value``) statement in *body*."""
    for stmt in body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        else:
            continue
        if isinstance(target, ast.Name):
            yield target.id, value


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level names bound to a string the reader can resolve."""
    constants: dict[str, str] = {}
    for name, value in _bindings(tree.body):
        resolved = _resolve_str(value, constants)
        if resolved is not None:
            constants[name] = resolved
    return constants


def _marks_of(node: ast.expr, constants: Mapping[str, str]) -> _Marks:
    """The spec IDs and xfail reasons a mark expression, or a list of them, holds."""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        found = _Marks()
        for element in node.elts:
            found |= _marks_of(element, constants)
        return found
    if isinstance(node, ast.Attribute) and _is_mark(node, "xfail"):
        return _Marks(xfail_reasons=(None,))
    if isinstance(node, ast.Attribute) and _is_mark(node, "skip"):
        return _Marks(xfail_reasons=("skip:",))
    if not isinstance(node, ast.Call):
        return _Marks()
    if _is_mark(node.func, "spec"):
        return _Marks(spec_ids=spec_call_ids(node))
    is_skip = _is_mark(node.func, "skip")
    if not (is_skip or _is_mark(node.func, "xfail")):
        return _Marks()
    reason_node = next(
        (k.value for k in node.keywords if k.arg == "reason"),
        node.args[0] if is_skip and node.args else None,
    )
    reason = (
        None if reason_node is None else _resolve_str(reason_node, constants)
    )
    if is_skip:
        reason = "skip:" if reason is None else f"skip: {reason}"
    return _Marks(xfail_reasons=(reason,))


def _param_variants(
    node: ast.expr, constants: Mapping[str, str]
) -> list[_Marks]:
    """The marks each parameter set one argument-list element can produce."""
    if isinstance(node, ast.IfExp):
        return _param_variants(node.body, constants) + _param_variants(
            node.orelse, constants
        )
    if isinstance(node, ast.Call) and dotted_name(node.func).endswith("param"):
        keywords = {k.arg: k.value for k in node.keywords}
        marks = keywords.get("marks")
        found = _Marks() if marks is None else _marks_of(marks, constants)
        param_id = keywords.get("id")
        if isinstance(param_id, ast.Constant) and isinstance(
            param_id.value, str
        ):
            found |= _Marks(param_ids=(param_id.value,))
        return [found]
    return [_Marks()]


_EMPTY_PARAMETER_SET = _Marks(xfail_reasons=("skip: got empty parameter set",))


def _parametrize_axis(
    call: ast.Call, constants: Mapping[str, str]
) -> tuple[_Marks, ...]:
    """The distinct marks of the parameter sets one ``parametrize`` produces."""
    argvalues = (
        call.args[1]
        if len(call.args) > 1
        else next(
            (k.value for k in call.keywords if k.arg == "argvalues"), None
        )
    )
    variants: list[_Marks]
    if isinstance(argvalues, (ast.List, ast.Tuple)):
        variants = [
            variant
            for element in argvalues.elts
            for variant in _param_variants(element, constants)
        ] or [_EMPTY_PARAMETER_SET]
    elif isinstance(argvalues, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
        variants = _param_variants(argvalues.elt, constants)
    else:
        variants = [_Marks()]
    return tuple(dict.fromkeys(variants))


def _scope_from(
    parent: _Scope,
    name: str | None,
    decorators: Iterable[ast.expr],
    constants: Mapping[str, str],
) -> _Scope:
    marks, axes = parent.marks, list(parent.axes)
    for decorator in _flattened(decorators):
        if isinstance(decorator, ast.Call) and _is_mark(
            decorator.func, "parametrize"
        ):
            axes.append(_parametrize_axis(decorator, constants))
        else:
            marks |= _marks_of(decorator, constants)
    qualname = parent.qualname if name is None else (*parent.qualname, name)
    return _Scope(marks, tuple(axes), qualname)


def _flattened(exprs: Iterable[ast.expr]) -> Iterator[ast.expr]:
    """*exprs*, with each list or tuple of marks opened into its elements."""
    for expr in exprs:
        if isinstance(expr, (ast.List, ast.Tuple)):
            yield from _flattened(expr.elts)
        else:
            yield expr


def _pytestmark(body: Iterable[ast.stmt]) -> list[ast.expr]:
    """The last ``pytestmark`` value of a module or class body, as pytest reads it."""
    values = [value for name, value in _bindings(body) if name == "pytestmark"]
    return values[-1:]


def _cases_in(
    path: str,
    body: Iterable[ast.stmt],
    scope: _Scope,
    constants: Mapping[str, str],
) -> Iterator[MarkedCase]:
    for stmt in body:
        if isinstance(stmt, ast.ClassDef):
            inner = _scope_from(
                scope,
                stmt.name,
                [*stmt.decorator_list, *_pytestmark(stmt.body)],
                constants,
            )
            yield from _cases_in(path, stmt.body, inner, constants)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            test = _scope_from(
                scope, stmt.name, stmt.decorator_list, constants
            )
            name = "::".join((path, *test.qualname))
            for combination in itertools.product(*test.axes):
                marks = test.marks
                for param_marks in combination:
                    marks |= param_marks
                if not marks.spec_ids:
                    continue
                named = bool(combination) and all(
                    c.param_ids for c in combination
                )
                suffix = f"[{'-'.join(marks.param_ids)}]" if named else ""
                yield MarkedCase(
                    name + suffix, marks.spec_ids, marks.xfail_reasons
                )


def marked_cases_in(path: str, source: str) -> list[MarkedCase]:
    """Each distinct way a marked test in *source* runs.

    Args:
        path: The file's path as reported in :attr:`MarkedCase.test`.
        source: The file's text.

    Returns:
        One :class:`MarkedCase` per test and distinct combination of
        parameter marks, for tests that carry at least one spec ID, and one
        case named *path*, held by no xfail, for the IDs of ``mark.spec``
        calls the reader cannot place in a test.

    Raises:
        SyntaxError: *source* does not parse; the error names *path*.
    """
    if "mark.spec" not in source:
        return []
    tree = ast.parse(source, filename=path)
    constants = _module_constants(tree)
    module = _scope_from(_Scope(), None, _pytestmark(tree.body), constants)
    cases = list(dict.fromkeys(_cases_in(path, tree.body, module, constants)))
    unplaced = _unplaced_spec_ids(tree)
    if unplaced:
        cases.append(MarkedCase(path, unplaced, ()))
    return cases


def _mark_sites(body: Iterable[ast.stmt]) -> Iterator[ast.expr]:
    """Every decorator and ``pytestmark`` value the reader places marks from."""
    yield from (
        value for name, value in _bindings(body) if name == "pytestmark"
    )
    for stmt in body:
        if isinstance(
            stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            yield from stmt.decorator_list
        if isinstance(stmt, ast.ClassDef):
            yield from _mark_sites(stmt.body)


def _unplaced_spec_ids(tree: ast.Module) -> frozenset[str]:
    """IDs of ``mark.spec`` calls outside every place the reader reads.

    Such a marker (in a factory function, under an ``if``) still marks a
    test pytest may run, so it gets a case no xfail holds: the report never
    calls a requirement xfail-only on the strength of the markers it can see
    while a passing one it cannot see exists.
    """
    placed = {
        id(node) for site in _mark_sites(tree.body) for node in ast.walk(site)
    }
    return frozenset().union(
        *(
            spec_call_ids(node)
            for node in ast.walk(tree)
            if id(node) not in placed
        )
    )
