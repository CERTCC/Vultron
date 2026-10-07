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
"""The triggers a joined participant answers the full-case Invite with (CM-11-011).

Each of Accept / TentativeReject / Reject carries the participant's own ledger
position, and fails closed until its ledger copy reaches the Invite's floor
(SYNC-10-004, CM-11-012).
"""

import json
from collections.abc import Iterator

import pytest

from test.support.received import archive_received
from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.use_cases.triggers.full_case_invite import (
    SvcAcceptFullCaseInviteUseCase,
    SvcRejectFullCaseInviteUseCase,
    SvcTentativeRejectFullCaseInviteUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptFullCaseInviteTriggerRequest,
    RejectFullCaseInviteTriggerRequest,
    TentativeRejectFullCaseInviteTriggerRequest,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.wire.as2.factories import rm_invite_to_full_case_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_MANAGER = "https://example.org/actors/manager-full-invite"

_CASES = [
    pytest.param(
        SvcAcceptFullCaseInviteUseCase,
        AcceptFullCaseInviteTriggerRequest,
        "Accept",
        id="accept",
    ),
    pytest.param(
        SvcTentativeRejectFullCaseInviteUseCase,
        TentativeRejectFullCaseInviteTriggerRequest,
        "TentativeReject",
        id="tentative-reject",
    ),
    pytest.param(
        SvcRejectFullCaseInviteUseCase,
        RejectFullCaseInviteTriggerRequest,
        "Reject",
        id="reject",
    ),
]


@pytest.fixture
def participant() -> Iterator[tuple[as_Service, SqliteDataLayer, str, str]]:
    """A participant store holding the case (empty ledger) and its genesis."""
    actor = as_Service(name="Participant")
    reset_datalayer(actor.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    case = as_VulnerabilityCase(
        id_="https://example.org/cases/full-invite-trigger",
        name="FULL-INVITE",
        attributed_to=_MANAGER,
    )
    dl.create(case)
    yield actor, dl, case.id_, case.genesis_hash
    dl.clear_all()
    dl.close()
    reset_datalayer(actor.id_)


def _hold_invite(dl, actor, case_id: str, floor: LedgerPosition) -> str:
    invite = rm_invite_to_full_case_activity(
        actor,
        case_id,
        floor,
        actor=_MANAGER,
        to=[actor.id_],
        id_=f"{case_id}/invitations/full-{floor.log_index}",
    )
    archive_received(dl, invite)
    return invite.id_


def _run(use_case, request, dl):
    return use_case(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.spec("CM-11-011")
@pytest.mark.parametrize(("use_case", "request_class", "kind"), _CASES)
def test_reply_carries_the_participants_own_position(
    participant, use_case, request_class, kind
) -> None:
    """An empty ledger is at its floor, so the reply is sent at (-1, genesis)."""
    actor, dl, case_id, genesis = participant
    floor = LedgerPosition(log_index=-1, entry_hash=genesis)
    invite_id = _hold_invite(dl, actor, case_id, floor)

    result = _run(
        use_case,
        request_class(actor_id=actor.id_, invite_id=invite_id),
        dl,
    )

    activity = activity_of(result)
    assert activity["type"] == kind
    assert activity["to"] == [_MANAGER]
    assert LedgerPosition.model_validate_json(
        activity["content"]
    ) == LedgerPosition(log_index=-1, entry_hash=genesis)
    assert json.loads(activity["content"]) == {
        "logIndex": -1,
        "entryHash": genesis,
    }


@pytest.mark.spec("SYNC-10-004")
@pytest.mark.parametrize(("use_case", "request_class", "kind"), _CASES)
def test_reply_fails_closed_until_the_ledger_reaches_the_floor(
    participant, use_case, request_class, kind
) -> None:
    actor, dl, case_id, _genesis = participant
    invite_id = _hold_invite(
        dl, actor, case_id, LedgerPosition(log_index=4, entry_hash="ab" * 32)
    )

    with pytest.raises(VultronInvalidStateTransitionError, match="caught up"):
        _run(
            use_case,
            request_class(actor_id=actor.id_, invite_id=invite_id),
            dl,
        )
    assert dl.outbox_list() == []


@pytest.mark.spec("CM-11-011")
def test_reply_to_something_that_is_not_a_full_case_invite_is_refused(
    participant,
) -> None:
    actor, dl, case_id, _genesis = participant
    stub_like = rm_invite_to_full_case_activity(
        actor,
        case_id,
        LedgerPosition(log_index=-1, entry_hash="ab" * 32),
        actor=_MANAGER,
    )
    stub_like = stub_like.model_copy(update={"content": None})
    dl.create(stub_like)

    with pytest.raises(VultronValidationError, match="full-case Invite"):
        _run(
            SvcAcceptFullCaseInviteUseCase,
            AcceptFullCaseInviteTriggerRequest(
                actor_id=actor.id_, invite_id=stub_like.id_
            ),
            dl,
        )


@pytest.mark.spec("SYNC-10-004")
def test_reply_fails_closed_with_409_when_the_tail_cannot_be_read(
    participant, monkeypatch
) -> None:
    """An unreadable ledger tail is a retryable refusal, never a 422."""
    from vultron.core.use_cases.triggers import full_case_invite as module

    actor, dl, case_id, genesis = participant
    invite_id = _hold_invite(
        dl, actor, case_id, LedgerPosition(log_index=-1, entry_hash=genesis)
    )

    def _unreadable(*_args, **_kwargs):
        raise VultronValidationError("genesis hash unavailable")

    monkeypatch.setattr(module, "ledger_tail_position", _unreadable)

    with pytest.raises(VultronInvalidStateTransitionError, match="caught up"):
        _run(
            SvcAcceptFullCaseInviteUseCase,
            AcceptFullCaseInviteTriggerRequest(
                actor_id=actor.id_, invite_id=invite_id
            ),
            dl,
        )
    assert dl.outbox_list() == []
