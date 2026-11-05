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
stays proportional to the match count (TB-13-002, TB-13-008).  The whole
derivation measures about 2.9 s with a warm corpus, above TB-13-004's 0.5 s
SHOULD and in the band of the heaviest existing ratchets (1–11 s); it is
cached per process, so one test pays it.

**Where it reads loosely.**  The derivation resolves names, not bindings, so
most of its imprecision lets a violation through rather than inventing one:

* **Names, not bindings.** A guard is matched by its bare name, so two
  same-named private guards in different modules share one another's
  references and call sites.  Resolving the binding would mean resolving
  every import in the package.
* **A self-call counts as a reference.** A guard whose only reference is its
  own recursive call reads as reached.
* **A splat supplies everything.** A ``*args`` or ``**kwargs`` call is a call
  the derivation cannot read, so it is given the benefit of the doubt.
* **A framework-invoked definition is out of both arms.** A decorator outside
  :data:`TRANSPARENT_DECORATORS` means something other than a call site runs
  the definition, so neither "no caller" nor "no caller supplied it" would be
  evidence of anything.
* **A module that refuses nothing is out of scope.** The file prefilter is
  the whole package's: a gate in a module with no ``raise `` anywhere, whose
  branch only delegates to a guard elsewhere, is never seen.  Dropping the
  file prefilter would double the derivation's cost for a shape that has no
  instance in the package today.

