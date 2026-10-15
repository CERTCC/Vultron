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
lines in a tree, and the growth guard (:func:`added_overlong_lines`) fails a
branch for each line it adds. A line edited, or written new, must fit; a line
left alone is not this branch's doing, even when a rename or a module split
carried it to another file.

A line counts as overlong as markdownlint's non-strict ``MD013`` counts it:
longer than the limit *and* with whitespace past the limit. A line whose
overflow is one unbreakable token, such as a URL or a pytest node ID, cannot be
wrapped and is not reported.

Requirements: specs/project-documentation.yaml PD-10.
"""

from __future__ import annotations

import io
import re
import token
import tokenize
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

from vultron.metadata.base import iter_tree_texts
from vultron.metadata.specs.growth_guard import (
    Extractor,
    GrowthCheck,
    compare_with_base,
)

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
#: Tokens after which a token starts a statement.
_STATEMENT_START = frozenset(
    {token.NEWLINE, token.NL, token.INDENT, token.DEDENT, token.ENCODING}
)
#: Tokens that carry no code, skipped when looking past a string.
_TRIVIA = frozenset({token.NL, token.COMMENT})


def is_overlong(line: str, limit: int = LINE_LIMIT) -> bool:
    """Whether *line* exceeds *limit* with whitespace past the limit."""
    text = line.rstrip("\r\n")
    return len(text) > limit and bool(_WHITESPACE_RE.search(text[limit:]))


def _items(rel: str, lines: Iterable[str]) -> Iterator[str]:
    """One item per overlong line: ``"<rel>: <text>"``, numbered on repeat.

    Keyed by text, not line number, so a line that only moved is the same
    item at the base and the head. A repeat is ``"<rel> (#<n>): <text>"``, so
    :func:`item_text` splits every item at its first ``": "``.
    """
    seen: Counter[str] = Counter()
    for line in lines:
        text = line.strip()
        seen[text] += 1
        n = seen[text]
        yield f"{rel}: {text}" if n == 1 else f"{rel} (#{n}): {text}"


def item_text(item: str) -> str:
    """The line text of an item :func:`_items` made, without its file."""
    return item.split(": ", 1)[1]


def new_lines(base: frozenset[str], head: frozenset[str]) -> frozenset[str]:
    """Head items for line text the tree has more of than at *base*.

    A rename or a module split moves a line to another file, so its item
    changes while the line does not. An item counts as added only when its
    text occurs more often in the whole head tree than in the base tree.
    """
    base_count = Counter(item_text(i) for i in base)
    head_count = Counter(item_text(i) for i in head)
    return frozenset(
        item
        for item in head - base
        if head_count[item_text(item)] > base_count[item_text(item)]
    )


def added_overlong_lines(
    extract: Extractor,
    *,
    repo_root: Path,
    paths: Sequence[str],
    base_ref: str | None = None,
    require_base: bool | None = None,
) -> GrowthCheck:
    """The overlong lines *extract* finds that the branch added.

    :func:`~vultron.metadata.specs.growth_guard.added_since_base`, except
    that a moved line is not counted as added (:func:`new_lines`). Arguments,
    skipping and errors are as that function documents.
    """
    seen = compare_with_base(
        extract,
        repo_root=repo_root,
        paths=paths,
        base_ref=base_ref,
        require_base=require_base,
    )
    head = seen.head_value
    if seen.base_value is None:
        return GrowthCheck(None, frozenset(), len(head), skipped=seen.skipped)
    return GrowthCheck(seen.base, new_lines(seen.base_value, head), len(head))


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


def _next_code(tokens: list[tokenize.TokenInfo], at: int) -> int:
    """Index of the first token from *at* on that is not trivia."""
    while at < len(tokens) and tokens[at].type in _TRIVIA:
        at += 1
    return at


def _string_statement_end(tokens: list[tokenize.TokenInfo], at: int) -> int:
    """Last row of the string statement starting at *at*, or ``0``.

    A string is a statement when the run of string tokens from *at* is
    followed by the end of the statement; otherwise it is part of a larger
    expression (``\"a\" + b``) and ``0`` is returned.
    """
    end = at
    while tokens[_next_code(tokens, end + 1)].type == token.STRING:
        end = _next_code(tokens, end + 1)
    after = tokens[_next_code(tokens, end + 1)]
    if after.type in (token.NEWLINE, token.ENDMARKER):
        return tokens[end].end[0]
    return 0


def _doc_rows(source: str) -> Iterator[int]:
    """The 1-based rows of standalone comments and string statements.

    A comment counts when it is alone on its line. A string counts when it is
    a whole statement, as a docstring is. A string passed as an argument or
    assigned to a name is data.

    Raises:
        SyntaxError: *source* does not tokenize.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        raise SyntaxError(str(exc)) from exc
    previous = token.NEWLINE
    for at, tok in enumerate(tokens):
        if tok.type == token.COMMENT:
            if not tok.line[: tok.start[1]].strip():
                yield tok.start[0]
            continue
        if tok.type == token.STRING and previous in _STATEMENT_START:
            last = _string_statement_end(tokens, at)
            yield from range(tok.start[0], last + 1)
        if tok.type != token.NL:
            previous = tok.type


def python_doc_lines(source: str) -> Iterator[str]:
    """The comment and docstring lines of *source*, as ruff's ``W505`` reads.

    A doc line is a comment alone on its line, or a line of a string that is
    a statement by itself, as docstrings are (:func:`_doc_rows`). The license
    notice every module opens with is skipped (:func:`_license_header_end`).

    Raises:
        SyntaxError: *source* does not tokenize.
    """
    lines = source.splitlines()
    skip = _license_header_end(lines)
    for row in sorted(set(_doc_rows(source))):
        if skip < row <= len(lines):
            yield lines[row - 1]


def overlong_python_doc_lines(repo_root: Path) -> frozenset[str]:
    """Every overlong doc line of every ``*.py`` under :data:`PYTHON_ROOTS`.

    A file with no overlong line past its license notice is not tokenized:
    most files have none, and tokenizing is the slow step.
    """
    items: set[str] = set()
    for rel, source in iter_tree_texts(repo_root, PYTHON_ROOTS, "*.py"):
        lines = source.splitlines()
        if not any(map(is_overlong, lines[_license_header_end(lines) :])):
            continue
        overlong = (ln for ln in python_doc_lines(source) if is_overlong(ln))
        items.update(_items(rel, overlong))
    return frozenset(items)


__all__ = [
    "LINE_LIMIT",
    "PYTHON_ROOTS",
    "SPEC_ROOT",
    "added_overlong_lines",
    "is_overlong",
    "item_text",
    "new_lines",
    "overlong_python_doc_lines",
    "overlong_spec_yaml_lines",
    "python_doc_lines",
]
