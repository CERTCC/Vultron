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
"""Reachability derivation for the guards under ``vultron/``.

The ratchet that reads this module is ``test_guards_run_in_production.py``;
its docstring states the rule.  This module answers the two questions the
rule turns on, both from the shared corpus parse (TB-13-001, TB-13-003):

1. Which functions under ``vultron/`` are **private guards** — undecorated,
   single-underscore, non-dunder definitions that raise in their own scope —
   and which parameters **gate** a refusal, by opening it only when a caller
   supplies them.
2. Whether production code reaches each one: whether any name reference to
   the guard exists outside its own definition, and whether some call site
   supplies each gating parameter.

:func:`findings` answers both for the package; :func:`findings_in_source`
answers both for one inline module, which is how the ratchet's synthetic
detector tests drive the same judgement without a file on disk.

Only files containing ``raise `` are parsed, and within them the guard pass
walks only definitions whose own source span contains ``raise ``, so the cost
stays proportional to the match count (TB-13-002, TB-13-008).

Four over-approximations are deliberate, and each one can only produce a
*pass* that a precise resolver would fail — never a failure a precise
resolver would pass, so the ratchet never blocks a change it should not:

* **Names, not bindings.** A guard is matched by its bare name, so two
  same-named private guards in different modules share one another's
  references and call sites.  Resolving the binding would mean resolving
  every import in the package.
* **A self-call counts as a reference.** A guard whose only reference is its
  own recursive call reads as reached.
* **A ``**kwargs`` splat supplies everything.** A call the derivation cannot
  read is given the benefit of the doubt.
* **A module that refuses nothing is out of scope.** The file prefilter is
  the whole package's: a gate in a module with no ``raise `` anywhere, whose
  branch only delegates to a guard elsewhere, is never seen.  Dropping the
  file prefilter would double the derivation's cost for a shape that has no
  instance in the package today.

Spec: TB-13-001, TB-13-002, TB-13-003 (``specs/testability.yaml``).
"""

import ast
import functools
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from test.architecture import _corpus

#: The package the rule is about.
PACKAGE = _corpus.REPO_ROOT / "vultron"

#: A guard body always contains this, so nothing without it is parsed or
#: walked (TB-13-002, TB-13-008).
RAISE_FRAGMENT = "raise "

#: A spec requirement id as every spec file and diagnostic spells it.
SPEC_ID = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{2}-\d{3}\b")


# ---------------------------------------------------------------------------
# What the derivation reports
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Guard:
    """One private guard definition.

    Attributes:
        name: The definition's bare name.
        path: Repo-relative path of the defining file.
        lineno: Line the ``def`` sits on.
        in_class: Whether the definition is a method (a guard reached as
            ``self._check(...)``) rather than a module-level function.  The
            two shapes are asserted separately, so retiring one is a
            deliberate edit rather than a silent narrowing (#5535).
    """

    name: str
    path: str
    lineno: int
    in_class: bool

    @property
    def site(self) -> str:
        """``path:lineno name()`` — how a violation names this guard."""
        return f"{self.path}:{self.lineno} {self.name}()"


@dataclass(frozen=True)
class Gate:
    """One parameter whose presence opens a refusal inside a function.

    Attributes:
        name: The enclosing function's bare name.
        path: Repo-relative path of the defining file.
        lineno: Line the ``def`` sits on.
        parameter: The parameter the refusal is gated on.
        index: The positional index *parameter* may also be passed at, or
            ``None`` when it is keyword-only.
        in_class: Whether the enclosing definition is a method.
    """

    name: str
    path: str
    lineno: int
    parameter: str
    index: int | None
    in_class: bool

    @property
    def site(self) -> str:
        """How a violation names this gate."""
        return f"{self.path}:{self.lineno} {self.name}() [{self.parameter}]"


@dataclass(frozen=True)
class CallSite:
    """One call of a name, and what it passes."""

    path: str
    lineno: int
    keywords: frozenset[str]
    double_starred: bool
    positional_count: int

    def supplies(self, parameter: str, index: int | None) -> bool:
        """Whether this call passes *parameter*."""
        if parameter in self.keywords or self.double_starred:
            return True
        return index is not None and self.positional_count > index


@dataclass(frozen=True)
class Findings:
    """Both arms' subjects and both arms' violations, over one file set."""

    guards: tuple[Guard, ...]
    gates: tuple[Gate, ...]
    #: Guards nothing references — dead on arrival.
    unreached: frozenset[str]
    #: Gating parameters no call site supplies — the check never runs.
    unsupplied: frozenset[str]


