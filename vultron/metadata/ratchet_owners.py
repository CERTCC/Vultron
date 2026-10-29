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
"""Report ratchet baselines whose ``# owner: #N`` issue is not open (ARCH-18-004).

Every non-empty ratchet baseline under ``test/`` names the issue that drives
it to its terminal value (ARCH-18-003). When that issue closes with entries
left, the debt has no owner. This script reads every ``# owner: #N`` marker
through :mod:`vultron.metadata.ratchet_markers` (the parser the offline test
uses), asks GitHub for each cited issue's state, and lists the baselines whose
owner is closed, does not exist, or could not be read. A lookup that fails is
reported, never passed: a check that cannot see an issue has not shown it open.

It exits 1 when it lists anything, so the scheduled workflow
(``.github/workflows/ratchet-baseline-owners.yml``) can file or update its one
tracking issue; that step runs with ``continue-on-error``, so a closed owner
never fails the build.

Usage::

    ratchet-owners                      # report to stdout (needs gh)
    ratchet-owners --report owners.md   # also write the tracking-issue text
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import (
    GH_LOOKUP_ERRORS,
    gh_issue_missing,
    gh_issue_state,
    gh_lookup_failure,
    repo_root,
)
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.ratchet_markers import Baseline, scan_paths

#: Looks up the state of one ``#N`` issue (``OPEN``, ``CLOSED``, ...).
IssueStateLookup = Callable[[str], str]


@dataclass(frozen=True)
class OwnerFinding:
    """One cited owner that is not an open issue, and the baselines citing it."""

    owner: int
    reason: str
    baselines: tuple[Baseline, ...]


def baselines_under_test(root: Path) -> list[Baseline]:
    """Every ratchet baseline in a Python file under *root*'s ``test/``.

    Each :attr:`Baseline.path` is relative to *root*.

    Raises:
        MetadataLoadError: When a file is not valid UTF-8 or not valid
            Python, naming it ``path:line:col`` (MS-17-001): a file skipped
            silently would leave its owners unchecked.
    """
    return scan_paths(sorted((root / "test").rglob("*.py")), root)


def _not_open_reason(ref: str, issue_state: IssueStateLookup) -> str | None:
    """Why issue *ref* is not shown open, or ``None`` when it is open."""
    try:
        state = issue_state(ref).upper()
    except GH_LOOKUP_ERRORS as exc:
        if gh_issue_missing(exc):
            return "does not exist"
        return f"could not be read ({gh_lookup_failure(exc)})"
    return None if state == "OPEN" else f"is {state}"


def owner_findings(
    baselines: Iterable[Baseline],
    issue_state: IssueStateLookup | None = None,
) -> list[OwnerFinding]:
    """The owners cited in *baselines* that are not open, in issue order.

    Each distinct owner is looked up once, however many baselines cite it.
    *issue_state* defaults to :func:`gh_issue_state`.
    """
    lookup = issue_state if issue_state is not None else gh_issue_state
    citing: dict[int, list[Baseline]] = defaultdict(list)
    for baseline in baselines:
        for owner in dict.fromkeys(baseline.owners):
            citing[owner].append(baseline)
    findings: list[OwnerFinding] = []
    for owner in sorted(citing):
        reason = _not_open_reason(f"#{owner}", lookup)
        if reason is not None:
            findings.append(OwnerFinding(owner, reason, tuple(citing[owner])))
    return findings


def report_markdown(findings: Sequence[OwnerFinding]) -> str:
    """The tracking-issue text listing each affected baseline by owner."""
    lines = [
        "Ratchet baselines whose `# owner: #N` issue is not open (ARCH-18-004)."
        " Re-point each marker at the open issue that took the work over, or"
        " finish the work and empty the baseline.",
        "",
    ]
    for finding in findings:
        lines.append(f"- #{finding.owner} {finding.reason}:")
        lines += [
            f"  - `{b.path}:{b.line}` `{b.name}`" for b in finding.baselines
        ]
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ratchet-owners",
        description=(
            "List ratchet baselines under test/ whose '# owner: #N' issue is"
            " not open (ARCH-18-004). Needs gh and a token. Exits 1 when it"
            " lists any."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="also write the tracking-issue Markdown to this file",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    issue_state: IssueStateLookup | None = None,
) -> int:
    """Run the report; 0 when every cited owner is open, 1 otherwise.

    A scan that cannot read a test file also returns 1, with the file's
    ``path:line:col`` in the report, since no owner was checked.
    """
    args = _parser().parse_args(argv)
    try:
        baselines = baselines_under_test(repo_root())
    except MetadataLoadError as exc:
        # The tracker should say why no owner was checked, not only that
        # the run failed.
        report = (
            "The ratchet-baseline owner scan could not read a test file, so"
            f" no owner was checked (ARCH-18-004):\n\n- {exc}\n"
        )
    else:
        findings = owner_findings(baselines, issue_state)
        if not findings:
            owners = {o for b in baselines for o in b.owners}
            print(
                f"All {len(owners)} ratchet baseline owner issue(s) are open."
            )
            return 0
        report = report_markdown(findings)
    if args.report is not None:
        args.report.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
