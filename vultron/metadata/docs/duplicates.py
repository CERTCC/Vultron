"""List paragraphs repeated across ``docs/`` pages, exact or drifted.

Requirements: specs/diataxis-requirements.yaml DF-10-001 and DF-10-002 (shared
content is sourced once, and a moved claim is verified), DF-09-007 (a block is
judged in the source file that holds it), DF-11-007 (a page's own opening stays
on the page), DF-09-009 (an empty target set fails). The rule it feeds is SG-43
in ``.agents/skills/shared/docs-style-guide.md``; ``lint-docs`` turns each
cluster into a judgment finding.

The report is advisory, so the command exits 0 whatever it finds. Only the
author can tell a page introducing itself in its own words (SG-44, never a
finding) from content one authority owns that was copied onto a second page.

Targets come from :func:`~vultron.metadata.docs.page_frontmatter.classify_docs_tree`,
so an include fragment is never read on its own: a block sourced from one
fragment that several pages include is the fix, not a copy. The cost is that
prose hand-copied from a fragment onto a page that does not include it is not
seen either; ``lint-docs`` still judges that case by reading. Also skipped are
decision records, generated pages (:data:`SKIPPED_PATTERNS`, and any page
carrying :data:`GENERATED_FILE_MARKER`), ``_``-prefixed files, and the
generated sections inside hand-written pages. Project history lives under
``plan/history/``, outside ``docs/``, so the target set never holds it.

A paragraph is a run of non-blank lines, ended by a blank line or a heading,
with frontmatter, fenced code, HTML comments and ``{% %}`` directives removed.
Fences are removed first, so a ``<!--`` or ``{%`` inside one is code. One shorter than :data:`MIN_CHARS` is too short to
say anything worth sourcing once, and a heading alone is not a paragraph.

* **Exact copies.** Each paragraph is keyed by its text with whitespace
  collapsed; a key held by paragraphs on two or more pages is a cluster. One
  pass over a hash map, with no pairwise comparison.
* **Drifted copies.** Each paragraph is split into sentences, normalized
  further (case and punctuation dropped), and indexed sentence → paragraphs.
  Only paragraphs that share a sentence become candidates, scored by the
  Jaccard overlap of their sentence sets; a pair at or above
  :data:`THRESHOLD` is an edge, and each connected group of edges whose
  paragraphs sit on two or more pages is a cluster. No path compares every
  paragraph with every other. A wording that is one variant of a drifted
  cluster is reported there, with all its hosts, and not again as exact.

Usage::

    uv run docs-duplicates                  # report clusters (advisory)
    uv run docs-duplicates --threshold 0.7  # only closer drifted copies
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pathspec.gitignore import GitIgnoreSpec

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.docs.page_frontmatter import classify_docs_tree
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.markdown_tables import fenced_lines

#: ``docs/``-relative pages that are never copies an author wrote: decision
#: records, and generated content classes (the ``lint-docs`` exemptions).
SKIPPED_PATTERNS: tuple[str, ...] = (
    "adr/**",
    "_acronyms/**",
    "ns/**",
    "reference/behaviors/**",
    "reference/case_states/**",
    "reference/code/**",
    "reference/codebase/**",
    "reference/user_stories/story_*.md",
    "*diagram*.md",
    "*table*.md",
)
_SKIPPED_SPEC = GitIgnoreSpec.from_lines(SKIPPED_PATTERNS)

#: A page whose source holds this comment was written by a generator.
GENERATED_FILE_MARKER = "<!-- This file is auto-generated. Do not edit. -->"

#: Shortest paragraph, in characters after whitespace is collapsed, worth
#: reporting.
MIN_CHARS = 120

#: Lowest sentence-set Jaccard overlap at which two paragraphs are a drifted
#: copy.
THRESHOLD = 0.5

#: Shortest normalized sentence that can link two paragraphs. A shorter one
#: (``See below.``) is shared by unrelated prose.
_MIN_SENTENCE_CHARS = 24

_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
# A generated section inside a hand-written page: the landing-page contents
# listing and the start-page reading path, which repeat each listed page's
# ``description:`` by design.
_GENERATED_SECTION_RE = re.compile(
    r"<!-- BEGIN GENERATED\b.*?<!-- END GENERATED\b[^>]*-->", re.DOTALL
)
_NON_PROSE_RE = re.compile(r"<!--.*?-->|\{%.*?%\}", re.DOTALL)
_HEADING_RE = re.compile(r"\A#{1,6}\s")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Paragraph:
    """One paragraph of a target page.

    Attributes:
        path: ``docs/``-relative path of the page.
        line: 1-based line the paragraph starts on.
        text: The paragraph with whitespace collapsed; the exact-copy key.
    """

    path: str
    line: int
    text: str


@dataclass(frozen=True)
class Variant:
    """One wording of a repeated paragraph and every place it appears."""

    text: str
    hosts: tuple[Paragraph, ...]


@dataclass(frozen=True)
class Cluster:
    """Paragraphs repeated across pages.

    Attributes:
        kind: ``"exact"``, one wording on every page, or ``"drifted"``,
            wordings that overlap at or above the threshold.
        variants: The wordings, each with its hosts. An exact cluster has one.
    """

    kind: Literal["exact", "drifted"]
    variants: tuple[Variant, ...]

    @property
    def files(self) -> tuple[str, ...]:
        """Every page the cluster appears on, sorted."""
        return tuple(sorted({p.path for v in self.variants for p in v.hosts}))


@dataclass(frozen=True)
class DuplicateReport:
    """What a run found."""

    pages: int
    clusters: tuple[Cluster, ...]


def is_target(docs_path: str, text: str) -> bool:
    """Whether a page from the classified tree is read for copies."""
    name = docs_path.rsplit("/", 1)[-1]
    return (
        not name.startswith("_")
        and not _SKIPPED_SPEC.match_file(docs_path)
        and GENERATED_FILE_MARKER not in text
    )


def _blank_non_prose(text: str) -> str:
    """Blank frontmatter, generated sections, comments and directives.

    Each removed span keeps its newlines, so every surviving line stays on
    the line number it has in the file.
    """

    def blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    text = _FRONTMATTER_RE.sub(blank, text, count=1)
    text = _GENERATED_SECTION_RE.sub(blank, text)
    return _NON_PROSE_RE.sub(blank, text)


def paragraphs(
    text: str, docs_path: str, *, min_chars: int = MIN_CHARS
) -> Iterator[Paragraph]:
    """Yield each paragraph of a page's source long enough to report."""
    fenced = fenced_lines(text)
    unfenced = "\n".join(
        "" if number in fenced else line
        for number, line in enumerate(text.splitlines(), start=1)
    )
    lines = _blank_non_prose(unfenced).splitlines()
    block: list[str] = []
    start = 0
    for number, line in enumerate([*lines, ""], start=1):
        if not line.strip() or _HEADING_RE.match(line.lstrip()):
            if block:
                collapsed = " ".join(" ".join(block).split())
                if len(collapsed) >= min_chars:
                    yield Paragraph(docs_path, start, collapsed)
                block = []
            continue
        if not block:
            start = number
        block.append(line)


