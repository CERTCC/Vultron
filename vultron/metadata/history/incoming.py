"""Validator for ``plan/incoming/learnings/*.md`` frontmatter.

Incoming learning files are staged in the same frontmatter format as history
entries so that archiving is a content-free move (BW-02-001).  The archiver
(``append-history --from-file``) validates each file through
:class:`~vultron.metadata.history.models.HistoryEntryFrontmatter` before it
writes anything, so a file that fails that model cannot be archived at all.

Nothing else in the pipeline used to check this.  A malformed entry looked fine
in review and in CI, and only failed months later when ``learn`` tried to drain
the queue — by which time 37 of 62 files had accumulated the same defect
(ISSUE-2762).  This module exists so the check runs at commit time against the
*same* model the archiver uses, which is what keeps the two from drifting.

Requirements: BW-02-001 through BW-02-004.
"""

from __future__ import annotations

import sys
from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.file_loading import (
    FailureCollector,
    MetadataLoadErrors,
    load_frontmatter,
    validate,
)
from vultron.metadata.history.models import HistoryEntryFrontmatter

LEARNINGS_DIR = Path("plan") / "incoming" / "learnings"

SKIP_FILES = {"README.md"}


#: Shared by the raising path and the CLI's report-and-continue path, so the
#: remediation text cannot drift between them.
_SUMMARY = (
    f"file(s) in {LEARNINGS_DIR} cannot be archived by"
    " `append-history --from-file` (BW-02-001):"
)
_FOOTER = (
    "Common fixes:\n"
    '  - timestamp MUST be tz-aware and quoted: "YYYY-MM-DDTHH:MM:SSZ"'
    " (BW-02-004);\n"
    "    a bare YYYY-MM-DD parses to a naive datetime and is rejected.\n"
    "  - source MUST be the originating work item, e.g. ISSUE-1234"
    " (BW-02-002).\n"
    "  - type MUST be `learning`.\n"
    "  - quote any title containing or ending with a colon."
)


def _collect_incoming_learnings(
    repo_root: Path | None = None,
) -> tuple[dict[str, HistoryEntryFrontmatter], FailureCollector]:
    """Parse every incoming learning, returning what validated and what did not.

    Split out from :func:`validate_incoming_learnings` so a reader that only
    wants the usable entries — ``learnings-index`` — can report the failures
    without losing the rest of the directory to an exception. The collector is
    returned rather than raised from so the caller chooses which it needs.
    """
    root = repo_root or _find_repo_root()
    directory = root / LEARNINGS_DIR

    collector = FailureCollector()
    if not directory.is_dir():
        return {}, collector

    validated: dict[str, HistoryEntryFrontmatter] = {}

    for path in sorted(directory.glob("*.md")):
        if path.name in SKIP_FILES:
            continue
        with collector.attempt():
            # A `title:` whose text contains or ends with a colon and is left
            # unquoted makes the whole block invalid YAML, so parse failures
            # are a real and recurring mode here rather than a theoretical one.
            post = load_frontmatter(path, root=root)
            validated[path.name] = validate(
                HistoryEntryFrontmatter, post.metadata, path=path, root=root
            )

    return validated, collector


def validate_incoming_learnings(
    repo_root: Path | None = None,
) -> dict[str, HistoryEntryFrontmatter]:
    """Validate every incoming learning file's frontmatter.

    Args:
        repo_root: Repository root.  Resolved automatically when ``None``.

    Returns:
        Mapping of filename to its parsed frontmatter, for the files that
        validated.

    Raises:
        MetadataLoadErrors: If any file fails to parse or validate.  The
            message lists every offending file so a contributor fixes them in
            one pass rather than one commit at a time, and ``failures`` carries
            each one.  A ``ValueError`` subclass.
    """
    validated, collector = _collect_incoming_learnings(repo_root)
    collector.raise_if_any(
        summary=f"{len(collector.failures)} {_SUMMARY}", footer=_FOOTER
    )
    return validated


def render_learnings_index(
    entries: dict[str, HistoryEntryFrontmatter],
) -> str:
    """Render one line per incoming learning: source, title, filename.

    Each learning's ``title`` states the lesson in full — that is the house
    style — so the titles alone carry what a reader of the whole directory
    would take away, at ~5% of the bytes.
    """
    lines = [
        f"{fm.source}  {fm.title}\n    {name}"
        for name, fm in sorted(
            entries.items(), key=lambda kv: kv[1].timestamp, reverse=True
        )
    ]
    header = (
        f"# {len(lines)} incoming learnings, newest first."
        f" Titles state the lesson; read {LEARNINGS_DIR}/<file> for the"
        " evidence behind one that bears on your task."
    )
    return "\n".join([header, *lines]) + "\n"


def main() -> None:
    """Print the incoming-learnings index (``learnings-index``).

    One malformed file must not cost orientation the whole index, so failures
    are reported on stderr and the valid entries still print.
    """
    validated, collector = _collect_incoming_learnings()
    if collector.failures:
        report = MetadataLoadErrors(
            collector.failures,
            summary=f"learnings-index: skipped {len(collector.failures)}"
            f" {_SUMMARY}",
            footer=_FOOTER,
        )
        print(report, file=sys.stderr)
    sys.stdout.write(render_learnings_index(validated))
