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

from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.file_loading import (
    FailureCollector,
    load_frontmatter,
    validate,
)
from vultron.metadata.history.models import HistoryEntryFrontmatter

LEARNINGS_DIR = Path("plan") / "incoming" / "learnings"

SKIP_FILES = {"README.md"}


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
    root = repo_root or _find_repo_root()
    directory = root / LEARNINGS_DIR

    if not directory.is_dir():
        return {}

    validated: dict[str, HistoryEntryFrontmatter] = {}
    collector = FailureCollector()

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

    collector.raise_if_any(
        summary=(
            f"{len(collector.failures)} file(s) in {LEARNINGS_DIR} cannot be"
            " archived by `append-history --from-file` (BW-02-001):"
        ),
        footer=(
            "Common fixes:\n"
            '  - timestamp MUST be tz-aware and quoted: "YYYY-MM-DDTHH:MM:SSZ"'
            " (BW-02-004);\n"
            "    a bare YYYY-MM-DD parses to a naive datetime and is rejected.\n"
            "  - source MUST be the originating work item, e.g. ISSUE-1234"
            " (BW-02-002).\n"
            "  - type MUST be `learning`.\n"
            "  - quote any title containing or ending with a colon."
        ),
    )

    return validated
