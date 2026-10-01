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

"""Regression tests for Bug #2120: CLP-08-005 unanchored chain bootstrap.

The Finder receives Announce(CaseLedgerEntry) activities before its genesis
hash is seeded whenever run_invite_path_rm_triage fires without first
confirming the Finder has the case replica (SYNC-13, CLP-08-005).

Each test verifies that wait_for_case_on_container(finder_client, case.id_)
is called BEFORE run_invite_path_rm_triage in every phase function that
triggers RM triage.
"""

import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.helpers.sync as sync_module
import vultron.demo.scenario.fcvcv_demo as demo
import vultron.demo.utils as demo_utils
from test.demo._helpers import patched_report_submission
from vultron.demo.actor_session import ActorSession
from vultron.demo.utils import reset_demo_failures


class _Helpers:
    @staticmethod
    def _actor(id_: str = "urn:test:actor"):
        a = MagicMock()
        a.id_ = id_
        return a

    @staticmethod
    def _case(id_: str = "urn:test:case"):
        c = MagicMock()
        c.id_ = id_
        return c

    @staticmethod
    def _client():
        c = MagicMock()
        c.get.return_value = {}
        return c


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaWaitBeforeV1Triage(_Helpers):
    """_phase_report_submission must wait for the Finder's case replica
    before running V1's RM triage (Bug #2120)."""

    def test_finder_wait_before_v1_triage(self):
        """wait_for_case_on_container(finder_client) precedes run_invite_path_rm_triage for V1."""
        finder_client = self._client()
        c1_client = self._client()
        v1_client = self._client()
        c2_client = self._client()
        v2_client = self._client()

        finder = self._actor("urn:test:finder")
        c1 = self._actor("urn:test:c1")
        c1_in_c1 = self._actor("urn:test:c1")
        v1 = self._actor("urn:test:v1")
        v1_in_v1 = self._actor("urn:test:v1")
        c2 = self._actor("urn:test:c2")
        c2_in_c2 = self._actor("urn:test:c2")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        case = self._case("urn:test:case")

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is finder_client:
                call_order.append("finder_wait")

        def _triage(**_kwargs):
            call_order.append("triage")

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fcvcv",
                return_value=(finder, c1, v1, c2, MagicMock()),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[c1_in_c1, v1_in_v1, c2_in_c2],
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_replica_ledger_coverage"),
            patch.object(demo, "verify_case_active"),
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                ),
            ),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(demo, "post_to_inbox_and_wait"),
            patch.object(demo, "verify_object_stored"),
            patch.object(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch.object(
                demo, "run_invite_path_rm_triage", side_effect=_triage
            ),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(
                demo,
                "demo_gate",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                c1_client=c1_client,
                v1_client=v1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                finder_id=None,
                c1_id=None,
                v1_id=None,
                c2_id=None,
                v2_id=None,
            )

        # finder_wait must appear before the first triage call
        assert "finder_wait" in call_order, (
            "wait_for_case_on_container(finder_client) was never called before V1 triage"
        )
        assert "triage" in call_order, (
            "run_invite_path_rm_triage was never called"
        )
        finder_idx = next(
            i for i, v in enumerate(call_order) if v == "finder_wait"
        )
        triage_idx = next(i for i, v in enumerate(call_order) if v == "triage")
        assert finder_idx < triage_idx, (
            f"Finder case-replica wait (index {finder_idx}) must come BEFORE "
            f"run_invite_path_rm_triage (index {triage_idx}). "
            f"Call order: {call_order} — Bug #2120 (CLP-08-005)"
        )


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaWaitBeforeV2Triage(_Helpers):
    """_phase_c2_suggests_v2 must wait for the Finder's case replica
    before running V2's RM triage (Bug #2120)."""

    def test_finder_client_in_signature(self):
        """_phase_c2_suggests_v2 must accept finder_client as a parameter."""
        import inspect

        sig = inspect.signature(demo._phase_c2_suggests_v2)
        assert "finder_client" in sig.parameters, (
            "_phase_c2_suggests_v2 must accept finder_client to gate V2 RM "
            "triage on the Finder having the case replica (Bug #2120)"
        )

    def test_finder_wait_before_v2_triage(self):
        """wait_for_case_on_container(finder_client) precedes run_invite_path_rm_triage for V2."""
        import inspect

        sig = inspect.signature(demo._phase_c2_suggests_v2)
        if "finder_client" not in sig.parameters:
            pytest.skip(
                "finder_client not yet in signature — prerequisite missing"
            )

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        v2_client = self._client()
        c1_in_c1 = self._actor("urn:test:c1")
        c2_in_c2 = self._actor("urn:test:c2")
        v2 = self._actor("urn:test:v2")
        case = self._case("urn:test:case")

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is finder_client:
                call_order.append("finder_wait")

        def _triage(**_kwargs):
            call_order.append("triage")

        with (
            patch.object(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch.object(
                demo, "run_invite_path_rm_triage", side_effect=_triage
            ),
            patch(
                "vultron.demo.actor_session.post_to_trigger",
                return_value={
                    "activity": {"id": "urn:test:act", "type": "Offer"}
                },
            ),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(
                demo,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:ca",
            ),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                return_value="urn:test:invite-id",
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=MagicMock(id_="urn:test:v2-in-v2"),
            ),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_c2_suggests_v2(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                c1_in_c1=c1_in_c1,
                c2_in_c2=c2_in_c2,
                v2=v2,
                case=case,
                offer=MagicMock(id_="urn:test:offer"),
                report=MagicMock(),
                finder=self._actor("urn:test:finder"),
                v1=self._actor("urn:test:v1"),
            )

        assert "finder_wait" in call_order, (
            "wait_for_case_on_container(finder_client) was never called before V2 triage"
        )
        assert "triage" in call_order, (
            "run_invite_path_rm_triage was never called"
        )
        finder_idx = next(
            i for i, v in enumerate(call_order) if v == "finder_wait"
        )
        triage_idx = next(i for i, v in enumerate(call_order) if v == "triage")
        assert finder_idx < triage_idx, (
            f"Finder case-replica wait (index {finder_idx}) must come BEFORE "
            f"run_invite_path_rm_triage (index {triage_idx}). "
            f"Call order: {call_order} — Bug #2120 (CLP-08-005)"
        )


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaGenesisWaitInReportSubmission(_Helpers):
    """_phase_report_submission must wait for Finder's case replica
    immediately after wait_for_case_participants — before any invitation
    sequence starts (Bug #2120, genesis-level race)."""

    def test_finder_genesis_wait_before_first_invitation(self):
        """wait_for_case_on_container(finder_client) is called in _phase_report_submission
        before any invite-to-case trigger fires (genesis-level guard)."""
        finder_client = self._client()
        c1_client = self._client()
        v1_client = self._client()
        c2_client = self._client()
        v2_client = self._client()

        finder = self._actor("urn:test:finder")
        c1 = self._actor("urn:test:c1")
        c1_in_c1 = self._actor("urn:test:c1")
        v1 = self._actor("urn:test:v1")
        v1_in_v1 = self._actor("urn:test:v1")
        c2 = self._actor("urn:test:c2")
        c2_in_c2 = self._actor("urn:test:c2")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        case = self._case("urn:test:case")

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is finder_client:
                call_order.append("finder_genesis_wait")

        def _invite(self, *_args, **_kwargs):
            call_order.append("invite_trigger")
            return SimpleNamespace(activity=MagicMock(id_="urn:test:invite"))

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fcvcv",
                return_value=(finder, c1, v1, c2, MagicMock()),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[c1_in_c1, v1_in_v1, c2_in_c2],
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_replica_ledger_coverage"),
            patch.object(demo, "verify_case_active"),
            patch.object(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                side_effect=_invite,
                autospec=True,
            ),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(demo, "post_to_inbox_and_wait"),
            patch.object(demo, "verify_object_stored"),
            patch.object(demo, "run_invite_path_rm_triage"),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(
                demo,
                "demo_gate",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                c1_client=c1_client,
                v1_client=v1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                finder_id=None,
                c1_id=None,
                v1_id=None,
                c2_id=None,
                v2_id=None,
            )

        assert "finder_genesis_wait" in call_order, (
            "wait_for_case_on_container(finder_client) was never called in "
            "_phase_report_submission — genesis hash unavailable race (Bug #2120)"
        )
        if "invite_trigger" in call_order:
            genesis_idx = next(
                i
                for i, v in enumerate(call_order)
                if v == "finder_genesis_wait"
            )
            trigger_idx = next(
                i for i, v in enumerate(call_order) if v == "invite_trigger"
            )
            assert genesis_idx < trigger_idx, (
                f"Finder genesis wait (index {genesis_idx}) must precede first "
                f"invite trigger (index {trigger_idx}). "
                f"Call order: {call_order} — Bug #2120 (CLP-08-005)"
            )


class TestFcvcvCausalGates(_Helpers):
    """Verify causal demo_gate sites skip dependent steps on timeout.

    Each test simulates an async-commit timeout at the precondition and
    confirms the dependent step is never reached.
    """

    def test_accept_not_called_when_cp_offer_gate_fails(self):
        """demo_gate skips accept-actor-recommendation when find_cp_offer_for_case times out."""
        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        v2_client = self._client()
        c1_in_c1 = self._actor("urn:test:c1-in-c1")
        c2_in_c2 = self._actor("urn:test:c2-in-c2")
        v1 = self._actor("urn:test:v1")
        v2 = self._actor("urn:test:v2")
        finder = self._actor("urn:test:finder")
        case = self._case()

        mock_post_to_trigger = MagicMock()

        with (
            patch.object(
                demo,
                "find_cp_offer_for_case",
                side_effect=AssertionError(
                    "timed out polling for Offer(CaseParticipant)"
                ),
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor",
            ),
            patch(
                "vultron.demo.actor_session.post_to_trigger",
                mock_post_to_trigger,
            ),
            patch.object(demo, "get_actor_by_id", return_value=MagicMock()),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "run_invite_path_rm_triage"),
        ):
            demo._phase_c2_suggests_v2(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                c1_in_c1=c1_in_c1,
                c2_in_c2=c2_in_c2,
                v2=v2,
                case=case,
                offer=MagicMock(),
                report=MagicMock(),
                finder=finder,
                v1=v1,
            )

        accept_calls = [
            c
            for c in mock_post_to_trigger.call_args_list
            if c.kwargs.get("behavior") == "accept-actor-recommendation"
        ]
        assert not accept_calls, (
            "accept-actor-recommendation must not be called when "
            f"cp_offer gate fails: {accept_calls}"
        )

    def test_v1_accept_not_called_when_invite_gate_fails(self):
        """demo_gate skips V1's accept-case-invite when find_case_invite_for_actor times out (#3038)."""
        finder_client = self._client()
        c1_client = self._client()
        v1_client = self._client()
        c2_client = self._client()
        v2_client = self._client()
        finder = self._actor("urn:test:finder")
        c1 = self._actor("urn:test:c1")
        v1 = self._actor("urn:test:v1")
        c2 = self._actor("urn:test:c2")
        v2 = self._actor("urn:test:v2")
        case = self._case()

        accept_invite = MagicMock()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fcvcv",
                return_value=(finder, c1, v1, c2, v2),
            ),
            patch.object(demo, "get_actor_by_id", side_effect=[c1, v1, c2]),
            patch.object(
                demo,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_case_on_container") as replica_wait,
            patch.object(demo, "verify_case_active"),
            patch.object(demo, "wait_for_replica_ledger_coverage"),
            patch.object(demo, "run_invite_path_rm_triage") as rm_triage,
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                ),
            ),
            patch.object(ActorSession, "accept_case_invite", accept_invite),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                side_effect=AssertionError("timed out polling for Invite"),
            ),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                c1_client=c1_client,
                v1_client=v1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                finder_id=None,
                c1_id=None,
                v1_id=None,
                c2_id=None,
                v2_id=None,
            )

        accept_invite.assert_not_called()
        # The replica waits and V1's RM triage depend on the accept, so the
        # closed gate skips them too (EDF-06-005).
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is v1_client
        ], "replica_wait ran for the skipped dependent: " + str(
            replica_wait.call_args_list
        )
        assert not [
            c
            for c in rm_triage.call_args_list
            if c.kwargs.get("invited_client") is v1_client
        ], "rm_triage ran for the skipped dependent: " + str(
            rm_triage.call_args_list
        )

    def test_v2_accept_not_called_when_invite_gate_fails(self):
        """demo_gate skips V2's accept-case-invite when find_case_invite_for_actor times out (#3038)."""
        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        v2_client = self._client()
        c1_in_c1 = self._actor("urn:test:c1-in-c1")
        c2_in_c2 = self._actor("urn:test:c2-in-c2")
        v1 = self._actor("urn:test:v1")
        v2 = self._actor("urn:test:v2")
        finder = self._actor("urn:test:finder")
        case = self._case()

        accept_invite = MagicMock()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(ActorSession, "accept_case_invite", accept_invite),
            patch.object(
                demo,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor",
            ),
            patch.object(demo, "get_actor_by_id", return_value=MagicMock()),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                side_effect=AssertionError("timed out polling for Invite"),
            ),
            patch.object(demo, "wait_for_case_on_container") as replica_wait,
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "run_invite_path_rm_triage"),
        ):
            demo._phase_c2_suggests_v2(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                c1_in_c1=c1_in_c1,
                c2_in_c2=c2_in_c2,
                v2=v2,
                case=case,
                offer=MagicMock(),
                report=MagicMock(),
                finder=finder,
                v1=v1,
            )

        accept_invite.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is v2_client
        ], "replica_wait ran for the skipped dependent: " + str(
            replica_wait.call_args_list
        )


