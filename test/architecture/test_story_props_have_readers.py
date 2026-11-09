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

"""Architecture invariant (DEMOMA-22-014 through DEMOMA-22-017): every story
prop is declared once, kept by a step and read by a step, and the step that
reads one is told which.

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
(#5592).  Each arm asserts its own subjects are non-empty, so none of them
can pass over an empty corpus (DF-09-009's shape).

Two shapes of site are recognised, because both are live:

* **direct** — ``state.keep(PROP, value)`` and ``state.kept(PROP)`` naming the
  prop constant;
* **through a parameter** — the prop handed to a step as ``joined=PROP``,
  where that step's ``joined`` parameter is one it keeps or reads.  This is
  the shape the #5535 fix introduced, and it is what makes a continuation's
  precondition structural rather than remembered.

Loose readings, with the direction each one errs in
(``notes/architecture-ratchet-corpus.md`` § "Say, Per Loose Reading, Whether
It Can Miss or Invent").  All but the last can only **miss** a violation,
never invent one, and none can be narrowed without resolving bindings:

* ``keep`` / ``kept`` are matched on the attribute name, whatever the
  receiver, so another object's ``keep`` whose first argument names a
  declared prop would be counted as a keep site.
* A call site is matched by its callee's bare name, so two functions that
  share a name share their prop-parameter roles: a prop passed as ``joined=``
  to a same-named function that does not read it reads as read.
* A local alias is followed by name through assignments and ``for`` targets
  rather than by binding, so a name rebound between the alias and the keep
  still resolves to the first binding's props.  This is the arm that reads
  ``rv``'s note pair, which is kept by iterating a local tuple of two props.
* The annotation that marks a prop parameter is matched on its trailing name,
  so a module that aliased the class under another name would have its
  parameters unchecked.
* The one arm that can **invent**: a ``StoryProp(...)`` call that is not a
  module-level assignment to a single name is reported as a stray
  construction.  It is narrow on purpose — it is what makes the enumeration
  complete, since every construction under ``vultron/demo/`` is then either a
  declaration this ratchet checks or a failure.  A prop built any other way
  is not reachable as a module constant, which is how every family declares
  one.

The derivation runs once at import time, outside the per-test timeout, and
costs about 0.8 s over the two prefilter rounds; each test then reads the
result and measures under 5 ms, within TB-13-004's budget.

Spec: DEMOMA-22-014 through DEMOMA-22-017, DEMOCI-01-011, TB-13-001,
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
#: Their own definitions take a prop positionally and are the primitives
#: every site calls, not steps of a story, so a definition named either one is
#: excluded from the parameter scan — and
#: :func:`test_the_state_primitives_are_the_only_definitions_excluded` pins
#: that there are exactly two, so the exclusion cannot widen unnoticed.
_KEEP, _READ = "keep", "kept"

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
    #: The declared name :class:`StoryState` keys the artifact under.
    label: str
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
    #: Whether the annotation admits ``None``.
    optional: bool


@dataclass
class PropSites:
    """Every prop declared under the scanned files, and what touches each."""

    declarations: tuple[PropDeclaration, ...] = ()
    parameters: tuple[PropParameter, ...] = ()
    #: Constants named by a ``state.keep`` / ``state.kept`` call directly.
    direct_keeps: frozenset[str] = frozenset()
    direct_reads: frozenset[str] = frozenset()
    #: Constants handed to a keeping / reading prop parameter by a caller.
    passed_keeps: frozenset[str] = frozenset()
    passed_reads: frozenset[str] = frozenset()
    #: Constants a local alias carried into a keep (``rv``'s note pair).
    aliased_keeps: frozenset[str] = frozenset()
    #: ``StoryProp(...)`` calls that are no module-level declaration.
    strays: tuple[str, ...] = ()
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


# ---------------------------------------------------------------------------
# AST readings
# ---------------------------------------------------------------------------


def _trailing_names(node: ast.expr | None) -> frozenset[str]:
    """Every identifier *node* mentions, an attribute by its trailing name.

    A quoted forward reference is read as the name it spells, so a module's
    import form does not decide whether its parameters are checked.
    """
    if node is None:
        return frozenset()
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Attribute):
            found.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            found.add(child.value.rsplit(".", 1)[-1])
    return frozenset(found)


def _is_optional(annotation: ast.expr | None) -> bool:
    """True when *annotation* admits ``None``.

    ``X | None``, ``Optional[X]`` and ``Union[X, None]`` all count: each one
    lets a caller hand the step nothing, which is the relaxation that made the
    #5535 mutation silent.
    """
    if annotation is None:
        return False
    for child in ast.walk(annotation):
        if isinstance(child, ast.Constant) and child.value is None:
            return True
        if isinstance(child, ast.Name) and child.id == "Optional":
            return True
        if isinstance(child, ast.Attribute) and child.attr == "Optional":
            return True
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


def _first_argument(call: ast.Call) -> ast.expr | None:
    return call.args[0] if call.args else None


def _parameter_names(fn: _FunctionNode) -> frozenset[str]:
    args = fn.args
    return frozenset(
        arg.arg
        for arg in (
            *args.posonlyargs,
            *args.args,
            *args.kwonlyargs,
            args.vararg,
            args.kwarg,
        )
        if arg is not None
    )


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
        names = _trailing_names(value)
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
    outright = _trailing_names(expression)
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


@dataclass
class _Accumulator:
    declarations: list[PropDeclaration] = field(default_factory=list)
    parameters: list[PropParameter] = field(default_factory=list)
    direct_keeps: set[str] = field(default_factory=set)
    direct_reads: set[str] = field(default_factory=set)
    aliased_keeps: set[str] = field(default_factory=set)
    strays: list[str] = field(default_factory=list)
    primitives: list[str] = field(default_factory=list)
    modules: set[str] = field(default_factory=set)
    #: ``(callee name, parameter) -> (keeps, reads)`` for every prop parameter.
    roles: dict[tuple[str, str], tuple[bool, bool]] = field(
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
        label = _first_argument(value)
        declared.add(id(value))
        into.declarations.append(
            PropDeclaration(
                constant=target.id,
                label=(
                    label.value
                    if isinstance(label, ast.Constant)
                    and isinstance(label.value, str)
                    else target.id
                ),
                where=f"{module}::{target.id}",
            )
        )
        into.modules.add(module)
    for call in ast.walk(tree):
        if (
            isinstance(call, ast.Call)
            and _corpus.callee_name(call.func) == _PROP_CLASS
            and id(call) not in declared
        ):
            into.strays.append(f"{module}:{_corpus.node_line(call)}")


def _read_sites(module: str, tree: ast.AST, into: _Accumulator) -> None:
    """Collect *module*'s keep and read sites, direct and by parameter."""
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name in (_KEEP, _READ):
            # The primitive itself, which every site calls and which no
            # caller hands a prop by keyword.  Named the same way the sites
            # name it, so a rename of the method moves this with them.
            into.primitives.append(f"{module}::{fn.name}")
            continue
        parameters = _parameter_names(fn)
        aliases = _alias_map(fn)
        kept_parameters: set[str] = set()
        read_parameters: set[str] = set()
        for method, direct, aliased, by_parameter in (
            (_KEEP, into.direct_keeps, into.aliased_keeps, kept_parameters),
            (_READ, into.direct_reads, into.aliased_keeps, read_parameters),
        ):
            for call in _method_calls(fn, method):
                constants, named, through_alias = _resolve(
                    _first_argument(call), aliases, parameters
                )
                direct.update(constants)
                # A read reached through an alias is counted as a direct read:
                # the prop still ends up in ``state.kept``, and only the keep
                # side has an aliasing shape worth asserting on its own.
                (aliased if method == _KEEP else direct).update(through_alias)
                by_parameter.update(named)
        _record_parameters(module, fn, kept_parameters, read_parameters, into)