# ---------------------------------------------------------------------------
# Judgements about one definition
# ---------------------------------------------------------------------------
def own_scope(fn: ast.AST) -> Iterator[ast.AST]:
    """Nodes in *fn*'s own scope, not descending into a nested scope.

    A nested function, lambda or class defined inside *fn* is its own scope:
    a raise in one is that scope's refusal, not *fn*'s, exactly as the
    DataLayer-mutation ratchet treats an inner function's write.
    """
    pending: list[ast.AST] = list(getattr(fn, "body", []))
    while pending:
        node = pending.pop()
        yield node
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef),
        ):
            continue
        for _field, value in ast.iter_fields(node):
            if isinstance(value, list):
                pending.extend(
                    item for item in value if isinstance(item, ast.AST)
                )
            elif isinstance(value, ast.AST):
                pending.append(value)


def raises_in(fn: ast.AST) -> Iterator[ast.Raise]:
    """Each ``raise <exception>`` in *fn*'s own scope.

    A bare ``raise`` is a re-raise inside an ``except`` block, not a refusal
    of its own, so it is skipped.
    """
    for node in own_scope(fn):
        if isinstance(node, ast.Raise) and node.exc is not None:
            yield node


def is_private(name: str) -> bool:
    """Whether *name* is single-underscore private and not a dunder."""
    return name.startswith("_") and not name.startswith("__")