Some readings go the other way and **invent** a violation, which is the
direction that fails correct code and gets a ratchet switched off
(``notes/architecture-ratchet-corpus.md`` § "Say, Per Loose Reading, Whether
It Can Miss or Invent").  Three are narrowed:

* A parameter the body **rebinds** before testing it is no longer a gate on
  what the caller passed, so :func:`reassigned_names` drops it.
* A **method**'s positional index must be read as the caller writes it, not
  as the signature declares it, because the receiver is implicit;
  :func:`receiver_offset` does that, and leaves a ``@staticmethod`` alone.
* An **imported** name is a reference even where nothing else in the file
  spells it, so :func:`_walk_module` collects ``import`` aliases as well as
  loads.  Without that, a guard reached only through
  ``from x import _guard as guard`` reads as unreached.

The rest cannot be narrowed without resolving bindings or intent, so they are
stated here instead.  Each would surface as a *failure*, so the first reader
of a red arm needs to know they exist:

* **"Refusing" is wider than "refuses the caller's input."** :func:`_refuses`
  accepts any raise in the gated branch — an error translated in an
  ``except``, a ``NotImplementedError`` stub, a per-entry check of the
  optional payload — and any call to a name :func:`_refusing_names` collected.
  Some of arm B's subjects today are that shape rather than gates: an
  optional seeding step and a lookup whose value the branch returns, each a
  subject only because the callee raises somewhere of its own. They pass
  because a call site does supply the argument; were one removed, the arm
  would fail code that refuses nothing. Narrowing to a spec-citing callee was
  measured: it drops only some of them and costs over half the names
  :func:`_refusing_names` collects, so the width is reported rather than
  traded away (#5896).
* **A name in** :func:`_refusing_names` **is matched across the whole
  corpus.** A gated branch that calls some *other* binding of a name that a
  spec-citing raiser elsewhere happens to share reads as refusing, which
  invents a gate and, if no caller supplies the parameter, a violation.
* **A gate opened through an indirect reference is not read.**
  :func:`_call_sites` wants a literal call of the gate's own name, so
  ``functools.partial(_check, limit=5)``, an alias assignment, or a dispatch
  table supplies nothing as far as arm B can see — the opposite of the
  benefit of the doubt a splat gets, and of arm A, which accepts a bare
  reference.
* **A guard reached only by a string** — ``getattr(self, "_guard")()`` — has
  no name load to find, so it reads as unreached.  Collecting every string
  constant instead would make a guard named in prose read as reached, which
  the detector tests' prose case deliberately refuses.

Only the first has an instance in the package today, and it is green; the
other three have none — measured, not assumed, since both arms' baselines
are empty.  All four are tracked for narrowing in #5896; read them before
reading a red arm as a real dead guard.

Where arm B's call-site scope is production only, that is not imprecision: a
gate opened solely from ``test/`` is a check that never runs where it matters
(:func:`_sites_for`).

Spec: TB-16-001, TB-16-002 (the rule); TB-13-001, TB-13-002, TB-13-003,
TB-13-004 (the corpus) — ``specs/testability.yaml``.
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
    #: A ``*args`` or ``**kwargs`` splat: the call may carry anything, so it
    #: counts as supplying every parameter.  Failing a call the derivation
    #: cannot read would make the ratchet untrustworthy, and an untrusted
    #: ratchet gets switched off.
    splatted: bool
    positional_count: int

    def supplies(self, parameter: str, index: int | None) -> bool:
        """Whether this call passes *parameter*."""
        if parameter in self.keywords or self.splatted:
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


#: Decorators that leave a definition callable by its own name at a call
#: site, so a guard carrying one is still policed.  Everything else is taken
#: to register the definition somewhere — a Pydantic ``@field_validator`` is
#: run by the model, a ``@property`` by attribute access, a CLI command by its
#: framework — and requiring a call site for those would fail every one.  The
#: list is an allow-list on purpose: a decorator nobody here has seen yet is
#: excluded, which can only cost coverage, never invent a violation.
TRANSPARENT_DECORATORS: frozenset[str] = frozenset(
    {
        "staticmethod",
        "classmethod",
        "cache",
        "lru_cache",
        "cached_property",
        "contextmanager",
        "override",
        "final",
        "wraps",
    }
)


def is_transparently_decorated(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Whether every decorator on *fn* leaves it callable by name."""
    return all(
        decorator_name(decorator) in TRANSPARENT_DECORATORS
        for decorator in fn.decorator_list
    )


def decorator_name(decorator: ast.expr) -> str | None:
    """The bare name a decorator expression names.

    ``@cache`` and ``@functools.cache`` give ``cache``; ``@lru_cache()`` and
    ``@main.command()`` give the name their call invokes.
    """
    if isinstance(decorator, ast.Call):
        return _corpus.callee_name(decorator.func)
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    return None


def is_private_guard(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether *fn* is a private guard: private, callable by name, raising.

    Keyed on the act — refusing — and on visibility, not on a naming
    convention for validators, so renaming a guard keeps it in the subject
    set (``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the
    Act").

    A definition whose decorators are not all in
    :data:`TRANSPARENT_DECORATORS` is excluded: something other than a call
    site invokes it, so "no call site" is not evidence of anything.  A
    ``@staticmethod`` guard *is* reached by an ordinary call, so it stays in.
    """
    if not is_private(fn.name):
        return False
    if not is_transparently_decorated(fn):
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


def receiver_offset(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, *, in_class: bool
) -> int:
    """How many declared parameters a call site does not write.

    ``1`` for a bound method or a ``classmethod``, whose receiver the call
    passes implicitly, and ``0`` otherwise — including a ``@staticmethod``,
    which declares no receiver.  Without this, a positional call on a method
    (``self._check(1, 2)``) looks one argument short of the parameter it
    plainly supplies, and the ratchet invents a violation.
    """
    if not in_class:
        return 0
    names = {decorator_name(d) for d in fn.decorator_list}
    return 0 if "staticmethod" in names else 1


def none_defaulted_params(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, *, offset: int = 0
) -> dict[str, int | None]:
    """Each parameter of *fn* defaulting to ``None``, by call-site index.

    The index is where a *caller* would write the argument, so *offset* —
    :func:`receiver_offset` — is subtracted from the declared position.
    ``None`` as the index marks a keyword-only parameter, which no positional
    argument can reach.  A parameter without a ``None`` default is excluded:
    a caller cannot omit it, so it is always supplied.
    """
    arguments = fn.args
    positional = arguments.posonlyargs + arguments.args
    found: dict[str, int | None] = {}
    first_default = len(positional) - len(arguments.defaults)
    for order, (argument, default) in enumerate(
        zip(positional[first_default:], arguments.defaults, strict=True)
    ):
        if isinstance(default, ast.Constant) and default.value is None:
            found[argument.arg] = first_default + order - offset
    # ``kw_defaults`` carries ``None`` for a keyword-only parameter with no
    # default at all, which is why the element type is optional.
    for argument, kw_default in zip(
        arguments.kwonlyargs, arguments.kw_defaults, strict=True
    ):
        if isinstance(kw_default, ast.Constant) and kw_default.value is None:
            found[argument.arg] = None
    return found


def reassigned_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names *fn* rebinds in its own scope.

    A parameter the body reassigns before testing it is not a gate on what
    the caller passed: ``x = x or compute()`` makes ``if x is not None:``
    always true, so requiring a caller to supply ``x`` would invent a
    violation.
    """
    return {
        node.id
        for node in own_scope(fn)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }


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
    """Whether *body* raises, or calls a name in *refusing*.

    Scoped the way :func:`own_scope` scopes arm A: a raise inside a nested
    function the branch merely *defines* is that function's refusal, not the
    branch's, so it does not make the branch a gate.
    """
    for statement in body:
        for node in _own_scope_of(statement):
            if isinstance(node, ast.Raise) and node.exc is not None:
                return True
            if (
                isinstance(node, ast.Call)
                and _corpus.callee_name(node.func) in refusing
            ):
                return True
    return False


def _own_scope_of(statement: ast.AST) -> Iterator[ast.AST]:
    """*statement* and its descendants, stopping at a nested scope."""
    pending: list[ast.AST] = [statement]
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


def gated_params(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    refusing: frozenset[str],
    *,
    offset: int = 0,
) -> dict[str, int | None]:
    """Parameters of *fn* whose presence opens a refusal inside *fn*.

    This is the half of the rule that "a caller exists" misses.
    ``_validate_canonical_entry`` had a caller; what it did not have was a
    caller that passed ``case_published``, and the CLP-14-013 check sat
    behind ``if case_published is not None:`` (ISSUE-2824).  A parameter
    like that is the switch the check runs on.

    *offset* is :func:`receiver_offset`, so each index is where a caller
    writes the argument rather than where the signature declares it.
    """
    candidates = none_defaulted_params(fn, offset=offset)
    for name in reassigned_names(fn):
        candidates.pop(name, None)
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
    #: Every identifier loaded as a name or an attribute in the module, plus
    #: every name an ``import`` binds.  Importing a guard is a reference to
    #: it even where the module then spells only the alias, so without the
    #: import names a guard reached through ``from x import _g as g`` would
    #: read as unreached.
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
        elif isinstance(node, ast.alias):
            referenced.add(node.name.rpartition(".")[2])
            if node.asname is not None:
                referenced.add(node.asname)
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
                is_private(definition.name)
                and is_transparently_decorated(definition)
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
            # A definition something else invokes has no readable call site
            # either, so "no caller supplied it" would be unfixable: a
            # ``@main.command()`` with an optional gating parameter is the
            # shape (TRANSPARENT_DECORATORS).
            if not is_transparently_decorated(definition):
                continue
            offset = receiver_offset(definition, in_class=in_class)
            # The gate pass gets no ``raise`` prefilter: the branch a
            # parameter opens may only *delegate* to a guard, which is the
            # shape ``_validate_canonical_entry`` had.  A ``None`` default
            # is the necessary condition instead, and reading it costs no
            # walk.
            if not none_defaulted_params(definition, offset=offset):
                continue
            for parameter, index in sorted(
                gated_params(definition, refusing, offset=offset).items()
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
    trees: Iterable[tuple[str, ast.AST]], wanted: frozenset[str]
) -> Mapping[str, tuple[CallSite, ...]]:
    """Every call of a name in *wanted* across *trees*, and what it passes.

    Takes bare ``(path, tree)`` pairs rather than a ``_FileScan``: this pass
    needs no definitions, methods or references, and building a full scan for
    each of the ~100 files naming a gated name was a second of duplicate
    walking.
    """
    sites: dict[str, list[CallSite]] = {}
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _corpus.callee_name(node.func)
            if callee not in wanted:
                continue
            sites.setdefault(callee, []).append(
                CallSite(
                    path=path,
                    lineno=_corpus.node_line(node),
                    keywords=frozenset(
                        keyword.arg
                        for keyword in node.keywords
                        if keyword.arg is not None
                    ),
                    splatted=any(
                        keyword.arg is None for keyword in node.keywords
                    )
                    or any(
                        isinstance(argument, ast.Starred)
                        for argument in node.args
                    ),
                    positional_count=len(node.args),
                )
            )
    return {name: tuple(found) for name, found in sorted(sites.items())}


def _sites_for(
    gates: Sequence[Gate],
) -> Mapping[str, tuple[CallSite, ...]]:
    """Call sites of every gated name under ``vultron/``.

    Production only, deliberately: a gate opened solely from ``test/`` is a
    check that never runs where it matters, which is the defect this arm
    exists to report, not a false positive.
    """
    gated = frozenset(gate.name for gate in gates)
    if not gated:
        return {}
    return _call_sites(
        (
            (_relative(path), tree)
            for path, tree in _corpus.files_mentioning(
                *sorted(gated), under=PACKAGE
            )
        ),
        gated,
    )


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


def referenced_among(
    wanted: frozenset[str], scans: Sequence[_FileScan]
) -> frozenset[str]:
    """Which of *wanted* any module under the package references.

    A private guard is usually named in the module that defines it, so this
    starts from what the corpus walk already collected and parses further
    files only for the handful of names that leaves unaccounted for.

    This is the one step :func:`findings_in_source` cannot drive — it reads a
    single module's references directly — so it is tested here rather than
    through a synthetic module.  Arm A covers the positive direction already:
    guards clear only through the second pass, so an empty baseline means it
    resolves.  What no other test would notice is this answering *yes* to
    everything, which would make arm A pass vacuously while every test in the
    ratchet stayed green (#5535), hence
    ``test_the_reference_search_answers_no_for_a_name_nothing_mentions``.
    """
    referenced = wanted & frozenset().union(
        *(scan.referenced for scan in scans), frozenset()
    )
    missing = wanted - referenced
    if not missing:
        return referenced
    return referenced | (
        wanted
        & frozenset().union(
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
    )


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

    referenced = referenced_among(
        frozenset(guard.name for guard in guards), scans
    )

    return Findings(
        guards=guards,
        gates=gates,
        unreached=frozenset(
            guard.site for guard in guards if guard.name not in referenced
        ),
        unsupplied=_unsupplied(gates, _sites_for(gates)),
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
    sites = _call_sites([(scan.path, scan.tree)], gated)
    return Findings(
        guards=guards,
        gates=gates,
        unreached=frozenset(
            guard.site for guard in guards if guard.name not in scan.referenced
        ),
        unsupplied=_unsupplied(gates, sites),
    )
