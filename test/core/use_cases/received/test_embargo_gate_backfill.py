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
"""The embargo gate backfills withheld ledger entries on admission (CM-10-006).

A participant outside the CM-10-004 gate is sent no ledger entry. When it is
admitted -- it accepts the active embargo (on time, or by a late Accept the
CASE_MANAGER honors, EMB-17-001), or the embargo ends -- every entry withheld
from it goes out in log order, the admitting entry included.
"""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from py_trees.common import Status

from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.embargo import SvcTerminateEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    TerminateEmbargoTriggerRequest,
)
from vultron.wire.as2.factories import (
    add_embargo_to_case_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import make_embargo_case_with_actor

MANAGER_ID = "https://example.org/actors/coordinator"
SIGNATORY_IDS = (
    "https://example.org/actors/vendor",
    "https://example.org/actors/deployer",
)
NON_SIGNATORY_ID = "https://example.org/actors/finder"
CASE_ID = "https://example.org/cases/fanout-backfill"


class _GateScenario:
    """A case under an active embargo that only the finder has not accepted."""

    def __init__(self, make_payload) -> None:
        self._make_payload = make_payload
        self.dl, _, case, embargo = make_embargo_case_with_actor(
            CASE_ID,
            MANAGER_ID,
            extra_participants=[*SIGNATORY_IDS, NON_SIGNATORY_ID],
            case_manager_actor_id=MANAGER_ID,
        )
        stored = cast(VulnerabilityCase, self.dl.read(case.id_))
        # The shared fixture indexes the extra participants without listing
        # them in ``case_participants``; the activation consent cascade walks
        # that list (EP-05-001), so seat every indexed record on it.
        for participant_id in stored.actor_participant_index.values():
            if participant_id not in stored.case_participants:
                stored.case_participants.append(participant_id)
        stored.current_status.em.state = EM.ACTIVE
        stored.set_embargo(embargo.id_)
        stored.proposed_embargoes.append(embargo.id_)
        self.dl.save(stored)
        self.embargo = embargo

    def _invite_to(self, actor_id: str):
        """The Invite the CASE_MANAGER relayed to *actor_id* alone (EP-09-010)."""
        invite = em_propose_embargo_activity(
            self.embargo,
            context=CASE_ID,
            actor=MANAGER_ID,
            to=[actor_id],
            id_=f"{CASE_ID}/embargo_invites/{actor_id.rsplit('/', 1)[-1]}",
        )
        if self.dl.read(invite.id_) is None:
            self.dl.create(invite)
        return invite

    def receive_accept(self, actor_id: str) -> None:
        accept = em_accept_embargo_activity(
            self._invite_to(actor_id),
            context=CASE_ID,
            actor=actor_id,
            to=[MANAGER_ID],
        )
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            self.dl,
            self._make_payload(accept, receiving_actor_id=MANAGER_ID),
            sync_port=SyncActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    def receive_remove(self) -> None:
        """The CASE_MANAGER receives the embargo's termination (EM -> EXITED)."""
        remove = remove_embargo_from_case_activity(
            self.embargo, origin=CASE_ID, actor=MANAGER_ID
        )
        RemoveEmbargoEventFromCaseReceivedUseCase(
            self.dl,
            self._make_payload(remove, receiving_actor_id=MANAGER_ID),
            sync_port=SyncActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    def receive_revision_accepted_by(self, actor_id: str) -> None:
        """Activate a shorter revision that *actor_id* had already accepted.

        The case is in REVISE with the revision proposed, and *actor_id*'s
        participant lists the revision, so the CASE_MANAGER's receipt of the
        owner's ``Add(EmbargoEvent)`` admits it (CM-10-004). The revision ends
        sooner than the active terms, so the signatories carry over by
        containment and stay admitted (EP-05-001).
        """
        revision = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e2",
            content="Shorter revision",
            context=CASE_ID,
            end_time=days_from_now_utc(30),
        )
        self.dl.create(revision)
        stored = cast(VulnerabilityCase, self.dl.read(CASE_ID))
        stored.current_status.em.state = EM.REVISE
        stored.proposed_embargoes.append(revision.id_)
        self.dl.save(stored)
        participant = self.dl.read(
            f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}"
        )
        assert isinstance(participant, CaseParticipant)
        participant.accepted_embargo_ids = [
            *participant.accepted_embargo_ids,
            revision.id_,
        ]
        self.dl.save(participant)

        activation = add_embargo_to_case_activity(
            revision, target=CASE_ID, actor=MANAGER_ID
        )
        AddEmbargoEventToCaseReceivedUseCase(
            self.dl,
            self._make_payload(activation, receiving_actor_id=MANAGER_ID),
            sync_port=SyncActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    def trigger_terminate(self) -> None:
        """The CASE_MANAGER terminates the embargo through its trigger."""
        self.dl.create(VultronOrganization(id_=MANAGER_ID, name="Coordinator"))
        SvcTerminateEmbargoUseCase(
            self.dl,
            TerminateEmbargoTriggerRequest(
                actor_id=MANAGER_ID, case_id=CASE_ID
            ),
            trigger_activity=TriggerActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(self.dl),
        ).execute()

    def cascade_terminate(self) -> None:
        """Run the shared terminate tree as a CS.P/X/A or threat cascade does.

        The cascade passes no activity builder, so the terminate notice comes
        from the blackboard's trigger factory.
        """
        sync_port = SyncActivityAdapter(self.dl)
        result = BTBridge(
            datalayer=self.dl,
            trigger_activity=TriggerActivityAdapter(self.dl),
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
        ).execute_with_setup(
            tree=terminate_embargo_bt(case_id=CASE_ID, result_out={}),
            actor_id=MANAGER_ID,
            sync_port=sync_port,
        )
        assert result.status == Status.SUCCESS, result.feedback_message

    def lapse_invite(self, actor_id: str) -> None:
        """Let *actor_id*'s invite pass its RSVP deadline unanswered."""
        participant = self.dl.read(
            f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}"
        )
        assert isinstance(participant, CaseParticipant)
        participant.embargo_consent_state = PEC.INVITED
        participant.invite_rsvp_deadline = datetime.now(tz=UTC) - timedelta(
            days=1
        )
        self.dl.save(participant)

    def ledger(self) -> list[CaseLedgerEntry]:
        entries = [
            e
            for e in self.dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == CASE_ID
        ]
        return sorted(entries, key=lambda e: e.log_index)

    def withhold_signatory_commits(self) -> list[str]:
        """Commit while the finder is outside the gate; return those entry ids.

        Under CM-10-005 none of these is ever sent to the finder.  Draining
        the outbox models that.
        """
        for signatory_id in SIGNATORY_IDS:
            self.receive_accept(signatory_id)
        withheld = [e.id_ for e in self.ledger()]
        while self.dl.outbox_pop() is not None:
            pass
        return withheld

    def announced_to(self, actor_id: str) -> list[str]:
        """Entry ids announced to *actor_id*, in outbox order."""
        announced = []
        for activity in (self.dl.read(i) for i in self.dl.outbox_list()):
            if getattr(activity, "type_", None) != "Announce":
                continue
            if actor_id not in (getattr(activity, "to", None) or []):
                continue
            if (entry := getattr(activity, "object_", None)) is not None:
                announced.append(entry.id_)
        return announced


