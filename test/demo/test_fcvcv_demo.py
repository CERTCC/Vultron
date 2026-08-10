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
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.scenario.fcvcv_demo as demo


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
            patch.object(demo, "receiver_validates_report"),
            patch.object(demo, "find_case_for_offer", return_value=case),
            patch.object(demo, "receiver_engages_case"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "verify_case_active"),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={
                    "activity": {"id": "urn:test:act", "type": "Offer"}
                },
            ),
            patch.object(demo, "post_to_inbox_and_wait"),
            patch.object(demo, "verify_object_stored"),
            patch.object(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch.object(
                demo, "run_invite_path_rm_triage", side_effect=_triage
            ),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
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
            mock_ta.model_validate.return_value = MagicMock(
                id_="urn:test:invite"
            )
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
        assert (
            "finder_wait" in call_order
        ), "wait_for_case_on_container(finder_client) was never called before V1 triage"
        assert (
            "triage" in call_order
        ), "run_invite_path_rm_triage was never called"
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
            patch.object(
                demo,
                "post_to_trigger",
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
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
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
            mock_ta.model_validate.return_value = MagicMock(
                id_="urn:test:invite"
            )
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
            )

        assert (
            "finder_wait" in call_order
        ), "wait_for_case_on_container(finder_client) was never called before V2 triage"
        assert (
            "triage" in call_order
        ), "run_invite_path_rm_triage was never called"
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

        def _post_to_trigger(**_kwargs):
            call_order.append("invite_trigger")
            return {"activity": {"id": "urn:test:act", "type": "Offer"}}

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
            patch.object(demo, "receiver_validates_report"),
            patch.object(demo, "find_case_for_offer", return_value=case),
            patch.object(demo, "receiver_engages_case"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "verify_case_active"),
            patch.object(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch.object(
                demo, "post_to_trigger", side_effect=_post_to_trigger
            ),
            patch.object(demo, "post_to_inbox_and_wait"),
            patch.object(demo, "verify_object_stored"),
            patch.object(demo, "run_invite_path_rm_triage"),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
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
            mock_ta.model_validate.return_value = MagicMock(
                id_="urn:test:invite"
            )
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
