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
"""Per-requirement ``verification_debt`` markers on unverified MUST-tier items.

MS-10-003 obliges every ``MUST`` and ``MUST_NOT`` requirement to carry a
``verification:`` field. Until the backlog is worked down, each requirement
that still lacks one carries ``verification_debt: '#N'`` instead, naming the
issue that owns verifying it (MS-10-006). The rule is checked one requirement
at a time, so there is no committed count for two concurrent PRs to race on
(#3984): two PRs conflict only when they edit the same requirement.

Per requirement, ``spec-lint`` fails when:

- a MUST-tier item has neither ``verification:`` nor a marker;
- an item has both (the marker is stale — delete it);
- a marker sits on an item below the MUST tier;
- a marker names an issue that does not own the item's kind in
  :data:`VERIFICATION_DEBT_OWNERS`. That covers a relabel that kept the old
  kind's marker (MS-10-008) and a marker on a kind whose backlog is finished
  and whose entry is gone (MS-10-026).

The owner table holds issue references only, never counts, so nothing in it
moves when a requirement is verified. ``spec-lint`` prints one summary line
per kind computed from the markers (MS-10-005, MS-10-019).

The per-item rule cannot by itself stop a new unverified MUST from arriving
with a marker on it. The PR-only growth guard
(``test/architecture/test_verification_debt_guard.py``, MS-10-016) does: it
compares :func:`debt_snapshot` at the merge base with the working tree and
fails on any marker the branch added (:func:`added_debt`). An item is a
requirement's ID with its marker, so a marker re-pointed at another issue — a
relabel that swaps in the destination kind's owner (MS-10-008) — is an addition
too, while a removed marker, or one that moves with its requirement to another
file, is not. Nor is the marker of a new ID split off a marked requirement
(MS-03-001): the new ID names that requirement in its ``relationships:`` and
carries the same marker, so the split moves debt without adding any. A
requirement with no marker has no debt to move, so a new ID split off it gets
no exemption: the split gives that ID a ``verification:`` check instead.

An owner is checked against GitHub at two points, both in
``.github/workflows/verification-debt-owners.yml`` (MS-10-006):

- ``spec-lint --check-closing-pr N`` fails pull request *N* when it closes an
  owner issue that a marker or the owner table still names. Closing the owner
  is that PR's own act, so failing it races no other PR.
- ``spec-lint --check-debt-owners`` reports every marker or table entry naming
  a closed issue. CI runs it each weekday morning and on each push to ``main``
  and files one tracking issue rather than failing the build: an issue closed by
  hand is caused by no PR, so failing would turn every PR in flight red
  (ARCH-18-009).

Runnable locally::

    spec-lint                         # one summary line per kind
    spec-lint --list-unverified       # plus the marked IDs
    spec-lint --check-debt-owners     # plus the open-owner check (needs gh)
    spec-lint --check-closing-pr 123  # plus the closing-PR check (needs gh)

Requirements: specs/meta-specifications.yaml MS-10-003, MS-10-005 through
MS-10-008, MS-10-016; specs/architecture.yaml ARCH-18-004.

Submodules, by concern: ``debt`` (the owner table, the markers and the
branch growth guard's snapshot), ``coverage`` (the per-item verification
checks and summary lines ``spec-lint`` prints) and ``owners`` (the GitHub
checks on owner issues and closing PRs).
"""

from vultron.metadata.specs.verification.coverage import (
    check_verification_coverage,
    idle_owners,
    listing_lines,
    summary_line,
    verification_problems,
)
from vultron.metadata.specs.verification.debt import (
    VERIFICATION_DEBT_OWNERS,
    DebtReport,
    DebtSnapshot,
    added_debt,
    debt_added_since_base,
    debt_by_kind,
    debt_snapshot,
    marked_specs,
    owes_verification,
    owns_kind,
)
from vultron.metadata.specs.verification.owners import (
    check_closing_pr,
    closed_debt_owners,
    closing_pr_problems,
    debt_owner_refs,
    gh_pr_closing_issues,
)

__all__ = [
    "DebtReport",
    "DebtSnapshot",
    "VERIFICATION_DEBT_OWNERS",
    "added_debt",
    "check_closing_pr",
    "check_verification_coverage",
    "closed_debt_owners",
    "closing_pr_problems",
    "debt_added_since_base",
    "debt_by_kind",
    "debt_owner_refs",
    "debt_snapshot",
    "gh_pr_closing_issues",
    "idle_owners",
    "listing_lines",
    "marked_specs",
    "owes_verification",
    "owns_kind",
    "summary_line",
    "verification_problems",
]
