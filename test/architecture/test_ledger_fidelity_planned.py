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
"""Planned behaviour recorded by the ledger-fidelity plan (#4425).

Every change the CASE_MANAGER makes to the case file is its own ledger entry,
and replicas copy the entries (ADR-0124, CLP-07-013).  Strict-``xfail`` tests
for the requirements the plan added or reworded before the code that satisfies
them exists.  Each flips to passing once the issue named in its reason lands;
see ``notes/spec-authoring-rules.md`` § "Never Raise the Ceiling — Use a
Strict ``xfail``".
"""

import inspect

import pytest

from test.architecture._ledger_commit_inventory import _COMMIT_BUILDERS
from test.architecture.test_ledger_event_types_are_replayed import (
    KNOWN_UNREPLAYED,
)
from vultron.core.behaviors.case import create_case_trigger_tree
from vultron.core.behaviors.sync.nodes import invite_accept_effect
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics as MS


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CLP-09-003")
@pytest.mark.xfail(
    strict=True,
    reason="CLP-07-013: the create-case trigger writes the case and its records with no entry. #4440.",
)
def test_create_case_trigger_commits_entries():
    source = inspect.getsource(create_case_trigger_tree)
    assert any(builder in source for builder in _COMMIT_BUILDERS)


@pytest.mark.spec("CM-11-006")
@pytest.mark.xfail(
    strict=True,
    reason="CM-11-006: the inert invitee's record has no entry of its own, so replicas cannot copy it. #4295.",
)
def test_stub_invite_record_is_replayed_from_its_own_entry():
    assert MS.INVITE_ACTOR_TO_CASE.value not in KNOWN_UNREPLAYED


@pytest.mark.spec("CM-23-016")
@pytest.mark.xfail(
    strict=True,
    reason="CM-23-016: the stub-Invite accept replay builds its own CaseParticipant. #4295.",
)
def test_replica_does_not_build_the_invitee_record_itself():
    assert "CaseParticipant(" not in inspect.getsource(invite_accept_effect)


@pytest.mark.spec("CLP-07-014")
@pytest.mark.xfail(
    strict=True,
    reason="CLP-07-014: recommendation_recommender_index is still a VulnerabilityCase field. #4444.",
)
def test_case_bookkeeping_is_not_a_case_field():
    assert (
        "recommendation_recommender_index"
        not in VulnerabilityCase.model_fields
    )
