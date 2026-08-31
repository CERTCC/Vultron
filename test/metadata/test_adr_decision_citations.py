"""Lint rule: ADR decision citations must reference defined anchors.

Background: ADR-0073 accumulated 22 comments citing "ADR-0073 decision N"
with positional numbers that did not match the ADR's structure (Bug #2627).
The ADR had no numbered decisions — only an unnumbered Concretely: bullet
list — so the citations were unresolvable and mutually inconsistent.

This rule prevents a recurrence by enforcing two properties:

1. **Named-anchor citations** (``ADR-NNNN#anchor-name``) must reference an
   anchor that actually exists in the referenced ADR file.  An anchor is any
   ``<a id="...">`` tag in the ADR markdown.

2. **Positional-number citations** (``ADR-NNNN decision N``) are always
   invalid.  ADRs in this project do not use numbered decisions; any
   positional citation is therefore unresolvable and must be corrected to
   use a named anchor instead.

Coverage: ``vultron/``, ``test/``, ``docs/``, and ``specs/``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[2]

_SOURCE_DIRS = (
    _REPO_ROOT / "vultron",
    _REPO_ROOT / "test",
    _REPO_ROOT / "docs",
    _REPO_ROOT / "specs",
)

_SOURCE_EXTENSIONS = {".py", ".md", ".yaml", ".yml"}

_SKIP_PATHS = {
    # The ADR files themselves are the source of truth, not citations.
    str(_REPO_ROOT / "docs" / "adr"),
    # This file contains intentionally bad citations in its demonstration
    # tests; exclude it to avoid false positives in the scanner.
    str(Path(__file__)),
}

# Matches ADR-NNNN#anchor-name citations.
_ANCHOR_CITATION_RE = re.compile(r"ADR-(\d{4})#([\w-]+)", re.ASCII)

# Matches positional "ADR-NNNN decision N" citations (case-insensitive).
_POSITIONAL_CITATION_RE = re.compile(
    r"ADR-\d{4}[^\n#)]{0,40}decision\s+\d+", re.IGNORECASE
)

# Matches <a id="..."> or <a id='...'> anchor declarations in ADR markdown.
_ANCHOR_DECL_RE = re.compile(r'<a\s+id=["\']([^"\']+)["\']', re.IGNORECASE)


class Citation(NamedTuple):
    file: str
    line: int
    adr_number: str
    anchor: str
    text: str


def _adr_file(adr_number: str) -> Path | None:
    """Resolve a 4-digit ADR number to its markdown file path, or None."""
    adr_dir = _REPO_ROOT / "docs" / "adr"
    matches = list(adr_dir.glob(f"{adr_number}-*.md"))
    if not matches:
        matches = list((adr_dir / "archived").glob(f"{adr_number}-*.md"))
    return matches[0] if matches else None


def _anchors_in_adr(adr_number: str) -> set[str]:
    """Return the set of anchor ids declared in the given ADR file."""
    path = _adr_file(adr_number)
    if path is None:
        return set()
    content = path.read_text(encoding="utf-8")
    return set(_ANCHOR_DECL_RE.findall(content))


def _iter_source_files():
    for source_dir in _SOURCE_DIRS:
        if not source_dir.exists():
            continue
        for path in source_dir.rglob("*"):
            if path.suffix not in _SOURCE_EXTENSIONS:
                continue
            if any(str(path).startswith(skip) for skip in _SKIP_PATHS):
                continue
            if path.is_file():
                yield path


def _collect_anchor_citations() -> list[Citation]:
    """Find all ADR-NNNN#anchor citations in source files."""
    citations: list[Citation] = []
    for path in _iter_source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in _ANCHOR_CITATION_RE.finditer(line):
                citations.append(
                    Citation(
                        file=str(path.relative_to(_REPO_ROOT)),
                        line=lineno,
                        adr_number=m.group(1),
                        anchor=m.group(2),
                        text=line.strip(),
                    )
                )
    return citations


def _collect_positional_citations() -> list[tuple[str, int, str]]:
    """Find all ADR-NNNN decision N (positional) citations in source files."""
    hits: list[tuple[str, int, str]] = []
    for path in _iter_source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _POSITIONAL_CITATION_RE.search(line):
                hits.append(
                    (str(path.relative_to(_REPO_ROOT)), lineno, line.strip())
                )
    return hits


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_positional_decision_citations():
    """No source file may cite an ADR with a positional decision number.

    Positional citations (``ADR-NNNN decision N``) are unresolvable because
    ADRs in this project do not use numbered decisions.  Every citation must
    use a named anchor (``ADR-NNNN#anchor-name``) instead.

    Demonstrated to detect violations by
    ``TestBadCitationDetected.test_positional_citation_detected``.
    """
    hits = _collect_positional_citations()
    if hits:
        detail = "\n".join(
            f"  {rel}:{lineno}: {text}" for rel, lineno, text in hits
        )
        pytest.fail(
            f"Found {len(hits)} positional ADR decision citation(s) — "
            f"replace each with a named anchor (ADR-NNNN#anchor-name):\n"
            f"{detail}"
        )