# ---------------------------------------------------------------------------
# Regression test — ISSUE-2811 timeout fix
# ---------------------------------------------------------------------------


class TestFcvcvRmTriageTimeout(_Helpers):
    """_phase_report_submission must forward timeout_seconds=60.0 to
    run_direct_path_rm_triage so the causal gate (ADR-0058) does not race
    under 4-container CI load (ISSUE-2811)."""

    def test_phase_report_submission_passes_60s_timeout_to_rm_triage(self):
        """Regression: fcvcv CI timed out at 20 s default (ISSUE-2811)."""
        import contextlib

        finder = self._actor("urn:test:finder")
        c1 = self._actor("urn:test:c1")
        c1_in_c1 = self._actor("urn:test:c1")
        v1 = self._actor("urn:test:v1")
        v1_in_v1 = self._actor("urn:test:v1")
        c2 = self._actor("urn:test:c2")
        c2_in_c2 = self._actor("urn:test:c2")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        invite = MagicMock()
        invite.id_ = "urn:test:invite"
        case = self._case()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fcvcv",
                return_value=(finder, c1, v1, c2, MagicMock()),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[c1_in_c1, v1_in_v1, c2_in_c2],
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(
                demo, "run_direct_path_rm_triage", return_value=case
            ) as mock_rm_triage,
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_replica_ledger_coverage"),
            patch.object(demo, "verify_case_active"),
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(activity=invite),
            ),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(demo, "post_to_inbox_and_wait"),
            patch.object(demo, "verify_object_stored"),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(demo, "run_invite_path_rm_triage"),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(
                demo,
                "demo_gate",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=self._client(),
                c1_client=self._client(),
                v1_client=self._client(),
                c2_client=self._client(),
                v2_client=self._client(),
                finder_id=None,
                c1_id=None,
                v1_id=None,
                c2_id=None,
                v2_id=None,
            )

        _call = mock_rm_triage.call_args
        assert _call is not None
        assert _call.kwargs.get("timeout_seconds") == 60.0, (
            "run_direct_path_rm_triage must receive timeout_seconds=60.0; "
            "the 20-second default races under 4-container CI load (ISSUE-2811)"
        )


