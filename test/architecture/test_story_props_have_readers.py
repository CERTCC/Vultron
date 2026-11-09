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

"""Architecture invariant (DEMOMA-22-014 through DEMOMA-22-019): every story
prop is declared once as a named constant, kept by a step and read by a step,
and the step that reads one is told which.

A :class:`~vultron.demo.helpers.story.StoryProp` is how a composed scenario
carries a causal gate through a flat sequence: the fragment that performs an
act keeps the prop inside the act's own ``demo_gate``, and the fragment that
depends on that act reads the prop first, so a failed act stops the story
(DEMOCI-01-011, ``notes/demo-scenario-tree.md`` § "Composition").

**Keeping a prop carries no guarantee.**  ``SECOND_COORDINATOR_JOINED`` was
kept by the roster gate and read by nobody, which dropped the guard that
skipped ``rccv-handoff``'s ownership transfer when the roster never filled.
Every unit, architecture and integration test passed and the recording was
unchanged; a human-style read of the composed fragment against the
hand-placed form it replaced is what caught it (#5535).  Two mutations were
still silent after that fix: relaxing a continuation's required keyword back
to ``joined: StoryProp[str] | None = None`` behind an ``if joined is not
None:`` guard left the whole suite green, because every call site happens to
pass the prop; and a brand-new prop kept and read by nobody was flagged by
nothing at all (#5598).

The subject is therefore **every prop construction under ``vultron/demo/``**,
found by the ``StoryProp(...)`` call rather than by the name of any module or
family that declares one, so a rename or a module split moves no subject out
of the scan (``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the
Act, Not on the Name of What Performs It").  Subpackages are covered by
construction: the scan walks every module under ``vultron/demo/``, so a prop
declared in a package a split created is found without an edit here
(#5592).  The arms assert their own subjects are non-empty, so none of them
can pass over an empty corpus (DF-09-009's shape).

Three shapes of site are recognised, because all three are live:

* **outright** — ``state.keep(PROP, value)`` and ``state.kept(PROP)`` naming
  the prop constant;
* **through a parameter** — the prop handed to a step as ``joined=PROP``,
  where that step's ``joined`` parameter is one it keeps or reads, directly or
  through any chain of forwarding wrappers.  This is the shape the #5535 fix
  introduced, and it is what makes a continuation's precondition structural
  rather than remembered;
* **through an alias** — the name a keep or a call site reaches the prop by is
  not the constant's own: a local binding, a ``for`` target over a collection
  of props (``rv``'s note pair), a module-level rename or an
  ``import ... as``.

Loose readings, with the direction each one errs in
(``notes/architecture-ratchet-corpus.md`` § "Say, Per Loose Reading, Whether
It Can Miss or Invent").  Every reading below can only **miss** a violation,
and none can be narrowed without resolving bindings; the arms that could
*invent* one — fail correct code — were removed rather than documented, since
a red arm on correct code is what gets a ratchet switched off (#5598):

* ``keep`` / ``kept`` are matched on the attribute name, whatever the
  receiver, so another object's ``keep`` whose first argument names a
  declared prop would be counted as a keep site.
* A call site is matched by its callee's bare name, so two functions that
  share a name share their prop-parameter roles: a prop passed as ``joined=``
  to a same-named function that does not read it reads as read.
* Sites are flat sets of bare identifiers, intersected with the declared
  constants' identifiers, so two modules declaring the same identifier
  cross-credit each other: a prop touched by nobody is hidden when a
  same-named one elsewhere is kept and read.  DEMOMA-22-019 forbids two
  declarations spelling one *declared name*, not one *constant*, so the shape
  is legal; narrowing it means keying every site on the declaring module and
  its importers.
* An alias is followed by name rather than by binding, so a name rebound
  between the alias and the site still resolves to the first binding's props.
* The annotation that marks a prop parameter is matched on the identifiers it
  spells, so a module that aliased the class under another name would have
  its parameters unchecked.

One arm is deliberately strict rather than loose: a ``StoryProp(...)`` call
that is not a module-level assignment to a single name, or whose declared
name is not a string literal, is reported (DEMOMA-22-018).  That is what makes
the enumeration complete rather than best-effort — every construction under
``vultron/demo/`` is then either a subject the other arms reach or a failure
of this one — and a prop built any other way is named by no site, which is
how every family declares one.

The derivation runs once at import time, outside the per-test timeout, and
costs about 0.8 s over the two prefilter rounds; each test then reads the
result and measures under 5 ms, within TB-13-004's budget.

Spec: DEMOMA-22-014 through DEMOMA-22-019, DEMOCI-01-011, TB-13-001,
TB-13-002.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

import pytest

from test.architecture import _corpus

#: Every module a demo story is written in: the shared families under
#: ``helpers/`` and the scenarios' own modules, packages included.
_DEMO_DIR = _corpus.REPO_ROOT / "vultron/demo"

#: The class a prop is an instance of.  The scan's subject is this call, not
#: the name of whatever declares it.
_PROP_CLASS = "StoryProp"

#: The two state methods that write and read a prop (``helpers/story/state``).
_KEEP, _READ = "keep", "kept"

#: The definitions the parameter scan skips: ``StoryState.keep`` and
#: ``StoryState.kept`` themselves, which take a prop positionally and are the
#: primitives every site calls rather than steps of a story.  A **pinned
#: exemption set**, not a ratchet — it has no terminal value, because the
#: methods are what the whole mechanism is made of (ARCH-18-005, ARCH-18-010).
#: :func:`test_the_state_primitives_are_the_only_definitions_excluded` pins it
#: in both directions, so a step that happened to be named after one is
#: reported rather than silently skipped.
# permanent: DEMOMA-22-014 — the two StoryState methods in
# vultron/demo/helpers/story/state.py, which every site calls.
_PRIMITIVE_DEFINITION_EXEMPTIONS = frozenset({_KEEP, _READ})

#: The fragments that seed the file prefilter (TB-13-002).  The call sites
#: that hand a prop to a step mention neither the class nor the methods, so
#: they are reached by a second prefilter on the declared constants' own names
#: (:func:`_live_files`).
_SEED_FRAGMENTS = (_PROP_CLASS, f".{_KEEP}(", f".{_READ}(")

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

# ---------------------------------------------------------------------------
# What the scan finds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PropDeclaration:
    """One module-level ``StoryProp`` declaration."""

    #: The module constant it is bound to, which is how every site names it.
    constant: str
    #: The declared name :class:`StoryState` keys the artifact under, or
    #: ``None`` when the construction did not give one as a string literal.
    label: str | None
    #: ``<module>::<constant>``, for the failure message.
    where: str


@dataclass(frozen=True)
class PropParameter:
    """A step's parameter that is handed a prop by its caller."""

    where: str
    function: str
    parameter: str
    #: Whether the step reads the prop it is handed (``state.kept(param)``).
    reads: bool
    #: Whether the step keeps under it (``state.keep(param, value)``).
    keeps: bool
    keyword_only: bool
    has_default: bool
    #: Whether the annotation admits ``None`` at its top level.
    optional: bool
    #: Whether it is a ``*args`` or ``**kwargs`` slot, which no caller can
    #: name and which therefore cannot be keyword-only.
    starred: bool = False


@dataclass
class PropSites:
    """Every prop declared under the scanned files, and what touches each."""

    declarations: tuple[PropDeclaration, ...] = ()
    parameters: tuple[PropParameter, ...] = ()
    #: Constants a ``state.keep`` call names, outright or through an alias.
    direct_keeps: frozenset[str] = frozenset()
    #: Constants a ``state.kept`` call names, outright or through an alias.
    direct_reads: frozenset[str] = frozenset()
    #: Constants handed to a keeping / reading prop parameter by a caller.
    passed_keeps: frozenset[str] = frozenset()
    passed_reads: frozenset[str] = frozenset()
    #: The subset of :attr:`direct_keeps` an alias carried, rather than the
    #: keep call naming the constant itself (``rv``'s note pair).
    aliased_keeps: frozenset[str] = frozenset()
    #: ``StoryProp(...)`` calls that are no module-level declaration.
    strays: tuple[str, ...] = ()
    #: Declarations whose name is not a string literal, so no site, message
    #: or collision check can read what the artifact is called.
    unnamed: tuple[str, ...] = ()
    #: The ``keep`` / ``kept`` definitions excluded as the primitives.
    primitives: tuple[str, ...] = ()
    #: Declaring modules, repo-relative, for the subpackage-coverage arm.
    modules: frozenset[str] = frozenset()

    @property
    def constants(self) -> frozenset[str]:
        return frozenset(found.constant for found in self.declarations)

    @property
    def keeps(self) -> frozenset[str]:
        return (
            self.direct_keeps | self.passed_keeps | self.aliased_keeps
        ) & self.constants

    @property
    def reads(self) -> frozenset[str]:
        return (self.direct_reads | self.passed_reads) & self.constants

    def without_a_keeper(self) -> list[str]:
        return sorted(
            found.where
            for found in self.declarations
            if found.constant not in self.keeps
        )

    def without_a_reader(self) -> list[str]:
        return sorted(
            found.where
            for found in self.declarations
            if found.constant not in self.reads
        )

    def collisions(self) -> dict[str, list[str]]:
        """Declared names bound by more than one construction, each with its
        sites."""
        by_label: dict[str, list[str]] = {}
        for found in self.declarations:
            if found.label is None:
                # Reported by :attr:`unnamed` instead; grouping them here
                # would read as one collision among every such declaration.
                continue
            by_label.setdefault(found.label, []).append(found.where)
        return {
            label: sorted(where)
            for label, where in by_label.items()
            if len(where) > 1
        }

    @property
    def readers(self) -> tuple[PropParameter, ...]:
        return tuple(found for found in self.parameters if found.reads)

    @property
    def keepers(self) -> tuple[PropParameter, ...]:
        return tuple(found for found in self.parameters if found.keeps)

    @property
    def starred(self) -> tuple[PropParameter, ...]:
        return tuple(found for found in self.parameters if found.starred)


