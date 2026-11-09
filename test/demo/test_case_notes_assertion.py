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

"""A note-thread check takes both note ids or neither (#5643)."""

from typing import cast

import pytest

from vultron.demo.helpers.verification.records import (
    verify_receiver_case_state,
)
from vultron.demo.helpers.verification.states import _assert_case_notes
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR = "https://example.org/actors/a"
Q = "https://example.org/notes/q"
R = "https://example.org/notes/r"


def _case(*note_ids: str) -> as_VulnerabilityCase:
    """A case holding exactly *note_ids* in its notes."""
    return as_VulnerabilityCase(attributed_to=ACTOR, notes=list(note_ids))


class _RecordingClient:
    """A ``DataLayerClient`` stand-in that records every read it is asked for."""

    def __init__(self) -> None:
        self.reads: list[str] = []

    def dl_path(self, key: str = "", actor_id: str | None = None) -> str:
        return f"/dl/{key}"

    def get(self, path: str) -> dict:
        self.reads.append(path)
        raise AssertionError(f"unexpected store read: {path}")


def test_both_none_is_skipped() -> None:
    _assert_case_notes(_case(), None, None)


def test_both_present_passes() -> None:
    _assert_case_notes(_case(Q, R), Q, R)


def test_both_given_one_missing_raises() -> None:
    with pytest.raises(AssertionError, match="Reply note"):
        _assert_case_notes(_case(Q), Q, R)


@pytest.mark.parametrize(
    ("question", "reply", "missing", "other"),
    [
        (None, R, "question_note_id", "reply_note_id"),
        (Q, None, "reply_note_id", "question_note_id"),
    ],
)
def test_exactly_one_none_raises_naming_missing(
    question: str | None, reply: str | None, missing: str, other: str
) -> None:
    # The case holds the given note, so only the pair check can reject the
    # call.  Both names appear in the message, so the assertions anchor on
    # which one opens it: an unanchored match passes either way round.
    case = _case(*(i for i in (question, reply) if i))
    with pytest.raises(AssertionError, match=rf"^{missing} is None") as exc:
        _assert_case_notes(case, question, reply)
    message = str(exc.value)
    assert not message.startswith(other)
    assert "needs both" in message


def test_the_receiver_check_refuses_one_id_before_reading_the_store() -> None:
    """The production entry point refuses before it fetches anything.

    A unit test of the private pair check says nothing about whether the
    caller reaches it (``notes/testing-pitfalls.md``, #3156), and refusing
    only at the end would let an unrelated earlier assertion mask the
    mis-call.
    """
    client = _RecordingClient()

    with pytest.raises(AssertionError, match=r"^reply_note_id is None"):
        verify_receiver_case_state(
            receiver_client=cast(DataLayerClient, client),
            case_id="https://example.org/cases/1",
            report_id="https://example.org/reports/1",
            receiver_actor_id=ACTOR,
            reporter_actor_id="https://example.org/actors/b",
            question_note_id=Q,
        )

    assert client.reads == []
