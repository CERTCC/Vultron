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
"""The ``uv run wire-context`` command (VM-10-001, VM-10-007).

CLI:
    --check   exit 1 if a wire field breaks a JSON-LD term rule that no
              owner's ratchet excuses, or a ratchet entry is stale
              (:mod:`~vultron.metadata.wire_context.terms`), or if
              ``docs/ns/context.jsonld`` or the page's table is stale
              (:mod:`~vultron.metadata.wire_context.sync`)
    --write   rewrite both generated files in place
"""

from __future__ import annotations

import argparse
import sys

from vultron.metadata.wire_context import sync, terms
from vultron.metadata.wire_context.sync import (
    CONTEXT_JSONLD_PATH,
    NS_INDEX_PATH,
    WRITE_COMMAND,
)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run wire-context [--check|--write]``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help=(
            "Exit 1 if a wire field has no JSON-LD term (VM-10-007, VM-10-009,"
            f" VM-10-012), or if {CONTEXT_JSONLD_PATH} or {NS_INDEX_PATH} is"
            " stale."
        ),
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help=f"Rewrite {CONTEXT_JSONLD_PATH} and {NS_INDEX_PATH}'s property "
        "table from the wire vocabulary.",
    )
    args = parser.parse_args(argv)

    artifacts = f"{CONTEXT_JSONLD_PATH} and {NS_INDEX_PATH}"
    if args.write:
        if sync.write_context():
            print(f"Wrote {artifacts}")
        else:
            print(f"{artifacts} already in sync.")
        return

    report = terms.check_wire_terms()
    if not report.ok:
        print(
            "[ERROR] wire fields break a JSON-LD term rule (ADR-0194); fix"
            f" each, or, for a known one, its owner's ratchet in {terms.RATCHET_PATH}:",
            file=sys.stderr,
        )
        for line in report.lines():
            print(f"  {line}", file=sys.stderr)
        sys.exit(1)

    if sync.is_stale():
        print(
            f"[ERROR] {artifacts} are stale — run '{WRITE_COMMAND}' "
            "(VM-10-001, VM-10-002, VM-10-010). A Vultron-namespace wire type "
            "or property was added, removed, re-annotated or redefined "
            "without regenerating the context.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"{artifacts} are in sync.")


if __name__ == "__main__":
    main()
