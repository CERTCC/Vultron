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

"""Regression tests for ISSUE-2390: async race-window in rcv-reject demo.

Root cause: ``participant_adds_note_to_case`` in ``notes.py`` raises an
``AssertionError`` *outside* any ``demo_step``/``demo_gate`` context manager
when the ``add-note-to-case`` trigger returns no note ID (e.g. because
``post_to_trigger`` was suppressed by ``demo_step`` after an HTTP error).
That bare ``raise`` escapes ``scenario_harness`` and crashes the scenario
before Phase 4–5 run, leaving ``close_case`` and ``add_note_to_case`` absent
from the case-actor ledger and the Reporter log empty.

The fix: move the ``note_id is None`` check inside ``demo_step`` so
``demo_step`` accumulates the failure; add an early ``return None`` guard
after the block so no downstream code runs against a ``None`` note ID.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx2 as httpx

import vultron.demo.scenario.rcv_reject_demo as demo
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import invite_chain
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.utils import reset_demo_failures


def _make_note_fixtures():
    mock_client = MagicMock()
    mock_actor = MagicMock()
    mock_actor.id_ = "http://example.test/actors/reporter"
    mock_case = MagicMock()
    mock_case.id_ = "http://example.test/cases/case-1"
    return mock_client, mock_actor, mock_case


class TestParticipantAddsNoteNoNoteId:
    """ISSUE-2390: AssertionError must not escape when trigger returns no note ID."""

    def setup_method(self):
        reset_demo_failures()

    def test_empty_trigger_response_returns_none(self):
        """Trigger returns {} — no note ID — function must return None, not raise."""
        mock_client, mock_actor, mock_case = _make_note_fixtures()
        with patch(
            "vultron.demo.actor_session.post_to_trigger",
            return_value={},
        ):
            result = participant_adds_note_to_case(
                posting_client=mock_client,
                watching_client=mock_client,
                poster=mock_actor,
                case=mock_case,
                note_name="test-note",
                note_content="test content",
            )
        assert result is None

    def test_trigger_http_error_returns_none(self):
        """Trigger raises HTTPStatusError — demo_step swallows it — function must return None, not raise."""
        mock_client, mock_actor, mock_case = _make_note_fixtures()
        mock_request = MagicMock()
        mock_response = MagicMock()
        http_error = httpx.HTTPStatusError(
            "422 Unprocessable Entity",
            request=mock_request,
            response=mock_response,
        )
        with patch(
            "vultron.demo.actor_session.post_to_trigger",
            side_effect=http_error,
        ):
            result = participant_adds_note_to_case(
                posting_client=mock_client,
                watching_client=mock_client,
                poster=mock_actor,
                case=mock_case,
                note_name="test-note",
                note_content="test content",
            )
        assert result is None

    def test_delivery_timeout_returns_none(self):
        """demo_gate swallows wait_for_note_in_case timeout — function must return None, not raise."""
        mock_client, mock_actor, mock_case = _make_note_fixtures()
        with (
            patch(
                "vultron.demo.actor_session.post_to_trigger",
                return_value={
                    "note": {"id": "http://example.test/notes/note-1"}
                },
            ),
            patch(
                "vultron.demo.helpers.notes.wait_for_note_in_case",
                side_effect=AssertionError(
                    "note not found in case after timeout"
                ),
            ),
        ):
            result = participant_adds_note_to_case(
                posting_client=mock_client,
                watching_client=mock_client,
                poster=mock_actor,
                case=mock_case,
                note_name="test-note",
                note_content="test content",
            )
        assert result is None


class TestRcvRejectInviteChainSkipsDependents:
    """Phase 2: a failed invite trigger or delivery lookup skips the reject.

    Before the fix ``invite_result.activity`` was read on a ``None`` sentinel
    after the suppressing ``demo_step`` (crash, #3038 sibling), and the
    delivery wait was a ``demo_check`` that let the reject post regardless
    (EDF-06-005).
    """

    def setup_method(self):
        reset_demo_failures()

    @staticmethod
    def _actor(id_: str = "urn:test:actor"):
        a = MagicMock()
        a.id_ = id_
        return a

    @staticmethod
    def _client():
        c = MagicMock()
        c.get.return_value = {}
        return c

    def _run(self, *, invite_trigger, invite_lookup):
        vendor = self._actor("urn:test:vendor")
        with (
            patch.object(
                ActorSession, "invite_actor_to_case", **invite_trigger
            ),
            patch.object(ActorSession, "reject_case_invite") as reject_invite,
            patch.object(
                invite_chain, "find_case_invite_for_actor", **invite_lookup
            ) as find_invite,
            patch.object(demo, "get_actor_by_id", return_value=vendor),
            # set_stub_summary is seeding infrastructure not under test here.
            patch.object(ActorSession, "set_stub_summary"),
            patch.object(demo, "wait_for_semantic_type_in_ledger"),
            patch.object(demo, "wait_for_case_participants"),
        ):
            # Must not raise: every failure is accumulated, never escaped.
            demo._phase_invite_vendor_reject(
                coordinator_client=self._client(),
                case_actor_client=self._client(),
                vendor_client=self._client(),
                reporter=self._actor("urn:test:reporter"),
                coordinator_in_coordinator=self._actor("urn:test:coordinator"),
                coordinator=self._actor("urn:test:coordinator"),
                vendor=vendor,
                case=self._actor("urn:test:case"),
            )
        return find_invite, reject_invite

    def test_invite_trigger_failure_skips_lookup_and_reject(self):
        find_invite, reject_invite = self._run(
            invite_trigger={
                "side_effect": RuntimeError("invite trigger failed")
            },
            invite_lookup={"return_value": "urn:test:invite"},
        )
        find_invite.assert_not_called()
        reject_invite.assert_not_called()

    def test_invite_lookup_failure_skips_reject(self):
        _, reject_invite = self._run(
            invite_trigger={
                "return_value": SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                )
            },
            invite_lookup={
                "side_effect": AssertionError("timed out polling for Invite")
            },
        )
        reject_invite.assert_not_called()


class TestRcvRejectReadsTheCaseManagersStore:
    """The rejection checks read the dedicated case-actor container (#1876).

    The rejection commits only in the CASE_MANAGER's store (CLP-10-006), which
    lives on the dedicated case-actor container; the Coordinator's container
    cannot address it, so every post-rejection read must go through
    ``case_actor_client``.
    """

    def setup_method(self):
        reset_demo_failures()

    def test_post_rejection_reads_go_through_case_actor_client(self):
        coordinator_client = MagicMock()
        case_actor_client = MagicMock()
        vendor = MagicMock(id_="urn:test:vendor")
        with (
            patch.object(demo, "run_case_invite_chain") as chain,
            patch.object(demo, "get_actor_by_id", return_value=vendor),
            patch.object(demo, "wait_for_semantic_type_in_ledger") as ledger,
            patch.object(demo, "wait_for_case_participants") as roster,
            patch.object(demo, "wait_for_participant_rm_state") as rm_wait,
            patch.object(demo, "_check_participant_rm_state_in") as rm_check,
        ):
            demo._phase_invite_vendor_reject(
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor_client=MagicMock(),
                reporter=MagicMock(id_="urn:test:reporter"),
                coordinator_in_coordinator=MagicMock(id_="urn:test:coord"),
                coordinator=MagicMock(id_="urn:test:coord"),
                vendor=vendor,
                case=MagicMock(id_="urn:test:case"),
            )
        assert chain.call_args.kwargs["case_manager_client"] is (
            case_actor_client
        )
        assert ledger.call_args.kwargs["client"] is case_actor_client
        assert roster.call_args.kwargs["vendor_client"] is case_actor_client
        assert rm_wait.call_args.kwargs["client"] is case_actor_client
        assert rm_check.call_args.kwargs["client"] is case_actor_client


class TestRcvRejectDumpTargetsTheCaseActorContainer:
    """The ``case-actor`` ledger is dumped from the dedicated container."""

    def test_case_actor_target_uses_case_actor_client(self):
        case_actor_client = MagicMock(
            actor_id="http://case-actor:7999/api/v2/actors/case-actor"
        )
        with patch.object(demo, "dump_case_ledgers") as dump:
            demo._phase_dump_case_ledgers(
                reporter_client=MagicMock(actor_id="http://f/actors/reporter"),
                coordinator_client=MagicMock(
                    actor_id="http://c/actors/coordinator"
                ),
                case_actor_client=case_actor_client,
                case=MagicMock(id_="urn:test:case"),
            )
        targets = {t.actor_name: t for t in dump.call_args.kwargs["targets"]}
        assert targets["case-actor"].client is case_actor_client
        assert targets["case-actor"].route_key == "case-actor"
