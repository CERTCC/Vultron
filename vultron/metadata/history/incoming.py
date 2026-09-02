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

import frontmatter
from pydantic import ValidationError

from vultron.metadata.history.models import HistoryEntryFrontmatter

LEARNINGS_DIR = Path("plan") / "incoming" / "learnings"

SKIP_FILES = {"README.md"}


def _find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``."""
    origin = start or Path.cwd()
    for parent in [origin, *origin.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        "Could not locate repository root (pyproject.toml) starting from"
        f" {origin}"
    )


def _describe(exc: Exception) -> str:
    """Render a validation failure as a single compact line."""
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors():
            field = ".".join(str(p) for p in err.get("loc", ())) or "<root>"
            parts.append(f"{field}: {err.get('msg', 'invalid')}")
        return "; ".join(parts)
    return f"{type(exc).__name__}: {exc}"


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
        ValueError: If any file fails to parse or validate.  The message lists
            every offending file so a contributor fixes them in one pass
            rather than one commit at a time.
    """
    root = repo_root or _find_repo_root()
    directory = root / LEARNINGS_DIR

    if not directory.is_dir():
        return {}

    validated: dict[str, HistoryEntryFrontmatter] = {}
    failures: list[str] = []

    for path in sorted(directory.glob("*.md")):
        if path.name in SKIP_FILES:
            continue
        try:
            post = frontmatter.load(path)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            # A `title:` whose text contains or ends with a colon and is left
            # unquoted makes the whole block invalid YAML, so parse failures
            # are a real and recurring mode here rather than a theoretical one.
            failures.append(f"  {path.name}: unparseable frontmatter — {exc}")
            continue

        try:
            validated[path.name] = HistoryEntryFrontmatter.model_validate(
                post.metadata
            )
        except ValidationError as exc:
            failures.append(f"  {path.name}: {_describe(exc)}")

    if failures:
        raise ValueError(
            f"{len(failures)} file(s) in {LEARNINGS_DIR} cannot be archived by"
            " `append-history --from-file` (BW-02-001):\n"
            + "\n".join(failures)
            + "\n\nCommon fixes:\n"
            '  - timestamp MUST be tz-aware and quoted: "YYYY-MM-DDTHH:MM:SSZ"'
            " (BW-02-004);\n"
            "    a bare YYYY-MM-DD parses to a naive datetime and is rejected.\n"
            "  - source MUST be the originating work item, e.g. ISSUE-1234"
            " (BW-02-002).\n"
            "  - type MUST be `learning`.\n"
            "  - quote any title containing or ending with a colon."
        )

    return validated
