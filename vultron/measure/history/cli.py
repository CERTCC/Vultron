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
"""The ``vultron-case-history`` command: dump one case's CVD event history (CEH-01-004).

A thin wrapper over :func:`~vultron.measure.history.case_history_report`, so
the tests exercise one code path.  It writes the history as JSON or as a
Markdown table (CEH-01-005), to a file or to standard output, and exits
non-zero when an input file is missing or unreadable, holds no case ledger
entry, or does not hold the case named with ``--case`` (CEH-01-008).

Writing its own output file is the one write the measure layer admits
(CEH-01-002); :func:`_write_output` is that write.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from vultron.errors import CaseHistoryInputError, LedgerReadError
from vultron.measure.history.render import HistoryFormat, case_history_report

logger = logging.getLogger(__name__)

#: Exit code for input the command cannot dump (CEH-01-008).
EXIT_BAD_INPUT = 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="vultron-case-history",
        description=(
            "Dump the CVD event history of the case in the given case-ledger "
            "JSONL files."
        ),
    )
    parser.add_argument(
        "ledgers",
        nargs="+",
        type=Path,
        help="Case-ledger JSONL files: one complete copy, or replicas to merge.",
    )
    parser.add_argument(
        "--case",
        dest="case_id",
        default=None,
        help="The case id to dump (default: every case the files hold).",
    )
    parser.add_argument(
        "--format",
        choices=[f.value for f in HistoryFormat],
        default=HistoryFormat.TABLE.value,
        help="table (Markdown, for a person) or json (for a program).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="File to write (default: standard output).",
    )
    return parser.parse_args(argv)


def _refuse(message: str) -> int:
    """Report input or output the command cannot handle; return its exit code."""
    logger.error("error: %s", message)
    return EXIT_BAD_INPUT


def _write_output(text: str, output: Path | None) -> None:
    """Write the dump to *output*, or to standard output when it is ``None``.

    The file is written beside *output* and then moved into place, so a write
    that fails partway leaves no truncated dump behind.  The partial file's
    name carries this process's id, so two runs writing one output never
    remove each other's.  A symlinked *output* is resolved first, so the dump
    replaces the file it points at, not the link.
    """
    if output is None:
        sys.stdout.write(text)
        return
    output = output.resolve()
    partial = output.with_name(f".{output.name}.{os.getpid()}.partial")
    try:
        partial.write_text(text, encoding="utf-8")
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Run the command; return its exit code (CEH-01-004, CEH-01-008)."""
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)
    try:
        text = case_history_report(
            args.ledgers,
            fmt=HistoryFormat(args.format),
            case_id=args.case_id,
        )
    except (LedgerReadError, CaseHistoryInputError) as exc:
        return _refuse(str(exc))
    try:
        _write_output(text, args.output)
    except OSError as exc:
        target = args.output or "standard output"
        return _refuse(f"cannot write {target}: {exc}")
    if args.output is not None:
        logger.info(
            "Wrote %s case event history → %s", args.format, args.output
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
