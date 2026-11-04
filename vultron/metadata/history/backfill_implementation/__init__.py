"""Backfill tool for legacy implementation history entries.

This tool creates a reviewable manifest from
``plan/history/IMPLEMENTATION_HISTORY.md`` and can later write immutable
history entry files from that manifest after review.

Submodules, by concern: ``legacy`` (reading the legacy file), ``manifest``
(building the manifest and writing entries from it), ``coerce`` (reading a
reviewed manifest back) and ``cli`` (the command line).
"""

from vultron.metadata.history.backfill_implementation.cli import main
from vultron.metadata.history.backfill_implementation.legacy import (
    normalize_title,
    split_legacy_sections,
)
from vultron.metadata.history.backfill_implementation.manifest import (
    build_manifest,
    write_manifest,
)

__all__ = [
    "build_manifest",
    "main",
    "normalize_title",
    "split_legacy_sections",
    "write_manifest",
]
