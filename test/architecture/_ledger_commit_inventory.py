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

"""Derive, from code, the ledger ``event_type`` values the CASE_MANAGER commits.

Companion to ``test_ledger_event_types_are_replayed.py`` (RSH-08-004).  Two
paths commit an entry:

* **The receive-side commit.**  ``CommitCaseLedgerEntryNode`` records the
  received activity under its ``MessageSemantics`` value.  A received use case
  reaches it when a tree factory it calls — directly or through further
  ``vultron.core`` functions — passes ``create_receive_activity_tree`` a
  ``case_id`` that is not the literal ``None`` (CLP-10-013), or builds the
  commit node or guarded-commit subtree itself.  :func:`received_commit_semantics`
  follows those calls from every routed use case's methods.
* **Explicit commits.**  A node that commits an entry of its own passes
  ``event_type=`` to the commit tree; :func:`explicit_event_types` collects
  every such keyword's value (a literal, a constant, or a ``self.<CONST>``
  class constant resolved through each subclass), plus every ``*EVENT_TYPE``
  constant passed as a positional call argument under ``vultron/core``.  A
  value threaded through a parameter (``event_type=event_type``) is found at
  the call that supplies it; any other unresolvable value fails the scan.  A
  constant a replay slot only compares against is not a call argument, so
  defining one never makes a type look committed.

Not covered, by design: the ``sync-log-entry`` trigger
(``vultron/core/use_cases/triggers/sync_log_entry.py``), an operator tool
whose client names the event type of an ``Announce(VulnerabilityCase)``
snapshot.

No source is read or parsed outside ``_corpus`` (TB-13-001, TB-13-003): a
function reached from a live object is found in the shared parse by
``_corpus.function_definition``.  A text-only fixed point
(:func:`_names_that_may_commit`) first names every top-level definition that
could reach a commit, and the precise walk parses only modules mentioning one
of those names (TB-13-002, TB-13-008); explicit commits are found only on the
lines that mention ``event_type=`` or ``EVENT_TYPE``.  Both derivations pause
the garbage collector and the combined set is cached per process, so each
ratchet test stays inside the TB-13-004 budget.
"""

import ast
import functools
import importlib
import inspect
import re
from collections.abc import Callable, Iterator
from types import ModuleType
from typing import Any

from test.architecture import _corpus
from vultron.semantic_registry import use_case_map

_RECEIVE_FACTORY = "create_receive_activity_tree"
#: Building either of these commits the received activity whatever the case id.
_COMMIT_BUILDERS = frozenset(
    {
        "CommitCaseLedgerEntryNode",
        "create_guarded_commit_case_ledger_entry_tree",
    }
)
_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"
_MAX_DEPTH = 8


def _callee_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _resolve(name: str, module: ModuleType) -> Any:
    """Resolve *name* as *module* sees it, or through a module it imported."""
    found = getattr(module, name, None)
    if found is not None:
        return found
    for value in vars(module).values():
        if inspect.ismodule(value) and hasattr(value, name):
            return getattr(value, name)
    return None


#: A top-level ``def`` or ``class`` line, and a bare-name call.
_TOP_LEVEL_DEFINITION = re.compile(
    r"^(?:async\s+def|def|class)\s+(\w+)", re.MULTILINE
)
_DEFINING_PREFIXES = ("def ", "class ")


def _called_names(span: str) -> frozenset[str]:
    """Every identifier written directly before a ``(`` in *span*.

    Splits on ``(`` and takes each chunk's trailing identifier, skipping the
    name a ``def`` or ``class`` line defines — several times faster than a
    regex, which retries at every position of a mostly-prose file.
    """
    names: set[str] = set()
    for chunk in span.split("(")[:-1]:
        end = len(chunk)
        start = end
        while start and (
            chunk[start - 1].isalnum() or chunk[start - 1] == "_"
        ):
            start -= 1
        if start == end or chunk[start].isdigit():
            continue
        if chunk.endswith(_DEFINING_PREFIXES, 0, start):
            continue
        names.add(chunk[start:end])
    return frozenset(names)


def _text_summaries(source: str) -> Iterator[tuple[str, frozenset[str]]]:
    """``(name, called names)`` for each top-level definition in *source*.

    Text, not AST: a definition's span runs to the next top-level definition,
    and every ``name(`` in it counts as a call.  Both over-approximate (a
    trailing module statement, a name in a string, a class's every method),
    which :func:`_names_that_may_commit` permits.
    """
    starts = list(_TOP_LEVEL_DEFINITION.finditer(source))
    if not starts:
        return
    ends = [match.start() for match in starts[1:]] + [len(source)]
    for match, end in zip(starts, ends, strict=True):
        span = source[match.end() : end]
        yield match.group(1), _called_names(span)