def _record_parameters(
    module: str,
    fn: _FunctionNode,
    kept: set[str],
    read: set[str],
    into: _Accumulator,
) -> None:
    """Record each parameter of *fn* annotated as a prop, with its shape."""
    args = fn.args
    positional = [*args.posonlyargs, *args.args]
    defaulted = {
        arg.arg for arg in positional[len(positional) - len(args.defaults) :]
    } | {
        arg.arg
        for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
        if default is not None
    }
    keyword_only = {arg.arg for arg in args.kwonlyargs}
    for arg in (*positional, *args.kwonlyargs):
        if _PROP_CLASS not in _trailing_names(arg.annotation):
            continue
        reads, keeps = arg.arg in read, arg.arg in kept
        into.parameters.append(
            PropParameter(
                where=f"{module}::{fn.name}",
                function=fn.name,
                parameter=arg.arg,
                reads=reads,
                keeps=keeps,
                keyword_only=arg.arg in keyword_only,
                has_default=arg.arg in defaulted,
                optional=_is_optional(arg.annotation),
            )
        )
        if reads or keeps:
            was_keeping, was_reading = into.roles.get(
                (fn.name, arg.arg), (False, False)
            )
            into.roles[(fn.name, arg.arg)] = (
                was_keeping or keeps,
                was_reading or reads,
            )


