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
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

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
from vultron.errors import UnroutableActivityError
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_SENDER_ID = "https://example.org/actors/sender-chain"
_RECEIVER_ID = "https://example.org/actors/receiver-chain"
_ORCHESTRATION_LOGGER = "vultron.adapters.driving.fastapi.inbox_orchestration"


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
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


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


@pytest.mark.spec("UCORG-05-012")
def test_unroutable_activity_is_not_processed(dl, body, monkeypatch):
    """No handler ran, so the dispatcher's synthesized verdict is a refusal."""

    def _unroutable(self: Any, event: Any, dl: Any) -> None:
        raise UnroutableActivityError(event.activity_id, "no case_id")

    monkeypatch.setattr(
        DirectActivityDispatcher, "_enforce_join_backfill_gate", _unroutable
    )

    outcome = _process(dl, body, _dispatcher_for(HandlerResult.applied()))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert "unroutable" in (outcome.failure_reason or "")


@pytest.mark.spec("UCORG-05-012")
def test_unhandled_semantics_is_not_processed(dl, body):
    outcome = _process(dl, body, DirectActivityDispatcher(use_case_map={}))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert "No use case found" in (outcome.failure_reason or "")


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
        id_="https://example.org/cases/c-chain-untrusted", name="untrusted"
    )
    announce = announce_vulnerability_case_activity(
        case, actor=_SENDER_ID, to=[_RECEIVER_ID], context=case.id_
    )
    announce_body = announce.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
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
    assert "untrusted sender" in outcome.failure_reason


@pytest.mark.spec("CLP-07-013", "CLP-02-013")
def test_received_update_vulnerability_case_is_refused_unchanged(dl):
    """#4443: a direct ``Update(VulnerabilityCase)`` has no received path.

    The wire class stays, because a CASE_MANAGER-authored ledger entry may carry
    an ``Update(VulnerabilityCase)`` snapshot, but no pattern routes one that
    arrives in an inbox: the real dispatcher resolves it to ``UNKNOWN`` and the
    inbox refuses it without touching the stored case.
    """
    from vultron.semantic_registry import (
        find_matching_semantics,
        use_case_map,
    )
    from vultron.wire.as2.factories import update_case_activity
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case_id = "https://example.org/cases/c-chain-update"
    dl.create(as_VulnerabilityCase(id_=case_id, name="original name"))
    update = update_case_activity(
        as_VulnerabilityCase(id_=case_id, name="renamed by sender"),
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
    )
    assert find_matching_semantics(update) is MessageSemantics.UNKNOWN
    update_body = update.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

    outcome = _process(
        dl, update_body, DirectActivityDispatcher(use_case_map=use_case_map())
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason == "unrecognized activity semantics"
    stored = dl.read(case_id)
    assert stored is not None
    assert stored.name == "original name"
    assert dl.outbox_list() == []
    assert dl.list_objects("CaseLedgerEntry") == []


_RETIRED_CASE_ID = "https://example.org/cases/c-chain-create"


def _retired_create_activities() -> list[Any]:
    """The four received ``Create(X)`` routes #4598 removed, one each.

    Each addressed to the receiver and naming the case the way the removed
    pattern required.  ``Create(CaseParticipant)`` is built with the factory
    the CASE_MANAGER's ledger entry still uses.
    """
    from vultron.wire.as2.factories import create_participant_activity
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )
    from vultron.wire.as2.vocab.objects.case_status import (
        as_CaseStatus,
        as_ParticipantStatus,
    )
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

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
                object_=as_EmbargoEvent(
                    context=_RETIRED_CASE_ID, end_time=days_from_now_utc(45)
                ),
                context=_RETIRED_CASE_ID,
                actor=_SENDER_ID,
                to=[_RECEIVER_ID],
            ),
            id="embargo-event",
        ),
        pytest.param(
            create_participant_activity(
                as_CaseParticipant(
                    id_=participant_id,
                    attributed_to=_SENDER_ID,
                    context=_RETIRED_CASE_ID,
                ),
                context=_RETIRED_CASE_ID,
                actor=_SENDER_ID,
                to=[_RECEIVER_ID],
            ),
            id="case-participant",
        ),
    ]


@pytest.mark.spec("CLP-07-013", "CLP-02-013", "VAM-01-010", "VAM-01-011")
@pytest.mark.parametrize("activity", _retired_create_activities())
def test_received_create_of_a_case_record_is_refused_case_unchanged(
    dl, activity
):
    """A received ``Create`` of a case record is not a protocol message (VAM-01-010, VAM-01-011).

    The protocol names one form for each act: ``Add(CaseStatus)``,
    ``Add(ParticipantStatus)``, ``Invite(Event)``, and the CASE_MANAGER's
    own consequence for a ``CaseParticipant`` (ADR-0137).
    Each of these ``Create`` forms once stored its object with no ledger
    entry, which CLP-07-013 rules out (#4598).
    The wire classes stay (a CASE_MANAGER-authored entry carries
    ``Create(CaseParticipant)``), but no pattern routes one that
    arrives in an inbox: the real dispatcher resolves it to ``UNKNOWN`` and
    the inbox refuses it, leaving the case, the ledger and the outbox as they
    were, and storing nothing from the inline object (#3763).
    """
    from vultron.semantic_registry import (
        find_matching_semantics,
        use_case_map,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    dl.create(as_VulnerabilityCase(id_=_RETIRED_CASE_ID, name="unchanged"))
    case_before = dl.read(_RETIRED_CASE_ID)
    assert find_matching_semantics(activity) is MessageSemantics.UNKNOWN
    activity_body = activity.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

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
    assert dl.read(activity.object_.id_) is None


# ---------------------------------------------------------------------------
# Ingress stores nothing from an inline object before its handler runs (#3763)
# ---------------------------------------------------------------------------

_IMPOSTER_CASE_ID = "https://example.org/cases/c-chain-imposter"


def _self_managed_case() -> Any:
    """A case whose snapshot names the sender as its own CASE_MANAGER (#4674)."""
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    participant = CaseParticipant(
        id_=f"{_IMPOSTER_CASE_ID}/participants/imposter",
        attributed_to=_SENDER_ID,
        context=_IMPOSTER_CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = as_VulnerabilityCase(
        id_=_IMPOSTER_CASE_ID, name="imposter", case_participants=[participant]
    )
    case.actor_participant_index[_SENDER_ID] = participant.id_
    return case


def _real_dispatcher() -> DirectActivityDispatcher:
    from vultron.semantic_registry import use_case_map

    return DirectActivityDispatcher(use_case_map=use_case_map())


def _wire_body(activity: BaseModel) -> dict[str, Any]:
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


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
    assert "untrusted sender" in outcome.failure_reason
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