@functools.cache
def _names_that_may_commit() -> frozenset[str]:
    """Top-level ``vultron.core`` names whose definition may reach a commit.

    A fixed point by name over source text: start from the commit builders
    and the receive factory, then add every top-level function or class
    whose span calls a name already in the set.  It reads each module's text
    once from ``_corpus`` and parses none, so it needs no prefilter; its
    result *is* the prefilter of the precise walk, which parses only a module
    that mentions one of these names (TB-13-002, TB-13-008).  It
    over-approximates — by name, not by resolution, and ignoring
    ``case_id=None`` — and :func:`_commits` decides.
    """
    seeds = frozenset({*_COMMIT_BUILDERS, _RECEIVE_FACTORY})
    summaries = [
        summary
        for _, source in _corpus.all_sources(under=_CORE_ROOT)
        for summary in _text_summaries(source)
    ]
    names: set[str] = set()
    while found := {
        name
        for name, called in summaries
        if name not in names and called & (seeds | names)
    }:
        names |= found
    return frozenset(names)


def _calls_in(node: ast.AST) -> Iterator[ast.Call]:
    return (n for n in ast.walk(node) if isinstance(n, ast.Call))


@functools.cache
def _named_calls(fn: Callable[..., Any]) -> tuple[ast.Call, ...]:
    """Every call in *fn*'s definition whose callee has a bare name.

    Empty, without parsing, unless *fn*'s module mentions a name that may
    commit (:func:`_names_that_may_commit`); the definition otherwise comes
    from the shared corpus parse (:func:`_corpus.function_definition`), so no
    source is re-read or parsed twice (TB-13-001, TB-13-003).
    """
    fragments = (
        *_COMMIT_BUILDERS,
        _RECEIVE_FACTORY,
        *_names_that_may_commit(),
    )
    definition = _corpus.function_definition(fn, mentioning=fragments)
    if definition is None:
        return ()
    return tuple(
        node
        for node in _calls_in(definition)
        if _callee_name(node) is not None
    )


def _commits(fn: Callable[..., Any], seen: set[Any], depth: int = 0) -> bool:
    """True when *fn*, or a ``vultron.core`` function it calls, commits."""
    if fn in seen or depth > _MAX_DEPTH:
        return False
    seen.add(fn)
    calls = _named_calls(fn)
    if not calls:
        return False
    module = inspect.getmodule(fn)
    assert module is not None
    return any(_call_commits(call, module, seen, depth) for call in calls)


def _passes_a_case_id(call: ast.Call) -> bool:
    """True unless a ``create_receive_activity_tree`` call passes ``None``."""
    case_id = next(
        (kw.value for kw in call.keywords if kw.arg == "case_id"),
        call.args[1] if len(call.args) > 1 else None,
    )
    return not (isinstance(case_id, ast.Constant) and case_id.value is None)


def _call_commits(
    call: ast.Call, module: ModuleType, seen: set[Any], depth: int
) -> bool:
    """True when *call* commits, directly or through the function it names."""
    name = _callee_name(call)
    assert name is not None
    if name in _COMMIT_BUILDERS:
        return True
    if name == _RECEIVE_FACTORY:
        return _passes_a_case_id(call)
    if name not in _names_that_may_commit():
        return False
    target = _resolve(name, module)
    if inspect.isclass(target):
        target = getattr(target, "__init__", None)
    return (
        inspect.isfunction(target)
        and target.__module__.startswith("vultron.core")
        and _commits(target, seen, depth + 1)
    )


@_corpus.gc_paused()
def received_commit_semantics() -> set[str]:
    """``MessageSemantics`` values a received use case commits as an entry."""
    committed: set[str] = set()
    for semantic, use_case in use_case_map().items():
        seen: set[Any] = set()
        if any(
            # Inherited methods too: a shared base class may build the tree.
            _commits(member, seen)
            for _, member in inspect.getmembers(use_case, inspect.isfunction)
        ):
            committed.add(semantic.value)
    return committed


def _module_name(path: Any) -> str:
    rel = path.relative_to(_corpus.REPO_ROOT).with_suffix("")
    return ".".join(rel.parts)


#: ``event_type=`` values that thread a caller's value through rather than
#: name one; the scan finds the value where the caller supplies it.  Any other
#: unresolvable value fails the scan, so a new commit cannot go unclassified.
_PASS_THROUGH_EVENT_TYPES = frozenset(
    {
        "event_type",
        "self.event_type",
        "self._event_type",
        "chain_entry.event_type",
    }
)


def _constant_value(expr: ast.expr, module: ModuleType) -> str | None:
    """The string *expr* names: a literal, or a constant reached from *module*.

    Handles a bare name (``EVENT_TYPE``) and an attribute chain rooted at a
    module-level name (``MessageSemantics.FOO.value``).
    """
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    chain: list[str] = []
    while isinstance(expr, ast.Attribute):
        chain.insert(0, expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name) or expr.id == "self":
        return None
    value: Any = getattr(module, expr.id, None)
    for attr in chain:
        value = getattr(value, attr, None)
    return value if isinstance(value, str) else None