# ---------------------------------------------------------------------------
# AST readings
# ---------------------------------------------------------------------------


#: The typing spellings whose argument list admits ``None``.
_OPTIONAL_WRAPPERS = frozenset({"Optional", "Union"})


def _is_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _is_optional(annotation: ast.expr | None) -> bool:
    """True when *annotation* lets a caller hand the step nothing.

    ``X | None``, ``Optional[X]`` and ``Union[X, None]`` all count: each one
    makes the prop a parameter the caller may omit in effect, which is the
    relaxation that made the #5535 mutation silent.

    Read at the **top level only**.  The obligation is on the parameter, not
    on its type argument, so walking the whole subtree would report
    ``joined: StoryProp[str | None]`` — a prop whose artifact may be
    ``None`` — as an optional parameter, failing correct code.
    """
    if annotation is None:
        return False
    if isinstance(annotation, ast.Constant) and isinstance(
        annotation.value, str
    ):
        # A quoted annotation, re-read as the expression it spells so the
        # same top-level reading applies (``_corpus.trailing_names``'s
        # tokenising answers a different question).
        try:
            inner = _corpus.parse_inline(annotation.value, "<annotation>")
        except SyntaxError:
            return False
        body = getattr(inner, "body", None)
        first = body[0] if body else None
        return _is_optional(getattr(first, "value", None))
    if isinstance(annotation, ast.BinOp) and isinstance(
        annotation.op, ast.BitOr
    ):
        return (
            _is_none(annotation.left)
            or _is_none(annotation.right)
            or _is_optional(annotation.left)
            or _is_optional(annotation.right)
        )
    if isinstance(annotation, ast.Subscript):
        wrapper = _corpus.callee_name(annotation.value)
        if wrapper not in _OPTIONAL_WRAPPERS:
            return False
        if wrapper == "Optional":
            return True
        elements = annotation.slice
        return isinstance(elements, ast.Tuple) and any(
            _is_none(element) for element in elements.elts
        )
    return False


def _method_calls(scope: ast.AST, method: str) -> Iterator[ast.Call]:
    """Every call in *scope* whose callee is an attribute named *method*."""
    for node in ast.walk(scope):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == method
        ):
            yield node


#: ``StoryProp``'s first field, which may be given either way.
_NAME_FIELD = "name"


def _first_argument(call: ast.Call) -> ast.expr | None:
    """*call*'s first positional argument, or ``None`` when it has none."""
    return call.args[0] if call.args else None


def _declared_name(call: ast.Call) -> str | None:
    """The string literal *call* gives as the prop's declared name.

    Reads the keyword form too: ``StoryProp(name="x", type_=str)`` is the
    same declaration as ``StoryProp("x", str)``, and reading only the
    positional slot would fall back to the constant's own identifier — which
    makes two declarations spelling one name look like two names (#5598).
    ``None`` when the name is not a string literal, which the caller reports
    rather than guessing at.
    """
    given = _first_argument(call)
    if given is None:
        given = next(
            (kw.value for kw in call.keywords if kw.arg == _NAME_FIELD), None
        )
    if isinstance(given, ast.Constant) and isinstance(given.value, str):
        return given.value
    return None


def _parameter_names(fn: _FunctionNode) -> frozenset[str]:
    """Every parameter name *fn* declares, starred ones included."""
    return frozenset(arg.arg for arg in _corpus.parameters_of(fn))


def _module_constants(
    tree: ast.AST,
) -> Iterator[tuple[ast.Name, ast.expr | None]]:
    """Each module-level assignment of one name, as ``(name, value)``.

    A tuple target or a chained assignment is not a declaration: a prop is
    bound to one name, which is how every site names it.
    """
    if not isinstance(tree, ast.Module):
        return
    for statement in tree.body:
        target: ast.expr
        value: ast.expr | None
        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1:
                continue
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign):
            target, value = statement.target, statement.value
        else:
            continue
        if isinstance(target, ast.Name):
            yield target, value


def _bindings(scope: ast.AST) -> Iterator[tuple[ast.expr, ast.expr | None]]:
    """Every ``(target, value)`` pair *scope* binds, however it binds it."""
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                yield target, node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            yield node.target, node.value
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            yield node.target, node.iter
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    yield item.optional_vars, item.context_expr


def _alias_map(fn: _FunctionNode) -> dict[str, frozenset[str]]:
    """Local names bound in *fn*, each to the identifiers it was bound from.

    Followed by name rather than by binding, which is what lets the scan read
    ``rv``'s note pair: two props go into a local tuple and a ``for`` target
    carries each into ``state.keep``.  A ``for`` target tuple maps each of its
    names to the whole iterable, which is wider than the real binding and can
    only add candidates the declaration set then filters out.
    """
    aliases: dict[str, set[str]] = {}
    for target, value in _bindings(fn):
        names = _corpus.trailing_names(value)
        if not names:
            continue
        elements = (
            target.elts
            if isinstance(target, (ast.Tuple, ast.List))
            else [target]
        )
        for element in elements:
            if isinstance(element, ast.Name):
                aliases.setdefault(element.id, set()).update(names)
    return {name: frozenset(sources) for name, sources in aliases.items()}


def _resolve(
    expression: ast.expr | None,
    aliases: dict[str, frozenset[str]],
    parameters: frozenset[str],
) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """Resolve *expression* to the constants and parameters it can name.

    Returns ``(constants named outright, parameters named, constants reached
    through a local alias)``.  The third set is separate from the first so
    each site shape can assert its own subjects.
    """
    aliased = frozenset(aliases)
    outright = _corpus.trailing_names(expression)
    constants = outright - parameters - aliased
    named_parameters: set[str] = set(outright & parameters)
    through_alias: set[str] = set()
    frontier: set[str] = set((outright & aliased) - parameters)
    #: Followed to a fixed point rather than to a depth cap.  A cap would make
    #: a chain longer than it read as unkept, which is the one direction this
    #: scan must not err in: it would fail correct code.  ``seen`` grows by the
    #: whole frontier each round and is bounded by the alias map, so the loop
    #: terminates on a cyclic binding as well as an acyclic one.
    seen: set[str] = set(frontier)
    while frontier:
        reached = frozenset(
            source for name in frontier for source in aliases.get(name, ())
        )
        named_parameters |= reached & parameters
        through_alias |= reached - parameters - aliased
        frontier = set((reached & aliased) - parameters - seen)
        seen |= frontier
    return constants, frozenset(named_parameters), frozenset(through_alias)


# ---------------------------------------------------------------------------
# The derivation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RawParameter:
    """A prop parameter as the signature declares it, before the roles run."""

    where: str
    function: str
    parameter: str
    keyword_only: bool
    has_default: bool
    optional: bool
    starred: bool
    keeps: bool
    reads: bool


