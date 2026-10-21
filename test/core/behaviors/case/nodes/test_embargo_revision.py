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

"""The creation-time revision relay (EP-04-011).

The shortest-wins loser registered at case creation is relayed like any other
revision (EP-04-011): one ``Invite(EmbargoEvent)`` to the party whose terms
won, from the CASE_MANAGER on the loser's behalf, under an id derived from the
proposal that created the case, and indexed only once it is sent.  The relay
runs in the creation act's one transaction (ADR-0146), so a failure rolls
back everything it wrote and nothing is kept for a later run.  These tests
pin the relay apart from the case-creation tree that places it.
"""

from collections.abc import Callable
from typing import cast

import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.case.nodes.revision_relay_fixtures import (
    CASE_ID,
    EMBARGO_ID,
    MANAGER,
    OWNER,
    REPORTER,
    index,
    invites,
    no_factory,
    relay,
    relayed_invite_id,
    seed,
)
from test.support.ledger import fail_commits
from vultron.core.behaviors.case.nodes import embargo_revision_relay
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent_semantic_types import (
    UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
)
from vultron.core.services.embargo_duration import EmbargoDurationSource
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)


def winner_row(scenario: BTTestScenario) -> EmbargoConsentState:
    """The reporter's (the winner's) row for the revision, as stored."""
    case = cast(VulnerabilityCase, scenario.dl.read(CASE_ID))
    record = scenario.dl.read(case.actor_participant_index[REPORTER])
    assert isinstance(record, CaseParticipant)
    return record.consent_for(EMBARGO_ID)


def proposal_entries(scenario: BTTestScenario) -> list[object]:
    """The ledger entries that record the relayed Invite."""
    invite_id = relayed_invite_id(REPORTER)
    return [
        e
        for e in scenario.dl.list_objects("CaseLedgerEntry")
        if getattr(e, "log_object_id", None) == invite_id
    ]


def assert_nothing_relayed(scenario: BTTestScenario) -> None:
    assert invites(scenario) == []
    assert proposal_entries(scenario) == []
    assert winner_row(scenario) is EmbargoConsentState.UNINVITED
    assert index(scenario) == {}


# --- RelayCreationTimeRevisionNode -------------------------------------------


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("EP-08-002")
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
    seed(bt_scenario)

    result = relay(bt_scenario, losing_source)

    bt_scenario.assert_success(result)
    (invite,) = invites(bt_scenario)
    assert invite.id_ == relayed_invite_id(winner)
    assert invite.to == [winner]
    assert invite.actor == MANAGER
    assert invite.attributed_to == loser
    # Indexed only now that it is sent, for the default selection (EP-08-002).
    assert index(bt_scenario) == {EMBARGO_ID: invite.id_}


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_relay_with_no_registration_in_its_act_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """A redelivery whose case was already created skips initialization, so
    no candidate is published; the open revision it finds on the case was
    relayed by the act that registered it."""
    seed(bt_scenario)

    result = relay(bt_scenario, None)

    bt_scenario.assert_success(result)
    assert_nothing_relayed(bt_scenario)


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_registered_revision_the_case_does_not_hold_open_raises(
    bt_scenario: BTTestScenario,
) -> None:
    """The act registered the revision, so a case without it open is the
    manager's own inconsistency: an internal error, never a silent SUCCESS."""
    seed(bt_scenario, open_proposal=False)

    result = relay(bt_scenario)

    bt_scenario.assert_failure(
        result, reason="holds no open proposal", allow_internal=True
    )
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("OX-06-002")
def test_the_same_creation_relays_under_the_same_id(
    bt_scenario: BTTestScenario,
) -> None:
    """The Invite's id is derived, never minted (ID-04-004): a relay that
    rolled back and runs again on the same case relays one Invite, under the
    id derived from the case proposal, the case, the revision and the
    invitee."""
    seed(bt_scenario)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            embargo_revision_relay,
            "record_embargo_proposal_index",
            _raise("index write failed"),
        )
        bt_scenario.assert_failure(
            relay(bt_scenario, in_act=True),
            reason="index write failed",
            allow_internal=True,
        )

    result = relay(bt_scenario, in_act=True)

    bt_scenario.assert_success(result)
    assert [a.id_ for a in invites(bt_scenario)] == [
        relayed_invite_id(REPORTER)
    ]


