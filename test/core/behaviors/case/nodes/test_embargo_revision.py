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

"""The creation-time revision relay and its durable obligation (EP-04-011).

The shortest-wins loser registered at case creation is relayed like any other
revision (EP-04-011): one ``Invite(EmbargoEvent)`` to the party whose terms
won, from the CASE_MANAGER on the loser's behalf, under the id the
registration minted, and indexed only once it is sent.  The obligation is a
``PendingCreationTimeRevisionRelay`` marker, so a relay that fails is retried
by the next run rather than lost (#4121).  These tests pin the marker writer
and the relay's guards — what it relays, indexes and discharges, and when it
keeps the obligation — apart from the case-creation tree that places them.
"""

from datetime import datetime

import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.case.nodes.revision_relay_fixtures import (
    CASE_ID,
    EMBARGO_ID,
    MANAGER,
    OWNER,
    PROPOSAL_ID,
    REPORTER,
    index,
    invites,
    marker,
    no_factory,
    owe,
    owed,
    record,
    relay,
    revision,
    seed,
)
from vultron.core.behaviors.case.nodes import embargo_revision_relay
from vultron.core.behaviors.case.nodes.embargo_revision_relay import (
    RelayCreationTimeRevisionNode,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.embargo_duration import EmbargoDurationSource

# --- RecordCreationTimeRevisionRelayNode -------------------------------------


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.parametrize(
    "losing_source",
    [
        EmbargoDurationSource.ACTOR_DEFAULT,
        EmbargoDurationSource.SENDER_PROPOSAL,
    ],
)
def test_a_registered_revision_is_recorded_as_owed(
    bt_scenario: BTTestScenario, losing_source: EmbargoDurationSource
) -> None:
    seed(bt_scenario)

    result = record(bt_scenario, revision(losing_source))

    bt_scenario.assert_success(result)
    assert owed(bt_scenario) == marker(losing_source)


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_no_registered_revision_records_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    seed(bt_scenario)

    result = record(bt_scenario, None)

    bt_scenario.assert_success(result)
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_revision_published_for_another_case_records_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """A value a previous run left on the process-global blackboard is not
    this case's revision (BT-17-003)."""
    seed(bt_scenario)

    result = record(
        bt_scenario, revision(case_id="https://example.org/cases/other")
    )

    bt_scenario.assert_success(result)
    assert (
        bt_scenario.dl.list_objects("PendingCreationTimeRevisionRelay") == []
    )


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
    owe(bt_scenario, losing_source)

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    (invite,) = invites(bt_scenario)
    assert invite.id_ == PROPOSAL_ID
    assert invite.to == [winner]
    assert invite.actor == MANAGER
    assert invite.attributed_to == loser
    # Indexed only now that it is sent, for the default selection (EP-08-002).
    assert index(bt_scenario) == {EMBARGO_ID: PROPOSAL_ID}
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_the_startup_runner_form_relays_the_named_case(
    bt_scenario: BTTestScenario,
) -> None:
    """With *case_id* passed in, the relay needs nothing on the blackboard."""
    seed(bt_scenario)
    owe(bt_scenario)

    result = relay(bt_scenario, case_id=CASE_ID)

    bt_scenario.assert_success(result)
    (invite,) = invites(bt_scenario)
    assert invite.id_ == PROPOSAL_ID
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_nothing_owed_relays_nothing(bt_scenario: BTTestScenario) -> None:
    seed(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_revision_no_longer_open_is_discharged_unsent(
    bt_scenario: BTTestScenario,
) -> None:
    seed(bt_scenario, open_proposal=False)
    owe(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_revision_already_in_the_ledger_is_not_relayed_again(
    bt_scenario: BTTestScenario,
) -> None:
    """The guard reads the ledger, so an obligation that survived a completed
    send sends no second Invite."""
    seed(bt_scenario)
    owe(bt_scenario)
    bt_scenario.assert_success(relay(bt_scenario))
    while bt_scenario.dl.outbox_pop() is not None:
        pass
    owe(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    assert invites(bt_scenario) == []
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("EP-08-002")
def test_an_invite_committed_but_never_indexed_is_indexed_on_retry(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relay that committed its Invite and then failed left no index entry;
    the retry writes it without sending a second Invite (#4121)."""
    seed(bt_scenario)
    owe(bt_scenario)

    def _fail(*_args: object, **_kwargs: object) -> bool:
        raise RuntimeError("index write failed")

    monkeypatch.setattr(
        embargo_revision_relay, "record_embargo_proposal_index", _fail
    )
    bt_scenario.assert_failure(
        relay(bt_scenario), reason="index write failed", allow_internal=True
    )
    assert index(bt_scenario) == {}
    assert owed(bt_scenario) is not None
    monkeypatch.undo()
    while bt_scenario.dl.outbox_pop() is not None:
        pass

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {EMBARGO_ID: PROPOSAL_ID}
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_failed_relay_keeps_the_obligation_and_a_retry_completes_it(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failure #4121 is about: the obligation survives, and the next run
    sends the Invite and indexes it."""
    seed(bt_scenario)
    owe(bt_scenario)
    monkeypatch.setattr(
        embargo_revision_relay,
        "invitation_recipients",
        lambda *_args, **_kwargs: [],
    )
    bt_scenario.assert_failure(
        relay(bt_scenario),
        reason="is not an invitation recipient",
        allow_internal=True,
    )
    assert owed(bt_scenario) == marker()
    monkeypatch.undo()

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    (invite,) = invites(bt_scenario)
    assert invite.id_ == PROPOSAL_ID
    assert index(bt_scenario) == {EMBARGO_ID: PROPOSAL_ID}
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_missing_factory_fails_and_keeps_the_obligation(
    bt_scenario: BTTestScenario,
) -> None:
    seed(bt_scenario)
    owe(bt_scenario)
    no_factory(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_failure(result)
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}
    assert owed(bt_scenario) == marker()


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_report_naming_no_reporter_raises_and_keeps_the_obligation(
    bt_scenario: BTTestScenario,
) -> None:
    seed(bt_scenario, report_author=None)
    owe(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_failure(
        result, reason="has no attributed_to", allow_internal=True
    )
    assert invites(bt_scenario) == []
    assert owed(bt_scenario) is not None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_revision_with_no_report_is_refused_at_the_writer(
    bt_scenario: BTTestScenario,
) -> None:
    """No relay could ever be sent for it, so recording it would only fail at
    every retry (ARCH-10-001): the writer raises as an internal error."""
    seed(bt_scenario)

    result = record(bt_scenario, revision(), report_id=None)

    bt_scenario.assert_failure(
        result, reason="has no report", allow_internal=True
    )
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_store_fault_writing_the_obligation_is_an_internal_error(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed(bt_scenario)

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(bt_scenario.dl, "save", _fail)

    result = record(bt_scenario, revision())

    bt_scenario.assert_failure(
        result, reason="store unavailable", allow_internal=True
    )


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("CM-14-007")
@pytest.mark.spec("CM-14-011")
@pytest.mark.parametrize("named", [False, True], ids=["tree", "runner"])
def test_a_case_whose_creation_entries_are_not_committed_relays_nothing_yet(
    bt_scenario: BTTestScenario, named: bool
) -> None:
    """A case tree that failed before its ledger commit leaves the obligation
    with no genesis entry.  Relaying then would fan the Invite out ahead of
    the case's creation, so nothing is sent and the obligation is kept for a
    later run."""
    seed(bt_scenario, created=False)
    owe(bt_scenario)

    result = relay(bt_scenario, case_id=CASE_ID if named else None)

    bt_scenario.assert_success(result)
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}
    assert bt_scenario.dl.list_objects("CaseLedgerEntry") == []
    assert owed(bt_scenario) == marker()


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("EP-09-004")
def test_an_invite_committed_before_its_consent_write_is_completed_on_retry(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relay that committed and queued its Invite and then failed applying
    the winner's PEC INVITE: the retry applies it, without a second Invite."""
    seed(bt_scenario)
    owe(bt_scenario)
    invite_where_legal = RelayCreationTimeRevisionNode._invite_where_legal

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("consent write failed")

    monkeypatch.setattr(
        RelayCreationTimeRevisionNode, "_invite_where_legal", _fail
    )
    bt_scenario.assert_failure(
        relay(bt_scenario), reason="consent write failed", allow_internal=True
    )
    while bt_scenario.dl.outbox_pop() is not None:
        pass
    applied: list[str] = []

    def _spy(
        self: RelayCreationTimeRevisionNode,
        dl: CaseOutboxPersistence,
        recipient_id: str,
        deadline: datetime | None,
    ) -> None:
        applied.append(recipient_id)
        invite_where_legal(self, dl, recipient_id, deadline)

    monkeypatch.setattr(
        RelayCreationTimeRevisionNode, "_invite_where_legal", _spy
    )

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    assert invites(bt_scenario) == []
    assert applied == [REPORTER]
    assert index(bt_scenario) == {EMBARGO_ID: PROPOSAL_ID}
    assert owed(bt_scenario) is None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_case_naming_no_owner_raises_and_keeps_the_obligation(
    bt_scenario: BTTestScenario,
) -> None:
    seed(bt_scenario, owner=None)
    owe(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_failure(
        result, reason="names no CASE_OWNER", allow_internal=True
    )
    assert invites(bt_scenario) == []
    assert owed(bt_scenario) is not None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_a_winner_who_is_not_a_recipient_raises_and_relays_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """The relay is a MUST: a registered revision whose winner cannot be
    invited is an internal error, never a silent SUCCESS that relays nothing
    and never a refusal of the sender's already-accepted proposal."""
    seed(bt_scenario, report_author="https://example.org/actors/outsider")
    owe(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_failure(
        result, reason="is not an invitation recipient", allow_internal=True
    )
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}
    assert owed(bt_scenario) is not None


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-04-011")
def test_an_owner_who_reported_to_itself_has_nobody_to_invite(
    bt_scenario: BTTestScenario,
) -> None:
    """Nothing is sent, so nothing is indexed: an index entry naming an
    Invite that never existed would be selected as the owner's default.  The
    obligation is discharged, since no retry could ever send anything."""
    seed(bt_scenario, report_author=OWNER)
    owe(bt_scenario)

    result = relay(bt_scenario)

    bt_scenario.assert_success(result)
    assert invites(bt_scenario) == []
    assert index(bt_scenario) == {}
    assert owed(bt_scenario) is None