@dataclass
class _Accumulator:
    declarations: list[PropDeclaration] = field(default_factory=list)
    raw_parameters: list[_RawParameter] = field(default_factory=list)
    direct_keeps: set[str] = field(default_factory=set)
    direct_reads: set[str] = field(default_factory=set)
    aliased_keeps: set[str] = field(default_factory=set)
    strays: list[str] = field(default_factory=list)
    unnamed: list[str] = field(default_factory=list)
    primitives: list[str] = field(default_factory=list)
    modules: set[str] = field(default_factory=set)
    #: ``(callee name, parameter) -> (keeps, reads)`` for every prop parameter.
    roles: dict[tuple[str, str], tuple[bool, bool]] = field(
        default_factory=dict
    )
    #: ``(function, its parameter, callee, that callee's keyword)`` for every
    #: call that forwards a parameter on.  The role fixed point reads these.
    forwardings: set[tuple[str, str, str, str]] = field(default_factory=set)
    #: ``function -> (positional parameter names in order, its ``*args``
    #: name)``, so a call site can name the slot a positional argument
    #: reaches.  A prop parameter must be keyword-only, so this only ever
    #: resolves a call into code that already fails that arm — without it,
    #: such a call would also report the prop as touched by nobody, which
    #: would be a second and false failure.
    signatures: dict[str, tuple[tuple[str, ...], str | None]] = field(
        default_factory=dict
    )


def _read_declarations(module: str, tree: ast.AST, into: _Accumulator) -> None:
    """Collect *module*'s prop declarations, and report any other prop call."""
    declared: set[int] = set()
    for target, value in _module_constants(tree):
        if not isinstance(value, ast.Call):
            continue
        if _corpus.callee_name(value.func) != _PROP_CLASS:
            continue
        declared.add(id(value))
        label = _declared_name(value)
        where = f"{module}::{target.id}"
        if label is None:
            into.unnamed.append(where)
        into.declarations.append(
            PropDeclaration(constant=target.id, label=label, where=where)
        )
        into.modules.add(module)
    for call in ast.walk(tree):
        if (
            isinstance(call, ast.Call)
            and _corpus.callee_name(call.func) == _PROP_CLASS
            and id(call) not in declared
        ):
            into.strays.append(f"{module}:{_corpus.node_line(call)}")


def _module_alias_map(source: str) -> dict[str, frozenset[str]]:
    """Module-level renames of one name to another, as the alias map shape.

    Both shapes a site may reach a prop through without naming its constant:
    ``ALIAS = ORIGINAL`` at module level, and ``from m import P as JOINED``.
    Read through ``_corpus.aliases`` rather than a second reading of its own
    (CS-22-001).
    """
    found: dict[str, set[str]] = {}
    for alias, original in _corpus.aliases(source):
        found.setdefault(alias, set()).add(original)
    return {alias: frozenset(names) for alias, names in found.items()}


def _read_sites(
    module: str, source: str, tree: ast.AST, into: _Accumulator
) -> None:
    """Collect *module*'s keep and read sites, direct and by parameter."""
    module_aliases = _module_alias_map(source)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name in _PRIMITIVE_DEFINITION_EXEMPTIONS:
            # The primitive itself, which every site calls and which no
            # caller hands a prop by keyword.  Named the same way the sites
            # name it, so a rename of the method moves this with them.
            into.primitives.append(f"{module}::{fn.name}")
            continue
        parameters = _parameter_names(fn)
        aliases = module_aliases | _alias_map(fn)
        kept_parameters: set[str] = set()
        read_parameters: set[str] = set()
        for method, sink, by_parameter in (
            (_KEEP, into.direct_keeps, kept_parameters),
            (_READ, into.direct_reads, read_parameters),
        ):
            for call in _method_calls(fn, method):
                constants, named, through_alias = _resolve(
                    _first_argument(call), aliases, parameters
                )
                sink.update(constants | through_alias)
                if method == _KEEP:
                    # Recorded separately so the alias shape can assert its
                    # own subject; the read side has no live aliased subject,
                    # and one arm per live shape is what keeps a shape from
                    # retiring unnoticed.
                    into.aliased_keeps.update(through_alias)
                by_parameter.update(named)
        _record_parameters(module, fn, kept_parameters, read_parameters, into)
        _record_forwardings(fn, parameters, into)


def _record_parameters(
    module: str,
    fn: _FunctionNode,
    kept: set[str],
    read: set[str],
    into: _Accumulator,
) -> None:
    """Record each parameter of *fn* annotated as a prop, with its shape."""
    defaulted = _corpus.defaulted_parameters(fn)
    keyword_only = {arg.arg for arg in fn.args.kwonlyargs}
    starred = {
        arg.arg for arg in (fn.args.vararg, fn.args.kwarg) if arg is not None
    }
    into.signatures[fn.name] = (
        tuple(arg.arg for arg in (*fn.args.posonlyargs, *fn.args.args)),
        fn.args.vararg.arg if fn.args.vararg is not None else None,
    )
    for arg in _corpus.parameters_of(fn):
        if _PROP_CLASS not in _corpus.trailing_names(arg.annotation):
            continue
        reads, keeps = arg.arg in read, arg.arg in kept
        into.raw_parameters.append(
            _RawParameter(
                # Qualified by line, so two same-named nested definitions in
                # one module are distinguishable in the failure message.
                where=f"{module}:{_corpus.node_line(fn)}::{fn.name}",
                function=fn.name,
                parameter=arg.arg,
                keyword_only=arg.arg in keyword_only,
                has_default=arg.arg in defaulted,
                optional=_is_optional(arg.annotation),
                starred=arg.arg in starred,
                keeps=keeps,
                reads=reads,
            )
        )


def _record_forwardings(
    fn: _FunctionNode, parameters: frozenset[str], into: _Accumulator
) -> None:
    """Record each call in *fn* that hands one of *fn*'s parameters on.

    A wrapper that only forwards ``joined=joined`` keeps and reads nothing
    itself, so without this its own callers' ``joined=PROP`` would be
    attributed to no role and the prop would read as touched by nobody — a
    composition helper reddening the gate.  :func:`_settle_roles` closes the
    chain.
    """
    for call in ast.walk(fn):
        if not isinstance(call, ast.Call):
            continue
        callee = _corpus.callee_name(call.func)
        if callee is None:
            continue
        for keyword in call.keywords:
            if keyword.arg is None or not isinstance(keyword.value, ast.Name):
                continue
            if keyword.value.id in parameters:
                into.forwardings.add(
                    (fn.name, keyword.value.id, callee, keyword.arg)
                )


def _settle_roles(into: _Accumulator) -> None:
    """Seed the roles from the direct sites, then follow every forwarding.

    A fixed point, because a wrapper may forward to a wrapper.  It terminates
    because a role only ever gains, and both flags are bounded.
    """
    for raw in into.raw_parameters:
        if not (raw.keeps or raw.reads):
            continue
        keeping, reading = into.roles.get(
            (raw.function, raw.parameter), (False, False)
        )
        into.roles[(raw.function, raw.parameter)] = (
            keeping or raw.keeps,
            reading or raw.reads,
        )
    changed = True
    while changed:
        changed = False
        for function, parameter, callee, keyword in into.forwardings:
            downstream = into.roles.get((callee, keyword))
            if downstream is None:
                continue
            keeping, reading = into.roles.get(
                (function, parameter), (False, False)
            )
            settled = (keeping or downstream[0], reading or downstream[1])
            if settled != (keeping, reading):
                into.roles[(function, parameter)] = settled
                changed = True


