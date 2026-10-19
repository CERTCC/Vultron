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
carried it to another file. Ruff's ``W505`` finds the Python doc lines, so
the guard and ``ruff check --select W505`` agree on what a doc line is; only
the files the branch changed are read.

A line counts as overlong as markdownlint's non-strict ``MD013`` counts it:
longer than the limit *and* with whitespace past the limit. A line whose
overflow is one unbreakable token, such as a URL or a pytest node ID, cannot be
wrapped and is not reported.

Requirements: specs/project-documentation.yaml PD-10.
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 - runs a fixed ruff command only
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

from vultron.metadata.base import iter_tree_texts
from vultron.metadata.specs.growth_guard import (
    Extractor,
    GrowthCheck,
    compare_changed_with_base,
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

    Only the files the branch changed are read, on both sides
    (:func:`~vultron.metadata.specs.growth_guard.compare_changed_with_base`):
    every extractor here is per file, so an unchanged file adds the same items,
    and the same count of each line, to both sides. The result's
    ``head_total`` is therefore ``None``.
    """
    seen = compare_changed_with_base(
        extract,
        repo_root=repo_root,
        paths=paths,
        base_ref=base_ref,
        require_base=require_base,
    )
    head = seen.head_value
    if seen.base_value is None:
        return GrowthCheck(None, frozenset(), None, skipped=seen.skipped)
    return GrowthCheck(seen.base, new_lines(seen.base_value, head), None)


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


#: The ruff rule that finds comment and docstring lines over the limit.
_RUFF_DOC_RULE = "W505"


def _ruff_doc_rows(
    repo_root: Path, roots: Sequence[str]
) -> dict[str, list[int]]:
    """The rows ruff's ``W505`` flags under *roots*, keyed by relative path.

    The rule runs alone and with ``--isolated``, so the limit is
    :data:`LINE_LIMIT` whatever the tree's own ruff configuration says, and the
    base tree is read under the same settings as the working tree. ``noqa``
    comments are ignored: the guard has no exemptions.

    Raises:
        SyntaxError: ruff cannot parse a file, so its doc lines are unknown.
        RuntimeError: ruff, a dev dependency, is not installed or fails.
    """
    proc = subprocess.run(  # nosec B603 - fixed ruff argv
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--no-cache",
            "--ignore-noqa",
            "--exit-zero",
            "--select",
            _RUFF_DOC_RULE,
            "--config",
            f"lint.pycodestyle.max-doc-length={LINE_LIMIT}",
            "--output-format",
            "json",
            *roots,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ruff check failed: {proc.stderr.strip()}")
    root = repo_root.resolve()
    rows: dict[str, list[int]] = {}
    for found in json.loads(proc.stdout):
        rel = Path(found["filename"]).resolve().relative_to(root).as_posix()
        row = found["location"]["row"]
        if found["code"] != _RUFF_DOC_RULE:
            raise SyntaxError(f"{rel}:{row}: {found['message']}")
        rows.setdefault(rel, []).append(row)
    return rows


def overlong_python_doc_lines(repo_root: Path) -> frozenset[str]:
    """Every overlong doc line of every ``*.py`` under :data:`PYTHON_ROOTS`.

    A doc line is a comment alone on its line, or a line of a string that is a
    statement by itself, as docstrings are: the lines ruff's ``W505`` reads,
    found by ruff itself (:func:`_ruff_doc_rows`). Of those, a line counts when
    :func:`is_overlong` holds, so a line whose overflow is one unbreakable
    token passes here as it does in spec YAML. The license notice every module
    opens with is skipped (:func:`_license_header_end`). Gitignored files are
    not read, as ruff does not read them.

    Raises:
        SyntaxError: A file under the roots does not parse.
    """
    roots = [r for r in PYTHON_ROOTS if (repo_root / r).is_dir()]
    if not roots:
        return frozenset()
    items: set[str] = set()
    for rel, rows in _ruff_doc_rows(repo_root, roots).items():
        lines = (repo_root / rel).read_text(encoding="utf-8").splitlines()
        skip = _license_header_end(lines)
        overlong = (
            lines[row - 1]
            for row in sorted(rows)
            if skip < row <= len(lines) and is_overlong(lines[row - 1])
        )
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
]
