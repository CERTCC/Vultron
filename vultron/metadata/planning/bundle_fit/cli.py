"""The ``bundle-fit`` console script: GraphQL JSON in, bundle proposal out.

Reads stdin rather than files so the selection logic stays testable without the
network — see ``vultron/metadata/AGENTS.md``. Exit codes: ``0`` a proposal was
produced, ``1`` there is nothing to select from, ``2`` the input was unusable.
"""

from __future__ import annotations

import argparse
import json
import sys

from vultron.metadata.planning.bundle_fit.model import (
    DEFAULT_BUDGET,
    DEFAULT_MAX_MEMBERS,
    PLANNING_PROJECT_NUMBER,
    WORKFLOW_BY_TYPE,
)
from vultron.metadata.planning.bundle_fit.parse import (
    graphql_errors,
    parse_graphql,
)
from vultron.metadata.planning.bundle_fit.render import _render
from vultron.metadata.planning.bundle_fit.select import (
    effective_schedule,
    select_bundle,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: GraphQL JSON on stdin, bundle proposal on stdout."""
    parser = argparse.ArgumentParser(
        description="Select a fit-checked work bundle from an Epic's leaf issues."
    )
    parser.add_argument(
        "--workflow", choices=sorted(set(WORKFLOW_BY_TYPE.values()))
    )
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--max-members", type=int, default=DEFAULT_MAX_MEMBERS)
    parser.add_argument(
        "--project-number", type=int, default=PLANNING_PROJECT_NUMBER
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"❌ stdin is not valid JSON: {exc}", file=sys.stderr)
        return 2

    errors = graphql_errors(payload)
    if errors:
        print("❌ the GraphQL query failed:", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        print(
            "   Reading the Schedule field needs the read:project scope: "
            "`gh auth refresh -s read:project`",
            file=sys.stderr,
        )
        return 2

    epic, epic_schedule, candidates = parse_graphql(
        payload, args.project_number
    )
    # Three distinct causes that all used to print "no sub-issues found for
    # Epic #None — is the number right?", which guessed at the cause and leaked
    # `None` into user-facing text.
    if epic is None:
        print(
            "❌ the payload carries no data.repository.issue — is the Epic "
            "number right, and does the token have repo access?",
            file=sys.stderr,
        )
        return 1
    if not candidates:
        print(
            f"❌ Epic #{epic} has no sub-issues, so there is nothing to "
            "select from. Run /plan-issue to decompose it first.",
            file=sys.stderr,
        )
        return 1

    bundle = select_bundle(
        candidates,
        epic=epic,
        epic_schedule=epic_schedule,
        workflow=args.workflow,
        budget=args.budget,
        max_members=args.max_members,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "epic": bundle.epic,
                    "epic_schedule": bundle.epic_schedule,
                    "workflow": bundle.workflow,
                    "command": bundle.command,
                    "budget": bundle.budget,
                    "weight": bundle.weight,
                    "members": [
                        {
                            "number": c.number,
                            "title": c.title,
                            "issue_type": c.issue_type,
                            "weight": c.weight,
                            "sized": c.sized,
                            "schedule": effective_schedule(
                                c, bundle.epic_schedule
                            ),
                        }
                        for c in bundle.members
                    ],
                    "rejected": [
                        {
                            "number": r.number,
                            "stage": r.stage,
                            "reason": r.reason,
                        }
                        for r in bundle.rejected
                    ],
                    "hints": bundle.hints,
                },
                indent=2,
            )
        )
    else:
        print(_render(bundle))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
