#!/usr/bin/env python
"""End-to-end: a handler's verdict reaches ``InboxOutcome`` (UCORG-05-010/011).

The defect #3373 fixes is that the *chain* dropped the verdict — every link
between ``execute()`` and ``DispatchNode`` returned ``None``, so a unit test of
the disposition mapping alone could pass while the pipeline still reported
``processed``. These tests therefore drive the real links: the FastAPI ingress
and dispatch adapters, ``inbox_handler.dispatch``, ``DirectActivityDispatcher``
and the inbox BT, with only the use case itself stubbed.
"""

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

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from test.support.case_owner import CASE_OWNER_ID
from test.support.received import delivered_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    run_inbox_pipeline,
)
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.dispatcher import DirectActivityDispatcher
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.events import MessageSemantics
from vultron.core.models.use_case_result import HandlerResult
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_SENDER_ID = "https://example.org/actors/sender-chain"
_RECEIVER_ID = "https://example.org/actors/receiver-chain"
# log_if_rejected logs every rejected outcome of an inbox run, live or replayed.
_ORCHESTRATION_LOGGER = "vultron.adapters.driving.fastapi.inbox_queue_drain"
_OUTBOX_LOGGER = "vultron.adapters.driving.fastapi.outbox_handler"


@pytest.fixture(autouse=True)
def clear_actor_locks():
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


@pytest.fixture
def dl():
    """The receiving actor's own store (ADR-0073)."""
    db = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_ID)
    yield db
    db.close()


@pytest.fixture
def body() -> dict[str, Any]:
    report = as_VulnerabilityReport(
        id_="https://example.org/reports/r-chain-1", content="chain report"
    )
    activity = rm_create_report_activity(
        report, actor=_SENDER_ID, to=[_RECEIVER_ID]
    )
    return delivered_body(activity)


def _use_case_returning(verdict: HandlerResult) -> type:
    """A received use case that does nothing but return *verdict*."""

    class _StubUseCase:
        def __init__(self, dl: Any, request: Any) -> None:
            pass

        def execute(self) -> HandlerResult:
            return verdict

    return _StubUseCase


def _dispatcher_for(verdict: HandlerResult) -> DirectActivityDispatcher:
    return DirectActivityDispatcher(
        use_case_map={
            MessageSemantics.CREATE_REPORT: _use_case_returning(verdict)
        }
    )


def _process(
    dl: SqliteDataLayer,
    body: dict[str, Any],
    dispatcher: DirectActivityDispatcher,
) -> InboxOutcome:
    """Run one payload through the real FastAPI adapters and the inbox BT."""
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_RECEIVER_ID, dispatcher=dispatcher
        ),
    )


