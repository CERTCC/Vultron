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
"""A failed received act is answered with a fault and runs again (#4981).

A received embargo act commits its own entry with its consequences, or none
of them (ADR-0151).  When the act fails, only intake's archive of the
activity (``ReceivedActivityRecord``) is kept, and the inbox answers the
sender with an internal-error ``Create(ProcessingFault)`` (ASK-07-010).
Through the FastAPI inbox the archive makes the ingress adapter treat the
next post of the same body as a redelivery (IE-10-001), so these tests check
that the rebuilt activity still commits as a first delivery would, and that
the redelivery of a committed act is still a repeat.

The CASE_MANAGER is served by a real app; the replica is a second store fed
the bodies the CASE_MANAGER's outbox delivers (TB-06-007).
"""

import json
import logging
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from test.adapters.driving.fastapi._redelivery import (
    assert_routed_as_archived_redelivery,
    faults,
    post,
    served_store,
)
from test.core.use_cases.received._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)
from test.support.emitter import RecordingEmitter
from test.support.ledger import fail_commits, ledger_entries
from test.support.ledger_rebuild import case_file_differences
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR,
)
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
# The members every serialized object carries; anything else is fault content.
_AS2_OBJECT_ENVELOPE = {"@context", "id", "type", "published", "updated"}


@pytest.fixture
def served_manager():
    """The CASE_MANAGER's store served by a real app, plus its network."""
    net = LedgerNetwork("https://example.org/cases/failed-act-redelivery")
    with served_store(net.stores[MANAGER], MANAGER, "Coordinator") as (
        client,
        emitter,
    ):
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
    post(client, _INBOX, body)


def _assert_answered_with_an_internal_error_fault(
    emitter: RecordingEmitter, failed_id: str
) -> dict[str, Any]:
    """The only delivery is the fault to the sender (ASK-07-010)."""
    assert [to for _body, to in emitter.sent] == [[PROPOSER]]
    (fault,) = faults(emitter)
    assert fault["actor"] == MANAGER
    # The class and the failed activity, and nothing else: no diagnostics
    # (ASK-07-006).
    assert fault["object"]["failureClass"] == (
        VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR
    )
    assert fault["object"]["inReplyTo"] == failed_id
    assert set(fault["object"]) - _AS2_OBJECT_ENVELOPE == {
        "failureClass",
        "inReplyTo",
    }
    assert "commit failed" not in json.dumps(fault), "the cause is not sent"
    return fault


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
@pytest.mark.spec("CLP-10-017")
@pytest.mark.spec("IE-10-001")
@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("HP-06-003")
@pytest.mark.spec("ASK-07-010")
@pytest.mark.spec("ASK-07-011")
@pytest.mark.spec("ASK-07-006")
def test_a_failed_proposal_is_applied_when_posted_again(
    served_manager, caplog: pytest.LogCaptureFixture
):
    """The first two posts fail, keep nothing and are answered with one
    fault; the third applies the act."""
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
    participants = len(net.case(MANAGER).actor_participant_index)
    assert _held_rows(net, MANAGER, revision_id) == [None] * participants
    assert net.case(MANAGER).em_state == EM.ACTIVE
    # The sender is answered with the internal-error fault, after the
    # rollback, so the fault is kept; nobody else gets anything.  Like every
    # fault the inbox sends, it is not ledgered: the entries above are
    # unchanged (ASK-07-008 is Concern #4800).
    fault = _assert_answered_with_an_internal_error_fault(emitter, body["id"])
    errors = [
        r
        for r in caplog.records
        if r.levelno >= logging.ERROR and body["id"] in r.getMessage()
    ]
    # One ERROR record names the failed act and its sender (HP-06-003); the
    # bridge's own record of the raising node names neither (ADR-0151).
    assert len(errors) == 1, [r.getMessage() for r in errors]
    assert PROPOSER in errors[0].getMessage()
    assert errors[0].exc_info is not None
    # The outcome is rejected, and that is logged with the receiver's id.
    assert any(
        r.levelno == logging.WARNING
        and "Inbox activity rejected" in r.getMessage()
        and body["id"] in r.getMessage()
        and MANAGER in r.getMessage()
        for r in caplog.records
    ), "the failed act's outcome is rejected"

    # A second failing post of the same body builds no second fault: the
    # fault id derives from the failed activity and the class, so the same
    # sealed fault is queued and sent again, same id and same body, which the
    # sender deduplicates (ID-04-004, ID-04-005).
    _fail_the_relay(client, body)
    assert [to for _body, to in emitter.sent] == [[PROPOSER], [PROPOSER]]
    assert all(f == fault for f in faults(emitter)), "the same fault"
    assert len(faults(emitter)) == len(emitter.sent)
    assert [
        e.id_ for e in ledger_entries(manager_dl, net.case_id)
    ] == entries_before
    emitter.sent.clear()

    caplog.clear()
    with caplog.at_level(logging.INFO):
        _post(client, body)

    assert_routed_as_archived_redelivery(caplog, body["id"])
    assert faults(emitter) == [], "the applied act is answered by no fault"
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
    assert_routed_as_archived_redelivery(caplog, body["id"])
    assert any(
        body["id"] in r.getMessage()
        and f"disposition={HandlerDisposition.SKIPPED}" in r.getMessage()
        for r in caplog.records
    ), "the repeat is answered SKIPPED"
