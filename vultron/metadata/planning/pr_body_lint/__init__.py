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
"""``pr-body-lint``: the mechanical rules of ``pr-body-guide.md``, as a tool.

A Pull Request body is judged against
``.agents/skills/shared/pr-body-guide.md``. The rules there that need no
judgment — where the closing references sit, which sections exist, what form
the ``Docs:`` line takes — are checked here, each under a stable ID that the
guide lists (:data:`RULES`), so the guide and the tool stay one list
(PAD-20-001, PAD-20-006). ``create-pr`` runs it on the composed body before the
first push (PAD-20-002); ``pr-triage`` runs it first in its body phases and judges only
what it cannot check, such as whether the body's claims match the diff
(PAD-20-004, PAD-20-009).

Usage::

    pr-body-lint --body body.md                     # facts from the branch diff
    pr-body-lint --body body.md --stage final       # after check-docs-sync
    pr-body-lint --body - --manifest /tmp/m.txt     # body on stdin
    gh pr view 4710 --json body,baseRefName,headRefOid \
      | pr-body-lint --pr-json - --stage final      # an open PR's body

Two stages: ``pre-push`` (default) accepts the placeholders ``create-pr``
writes — ``Docs: pending check-docs-sync`` and ``<TODO>`` in ``## Spec
amended`` — and ``final`` refuses them (PD-03-013).

Like the rest of ``planning/``, the tool never calls GitHub itself: an open
PR's body, base branch and head commit arrive as the ``gh pr view`` JSON
payload on stdin (or in a file), so the rules stay testable without the
network. The changed files and the spec amendments are read from the local
checkout, which must be at the PR's head commit: GitHub's ``files`` list stops
at 100 entries, so a large PR's ``.py`` files may be missing from it.

Both stages read the branch as committed, from its merge base with the base
ref: an uncommitted or untracked file in the worktree is not part of the PR.

Exit codes: 0 = clean; 1 = findings; 2 = setup error (unreadable body,
payload or manifest, bad base ref, a checkout not at the PR's head, failed
``spec-amendments.sh`` call).

Requirements: specs/parallel-development.yaml PAD-20;
specs/project-documentation.yaml PD-03-008, PD-03-013, PD-03-014.

Submodules, by concern: ``rules`` (the rule table and the path sets the docs
rules judge), ``facts`` (gathering a PR's facts from git and ``gh``),
``checks`` (the per-rule checks and :func:`lint_body`) and ``cli`` (the
command line).
"""

from vultron.metadata.planning.pr_body_lint.checks import Finding, lint_body
from vultron.metadata.planning.pr_body_lint.cli import cli, main
from vultron.metadata.planning.pr_body_lint.facts import (
    BodyFacts,
    SetupError,
    amended_ids,
)
from vultron.metadata.planning.pr_body_lint.rules import (
    BODY_LIMIT,
    DOCS_PLACEHOLDER,
    MAINTAINER_DOC_FILES,
    MAINTAINER_DOC_PREFIXES,
    MANIFEST_LINES,
    RULES,
    RULES_BY_ID,
    TOOLING_FILES,
    TOOLING_PREFIXES,
    PrType,
    Rule,
    Stage,
    is_maintainer_doc,
    undocumented_tooling,
)

__all__ = [
    "BODY_LIMIT",
    "BodyFacts",
    "DOCS_PLACEHOLDER",
    "Finding",
    "MAINTAINER_DOC_FILES",
    "MAINTAINER_DOC_PREFIXES",
    "MANIFEST_LINES",
    "PrType",
    "RULES",
    "RULES_BY_ID",
    "Rule",
    "SetupError",
    "Stage",
    "TOOLING_FILES",
    "TOOLING_PREFIXES",
    "amended_ids",
    "cli",
    "is_maintainer_doc",
    "lint_body",
    "main",
    "undocumented_tooling",
]
