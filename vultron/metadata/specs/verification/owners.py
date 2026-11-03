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
"""GitHub checks on ``verification_debt`` owner issues and on a PR that closes
one (MS-10-006).
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from collections.abc import Callable, Iterable, Mapping

from vultron.metadata.base import (
    GH_LOOKUP_ERRORS,
    gh_issue_state,
    gh_lookup_failure as _lookup_failure,
    issue_number,
)
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import SpecKind
from vultron.metadata.specs.verification.debt import marked_specs


def debt_owner_refs(
    registry: SpecRegistry,
    owners: Mapping[SpecKind, frozenset[str]],
) -> set[str]:
    """Every issue a marker or an owner-table entry names."""
    refs = {ref for kind_owners in owners.values() for ref in kind_owners}
    refs.update(marker for _id, _spec, marker in marked_specs(registry))
    return refs


def closed_debt_owners(
    refs: Iterable[str],
    issue_state: Callable[[str], str] | None = None,
) -> list[str]:
    """Hard errors for every ref whose issue is closed or cannot be read.

    A lookup failure is an error, not a pass: a check that cannot see the
    issue has not shown it is open. *issue_state* defaults to
    :func:`gh_issue_state`.
    """
    if issue_state is None:
        issue_state = gh_issue_state
    errors: list[str] = []
    for ref in sorted(refs, key=issue_number):
        try:
            state = issue_state(ref)
        except GH_LOOKUP_ERRORS as exc:
            errors.append(
                f"verification_debt owner {ref}: could not read its state "
                f"({_lookup_failure(exc)}); the open-owner check needs gh and "
                f"a token"
            )
            continue
        if state.upper() != "OPEN":
            errors.append(
                f"verification_debt owner {ref} is {state.upper()}: an "
                f"unverified requirement must name an open owning issue "
                f"(MS-10-006); verify the items that cite it, or re-point "
                f"them and the owner table at the issue that took the work over"
            )
    return errors


def gh_pr_closing_issues(pr_number: int) -> set[str]:
    """The issues pull request *pr_number* closes on merge, as ``#N`` refs.

    Read from GitHub's ``closingIssuesReferences`` (the ``Closes #N`` keywords
    in the PR body, plus manually linked issues). Only issues in the PR's own
    repository count: ``Fixes Other/Repo#N`` closes no owner here. A closing
    keyword in a commit message is not in that list, so a PR that closes an
    owner only that way passes; the scheduled ``--check-debt-owners`` run
    reports the closed owner after merge. Needs ``gh`` and a token; raises
    one of :data:`~vultron.metadata.base.GH_LOOKUP_ERRORS` when the lookup
    cannot be made.
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "closingIssuesReferences,url",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    repo_prefix = payload["url"].split("/pull/")[0] + "/issues/"
    return {
        f"#{ref['number']}"
        for ref in payload["closingIssuesReferences"]
        if ref["url"].startswith(repo_prefix)
    }


def closing_pr_problems(
    registry: SpecRegistry,
    owners: Mapping[SpecKind, frozenset[str]],
    closing: Iterable[str],
) -> list[str]:
    """Hard errors for a PR that closes an owner issue still in use (MS-10-006).

    *closing* is the set of issues the PR closes. An owner may close only once
    no marker names it and it is gone from the owner table — so the backfill
    PR that finishes an owner's work also removes the entry (MS-10-007).
    """
    marked = Counter(marker for _id, _spec, marker in marked_specs(registry))
    tabled = {ref for kind_owners in owners.values() for ref in kind_owners}
    errors: list[str] = []
    for ref in sorted(set(closing), key=issue_number):
        if marked.get(ref):
            errors.append(
                f"this PR closes {ref}, but {marked[ref]} requirement(s) still "
                f"carry verification_debt: '{ref}' (MS-10-006); verify them, "
                f"or drop the closing reference — `spec-lint "
                f"--list-unverified` names them"
            )
        elif ref in tabled:
            errors.append(
                f"this PR closes {ref}, which no marker names any more; remove "
                f"it from VERIFICATION_DEBT_OWNERS in this PR (MS-10-007)"
            )
    return errors


def check_closing_pr(
    registry: SpecRegistry,
    owners: Mapping[SpecKind, frozenset[str]],
    pr_number: int,
    closing_issues: Callable[[int], set[str]] | None = None,
) -> list[str]:
    """The ``--check-closing-pr`` hard errors for pull request *pr_number*.

    A lookup failure is an error: a check that cannot see what the PR closes
    has not shown it closes no owner. *closing_issues* defaults to
    :func:`gh_pr_closing_issues`.
    """
    if closing_issues is None:
        closing_issues = gh_pr_closing_issues
    try:
        closing = closing_issues(pr_number)
    except GH_LOOKUP_ERRORS as exc:
        return [
            f"could not read the issues PR #{pr_number} closes "
            f"({_lookup_failure(exc)}); the closing-PR check needs gh and a "
            f"token"
        ]
    return closing_pr_problems(registry, owners, closing)