@pytest.mark.spec("UCORG-05-011")
def test_refused_handler_yields_rejected_with_its_reason(dl, body):
    outcome = _process(
        dl, body, _dispatcher_for(HandlerResult.refused("not a participant"))
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason == "not a participant"


@pytest.mark.spec("UCORG-05-011")
@pytest.mark.parametrize(
    "verdict", [HandlerResult.applied(), HandlerResult.skipped("duplicate")]
)
def test_applied_or_skipped_handler_yields_processed(dl, body, verdict):
    outcome = _process(dl, body, _dispatcher_for(verdict))

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    assert outcome.failure_reason is None


@pytest.mark.spec("UCORG-05-011")
def test_deferred_handler_yields_deferred(dl, body):
    outcome = _process(
        dl, body, _dispatcher_for(HandlerResult.deferred("awaiting entry 3"))
    )

    assert outcome.status is InboxOutcomeStatus.DEFERRED
    assert outcome.failure_reason == "awaiting entry 3"


@pytest.mark.spec("HP-05-002")
def test_remove_embargo_naming_no_case_is_refused_by_its_handler(dl):
    """A ``Remove(EmbargoEvent)`` with no ``origin`` names no case to act on.

    Its pattern requires no case field, so it still routes to the Remove
    handler, which reads the case from ``origin`` alone and refuses it. The
    verdict is the handler's own, reached through the production dispatcher;
    the dispatcher refuses nothing.
    """
    from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
    from vultron.core.states.embargo_register import TerminationReason
    from vultron.wire.as2.factories import remove_embargo_from_case_activity
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    remove = remove_embargo_from_case_activity(
        as_EmbargoEvent(
            id_="https://example.org/embargoes/e-chain-1",
            context="https://example.org/cases/c-chain-remove",
            end_time=days_from_now_utc(45),
        ),
        reason=TerminationReason.EARLY,
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
    )
    body = _wire_body(remove)
    assert "origin" not in body

    outcome = process_payload(
        body,
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_RECEIVER_ID, dispatcher=make_dispatcher()
        ),
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason == (
        "Remove(EmbargoEvent) is missing its embargo id or case id"
    )


@pytest.mark.spec("UCORG-05-012")
@pytest.mark.spec("SE-05-002")
def test_unhandled_semantics_is_not_processed(dl, body):
    outcome = _process(dl, body, DirectActivityDispatcher(use_case_map={}))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert (
        outcome.failure_reason
        == "No use case found for semantics 'create_report'"
    )


class _RaisingUseCase:
    """A received use case that fails, so the inbox answers with a fault."""

    def __init__(self, dl: Any, request: Any) -> None:
        pass

    def execute(self) -> HandlerResult:
        raise RuntimeError("handler blew up")


def test_a_raised_dispatch_leaves_a_fault_in_the_outbox(dl, body):
    """Control: the outbox does record the fault a raise sends.

    So the empty outbox the no-use-case test asserts is evidence, not a
    property of this fixture.
    """
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: _RaisingUseCase}
    )

    outcome = _process(dl, body, dispatcher)

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.unhandled is False
    assert dl.outbox_list() != []


@pytest.mark.spec("SE-05-002")
@pytest.mark.spec("IO-01-005")
def test_unhandled_semantics_is_reported_not_raised(dl, body, caplog):
    """A recognized type no use case handles is a normal outcome (AC-2).

    It is reported at INFO naming the activity and its sender, with no
    traceback anywhere, and the sender is answered with neither a fault nor
    a ``Reject``: the receiver does not handle the message, which does not
    make the message invalid (ADR-0140 item 5).
    """
    caplog.set_level(logging.DEBUG)

    outcome = _process(dl, body, DirectActivityDispatcher(use_case_map={}))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.unhandled is True
    assert dl.outbox_list() == []
    assert [r for r in caplog.records if r.exc_info] == []
    [record] = [
        r
        for r in caplog.records
        if r.name == "vultron.core.dispatcher"
        and "No use case found" in r.getMessage()
    ]
    assert record.levelno == logging.INFO
    assert body["id"] in record.getMessage()
    assert _SENDER_ID in record.getMessage()


@pytest.mark.spec("IO-01-005")
def test_a_handler_refusal_is_not_unhandled(dl, body):
    outcome = _process(
        dl, body, _dispatcher_for(HandlerResult.refused("not a participant"))
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.unhandled is False


def _run_pipeline(
    dl: SqliteDataLayer, body: dict[str, Any], verdict: HandlerResult
) -> None:
    emitter = AsyncMock()
    asyncio.run(
        run_inbox_pipeline(
            body, dl, _RECEIVER_ID, _dispatcher_for(verdict), emitter
        )
    )


def _orchestration_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == _ORCHESTRATION_LOGGER and r.levelno >= logging.WARNING
    ]


@pytest.mark.spec("UCORG-05-013")
def test_pipeline_logs_a_rejection_above_debug(dl, body, caplog):
    with caplog.at_level(logging.WARNING, logger=_ORCHESTRATION_LOGGER):
        _run_pipeline(dl, body, HandlerResult.refused("not a participant"))

    [message] = _orchestration_warnings(caplog)
    assert "not a participant" in message
    assert _RECEIVER_ID in message
    assert f"activity_id={body['id']}" in message
    assert "replayed=False" in message


