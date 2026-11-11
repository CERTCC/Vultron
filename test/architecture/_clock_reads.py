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
"""Find every clock read in the application's source (ADR-0176).

A **clock read** is a reference to anything that returns the current time:

- the core clock helpers that read the clock — ``now_utc`` and
  ``require_future_aware`` — by name or attribute, called or not, so
  ``Field(default_factory=now_utc)`` counts (the ordered-stamp and deadline
  helpers take the act's instant and read no clock, ADR-0176);
- ``now``, ``utcnow`` or ``today`` on ``datetime`` or ``date``;
- ``time``, ``time_ns``, ``monotonic``, ``monotonic_ns``, ``perf_counter`` or
  ``perf_counter_ns`` from the ``time`` module.

A read through a clock port (``clock.now()``) is not one: the port is how an
act's entry point reads the clock.

Each read is reported as a :data:`ClockRead`, ``(path, scope, read)``: the
file relative to the repository root, the dotted name of the enclosing
definitions (a class-body field adds its own name; ``<module>`` at top
level), and the read's name.  Two reads of one name in one scope are two
equal items, so a baseline is a multiset.

Loose readings, by direction (``notes/architecture-ratchet-corpus.md``):

- **Can miss.** A read reached through ``getattr``, or through a variable
  bound to one of these callables at run time.  An import alias is followed
  (``import time as t``, ``from datetime import datetime as dt``,
  ``from time import monotonic as m``).  The package holds none today.
- **Can invent.** A local name or attribute that shadows a helper's name, or
  an attribute ``now``/``today`` on an object merely named ``datetime`` or
  ``date``.  Narrowed to the receiver's last name; the package holds none
  today.

``vultron/metadata/`` is not scanned: it is the repository's own tooling
(history, ADR and spec CLIs), not the application, and ADR-0176 governs the
application's time.
"""

import ast
from collections import Counter
from collections.abc import Iterator
from functools import cache
from pathlib import Path

from test.architecture import _corpus

#: ``(path relative to the repository root, enclosing scope, read name)``.
ClockRead = tuple[str, str, str]

_SCAN_ROOT = _corpus.REPO_ROOT / "vultron"
_NOT_SCANNED = (_SCAN_ROOT / "metadata",)

_HELPERS = frozenset(
    {
        "now_utc",
        "require_future_aware",
    }
)
_WALL_ATTRS = frozenset({"now", "utcnow", "today"})
_WALL_RECEIVERS = frozenset({"datetime", "date"})
_TIME_FUNCS = frozenset(
    {
        "time",
        "time_ns",
        "monotonic",
        "monotonic_ns",
        "perf_counter",
        "perf_counter_ns",
    }
)

#: Substrings at least one of which every module with a read contains.
_FRAGMENTS = (
    "now_utc",
    "require_future_aware",
    "now(",
    "utcnow",
    "today",
    "time",
    "perf_counter",
)


def _last_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


class _Finder(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.scope: list[str] = []
        self.reads: list[ClockRead] = []
        # Names bound by ``from time import monotonic`` and the like, and
        # import aliases of the helpers, mapped to the read they stand for.
        self.bound: dict[str, str] = {}
        # Local names for the ``time`` module, and aliases of ``datetime`` /
        # ``date`` bound by ``from datetime import datetime as dt``.
        self.time_modules: set[str] = {"time"}
        self.wall_types: dict[str, str] = {
            name: name for name in _WALL_RECEIVERS
        }

    def _record(self, read: str) -> None:
        scope = ".".join(self.scope) or "<module>"
        self.reads.append((self.path, scope, read))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "time" and alias.asname:
                self.time_modules.add(alias.asname)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            local = alias.asname or alias.name
            if node.module == "time" and alias.name in _TIME_FUNCS:
                self.bound[local] = f"time.{alias.name}"
            elif alias.name in _HELPERS and alias.asname:
                self.bound[local] = alias.name
            elif (
                node.module == "datetime"
                and alias.name in _WALL_RECEIVERS
                and alias.asname
            ):
                self.wall_types[alias.asname] = alias.name

    def _visit_scope(self, node: ast.AST, name: str) -> None:
        self.scope.append(name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node, node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        for child in node.body:
            target: ast.expr | None = None
            if isinstance(child, ast.AnnAssign):
                target = child.target
            elif isinstance(child, ast.Assign) and len(child.targets) == 1:
                target = child.targets[0]
            if isinstance(target, ast.Name):
                self._visit_scope(child, target.id)
            else:
                self.visit(child)
        self.scope.pop()

    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load):
            return
        if node.id in _HELPERS:
            self._record(node.id)
        elif node.id in self.bound:
            self._record(self.bound[node.id])

    def visit_Attribute(self, node: ast.Attribute) -> None:
        receiver = _last_name(node.value)
        if node.attr in _HELPERS:
            self._record(node.attr)
        elif node.attr in _WALL_ATTRS and receiver in self.wall_types:
            self._record(f"{self.wall_types[receiver]}.{node.attr}")
        elif (
            node.attr in _TIME_FUNCS
            and isinstance(node.value, ast.Name)
            and node.value.id in self.time_modules
        ):
            self._record(f"time.{node.attr}")
        else:
            self.generic_visit(node)


def reads_in_source(source: str, path: str) -> list[ClockRead]:
    """Every clock read in *source*, reported against *path*."""
    finder = _Finder(path)
    finder.visit(_corpus.parse_inline(source, path))
    return finder.reads


def _scanned(path: Path) -> bool:
    return not any(path.is_relative_to(root) for root in _NOT_SCANNED)


def _reads() -> Iterator[ClockRead]:
    for path, tree in _corpus.files_mentioning(*_FRAGMENTS, under=_SCAN_ROOT):
        if not _scanned(path):
            continue
        finder = _Finder(path.relative_to(_corpus.REPO_ROOT).as_posix())
        finder.visit(tree)
        yield from finder.reads


@cache
def clock_reads() -> Counter[ClockRead]:
    """Every clock read under ``vultron/`` outside the tooling, counted."""
    with _corpus.gc_paused():
        return Counter(_reads())