def sentences(text: str) -> frozenset[str]:
    """The paragraph's sentences, case and punctuation dropped."""
    found: set[str] = set()
    for sentence in _SENTENCE_END_RE.split(text):
        normalized = " ".join(_WORD_RE.findall(sentence.lower()))
        if len(normalized) >= _MIN_SENTENCE_CHARS:
            found.add(normalized)
    return frozenset(found)


def _hosts_by_text(
    found: Iterable[Paragraph],
) -> dict[str, tuple[Paragraph, ...]]:
    """Group paragraphs by their exact-copy key."""
    grouped: dict[str, list[Paragraph]] = defaultdict(list)
    for paragraph in found:
        grouped[paragraph.text].append(paragraph)
    return {text: tuple(hosts) for text, hosts in grouped.items()}


def _on_several_pages(hosts: Iterable[Paragraph]) -> bool:
    return len({p.path for p in hosts}) > 1


def _overlap(left: frozenset[str], right: frozenset[str]) -> float:
    """Jaccard overlap of two non-empty sentence sets."""
    return len(left & right) / len(left | right)


def _drift_edges(
    texts: list[str], threshold: float
) -> Iterator[tuple[int, int]]:
    """Yield each pair of wordings whose sentence sets overlap enough.

    Candidates come from the sentence index only: two wordings are scored
    when they share at least one sentence, and never otherwise.
    """
    sentence_sets = [sentences(text) for text in texts]
    index: dict[str, list[int]] = defaultdict(list)
    for number, found in enumerate(sentence_sets):
        for sentence in found:
            index[sentence].append(number)
    for number, found in enumerate(sentence_sets):
        candidates = {
            other
            for sentence in found
            for other in index[sentence]
            if other > number
        }
        for other in sorted(candidates):
            if _overlap(found, sentence_sets[other]) >= threshold:
                yield number, other


