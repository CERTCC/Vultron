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
"""PR-only growth guard: no pull request adds a compound statement (MS-03-007).

The corpus holds a backlog of compound requirements, so the rule cannot fail
corpus-wide. ``spec-lint --changed-since`` holds it before a pull request's
first push; this guard holds it in CI, so a later fix commit cannot reword a
statement past it. Each item is a requirement's ID with its statement text, so
a statement added or reworded is new since the merge base. So is a compound
statement whose reasoned suppression the branch removes, which
``--changed-since`` does not check; a change to any other field is not new.
"""

from __future__ import annotations

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.growth_guard import added_since_base
from vultron.metadata.specs.statement_style import (
    unexcused_compound_statements,
)


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-03-007")
def test_no_pr_adds_a_compound_statement():
    """No compound statement in HEAD that the merge base lacks."""
    check = added_since_base(
        unexcused_compound_statements,
        repo_root=_corpus.REPO_ROOT,
        paths=("specs",),
    )
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.added, check.failure_message(
        "statement(s) with more than one RFC 2119 keyword",
        "Split each one: the original ID keeps the main obligation and each "
        "other one gets a new ID (notes/spec-authoring-rules.md § One "
        "Obligation per Requirement). Quote a keyword you only name in "
        "backticks, or add lint_suppress: [compound_statement] with the "
        "reason in a YAML comment (MS-03-007).",
    )