def _read_call_sites(
    module: str, tree: ast.AST, into: _Accumulator
) -> tuple[frozenset[str], frozenset[str]]:
    """Return the constants *module* hands to a keeping / reading parameter.

    Keywords only: every prop parameter must be keyword-only
    (:func:`test_a_prop_parameter_is_keyword_only`), so a positional one is
    reported as that failure rather than resolved here.
    """
    keeps: set[str] = set()
    reads: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _corpus.callee_name(node.func)
        if callee is None:
            continue
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            role = into.roles.get((callee, keyword.arg))
            if role is None:
                continue
            keeping, reading = role
            handed = _trailing_names(keyword.value)
            if keeping:
                keeps.update(handed)
            if reading:
                reads.update(handed)
    return frozenset(keeps), frozenset(reads)


def story_prop_sites(files: Iterable[tuple[str, ast.AST]]) -> PropSites:
    """Every prop the given modules declare, and every site that touches it.

    *files* is ``(module label, tree)`` pairs — the live corpus from
    :func:`_live_files`, or inline sources a planted-violation test parses
    with ``_corpus.parse_inline``.  The passes run in order because each one
    needs the one before it: the declarations name the constants, the
    parameter scan names the roles, and the call-site scan reads a keyword
    only once a role is known for it.
    """
    scanned = list(files)
    into = _Accumulator()
    for module, tree in scanned:
        _read_declarations(module, tree, into)
    for module, tree in scanned:
        _read_sites(module, tree, into)
    passed_keeps: set[str] = set()
    passed_reads: set[str] = set()
    for module, tree in scanned:
        keeps, reads = _read_call_sites(module, tree, into)
        passed_keeps |= keeps
        passed_reads |= reads
    return PropSites(
        declarations=tuple(into.declarations),
        parameters=tuple(into.parameters),
        direct_keeps=frozenset(into.direct_keeps),
        direct_reads=frozenset(into.direct_reads),
        passed_keeps=frozenset(passed_keeps),
        passed_reads=frozenset(passed_reads),
        aliased_keeps=frozenset(into.aliased_keeps),
        strays=tuple(into.strays),
        primitives=tuple(into.primitives),
        modules=frozenset(into.modules),
    )


def _demo_files(*fragments: str) -> Iterator[tuple[str, ast.AST]]:
    """``(repo-relative module, tree)`` for demo files mentioning a fragment."""
    if not fragments:
        return
    for path, tree in _corpus.files_mentioning(*fragments, under=_DEMO_DIR):
        yield path.relative_to(_corpus.REPO_ROOT).as_posix(), tree


def _live_files() -> list[tuple[str, ast.AST]]:
    """Every demo module the scan must read, prefiltered in two rounds.

    The first round takes the modules that mention the class or either state
    method.  Those hold the declarations, so the second round can prefilter on
    the constants' own names and reach the scenario modules that hand a prop
    to a step while mentioning neither (TB-13-002, TB-13-008).  The corpus
    caches each parse, so a module both rounds select is parsed once.
    """
    found = dict(_demo_files(*_SEED_FRAGMENTS))
    constants = story_prop_sites(found.items()).constants
    found.update(_demo_files(*sorted(constants)))
    return sorted(found.items())


