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
"""``theme-gate``: refuse to create an Issue that would break the theme rules.

::

    theme-gate --label size:M --label theme:dev-workflow --parent 42 \\
        --body-file body.md
    theme-gate --epic --label theme:dev-workflow --body-file - < body.md

``manage_github_issue.sh`` and ``create_epic.sh`` run it before they create
anything, so an Issue that ``theme-fit`` would report never gets made. It
applies the same label rules as ``theme-fit`` (:func:`.analyze.label_findings`)
to the Issue about to be created, and checks the parent's theme:

- a leaf carries exactly one active catalog theme (PAD-02-014); an Epic one,
  or two with a body line naming both (PAD-02-015);
- the body has a ``Theme: <label> — <outcome>`` line naming it (PAD-02-018);
- the ``--parent``, when given, is open and carries that theme (PAD-02-017,
  PAD-01-007).

Every violation is printed, not only the first. Exit codes: 0 the Issue may be
created, 1 it may not, 2 the catalog cannot be loaded or a ``gh`` call fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.planning.gh import (
    DEFAULT_REPO,
    GH_FAILURES,
    GhError,
    Runner,
    gh_failure_detail,
    run_gh,
)
from vultron.metadata.planning.theme_fit.analyze import label_findings
from vultron.metadata.planning.theme_fit.model import (
    EPIC_TYPE,
    FindingKind,
    OpenIssue,
)
from vultron.metadata.planning.themes import (
    THEME_PREFIX,
    ThemeCatalog,
    load_theme_catalog,
)


@dataclass(frozen=True)
class ParentIssue:
    """The parent an Issue is about to be created under."""

    number: int
    is_open: bool
    labels: frozenset[str]

    @property
    def themes(self) -> tuple[str, ...]:
        """The ``theme:`` labels it carries, case-folded and sorted."""
        return tuple(
            sorted(
                label.casefold()
                for label in self.labels
                if label.casefold().startswith(THEME_PREFIX)
            )
        )


def fetch_parent(number: int, repo: str, run: Runner) -> ParentIssue:
    """Read the state and labels of Issue *number* through ``gh``.

    Raises:
        GhError: If the reply is not the JSON ``gh issue view`` prints.
        subprocess.CalledProcessError: If ``gh`` exits non-zero.
    """
    out = run(
        [
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "state,labels",
        ]
    )
    try:
        data = json.loads(out)
        return ParentIssue(
            number=number,
            is_open=data["state"] == "OPEN",
            labels=frozenset(label["name"] for label in data["labels"]),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise GhError(f"unreadable reply for #{number}: {exc}") from exc


def _listed(themes: Iterable[str]) -> str:
    return ", ".join(f"`{t}`" for t in themes)


def _parent_findings(
    issue: OpenIssue, parent: ParentIssue
) -> Iterator[tuple[FindingKind, str]]:
    """Why *parent* cannot take *issue*, one reason per finding."""
    if not parent.is_open:
        yield FindingKind.UNPARENTED, f"parent #{parent.number} is closed"
    if not issue.themes:
        # The missing theme is already a theme-count finding.
        return
    if not parent.themes:
        yield (
            FindingKind.THEME_MISMATCH,
            f"parent #{parent.number} carries no theme label",
        )
        return
    stray = [t for t in issue.themes if t not in parent.themes]
    if stray:
        yield (
            FindingKind.THEME_MISMATCH,
            f"carries {_listed(stray)}; parent #{parent.number} carries "
            f"{_listed(parent.themes)}",
        )


def gate_findings(
    labels: Iterable[str],
    body: str,
    catalog: ThemeCatalog,
    *,
    epic: bool = False,
    parent: ParentIssue | None = None,
) -> list[tuple[FindingKind, str]]:
    """Every theme rule the Issue about to be created would break.

    Args:
        labels: Every label it will carry; non-theme labels are ignored.
        body: Its body text.
        catalog: The theme catalog its labels are checked against.
        epic: True when it is an Epic, which may carry a named second theme.
        parent: The Issue it will be a sub-issue of, if any.
    """
    issue = OpenIssue(
        number=0,
        title="",
        issue_type=EPIC_TYPE if epic else None,
        labels=frozenset(labels),
        body=body,
    )
    found = list(label_findings(issue, catalog, is_leaf=True))
    if parent is not None:
        found.extend(_parent_findings(issue, parent))
    return found


def split_labels(values: Iterable[str]) -> list[str]:
    """The labels in *values*, each of which may be a comma-separated list."""
    return [
        label.strip()
        for value in values
        for label in value.split(",")
        if label.strip()
    ]


def main(argv: list[str] | None = None, run: Runner = run_gh) -> int:
    """CLI entry point: check the Issue described by *argv*."""
    parser = argparse.ArgumentParser(
        description=(
            "Refuse to create an Issue without exactly one theme, a Theme: "
            "line, and a parent carrying that theme."
        )
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="a label it will carry; repeatable, or comma-separated",
    )
    parser.add_argument(
        "--body-file",
        required=True,
        help="file holding its body, or - for standard input",
    )
    parser.add_argument(
        "--parent", type=int, help="the Issue it will be a sub-issue of"
    )
    parser.add_argument(
        "--epic",
        action="store_true",
        help="it is an Epic (one theme, or two with a named split)",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="OWNER/NAME (default: %(default)s)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="the catalog note (default: notes/epic-themes.md)",
    )
    args = parser.parse_args(argv)

    if args.body_file == "-":
        body = sys.stdin.read()
    else:
        try:
            body = Path(args.body_file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"theme-gate: cannot read body: {exc}", file=sys.stderr)
            return 2

    try:
        catalog = load_theme_catalog(args.catalog)
    except (MetadataLoadError, FileNotFoundError) as exc:
        print(f"theme-gate: {exc}", file=sys.stderr)
        return 2

    parent = None
    if args.parent is not None:
        try:
            parent = fetch_parent(args.parent, args.repo, run)
        except GH_FAILURES as exc:
            print(
                f"theme-gate: gh failed: {gh_failure_detail(exc)}",
                file=sys.stderr,
            )
            return 2

    found = gate_findings(
        split_labels(args.label),
        body,
        catalog,
        epic=args.epic,
        parent=parent,
    )
    for kind, detail in found:
        print(
            f"theme-gate: {kind.rule} {kind.heading}: {detail}",
            file=sys.stderr,
        )
    if found:
        print(
            "theme-gate: refusing to create the Issue; see "
            "notes/epic-themes.md and the create-issue skill",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
