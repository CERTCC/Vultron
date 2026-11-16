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
"""Refuse a pull request that closes a ratchet's owner while it is not empty.

Every non-empty ratchet baseline under ``test/`` names its owner with
``# owner: #N`` (ARCH-18-003). A pull request whose body says ``Closes #N``
closes that owner on merge, and the scheduled closed-owner report
(:mod:`vultron.metadata.ratchet_owners`, ARCH-18-004) only notices afterwards,
without failing the build (ARCH-18-009). This check runs on the pull request
instead (ARCH-18-012): it reads the body's closing references
(:func:`~vultron.metadata.planning.pr_body_lint.closing_references`) and the
markers at the checked-out head (:mod:`vultron.metadata.ratchet_markers`), and
fails when a closed issue still owns a baseline that is not at its terminal
value. A ``# permanent:`` marker never counts, and a ratchet the same pull
request empties no longer cites its owner.

It makes no network call: the workflow
(``.github/workflows/ratchet-owner-close-guard.yml``) writes the event's body to
a file. Only a closing reference in the body is read; an issue closed some other
way is still caught by the scheduled report.

Usage::

    ratchet-close-guard --body-file body.md
    ratchet-close-guard --body-file - --repo CERTCC/Vultron   # body on stdin

Exit codes: 0 = closes no owner still cited; 1 = it does; 2 = the body or a
test file could not be read.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.planning.gh import DEFAULT_REPO
from vultron.metadata.planning.pr_body_lint import closing_references
from vultron.metadata.ratchet_markers import Baseline
from vultron.metadata.ratchet_owners import baselines_under_test

#: The issue a closing reference names: ``#N``, ``owner/repo#N`` or an issue
#: URL, the last word of the reference.
_BARE = re.compile(r"#(\d+)")
_QUALIFIED = re.compile(r"([\w.-]+/[\w.-]+)#(\d+)")
_URL = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")


@dataclass(frozen=True)
class ClosedOwner:
    """An issue the pull request closes and the ratchets that still cite it."""

    owner: int
    baselines: tuple[Baseline, ...]

    def message(self) -> str:
        """The failure line, naming each baseline by path and constant."""
        cited = ", ".join(f"`{b.path}` `{b.name}`" for b in self.baselines)
        return (
            f"this PR closes #{self.owner}, but '# owner: #{self.owner}' still"
            f" cites it on {cited} (ARCH-18-012); empty the ratchet in this PR,"
            f" re-point its marker at the open issue that takes the work over,"
            f" or drop the closing reference"
        )


def _issue_in_repo(reference: str, repo: str) -> int | None:
    """The issue *reference* closes in *repo*, or ``None`` for another repo."""
    target = reference.rsplit(maxsplit=1)[-1]
    if bare := _BARE.fullmatch(target):
        return int(bare.group(1))
    for pattern in (_QUALIFIED, _URL):
        if found := pattern.fullmatch(target):
            same = found.group(1).lower() == repo.lower()
            return int(found.group(2)) if same else None
    return None  # pragma: no cover - closing_references matches only these


def closed_issues(body: str, repo: str) -> set[int]:
    """The issues in *repo* that a pull request with *body* closes on merge.

    The keywords are ``close``, ``fix`` and ``resolve`` in any tense and case
    (GitHub's list); a reference to another repository closes nothing here.
    """
    found = (_issue_in_repo(ref, repo) for ref in closing_references(body))
    return {n for n in found if n is not None and n > 0}


def closed_owners(
    closing: Iterable[int], baselines: Iterable[Baseline]
) -> list[ClosedOwner]:
    """Each issue in *closing* that a non-terminal baseline's owner cites.

    In issue order; a terminal baseline (empty, or a zero ceiling) holds no
    debt, so its leftover marker does not keep its owner open.
    """
    closing = set(closing)
    citing: dict[int, list[Baseline]] = {}
    for baseline in baselines:
        if baseline.terminal:
            continue
        for owner in dict.fromkeys(baseline.owners):
            if owner in closing:
                citing.setdefault(owner, []).append(baseline)
    return [
        ClosedOwner(owner, tuple(citing[owner])) for owner in sorted(citing)
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ratchet-close-guard",
        description=(
            "Fail when a pull request body closes an issue that an"
            " '# owner: #N' marker on a non-empty ratchet baseline under test/"
            " still cites (ARCH-18-012)."
        ),
    )
    parser.add_argument(
        "--body-file",
        required=True,
        help="the pull request body, or '-' to read it from stdin",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO,
        help="owner/name of the repository whose issues count"
        " (default: $GITHUB_REPOSITORY, else %(default)s)",
    )
    return parser


def _read_body(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: Sequence[str] | None = None, root: Path | None = None) -> int:
    """Run the check; see the module docstring for the exit codes."""
    args = _parser().parse_args(argv)
    try:
        body = _read_body(args.body_file)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"could not read the PR body: {exc}", file=sys.stderr)
        return 2
    closing = closed_issues(body, args.repo)
    if not closing:
        print("The PR body closes no issue, so it closes no ratchet owner.")
        return 0
    try:
        baselines = baselines_under_test(
            root if root is not None else repo_root()
        )
    except MetadataLoadError as exc:
        # A file skipped would leave its owners unchecked: never a pass.
        print(f"could not scan the ratchet baselines: {exc}", file=sys.stderr)
        return 2
    findings = closed_owners(closing, baselines)
    for finding in findings:
        print(finding.message(), file=sys.stderr)
    if findings:
        return 1
    shown = ", ".join(f"#{n}" for n in sorted(closing))
    print(
        f"No ratchet baseline still cites an issue this PR closes ({shown})."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
