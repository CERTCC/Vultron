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


@pytest.fixture(autouse=True)
def stub_summary_seed():
    """Override the conftest stub: these tests exercise the real seed."""
    yield


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
        patch.object(
            invite_chain,
            "find_full_case_invite_for_actor",
            return_value="urn:t:full-invite",
        ) as full_invite,
    ):
        yield SimpleNamespace(
            invite=invite,
            accept=accept,
            reject=reject,
            find=find,
            received=received,
            replica=replica,
            full_invite=full_invite,
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
    chain_mocks.full_invite.assert_called_once()
    assert (
        chain_mocks.full_invite.call_args.kwargs["invitee_id"]
        == "urn:t:vendor"
    )
    assert ran == [True]
    assert demo_utils._demo_failures == []


def test_reject_path_rejects_and_awaits_no_replica(chain_mocks):
    _run(respond="reject")

    chain_mocks.reject.assert_called_once_with(invite_id="urn:t:invite")
    chain_mocks.accept.assert_not_called()
    chain_mocks.replica.assert_not_called()
    chain_mocks.full_invite.assert_not_called()
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
        "Vendor received the full-case Invite",
    ]


def test_chain_seeds_stub_summary_on_case_manager_before_inviting(chain_mocks):
    """The CASE_MANAGER builds the stub Invite from its own case copy, which
    has no ``stub_summary`` until seeded (CM-17-010, MV-10-001, #4285)."""
    order: list[str] = []
    manager_client = MagicMock()
    chain_mocks.invite.side_effect = lambda *a, **k: (
        order.append("invite"),
        SimpleNamespace(activity=MagicMock(id_="urn:t:inv")),
    )[1]
    with (
        patch.object(
            invite_chain,
            "find_case_actor_participant_id",
            return_value="urn:t:case-actor",
        ),
        patch.object(
            invite_chain,
            "get_actor_by_id",
            return_value=mock_actor("urn:t:ca"),
        ) as get_actor,
        patch.object(
            ActorSession,
            "set_stub_summary",
            side_effect=lambda *a, **k: order.append("seed"),
        ) as seed,
    ):
        _run(case_manager_client=manager_client)

    get_actor.assert_called_once_with(manager_client, "urn:t:case-actor")
    seed.assert_called_once()
    assert order == ["seed", "invite"]


def test_chain_without_case_manager_client_does_not_seed(chain_mocks):
    with patch.object(ActorSession, "set_stub_summary") as seed:
        _run()
    seed.assert_not_called()


def test_every_scenario_chain_with_an_inviter_is_ordered_after_a_seed():
    """A scenario's first inviter-triggered chain must seed ``stub_summary``.

    Docker CI is the only place a missing seed shows (the in-process demo
    tests patch ``set_stub_summary`` out), so pin it statically: within each
    scenario module, the first ``run_case_invite_chain`` call that passes
    ``inviter=`` must also pass ``case_manager_client=`` (#4285).
    """
    import ast
    from pathlib import Path

    scenario_dir = Path(invite_chain.__file__).parents[1] / "scenario"
    offenders = []
    for path in sorted(scenario_dir.glob("*_demo.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "run_case_invite_chain"
            ):
                continue
            keywords = {k.arg for k in node.keywords}
            if "inviter" in keywords:
                if "case_manager_client" not in keywords:
                    offenders.append(f"{path.name}:{node.lineno}")
                break
    assert not offenders, offenders