@pytest.mark.spec("UCORG-05-013")
def test_pipeline_logs_a_rejected_replay_above_debug(dl, body, caplog):
    """A replayed item that is rejected is surfaced like a fresh one."""
    dl.inbox_append("https://example.org/activities/never-stored")

    with caplog.at_level(logging.WARNING, logger=_ORCHESTRATION_LOGGER):
        _run_pipeline(dl, body, HandlerResult.applied())

    [message] = _orchestration_warnings(caplog)
    assert "replayed=True" in message
    assert _RECEIVER_ID in message


@pytest.mark.spec("UCORG-05-013")
@pytest.mark.parametrize(
    "verdict",
    [HandlerResult.applied(), HandlerResult.deferred("awaiting entry 3")],
)
def test_pipeline_does_not_warn_for_routine_outcomes(
    dl, body, caplog, verdict
):
    with caplog.at_level(logging.WARNING, logger=_ORCHESTRATION_LOGGER):
        _run_pipeline(dl, body, verdict)

    assert _orchestration_warnings(caplog) == []


@pytest.mark.spec("IO-01-005")
@pytest.mark.spec("SE-05-002")
def test_pipeline_reports_no_use_case_found_at_info_only(dl, body, caplog):
    """Through the driving adapter, no logger reports it at WARNING or above.

    The adapter logs a rejected outcome at WARNING, except an unhandled one,
    which it logs at INFO (IO-01-005).
    """
    caplog.set_level(logging.DEBUG)
    asyncio.run(
        run_inbox_pipeline(
            body,
            dl,
            _RECEIVER_ID,
            DirectActivityDispatcher(use_case_map={}),
            AsyncMock(),
        )
    )

    # The outbox drain after every delivery warns that this fixture stores
    # no receiver actor; that is about the fixture, not the activity.
    loud = [
        f"{r.name}: {r.getMessage()}"
        for r in caplog.records
        if r.levelno >= logging.WARNING and r.name != _OUTBOX_LOGGER
    ]
    assert loud == []
    [notice] = [
        r
        for r in caplog.records
        if r.name == _ORCHESTRATION_LOGGER
        and "Inbox activity not handled" in r.getMessage()
    ]
    assert notice.levelno == logging.INFO
    assert _RECEIVER_ID in notice.getMessage()
    assert f"activity_id={body['id']}" in notice.getMessage()
    assert "No use case found" in notice.getMessage()


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("UCORG-05-011")
def test_real_handler_refusal_reaches_inbox_outcome(dl):
    """#2255: a real received handler's refusal is not reported as processed.

    Every link above is exercised with a stub use case; this drives the real
    ``AnnounceVulnerabilityCaseReceivedUseCase``, whose trust check used to log
    "rejected" and then return ``applied()`` — so the outcome said
    ``processed`` and the bootstrap replay ran for a case never seeded.
    """
    from vultron.core.use_cases.received.actor.announce import (
        AnnounceVulnerabilityCaseReceivedUseCase,
    )
    from vultron.wire.as2.factories import (
        announce_vulnerability_case_activity,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_="https://example.org/cases/c-chain-untrusted",
        name="untrusted",
    )
    announce = announce_vulnerability_case_activity(
        case, actor=_SENDER_ID, to=[_RECEIVER_ID], context=case.id_
    )
    announce_body = delivered_body(announce)
    dispatcher = DirectActivityDispatcher(
        use_case_map={
            MessageSemantics.ANNOUNCE_VULNERABILITY_CASE: (
                AnnounceVulnerabilityCaseReceivedUseCase
            )
        }
    )

    outcome = _process(dl, announce_body, dispatcher)

    assert outcome.status == InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason is not None
    assert "No CASE_MANAGER is known" in outcome.failure_reason


_MANAGER_ACT_CASE_ID = "https://example.org/cases/c-chain-manager-act"


