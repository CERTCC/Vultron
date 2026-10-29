"""The ``test/demo`` autouse stubs skip a protocol step only for a mock client.

``conftest.stub_full_case_reply`` once replaced the invite chain's full-case
Invite reply with a no-op in every test here, real-app demo tests included,
so a refused full-case Invite passed unseen (#4970, #5444).  These tests pin
the stub to mock clients, the way ``stub_summary_seed`` already works.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.helpers import invite_chain
from vultron.demo.utils import reset_demo_failures


@pytest.fixture(autouse=True)
def _fresh_failures():
    """The real reply's gate records the stopped wait; drop it after."""
    reset_demo_failures()
    yield
    reset_demo_failures()


class _ReplyRan(Exception):
    """Raised by the patched first step of the real full-case reply."""


def _reply(invitee_client: object) -> None:
    invite_chain.reply_to_full_case_invite(
        invitee_name="Invitee",
        invitee_client=invitee_client,  # type: ignore[arg-type]
        invitee=MagicMock(),
        invitee_in_own_container=MagicMock(),
        case=MagicMock(),
        authority_client=MagicMock(),
        timeout=0.1,
    )


@pytest.mark.spec("CM-11-010")
def test_full_case_reply_runs_for_a_real_client():
    """A non-mock client reaches the real reply, so its wait for the Invite runs."""
    with patch.object(
        invite_chain, "find_full_case_invite_for_actor", side_effect=_ReplyRan
    ) as find:
        _reply(SimpleNamespace())
    find.assert_called_once()


def test_full_case_reply_is_skipped_for_a_mock_client():
    """A mock client has no container to poll, so the stub skips the reply."""
    with patch.object(
        invite_chain, "find_full_case_invite_for_actor", side_effect=_ReplyRan
    ) as find:
        _reply(MagicMock())
    find.assert_not_called()
