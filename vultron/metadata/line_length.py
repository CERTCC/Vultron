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
"""The 88-character prose limit outside ``docs/``, for text markdownlint skips.

Markdown outside ``docs/`` is held to :data:`LINE_LIMIT` by markdownlint's
``MD013`` (``.markdownlint-cli2.yaml``; ``docs/`` keeps no limit, SG-38). Spec
YAML and Python doc lines (comments and docstrings) have no linter that can
take a baseline, and the corpus predates the limit, so this module holds them
back per line instead (PD-10-002): each extractor returns the set of overlong
lines in a tree, and the growth guard
(:func:`vultron.metadata.specs.growth_guard.added_since_base`) fails a branch
for each line it adds. A line edited, or written new, must fit; a line left
alone is not this branch's doing.

A line counts as overlong as markdownlint's non-strict ``MD013`` counts it:
longer than the limit *and* with whitespace past the limit. A line whose
overflow is one unbreakable token, such as a URL or a pytest node ID, cannot be
wrapped and is not reported.

Requirements: specs/project-documentation.yaml PD-10.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

from vultron.metadata.base import iter_tree_texts

#: The prose line limit outside ``docs/`` (AGENTS.md § Markdown Formatting).
#: ``.markdownlint-cli2.yaml`` ``MD013.line_length`` and pyproject's ruff
#: ``max-doc-length`` carry the same number; a test pins all three.
LINE_LIMIT = 88

#: Top-level directories whose ``*.py`` doc lines are held to the limit.
PYTHON_ROOTS: tuple[str, ...] = (
    "vultron",
    "test",
    "integration_tests",
    "scripts",
    ".agents",
)

#: The directory of spec YAML files.
SPEC_ROOT = "specs"

_WHITESPACE_RE = re.compile(r"\s")
_DOC_OPEN_RE = re.compile(r"^[rRbBuUfF]{0,2}(\"\"\"|''')")
_TRIPLE_RE = re.compile(r"\"\"\"|'''")


def is_overlong(line: str, limit: int = LINE_LIMIT) -> bool:
    """Whether *line* exceeds *limit* with whitespace past the limit."""
    text = line.rstrip("\r\n")
    return len(text) > limit and bool(_WHITESPACE_RE.search(text[limit:]))


def _items(rel: str, lines: Iterable[str]) -> Iterator[str]:
    """One item per overlong line: ``"<rel>: <text>"``, numbered on repeat.

    Keyed by text, not line number, so a line that only moved is the same
    item at the base and the head.
    """
    seen: Counter[str] = Counter()
    for line in lines:
        text = line.strip()
        seen[text] += 1
        n = seen[text]
        yield f"{rel}: {text}" if n == 1 else f"{rel}: {text} (#{n})"


def overlong_spec_yaml_lines(repo_root: Path) -> frozenset[str]:
    """Every overlong line of every ``specs/**/*.yaml`` file under *repo_root*."""
    items: set[str] = set()
    for rel, text in iter_tree_texts(repo_root, (SPEC_ROOT,), "*.yaml"):
        lines = text.splitlines()
        items.update(_items(rel, (ln for ln in lines if is_overlong(ln))))
    return frozenset(items)


def _license_header_end(lines: list[str]) -> int:
    """Index of the first line after a leading license notice.

    Every module opens with the same copyright notice, after an optional
    shebang and blank lines, and one line of it runs past the limit. The notice
    is a fixed template, not prose an author wraps, so its comment lines are
    skipped: the leading comment block up to its last line naming Carnegie
    Mellon. A comment after that line is read like any other.
    """
    start = 1 if lines and lines[0].startswith("#!") else 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = start
    notice_end = 0
    while end < len(lines) and lines[end].lstrip().startswith("#"):
        if "Carnegie Mellon" in lines[end]:
            notice_end = end + 1
        end += 1
    return notice_end


def _scan_triples(text: str, quote: str | None) -> str | None:
    """The triple quote *text* leaves open, given the one open before it."""
    for match in _TRIPLE_RE.finditer(text):
        if quote is None:
            quote = match.group(0)
        elif match.group(0) == quote:
            quote = None
    return quote


def python_doc_lines(source: str) -> Iterator[str]:
    """The comment and docstring lines of *source*, as ruff's ``W505`` reads.

    A doc line is a comment-only line, or a line of a string statement — a
    triple-quoted string that opens a line, as docstrings do. A line of a
    triple-quoted string opened mid-line (``x = \"\"\"``) is data and is not
    one. A line scan rather than a tokenizer: the growth guard reads the whole
    tree twice.
    """
    lines = source.splitlines()
    open_quote: str | None = None
    in_doc = False
    for line in lines[_license_header_end(lines) :]:
        stripped = line.lstrip()
        if open_quote is not None:
            if in_doc:
                yield line
            open_quote = _scan_triples(line, open_quote)
            continue
        if stripped.startswith("#"):
            yield line
            continue
        doc = _DOC_OPEN_RE.match(stripped)
        open_quote = _scan_triples(stripped, None)
        in_doc = doc is not None
        if in_doc:
            yield line


def overlong_python_doc_lines(repo_root: Path) -> frozenset[str]:
    """Every overlong doc line of every ``*.py`` under :data:`PYTHON_ROOTS`."""
    items: set[str] = set()
    for rel, source in iter_tree_texts(repo_root, PYTHON_ROOTS, "*.py"):
        overlong = (ln for ln in python_doc_lines(source) if is_overlong(ln))
        items.update(_items(rel, overlong))
    return frozenset(items)


__all__ = [
    "LINE_LIMIT",
    "PYTHON_ROOTS",
    "SPEC_ROOT",
    "is_overlong",
    "overlong_python_doc_lines",
    "overlong_spec_yaml_lines",
    "python_doc_lines",
]
