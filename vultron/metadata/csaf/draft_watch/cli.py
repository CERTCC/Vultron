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
"""The ``csaf-draft-watch`` command line."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from vultron.metadata.csaf.draft_watch.compare import compare
from vultron.metadata.csaf.draft_watch.issue import render_issue
from vultron.metadata.csaf.pin import load_pin
from vultron.metadata.generated_files import write_generated

#: The first line of the package docstring, for ``--help``.
_DESCRIPTION = "Say whether the CSAF 2.1 draft upstream changes what the models depend on."

#: Exit status when upstream changes what the models, profiles or test list
#: depend on.
EXIT_CHANGED = 3


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="csaf-draft-watch", description=_DESCRIPTION
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="a checkout of the upstream repository at the pinned commit",
    )
    parser.add_argument(
        "--upstream",
        type=Path,
        required=True,
        help="a checkout of the upstream repository at the commit to compare",
    )
    parser.add_argument(
        "--upstream-commit",
        help="the commit --upstream is at, named in the issue body",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="where to write the issue body when something changed",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Compare the checkouts; exit :data:`EXIT_CHANGED` when something changed."""
    args = _parse_args(argv)
    pin = load_pin()
    change = compare(pin, args.baseline, args.upstream)
    if not change.changed:
        print(
            "No change to what the CSAF models, profiles or tests depend on."
        )
        return 0
    body = render_issue(change, pin, args.upstream_commit)
    if args.report is not None:
        write_generated(args.report, body)
    print(body)
    return EXIT_CHANGED


if __name__ == "__main__":
    sys.exit(main())
