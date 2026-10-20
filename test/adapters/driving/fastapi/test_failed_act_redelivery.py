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
"""A failed received act runs again when its activity is posted again (#4986).

A received embargo act commits its own entry with its consequences, or none
of them (ADR-0151).  When the act fails, only intake's archive of the
activity (``ReceivedActivityRecord``) is kept.  Through the FastAPI inbox the
archive makes the ingress adapter treat the next post of the same body as a
redelivery (IE-10-001), so these tests check that the rebuilt activity still
commits as a first delivery would, and that the redelivery of a committed act
is still a repeat.

The CASE_MANAGER is served by a real app; the replica is a second store fed
the bodies the CASE_MANAGER's outbox delivers (TB-06-007).
"""

import json
import logging
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from test.core.use_cases.received._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)
from test.support.ledger import fail_commits, ledger_entries
from test.support.ledger_rebuild import case_file_differences
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.actor import CoreActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

pytestmark = pytest.mark.integration

_INBOX = "/api/v2/actors/coord/inbox/"
_PROPOSAL_ENTRY = "invite_to_embargo_on_case"


class _RecordingEmitter:
    """Keeps every body the CASE_MANAGER's outbox delivers, and to whom."""

    def __init__(self) -> None:
        self.sent: list[tuple[dict[str, Any], list[str]]] = []

    async def emit(
        self, activity_id: str, json_body: str, recipients: list[str]
    ) -> None:
        self.sent.append((json.loads(json_body), list(recipients)))

    def to(self, recipient: str) -> list[dict[str, Any]]:
        return [body for body, to in self.sent if recipient in to]


@pytest.fixture
def served_manager():
    """The CASE_MANAGER's store served by a real app, plus its network."""
    net = LedgerNetwork("https://example.org/cases/failed-act-redelivery")
    manager_dl = net.stores[MANAGER]
    manager_dl.create(
        object_to_record(
            CoreActor(
                id_=MANAGER,
                name="Coordinator",
                inbox=f"{MANAGER}/inbox",
                outbox=f"{MANAGER}/outbox",
            )
        )
    )
    app = create_app(docs_url=None, openapi_url=None)
    app.dependency_overrides[get_actor_dl] = lambda actor_id: manager_dl
    emitter = _RecordingEmitter()
    with TestClient(app) as client:
        app.state.emitter = emitter
        yield client, net, emitter


def _proposal_body(net: LedgerNetwork) -> tuple[dict[str, Any], str]:
    """PROPOSER's revision, sent to the CASE_MANAGER only (EP-09-001)."""
    revision = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/revision",
        content="Longer terms",
        context=net.case_id,
        end_time=days_from_now_utc(90),
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=net.case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{net.case_id}/embargo_proposals/revision",
    )
    return json.loads(dump_outbound_body(proposal)), revision.id_


def _held_rows(net: LedgerNetwork, actor_id: str, embargo_id: str) -> list:
    """Every participant's consent row for *embargo_id* in *actor_id*'s store."""
    case = net.case(actor_id)
    rows = []
    for participant_id in case.actor_participant_index.values():
        participant = cast(
            CaseParticipant, net.stores[actor_id].read(str(participant_id))
        )
        rows.append(participant.held_row(embargo_id))
    return rows


def _post(client: TestClient, body: dict[str, Any]) -> None:
    response = client.post(_INBOX, json=body)
    assert response.status_code == 202, response.text


def _assert_routed_as_archived_redelivery(
    caplog: pytest.LogCaptureFixture, activity_id: str
) -> None:
    """The ingress adapter found intake's archive and rebuilt the activity.

    Without this the test could pass on a path that never meets the archive
    (IE-10-001).
    """
    assert any(
        activity_id in r.getMessage()
        and "already held (archived)" in r.getMessage()
        for r in caplog.records
    ), "the post was not routed as a redelivery"


def _fail_the_relay(client: TestClient, body: dict[str, Any]) -> None:
    """Post *body* while the second relayed Invite's commit fails."""
    with pytest.MonkeyPatch.context() as mp:
        failed = fail_commits(
            mp,
            commit_tree,
            allowed=1,
            when=lambda kw: (
                kw["semantic_type"] == _PROPOSAL_ENTRY
                and kw["object_id"] != body["id"]
            ),
        )
        _post(client, body)
    assert len(failed) == 2, "the relay failed part-way, after one Invite"


