"""The ``backfill-implementation-history`` command line."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.history.backfill_implementation.coerce import (
    _coerce_manifest,
)
from vultron.metadata.history.backfill_implementation.manifest import (
    _write_manifest_output,
    build_manifest,
    write_manifest,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backfill-implementation-history",
        description=(
            "Build a dry-run manifest for legacy implementation history "
            "backfill, or write reviewed entries from an existing manifest."
        ),
    )
    parser.add_argument(
        "--legacy-file",
        default="plan/history/IMPLEMENTATION_HISTORY.md",
        help="Legacy implementation history file to parse.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write the generated manifest to PATH instead of stdout.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Reviewed manifest JSON to write from.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write immutable history files from --manifest.",
    )
    return parser


def main() -> None:
    """CLI entry point for implementation history backfill."""
    parser = _build_parser()
    args = parser.parse_args()
    repo_root = _find_repo_root()

    try:
        if args.write:
            if args.manifest is None:
                raise ValueError("--write requires --manifest")  # noqa: TRY301  # ruff-baseline #3353
            manifest_path = Path(args.manifest)
            manifest = _coerce_manifest(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            written_paths = write_manifest(repo_root, manifest)
            print(
                f"Wrote {len(written_paths)} implementation history entries."
            )
            return

        legacy_file = (repo_root / args.legacy_file).resolve()
        manifest = build_manifest(repo_root, legacy_file)
        output_path = Path(args.output).resolve() if args.output else None
        _write_manifest_output(manifest, output_path)
    except (
        FileExistsError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
