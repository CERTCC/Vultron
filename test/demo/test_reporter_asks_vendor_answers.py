"""The shared Reporter/Vendor note exchange puts both notes in the case.

Spec: DEMOMA-16-001.
"""

from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.helpers import notes


@pytest.mark.spec("DEMOMA-16-001")
def test_the_vendor_answer_replies_to_the_reporter_question():
    reporter, vendor = MagicMock(), MagicMock()
    watching, case = MagicMock(), MagicMock()
    question = MagicMock(id_="urn:note:question")

    with patch.object(
        notes, "participant_adds_note_to_case", side_effect=[question, None]
    ) as add_note:
        notes.reporter_asks_vendor_answers(reporter, vendor, watching, case)

    first, second = add_note.call_args_list
    assert first.kwargs["posting_client"] is reporter.client
    assert first.kwargs["poster"] is reporter.actor
    assert second.kwargs["posting_client"] is vendor.client
    assert second.kwargs["poster"] is vendor.actor
    assert second.kwargs["in_reply_to"] == "urn:note:question"
    assert first.kwargs["watching_client"] is watching
    assert second.kwargs["watching_client"] is watching


@pytest.mark.spec("DEMOMA-16-001")
def test_a_failed_question_leaves_the_reply_unthreaded():
    with patch.object(
        notes, "participant_adds_note_to_case", return_value=None
    ) as add_note:
        notes.reporter_asks_vendor_answers(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )

    assert add_note.call_args_list[1].kwargs["in_reply_to"] is None