def _assert_backfilled(scenario: _GateScenario, withheld: list[str]) -> None:
    """The finder got every withheld entry, in log order, then the admitting one.

    The backfill goes to the admitted participant only, not to everyone, each
    entry goes to it once, and the CASE_MANAGER never announces to itself.
    """
    announced = scenario.announced_to(NON_SIGNATORY_ID)
    assert announced[: len(withheld)] == withheld
    admitting = [e.id_ for e in scenario.ledger()][len(withheld) :]
    assert announced[len(withheld) :] == admitting
    assert len(announced) == len(set(announced))
    for signatory_id in SIGNATORY_IDS:
        to_signatory = scenario.announced_to(signatory_id)
        assert not set(withheld) & set(to_signatory)
        assert len(to_signatory) == len(set(to_signatory))
    assert scenario.announced_to(MANAGER_ID) == []


def test_signatory_accepts_commit_entries_before_the_finder_is_admitted(
    make_payload,
) -> None:
    """Precondition for the backfill tests: more than one entry is withheld.

    Kept as its own test so that a change in what an accept commits fails
    loudly here, not as a confusing ordering failure in a backfill test.
    """
    scenario = _GateScenario(make_payload)

    assert len(scenario.withhold_signatory_commits()) >= 2


@pytest.mark.spec("CM-10-006")
def test_accepting_the_active_embargo_backfills_withheld_entries(
    make_payload,
) -> None:
    scenario = _GateScenario(make_payload)
    withheld = scenario.withhold_signatory_commits()

    scenario.receive_accept(NON_SIGNATORY_ID)

    _assert_backfilled(scenario, withheld)