@pytest.mark.spec("CLP-07-015")
@pytest.mark.spec("IE-10-001")
@pytest.mark.spec("CM-23-016")
def test_a_failed_proposal_is_applied_when_posted_again(
    served_manager, caplog: pytest.LogCaptureFixture
):
    """The first post fails and keeps nothing; the second applies the act."""
    client, net, emitter = served_manager
    body, revision_id = _proposal_body(net)
    manager_dl = net.stores[MANAGER]
    entries_before = [e.id_ for e in ledger_entries(manager_dl, net.case_id)]

    with caplog.at_level(logging.INFO):
        _fail_the_relay(client, body)

    # The act kept nothing; only intake's archive of the activity stands.
    assert isinstance(
        manager_dl.read(ReceivedActivityRecord.build_id(body["id"])),
        ReceivedActivityRecord,
    )
    assert [
        e.id_ for e in ledger_entries(manager_dl, net.case_id)
    ] == entries_before
    assert _held_rows(net, MANAGER, revision_id) == [None] * 4
    assert net.case(MANAGER).em_state == EM.ACTIVE
    # The sender gets no notice, and nobody else gets anything (ADR-0151).
    assert emitter.sent == []
    errors = [
        r
        for r in caplog.records
        if r.levelno >= logging.ERROR and body["id"] in r.getMessage()
    ]
    assert len(errors) == 1, [r.getMessage() for r in errors]
    assert PROPOSER in errors[0].getMessage()

    caplog.clear()
    with caplog.at_level(logging.INFO):
        _post(client, body)

    _assert_routed_as_archived_redelivery(caplog, body["id"])
    # The redelivery ran as a first delivery: the proposal's entry and one
    # relayed Invite per other participant are committed.
    new_entries = [
        e
        for e in ledger_entries(manager_dl, net.case_id)
        if e.id_ not in entries_before
    ]
    assert [e.semantic_type for e in new_entries].count(
        _PROPOSAL_ENTRY
    ) == 1 + len((OWNER, BYSTANDER))
    assert net.case(MANAGER).em_state == EM.REVISE
    assert None not in _held_rows(net, MANAGER, revision_id)
    for recipient in (OWNER, BYSTANDER):
        invites = [b for b in emitter.to(recipient) if b["type"] == "Invite"]
        assert len(invites) == 1, recipient
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR], (
        "the redelivery is no failure"
    )

    # The replica copies the act from what the CASE_MANAGER delivered, and
    # holds the same rows (CM-23-016).
    for delivered in emitter.to(BYSTANDER):
        verdict = net.receive(BYSTANDER, delivered)
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            delivered["type"],
            verdict.reason,
        )
    assert _held_rows(net, BYSTANDER, revision_id) == _held_rows(
        net, MANAGER, revision_id
    )
    assert (
        case_file_differences(manager_dl, net.stores[BYSTANDER], net.case_id)
        == []
    )


@pytest.mark.spec("IE-10-001")
@pytest.mark.spec("ID-04-004")
def test_a_committed_proposal_posted_again_is_skipped(
    served_manager, caplog: pytest.LogCaptureFixture
):
    """The redelivery of an applied act commits and sends nothing new."""
    client, net, emitter = served_manager
    body, _revision_id = _proposal_body(net)
    manager_dl = net.stores[MANAGER]
    _post(client, body)
    entries = [e.id_ for e in ledger_entries(manager_dl, net.case_id)]
    sent = len(emitter.sent)
    assert sent > 0, "the first post applied the act and relayed it"

    with caplog.at_level(logging.INFO):
        _post(client, body)

    assert [e.id_ for e in ledger_entries(manager_dl, net.case_id)] == entries
    assert len(emitter.sent) == sent
    _assert_routed_as_archived_redelivery(caplog, body["id"])
    assert any(
        body["id"] in r.getMessage()
        and f"disposition={HandlerDisposition.SKIPPED}" in r.getMessage()
        for r in caplog.records
    ), "the repeat is answered SKIPPED"