def _raise(message: str) -> Callable[..., None]:
    """A stand-in that raises *message*, for ``monkeypatch.setattr``."""

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError(message)

    return _fail


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("EP-08-002")
@pytest.mark.spec("CLP-07-015")
def test_a_failed_index_write_in_the_act_keeps_nothing(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The send, the winner's row and the index are one act (ADR-0146): a
    failed index write leaves no Invite queued or committed and no row
    moved."""
    seed(bt_scenario)
    monkeypatch.setattr(
        embargo_revision_relay,
        "record_embargo_proposal_index",
        _raise("index write failed"),
    )

    result = relay(bt_scenario, in_act=True)

    bt_scenario.assert_failure(
        result, reason="index write failed", allow_internal=True
    )
    assert_nothing_relayed(bt_scenario)


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("EP-09-004")
@pytest.mark.spec("CLP-07-015")
def test_a_failed_consent_commit_in_the_act_keeps_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """The relay's Invite, its queued receipt and the winner's consent row
    (its ``Update(EmbargoConsent)`` entry, ADR-0124) are one act: when the
    row's commit fails, none of them is kept."""
    seed(bt_scenario)
    with pytest.MonkeyPatch.context() as patch:
        fail_commits(
            patch,
            commit_tree,
            when=lambda kw: (
                kw["semantic_type"] == UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE
            ),
        )
        result = relay(bt_scenario, in_act=True)

    bt_scenario.assert_failure(
        result, reason="ledger commit failed", allow_internal=True
    )
    assert_nothing_relayed(bt_scenario)


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("CLP-07-015")
def test_a_failed_outbox_write_in_the_act_keeps_nothing(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The outbox write fails before the commit: nothing is committed."""
    seed(bt_scenario)
    monkeypatch.setattr(
        bt_scenario.dl, "outbox_append", _raise("outbox unavailable")
    )

    result = relay(bt_scenario, in_act=True)

    bt_scenario.assert_failure(
        result, reason="outbox unavailable", allow_internal=True
    )
    monkeypatch.undo()
    assert_nothing_relayed(bt_scenario)


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_missing_factory_fails_and_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    seed(bt_scenario)
    no_factory(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_failure(result)
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_report_naming_no_reporter_raises(
    bt_scenario: BTTestScenario,
) -> None:
    seed(bt_scenario, report_author=None)

    result = relay(bt_scenario)

    bt_scenario.assert_failure(
        result, reason="has no attributed_to", allow_internal=True
    )
    assert invites(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_case_naming_no_owner_raises(
    bt_scenario: BTTestScenario,
) -> None:
    seed(bt_scenario, owner=None)

    result = relay(bt_scenario)

    bt_scenario.assert_failure(
        result, reason="names no CASE_OWNER", allow_internal=True
    )
    assert invites(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_winner_who_is_not_a_recipient_raises_and_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """The relay is a MUST: a registered revision whose winner cannot be
    invited is an internal error, never a silent SUCCESS that relays nothing
    and never a refusal of the sender's already-accepted proposal."""
    seed(bt_scenario, report_author="https://example.org/actors/outsider")

    result = relay(bt_scenario)

    bt_scenario.assert_failure(
        result, reason="is not an invitation recipient", allow_internal=True
    )
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_an_owner_who_reported_to_itself_has_nobody_to_invite(
    bt_scenario: BTTestScenario,
) -> None:
    """Nothing is sent, so nothing is indexed: an index entry naming an
    Invite that never existed would be selected as the owner's default."""
    seed(bt_scenario, report_author=OWNER)

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}