def is_private_guard(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether *fn* is a private guard: private, undecorated, and it raises.

    Keyed on the act — refusing — and on visibility, not on a naming
    convention for validators, so renaming a guard keeps it in the subject
    set (``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the
    Act").

    A **decorated** definition is excluded because something other than a
    call site invokes it: a Pydantic ``@field_validator`` is run by the
    model, a ``@property`` by attribute access, a registered CLI command by
    the framework.  Requiring a call site for those would fail every one.
    """
    if fn.decorator_list or not is_private(fn.name):
        return False
    return any(True for _raise in raises_in(fn))


def cites_a_spec(node: ast.AST) -> bool:
    """Whether any string constant under *node* names a spec requirement."""
    return any(
        isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and SPEC_ID.search(child.value)
        for child in ast.walk(node)
    )


def none_defaulted_params(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, int | None]:
    """Each parameter of *fn* defaulting to ``None``, by positional index.

    ``None`` as the index marks a keyword-only parameter, which no
    positional argument can reach.  A parameter without a ``None`` default
    is excluded: a caller cannot omit it, so it is always supplied.
    """
    arguments = fn.args
    positional = arguments.posonlyargs + arguments.args
    found: dict[str, int | None] = {}
    first_default = len(positional) - len(arguments.defaults)
    for offset, (argument, default) in enumerate(
        zip(positional[first_default:], arguments.defaults, strict=True)
    ):
        if isinstance(default, ast.Constant) and default.value is None:
            found[argument.arg] = first_default + offset
    # ``kw_defaults`` carries ``None`` for a keyword-only parameter with no
    # default at all, which is why the element type is optional.
    for argument, kw_default in zip(
        arguments.kwonlyargs, arguments.kw_defaults, strict=True
    ):
        if isinstance(kw_default, ast.Constant) and kw_default.value is None:
            found[argument.arg] = None
    return found


def presence_asserted(
    test: ast.expr, *, positive: bool = True
) -> Iterator[str]:
    """Parameter names whose *presence* makes *test* true under *positive*.

    Polarity is what separates a gate from a default.  ``if p is not None:``
    opens its body only when the caller supplied ``p``; the inverted
    ``discover() if p is None else tuple(p)`` runs its first branch only
    when the caller *omitted* it, and is an injection seam, not a gate.
    Reading the two the same way reported the scenario exporter's
    ``specs=None`` seam as a dead check.

    ``and`` preserves positive polarity and ``or`` preserves negative, so
    ``p is not None and x < y`` still gates on ``p``; the other combinations
    make presence insufficient and are not followed.
    """
    if isinstance(test, ast.BoolOp):
        preserved = (
            isinstance(test.op, ast.And)
            if positive
            else isinstance(test.op, ast.Or)
        )
        if preserved:
            for value in test.values:
                yield from presence_asserted(value, positive=positive)
        return
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        yield from presence_asserted(test.operand, positive=not positive)
        return
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        if not isinstance(test.left, ast.Name):
            return
        other = test.comparators[0]
        if not (isinstance(other, ast.Constant) and other.value is None):
            return
        operator = test.ops[0]
        if (isinstance(operator, ast.IsNot) and positive) or (
            isinstance(operator, ast.Is) and not positive
        ):
            yield test.left.id
        return
    if isinstance(test, ast.Name) and positive:
        yield test.id


def _refuses(body: Sequence[ast.AST], refusing: frozenset[str]) -> bool:
    """Whether *body* raises, or calls a name in *refusing*."""
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Raise) and node.exc is not None:
                return True
            if (
                isinstance(node, ast.Call)
                and _corpus.callee_name(node.func) in refusing
            ):
                return True
    return False


def gated_params(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, refusing: frozenset[str]
) -> dict[str, int | None]:
    """Parameters of *fn* whose presence opens a refusal inside *fn*.

    This is the half of the rule that "a caller exists" misses.
    ``_validate_canonical_entry`` had a caller; what it did not have was a
    caller that passed ``case_published``, and the CLP-14-013 check sat
    behind ``if case_published is not None:`` (ISSUE-2824).  A parameter
    like that is the switch the check runs on.
    """
    candidates = none_defaulted_params(fn)
    if not candidates:
        return {}
    found: dict[str, int | None] = {}
    for node in own_scope(fn):
        if isinstance(node, ast.If):
            branches: tuple[tuple[bool, Sequence[ast.AST]], ...] = (
                (True, node.body),
                (False, node.orelse),
            )
        elif isinstance(node, ast.IfExp):
            branches = ((True, [node.body]), (False, [node.orelse]))
        else:
            continue
        for polarity, body in branches:
            if not body or not _refuses(body, refusing):
                continue
            for name in presence_asserted(node.test, positive=polarity):
                if name in candidates:
                    found[name] = candidates[name]
    return found


# ---------------------------------------------------------------------------
# One walk per module, serving both arms
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _FileScan:
    """What one walk of a module's tree yields."""

    path: str
    #: The module's source lines, for the per-definition prefilter.
    lines: tuple[str, ...]
    tree: ast.AST
    definitions: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]
    #: ``id()`` of each definition that is a method: a function in a
    #: ``ClassDef`` body.  A function nested inside another function is not a
    #: method, whatever class the outer one sits in.
    methods: frozenset[int]
    #: Every identifier loaded as a name or an attribute in the module.
    referenced: frozenset[str]


def _walk_module(path: str, source: str, tree: ast.AST) -> _FileScan:
    """Collect in one walk everything both arms need from one module.

    Walking the tree once for the definitions and again for the references
    doubled the whole derivation, and the two want the same nodes.
    """
    definitions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    methods: set[int] = set()
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.append(node)
        elif isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.ClassDef):
            methods.update(
                id(member)
                for member in node.body
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return _FileScan(
        path=path,
        lines=tuple(source.splitlines()),
        tree=tree,
        definitions=tuple(definitions),
        methods=frozenset(methods),
        referenced=frozenset(referenced),
    )


def _may_raise(lines: Sequence[str], fn: ast.AST) -> bool:
    """Whether *fn*'s source span contains ``raise `` at all.

    A text prefilter in front of the own-scope walk: most definitions never
    raise, and walking every one of them to find that out cost more than the
    rest of the derivation together — TB-13-002 applied per definition
    rather than per file.  The span includes any nested definition, so this
    only ever admits a candidate the walk then judges.
    """
    start = getattr(fn, "lineno", 0)
    end = getattr(fn, "end_lineno", None) or start
    return any(RAISE_FRAGMENT in line for line in lines[start - 1 : end])


def _refusing_names(scans: Sequence[_FileScan]) -> frozenset[str]:
    """Names a gated branch may call and still count as refusing.

    A private guard, or any function whose raise names a spec requirement.
    Both are the act of refusing, so neither is lost to a rename; a
    delegation to one of them is the shape ``_validate_canonical_entry``
    had, where the gated branch raised nothing itself.
    """
    found: set[str] = set()
    for scan in scans:
        for definition in scan.definitions:
            if not _may_raise(scan.lines, definition):
                continue
            raises = list(raises_in(definition))
            if not raises:
                continue
            if (
                is_private(definition.name) and not definition.decorator_list
            ) or any(cites_a_spec(node) for node in raises):
                found.add(definition.name)
    return frozenset(found)


def _subjects(
    scans: Sequence[_FileScan],
) -> tuple[tuple[Guard, ...], tuple[Gate, ...]]:
    """Both arms' subjects, from one pass over *scans*."""
    refusing = _refusing_names(scans)
    guards: list[Guard] = []
    gates: list[Gate] = []
    for scan in scans:
        for definition in scan.definitions:
            in_class = id(definition) in scan.methods
            if _may_raise(scan.lines, definition) and is_private_guard(
                definition
            ):
                guards.append(
                    Guard(
                        name=definition.name,
                        path=scan.path,
                        lineno=definition.lineno,
                        in_class=in_class,
                    )
                )
            # A dunder has no call site spelled by its name — ``__init__``'s
            # arguments are passed at ``ClassName(...)`` — so a gate in one
            # is invisible to the supply check rather than unsupplied.
            if definition.name.startswith("__"):
                continue
            # The gate pass gets no ``raise`` prefilter: the branch a
            # parameter opens may only *delegate* to a guard, which is the
            # shape ``_validate_canonical_entry`` had.  A ``None`` default
            # is the necessary condition instead, and reading it costs no
            # walk.
            if not none_defaulted_params(definition):
                continue
            for parameter, index in sorted(
                gated_params(definition, refusing).items()
            ):
                gates.append(
                    Gate(
                        name=definition.name,
                        path=scan.path,
                        lineno=definition.lineno,
                        parameter=parameter,
                        index=index,
                        in_class=in_class,
                    )
                )
    return tuple(guards), tuple(gates)


def _call_sites(
    scans: Iterable[_FileScan], wanted: frozenset[str]
) -> Mapping[str, tuple[CallSite, ...]]:
    """Every call of a name in *wanted* across *scans*, and what it passes."""
    sites: dict[str, list[CallSite]] = {}
    for scan in scans:
        for node in ast.walk(scan.tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _corpus.callee_name(node.func)
            if callee not in wanted:
                continue
            sites.setdefault(callee, []).append(
                CallSite(
                    path=scan.path,
                    lineno=_corpus.node_line(node),
                    keywords=frozenset(
                        keyword.arg
                        for keyword in node.keywords
                        if keyword.arg is not None
                    ),
                    double_starred=any(
                        keyword.arg is None for keyword in node.keywords
                    ),
                    positional_count=len(node.args),
                )
            )
    return {name: tuple(found) for name, found in sorted(sites.items())}


def _unsupplied(
    gates: Sequence[Gate], sites_by_name: Mapping[str, tuple[CallSite, ...]]
) -> frozenset[str]:
    """Gates no call site outside the definition itself supplies."""
    return frozenset(
        gate.site
        for gate in gates
        if not any(
            site.supplies(gate.parameter, gate.index)
            for site in sites_by_name.get(gate.name, ())
            if site.path != gate.path or site.lineno != gate.lineno
        )
    )


# ---------------------------------------------------------------------------
# The two entry points
# ---------------------------------------------------------------------------
def _relative(path: Path) -> str:
    return path.relative_to(_corpus.REPO_ROOT).as_posix()


@functools.cache
@_corpus.gc_paused()
def findings() -> Findings:
    """Both arms' subjects and violations for the whole package.

    Cached per process and derived with the collector paused: the walk
    allocates enough AST nodes that each collection threshold would
    otherwise cost a pass over the whole pytest heap
    (``notes/architecture-ratchet-corpus.md``).
    """
    scans = [
        _walk_module(_relative(path), _corpus.source_of(path), tree)
        for path, tree in _corpus.files_mentioning(
            RAISE_FRAGMENT, under=PACKAGE
        )
    ]
    guards, gates = _subjects(scans)

    # Arm A: a private guard is usually called in the module that defines
    # it, so start from what the walk already collected and parse further
    # files only for the handful of names that leaves unaccounted for.
    wanted = frozenset(guard.name for guard in guards)
    referenced = wanted & frozenset().union(
        *(scan.referenced for scan in scans), frozenset()
    )
    missing = wanted - referenced
    if missing:
        referenced |= frozenset().union(
            *(
                _walk_module(
                    _relative(path), _corpus.source_of(path), tree
                ).referenced
                for path, tree in _corpus.files_mentioning(
                    *sorted(missing), under=PACKAGE
                )
            ),
            frozenset(),
        )

    # Arm B: only the gated names are looked up, so the prefilter names a
    # few fragments rather than every guard in the package.
    gated = frozenset(gate.name for gate in gates)
    sites = (
        _call_sites(
            (
                _walk_module(_relative(path), _corpus.source_of(path), tree)
                for path, tree in _corpus.files_mentioning(
                    *sorted(gated), under=PACKAGE
                )
            ),
            gated,
        )
        if gated
        else {}
    )
    return Findings(
        guards=guards,
        gates=gates,
        unreached=frozenset(
            guard.site for guard in guards if guard.name not in referenced
        ),
        unsupplied=_unsupplied(gates, sites),
    )


def findings_in_source(source: str, path: str = "inline.py") -> Findings:
    """Both arms' subjects and violations for one inline module.

    The ratchet's synthetic detector tests drive the same judgement
    functions as :func:`findings` through this, so a detector change cannot
    pass its own tests while the package scan reads the code differently.
    """
    scan = _walk_module(path, source, _corpus.parse_inline(source, path))
    guards, gates = _subjects([scan])
    gated = frozenset(gate.name for gate in gates)
    return Findings(
        guards=guards,
        gates=gates,
        unreached=frozenset(
            guard.site for guard in guards if guard.name not in scan.referenced
        ),
        unsupplied=_unsupplied(gates, _call_sites([scan], gated)),
    )
