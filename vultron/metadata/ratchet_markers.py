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
"""Owner and permanent markers on ratchet baselines under ``test/`` (ARCH-18-003).

A ratchet baseline is a module-level constant whose name says it is one:
``KNOWN_*``, ``*_BASELINE``, ``MAX_*`` or ``*_EXEMPTIONS`` (leading underscores
ignored). Once it is not at its terminal value -- an empty collection or a zero
ceiling -- it must carry one of two comments, either directly above the
assignment (in the comment block that touches it) or trailing its first line:

- ``# owner: #N`` -- the issue that drives the baseline to its terminal value
  (a ratchet, ARCH-18-005);
- ``# permanent: <reference>`` -- the issue (``#N``), ADR (``ADR-NNNN``) or spec
  requirement (``ARCH-18-003``) that made it permanent by design (a pinned
  exemption set). The reference must cite one of those on the marker's line.

This module is the one parser of those markers. The offline architecture test
(``test/architecture/test_ratchet_baselines_name_an_owner.py``) feeds it the
shared corpus's cached trees; the scheduled closed-owner report (ARCH-18-004)
reads :attr:`Baseline.owners` through :func:`scan_paths`. Neither makes a
network call here: whether a cited owner is still open is the caller's
question.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

#: A constant-case identifier (upper case, digits and underscores).
_CONSTANT_CASE = re.compile(r"[A-Z0-9_]+")

#: ``# owner: #N`` -- group 1 is the issue number; anything else after
#: ``owner:`` is a malformed marker.
_OWNER_MARKER = re.compile(r"#\s*owner:\s*(.*)$")
_OWNER_ISSUE = re.compile(r"#(\d+)\b")

#: A marker trailing the assignment's own line.
_TRAILING_MARKER = re.compile(r"#\s*(?:owner|permanent):.*$")

#: ``# permanent: <reference>`` -- group 1 is the reference text.
_PERMANENT_MARKER = re.compile(r"#\s*permanent:\s*(.*)$")

#: What a permanent reference must cite: an issue, an ADR, or a spec ID.
_CITATION = re.compile(
    r"#\d+\b|\bADR-\d{4}\b|\b[A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d{2}-\d{3}\b"
)

#: Callables whose zero-argument (or empty-argument) call is an empty value.
_EMPTY_CONSTRUCTORS = frozenset(
    {"frozenset", "set", "list", "tuple", "dict", "sorted", "MappingProxyType"}
)


def is_ratchet_name(name: str) -> bool:
    """Whether *name* is named as a ratchet baseline (ARCH-18-003).

    ``KNOWN_*``, ``*_BASELINE``, ``MAX_*`` or ``*_EXEMPTIONS`` in constant case;
    leading underscores are ignored, so ``_BASELINE`` and ``_KNOWN_X`` count.
    """
    if not _CONSTANT_CASE.fullmatch(name):
        return False
    bare = name.lstrip("_")
    return (
        bare.startswith(("KNOWN_", "MAX_"))
        or name.endswith("_BASELINE")
        or name.endswith("_EXEMPTIONS")
    )


def is_terminal_value(value: ast.expr) -> bool:
    """Whether *value* is statically at a terminal value: empty or zero.

    An empty literal (``[]``, ``()``, ``{}``), a zero number, or a call such as
    ``frozenset()`` / ``frozenset({})`` / ``MappingProxyType({})`` whose only
    argument is itself terminal. Anything else -- including a value computed
    at import time -- is treated as non-empty, so it needs a marker.
    """
    if isinstance(value, ast.Constant):
        return (
            isinstance(value.value, (int, float))
            and not isinstance(value.value, bool)
            and value.value == 0
        )
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return not value.elts
    if isinstance(value, ast.Dict):
        return not value.keys
    if isinstance(value, ast.Call) and not value.keywords:
        func = value.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else None
        )
        if name not in _EMPTY_CONSTRUCTORS:
            return False
        if not value.args:
            return True
        return len(value.args) == 1 and is_terminal_value(value.args[0])
    return False


@dataclass(frozen=True)
class Baseline:
    """One ratchet-named module-level constant and its markers.

    ``owners`` holds every issue an ``# owner:`` marker cites; ``permanent``
    holds the reference text of each ``# permanent:`` marker (possibly empty);
    ``malformed_owners`` holds the text of each ``# owner:`` marker that names
    no ``#N`` issue.
    """

    path: Path
    name: str
    line: int
    terminal: bool
    owners: tuple[int, ...] = ()
    permanent: tuple[str, ...] = ()
    malformed_owners: tuple[str, ...] = ()

    @property
    def where(self) -> str:
        """``path:line NAME`` for messages."""
        return f"{self.path}:{self.line} {self.name}"

    def violations(self) -> list[str]:
        """Every way this baseline breaks ARCH-18-003; empty when it complies.

        A terminal baseline needs no marker, but a malformed or citation-free
        marker on it is still reported: a marker that says nothing is wrong
        wherever it sits.
        """
        problems = [
            f"{self.where}: '# owner: {text}' names no issue; write"
            " '# owner: #N'"
            for text in self.malformed_owners
        ]
        problems += [
            f"{self.where}: '# permanent: {text}' cites no issue (#N), ADR"
            " (ADR-NNNN) or spec requirement (XX-NN-NNN)"
            for text in self.permanent
            if not _CITATION.search(text)
        ]
        if self.owners and self.permanent:
            problems.append(
                f"{self.where}: carries both '# owner:' and '# permanent:';"
                " a ratchet has an owner, a pinned exemption set a permanent"
                " reason, never both (ARCH-18-005)"
            )
        if (
            not self.terminal
            and not self.owners
            and not self.permanent
            and not self.malformed_owners
        ):
            problems.append(
                f"{self.where}: non-empty baseline names no owner; add"
                " '# owner: #N' (the issue that drives it to empty or zero) or"
                " '# permanent: <issue, ADR or spec ID>' directly above it"
            )
        return problems


def _marker_lines(lines: list[str], first_line: int) -> Iterator[str]:
    """The trailing comment of the assignment's first line, then the
    contiguous comment block directly above it, nearest first."""
    trailing = _TRAILING_MARKER.search(lines[first_line - 1])
    if trailing:
        yield trailing.group(0)
    index = first_line - 2
    while index >= 0 and lines[index].lstrip().startswith("#"):
        yield lines[index].strip()
        index -= 1


def _assigned_names(node: ast.stmt) -> tuple[list[str], ast.expr | None]:
    """The plain names a module-level assignment binds, with its value."""
    if isinstance(node, ast.Assign):
        return [
            t.id for t in node.targets if isinstance(t, ast.Name)
        ], node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id], node.value
    return [], None


def baselines_in(tree: ast.AST, source: str, path: Path) -> list[Baseline]:
    """Every ratchet-named module-level constant in *tree*, with its markers.

    *source* is the text *tree* was parsed from (markers are comments, which
    the tree drops); *path* is carried into each :class:`Baseline` for
    reporting. Callers that already hold a cached parse -- the architecture
    corpus -- pass it here rather than parsing again.
    """
    if not isinstance(tree, ast.Module):
        return []
    lines = source.splitlines()
    found: list[Baseline] = []
    for node in tree.body:
        names, value = _assigned_names(node)
        if value is None:
            continue
        for name in names:
            if not is_ratchet_name(name):
                continue
            owners: list[int] = []
            malformed: list[str] = []
            permanent: list[str] = []
            for comment in _marker_lines(lines, node.lineno):
                if owner := _OWNER_MARKER.match(comment):
                    text = owner.group(1).strip()
                    issue = _OWNER_ISSUE.match(text)
                    if issue:
                        owners.append(int(issue.group(1)))
                    else:
                        malformed.append(text)
                elif perm := _PERMANENT_MARKER.match(comment):
                    permanent.append(perm.group(1).strip())
            found.append(
                Baseline(
                    path=path,
                    name=name,
                    line=node.lineno,
                    terminal=is_terminal_value(value),
                    owners=tuple(owners),
                    permanent=tuple(permanent),
                    malformed_owners=tuple(malformed),
                )
            )
    return found


def baselines_in_source(source: str, path: Path) -> list[Baseline]:
    """Parse *source* and return its baselines (see :func:`baselines_in`)."""
    return baselines_in(ast.parse(source, filename=str(path)), source, path)


def scan_paths(paths: Iterable[Path]) -> list[Baseline]:
    """Read, parse and scan each Python file in *paths*.

    For a caller with no cached corpus (a CI script). A file that cannot be
    read or parsed raises: a baseline silently skipped is an owner unchecked.
    """
    found: list[Baseline] = []
    for path in paths:
        found += baselines_in_source(path.read_text(encoding="utf-8"), path)
    return found


def violations(baselines: Iterable[Baseline]) -> list[str]:
    """Every ARCH-18-003 violation across *baselines*, in order."""
    return [problem for b in baselines for problem in b.violations()]
