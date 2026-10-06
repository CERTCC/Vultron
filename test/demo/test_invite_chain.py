"""Unit tests for the shared case-invite chain (DEMOMA-17-001, #4192)."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from test.demo._helpers import mock_actor, mock_case
from vultron.demo import utils as demo_utils
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import invite_chain
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    EmittedBy,
    run_case_invite_chain,
)
from vultron.demo.utils import reset_demo_failures
from vultron.enums.roles import CVDRole


@pytest.fixture(autouse=True)
def _fresh_failures():
    reset_demo_failures()
    yield
    reset_demo_failures()


@pytest.fixture
def chain_mocks():
    """Stub every collaborator the chain calls; yield them by name."""
    with (
        patch.object(
            ActorSession,
            "invite_actor_to_case",
            return_value=SimpleNamespace(activity=MagicMock(id_="urn:t:inv")),
        ) as invite,
        patch.object(ActorSession, "accept_case_invite") as accept,
        patch.object(ActorSession, "reject_case_invite") as reject,
        patch.object(
            invite_chain,
            "find_case_invite_for_actor",
            return_value="urn:t:invite",
        ) as find,
        patch.object(invite_chain, "assert_received_from") as received,
        patch.object(invite_chain, "wait_for_case_on_container") as replica,
    ):
        yield SimpleNamespace(
            invite=invite,
            accept=accept,
            reject=reject,
            find=find,
            received=received,
            replica=replica,
        )


def _run(**overrides):
    kwargs: dict[str, Any] = dict(
        case=mock_case(),
        invitee_name="Vendor",
        invitee_client=MagicMock(),
        invitee=mock_actor("urn:t:vendor"),
        invitee_in_own_container=mock_actor("urn:t:vendor"),
        inviter=CaseInviter(
            name="Coordinator",
            client=MagicMock(),
            actor=mock_actor("urn:t:coord"),
            role=CVDRole.VENDOR,
        ),
    )
    kwargs.update(overrides)
    run_case_invite_chain(**kwargs)


def test_accept_path_invites_finds_accepts_and_waits_for_replica(chain_mocks):
    ran = []
    _run(then=lambda: ran.append(True))

    chain_mocks.invite.assert_called_once()
    assert chain_mocks.invite.call_args.kwargs == {
        "invitee_id": "urn:t:vendor",
        "roles": [CVDRole.VENDOR],
    }
    chain_mocks.accept.assert_called_once_with(invite_id="urn:t:invite")
    chain_mocks.reject.assert_not_called()
    chain_mocks.replica.assert_called_once()
    assert ran == [True]
    assert demo_utils._demo_failures == []


def test_reject_path_rejects_and_awaits_no_replica(chain_mocks):
    _run(respond="reject")

    chain_mocks.reject.assert_called_once_with(invite_id="urn:t:invite")
    chain_mocks.accept.assert_not_called()
    chain_mocks.replica.assert_not_called()
    assert demo_utils._demo_failures == []


def test_recommend_path_has_no_inviter_and_triggers_no_invite(chain_mocks):
    _run(inviter=None)

    chain_mocks.invite.assert_not_called()
    chain_mocks.find.assert_called_once()
    chain_mocks.accept.assert_called_once_with(invite_id="urn:t:invite")


def test_timeouts_are_forwarded(chain_mocks):
    _run(invite_timeout=90.0, replica_timeout=42.0)

    assert chain_mocks.find.call_args.kwargs["timeout_seconds"] == 90.0
    assert chain_mocks.replica.call_args.kwargs["timeout_seconds"] == 42.0


def test_replica_timeout_defaults_to_the_polling_default(chain_mocks):
    _run()

    assert "timeout_seconds" not in chain_mocks.replica.call_args.kwargs


def test_failed_invite_trigger_skips_every_dependent(chain_mocks):
    chain_mocks.invite.side_effect = RuntimeError("trigger failed")
    ran = []

    _run(then=lambda: ran.append(True))

    chain_mocks.find.assert_not_called()
    chain_mocks.accept.assert_not_called()
    chain_mocks.replica.assert_not_called()
    assert ran == []
    assert len(demo_utils._demo_failures) == 1
    assert (
        "Coordinator invites Vendor with CVDRole.VENDOR"
        in (demo_utils._demo_failures[0])
    )


def test_undelivered_invite_skips_the_answer_and_what_follows(chain_mocks):
    chain_mocks.find.side_effect = AssertionError("timed out")
    ran = []

    _run(then=lambda: ran.append(True))

    chain_mocks.accept.assert_not_called()
    chain_mocks.replica.assert_not_called()
    assert ran == []
    assert len(demo_utils._demo_failures) == 1
    assert (
        "Vendor invite delivered to Vendor's DataLayer"
        in (demo_utils._demo_failures[0])
    )


def test_sender_check_runs_before_the_answer(chain_mocks):
    order: list[str] = []
    chain_mocks.received.side_effect = lambda *a, **k: order.append("check")
    chain_mocks.accept.side_effect = lambda *a, **k: order.append("accept")

    _run(
        expect_emitted_by=EmittedBy(
            case_actor_id="urn:t:case-actor", consequence="it would misroute"
        )
    )

    assert order == ["check", "accept"]
    assert chain_mocks.received.call_args.args[1:] == (
        "urn:t:invite",
        "urn:t:case-actor",
        "it would misroute",
    )
    chain_mocks.accept.assert_called_once()


def test_failed_sender_check_is_recorded_but_does_not_block_the_answer(
    chain_mocks,
):
    chain_mocks.received.side_effect = AssertionError("emitted by participant")

    _run(
        expect_emitted_by=EmittedBy(case_actor_id="x", consequence="y"),
    )

    chain_mocks.accept.assert_called_once()
    assert len(demo_utils._demo_failures) == 1


def test_failed_replica_wait_is_recorded_and_then_still_runs(chain_mocks):
    chain_mocks.replica.side_effect = AssertionError("no replica")
    ran = []

    _run(then=lambda: ran.append(True))

    assert ran == [True]
    assert len(demo_utils._demo_failures) == 1


def test_then_runs_after_a_reject(chain_mocks):
    ran = []

    _run(respond="reject", then=lambda: ran.append(True))

    assert ran == [True]
    chain_mocks.replica.assert_not_called()


def test_step_and_gate_labels_are_pinned(chain_mocks):
    """Scenario logs and CI triage grep these labels; changing one is visible."""
    labels: list[str] = []
    real_step, real_gate, real_check = (
        invite_chain.demo_step,
        invite_chain.demo_gate,
        invite_chain.demo_check,
    )

    def recording(real):
        def wrapper(label, *a, **k):
            labels.append(label)
            return real(label, *a, **k)

        return wrapper

    with (
        patch.object(invite_chain, "demo_step", recording(real_step)),
        patch.object(invite_chain, "demo_gate", recording(real_gate)),
        patch.object(invite_chain, "demo_check", recording(real_check)),
    ):
        _run(
            expect_emitted_by=EmittedBy(case_actor_id="x", consequence="y"),
        )

    assert labels == [
        "Coordinator invites Vendor with CVDRole.VENDOR",
        "Vendor invite delivered to Vendor's DataLayer",
        "Vendor invite was emitted as the CaseActor (PCR-08-008)",
        "Vendor accepts the case invitation",
        "Vendor's DataLayer received case replica",
    ]