class TestFcvcvInviteTriggerFailureSkipsDependents(_Helpers):
    """A failed invite *trigger* skips the lookup gate and everything under it.

    Before the fix the trigger result was pre-initialised to ``None`` and
    ``.activity`` was read after the suppressing ``demo_step``, so a failed
    trigger crashed the run with ``AttributeError`` outside the accumulator
    (DEMOCI-01-003, #3038 sibling).
    """

    def test_v1_invite_trigger_failure_skips_lookup_accept_and_triage(self):
        finder_client = self._client()
        c1_client = self._client()
        v1_client = self._client()
        c2_client = self._client()
        v2_client = self._client()
        finder = self._actor("urn:test:finder")
        c1 = self._actor("urn:test:c1")
        v1 = self._actor("urn:test:v1")
        c2 = self._actor("urn:test:c2")
        v2 = self._actor("urn:test:v2")
        case = self._case()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fcvcv",
                return_value=(finder, c1, v1, c2, v2),
            ),
            patch.object(demo, "get_actor_by_id", side_effect=[c1, v1, c2]),
            patch.object(
                demo,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_case_on_container") as replica_wait,
            patch.object(demo, "verify_case_active"),
            patch.object(demo, "wait_for_replica_ledger_coverage"),
            patch.object(demo, "run_invite_path_rm_triage") as rm_triage,
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                side_effect=RuntimeError("invite trigger failed"),
            ),
            patch.object(ActorSession, "accept_case_invite") as accept_invite,
            patch.object(demo, "find_case_invite_for_actor") as find_invite,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
        ):
            mock_vc.model_validate.return_value = case
            # Must not raise: the failure is accumulated, not escaped.
            demo._phase_report_submission(
                finder_client=finder_client,
                c1_client=c1_client,
                v1_client=v1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                finder_id=None,
                c1_id=None,
                v1_id=None,
                c2_id=None,
                v2_id=None,
            )

        find_invite.assert_not_called()
        accept_invite.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is v1_client
        ], "replica_wait ran for the skipped dependent: " + str(
            replica_wait.call_args_list
        )
        assert not [
            c
            for c in rm_triage.call_args_list
            if c.kwargs.get("invited_client") is v1_client
        ], "rm_triage ran for the skipped dependent: " + str(
            rm_triage.call_args_list
        )