#: Derived once at import time, outside the per-test timeout (TB-13-001).
with _corpus.gc_paused():
    _SITES = story_prop_sites(_live_files())


# ---------------------------------------------------------------------------
# The corpus the arms run against is real
# ---------------------------------------------------------------------------


def _assert_declarations_found(_SITES: PropSites) -> None:
    """Fail unless props were found in both halves and in a subpackage.

    A function rather than a test body so
    :func:`test_an_empty_corpus_fails_the_non_vacuity_arm` can hand it a
    corpus with no subjects and pin that it fails (DF-09-009's shape: a gate
    that resolves zero targets must fail, not pass).
    """
    assert _SITES.declarations, (
        "no StoryProp construction was found under vultron/demo/, so every "
        "arm of this ratchet would pass vacuously: either the declarations "
        f"have moved out of {_DEMO_DIR.name}/ or {_PROP_CLASS!r} was renamed"
    )
    halves = {module.split("/")[2] for module in _SITES.modules}
    assert {"helpers", "scenario"} <= halves, (
        f"props are declared only under {sorted(halves)}; the scan must "
        "reach both the shared families and the scenarios' own modules"
    )
    nested = [module for module in _SITES.modules if module.count("/") > 3]
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


def _assert_site_shapes_live(_SITES: PropSites) -> None:
    """Fail unless each shape of keep and read site has a live subject.

    A function for the same reason as :func:`_assert_declarations_found`.
    """
    assert _SITES.direct_keeps & _SITES.constants, "no direct keep site"
    assert _SITES.direct_reads & _SITES.constants, "no direct read site"
    assert _SITES.aliased_keeps & _SITES.constants, (
        "no prop is kept through a local alias; the alias arm now has no "
        "subject and would pass over a corpus that reintroduced one"
    )
    assert _SITES.passed_keeps & _SITES.constants, (
        "no prop is handed to a keeping parameter"
    )
    assert _SITES.passed_reads & _SITES.constants, (
        "no prop is handed to a reading parameter; that is the shape the "
        "#5535 fix introduced, and DEMOMA-22-015 is only worth what it finds"
    )
    assert _SITES.readers, "no step reads a prop parameter"
    assert _SITES.keepers, "no step keeps under a prop parameter"


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


@pytest.mark.spec("DEMOMA-22-017")
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


@pytest.mark.spec("DEMOMA-22-014")
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
        "inside a function or into a collection is reachable by nothing and "
        "is checked by nothing."
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


@pytest.mark.spec("DEMOMA-22-015")
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
            (f"vultron/demo/{path}", _corpus.parse_inline(source, path))
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
    with pytest.raises(AssertionError, match="no direct keep site"):
        _assert_site_shapes_live(_planted())


def test_dropping_any_one_site_shape_fails_the_shape_arm() -> None:
    """No shape can quietly retire: each one missing is reported by name.

    A migration that rewrote every family in one shape would otherwise narrow
    the ratchet to that shape and keep passing
    (``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the Act,
    Not on the Name of What Performs It").  Each row drops one shape from the
    control corpus and keeps the other two.
    """
    with pytest.raises(AssertionError, match="no direct keep site"):
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

    ``_story_prop_declarations``'s walk skipped packages before #5592, which
    is how a prop in a split module escaped even the uniqueness check.  The
    equivalent here is a scan that reads only flat modules.
    """
    with pytest.raises(AssertionError, match="props are declared only under"):
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


@pytest.mark.spec("DEMOMA-22-015")
@pytest.mark.parametrize(
    ("annotation", "reason"),
    [
        ("StoryProp[str] | None = None", "has a default, admits None"),
        ("StoryProp[str] = _NO_PROP", "has a default"),
        ("StoryProp[str] | None", "admits None"),
        ("Optional[StoryProp[str]]", "admits None"),
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


@pytest.mark.spec("DEMOMA-22-016")
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


@pytest.mark.spec("DEMOMA-22-017")
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
