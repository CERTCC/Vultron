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
ceiling -- it must carry one of two comments (``#`` or ``#:``), either directly
above the assignment (in the comment block that touches it) or trailing its
first line:

- ``# owner: #N`` -- the issue that drives the baseline to its terminal value
  (a ratchet, ARCH-18-005);
- ``# permanent: <reference>`` -- the issue (``#N``), ADR (``ADR-NNNN``) or spec
  requirement (``ARCH-18-003``) that made it permanent by design (a pinned
  exemption set). The reference must cite one of those on the marker's line.

This module is the one parser of those markers. The offline architecture test
(``test/architecture/test_ratchet_baselines_name_an_owner.py``) feeds it the
shared corpus's cached trees; the scheduled closed-owner report
(:mod:`vultron.metadata.ratchet_owners`, ARCH-18-004) reads
:attr:`Baseline.owners` through :func:`baselines_in_source`. Neither makes a
network call here: whether a cited owner is still open is the caller's
question.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.file_loading import MetadataLoadError, read_utf8

#: A constant-case identifier (upper case, digits and underscores).
_CONSTANT_CASE = re.compile(r"[A-Z0-9_]+")

#: ``# owner: <text>`` (or the Sphinx ``#: owner:`` form) -- group 1 is the
#: text, which must cite at least one ``#N`` issue.
_OWNER_MARKER = re.compile(r"#:?\s*owner:\s*(.*)$")
_OWNER_ISSUE = re.compile(r"#(\d+)\b")

#: ``# permanent: <reference>`` (or ``#: permanent:``) -- group 1 is the
#: reference text.
_PERMANENT_MARKER = re.compile(r"#:?\s*permanent:\s*(.*)$")

#: What a permanent reference must cite: an issue, an ADR, or a spec ID.
_CITATION = re.compile(
    r"#[1-9]\d*\b|\bADR-\d{4}\b|\b[A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d{2}-\d{3}\b"
)

#: Methods that grow a collection in place, so a module-level call on a
#: baseline means its literal is not its value.
_MUTATORS = frozenset(
    {
        "add",
        "append",
        "extend",
        "insert",
        "update",
        "setdefault",
        "__setitem__",
    }
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


def _comments(source: str) -> tuple[dict[int, str], frozenset[int]]:
    """Real comments by line (never ``#`` inside a string), and the lines
    that hold nothing but a comment."""
    by_line: dict[int, str] = {}
    alone: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        row, col = token.start
        by_line[row] = token.string
        # The token's own physical line: ``str.splitlines`` also breaks at
        # form feeds and Unicode separators, so its rows drift from these.
        if not token.line[:col].strip():
            alone.add(row)
    return by_line, frozenset(alone)


def _marker_comments(
    comments: dict[int, str], alone: frozenset[int], first_line: int
) -> Iterator[str]:
    """The trailing comment of the assignment's first line, then the
    contiguous comment-only block directly above it, nearest first."""
    if first_line in comments and first_line not in alone:
        yield comments[first_line]
    row = first_line - 1
    while row in alone:
        yield comments[row]
        row -= 1


def _module_statements(body: list[ast.stmt]) -> Iterator[ast.stmt]:
    """Module-level statements, including those nested in ``if``, ``for``,
    ``while``, ``try``, ``with`` and ``match`` blocks (which still run at
    import), but not in a function or class body."""
    for node in body:
        yield node
        if isinstance(node, (ast.If, ast.For, ast.While)):
            yield from _module_statements(node.body + node.orelse)
        elif isinstance(node, ast.With):
            yield from _module_statements(node.body)
        elif isinstance(node, ast.Match):
            for case in node.cases:
                yield from _module_statements(case.body)
        elif isinstance(node, (ast.Try, ast.TryStar)):
            yield from _module_statements(node.body)
            for handler in node.handlers:
                yield from _module_statements(handler.body)
            yield from _module_statements(node.orelse + node.finalbody)


def _bindings(node: ast.stmt) -> Iterator[tuple[str, ast.expr]]:
    """Each plain name a statement binds, with the value bound to it.

    Unpacking pairs names with elements when the value is a literal tuple or
    list of the same length; otherwise each name gets the whole value, which
    is never terminal.
    """
    if isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.value is not None:
            yield node.target.id, node.value
        return
    if not isinstance(node, ast.Assign):
        return
    for target in node.targets:
        yield from _bind_target(target, node.value)


def _bind_target(
    target: ast.expr, value: ast.expr
) -> Iterator[tuple[str, ast.expr]]:
    """Pair the names in *target* (a name, or a tuple or list of targets,
    nested to any depth) with the parts of *value* bound to them."""
    if isinstance(target, ast.Name):
        yield target.id, value
    elif isinstance(target, (ast.Tuple, ast.List)):
        elements: list[ast.expr] = (
            value.elts
            if isinstance(value, (ast.Tuple, ast.List))
            and len(value.elts) == len(target.elts)
            else [value] * len(target.elts)
        )
        for element, bound in zip(target.elts, elements, strict=True):
            yield from _bind_target(element, bound)


def _import_time_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """*node* and its descendants, stopping at function and lambda bodies
    (which do not run at import)."""
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
        ):
            continue
        yield from _import_time_nodes(child)


def _mutated_names(node: ast.stmt) -> Iterator[str]:
    """Names a module-level statement grows in place: ``X |= ...``,
    ``X[k] = ...`` (annotated or not), and ``X.add(...)`` or another of the
    :data:`_MUTATORS` anywhere in the statement, its result used or not."""
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
        targets = [node.target]
    for target in targets:
        if isinstance(target, ast.Subscript) and isinstance(
            target.value, ast.Name
        ):
            yield target.value.id
        elif isinstance(node, ast.AugAssign) and isinstance(target, ast.Name):
            yield target.id
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return
    for sub in _import_time_nodes(node):
        if (
            isinstance(sub, ast.Call)
            and isinstance(func := sub.func, ast.Attribute)
            and func.attr in _MUTATORS
            and isinstance(func.value, ast.Name)
        ):
            yield func.value.id


def _read_markers(
    texts: Iterable[str],
) -> tuple[tuple[int, ...], tuple[str, ...], tuple[str, ...]]:
    """(owners, permanent references, malformed owner texts) in *texts*."""
    owners: list[int] = []
    permanent: list[str] = []
    malformed: list[str] = []
    for comment in texts:
        if owner := _OWNER_MARKER.match(comment):
            text = owner.group(1).strip()
            issues = [int(n) for n in _OWNER_ISSUE.findall(text) if int(n) > 0]
            if issues:
                owners += issues
            else:
                malformed.append(text)
        elif perm := _PERMANENT_MARKER.match(comment):
            permanent.append(perm.group(1).strip())
    return tuple(owners), tuple(permanent), tuple(malformed)


def baselines_in(tree: ast.AST, source: str, path: Path) -> list[Baseline]:
    """Every ratchet-named module-level constant in *tree*, with its markers.

    *source* is the text *tree* was parsed from (markers are comments, which
    the tree drops); *path* is carried into each :class:`Baseline` for
    reporting. Callers that already hold a cached parse -- the architecture
    corpus -- pass it here rather than parsing again. A baseline grown in
    place at module level (``|=``, ``.add()``, item assignment) is never
    terminal, whatever its literal.
    """
    if not isinstance(tree, ast.Module):
        return []
    comments, alone = _comments(source)
    statements = list(_module_statements(tree.body))
    mutated = {name for node in statements for name in _mutated_names(node)}
    found: list[Baseline] = []
    for node in statements:
        for name, value in _bindings(node):
            if not is_ratchet_name(name):
                continue
            owners, permanent, malformed = _read_markers(
                _marker_comments(comments, alone, node.lineno)
            )
            found.append(
                Baseline(
                    path=path,
                    name=name,
                    line=node.lineno,
                    terminal=name not in mutated and is_terminal_value(value),
                    owners=owners,
                    permanent=permanent,
                    malformed_owners=malformed,
                )
            )
    return found


def baselines_in_source(source: str, path: Path) -> list[Baseline]:
    """Parse *source* and return its baselines (see :func:`baselines_in`)."""
    return baselines_in(ast.parse(source, filename=str(path)), source, path)


def scan_paths(
    paths: Iterable[Path], root: Path | None = None
) -> list[Baseline]:
    """Read, parse and scan each Python file in *paths*.

    For a caller with no cached corpus (a CI script). When *root* is given,
    each :attr:`Baseline.path` (and any error's path) is relative to it.

    Raises:
        MetadataLoadError: When a file is not valid UTF-8 or not valid
            Python, naming it ``path:line:col`` (MS-17-001): a baseline
            silently skipped is an owner unchecked.
    """
    found: list[Baseline] = []
    for path in paths:
        shown = path.relative_to(root) if root is not None else path
        text = read_utf8(path, str(shown))
        try:
            found += baselines_in_source(text, shown)
        except SyntaxError as exc:
            raise MetadataLoadError(
                f"not valid Python: {exc.msg}",
                path=str(shown),
                line=exc.lineno,
                column=exc.offset,
            ) from exc
    return found


def violations(baselines: Iterable[Baseline]) -> list[str]:
    """Every ARCH-18-003 violation across *baselines*, in order."""
    return [problem for b in baselines for problem in b.violations()]