def _read_call_sites(
    module: str, source: str, tree: ast.AST, into: _Accumulator
) -> tuple[frozenset[str], frozenset[str]]:
    """Return the constants *module* hands to a keeping / reading parameter.

    Each argument is matched to the parameter it reaches
    (:func:`_slots`) and its value resolved through the aliases in scope, so
    a call site that hands over a local name, a module constant or an
    ``import ... as`` name is a site like any other rather than a prop
    nothing touches.
    """
    module_aliases = _module_alias_map(source)
    scopes: list[tuple[ast.AST, dict[str, frozenset[str]]]] = [
        (tree, module_aliases)
    ]
    scopes.extend(
        (node, module_aliases | _alias_map(node))
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    keeps: set[str] = set()
    reads: set[str] = set()
    for scope, aliases in scopes:
        for call in ast.walk(scope):
            if not isinstance(call, ast.Call):
                continue
            for keeping, reading, handed in _handed_over(call, aliases, into):
                if keeping:
                    keeps.update(handed)
                if reading:
                    reads.update(handed)
    return frozenset(keeps), frozenset(reads)


def _slots(
    call: ast.Call, callee: str, into: _Accumulator
) -> Iterator[tuple[str, ast.expr]]:
    """``(parameter name, argument)`` per argument of *call* whose slot is
    known.

    Keywords name their slot outright.  A positional argument names the
    parameter at its index, or the ``*args`` parameter once the declared
    positionals run out: a prop parameter must be keyword-only, so a
    positional one is already failing that arm, and reading it here is what
    stops the same code from *also* reporting its prop as touched by nobody.
    """
    for keyword in call.keywords:
        if keyword.arg is not None:
            yield keyword.arg, keyword.value
    positionals, vararg = into.signatures.get(callee, ((), None))
    for index, argument in enumerate(call.args):
        if index < len(positionals):
            yield positionals[index], argument
        elif vararg is not None:
            yield vararg, argument


def _handed_over(
    call: ast.Call, aliases: dict[str, frozenset[str]], into: _Accumulator
) -> Iterator[tuple[bool, bool, frozenset[str]]]:
    """``(keeping, reading, constants)`` per argument of *call* with a role."""
    callee = _corpus.callee_name(call.func)
    if callee is None:
        return
    for parameter, value in _slots(call, callee, into):
        role = into.roles.get((callee, parameter))
        if role is None:
            continue
        constants, _, through_alias = _resolve(value, aliases, frozenset())
        yield role[0], role[1], constants | through_alias


def story_prop_sites(
    files: Iterable[tuple[str, str, ast.AST]],
) -> PropSites:
    """Every prop the given modules declare, and every site that touches it.

    *files* is ``(module label, source, tree)`` triples — the live corpus
    from :func:`_live_files`, or inline sources a planted-violation test
    parses with ``_corpus.parse_inline``.  The passes run in order because
    each one needs the one before it: the declarations name the constants,
    the signature scan finds the prop parameters, the role pass settles what
    each one keeps or reads through any chain of forwarding wrappers, and
    only then can the call-site scan read a keyword.
    """
    scanned = list(files)
    into = _Accumulator()
    for module, _, tree in scanned:
        _read_declarations(module, tree, into)
    for module, source, tree in scanned:
        _read_sites(module, source, tree, into)
    _settle_roles(into)
    passed_keeps: set[str] = set()
    passed_reads: set[str] = set()
    for module, source, tree in scanned:
        keeps, reads = _read_call_sites(module, source, tree, into)
        passed_keeps |= keeps
        passed_reads |= reads
    roles = into.roles
    return PropSites(
        declarations=tuple(into.declarations),
        parameters=tuple(
            PropParameter(
                where=raw.where,
                function=raw.function,
                parameter=raw.parameter,
                reads=roles.get((raw.function, raw.parameter), (False, False))[
                    1
                ],
                keeps=roles.get((raw.function, raw.parameter), (False, False))[
                    0
                ],
                keyword_only=raw.keyword_only,
                has_default=raw.has_default,
                optional=raw.optional,
                starred=raw.starred,
            )
            for raw in into.raw_parameters
        ),
        direct_keeps=frozenset(into.direct_keeps),
        direct_reads=frozenset(into.direct_reads),
        passed_keeps=frozenset(passed_keeps),
        passed_reads=frozenset(passed_reads),
        aliased_keeps=frozenset(into.aliased_keeps),
        strays=tuple(into.strays),
        unnamed=tuple(into.unnamed),
        primitives=tuple(into.primitives),
        modules=frozenset(into.modules),
    )


def _demo_files(*fragments: str) -> Iterator[tuple[str, tuple[str, ast.AST]]]:
    """``(module, (source, tree))`` for demo files mentioning a fragment.

    The source comes with the tree because the alias readings need the text
    (``_corpus.aliases``); both are the corpus's cached copies, read once at
    import time (TB-13-001).
    """
    if not fragments:
        return
    for path, tree in _corpus.files_mentioning(*fragments, under=_DEMO_DIR):
        module = path.relative_to(_corpus.REPO_ROOT).as_posix()
        yield module, (_corpus.source_of(path), tree)


def _flatten(
    found: dict[str, tuple[str, ast.AST]],
) -> list[tuple[str, str, ast.AST]]:
    return [
        (module, source, tree)
        for module, (source, tree) in sorted(found.items())
    ]


def _live_files() -> list[tuple[str, str, ast.AST]]:
    """Every demo module the scan must read, prefiltered in two rounds.

    The first round takes the modules that mention the class or either state
    method.  Those hold the declarations, so the second round can prefilter on
    the constants' own names and reach the scenario modules that hand a prop
    to a step while mentioning neither (TB-13-002, TB-13-008).  The corpus
    caches each parse, so a module both rounds select is parsed once.
    """
    found = dict(_demo_files(*_SEED_FRAGMENTS))
    constants = story_prop_sites(_flatten(found)).constants
    found.update(_demo_files(*sorted(constants)))
    return _flatten(found)


#: Derived once at import time, outside the per-test timeout (TB-13-001).
with _corpus.gc_paused():
    _SITES = story_prop_sites(_live_files())


# ---------------------------------------------------------------------------
# The corpus the arms run against is real
# ---------------------------------------------------------------------------


def _assert_declarations_found(sites: PropSites) -> None:
    """Fail unless props were found in both halves and in a subpackage.

    A function rather than a test body so
    :func:`test_an_empty_corpus_fails_the_non_vacuity_arm` can hand it a
    corpus with no subjects and pin that it fails (DF-09-009's shape: a gate
    that resolves zero targets must fail, not pass).
    """
    assert sites.declarations, (
        "no StoryProp construction was found under vultron/demo/, so every "
        "arm of this ratchet would pass vacuously: either the declarations "
        f"have moved out of {_DEMO_DIR.name}/ or {_PROP_CLASS!r} was renamed"
    )
    # Read off the observed modules rather than against the directory names
    # the tree happens to use today, so renaming either half of
    # ``vultron/demo/`` moves no subject out of the check and reddens
    # nothing.
    halves = {module.split("/")[2] for module in sites.modules}
    assert len(halves) > 1, (
        f"props are declared only under {sorted(halves)}; the scan must "
        "reach both the shared families and the scenarios' own modules, "
        "which are two different directories of vultron/demo/"
    )
    nested = [module for module in sites.modules if module.count("/") > 3]
    assert nested, (
        "every prop is declared in a flat module, so a walk that skipped "
        "packages would still pass; the scan must read a module of a "
        "subpackage (#5592)"
    )


def test_the_scan_finds_props_in_both_halves_and_in_a_subpackage() -> None:
    """The enumeration reaches the shared families and the scenarios' own.

    Every arm below asserts an absence, so each is worth only what the scan
    reaches.  A prop lives in one of three places: a helper module, a module
    of a helper package a split created, or a scenario's own module or
    package (#5592).  Asserted structurally rather than as a list of modules,
    so a rename or a further split moves no subject out of the check.
    """
    _assert_declarations_found(_SITES)


def _assert_site_shapes_live(sites: PropSites) -> None:
    """Fail unless each shape of keep and read site has a live subject.

    A function for the same reason as :func:`_assert_declarations_found`.
    ``aliased_keeps`` is a subset of ``direct_keeps``, so the outright arm
    subtracts it: otherwise a corpus that aliased every keep would still
    satisfy the outright arm, and the two shapes would stop being told apart.
    There is no aliased *read* in the tree, so the read side is asserted as
    one shape; the day one lands, split it here as the keep side is split.
    """
    assert (sites.direct_keeps - sites.aliased_keeps) & sites.constants, (
        "no keep site names a prop outright; every keep now reaches its prop "
        "through an alias, so the two shapes are no longer told apart"
    )
    assert sites.direct_reads & sites.constants, "no direct read site"
    assert sites.aliased_keeps & sites.constants, (
        "no prop is kept through a local alias. The shape has exactly one "
        "live subject, vendor_story/opening.py's zip loop over its note "
        "pair, so unrolling that loop reddens this arm: retiring the shape "
        "means deleting this assertion and the aliased_keeps field in the "
        "same commit, not leaving an arm with nothing to find"
    )
    assert sites.passed_keeps & sites.constants, (
        "no prop is handed to a keeping parameter"
    )
    assert sites.passed_reads & sites.constants, (
        "no prop is handed to a reading parameter; that is the shape the "
        "#5535 fix introduced, and DEMOMA-22-016 is only worth what it finds"
    )
    assert sites.readers, "no step reads a prop parameter"
    assert sites.keepers, "no step keeps under a prop parameter"


def test_both_site_shapes_are_live() -> None:
    """Direct, by-parameter and aliased sites each have subjects.

    A ratchet whose subjects come in known shapes asserts something per
    shape, so retiring an arm is a deliberate edit rather than a silent
    narrowing (``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on
    the Act, Not on the Name of What Performs It").  Three shapes are live:
    a prop named outright in ``state.keep`` / ``state.kept``, a prop handed to
    a step as a keyword, and the note pair ``rv``'s opening keeps by iterating
    a local tuple.
    """
    _assert_site_shapes_live(_SITES)


def test_the_state_primitives_are_the_only_definitions_excluded() -> None:
    """``StoryState.keep`` and ``StoryState.kept``, and nothing else.

    They take a prop positionally and are what every site calls, so the
    parameter scan skips them.  Pinned because the exclusion is by name: a
    step that happened to be called ``keep`` would be skipped too, and this
    is what reports it instead of letting it go unchecked.
    """
    assert sorted(_SITES.primitives) == [
        f"vultron/demo/helpers/story/state.py::{_KEEP}",
        f"vultron/demo/helpers/story/state.py::{_READ}",
    ], (
        f"the parameter scan excluded {sorted(_SITES.primitives)}; only the "
        "two StoryState methods that write and read a prop are primitives, "
        "and anything else named after one is a step the scan must check"
    )


# ---------------------------------------------------------------------------
# DEMOMA-22-014 — a prop is kept by a step and read by a step
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-22-014")
def test_every_prop_is_read_by_a_step() -> None:
    """A prop no step reads is a causal gate that has gone quiet.

    The #5535 defect exactly: the roster gate kept the prop and both owner
    decisions ran whether the roster filled or not, with every test green.
    """
    assert not _SITES.without_a_reader(), (
        "these story props are kept but read by nobody, so the act they "
        f"gate no longer stops the story: {_SITES.without_a_reader()}. The "
        "fragment whose precondition is that act must take the prop as a "
        "required keyword and read it first (DEMOMA-22-015), or the prop "
        "must go."
    )


@pytest.mark.spec("DEMOMA-22-014")
def test_every_prop_is_kept_by_a_step() -> None:
    """A prop no step keeps stops every story that reads it.

    The other half of the same rule, and the louder one: ``kept()`` raises, so
    this fails the scenario at run time.  It is checked here because a prop a
    refactor orphaned fails only the scenarios that reach its reader, which on
    a tree of eleven scenarios is a subset of the demo gate.
    """
    assert not _SITES.without_a_keeper(), (
        "these story props are read but kept by nobody, so every fragment "
        f"that reads one stops its story: {_SITES.without_a_keeper()}"
    )


@pytest.mark.spec("DEMOMA-22-019")
def test_every_prop_name_is_declared_once() -> None:
    """One name, one declaration: the state keys the artifact on the name.

    ``StoryState._props`` is one dictionary per run, keyed on the declared
    name, and a composed scenario draws fragments from more than one family's
    module.  Nothing in :class:`StoryProp` reserves a name, so a second
    declaration spelling an existing one would have the two families
    overwrite each other's artifact.  Worse when their types differ:
    ``kept()`` checks the type it got back, so the cross-type collision is
    reported as "the story has no X yet" — the message for a fragment placed
    before the one that makes what it reads, which is a different defect with
    a different fix.

    Checked here rather than from a runtime walk of the demo packages, so one
    enumeration serves every rule about props: this one reads the declaration
    site, which also covers a prop declared in a package's ``__init__``.
    """
    assert not _SITES.collisions(), (
        "these story prop names are declared more than once: "
        f"{_SITES.collisions()}. The name is the key StoryState keeps the "
        "artifact under, so each family would read the other's."
    )


@pytest.mark.spec("DEMOMA-22-018")
def test_every_prop_declares_its_name_as_a_literal() -> None:
    """A declared name no reader can read is a prop nothing can key on.

    :class:`StoryState` keys the artifact on the name, the failure messages
    quote it, and DEMOMA-22-019 groups declarations by it.  A name given as a
    variable or an expression leaves all three with nothing, so the fallback
    to the constant's own identifier is reported here rather than being
    silently taken (#5598).
    """
    assert not _SITES.unnamed, (
        "these story props do not give their declared name as a string "
        f"literal: {list(_SITES.unnamed)}. The name is what StoryState keys "
        "the artifact under and what the failure message quotes, so it is "
        "written at the declaration, not computed."
    )


@pytest.mark.spec("DEMOMA-22-018")
def test_every_prop_construction_is_a_module_constant() -> None:
    """A prop built any other way is not reachable as a constant.

    This is what makes the enumeration complete: with it, every
    ``StoryProp(...)`` under ``vultron/demo/`` is either a declaration the
    arms above check or a failure here, so no construction escapes by being
    written somewhere the declaration reading does not look.
    """
    assert not _SITES.strays, (
        "these StoryProp constructions are not a module-level assignment to "
        f"a single name: {list(_SITES.strays)}. A prop is declared beside "
        "the fragments that share it, so every site can name it; one built "
        "inside a function, in a class body (which a grouping refactor is "
        "most likely to reach for) or into a collection is reachable by "
        "nothing and is checked by nothing."
    )


# ---------------------------------------------------------------------------
# DEMOMA-22-015 — the step that reads a prop is told which one
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-22-015")
def test_a_prop_parameter_is_keyword_only() -> None:
    """A prop is handed over by name, never by position.

    Every site reads the keyword (:func:`_read_call_sites`), and a positional
    prop would also let a cast part or a label land in its place at a call
    site that miscounted.
    """
    positional = sorted(
        f"{found.where}({found.parameter})"
        for found in _SITES.parameters
        if not found.keyword_only
    )
    assert not positional, (
        f"these prop parameters are positional: {positional}. A prop is "
        "handed over by name: the parameter goes after the bare `*`."
    )


@pytest.mark.spec("DEMOMA-22-016")
def test_a_step_that_reads_a_prop_requires_it() -> None:
    """A continuation cannot be assembled without being told what it depends on.

    The mutation this exists to stop: relaxing a required keyword back to
    ``joined: StoryProp[str] | None = None`` behind an ``if joined is not
    None:`` guard left the whole suite green, because every call site happens
    to pass the prop.  The next continuation or call site added after that
    relaxation drops the gate again (#5535, #5598).

    A step that only *keeps* under a prop parameter may still make it
    optional, and one does: ``invitee_joins_the_case`` keeps a prop only for
    a joiner whose roster some later act depends on, and is a plain check for
    the rest.  The guarantee is on the reading side, where an absent prop
    would mean no gate at all rather than no gate needed.
    """
    relaxed = sorted(
        f"{found.where}({found.parameter}): "
        + ", ".join(
            reason
            for reason, applies in (
                ("has a default", found.has_default),
                ("admits None", found.optional),
            )
            if applies
        )
        for found in _SITES.readers
        if found.has_default or found.optional
    )
    assert not relaxed, (
        "these steps read a prop they may not have been given, so the "
        f"causal gate it carries is optional: {relaxed}. The parameter is "
        "`<name>: StoryProp[T]` with no default, so a caller that does not "
        "name the act this step depends on cannot assemble it."
    )


# ---------------------------------------------------------------------------
# Each arm is proved non-vacuous by a planted violation of its own shape
# ---------------------------------------------------------------------------
#
# The real corpus is clean (every arm above passes), so nothing there shows
# that any arm can fail. These feed the same derivation a small planted
# corpus — one violation per shape, plus the compliant form of each as a
# control — so a change that disarmed an arm fails here rather than going on
# passing over code it no longer judges.


def _planted(*modules: tuple[str, str]) -> PropSites:
    """Run the derivation over inline modules under ``vultron/demo/``.

    Each module is a ``(path below vultron/demo/, source)`` pair.  The path is
    what the coverage arm reads halves and nesting from, so it is written out
    rather than generated.
    """
    return story_prop_sites(
        [
            (
                f"vultron/demo/{path}",
                source,
                _corpus.parse_inline(source, path),
            )
            for path, source in modules
        ]
    )


#: A prop and the two steps that keep and read it, by name.  The compliant
#: direct shape, used as the control the violations are varied from.
_DIRECT = (
    "ENGAGED_CASE: StoryProp[str] = StoryProp('case the owner engaged', str)\n"
    "\n"
    "def the_owner_engages(state: StoryState) -> None:\n"
    "    with demo_gate('roster'):\n"
    "        wait_for_case_participants(client)\n"
    "        state.keep(ENGAGED_CASE, str(state.case.id_))\n"
    "\n"
    "def the_reporter_asks(state: StoryState) -> None:\n"
    "    state.kept(ENGAGED_CASE)\n"
)

#: The by-parameter shape: a gate keeps under a prop it is handed, and a
#: continuation reads the prop it is handed (the #5535 fix).
_BY_PARAMETER_HELPER = (
    "def invitee_joins_the_case(\n"
    "    state: StoryState, name: str, *, joined: StoryProp[str] | None = None\n"
    ") -> None:\n"
    "    with demo_gate('roster'):\n"
    "        if joined is not None:\n"
    "            state.keep(joined, str(state.case.id_))\n"
    "\n"
    "def the_owner_hands_the_case_over(\n"
    "    state: StoryState, *, joined: StoryProp[str], owner: Part\n"
    ") -> None:\n"
    "    state.kept(joined)\n"
)

_BY_PARAMETER_FAMILY = (
    "C2_JOINED: StoryProp[str] = StoryProp('case C2 joined', str)\n"
    "\n"
    "def c1_invites_c2(state: StoryState) -> None:\n"
    "    invitee_joins_the_case(state, C2, joined=C2_JOINED)\n"
    "\n"
    "def c1_hands_the_case_to_c2(state: StoryState) -> None:\n"
    "    the_owner_hands_the_case_over(state, joined=C2_JOINED, owner=C1_PART)\n"
)

#: The aliased shape: two props into a local tuple, each kept in a loop,
#: which is how ``rv``'s opening keeps the note pair.
_ALIASED = (
    "REPORTERS_QUESTION: StoryProp[as_Note] = StoryProp('q', as_Note)\n"
    "VENDORS_ANSWER: StoryProp[as_Note] = StoryProp('a', as_Note)\n"
    "\n"
    "def the_reporter_asks_about_the_workaround(state: StoryState) -> None:\n"
    "    props: tuple[StoryProp[as_Note], ...] = (\n"
    "        REPORTERS_QUESTION,\n"
    "        VENDORS_ANSWER,\n"
    "    )\n"
    "    for prop, note in zip(props, posted, strict=False):\n"
    "        if note is not None:\n"
    "            state.keep(prop, note)\n"
    "\n"
    "def the_vendor_replies(state: StoryState) -> None:\n"
    "    state.kept(REPORTERS_QUESTION)\n"
    "    state.kept(VENDORS_ANSWER)\n"
)


def _compliant() -> PropSites:
    """The compliant form of all three site shapes, in one planted corpus."""
    return _planted(
        ("helpers/coordinated_story/opening.py", _DIRECT),
        ("helpers/vendor_story/opening.py", _ALIASED),
        ("helpers/owner_decision_story/handover.py", _BY_PARAMETER_HELPER),
        ("scenario/rcvcv_demo/fragments.py", _BY_PARAMETER_FAMILY),
    )


def test_the_planted_control_corpus_passes_every_arm() -> None:
    """The compliant form of all three shapes raises nothing.

    Without this, a derivation that reported every prop as a violation would
    make each planted violation below pass for the wrong reason.
    """
    sites = _compliant()
    _assert_declarations_found(sites)
    _assert_site_shapes_live(sites)
    assert sites.without_a_reader() == []
    assert sites.without_a_keeper() == []
    assert sites.strays == ()
    assert [found for found in sites.readers if found.has_default] == []
    assert [
        found for found in sites.parameters if not found.keyword_only
    ] == []
    # Both shapes resolved, so the controls below vary a corpus the
    # derivation really reads rather than one it passes over.
    assert sites.direct_reads & sites.constants == {
        "ENGAGED_CASE",
        "REPORTERS_QUESTION",
        "VENDORS_ANSWER",
    }
    assert sites.passed_reads & sites.constants == {"C2_JOINED"}
    assert sites.passed_keeps & sites.constants == {"C2_JOINED"}
    assert sites.aliased_keeps & sites.constants == {
        "REPORTERS_QUESTION",
        "VENDORS_ANSWER",
    }


def test_the_gate_catches_a_prop_that_nothing_reads() -> None:
    """AC-1 / DEMOMA-22-014: the #5535 defect, as a planted module.

    The roster gate keeps the prop; no continuation takes it.  Everything
    else about the corpus is the compliant form, so the only difference is
    the missing read.
    """
    sites = _planted(
        (
            "helpers/two_coordinator_story.py",
            (
                "SECOND_COORDINATOR_JOINED: StoryProp[str] = StoryProp(\n"
                "    'case the second coordinator joined', str\n"
                ")\n"
                "\n"
                "def c1_invites_c2(state: StoryState) -> None:\n"
                "    with demo_gate('roster'):\n"
                "        state.keep(SECOND_COORDINATOR_JOINED, str(state.case.id_))\n"
                "\n"
                "def c1_hands_the_case_to_c2(state: StoryState) -> None:\n"
                "    the_owner_hands_the_case_over(state, owner=C1_PART)\n"
            ),
        ),
    )
    assert sites.without_a_reader() == [
        "vultron/demo/helpers/two_coordinator_story.py"
        "::SECOND_COORDINATOR_JOINED"
    ]
    assert sites.without_a_keeper() == []


def test_the_gate_catches_a_prop_that_nothing_keeps() -> None:
    """The other half of DEMOMA-22-014: a read with no keep behind it."""
    sites = _planted(
        (
            "helpers/vendor_story/opening.py",
            (
                "VENDORS_ANSWER: StoryProp[as_Note] = StoryProp('answer', as_Note)\n"
                "\n"
                "def the_vendor_replies(state: StoryState) -> None:\n"
                "    state.kept(VENDORS_ANSWER)\n"
            ),
        ),
    )
    assert sites.without_a_keeper() == [
        "vultron/demo/helpers/vendor_story/opening.py::VENDORS_ANSWER"
    ]
    assert sites.without_a_reader() == []


def test_the_gate_catches_a_prop_built_outside_a_module_constant() -> None:
    """A construction the declaration reading does not recognise is reported.

    This is what makes the enumeration complete rather than best-effort: a
    prop smuggled into a function body or a collection cannot escape by
    being written where the scan does not look for a declaration.
    """
    sites = _planted(
        (
            "helpers/coordinated_embargo_story.py",
            (
                "REVISIONS = [StoryProp('first revision', str)]\n"
                "\n"
                "def the_reporter_revises(state: StoryState) -> None:\n"
                "    prop = StoryProp('second revision', str)\n"
                "    state.keep(prop, revised)\n"
            ),
        ),
    )
    assert sites.declarations == ()
    assert sorted(sites.strays) == [
        "vultron/demo/helpers/coordinated_embargo_story.py:1",
        "vultron/demo/helpers/coordinated_embargo_story.py:4",
    ]


def test_an_empty_corpus_fails_the_non_vacuity_arm() -> None:
    """A gate that resolves zero subjects fails, rather than passing.

    The emptiness the arm guards is reachable in three ways — the class
    renamed, the declarations moved out of ``vultron/demo/``, or a prefilter
    that stopped matching — and each one would otherwise leave every absence
    assertion above passing over nothing.
    """
    with pytest.raises(AssertionError, match="would pass vacuously"):
        _assert_declarations_found(_planted())
    with pytest.raises(AssertionError, match="names a prop outright"):
        _assert_site_shapes_live(_planted())


def test_dropping_any_one_site_shape_fails_the_shape_arm() -> None:
    """No shape can quietly retire: each one missing is reported by name.

    A migration that rewrote every family in one shape would otherwise narrow
    the ratchet to that shape and keep passing
    (``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the Act,
    Not on the Name of What Performs It").  Each row drops one shape from the
    control corpus and keeps the other two.
    """
    with pytest.raises(AssertionError, match="names a prop outright"):
        _assert_site_shapes_live(
            _planted(
                ("helpers/vendor_story/opening.py", _ALIASED),
                (
                    "helpers/owner_decision_story/handover.py",
                    _BY_PARAMETER_HELPER,
                ),
                ("scenario/rcvcv_demo/fragments.py", _BY_PARAMETER_FAMILY),
            )
        )
    with pytest.raises(AssertionError, match="through a local alias"):
        _assert_site_shapes_live(
            _planted(
                ("helpers/coordinated_story/opening.py", _DIRECT),
                (
                    "helpers/owner_decision_story/handover.py",
                    _BY_PARAMETER_HELPER,
                ),
                ("scenario/rcvcv_demo/fragments.py", _BY_PARAMETER_FAMILY),
            )
        )
    # Either half of the by-parameter shape going missing proves it is gone,
    # so the pattern does not pin which of the two asserts runs first.
    with pytest.raises(
        AssertionError, match=r"handed to a (keeping|reading) parameter"
    ):
        _assert_site_shapes_live(
            _planted(
                ("helpers/coordinated_story/opening.py", _DIRECT),
                ("helpers/vendor_story/opening.py", _ALIASED),
            )
        )


def test_the_coverage_arm_fails_on_a_flat_corpus_and_on_one_half() -> None:
    """Subpackages and both halves of the tree are each required.

    The runtime walk this enumeration replaced skipped packages before
    #5592, which is how a prop in a split module escaped even the uniqueness
    check.  The equivalent here is a scan that reads only flat modules.
    """
    with pytest.raises(AssertionError, match="declared only under"):
        _assert_declarations_found(
            _planted(("helpers/coordinated_story/opening.py", _DIRECT))
        )
    with pytest.raises(AssertionError, match="declared in a flat module"):
        _assert_declarations_found(
            _planted(
                ("helpers/two_coordinator_story.py", _DIRECT),
                (
                    "scenario/rcvv_embargo_demo.py",
                    (
                        "REVISED: StoryProp[str] = StoryProp('revised', str)\n"
                        "\n"
                        "def revise(state: StoryState) -> None:\n"
                        "    state.keep(REVISED, revised)\n"
                        "\n"
                        "def publish(state: StoryState) -> None:\n"
                        "    state.kept(REVISED)\n"
                    ),
                ),
            )
        )


@pytest.mark.spec("DEMOMA-22-016")
@pytest.mark.parametrize(
    ("annotation", "reason"),
    [
        ("StoryProp[str] | None = None", "has a default, admits None"),
        ("StoryProp[str] = _NO_PROP", "has a default"),
        ("StoryProp[str] | None", "admits None"),
        ("Optional[StoryProp[str]]", "admits None"),
        ("Union[StoryProp[str], None]", "admits None"),
        # Quoted, which read whole removed the parameter from the scan
        # altogether rather than reporting it (#5598).
        ('"StoryProp[str] | None" = None', "has a default, admits None"),
    ],
)
def test_the_gate_catches_a_relaxed_reader_parameter(
    annotation: str, reason: str
) -> None:
    """AC-2 / DEMOMA-22-015: each way of relaxing a read prop is reported.

    The first row is the mutation that left the whole suite green on PR
    #5595's head, because every call site happened to pass the prop (#5598).
    The rest are the same relaxation written differently, so the check does
    not rest on one spelling.
    """
    sites = _planted(
        (
            "helpers/owner_decision_story/handover.py",
            (
                f"def the_owner_hands_the_case_over(\n"
                f"    state: StoryState, *, joined: {annotation}\n"
                f") -> None:\n"
                f"    if joined is not None:\n"
                f"        state.kept(joined)\n"
            ),
        ),
    )
    assert [found.parameter for found in sites.readers] == ["joined"]
    relaxed = [
        found for found in sites.readers if found.has_default or found.optional
    ]
    assert relaxed, f"a reader annotated {annotation!r} was read as required"
    assert (relaxed[0].has_default, relaxed[0].optional) == (
        "has a default" in reason,
        "admits None" in reason,
    )


@pytest.mark.spec("DEMOMA-22-015")
def test_the_gate_catches_a_positional_prop_parameter() -> None:
    """A prop passed by position is reported, not resolved.

    The call-site reading takes keywords only, so a positional prop
    parameter would silently stop contributing a read site.  It is reported
    as this failure instead.
    """
    sites = _planted(
        (
            "helpers/owner_decision_story/keep.py",
            (
                "def the_owner_approves(\n"
                "    state: StoryState, joined: StoryProp[str]\n"
                ") -> None:\n"
                "    state.kept(joined)\n"
            ),
        ),
    )
    assert [
        found.parameter for found in sites.parameters if not found.keyword_only
    ] == ["joined"]


@pytest.mark.spec("DEMOMA-22-017")
def test_a_keeper_only_parameter_may_be_optional() -> None:
    """The keep side's prop parameter is allowed to default to nothing.

    ``invitee_joins_the_case`` keeps a prop only for a joiner whose roster a
    later act depends on, and runs a plain ``demo_check`` for the rest, so
    its parameter is optional by design (DEMOCI-01-011).  The guarantee
    DEMOMA-22-015 asks for is on the reading side: an absent prop there means
    no gate at all, where here it means no gate needed.
    """
    sites = _planted(
        (
            "helpers/coordinated_story/joining.py",
            (
                "def invitee_joins_the_case(\n"
                "    state: StoryState, *, joined: StoryProp[str] | None = None\n"
                ") -> None:\n"
                "    if joined is not None:\n"
                "        state.keep(joined, str(state.case.id_))\n"
            ),
        ),
    )
    keeper = sites.parameters[0]
    assert (keeper.keeps, keeper.reads) == (True, False)
    assert (keeper.has_default, keeper.optional) == (True, True)
    assert [
        found for found in sites.readers if found.has_default or found.optional
    ] == []


def test_a_prop_kept_through_a_local_alias_counts_as_kept() -> None:
    """``rv``'s note pair: two props into a tuple, each kept in a loop.

    The alias arm is the one that reads this.  Pinned as a control, because
    an alias reading that stopped following the tuple would report both notes
    as kept by nobody and get the ratchet switched off.
    """
    sites = _planted(("helpers/vendor_story/opening.py", _ALIASED))
    assert sites.aliased_keeps & sites.constants == {
        "REPORTERS_QUESTION",
        "VENDORS_ANSWER",
    }
    assert sites.without_a_keeper() == []
    assert sites.without_a_reader() == []


def test_a_prop_handed_to_an_unrelated_keyword_is_not_a_read() -> None:
    """Only a keyword some step keeps or reads under counts.

    Otherwise a prop mentioned anywhere in a call would read as read, and the
    ratchet would pass over the very omission it exists to catch.
    """
    sites = _planted(
        (
            "helpers/two_coordinator_story.py",
            (
                "SECOND_COORDINATOR_JOINED: StoryProp[str] = StoryProp('c2', str)\n"
                "\n"
                "def c1_invites_c2(state: StoryState) -> None:\n"
                "    with demo_gate('roster'):\n"
                "        state.keep(SECOND_COORDINATOR_JOINED, str(state.case.id_))\n"
                "\n"
                "def c1_decides(state: StoryState) -> None:\n"
                "    logger.info('decided', extra=SECOND_COORDINATOR_JOINED)\n"
            ),
        ),
    )
    assert sites.without_a_reader() == [
        "vultron/demo/helpers/two_coordinator_story.py"
        "::SECOND_COORDINATOR_JOINED"
    ]


@pytest.mark.spec("DEMOMA-22-019")
def test_the_gate_catches_two_declarations_spelling_one_name() -> None:
    """A collision is read from the declaration sites, not from a live walk.

    Two separate constructions spelling one name are two declarations, even
    where the constants differ: the name is what :class:`StoryState` keys the
    artifact under, so the families would read each other's.
    """
    sites = _planted(
        (
            "helpers/two_coordinator_story.py",
            (
                "SECOND_COORDINATOR_JOINED: StoryProp[str] = StoryProp(\n"
                "    'case the coordinator joined', str\n"
                ")\n"
                "\n"
                "def keep_it(state: StoryState) -> None:\n"
                "    state.keep(SECOND_COORDINATOR_JOINED, case_id)\n"
                "\n"
                "def read_it(state: StoryState) -> None:\n"
                "    state.kept(SECOND_COORDINATOR_JOINED)\n"
            ),
        ),
        (
            "helpers/vendor_coordinator_story.py",
            (
                "COORDINATOR_JOINED: StoryProp[str] = StoryProp(\n"
                "    'case the coordinator joined', str\n"
                ")\n"
                "\n"
                "def keep_it(state: StoryState) -> None:\n"
                "    state.keep(COORDINATOR_JOINED, case_id)\n"
                "\n"
                "def read_it(state: StoryState) -> None:\n"
                "    state.kept(COORDINATOR_JOINED)\n"
            ),
        ),
    )
    assert sites.collisions() == {
        "case the coordinator joined": [
            "vultron/demo/helpers/two_coordinator_story.py"
            "::SECOND_COORDINATOR_JOINED",
            "vultron/demo/helpers/vendor_coordinator_story.py"
            "::COORDINATOR_JOINED",
        ]
    }
    # The collision is the only finding: both props are kept and read.
    assert sites.without_a_keeper() == []
    assert sites.without_a_reader() == []


def test_a_prop_in_a_package_init_is_enumerated() -> None:
    """A declaration in a package's ``__init__`` is a subject like any other.

    The runtime walk this enumeration replaced skipped package modules, so a
    prop declared in one escaped even the uniqueness check.  Reading the
    declaration site covers every module the package holds, ``__init__``
    included.
    """
    sites = _planted(("helpers/vendor_story/__init__.py", _DIRECT))
    assert [found.where for found in sites.declarations] == [
        "vultron/demo/helpers/vendor_story/__init__.py::ENGAGED_CASE"
    ]


def test_a_long_alias_chain_and_a_cyclic_one_both_resolve() -> None:
    """The alias reading follows a chain to its end, and survives a cycle.

    It runs to a fixed point rather than to a depth cap, because a cap would
    report a prop beyond it as kept by nobody — failing correct code, the one
    direction this scan must not err in.  A cyclic binding is the reason the
    fixed point is bounded by the alias map rather than by the chain.
    """
    chain = "".join(f"    step_{n} = step_{n - 1}\n" for n in range(1, 24))
    sites = _planted(
        (
            "helpers/coordinated_embargo_story.py",
            (
                "DEEP: StoryProp[str] = StoryProp('deep', str)\n"
                "\n"
                "def keep_it(state: StoryState) -> None:\n"
                "    step_0 = DEEP\n"
                f"{chain}"
                "    loop_a = loop_b\n"
                "    loop_b = loop_a\n"
                f"    state.keep(step_{23}, value)\n"
                "    state.keep(loop_a, value)\n"
                "\n"
                "def read_it(state: StoryState) -> None:\n"
                "    state.kept(DEEP)\n"
            ),
        ),
    )
    assert sites.aliased_keeps & sites.constants == {"DEEP"}
    assert sites.without_a_keeper() == []


@pytest.mark.spec("DEMOMA-22-018")
def test_the_gate_catches_a_name_that_is_not_a_literal() -> None:
    """A computed declared name is reported, never guessed at.

    Falling back to the constant's own identifier would make two
    declarations spelling one name look like two names, which is how
    DEMOMA-22-019's arm went quiet on the keyword construction form.
    """
    sites = _planted(
        (
            "helpers/two_coordinator_story.py",
            (
                "LABEL = 'case the second coordinator joined'\n"
                "JOINED: StoryProp[str] = StoryProp(LABEL, str)\n"
                "\n"
                "def keep_it(state: StoryState) -> None:\n"
                "    state.keep(JOINED, case_id)\n"
                "\n"
                "def read_it(state: StoryState) -> None:\n"
                "    state.kept(JOINED)\n"
            ),
        ),
    )
    assert sites.unnamed == (
        "vultron/demo/helpers/two_coordinator_story.py::JOINED",
    )
    assert [found.label for found in sites.declarations] == [None]
    # The keep and read sites still resolve, so the only finding is the name.
    assert (sites.without_a_keeper(), sites.without_a_reader()) == ([], [])


@pytest.mark.spec("DEMOMA-22-019")
def test_the_declared_name_is_read_from_the_keyword_form_too() -> None:
    """``StoryProp(name=..., type_=...)`` is the same declaration.

    Reading only the positional slot fell back to the constant's own
    identifier, so two modules declaring one name under different constants
    collided with nothing to report it (#5598).
    """
    declaration = (
        "{constant}: StoryProp[str] = StoryProp(\n"
        "    name='case the coordinator joined', type_=str\n"
        ")\n"
        "\n"
        "def keep_{constant}(state: StoryState) -> None:\n"
        "    state.keep({constant}, case_id)\n"
        "\n"
        "def read_{constant}(state: StoryState) -> None:\n"
        "    state.kept({constant})\n"
    )
    sites = _planted(
        (
            "helpers/two_coordinator_story.py",
            declaration.format(constant="SECOND_COORDINATOR_JOINED"),
        ),
        (
            "helpers/vendor_coordinator_story.py",
            declaration.format(constant="COORDINATOR_JOINED"),
        ),
    )
    assert sites.unnamed == ()
    assert sites.collisions() == {
        "case the coordinator joined": [
            "vultron/demo/helpers/two_coordinator_story.py"
            "::SECOND_COORDINATOR_JOINED",
            "vultron/demo/helpers/vendor_coordinator_story.py"
            "::COORDINATOR_JOINED",
        ]
    }


@pytest.mark.spec("DEMOMA-22-015")
def test_the_gate_catches_a_starred_prop_parameter() -> None:
    """A ``*args`` prop slot cannot be keyword-only, so it is reported.

    It is also resolved at its call site, so the same code does not *also*
    report its prop as touched by nobody — a second and false failure
    (:func:`_slots`).
    """
    sites = _planted(
        (
            "helpers/vendor_story/opening.py",
            (
                "VENDORS_ANSWER: StoryProp[as_Note] = StoryProp('a', as_Note)\n"
                "\n"
                "def keep_each(state: StoryState, *props: StoryProp[as_Note])"
                " -> None:\n"
                "    for prop in props:\n"
                "        state.keep(prop, note)\n"
                "\n"
                "def the_reporter_asks(state: StoryState) -> None:\n"
                "    keep_each(state, VENDORS_ANSWER)\n"
                "\n"
                "def the_vendor_replies(state: StoryState) -> None:\n"
                "    state.kept(VENDORS_ANSWER)\n"
            ),
        ),
    )
    starred = [found.parameter for found in sites.starred]
    assert starred == ["props"]
    assert [
        found.parameter for found in sites.parameters if not found.keyword_only
    ] == ["props"]
    assert (sites.without_a_keeper(), sites.without_a_reader()) == ([], [])


@pytest.mark.spec("DEMOMA-22-016")
def test_an_inner_optional_type_argument_is_not_a_relaxed_reader() -> None:
    """``StoryProp[str | None]`` is a required parameter of an optional type.

    The obligation is on the parameter, not on the artifact's type, so
    reading the whole annotation subtree would fail correct code — the one
    direction this scan must not err in.
    """
    sites = _planted(
        (
            "helpers/owner_decision_story/handover.py",
            (
                "def the_owner_hands_the_case_over(\n"
                "    state: StoryState, *, joined: StoryProp[str | None]\n"
                ") -> None:\n"
                "    state.kept(joined)\n"
            ),
        ),
    )
    assert [found.parameter for found in sites.readers] == ["joined"]
    assert [
        found for found in sites.readers if found.has_default or found.optional
    ] == []


@pytest.mark.spec("DEMOMA-22-014")
@pytest.mark.parametrize(
    ("label", "handing"),
    [
        (
            "a local name",
            "    prop = C2_JOINED\n"
            "    invitee_joins_the_case(state, C2, joined=prop)\n",
        ),
        (
            "a module constant",
            "    invitee_joins_the_case(state, C2, joined=ALIAS)\n",
        ),
        (
            "an imported rename",
            "    invitee_joins_the_case(state, C2, joined=RENAMED)\n",
        ),
    ],
)
def test_a_prop_handed_over_through_an_alias_is_still_a_site(
    label: str, handing: str
) -> None:
    """A call site that names the prop indirectly is a site like any other.

    Each of these is legitimate code, so reading only the constant's own
    identifier would fail it — the invent direction.  The module-level and
    ``import ... as`` shapes are read through ``_corpus.aliases``, the local
    one through the enclosing function's own alias map.
    """
    sites = _planted(
        (
            "helpers/owner_decision_story/handover.py",
            _BY_PARAMETER_HELPER,
        ),
        (
            "scenario/rcvcv_demo/fragments.py",
            "from vultron.demo.helpers.story import StoryProp\n"
            "C2_JOINED: StoryProp[str] = StoryProp('case C2 joined', str)\n"
            "ALIAS = C2_JOINED\n"
            "from vultron.demo.scenario.other import C2_JOINED as RENAMED\n"
            "\n"
            "def c1_invites_c2(state: StoryState) -> None:\n"
            f"{handing}"
            "\n"
            "def c1_hands_over(state: StoryState) -> None:\n"
            "    the_owner_hands_the_case_over(state, joined=C2_JOINED,"
            " owner=C1)\n",
        ),
    )
    assert sites.without_a_keeper() == [], (
        f"a prop handed over as {label} was read as kept by nobody"
    )
    assert sites.without_a_reader() == []


@pytest.mark.spec("DEMOMA-22-014")
def test_a_forwarding_wrapper_carries_the_role_to_its_callers() -> None:
    """A wrapper that only passes a prop on is not a dead end.

    A role is seeded from the step that keeps or reads, then followed through
    every forwarding (:func:`_settle_roles`).  Without that, a composition
    helper — the tree's stated direction of travel — would make its callers'
    ``joined=PROP`` count for nothing and redden the gate.
    """
    sites = _planted(
        ("helpers/owner_decision_story/handover.py", _BY_PARAMETER_HELPER),
        (
            "helpers/two_coordinator_story.py",
            "def the_owner_decides(\n"
            "    state: StoryState, *, joined: StoryProp[str]\n"
            ") -> None:\n"
            "    the_owner_hands_the_case_over(state, joined=joined,"
            " owner=C1)\n",
        ),
        (
            "scenario/rccv_handoff_demo.py",
            "SECOND_COORDINATOR_JOINED: StoryProp[str] = StoryProp('c2', str)\n"
            "\n"
            "def c1_invites_c2(state: StoryState) -> None:\n"
            "    invitee_joins_the_case(\n"
            "        state, C2, joined=SECOND_COORDINATOR_JOINED\n"
            "    )\n"
            "\n"
            "def c1_hands_over(state: StoryState) -> None:\n"
            "    the_owner_decides(\n"
            "        state, joined=SECOND_COORDINATOR_JOINED\n"
            "    )\n",
        ),
    )
    roles = {
        (found.function, found.keeps, found.reads)
        for found in sites.parameters
    }
    assert ("the_owner_decides", False, True) in roles, (
        "the wrapper did not inherit the reading role of the step it "
        f"forwards to; roles were {sorted(roles)}"
    )
    assert (sites.without_a_keeper(), sites.without_a_reader()) == ([], [])
