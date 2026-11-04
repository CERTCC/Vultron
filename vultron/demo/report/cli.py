"""Report generation and the ``vultron-demo-report`` command line (DRPT-01-004)."""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from __future__ import annotations

import argparse
import logging
import webbrowser
from pathlib import Path

from vultron.demo.helpers.ledger_dump import default_devlogs_root
from vultron.demo.report.render import render_html, render_markdown
from vultron.demo.report.timeline import (
    ReportError,
    build_timeline,
    discover_replicas,
    discovered_actors,
)

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


_RENDERERS = {"markdown": render_markdown, "html": render_html}
_EXTENSIONS = {"markdown": ".md", "html": ".html"}


def generate_report(input_dir: Path, fmt: str) -> str:
    """Discover, distil, and render the report for ``input_dir`` in ``fmt``."""
    replicas = discover_replicas(input_dir)
    events = build_timeline(replicas)
    actors = discovered_actors(replicas)
    logger.info(
        "Distilled %d canonical events across %d replicas: %s",
        len(events),
        len(actors),
        ", ".join(actors),
    )
    return _RENDERERS[fmt](events, actors)


# ---------------------------------------------------------------------------
# CLI (DRPT-01-001, DRPT-01-006, DRPT-04-004, DRPT-04-005, DRPT-04-017,
# DRPT-04-018)
# ---------------------------------------------------------------------------


def default_input_dir() -> Path:
    """Return the default input directory (``DEVLOGS_DIR`` env, else ``devlogs/``).

    Delegates to :func:`vultron.demo.helpers.ledger_dump.default_devlogs_root`
    so this reader and the dump that writes the ledgers cannot disagree about
    where they live (DEMOMA-17-001).
    """
    return default_devlogs_root()


def default_output_path(input_dir: Path, fmt: str) -> Path:
    """Return the default report file path for ``fmt`` under ``input_dir``."""
    return input_dir / f"case-timeline-report{_EXTENSIONS[fmt]}"


def _parse_args(
    argv: list[str] | None = None, *, prog: str | None = None
) -> argparse.Namespace:
    """Parse command-line arguments for the report tool.

    *prog* names the program in ``--help``; ``None`` takes it from
    ``sys.argv[0]``, which is right for the ``vultron-demo-report`` console
    script.  ``python -m vultron.demo.report`` passes its own name (see
    :mod:`vultron.demo.report.__main__`).
    """
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Render a readable report from demo scenario case-ledger JSONL "
            "replica files."
        ),
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=None,
        help=(
            "Directory to scan for **/*-case-ledger.jsonl files "
            "(default: $DEVLOGS_DIR, else devlogs/)."
        ),
    )
    parser.add_argument(
        "--format",
        choices=sorted(_RENDERERS),
        default="markdown",
        help="Output format (default: markdown).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Report output file path (default: <input-dir>/case-timeline-report.*).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open an HTML report in the browser (required for CI).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    """CLI entry point. Returns a process exit code (DRPT-01-004).

    Callable with no arguments (defaults to ``sys.argv[1:]``) so it also works
    as a console-script target.  *prog* is passed to the argument parser (see
    :func:`_parse_args`).
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    args = _parse_args(argv, prog=prog)
    input_dir = Path(args.input_dir) if args.input_dir else default_input_dir()
    output_path = (
        Path(args.output)
        if args.output
        else default_output_path(input_dir, args.format)
    )

    try:
        report = generate_report(input_dir, args.format)
    except ReportError as exc:
        logger.error("error: %s", exc)  # noqa: TRY400  # ruff-baseline #3353
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    except OSError as exc:
        logger.error("error: cannot write %s: %s", output_path, exc)  # noqa: TRY400  # ruff-baseline #3353
        return 1

    logger.info("Wrote %s report → %s", args.format, output_path)

    if args.format == "html" and not args.no_open:
        webbrowser.open(output_path.resolve().as_uri())

    return 0
