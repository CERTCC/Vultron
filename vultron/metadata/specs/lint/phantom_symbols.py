"""Phantom-symbol and phantom spec-id citation checks for the spec linter
(SR-04).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from vultron.metadata.base import relative_posix
from vultron.metadata.specs.lint.phantom_paths import (
    _PHANTOM_ID_ALLOWLIST_DIRS,
    _scanned_texts,
)
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    SPEC_ID_CITATION_RE,
    LintWarningCode,
)

#: MS-04-001 requirement-ID shape, shared with the citation ratchets and
#: bundle-fit via :data:`vultron.metadata.specs.schema.SPEC_ID_CITATION_RE`.
_SPEC_ID_RE = SPEC_ID_CITATION_RE

#: MS-15: a backticked ``SCREAMING_SNAKE_CASE`` token in spec prose, read as a
#: reference to a module-level code symbol (e.g. ``SEMANTIC_REGISTRY``,
#: ``CORE_VOCABULARY``). At least one underscore is required, which excludes the
#: three shapes that would otherwise dominate the matches and are not symbols:
#: RFC 2119 keywords (``MUST``), protocol shorthands (``RS``, ``EP``), and
#: single-word state or role names (``SIGNATORY``, ``VFD``). A dotted member
#: reference (`` `MessageSemantics.UNKNOWN` ``) does not match either, since
#: the opening backtick must be followed immediately by the token.
_SPEC_SYMBOL_RE = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")

#: Uppercase word tokens in Python source. Used to build the symbol corpus
#: that :func:`_check_phantom_symbols` resolves spec references against. A
#: textual scan rather than an AST walk on purpose: a spec may legitimately
#: name a symbol that appears only in a docstring, a comment, or a string
#: literal, and none of those are bindings an AST pass would report.
#:
#: Means ``\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b``. The leading ``\b`` is written
#: as a lookbehind after the first letter so the pattern opens on a character
#: class, which the regex engine can skip ahead to; the scan of every Python
#: file, run on each ``spec-lint``, takes about half as long.
SOURCE_SYMBOL_RE = re.compile(r"[A-Z](?<!\w[A-Z])[A-Z0-9]*(?:_[A-Z0-9]+)+\b")

#: Files and directories excluded from the symbol corpus that
#: :func:`_check_phantom_symbols` resolves against. Each entry matches either an
#: exact file or a directory prefix. Both hold symbol names that are *examples*
#: rather than code the specs describe: the linter quotes retired names while
#: documenting the check that exists to reject them — including
#: ``SEMANTICS_ACTIVITY_PATTERNS`` itself, which would otherwise resolve as live
#: and blind the guard to the case it was built for — and the linter's own tests
#: invent names for fixtures.
#:
#: Scoped to the ``lint/`` package rather than the whole ``vultron/metadata/specs/``
#: package on purpose: ``schema.py`` defines symbols the specs legitimately
#: cite (``RFC2119Priority`` members such as ``SHOULD_NOT``), so excluding the
#: package would reject real references. Separate from
#: :data:`_PHANTOM_ID_ALLOWLIST_DIRS` for the same reason in reverse — a stale
#: spec ID cited by the linter is a real defect and must stay scanned.
_SYMBOL_CORPUS_EXCLUDED_PATHS = frozenset(
    ["vultron/metadata/specs/lint", "test/metadata/specs"]
)


class _SourceScan:
    """One pass over the ``vultron/`` and ``test/`` Python trees.

    Two checks need the full text of every tracked Python file:
    :func:`_check_phantom_spec_id_citations` reads spec IDs *out* of the source,
    and :func:`_check_phantom_symbols` resolves spec references *into* it.
    Walking the tree once and sharing the result keeps the linter's I/O flat as
    the second check is added — ``spec-lint`` runs on every commit and its
    pytest wrapper sits close to a 5 s budget.

    The two exclusion sets differ on purpose — see
    :data:`_PHANTOM_ID_ALLOWLIST_DIRS` and
    :data:`_SYMBOL_CORPUS_EXCLUDED_PATHS`.

    Attributes:
        spec_id_citations: ``(relative_path, spec_id)`` for every distinct spec
            ID token cited by a file, excluding
            :data:`_PHANTOM_ID_ALLOWLIST_DIRS`.
        symbols: Every uppercase word token seen anywhere in the scanned
            source, excluding :data:`_SYMBOL_CORPUS_EXCLUDED_PATHS`.
    """

    def __init__(self, repo_root: Path) -> None:
        self.spec_id_citations: list[tuple[str, str]] = []
        self.symbols: set[str] = set()

        for rel_str, text in iter_python_sources(repo_root):
            if not path_is_under(rel_str, _SYMBOL_CORPUS_EXCLUDED_PATHS):
                self.symbols.update(SOURCE_SYMBOL_RE.findall(text))

            if any(
                rel_str.startswith(d + "/") for d in _PHANTOM_ID_ALLOWLIST_DIRS
            ):
                continue
            seen_in_file: set[str] = set()
            for match in _SPEC_ID_RE.finditer(text):
                sid = match.group(0)
                if sid not in seen_in_file:
                    seen_in_file.add(sid)
                    self.spec_id_citations.append((rel_str, sid))


def iter_python_sources(repo_root: Path) -> Iterator[tuple[str, str]]:
    """Yield ``(relative_path, text)`` for every Python file under ``vultron/`` and ``test/``.

    The tree the phantom-reference checks resolve code symbols against —
    :class:`_SourceScan` here, and the decision-record check in
    :mod:`vultron.metadata.adr.added_refs` (MS-15-006). Paths are POSIX,
    relative to ``repo_root``, and visited in sorted order; a missing tree is
    skipped.
    """
    for scan_root in (repo_root / "vultron", repo_root / "test"):
        if not scan_root.is_dir():
            continue
        for py_file in sorted(scan_root.rglob("*.py")):
            rel = relative_posix(py_file, repo_root)
            yield rel, py_file.read_text(encoding="utf-8", errors="replace")


def path_is_under(rel_path: str, prefixes: Iterable[str]) -> bool:
    """True when ``rel_path`` is one of ``prefixes`` or lies below one of them."""
    return any(rel_path == p or rel_path.startswith(p + "/") for p in prefixes)


def _check_phantom_spec_id_citations(
    registry: SpecRegistry, scan: _SourceScan
) -> list[str]:
    """Hard error when Python source cites a spec ID that does not exist (SR-04-008).

    Reads the spec ID tokens (pattern ``[A-Z]{2,8}-\\d{2}-\\d{3}``) that
    *scan* collected from ``vultron/`` and ``test/`` and rejects any that are
    not present in the registry.  Files under ``test/metadata/specs/`` are
    excluded by the scan because they legitimately cite synthetic fixture IDs.
    """
    known_ids = set(registry.all_specs.keys())
    return [
        f"{rel_str}: cites unknown spec ID {sid}"
        for rel_str, sid in scan.spec_id_citations
        if sid not in known_ids
    ]


def _check_phantom_symbols(
    registry: SpecRegistry, scan: _SourceScan
) -> list[str]:
    """Hard error when a spec field names a code symbol that does not exist (MS-15-004).

    The mirror image of :func:`_check_phantom_paths`, for the reference shape
    that check cannot see. ``_check_phantom_paths`` only inspects backticked
    tokens containing a directory separator, so a bare symbol name such as
    `` `SEMANTICS_ACTIVITY_PATTERNS` `` passed silently — and did, across 33
    occurrences and 8 MUST-level statements, for the whole interval between the
    symbol's removal and issue #3022.

    A statement that asserts a MUST about a symbol nobody can find is worse
    than an absent requirement: an agent reads it, cannot locate the referent,
    and either invents a replacement or quietly drops the obligation. Making
    the divergence *detectable* rather than merely absent is the principle
    ADR-0083 applies to message shapes; this applies it to symbol names.

    Scanned fields are :func:`_scanned_texts` — the same set
    ``_check_phantom_paths`` uses. ``rationale`` is again excluded: the problem it
    names (MS-10-012) may legitimately be a symbol that has been removed.

    Resolution is deliberately loose — a token counts as live if it appears
    *anywhere* in the ``vultron/`` or ``test/`` Python text, including comments
    and docstrings. The check is aimed at names with no trace left in the
    codebase, not at proving a binding exists at the cited location, so it
    prefers a false negative over blocking a commit on a legitimate reference.
    The one exception to that preference is the whole-token corpus: a cited
    ``FOO`` whose only occurrence in source is as a fragment of a longer
    identifier (``FOO_V2``) does *not* resolve, because :data:`SOURCE_SYMBOL_RE`
    captures whole ``\\b``-delimited runs. That is a deliberate true positive —
    ``FOO`` and ``FOO_V2`` are distinct symbols — not an oversight; suppress with
    ``lint_suppress`` if a spec genuinely means the longer name.

    Exemption: per-spec opt-out via ``lint_suppress: [phantom_symbol_ref]``,
    for a statement that deliberately names a retired symbol in order to
    record its removal, or names a convention token that was never code.
    """
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if LintWarningCode.PHANTOM_SYMBOL_REF in set(spec.lint_suppress or []):
            continue
        seen: set[str] = set()
        for field_label, text in _scanned_texts(spec):
            for match in _SPEC_SYMBOL_RE.findall(text):
                if match in scan.symbols or match in seen:
                    continue
                seen.add(match)
                errors.append(
                    f"{spec_id}: {field_label} references symbol "
                    f"'{match}' which does not appear anywhere in vultron/ or "
                    f"test/ (MS-15-004). Point at the live symbol, or — if the "
                    f"reference is deliberately historical — suppress with "
                    f"lint_suppress: [phantom_symbol_ref]."
                )
    return errors
