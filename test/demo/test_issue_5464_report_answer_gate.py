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

"""Regression tests for #5464: a report answer waits for the case replica.

The ``validate-report`` and ``invalidate-report`` triggers address the
CASE_MANAGER of the case opened on receipt, which the receiver learns only
when the CaseActor's ``Create(VulnerabilityCase)`` replica reaches its own
store.  Against a live server that replica lands seconds after the report
(the outbox monitor delivers it on a poll), so answering at once was refused:
``validate-report`` with HTTP 422, and ``invalidate-report`` fell back to the
reporter, whose inbox refused it.

The in-process TestClient drains every outbox before a request returns, so the
replica is always present there and ``test_receive_report_demo.py`` cannot see
the race.  These tests pin the causal gate instead (ADR-0058, DEMOCI-01-007):
the trigger runs only after the replica is in the receiver's own store, and a
replica that never arrives records one gate failure and posts no trigger.
"""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from vultron.demo import utils as demo_utils
from vultron.demo.helpers import workflow

_OFFER_ID = "urn:uuid:offer-5464"

_ANSWERS: list[tuple[str, Callable[..., dict]]] = [
    ("validate_report", workflow.receiver_validates_report),
    ("invalidate_report", workflow.receiver_invalidates_report),
]


@pytest.fixture(autouse=True)
def _clean_failures():
    demo_utils.reset_demo_failures()
    yield
    demo_utils.reset_demo_failures()


@pytest.fixture
def receiver():
    actor = MagicMock()
    actor.id_ = "http://localhost:7999/api/v2/actors/vendorco"
    return actor


def _recording_session(call_order: list[str], trigger: str) -> MagicMock:
    """An ``ActorSession`` stand-in that records when *trigger* is posted."""
    session = MagicMock(name="ActorSession")
    quiet = session.return_value.quiet.return_value

    def _post(**_kwargs):
        call_order.append(trigger)
        result = MagicMock()
        result.model_dump.return_value = {}
        return result

    getattr(quiet, trigger).side_effect = _post
    return session


@pytest.mark.parametrize(
    ("trigger", "answer"), _ANSWERS, ids=[t for t, _ in _ANSWERS]
)
def test_answer_posts_trigger_only_after_case_replica_arrives(
    trigger, answer, receiver
):
    """The trigger fires only once the receiver's store holds the case."""
    client = MagicMock(name="receiver_client")
    call_order: list[str] = []
    polls = iter([None, None, MagicMock(id_="urn:uuid:case-5464")])

    def _find_case(polled_client, offer_id):
        assert polled_client is client
        assert offer_id == _OFFER_ID
        found = next(polls)
        call_order.append("found" if found is not None else "absent")
        return found

    with (
        patch.object(
            workflow,
            "ActorSession",
            _recording_session(call_order, trigger),
        ),
        patch.object(workflow, "find_case_for_offer", side_effect=_find_case),
        patch("vultron.demo.helpers.polling.time.sleep"),
    ):
        answer(client, receiver, _OFFER_ID)

    assert call_order == ["absent", "absent", "found", trigger]
    demo_utils.assert_demo_success()


@pytest.mark.parametrize(
    ("trigger", "answer"), _ANSWERS, ids=[t for t, _ in _ANSWERS]
)
def test_answer_without_case_replica_records_gate_and_posts_nothing(
    trigger, answer, receiver
):
    """A replica that never arrives is one gate failure, and no trigger."""
    call_order: list[str] = []

    with (
        patch.object(
            workflow,
            "ActorSession",
            _recording_session(call_order, trigger),
        ),
        patch.object(
            workflow,
            "wait_for_case_for_offer",
            side_effect=AssertionError("no case replica"),
        ),
    ):
        answer(MagicMock(name="receiver_client"), receiver, _OFFER_ID)

    assert call_order == []
    with pytest.raises(Exception) as excinfo:
        demo_utils.assert_demo_success()
    failures = getattr(excinfo.value, "failures", [])
    assert len(failures) == 1
    assert failures[0].startswith("GATE FAILED")