def _case_manager_acts() -> list[Any]:
    """The CASE_MANAGER-only shapes, each as a sender would post it (#4724).

    Each is the CASE_MANAGER's own act, committed as its own ledger entry
    (CLP-07-013).  Built from the vocabulary examples, then re-addressed from
    an outside sender, so the test shows what an inbox does with one it did
    not expect.
    """
    from vultron.wire.as2.vocab.examples import case, embargo, participant

    return [
        pytest.param(build, semantics, id=semantics.value)
        for build, semantics in (
            (
                participant.create_participant,
                MessageSemantics.CREATE_CASE_PARTICIPANT,
            ),
            (
                participant.update_participant,
                MessageSemantics.UPDATE_CASE_PARTICIPANT,
            ),
            (case.update_case, MessageSemantics.UPDATE_CASE_OWNER),
            (
                embargo.create_embargo_event,
                MessageSemantics.CREATE_EMBARGO_EVENT,
            ),
            (
                embargo.create_embargo_consent,
                MessageSemantics.CREATE_EMBARGO_CONSENT,
            ),
            (
                embargo.update_embargo_consent,
                MessageSemantics.UPDATE_EMBARGO_CONSENT,
            ),
        )
    ]


@pytest.mark.spec("SE-05-002", "CLP-07-013", "VAM-01-010")
@pytest.mark.parametrize(("build", "semantics"), _case_manager_acts())
def test_a_received_case_manager_act_is_recognized_and_unhandled(
    dl, build, semantics
):
    """A CASE_MANAGER-only shape is recognized but not processed (#4724 AC-1).

    The registry labels it (ADR-0140), so the dispatcher reports "no use
    case found" (SE-05-002) rather than an unrecognized activity, and the
    inbox leaves the stored case, the ledger and the outbox as they were.
    """
    from vultron.semantic_registry import (
        find_matching_semantics,
        use_case_map,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    dl.create(
        as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_=_MANAGER_ACT_CASE_ID,
            name="original",
        )
    )
    case_before = dl.read(_MANAGER_ACT_CASE_ID)
    activity = build().model_copy(
        update={"actor": _SENDER_ID, "to": [_RECEIVER_ID]}
    )
    assert find_matching_semantics(activity) is semantics
    body = delivered_body(activity)

    outcome = _process(
        dl, body, DirectActivityDispatcher(use_case_map=use_case_map())
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.unhandled is True
    assert dl.read(_MANAGER_ACT_CASE_ID) == case_before
    assert dl.outbox_list() == []
    assert dl.list_objects("CaseLedgerEntry") == []


_RETIRED_CASE_ID = "https://example.org/cases/c-chain-create"


def _retired_create_activities() -> list[Any]:
    """The received ``Create(X)`` routes #4598 and #4707 removed, one each.

    Each addressed to the receiver and naming the case the way the removed
    pattern required.  ``Create(CaseParticipant)`` is not among them: it is
    the CASE_MANAGER's own act, which the registry recognizes (#4724), and
    neither is ``Create(EmbargoEvent)`` (VAM-05-016).  A ``Create`` of a plain
    ``Event`` is among them: only an ``EmbargoEvent`` object is recognized
    (VAM-01-010).  ``Create(Note)`` is sent
    twice: once with the note's ``context`` naming the case (the form the
    removed route attached) and once with no case context at all.
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.base.objects.object_types import (
        as_Event,
        as_Note,
    )
    from vultron.wire.as2.vocab.objects.case_status import (
        as_CaseStatus,
        as_ParticipantStatus,
    )

    participant_id = f"{_RETIRED_CASE_ID}/participants/sender"
    return [
        pytest.param(
            as_Create(
                object_=as_CaseStatus(context=_RETIRED_CASE_ID),
                context=_RETIRED_CASE_ID,
                actor=_SENDER_ID,
                to=[_RECEIVER_ID],
            ),
            id="case-status",
        ),
        pytest.param(
            as_Create(
                object_=as_ParticipantStatus(context=participant_id),
                actor=_SENDER_ID,
                to=[_RECEIVER_ID],
            ),
            id="participant-status",
        ),
        pytest.param(
            as_Create(
                object_=as_Note(
                    id_=f"{_RETIRED_CASE_ID}/notes/n-ctx",
                    content="a note naming the case",
                    context=_RETIRED_CASE_ID,
                ),
                actor=_SENDER_ID,
                to=[_RECEIVER_ID],
            ),
            id="note-with-case-context",
        ),
        pytest.param(
            as_Create(
                object_=as_Note(
                    id_="https://example.org/notes/n-no-case",
                    content="a note outside any case",
                ),
                actor=_SENDER_ID,
                to=[_RECEIVER_ID],
            ),
            id="note-without-case-context",
        ),
        pytest.param(
            as_Create(
                object_=as_Event(
                    id_=f"{_RETIRED_CASE_ID}/events/plain",
                    name="a plain event, not an embargo",
                    context=_RETIRED_CASE_ID,
                ),
                context=_RETIRED_CASE_ID,
                actor=_SENDER_ID,
                to=[_RECEIVER_ID],
            ),
            id="plain-event",
        ),
    ]


@pytest.mark.spec("CLP-07-013", "CLP-02-013", "VAM-01-010", "VAM-01-011")
@pytest.mark.parametrize("activity", _retired_create_activities())
def test_received_create_of_a_case_record_is_refused_case_unchanged(
    dl, activity
):
    """A received ``Create`` of a case record is not a protocol message (VAM-01-010, VAM-01-011).

    The protocol names one form for each act: ``Add(CaseStatus)``,
    ``Add(ParticipantStatus)``, ``Add(Note)``, and the CASE_MANAGER's own
    record of a ``CaseParticipant`` or a creation-time ``EmbargoEvent``
    (ADR-0137, VAM-05-016), which ``test_a_received_case_manager_act_is_recognized_and_unhandled``
    covers.
    Each of the record ``Create`` forms once stored its object with no ledger
    entry, which CLP-07-013 rules out (#4598); ``Create(Note)`` was a second
    way to attach a note (#4707).
    No pattern routes one that arrives in an inbox: the real dispatcher
    resolves it to ``UNKNOWN`` and the inbox refuses it, leaving the case,
    the ledger and the outbox as they were, and storing nothing from the
    inline object (#3763).
    """
    from vultron.semantic_registry import (
        find_matching_semantics,
        use_case_map,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    dl.create(
        as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, id_=_RETIRED_CASE_ID, name="unchanged"
        )
    )
    case_before = dl.read(_RETIRED_CASE_ID)
    assert find_matching_semantics(activity) is MessageSemantics.UNKNOWN
    activity_body = delivered_body(activity)

    outcome = _process(
        dl,
        activity_body,
        DirectActivityDispatcher(use_case_map=use_case_map()),
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason == "unrecognized activity semantics"
    assert dl.read(_RETIRED_CASE_ID) == case_before
    assert dl.outbox_list() == []
    assert dl.list_objects("CaseLedgerEntry") == []
    stored_case = dl.read(_RETIRED_CASE_ID)
    assert stored_case is not None and stored_case.notes == []
    assert dl.read(activity.object_.id_) is None


# ---------------------------------------------------------------------------
# Ingress stores nothing from an inline object before its handler runs (#3763)
# ---------------------------------------------------------------------------

_IMPOSTER_CASE_ID = "https://example.org/cases/c-chain-imposter"


def _case_with(
    case_id: str, name: str, participants: list[Any], **fields: Any
) -> Any:
    """A wire case whose roster and participant index list *participants*."""
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    fields.setdefault("attributed_to", CASE_OWNER_ID)
    case = as_VulnerabilityCase(
        id_=case_id, name=name, case_participants=participants, **fields
    )
    for participant in participants:
        case.actor_participant_index[participant.attributed_to] = (
            participant.id_
        )
    return case


def _self_managed_case() -> Any:
    """A case whose snapshot names the sender as its own CASE_MANAGER (#4674)."""
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole

    participant = CaseParticipant(
        id_=f"{_IMPOSTER_CASE_ID}/participants/imposter",
        attributed_to=_SENDER_ID,
        context=_IMPOSTER_CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    return _case_with(_IMPOSTER_CASE_ID, "imposter", [participant])


def _real_dispatcher() -> DirectActivityDispatcher:
    from vultron.semantic_registry import use_case_map

    return DirectActivityDispatcher(use_case_map=use_case_map())


def _wire_body(activity: BaseModel) -> dict[str, Any]:
    return delivered_body(cast(as_Activity, activity))


@pytest.mark.spec("PCR-03-004", "CBT-01-011", "CLP-10-017")
def test_untrusted_announce_case_is_refused_and_unstored(dl):
    """A refused untrusted ``Announce`` leaves no inline case behind (#3763).

    Ingress stored the inline case before the handler ran, so the trust check
    read a CASE_MANAGER from the very payload it was judging, and accepted it
    (#4674).
    """
    from vultron.wire.as2.factories import (
        announce_vulnerability_case_activity,
    )

    announce = announce_vulnerability_case_activity(
        _self_managed_case(), actor=_SENDER_ID, to=[_RECEIVER_ID]
    )

    outcome = _process(dl, _wire_body(announce), _real_dispatcher())

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason is not None
    assert "PCR-03-004" in outcome.failure_reason
    assert dl.read(_IMPOSTER_CASE_ID) is None
    assert dl.read(f"{_IMPOSTER_CASE_ID}/participants/imposter") is None


@pytest.mark.spec("CLP-10-017", "CLP-10-019")
def test_add_note_at_case_manager_stores_the_note_from_the_event(dl):
    """The CASE_MANAGER's own effect node writes the Note, not ingress."""
    from test.core.use_cases.received.conftest import (
        seed_case_participant,
        seed_store_owner_as_case_manager,
    )
    from vultron.wire.as2.factories import add_note_to_case_activity
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case = as_VulnerabilityCase(
        id_="https://example.org/cases/c-chain-note",
        name="note case",
        attributed_to=_RECEIVER_ID,
    )
    seed_store_owner_as_case_manager(dl, case)
    seed_case_participant(dl, case, _SENDER_ID)
    dl.create(case)
    note = as_Note(
        id_="https://example.org/notes/n-chain-1",
        content="a note",
        context=case.id_,
        attributed_to=_SENDER_ID,
    )
    add = add_note_to_case_activity(
        note, target=case, actor=_SENDER_ID, to=[_RECEIVER_ID]
    )

    from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher

    # The CASE_MANAGER's commit fans out, so it needs the production ports.
    outcome = process_payload(
        _wire_body(add),
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_RECEIVER_ID, dispatcher=make_dispatcher()
        ),
    )

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    stored = dl.read(note.id_)
    assert stored is not None
    assert getattr(stored, "content", None) == "a note"


@pytest.mark.spec("PCR-03-004", "CBT-01-011", "HP-01-006", "IO-03-004")
def test_untrusted_create_then_announce_both_refused_unstored(dl):
    """A refused imposter ``Create`` leaves no case to anchor its ``Announce``.

    Ingress stores nothing from either inline case (IO-03-004), so the
    imposter's bootstrap ``Create(VulnerabilityCase)`` is refused with nothing
    stored, and the ``Announce`` that follows finds no CASE_MANAGER anchor and
    is refused too. Before #4834 the refused ``Create``'s stored row anchored
    the ``Announce`` (#4674, AC-2).
    """
    from vultron.wire.as2.factories import (
        announce_vulnerability_case_activity,
        create_case_activity,
    )

    create = create_case_activity(
        _self_managed_case(),
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
        context=_IMPOSTER_CASE_ID,
    )
    announce = announce_vulnerability_case_activity(
        _self_managed_case(), actor=_SENDER_ID, to=[_RECEIVER_ID]
    )

    for activity, citation in (
        (create, "CBT-01-011"),
        (announce, "PCR-03-004"),
    ):
        outcome = _process(dl, _wire_body(activity), _real_dispatcher())

        assert outcome.status is InboxOutcomeStatus.REJECTED, (
            activity.type_,
            outcome.failure_reason,
        )
        assert outcome.failure_reason is not None
        assert citation in outcome.failure_reason, outcome.failure_reason
        assert dl.read(_IMPOSTER_CASE_ID) is None, activity.type_
        assert dl.read(f"{_IMPOSTER_CASE_ID}/participants/imposter") is None


# ---------------------------------------------------------------------------
# The legitimate first contacts still seed a replica through the inbox (#4674)
# ---------------------------------------------------------------------------

_VENDOR_ID = "https://example.org/actors/vendor-chain"
_CASE_MANAGER_ID = "https://example.org/actors/case-manager-chain"
_LEGIT_CASE_ID = "https://example.org/cases/c-chain-legit"
_LEGIT_REPORT_ID = "https://example.org/reports/r-chain-legit"


def _managed_case() -> Any:
    """The case as its CASE_MANAGER sends it: the receiver is a participant."""
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.dimensions import RmDimension
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.core.states.rm import RM
    from vultron.enums.roles import CVDRole

    manager = CaseParticipant(
        id_=f"{_LEGIT_CASE_ID}/participants/case-manager",
        attributed_to=_CASE_MANAGER_ID,
        context=_LEGIT_CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    receiver = CaseParticipant(
        id_=f"{_LEGIT_CASE_ID}/participants/receiver",
        attributed_to=_RECEIVER_ID,
        context=_LEGIT_CASE_ID,
        participant_statuses=[
            ParticipantStatus(
                context=_LEGIT_CASE_ID,
                attributed_to=_RECEIVER_ID,
                rm=RmDimension(state=RM.ACCEPTED),
            )
        ],
    )
    return _case_with(
        _LEGIT_CASE_ID,
        "legitimate",
        [manager, receiver],
        attributed_to=_VENDOR_ID,
        vulnerability_reports=[_LEGIT_REPORT_ID],
        # One creation time, so every copy has the genesis hash the held
        # case has, as the CASE_MANAGER's copies do (SYNC-16-006).
        published=datetime(2026, 10, 1, tzinfo=UTC),
    )


def _announce_from_case_manager() -> dict[str, Any]:
    from vultron.wire.as2.factories import (
        announce_vulnerability_case_activity,
    )

    return _wire_body(
        announce_vulnerability_case_activity(
            _managed_case(), actor=_CASE_MANAGER_ID, to=[_RECEIVER_ID]
        )
    )


@pytest.mark.spec("PCR-03-004", "CBT-01-006", "HP-01-006", "IO-03-004")
def test_reporter_after_bootstrap_accepts_case_manager_announce(dl):
    """A reporter's bootstrap admits only its CASE_MANAGER's ``Announce`` (#4674).

    The reporter wrote a ``ReportCaseLink`` expecting the case from the
    vendor it reported to. The vendor's bootstrap ``Create`` binds the link,
    records the CASE_MANAGER it introduces, and seeds the replica. The
    CASE_MANAGER's ``Announce`` is then admitted against what the receiver
    stored, and an imposter ``Announce`` for the same case, whose own snapshot
    names the imposter as CASE_MANAGER, is refused (AC-3).
    """
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.report import VulnerabilityReport
    from vultron.core.models.report_case_link import VultronReportCaseLink
    from vultron.core.participants.authority import (
        established_link_case_manager_id,
        resolve_case_manager_id,
    )
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.factories import (
        announce_vulnerability_case_activity,
        create_case_activity,
    )

    dl.create(
        VulnerabilityReport(id_=_LEGIT_REPORT_ID, attributed_to=_RECEIVER_ID)
    )
    dl.save(
        VultronReportCaseLink(
            report_id=_LEGIT_REPORT_ID, case_creator_id=_VENDOR_ID
        )
    )
    create = create_case_activity(
        _managed_case(),
        actor=_VENDOR_ID,
        to=[_RECEIVER_ID],
        context=_LEGIT_CASE_ID,
    )

    created = _process(dl, _wire_body(create), _real_dispatcher())

    assert created.status is InboxOutcomeStatus.PROCESSED, (
        created.failure_reason
    )
    assert (
        established_link_case_manager_id(dl, _LEGIT_CASE_ID)
        == _CASE_MANAGER_ID
    )

    announced = _process(dl, _announce_from_case_manager(), _real_dispatcher())

    assert announced.status is InboxOutcomeStatus.PROCESSED, (
        announced.failure_reason
    )

    imposter = CaseParticipant(
        id_=f"{_LEGIT_CASE_ID}/participants/imposter",
        attributed_to=_SENDER_ID,
        context=_LEGIT_CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    hijack = announce_vulnerability_case_activity(
        _case_with(_LEGIT_CASE_ID, "hijacked", [imposter]),
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
    )

    refused = _process(dl, _wire_body(hijack), _real_dispatcher())

    assert refused.status is InboxOutcomeStatus.REJECTED
    assert refused.failure_reason is not None
    assert "HP-01-006" in refused.failure_reason, refused.failure_reason
    stored = dl.read_case(_LEGIT_CASE_ID)
    assert stored is not None
    assert resolve_case_manager_id(stored, dl) == _CASE_MANAGER_ID
    assert dl.read(imposter.id_) is None


@pytest.mark.spec("PCR-03-004", "IO-03-004")
def test_late_joiner_after_accepted_invite_accepts_case_manager_announce(dl):
    """A late joiner's Invite anchors the CASE_MANAGER's ``Announce`` (#4674).

    The CASE_MANAGER's stub Invite records it as the case's trust anchor on
    receipt, and that anchor is what admits the ``Announce``. The joiner
    accepts the Invite first, as in the real flow, and the ``Announce`` the
    CASE_MANAGER then sends seeds the replica (AC-3).
    """
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
    from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
    from vultron.core.use_cases.triggers.actor import (
        SvcAcceptCaseInviteUseCase,
    )
    from vultron.core.use_cases.triggers.requests import (
        AcceptCaseInviteTriggerRequest,
    )
    from vultron.wire.as2.factories import rm_invite_to_case_activity
    from vultron.wire.as2.vocab.base.objects.actors import as_Actor

    receiver = as_Actor(id_=_RECEIVER_ID, name="receiver")
    dl.create(receiver)
    dl.create(as_Actor(id_=_CASE_MANAGER_ID, name="case manager"))
    case = _managed_case()
    case.stub_summary = "A case you are invited to join."
    invite = rm_invite_to_case_activity(
        receiver,
        target=case,
        roles=["coordinator"],
        actor=_CASE_MANAGER_ID,
        to=[_RECEIVER_ID],
        id_=f"{_LEGIT_CASE_ID}/invitations/late-joiner",
    )

    invited = _process(dl, _wire_body(invite), _real_dispatcher())

    assert invited.status is InboxOutcomeStatus.PROCESSED, (
        invited.failure_reason
    )
    anchor = dl.read(VultronPendingCaseInbox.build_id(_LEGIT_CASE_ID))
    assert isinstance(anchor, VultronPendingCaseInbox)
    assert anchor.case_actor_id == _CASE_MANAGER_ID
    assert dl.read(_LEGIT_CASE_ID) is None

    accepted = SvcAcceptCaseInviteUseCase(
        dl,
        AcceptCaseInviteTriggerRequest(
            actor_id=_RECEIVER_ID, invite_id=invite.id_
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert accepted.activity is not None
    assert accepted.activity["inReplyTo"] == invite.id_
    assert accepted.activity.get("to") == [_CASE_MANAGER_ID]

    announced = _process(dl, _announce_from_case_manager(), _real_dispatcher())

    assert announced.status is InboxOutcomeStatus.PROCESSED, (
        announced.failure_reason
    )
    assert dl.read(_LEGIT_CASE_ID) is not None
