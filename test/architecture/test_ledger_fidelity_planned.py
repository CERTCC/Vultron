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
"""Planned behaviour recorded by the ledger-fidelity plan (#4425).

Every change the CASE_MANAGER makes to the case file is its own ledger entry,
and replicas copy the entries (ADR-0124, CLP-07-013).  Strict-``xfail`` tests
for the requirements the plan added or reworded before the code that satisfies
them exists.  Each strict xfail fails once the issue named in its reason
lands, prompting its removal; see ``notes/spec-authoring-rules.md`` § "Use a Strict ``xfail`` for
Not-Yet-Implemented Specs".
"""

import pytest

from test.architecture._ledger_commit_inventory import (
    received_commit_semantics,
)
from vultron.core.models.case import VulnerabilityCase


@pytest.mark.spec("CLP-07-014")
def test_case_bookkeeping_is_not_a_case_field():
    assert (
        "recommendation_recommender_index"
        not in VulnerabilityCase.model_fields
    )


@pytest.mark.spec("CM-21-012")
@pytest.mark.spec("CLP-02-012")
def test_ownership_transfer_reject_commits_an_entry():
    assert "reject_case_ownership_transfer" in received_commit_semantics()


@pytest.mark.spec("CM-21-015")
def test_ownership_transfer_withdrawal_commits_an_entry():
    assert "undo_case_ownership_transfer" in received_commit_semantics()