@pytest.mark.spec("CM-10-005")
def test_withheld_participant_is_sent_nothing_before_admission(
    make_payload,
) -> None:
    """Control for the backfill tests: the gate really withheld the entries."""
    scenario = _GateScenario(make_payload)
    for signatory_id in SIGNATORY_IDS:
        scenario.receive_accept(signatory_id)

    assert scenario.announced_to(NON_SIGNATORY_ID) == []
    assert scenario.announced_to(SIGNATORY_IDS[0])


@pytest.mark.spec("CM-10-006")
def test_terminating_the_embargo_backfills_every_paused_participant(
    make_payload,
) -> None:
    """AC-4: the embargo ending admits the participant just as accepting does."""
    scenario = _GateScenario(make_payload)
    withheld = scenario.withhold_signatory_commits()

    scenario.receive_remove()

    stored = cast(VulnerabilityCase, scenario.dl.read(CASE_ID))
    assert stored.active_embargo_id is None
    _assert_backfilled(scenario, withheld)


@pytest.mark.spec("CM-10-006")
@pytest.mark.parametrize(
    "terminate",
    [_GateScenario.trigger_terminate, _GateScenario.cascade_terminate],
    ids=["trigger", "cascade"],
)
def test_terminating_the_embargo_locally_backfills_paused_participant(
    make_payload, terminate
) -> None:
    """Ending the embargo locally admits the finder at the next fan-out.

    ``terminate_embargo_bt`` serves the terminate trigger and the CS.P/X/A and
    threat cascades alike. It ends the embargo and then commits the new case
    status, so that entry's fan-out backfills the finder before sending it.
    """
    scenario = _GateScenario(make_payload)
    withheld = scenario.withhold_signatory_commits()

    terminate(scenario)

    stored = cast(VulnerabilityCase, scenario.dl.read(CASE_ID))
    assert stored.active_embargo_id is None
    _assert_backfilled(scenario, withheld)


@pytest.mark.spec("CM-10-006")
@pytest.mark.spec("EMB-17-001")
def test_an_honored_late_accept_backfills_withheld_entries(
    make_payload,
) -> None:
    """A late Accept the CASE_MANAGER honors admits the participant too."""
    scenario = _GateScenario(make_payload)
    withheld = scenario.withhold_signatory_commits()
    scenario.lapse_invite(NON_SIGNATORY_ID)

    scenario.receive_accept(NON_SIGNATORY_ID)

    finder = scenario.dl.read(f"{CASE_ID}/participants/finder")
    assert isinstance(finder, CaseParticipant)
    assert scenario.embargo.id_ in finder.accepted_embargo_ids
    _assert_backfilled(scenario, withheld)


@pytest.mark.spec("CM-10-006")
def test_activating_a_revision_the_participant_accepted_backfills_it(
    make_payload,
) -> None:
    """A received Add(EmbargoEvent) that admits the finder backfills it.

    The Add entry is committed and fanned out while the old embargo is still
    active, so its fan-out withholds the finder; the backfill after the
    activation sends it everything, the Add entry included.
    """
    scenario = _GateScenario(make_payload)
    withheld = scenario.withhold_signatory_commits()

    scenario.receive_revision_accepted_by(NON_SIGNATORY_ID)

    stored = cast(VulnerabilityCase, scenario.dl.read(CASE_ID))
    assert stored.active_embargo_id == f"{CASE_ID}/embargo_events/e2"
    _assert_backfilled(scenario, withheld)
