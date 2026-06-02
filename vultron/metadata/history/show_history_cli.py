"""CLI entry point for the ``show-history`` tool.

Usage::

    uv run show-history                    # current month
    uv run show-history --month 2604       # April 2026
    uv run show-history --all              # all months, newest first

Prints a markdown history index table to stdout by scanning
``plan/history/YYMM/<type>/`` entry files on demand.

Monthly ``plan/history/YYMM/README.md`` files are gitignored generated
artifacts.  This command is the canonical way to view the history index
without relying on a committed file.

See ``specs/history-management.yaml`` HM-01-003, HM-03-006.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

from vultron.metadata.history.readme_gen import format_month_index

_UTC = datetime.timezone.utc


def _find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``.

    Raises:
        FileNotFoundError: If ``pyproject.toml`` cannot be found in any
            parent directory.
    """
    origin = (start or Path.cwd()).resolve()
    for parent in [origin, *origin.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        f"Could not locate repository root (pyproject.toml) starting from "
        f"{origin}"
    )


def _month_dirs_descending(history_root: Path) -> list[Path]:
    """Return all ``YYMM`` subdirectories under *history_root*, newest first."""
    dirs = [
        d
        for d in history_root.iterdir()
        if d.is_dir() and len(d.name) == 4 and d.name.isdigit()
    ]
    return sorted(dirs, key=lambda d: d.name, reverse=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="show-history",
        description=(
            "Print the project history index as a markdown table. "
            "Scans plan/history/YYMM/ entry files on demand — "
            "no committed index file required."
        ),
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--month",
        metavar="YYMM",
        default=None,
        help="Show a specific month (e.g. 2604 for April 2026).",
    )
    scope.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Show all months, newest first.",
    )
    return parser


def main() -> None:
    """Entry point for ``uv run show-history``."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    history_root = repo_root / "plan" / "history"
    if not history_root.is_dir():
        print("Error: plan/history/ directory not found.", file=sys.stderr)
        sys.exit(1)

    if args.all:
        month_dirs = _month_dirs_descending(history_root)
        if not month_dirs:
            print("No history months found.", file=sys.stderr)
            sys.exit(0)
        print("\n\n".join(format_month_index(d) for d in month_dirs))
    else:
        if args.month:
            yymm = args.month
        else:
            yymm = datetime.datetime.now(_UTC).strftime("%y%m")
        month_dir = history_root / yymm
        if not month_dir.is_dir():
            print(
                f"Error: no history directory found for {yymm} "
                f"(expected {month_dir}).",
                file=sys.stderr,
            )
            sys.exit(1)
        print(format_month_index(month_dir))


if __name__ == "__main__":
    main()
