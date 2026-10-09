"""Refuse an unresolvable reference an edit writes into an ADR (MS-15-006).

An ADR is a historical record (ADR-0127): a code reference in its body that
has aged since it was written is an accurate account of the code as it then
stood, not a defect, and nothing fails on it. A reference *newly written* into
a record is different — it should resolve on the day it is written. That is a
question about one edit, not about the corpus, so this check compares each
edited record with its text at a base commit and fails only on a backticked
reference the edit adds:

- a file or directory path that does not exist in the repository, resolved
  the way the spec phantom-path check (MS-15-001) resolves it; or
- a code symbol that appears nowhere in the ``vultron/`` or ``test/`` Python
  sources, resolved textually as the spec phantom-symbol check (MS-15-004)
  does, but over a wider set of shapes (see :func:`symbols_in`).

A reference already present at the base never fails, however stale; an edit
that touches no record is never examined; and no code change can fail it,
because only the record's own text is compared (ADR-0127 rejects a check keyed
on code changes). A record that deliberately adds a name that does not
resolve — one it annotates as removed, or a convention token that was never
code — opts out with ``lint_suppress: [phantom_symbol_ref]`` or
``[phantom_path_ref]`` in its frontmatter (MS-15-007).

Runs as the ``adr-added-reference-check`` pre-commit hook against ``HEAD`` and
as a step of the ``ADR Lifecycle`` pull-request workflow against the merge
base, so a skipped local hook cannot bypass it.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pydantic import ValidationError

from vultron.metadata.adr.lifecycle import edited_adrs
from vultron.metadata.adr.schema import AdrFrontmatter, AdrLintSuppressCode
from vultron.metadata.file_loading import (
    MetadataLoadError,
    display_path,
    loads_frontmatter,
)
from vultron.metadata.specs.lint import (
    _SOURCE_SYMBOL_RE,
    _SPEC_DIR_RE,
    _SPEC_PATH_RE,
    _PathResolver,
    iter_python_sources,
    path_is_under,
)

#: One inline code span on a single line. A double-backtick span is not a
#: reference shape this check reads.
_SPAN_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")

#: A span that is wholly a (possibly dotted) identifier, optionally called:
#: ``CaseStatus``, ``dl.save()``, ``Foo.BAR``, ``make(x, y)``. Anything else —
#: an expression, a type annotation, a shell command — is not read as a
#: reference, preferring a false negative over refusing legitimate prose.
_REF_RE = re.compile(
    r"(?P<ref>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
    r"(?P<call>\(.*\))?"
)

_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")

#: Files whose text quotes invented names as examples of what this check
#: refuses; letting them into the corpus would make those names resolve.
_CORPUS_EXCLUDED_PATHS = frozenset(
    {
        "vultron/metadata/adr/added_refs.py",
        "test/metadata/test_adr_added_refs.py",
    }
)


class RefKind(StrEnum):
    """What a backticked reference names."""

    PATH = "path"
    DIRECTORY = "directory"
    SYMBOL = "symbol"


_SUPPRESSED_BY: dict[RefKind, AdrLintSuppressCode] = {
    RefKind.PATH: AdrLintSuppressCode.PHANTOM_PATH_REF,
    RefKind.DIRECTORY: AdrLintSuppressCode.PHANTOM_PATH_REF,
    RefKind.SYMBOL: AdrLintSuppressCode.PHANTOM_SYMBOL_REF,
}


@dataclass(frozen=True)
class Reference:
    """One backticked reference and where it starts (1-based)."""

    kind: RefKind
    name: str
    line: int
    column: int


def _is_camel_case(segment: str) -> bool:
    """``CaseLogEntry``, ``EMState``; not ``Case``, ``README`` or ``as_Link``."""
    return (
        segment[0].isupper()
        and segment.isalnum()
        and any(c.islower() for c in segment)
        and sum(c.isupper() for c in segment) >= 2
    )


def symbols_in(span: str) -> list[str]:
    """Return the code symbols a backticked ``span`` names.

    Four shapes are read, each a whole identifier or a dotted segment of one:

    - an all-caps constant containing an underscore (``SEMANTIC_REGISTRY``),
      the one shape the spec-corpus check (MS-15-004) reads;
    - a CamelCase class name (``CaseLogEntry``, ``EMState``) — at least two
      capitals and a lowercase letter, so a plain word (``Case``) is not one;
    - a called name (``snake_case()``, ``dl.save()``, ``make(x)``), whose final
      segment is the function;
    - a member of a CamelCase class (``AppConfig.max_retries``), or an all-caps
      member after any dot (``PECState.SIGNATORY``).

    A bare lowercase name (``queue``), a bare one-word all-caps token
    (``MUST``) and a dotted module path (``httpx.AsyncClient``'s ``httpx``) are
    not read: they are too often prose, vocabulary or third-party names.
    """
    match = _REF_RE.fullmatch(span.strip())
    if match is None:
        return []
    segments = match.group("ref").split(".")
    found: list[str] = []
    for idx, segment in enumerate(segments):
        if (
            _SOURCE_SYMBOL_RE.fullmatch(segment)
            or _is_camel_case(segment)
            or (idx > 0 and len(segment) > 1 and segment.isupper())
            or (idx > 0 and _is_camel_case(segments[idx - 1]))
            or (match.group("call") and idx == len(segments) - 1)
        ):
            found.append(segment)
    return found


def _body_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line_number, line)`` outside frontmatter and fenced code."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        closing = next(
            (i for i in range(1, len(lines)) if lines[i].strip() == "---"),
            None,
        )
        start = 0 if closing is None else closing + 1
    in_fence = False
    for idx in range(start, len(lines)):
        line = lines[idx]
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield idx + 1, line


def references_in(text: str) -> list[Reference]:
    """Return every backticked path and code symbol in an ADR's body text."""
    refs: list[Reference] = []
    for line_no, line in _body_lines(text):
        for span_match in _SPAN_RE.finditer(line):
            span = span_match.group(1)
            column = span_match.start(1) + 1
            quoted = f"`{span}`"
            if _SPEC_PATH_RE.fullmatch(quoted):
                refs.append(Reference(RefKind.PATH, span, line_no, column))
            elif _SPEC_DIR_RE.fullmatch(quoted):
                refs.append(
                    Reference(RefKind.DIRECTORY, span, line_no, column)
                )
            else:
                refs.extend(
                    Reference(RefKind.SYMBOL, name, line_no, column)
                    for name in symbols_in(span)
                )
    return refs


class ReferenceResolver:
    """Decides whether a reference names something in the repository.

    Paths resolve through the spec phantom-path resolver (MS-15-001). Symbols
    resolve when they occur as a whole identifier anywhere in the ``vultron/``
    or ``test/`` Python text, comments and docstrings included (MS-15-004):
    the check is aimed at names with no trace left, not at proving a binding.
    The symbol corpus is built at most once, and only if a symbol is asked
    about.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._paths = _PathResolver(repo_root)
        self._symbols: set[str] | None = None

    def resolves(self, ref: Reference) -> bool:
        if ref.kind is RefKind.PATH:
            return self._paths.problem_with(ref.name) is None
        if ref.kind is RefKind.DIRECTORY:
            return self._paths.problem_with_dir(ref.name) is None
        if self._symbols is None:
            self._symbols = {
                token
                for rel, text in iter_python_sources(self._repo_root)
                if not path_is_under(rel, _CORPUS_EXCLUDED_PATHS)
                for token in _IDENTIFIER_RE.findall(text)
            }
        return ref.name in self._symbols


def _suppressed(text: str) -> set[AdrLintSuppressCode]:
    """Return the record's ``lint_suppress`` codes.

    Frontmatter that fails its schema suppresses nothing: the loader reports
    the schema fault, and this check still runs rather than passing silently.
    """
    try:
        fm = AdrFrontmatter.model_validate(loads_frontmatter(text).metadata)
    except (ValidationError, ValueError):
        return set()
    return set(fm.lint_suppress or [])


def _describe(ref: Reference) -> str:
    code = _SUPPRESSED_BY[ref.kind].value
    if ref.kind is RefKind.SYMBOL:
        where = "appears nowhere in the vultron/ or test/ Python sources"
        live = "the live name"
    else:
        where = "does not exist in the repository"
        live = "the real path"
    return (
        f"this edit adds a reference to {ref.kind.value} '{ref.name}', which "
        f"{where} (MS-15-006). Point at {live}, or — if the reference is "
        f"deliberately historical, such as a name the record annotates as "
        f"removed — opt the record out with 'lint_suppress: [{code}]' "
        f"(MS-15-007)"
    )


def added_reference_faults(
    shown: str,
    old_text: str | None,
    new_text: str,
    resolver: ReferenceResolver,
) -> list[MetadataLoadError]:
    """Return a fault for each unresolvable reference the edit adds.

    ``old_text`` is ``None`` for a new record, every reference of which is
    added. A reference is added when no reference of the same name is in
    ``old_text``; each added name is reported once, at its first position.
    ``shown`` is the path the fault names (MS-17-001).
    """
    existing = {ref.name for ref in references_in(old_text or "")}
    suppressed = _suppressed(new_text)
    faults: list[MetadataLoadError] = []
    reported: set[str] = set()
    for ref in references_in(new_text):
        if ref.name in existing or ref.name in reported:
            continue
        if _SUPPRESSED_BY[ref.kind] in suppressed:
            continue
        if resolver.resolves(ref):
            continue
        reported.add(ref.name)
        faults.append(
            MetadataLoadError(
                _describe(ref), path=shown, line=ref.line, column=ref.column
            )
        )
    return faults


def check_paths(
    paths: Iterable[Path], base: str, repo_root: Path
) -> list[MetadataLoadError]:
    """Check each edited ADR's working-tree text against its text at ``base``.

    ``paths`` are relative to the current directory, which is the repository
    root under both the hook and the workflow. Raises ``ValueError`` if
    ``base`` is not a commit.
    """
    resolver = ReferenceResolver(repo_root)
    faults: list[MetadataLoadError] = []
    for path, old_text, new_text in edited_adrs(paths, base):
        faults.extend(
            added_reference_faults(
                display_path(path, repo_root), old_text, new_text, resolver
            )
        )
    return faults


def main(argv: list[str] | None = None) -> None:
    """CLI: ``python -m vultron.metadata.adr.added_refs [--base REF] [paths...]``."""
    parser = argparse.ArgumentParser(
        prog="adr-added-reference-check",
        description=(
            "Refuse an unresolvable path or code symbol that an edit adds to "
            "an ADR (MS-15-006)."
        ),
    )
    parser.add_argument("--base", default="HEAD", help="ref to diff against")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    try:
        faults = check_paths(args.paths, args.base, Path.cwd())
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
    for fault in faults:
        print(f"[ERROR] {fault}", file=sys.stderr)
    sys.exit(1 if faults else 0)


if __name__ == "__main__":
    main()
