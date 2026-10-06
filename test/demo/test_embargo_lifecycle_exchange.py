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

"""Unit tests for the embargo lifecycle exchange helpers (#2070).

The helpers drive real trigger endpoints on several containers, so these tests
pin the call shapes and the causal order instead of a running stack: who
proposes, who polls for which Invite, who answers last, and what is read where.
"""

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import MagicMock, create_autospec, patch

import pytest

from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.demo.actor_session import ActorSession
from vultron.demo.exchange import embargo_lifecycle as lifecycle
from vultron.demo.utils import _demo_failures, reset_demo_failures

CASE_ID = "http://case-actor:7999/api/v2/VulnerabilityCases/abc"
EMBARGO_ID = f"{CASE_ID}/embargo_events/90d"
MANAGER = "http://coordinator:7999/api/v2/actors/case-actor"


def _session(name: str, log: list[str]) -> MagicMock:
    """An ActorSession stand-in that records its verbs on the shared *log*."""
    session = create_autospec(ActorSession, instance=True)
    # Dataclass fields are instance attributes, so autospec does not copy them.
    session.actor = MagicMock()
    session.client = MagicMock()
    session.actor.id_ = f"http://{name}:7999/api/v2/actors/{name}"
    session.client.base_url = f"http://{name}:7999/api/v2"
    session.with_case.return_value = session
    proposal = MagicMock()
    proposal.activity.object_ = EMBARGO_ID

    def propose(verb: str):
        def _propose(**_):
            log.append(f"{name}:{verb}")
            return proposal

        return _propose

    session.propose_embargo.side_effect = propose("propose")
    session.propose_embargo_revision.side_effect = propose("propose-revision")
    session.accept_embargo.side_effect = lambda **_: log.append(
        f"{name}:accept"
    )
    session.terminate_embargo.side_effect = lambda **_: log.append(
        f"{name}:terminate"
    )
    return cast(MagicMock, session)


@pytest.fixture
def case() -> MagicMock:
    case = MagicMock()
    case.id_ = CASE_ID
    return case


@pytest.fixture(autouse=True)
def _clean_failures():
    reset_demo_failures()
    yield
    reset_demo_failures()


@pytest.fixture
def polls():
    """Patch every poll the helpers make and log it in call order."""
    log: list[str] = []
    with ExitStack() as stack:
        mocks = {
            "invite": stack.enter_context(
                patch.object(
                    lifecycle,
                    "find_embargo_invite_for_actor",
                    side_effect=lambda **kw: log.append(
                        "invite:" + kw["invitee_id"].split("/")[-1]
                    ),
                )
            ),
            "em": stack.enter_context(
                patch.object(
                    lifecycle,
                    "wait_for_case_em_state",
                    side_effect=lambda *a, **kw: log.append(f"em:{a[2].name}"),
                )
            ),
            "consent": stack.enter_context(
                patch.object(lifecycle, "wait_for_participant_embargo_consent")
            ),
            "accepted": stack.enter_context(
                patch.object(
                    lifecycle,
                    "wait_for_participant_embargo_accepted",
                    side_effect=lambda *a, **kw: log.append("accepted"),
                )
            ),
            "store": stack.enter_context(
                patch.object(
                    lifecycle,
                    "resolve_case_actor_store_id",
                    return_value=MANAGER,
                )
            ),
        }
        yield mocks, log