def _components(size: int, edges: Iterable[tuple[int, int]]) -> list[set[int]]:
    """Connected components of *edges*, each with more than one member."""
    parent = list(range(size))

    def root(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for left, right in edges:
        parent[root(left)] = root(right)
    groups: dict[int, set[int]] = defaultdict(set)
    for node in range(size):
        groups[root(node)].add(node)
    return [group for group in groups.values() if len(group) > 1]


def find_clusters(
    found: Iterable[Paragraph], *, threshold: float = THRESHOLD
) -> tuple[Cluster, ...]:
    """Cluster *found* paragraphs into exact and drifted cross-page copies."""
    hosts = _hosts_by_text(found)
    texts = sorted(hosts)
    clusters: list[Cluster] = []
    drifted: set[str] = set()
    for group in _components(len(texts), _drift_edges(texts, threshold)):
        variants = tuple(
            Variant(texts[n], hosts[texts[n]]) for n in sorted(group)
        )
        if _on_several_pages(p for v in variants for p in v.hosts):
            clusters.append(Cluster("drifted", variants))
            drifted.update(v.text for v in variants)
    # A wording already shown as one variant of a drifted cluster, with all
    # its hosts, is not reported a second time as an exact cluster.
    clusters.extend(
        Cluster("exact", (Variant(text, places),))
        for text, places in hosts.items()
        if text not in drifted and _on_several_pages(places)
    )
    return tuple(sorted(clusters, key=lambda c: (c.files, c.kind)))


def duplicate_report(
    root: Path,
    *,
    min_chars: int = MIN_CHARS,
    threshold: float = THRESHOLD,
) -> DuplicateReport:
    """Read every target page under *root*'s ``docs/`` and cluster its copies.

    Raises:
        MetadataLoadError: when no target page resolves (DF-09-009).
    """
    docs_dir = root / "docs"
    pages = classify_docs_tree(root).pages if docs_dir.is_dir() else ()
    texts: Mapping[str, str] = {
        page: (docs_dir / page).read_text(encoding="utf-8", errors="replace")
        for page in pages
    }
    targets = {
        page: text for page, text in texts.items() if is_target(page, text)
    }
    if not targets:
        raise MetadataLoadError(
            "docs-duplicates resolved no target page to read; an empty "
            "target set is a failure, not a pass (DF-09-009)",
            path="docs",
        )
    found = [
        paragraph
        for page, text in sorted(targets.items())
        for paragraph in paragraphs(text, page, min_chars=min_chars)
    ]
    return DuplicateReport(
        len(targets), find_clusters(found, threshold=threshold)
    )


def format_cluster(cluster: Cluster) -> str:
    """Render one cluster: its kind, then each wording with its hosts."""
    lines = [f"{cluster.kind} copy across {len(cluster.files)} pages:"]
    for variant in cluster.variants:
        for host in variant.hosts:
            lines.append(f"  docs/{host.path}:{host.line}")
        lines.append(f"    > {variant.text}")
    return "\n".join(lines)


def _min_chars(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _threshold(value: str) -> float:
    number = float(value)
    if not 0 < number <= 1:
        raise argparse.ArgumentTypeError("must be in (0, 1]")
    return number


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-duplicates`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "List paragraphs repeated across docs/ pages, exact or drifted "
            "(advisory, SG-43)."
        )
    )
    parser.add_argument(
        "--threshold",
        type=_threshold,
        default=THRESHOLD,
        help=f"sentence overlap for a drifted copy (default {THRESHOLD})",
    )
    parser.add_argument(
        "--min-chars",
        type=_min_chars,
        default=MIN_CHARS,
        help=f"shortest paragraph reported (default {MIN_CHARS})",
    )
    args = parser.parse_args(argv)

    try:
        report = duplicate_report(
            _find_repo_root(),
            min_chars=args.min_chars,
            threshold=args.threshold,
        )
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    for cluster in report.clusters:
        print(format_cluster(cluster))
        print()
    exact = sum(1 for c in report.clusters if c.kind == "exact")
    print(
        f"{len(report.clusters)} cluster(s) of repeated paragraphs "
        f"({exact} exact, {len(report.clusters) - exact} drifted) across "
        f"{report.pages} page(s); advisory, see SG-43."
    )


if __name__ == "__main__":
    main()