def _subclasses(cls: type) -> Iterator[type]:
    yield cls
    for sub in cls.__subclasses__():
        yield from _subclasses(sub)


def _class_attribute_values(
    owner: ast.ClassDef, attr: str, module: ModuleType
) -> set[str]:
    """``<cls>.<attr>`` for *owner* and every subclass that overrides it."""
    cls = getattr(module, owner.name, None)
    if not inspect.isclass(cls):
        return set()
    values = {getattr(sub, attr, None) for sub in _subclasses(cls)}
    return {value for value in values if isinstance(value, str)}


def _calls_on_lines_with(
    path: Any, tree: ast.AST, fragment: str
) -> Iterator[ast.Call]:
    """Every call in *tree* whose source lines include *fragment*.

    Descends only into nodes whose line span holds such a line, so the bulk
    of a module — prose, unrelated classes — is never visited.
    """
    lines = {
        number
        for number, line in enumerate(
            _corpus.source_of(path).splitlines(), start=1
        )
        if fragment in line
    }
    pending: list[ast.AST] = [tree]
    while pending:
        node = pending.pop()
        start = getattr(node, "lineno", None)
        if start is not None:
            end = getattr(node, "end_lineno", None) or start
            if not any(start <= line <= end for line in lines):
                continue
            if isinstance(node, ast.Call):
                yield node
        pending.extend(ast.iter_child_nodes(node))


def _enclosing_class(tree: ast.AST, node: ast.AST) -> ast.ClassDef | None:
    """The innermost class whose source lines contain *node*, if any."""
    line = _corpus.node_line(node)
    owner: ast.ClassDef | None = None
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        end = cls.end_lineno or cls.lineno
        if cls.lineno <= line <= end and (
            owner is None or cls.lineno >= owner.lineno
        ):
            owner = cls
    return owner


def _event_type_keyword_values(
    path: Any, tree: ast.AST, module: ModuleType
) -> Iterator[str]:
    """The value of every ``event_type=`` keyword in *tree*.

    ``self.<NAME>`` with an upper-case *NAME* is a class constant: it resolves
    through the enclosing class and each subclass that overrides it.

    Raises:
        AssertionError: on a value the scan cannot resolve and that is not a
            known pass-through (:data:`_PASS_THROUGH_EVENT_TYPES`).
    """
    for node in _calls_on_lines_with(path, tree, "event_type="):
        for kw in node.keywords:
            if kw.arg != "event_type":
                continue
            value = _constant_value(kw.value, module)
            if value is not None:
                yield value
                continue
            expr = kw.value
            if (
                isinstance(expr, ast.Attribute)
                and isinstance(expr.value, ast.Name)
                and expr.value.id == "self"
                and expr.attr.lstrip("_").isupper()
                and (owner := _enclosing_class(tree, node)) is not None
            ):
                yield from _class_attribute_values(owner, expr.attr, module)
                continue
            source = ast.unparse(expr)
            assert source in _PASS_THROUGH_EVENT_TYPES, (
                f"{module.__name__}:{node.lineno}: cannot resolve"
                f" event_type={source}; name a constant, or add a"
                " pass-through whose caller the scan resolves"
            )


def _event_type_positional_values(
    path: Any, tree: ast.AST, module: ModuleType
) -> Iterator[str]:
    """Each ``*EVENT_TYPE`` constant passed as a positional call argument.

    A commit helper that takes the event type positionally
    (``_commit_one(case_id, object_id, CREATE_CASE_EVENT_TYPE, ...)``) is found
    here.  A constant only *compared* against an entry's ``event_type`` — a
    replay slot's condition — is never a call argument, so it is not counted.
    """
    for node in _calls_on_lines_with(path, tree, "EVENT_TYPE"):
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id.endswith("EVENT_TYPE"):
                value = _constant_value(arg, module)
                if value is not None:
                    yield value


@_corpus.gc_paused()
def explicit_event_types() -> set[str]:
    """Event types a ``vultron.core`` node passes to a commit of its own."""
    found: set[str] = set()
    for path, tree in _corpus.files_mentioning("EVENT_TYPE", under=_CORE_ROOT):
        module = importlib.import_module(_module_name(path))
        found.update(_event_type_positional_values(path, tree, module))
    for path, tree in _corpus.files_mentioning(
        "event_type=", under=_CORE_ROOT
    ):
        module = importlib.import_module(_module_name(path))
        found.update(_event_type_keyword_values(path, tree, module))
    return found


@functools.cache
def _committed_event_types() -> frozenset[str]:
    return frozenset(received_commit_semantics() | explicit_event_types())


def committed_event_types() -> set[str]:
    """Every ``event_type`` the code base can commit to a case ledger.

    Derived once per process: the scan reads only import-time state, and the
    ratchets that ask for it each stay inside their budget (TB-13).
    """
    return set(_committed_event_types())
