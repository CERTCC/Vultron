#!/usr/bin/env python

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

"""The relay of the creation-time revision (``RelayCreationTimeRevisionNode``).

The shortest-wins loser registered at case creation is relayed like any other
revision (EP-04-011): one ``Invite(EmbargoEvent)`` to the party whose terms
won, from the CASE_MANAGER on the loser's behalf, under the id the
registration minted, and indexed only once it is sent.  These tests pin the
node's guards — what it relays and indexes, and when it does neither — apart
from the case-creation tree that places it.
"""

from typing import cast

import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.behaviors.case.nodes.embargo_revision import (
    CreationTimeRevision,
)
from vultron.core.behaviors.case.nodes.embargo_revision_relay import (
    RelayCreationTimeRevisionNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.report import VulnerabilityReport
from vultron.core.services.embargo_duration import EmbargoDurationSource
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (  # noqa: F401
    as_VulnerabilityReport,
)

CASE_ID = "https://example.org/cases/creation-revision"
EMBARGO_ID = f"{CASE_ID}/embargo_events/revision"
PROPOSAL_ID = "urn:uuid:creation-time-revision-invite"
REPORT_ID = "https://example.org/reports/creation-revision"
MANAGER = "https://example.org/actors/case-actor"
OWNER = "https://example.org/actors/owner"
REPORTER = "https://example.org/actors/reporter"


def _participant(actor_id: str, role: CVDRole) -> CaseParticipant:
    return CaseParticipant(
        id_=f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=[role],
    )


def _seed(
    scenario: BTTestScenario,
    *,
    open_proposal: bool = True,
    report_author: str | None = REPORTER,
    owner: str | None = OWNER,
) -> None:
    """A REVISE case owned by OWNER, managed by MANAGER, reported by REPORTER."""
    records = [
        _participant(MANAGER, CVDRole.CASE_MANAGER),
        _participant(OWNER, CVDRole.VENDOR),
        _participant(REPORTER, CVDRole.FINDER),
    ]
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="Creation-time revision",
        attributed_to=OWNER,
        case_participants=[p.id_ for p in records],
        actor_participant_index={
            cast(str, p.attributed_to): p.id_ for p in records
        },
        proposed_embargoes=[EMBARGO_ID] if open_proposal else [],
    )
    case.append_case_status(em_state=EM.REVISE)
    # A case only materializes status with an owner, so an ownerless case is
    # one whose record lost it after construction (assignment skips checks).
    case.attributed_to = owner
    embargo = as_EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(60)
    )
    report = VulnerabilityReport(id_=REPORT_ID, attributed_to=report_author)
    scenario.seed(*records, case, embargo, report)


def _revision(
    losing_source: EmbargoDurationSource = EmbargoDurationSource.ACTOR_DEFAULT,
    case_id: str = CASE_ID,
) -> CreationTimeRevision:
    return CreationTimeRevision(
        case_id=case_id,
        embargo_id=EMBARGO_ID,
        proposal_id=PROPOSAL_ID,
        losing_source=losing_source,
    )


def _relay(
    scenario: BTTestScenario, revision: CreationTimeRevision | None
) -> BTExecutionResult:
    return scenario.run(
        RelayCreationTimeRevisionNode(report_id=REPORT_ID),
        case_id=CASE_ID,
        creation_time_revision=revision,
    )


def _invites(scenario: BTTestScenario) -> list[VultronActivity]:
    return [
        a
        for a in (
            cast(VultronActivity, scenario.dl.read(i))
            for i in scenario.dl.outbox_list()
        )
        if a.type_ == "Invite"
    ]


def _index(scenario: BTTestScenario) -> dict[str, str]:
    case = scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return dict(case.pending_embargo_proposal_index)


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("CM-24-001")
@pytest.mark.spec("CM-24-002")
@pytest.mark.parametrize(
    ("losing_source", "loser", "winner"),
    [
        (EmbargoDurationSource.ACTOR_DEFAULT, OWNER, REPORTER),
        (EmbargoDurationSource.SENDER_PROPOSAL, REPORTER, OWNER),
    ],
    ids=["owner-lost", "reporter-lost"],
)
def test_the_winner_alone_is_invited_on_the_losers_behalf(
    bt_scenario: BTTestScenario,
    losing_source: EmbargoDurationSource,
    loser: str,
    winner: str,
) -> None:
    _seed(bt_scenario)

    result = _relay(bt_scenario, _revision(losing_source))

    bt_scenario.assert_success(result)
    (invite,) = _invites(bt_scenario)
    assert invite.id_ == PROPOSAL_ID
    assert invite.to == [winner]
    assert invite.actor == MANAGER
    assert invite.attributed_to == loser
    # Indexed only now that it is sent, for the default selection (EP-08-002).
    assert _index(bt_scenario) == {EMBARGO_ID: PROPOSAL_ID}


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_no_registered_revision_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    _seed(bt_scenario)

    result = _relay(bt_scenario, None)

    bt_scenario.assert_success(result)
    assert _invites(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_revision_published_for_another_case_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """A value a previous run left on the process-global blackboard is not
    this case's revision (BT-17-003)."""
    _seed(bt_scenario)

    result = _relay(
        bt_scenario, _revision(case_id="https://example.org/cases/other")
    )

    bt_scenario.assert_success(result)
    assert _invites(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_revision_no_longer_open_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    _seed(bt_scenario, open_proposal=False)

    result = _relay(bt_scenario, _revision())

    bt_scenario.assert_success(result)
    assert _invites(bt_scenario) == []
    assert _index(bt_scenario) == {}


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_revision_already_in_the_ledger_is_not_relayed_again(
    bt_scenario: BTTestScenario,
) -> None:
    """The guard reads the ledger, not the blackboard, so a retry after a
    completed relay sends no second Invite."""
    _seed(bt_scenario)
    bt_scenario.assert_success(_relay(bt_scenario, _revision()))
    while bt_scenario.dl.outbox_pop() is not None:
        pass

    result = _relay(bt_scenario, _revision())

    bt_scenario.assert_success(result)
    assert _invites(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_report_naming_no_reporter_raises_and_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    _seed(bt_scenario, report_author=None)

    result = _relay(bt_scenario, _revision())

    bt_scenario.assert_failure(
        result, reason="has no attributed_to", allow_internal=True
    )
    assert _invites(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_case_naming_no_owner_raises_and_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    _seed(bt_scenario, owner=None)

    result = _relay(bt_scenario, _revision())

    bt_scenario.assert_failure(
        result, reason="names no CASE_OWNER", allow_internal=True
    )
    assert _invites(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_winner_who_is_not_a_recipient_raises_and_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """The relay is a MUST: a registered revision whose winner cannot be
    invited is an internal error, never a silent SUCCESS that relays nothing
    and never a refusal of the sender's already-accepted proposal."""
    _seed(bt_scenario, report_author="https://example.org/actors/outsider")

    result = _relay(bt_scenario, _revision())

    bt_scenario.assert_failure(
        result, reason="is not an invitation recipient", allow_internal=True
    )
    assert _invites(bt_scenario) == []
    assert _index(bt_scenario) == {}


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_an_owner_who_reported_to_itself_has_nobody_to_invite(
    bt_scenario: BTTestScenario,
) -> None:
    """Nothing is sent, so nothing is indexed: an index entry naming an
    Invite that never existed would be selected as the owner's default."""
    _seed(bt_scenario, report_author=OWNER)

    result = _relay(bt_scenario, _revision())

    bt_scenario.assert_success(result)
    assert _invites(bt_scenario) == []
    assert _index(bt_scenario) == {}