def test_anchor_citations_resolve():
    """Every ADR-NNNN#anchor citation must reference an anchor that exists.

    The anchor must be a ``<a id="...">`` tag declared in the body of
    ``docs/adr/NNNN-*.md`` (or its archived counterpart).

    Demonstrated to detect violations by
    ``TestBadCitationDetected.test_missing_anchor_detected``.
    """
    citations = _collect_anchor_citations()
    failures: list[str] = []
    _anchor_cache: dict[str, set[str]] = {}

    for cit in citations:
        num = cit.adr_number
        if num not in _anchor_cache:
            _anchor_cache[num] = _anchors_in_adr(num)
        available = _anchor_cache[num]

        if not available and _adr_file(num) is None:
            failures.append(
                f"  {cit.file}:{cit.line}: ADR-{num} not found in "
                f"docs/adr/ — cannot resolve #{cit.anchor}"
            )
        elif cit.anchor not in available:
            failures.append(
                f"  {cit.file}:{cit.line}: ADR-{num}#{cit.anchor} "
                f"— anchor not declared in the ADR.  "
                f"Declared: {sorted(available) or '(none)'}"
            )

    if failures:
        pytest.fail(
            f"Found {len(failures)} unresolvable ADR anchor citation(s):\n"
            + "\n".join(failures)
        )


# ---------------------------------------------------------------------------
# Demonstration: the rule catches bad citations
# ---------------------------------------------------------------------------


class TestBadCitationDetected:
    """Verify the detection helpers catch violations using synthetic fixtures."""

    def test_positional_citation_detected(self, tmp_path):
        """A positional 'decision N' citation is caught.

        This test stands as evidence that the lint rule is live (AC-4): a
        freshly introduced positional citation would cause
        ``test_no_positional_decision_citations`` to fail.
        """
        bad_file = tmp_path / "bad_source.py"
        bad_file.write_text(
            '"""Uses ADR-0073 decision 5 which no longer exists as a number."""\n'
        )

        hits = []
        text = bad_file.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _POSITIONAL_CITATION_RE.search(line):
                hits.append((str(bad_file), lineno, line.strip()))

        assert hits, "detector must find the positional citation"
        assert any("decision 5" in h[2] for h in hits)

    def test_missing_anchor_detected(self, tmp_path):
        """A citation pointing at a nonexistent anchor is caught.

        Writes a minimal ADR stub with one known anchor, then checks that a
        citation to a *different* anchor is reported as unresolvable.
        """
        # Build a tiny fake ADR registry under tmp_path.
        adr_dir = tmp_path / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "0073-test-stub.md").write_text(
            "---\nstatus: accepted\n---\n"
            "# Stub\n"
            '<a id="real-anchor"></a>\n'
            "- The real decision.\n"
        )

        # A source file that cites a nonexistent anchor.
        source = tmp_path / "vultron" / "demo" / "utils.py"
        source.parent.mkdir(parents=True)
        source.write_text("# (ADR-0073#ghost-anchor) see the ADR\n")

        # Reproduce the anchor lookup against the tmp_path ADR file.
        content = (adr_dir / "0073-test-stub.md").read_text()
        declared = set(_ANCHOR_DECL_RE.findall(content))
        assert "real-anchor" in declared
        assert "ghost-anchor" not in declared

        # And show the citation regex would find the ghost reference.
        source_text = source.read_text()
        found = _ANCHOR_CITATION_RE.findall(source_text)
        assert ("0073", "ghost-anchor") in found

    def test_real_anchor_passes(self, tmp_path):
        """A citation pointing at a declared anchor passes validation."""
        adr_dir = tmp_path / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "0073-test-stub.md").write_text(
            "---\nstatus: accepted\n---\n"
            '<a id="peer-records-in-knowers-store"></a>\n'
            "- Peer actor records live in the address book of each hosted actor.\n"
        )

        content = (adr_dir / "0073-test-stub.md").read_text()
        declared = set(_ANCHOR_DECL_RE.findall(content))
        assert "peer-records-in-knowers-store" in declared

        source_text = "# (ADR-0073#peer-records-in-knowers-store)\n"
        found = _ANCHOR_CITATION_RE.findall(source_text)
        assert ("0073", "peer-records-in-knowers-store") in found
        # The cited anchor IS in declared → no failure.
        assert found[0][1] in declared
