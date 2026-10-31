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

from unittest.mock import MagicMock, patch

import httpx2 as httpx

import vultron.demo.scenario.rcv_reject_demo as demo
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