class TestProposeAndActivate:
    def _run(self, case, log):
        reporter, coordinator, vendor = (
            _session(n, log) for n in ("reporter", "coordinator", "vendor")
        )
        lifecycle.demo_propose_and_activate_embargo(
            reporter, coordinator, vendor, case
        )
        return reporter, coordinator, vendor

    @pytest.mark.spec("DEMOMA-20-002")
    def test_relayed_sequence_runs_in_causal_order(self, case, polls):
        """The reporter proposes; the vendor answers, then the owner decides."""
        _, log = polls
        self._run(case, log)
        assert log[:5] == [
            "reporter:propose",
            "invite:vendor",
            "vendor:accept",
            "invite:coordinator",
            "coordinator:accept",
        ]

    @pytest.mark.spec("DEMOMA-20-002")
    def test_no_participant_polls_for_anothers_message(self, case, polls):
        """Each answerer polls its own replica for an Invite to itself."""
        mocks, log = polls
        _, coordinator, vendor = self._run(case, log)
        polled = {
            (c.kwargs["client"], c.kwargs["invitee_id"])
            for c in mocks["invite"].call_args_list
        }
        assert polled == {
            (vendor.client, vendor.actor.id_),
            (coordinator.client, coordinator.actor.id_),
        }
        assert all(
            c.kwargs["embargo_id"] == EMBARGO_ID
            for c in mocks["invite"].call_args_list
        )

    @pytest.mark.spec("DEMOMA-20-002")
    def test_every_replica_and_the_manager_are_checked_for_active(
        self, case, polls
    ):
        mocks, log = polls
        reporter, coordinator, vendor = self._run(case, log)
        em_calls = mocks["em"].call_args_list
        assert all(c.args[2] is EM.ACTIVE for c in em_calls)
        assert all(
            c.kwargs["active_embargo_id"] == EMBARGO_ID for c in em_calls
        )
        read_through = [
            (c.args[0], c.kwargs.get("dl_actor_id")) for c in em_calls
        ]
        assert read_through == [
            (coordinator.client, MANAGER),
            (reporter.client, None),
            (coordinator.client, None),
            (vendor.client, None),
        ]

    @pytest.mark.spec("DEMOMA-20-009")
    def test_all_three_participants_are_signatories_on_the_coordinator(
        self, case, polls
    ):
        mocks, log = polls
        reporter, coordinator, vendor = self._run(case, log)
        checked = [
            (c.args[0], c.args[2], c.args[3])
            for c in mocks["consent"].call_args_list
            if "dl_actor_id" not in c.kwargs
        ]
        assert checked == [
            (coordinator.client, s.actor.id_, PEC.SIGNATORY)
            for s in (reporter, coordinator, vendor)
        ]

    @pytest.mark.spec("EP-09-006")
    def test_owner_waits_for_the_vendors_consent_to_commit(self, case, polls):
        """The accept's 202 is no evidence of the commit (EDF-06-001)."""
        mocks, log = polls
        mocks["consent"].side_effect = lambda *a, **kw: log.append("consent")
        _, _, vendor = self._run(case, log)
        assert log.index("vendor:accept") < log.index("consent")
        assert log.index("consent") < log.index("coordinator:accept")
        first = mocks["consent"].call_args_list[0]
        assert first.args[2] == vendor.actor.id_
        assert first.kwargs["dl_actor_id"] == MANAGER

    @pytest.mark.spec("EP-09-006")
    def test_owner_does_not_decide_when_the_vendors_consent_never_commits(
        self, case, polls
    ):
        mocks, log = polls
        mocks["consent"].side_effect = AssertionError("timed out")
        _, coordinator, _ = self._run(case, log)
        coordinator.accept_embargo.assert_not_called()
        assert _demo_failures

    @pytest.mark.spec("DEMOMA-20-002")
    def test_a_missing_invite_skips_the_answer_and_is_recorded(
        self, case, polls
    ):
        """No Invite reached the vendor: it is not answered, the failure stays."""
        mocks, log = polls
        mocks["invite"].side_effect = AssertionError("timed out")
        _, _, vendor = self._run(case, log)
        vendor.accept_embargo.assert_not_called()
        assert any("received the relayed Invite" in f for f in _demo_failures)

    @pytest.mark.spec("EP-09-006")
    def test_no_commit_wait_for_a_vendor_that_never_answered(
        self, case, polls
    ):
        mocks, log = polls
        mocks["invite"].side_effect = AssertionError("timed out")
        self._run(case, log)
        # The commit wait reads the manager's store; the final checks do not.
        assert not [
            c
            for c in mocks["consent"].call_args_list
            if "dl_actor_id" in c.kwargs
        ]

    @pytest.mark.spec("DEMOMA-20-002")
    def test_a_failed_proposal_skips_everything_after_it(self, case, polls):
        mocks, log = polls
        reporter = _session("reporter", log)
        reporter.propose_embargo.side_effect = RuntimeError("409")
        coordinator, vendor = (_session(n, log) for n in ("c", "v"))
        lifecycle.demo_propose_and_activate_embargo(
            reporter, coordinator, vendor, case
        )
        mocks["invite"].assert_not_called()
        coordinator.accept_embargo.assert_not_called()
        assert any("Reporter's proposal reaches" in f for f in _demo_failures)

    def test_the_proposed_end_time_is_tz_aware_and_in_the_future(
        self, case, polls
    ):
        _, log = polls
        reporter, *_ = self._run(case, log)
        end_time = reporter.propose_embargo.call_args.kwargs["end_time"]
        assert end_time.tzinfo is not None
        assert end_time > datetime.now(UTC) + timedelta(days=89)