# ---------------------------------------------------------------------------
# Phase 1 drain goes through the shared coverage helper (DEMOMA-23-005, #3906)
# ---------------------------------------------------------------------------


class TestFcvcvPhase1DrainViaSharedHelper(_Helpers):
    """The Phase 1 ledger drain is ``wait_for_replica_ledger_coverage``.

    ``drain_phase1_ledger`` was the last private copy of the
    read-authority-tail-then-poll-each-replica loop outside
    ``vultron/demo/helpers/sync.py`` (#3906).  The scenario now calls the
    shared helper with the same authority and replica pairs it passed the
    drain, and inherits the helper's behaviour when the authority holds no
    entries: one recorded gate failure naming the authority (EDF-06-005)
    where the drain used to return silently.
    """

    _CLIENTS = (
        "finder_client",
        "c1_client",
        "v1_client",
        "c2_client",
        "v2_client",
    )

    def _run_report_submission(self, clients: dict, *, stub_coverage: bool):
        """Run ``_phase_report_submission`` with every other collaborator patched.

        With ``stub_coverage=False`` the real ``wait_for_replica_ledger_coverage``
        runs, and the only demo context that can record anything is the one
        inside it, which the helper takes from ``vultron.demo.utils`` directly.
        """
        case = self._case("urn:test:case")
        demo_patches: dict[str, dict] = {
            name: {}
            for name in (
                "wait_for_case_participants",
                "verify_case_active",
                "post_to_inbox_and_wait",
                "verify_object_stored",
                "wait_for_case_on_container",
                "run_invite_path_rm_triage",
            )
        }
        demo_patches["find_case_invite_for_actor"] = {
            "return_value": "urn:test:invite"
        }
        if stub_coverage:
            demo_patches["wait_for_replica_ledger_coverage"] = {}
        with patched_report_submission(
            demo,
            seed_fn="seed_containers_fcvcv",
            seeded_actors=(
                self._actor("urn:test:finder"),
                self._actor("urn:test:c1"),
                self._actor("urn:test:v1"),
                self._actor("urn:test:c2"),
                MagicMock(),
            ),
            actor_lookups=[
                self._actor("urn:test:c1"),
                self._actor("urn:test:v1"),
                self._actor("urn:test:c2"),
            ],
            case=case,
            demo_patches=demo_patches,
            session_patches=("accept_case_invite",),
        ) as mocks:
            demo._phase_report_submission(
                finder_id=None,
                c1_id=None,
                v1_id=None,
                c2_id=None,
                v2_id=None,
                **clients,
            )
        return case, mocks

    def test_phase1_drain_calls_shared_helper_with_same_authority_and_replicas(
        self,
    ):
        """AC-1: same authority, same replica pairs, Phase 1 label, causal gate."""
        clients = {k: self._client() for k in self._CLIENTS}
        case, mocks = self._run_report_submission(clients, stub_coverage=True)

        coverage = mocks["wait_for_replica_ledger_coverage"]
        coverage.assert_called_once()
        kwargs = coverage.call_args.kwargs
        assert kwargs["auth_client"] is clients["c1_client"]
        assert kwargs["replicas"] == [
            (clients["finder_client"], "Finder"),
            (clients["v1_client"], "V1"),
            (clients["c2_client"], "C2"),
        ]
        assert kwargs["case_id"] == case.id_
        assert kwargs["phase_label"] == "Phase 1 drain before Phase 2"
        # The drain is a causal gate for Phase 2 (EDF-06-005): the helper's
        # default, so the scenario must not downgrade it to a temporal check.
        assert "causal" not in kwargs
        assert "late_joiners" not in kwargs

    def test_phase1_drain_records_gate_failure_when_authority_holds_no_entries(
        self,
    ):
        """AC-4: an empty authority ledger is one GATE FAILED naming the authority.

        ``drain_phase1_ledger`` returned silently here; the shared helper records
        the writer's fault instead of leaving a replica-side check to report
        "replication did not complete" (EDF-06-005).  The real
        ``wait_for_replica_ledger_coverage`` and the real ``demo_gate`` run;
        only the authority-tail read and the per-replica primitive are stubbed.
        """
        clients = {k: self._client() for k in self._CLIENTS}
        clients["c1_client"].base_url = "http://c1.test/api/v2"
        reset_demo_failures()
        try:
            with (
                patch.object(
                    sync_module, "_get_log_entries_for_case", return_value=[]
                ),
                patch.object(
                    sync_module, "wait_for_contiguous_ledger_coverage"
                ) as per_replica,
            ):
                self._run_report_submission(clients, stub_coverage=False)

            per_replica.assert_not_called()
            (failure,) = demo_utils._demo_failures
        finally:
            reset_demo_failures()
        assert failure.startswith("GATE FAILED")
        assert "http://c1.test/api/v2" in failure
        assert "Phase 1 drain before Phase 2" in failure
        assert "holds no CaseLedgerEntry" in failure
        for label in ("Finder", "V1", "C2"):
            assert label not in failure, failure