class TestProposeRevision:
    def _run(self, case, log, owner_is_proposer=False):
        proposing = _session("proposer", log)
        accepting = _session("acceptor", log)
        owner = proposing if owner_is_proposer else _session("owner", log)
        lifecycle.demo_propose_embargo_revision(
            proposing, accepting, owner, case
        )
        return proposing, accepting, owner

    @pytest.mark.spec("DEMOMA-21-002")
    def test_revision_is_confirmed_before_anyone_waits_for_active(
        self, case, polls
    ):
        """The replicas read ACTIVE both before and after; REVISE goes first."""
        _, log = polls
        self._run(case, log)
        assert log[:7] == [
            "proposer:propose-revision",
            "em:REVISE",
            "invite:acceptor",
            "acceptor:accept",
            "accepted",
            "invite:owner",
            "owner:accept",
        ]
        assert log[7:] == ["em:ACTIVE"] * 4

    @pytest.mark.spec("EP-05-001")
    def test_owner_waits_for_the_acceptors_answer_to_commit(self, case, polls):
        """An owner that activates first would lapse the acceptor (EP-05-001)."""
        mocks, log = polls
        _, accepting, _ = self._run(case, log)
        call = mocks["accepted"].call_args
        assert call.args[2] == accepting.actor.id_
        assert call.args[3] == EMBARGO_ID
        assert call.kwargs["dl_actor_id"] == MANAGER

    @pytest.mark.spec("EP-05-001")
    def test_owner_does_not_decide_when_the_acceptors_answer_never_commits(
        self, case, polls
    ):
        mocks, log = polls
        mocks["accepted"].side_effect = AssertionError("timed out")
        _, _, owner = self._run(case, log)
        owner.accept_embargo.assert_not_called()
        assert _demo_failures

    @pytest.mark.spec("EP-09-006")
    def test_no_commit_wait_for_an_acceptor_that_never_answered(
        self, case, polls
    ):
        """The Invite never arrived: nothing was answered, so nothing to await."""
        mocks, log = polls
        mocks["invite"].side_effect = AssertionError("timed out")
        _, accepting, _ = self._run(case, log)
        accepting.accept_embargo.assert_not_called()
        mocks["accepted"].assert_not_called()

    @pytest.mark.spec("DEMOMA-21-010")
    def test_manager_and_each_distinct_replica_checked_for_the_revision(
        self, case, polls
    ):
        mocks, log = polls
        proposing, accepting, owner = self._run(case, log)
        active = [
            c for c in mocks["em"].call_args_list if c.args[2] is EM.ACTIVE
        ]
        assert [c.args[0] for c in active] == [
            owner.client,
            proposing.client,
            accepting.client,
            owner.client,
        ]
        assert active[0].kwargs["dl_actor_id"] == MANAGER
        assert all(c.kwargs["active_embargo_id"] == EMBARGO_ID for c in active)

    @pytest.mark.spec("DEMOMA-21-002")
    def test_owner_who_proposed_answers_without_an_invite(self, case, polls):
        """The CASE_MANAGER never invites the proposer (EP-09-002)."""
        mocks, log = polls
        proposing, accepting, owner = self._run(
            case, log, owner_is_proposer=True
        )
        assert owner is proposing
        invited = [
            c.kwargs["invitee_id"] for c in mocks["invite"].call_args_list
        ]
        assert invited == [accepting.actor.id_]
        assert log.count("proposer:accept") == 1
        assert log.index("acceptor:accept") < log.index("proposer:accept")
        active = [
            c for c in mocks["em"].call_args_list if c.args[2] is EM.ACTIVE
        ]
        assert [c.args[0] for c in active] == [
            proposing.client,
            proposing.client,
            accepting.client,
        ]

    @pytest.mark.spec("DEMOMA-21-002")
    def test_a_revision_that_never_reaches_revise_stops_the_sequence(
        self, case, polls
    ):
        mocks, log = polls
        mocks["em"].side_effect = AssertionError("timed out")
        _, accepting, owner = self._run(case, log)
        accepting.accept_embargo.assert_not_called()
        owner.accept_embargo.assert_not_called()
        assert _demo_failures


class TestTerminate:
    @pytest.mark.spec("DEMOMA-20-011")
    def test_terminates_then_reads_exited_from_the_manager(self, case, polls):
        mocks, log = polls
        terminating = _session("coordinator", log)
        lifecycle.demo_terminate_embargo(terminating, case)
        assert log == ["coordinator:terminate", "em:EXITED"]
        em_call = mocks["em"].call_args
        assert em_call.args[0] is terminating.client
        assert em_call.kwargs["dl_actor_id"] == MANAGER

    @pytest.mark.spec("DEMOMA-20-012")
    def test_asserts_no_participant_consent(self, case, polls):
        mocks, log = polls
        lifecycle.demo_terminate_embargo(_session("coordinator", log), case)
        mocks["consent"].assert_not_called()
        mocks["invite"].assert_not_called()

    @pytest.mark.spec("DEMOMA-20-011")
    def test_an_embargo_that_never_exits_is_recorded(self, case, polls):
        mocks, log = polls
        mocks["em"].side_effect = AssertionError("timed out")
        lifecycle.demo_terminate_embargo(_session("coordinator", log), case)
        assert any("EM.EXITED" in f for f in _demo_failures)
