#!/usr/bin/env python
"""Ingress stages a delivery for routing and stores none of it (#3763, #4871).

The routed activity is rebuilt by a by-id read through a staging store that
holds the parsed activity's row and its inline objects.  Nothing staged
reaches the receiver's store (DL-06-006, IO-03-004), and a deferred activity
is held whole, its sealed body and staged rows, only until its replay.
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

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.datalayer_sqlite.engine import (
    actor_db_url,
    scratch_memory_url,
)
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
    FastAPIQueuePort,
    StoredActivityIngressAdapter,
)
from vultron.adapters.driving.fastapi.inbox_pending_queue import (
    _expire_pending_case_activities,
)
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
    _stage_inline_object,
    _StagingStore,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.errors import VultronWiringError
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseStub,
)

_SENDER_ID = "https://example.org/actors/sender-staging"
_RECEIVER_ID = "https://example.org/actors/receiver-staging"
_CASE_ID = "https://example.org/cases/c-staging"
_NOTE_ID = "https://example.org/notes/n-staging"
_ACTOR_URI = "https://example.org/actors/alice"


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    """The receiving actor's own store (ADR-0073)."""
    db = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_ID)
    yield db
    db.close()


def _add_note_body(content: str = "staged") -> dict[str, Any]:
    note = as_Note(id_=_NOTE_ID, content=content, context=_CASE_ID)
    activity = add_note_to_case_activity(
        note,
        target=_CASE_ID,
        context=_CASE_ID,
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
    )
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


def _routed(dl: SqliteDataLayer, body: dict[str, Any], **kwargs: Any) -> Any:
    ingress = FastAPIIngressAdapter(dl=dl, **kwargs)
    parsed = ingress.parse(body)
    assert parsed is not None
    return ingress.rehydrate(parsed)


@pytest.mark.spec("CLP-10-017", "IO-03-004", "DL-06-006")
def test_rehydrate_routes_the_inline_object_without_storing_it(dl):
    routed = _routed(dl, _add_note_body())

    assert getattr(routed.object_, "id_", None) == _NOTE_ID
    assert getattr(routed.object_, "content", None) == "staged"
    assert dl.read(_NOTE_ID) is None
    assert dl.read(routed.id_) is None, "nor is the activity itself"
    assert sum(dl.count_all().values()) == 0, "nothing at all is written"


@pytest.mark.spec("IO-03-004")
def test_rehydrate_routes_the_receivers_own_copy_over_the_inline_one(dl):
    """A held object wins, as it did when ingress skipped a duplicate."""
    dl.create(as_Note(id_=_NOTE_ID, content="held", context=_CASE_ID))

    routed = _routed(dl, _add_note_body(content="sender's"))

    assert getattr(routed.object_, "content", None) == "held"


@pytest.mark.spec("IO-03-004", "CBT-03-001", "DL-06-006", "VM-08-002")
def test_deferred_activity_replays_with_its_inline_object(dl):
    staging = InlineObjectStaging(dl)
    queue = FastAPIQueuePort(
        dl=dl, actor_dl=dl, actor_id=_RECEIVER_ID, staging=staging
    )
    body = _add_note_body()
    routed = _routed(dl, body, staging=staging)
    queue.queue(activity_id=routed.id_, case_id=_CASE_ID)
    held = dl.read(DeferredInboxActivity.build_id(routed.id_))
    assert isinstance(held, DeferredInboxActivity)
    assert held.received_body is not None
    assert json.loads(held.received_body) == body, "held as it arrived"
    assert held.activity_row_json is None
    assert dl.read(routed.id_) is None, "never under the sender's id"

    dl.create(as_VulnerabilityCase(id_=_CASE_ID, name="arrived"))
    queue.replay(_CASE_ID)
    replay_id = dl.inbox_pop()
    assert replay_id == routed.id_
    replayed = StoredActivityIngressAdapter(dl=dl, staging=staging).parse(
        replay_id
    )

    assert replayed is not None
    assert getattr(getattr(replayed, "object_", None), "content", None) == (
        "staged"
    )
    assert replayed.received_evidence == body, "the first delivery's evidence"
    assert dl.read(_NOTE_ID) is None
    assert dl.read(DeferredInboxActivity.build_id(routed.id_)) is None


@pytest.mark.spec("IO-03-004", "CBT-03-003")
def test_expired_queue_drops_the_inline_objects_held_for_replay(dl):
    staging = InlineObjectStaging(dl)
    queue = FastAPIQueuePort(
        dl=dl, actor_dl=dl, actor_id=_RECEIVER_ID, staging=staging
    )
    routed = _routed(dl, _add_note_body(), staging=staging)
    queue.queue(activity_id=routed.id_, case_id=_CASE_ID)
    pending = dl.read(VultronPendingCaseInbox.build_id(_CASE_ID))
    assert isinstance(pending, VultronPendingCaseInbox)
    dl.save(
        pending.model_copy(
            update={"queued_at": datetime.now(UTC) - timedelta(days=30)}
        )
    )

    expired = _expire_pending_case_activities(
        case_id=_CASE_ID,
        actor_id=_RECEIVER_ID,
        dl=dl,
        queue_dl=dl,
        timeout_seconds=1,
    )

    assert expired is True
    assert dl.read(DeferredInboxActivity.build_id(routed.id_)) is None


@pytest.mark.spec("IO-03-004")
def test_staging_store_is_empty_after_a_rebuild(dl):
    """A delivery's staged objects do not outlive its rebuild."""
    _routed(dl, _add_note_body())

    assert _StagingStore(dl, "urn:uuid:next").read(_NOTE_ID) is None


@pytest.mark.spec("IO-03-004")
def test_staging_store_is_emptied_when_the_rebuild_raises(dl):
    """A failed rebuild leaves nothing staged for the next delivery."""
    body = _add_note_body()
    parsed = FastAPIIngressAdapter(dl=dl).parse(body)
    assert parsed is not None
    staging = InlineObjectStaging(dl)

    def _stage_then_fail(store: Any) -> None:
        store.create(as_Note(id_=_NOTE_ID, content="staged", context=_CASE_ID))
        raise RuntimeError("rebuild failed")

    with pytest.raises(RuntimeError, match="rebuild failed"):
        staging._rehydrate(parsed.id_, _stage_then_fail, received_body=None)

    assert _StagingStore(dl, "urn:uuid:next").read(_NOTE_ID) is None


@pytest.mark.spec("IO-03-004")
def test_a_later_bare_reference_does_not_see_an_earlier_staged_object(dl):
    """One sender's staged object never routes another delivery."""
    first = _add_note_body()
    _routed(dl, first)
    bare = {**first, "id": "https://example.org/activities/bare-add"}
    bare["object"] = _NOTE_ID

    routed = _routed(dl, bare)

    assert routed.object_ == _NOTE_ID


@pytest.mark.spec("IO-03-004", "CBT-03-003")
def test_held_rows_are_released_when_the_replay_rebuild_raises(
    dl, monkeypatch
):
    """The replay already left the queue, so its held record goes regardless."""
    staging = InlineObjectStaging(dl)
    queue = FastAPIQueuePort(
        dl=dl, actor_dl=dl, actor_id=_RECEIVER_ID, staging=staging
    )
    routed = _routed(dl, _add_note_body(), staging=staging)
    queue.queue(activity_id=routed.id_, case_id=_CASE_ID)
    held_id = DeferredInboxActivity.build_id(routed.id_)
    assert dl.read(held_id) is not None

    def _fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("rebuild failed")

    monkeypatch.setattr(staging, "_rehydrate", _fail)
    with pytest.raises(RuntimeError, match="rebuild failed"):
        staging.rehydrate_deferred(routed.id_)

    assert dl.read(held_id) is None


def test_staging_store_never_shares_an_actor_store_name():
    """A slug never contains ``~``, so no actor resolves to the staging name."""
    staging = actor_db_url(
        scratch_memory_url("sqlite:///:memory:", "inbox-staging"), "x"
    )
    lookalike = actor_db_url("sqlite:///:memory:", "inbox-staging-x")

    assert staging != lookalike
    assert staging.startswith("sqlite:///file:vultron-")


# ---------------------------------------------------------------------------
# _stage_inline_object stages what the parser produced (MV-11-005)
# ---------------------------------------------------------------------------
#
# These replace the tests of ``_reparse_as_specific_type``, which re-validated
# an inline object from the raw request body and was deleted by #3922.  Each
# drives a raw body through ``parse_activity`` — the only door inbound data
# enters by — and asserts that the object it stages is the parsed one.

_PUBLISHED = "2026-03-04T05:06:07+00:00"


def _parsed_announce(inline: dict[str, Any]) -> as_Announce:
    activity = parse_activity(_announce_body(inline))
    assert isinstance(activity, as_Announce)
    return activity


def _announce_body(inline: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Announce",
        "id": "https://example.org/activities/announce-1",
        "actor": _ACTOR_URI,
        "published": _PUBLISHED,
        "object": inline,
    }


@pytest.fixture
def persisted(monkeypatch) -> list[object]:
    """Capture every object ``_stage_inline_object`` hands to storage."""
    from vultron.adapters import inbox_staging

    captured: list[object] = []
    real_object_to_record = inbox_staging.object_to_record

    def _spy(obj):
        captured.append(obj)
        return real_object_to_record(obj)

    monkeypatch.setattr(inbox_staging, "object_to_record", _spy)
    return captured


@pytest.mark.spec("MV-11-005")
def test_stage_inline_object_stages_the_parsed_inline_case(
    datalayer, persisted
):
    """A full inline case is stored as the ``VulnerabilityCase`` parsed."""
    activity = _parsed_announce(
        {
            "type": "VulnerabilityCase",
            "id": "urn:uuid:case-parsed-001",
            "name": "Parsed Case",
        }
    )

    _stage_inline_object(datalayer, activity)

    assert persisted == [activity.object_]
    assert type(persisted[0]) is as_VulnerabilityCase
    stored = datalayer.read("urn:uuid:case-parsed-001")
    assert isinstance(stored, VulnerabilityCase)


@pytest.mark.spec("EMB-18-003")
def test_stage_inline_object_stages_the_inline_embargo_a_case_names(
    datalayer,
):
    """An inline active embargo is held as a record beside the case."""
    case_id = "urn:uuid:case-embargo-001"
    embargo_id = f"{case_id}/embargo_events/e1"
    activity = _parsed_announce(
        {
            "type": "VulnerabilityCase",
            "id": case_id,
            "name": "Embargoed Case",
            "embargoRegister": [
                {
                    "embargo": {
                        "type": "EmbargoEvent",
                        "id": embargo_id,
                        "context": case_id,
                        "startTime": _PUBLISHED,
                        "endTime": "2099-01-01T00:00:00+00:00",
                    },
                    "status": "ACTIVE",
                }
            ],
        }
    )

    _stage_inline_object(datalayer, activity)

    assert isinstance(datalayer.read(embargo_id), EmbargoEvent)
    assert isinstance(datalayer.read(case_id), VulnerabilityCase)


@pytest.mark.spec("EMB-18-003")
def test_stage_inline_object_skips_a_case_naming_an_unheld_embargo(
    datalayer, caplog
):
    """A bare embargo id this store cannot read keeps the case out of it."""
    case_id = "urn:uuid:case-embargo-002"
    activity = _parsed_announce(
        {
            "type": "VulnerabilityCase",
            "id": case_id,
            "name": "Unheld Embargo Case",
            "embargoRegister": [
                {
                    "embargo": f"{case_id}/embargo_events/unheld",
                    "status": "ACTIVE",
                }
            ],
        }
    )

    with caplog.at_level(logging.WARNING):
        _stage_inline_object(datalayer, activity)

    assert datalayer.read(case_id) is None
    assert any("EMB-18-003" in r.getMessage() for r in caplog.records)


@pytest.mark.spec("MV-11-005")
def test_stage_inline_object_stages_the_parsed_case_stub(datalayer, persisted):
    """A case stub is stored as the ``as_VulnerabilityCaseStub`` parsed."""
    activity = _parsed_announce(
        {
            "type": "VulnerabilityCaseStub",
            "caseId": "urn:uuid:case-stub-001",
            "summary": "Security issue — details shared after acceptance",
        }
    )
    assert type(activity.object_) is as_VulnerabilityCaseStub

    _stage_inline_object(datalayer, activity)

    assert persisted == [activity.object_]


@pytest.mark.spec("MV-11-005")
@pytest.mark.spec("MV-11-003")
def test_stage_inline_object_stages_parsed_class_after_a_set_aside_key(
    datalayer, persisted, caplog
):
    """A set-aside foreign key does not demote the stored class (#3922).

    The retired re-parse validated the raw body again, met the key the parse
    edge had set aside, failed the case's ``extra="forbid"``, and stored the
    base ``as_Object`` instead.  Storage now sees only the parsed case, and the
    stored record carries no trace of the key.
    """
    import logging

    activity = _parsed_announce(
        {
            "type": "VulnerabilityCase",
            "id": "urn:uuid:case-foreign-001",
            "name": "Case With A Foreign Key",
            "fooBar": 1,
        }
    )

    with caplog.at_level(logging.DEBUG):
        _stage_inline_object(datalayer, activity)

    assert persisted == [activity.object_]
    assert type(persisted[0]) is as_VulnerabilityCase
    stored = datalayer.read("urn:uuid:case-foreign-001")
    assert isinstance(stored, VulnerabilityCase)
    assert "fooBar" not in stored.model_dump(by_alias=True)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    # The key survives only in the received evidence (VM-08-002).
    evidence = activity.received_evidence
    assert evidence is not None and evidence["object"]["fooBar"] == 1


@pytest.mark.spec("VM-06-008")
def test_stage_inline_object_stages_no_core_class_for_core_only_name(
    datalayer, persisted
):
    """The object the inbox persists for a core-only name is not core.

    ``CoreActor`` is registered only in the core map.  Before the lookups went
    wire-only the inbox handed a core object to the DataLayer for an inbound
    ``{"type": "CoreActor"}`` (ISSUE-3565); the parser leaves an unresolved
    type to its parent field, and storage keeps what the parser produced.
    """
    from vultron.core.models.base import CoreObject

    activity = _parsed_announce(
        {"id": "urn:uuid:core-only-store", "type": "CoreActor"}
    )

    _stage_inline_object(datalayer, activity)

    assert len(persisted) == 1
    assert not isinstance(persisted[0], (CoreObject, CoreActor))


# ---------------------------------------------------------------------------
# _stage_inline_object
# ---------------------------------------------------------------------------


def test_stage_inline_object_stages_inline_case(datalayer):
    case = as_VulnerabilityCase(
        id_="urn:uuid:case-nest-001",
        name="Nested Case",
    )
    activity = as_Announce(
        actor=_ACTOR_URI,
        object_=case,
    )
    _stage_inline_object(datalayer, activity)
    stored = datalayer.read(case.id_)
    assert stored is not None


def test_stage_inline_object_skips_string_object(datalayer):
    """When object_ is a URI string, no persistence should happen."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Announce,
    )

    activity = as_Announce(actor=_ACTOR_URI, object_="urn:uuid:some-id")
    # Should not raise; DL should remain empty
    _stage_inline_object(datalayer, activity)


def test_stage_inline_object_projection_failure_surfaces_on_read(
    datalayer, caplog
):
    """An unreadable inline object surfaces its failure on read (#2232, #2940).

    Since #2940 removed write-side wire→core normalisation (``extra="forbid"``
    is the boundary contract now), staging holds the inline object verbatim
    rather than rejecting it at write.  The failure is not silently swallowed
    on the way back out: reading the row logs a WARNING naming #2232 rather
    than reporting a misleading "not found" with no trace.
    """
    import logging

    from pydantic import BaseModel

    # The fixture changed with ARCH-25-003 (ADR-0099), and the reason is worth keeping.
    # It used to build an ``as_CaseParticipant`` with ``accepted_embargo_ids=[""]``
    # — legal on the lenient wire class, rejected by the core class's
    # ``NonEmptyString``, so "constructible yet unprojectable". Collapsing the pair
    # removes that state: one class means such an object fails *construction*
    # instead of projection, and there is no wire object left to hand back on
    # read. What still reaches the store is a shape the core class refuses — here
    # a key no ``CaseParticipant`` field accepts, which ``extra="forbid"`` rejects.
    #
    # Deliberately a plain ``BaseModel`` and not a ``CoreObject`` subclass: the
    # latter self-registers in ``CORE_TYPE_MAP`` via ``__init_subclass__``, and with
    # ``type_ = "CaseParticipant"`` it would clobber the real entry for every test
    # that ran afterwards. ``model_construct`` puts it in the slot without the
    # union validation a non-core model would fail.
    class _ShadowingParticipant(BaseModel):
        id_: str = "urn:uuid:participant-2232-unprojectable"
        type_: str = "CaseParticipant"
        not_a_participant_field: str = "x"

    _ShadowingParticipant.__module__ = "vultron.wire.as2.vocab.objects.fake"

    unprojectable = _ShadowingParticipant()
    activity = as_Announce.model_construct(
        actor=_ACTOR_URI, object_=unprojectable
    )

    _stage_inline_object(datalayer, activity)

    with caplog.at_level(logging.WARNING):
        result = datalayer.read(unprojectable.id_)

    # No class can read the row, so it reads as absent — but loudly.
    assert result is None
    assert "issue #2232" in caplog.text


def test_stage_inline_object_duplicate_stays_at_debug(datalayer, caplog):
    """A genuine duplicate is not an error — it must not be logged as one."""
    import logging

    case = as_VulnerabilityCase(
        id_="urn:uuid:case-dup-2232",
        name="Duplicate Case",
    )
    activity = as_Announce(actor=_ACTOR_URI, object_=case)
    _stage_inline_object(datalayer, activity)

    with caplog.at_level(logging.DEBUG):
        _stage_inline_object(datalayer, activity)

    assert "already staged" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.spec("IO-03-004", "DL-06-006")
def test_deferring_an_activity_with_no_inline_object_holds_it_alone(dl):
    staging = InlineObjectStaging(dl)
    queue = FastAPIQueuePort(
        dl=dl, actor_dl=dl, actor_id=_RECEIVER_ID, staging=staging
    )
    note = as_Note(id_=_NOTE_ID, content="by reference", context=_CASE_ID)
    activity = add_note_to_case_activity(
        note,
        target=_CASE_ID,
        context=_CASE_ID,
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
    )
    body = activity.model_dump(mode="json", by_alias=True, exclude_none=True)
    body["object"] = _NOTE_ID
    routed = _routed(dl, body, staging=staging)

    queue.queue(activity_id=routed.id_, case_id=_CASE_ID)

    held = dl.read(DeferredInboxActivity.build_id(routed.id_))
    assert isinstance(held, DeferredInboxActivity)
    assert json.loads(held.rows_json) == []
    replayed = StoredActivityIngressAdapter(dl=dl, staging=staging).parse(
        routed.id_
    )
    assert replayed is not None
    assert getattr(replayed, "object_", None) == _NOTE_ID


@pytest.mark.spec("DL-06-006")
def test_replaying_an_activity_nothing_holds_finds_nothing(dl, caplog):
    """With no record, nothing under the sender's id is read in its place."""
    with caplog.at_level(logging.WARNING):
        assert (
            InlineObjectStaging(dl).rehydrate_deferred("urn:uuid:never-held")
            is None
        )
    assert "urn:uuid:never-held" in caplog.text


@pytest.mark.spec("DL-06-006")
def test_a_row_under_the_senders_id_is_not_replayed(dl):
    """A row of the activity's type under its id is never the held copy."""
    parsed = parse_activity(_add_note_body())
    dl.create(parsed)

    assert InlineObjectStaging(dl).rehydrate_deferred(parsed.id_) is None


@pytest.mark.spec("IO-03-004", "IE-10-001")
def test_a_redelivery_of_a_deferred_activity_is_not_held_again(dl):
    """The held body is kept; the redelivered one is not held again.

    A redelivery is the same body (IE-10-002 refuses a different one), so
    the record written by the first delivery is the one kept.
    """
    staging = InlineObjectStaging(dl)
    first = _add_note_body(content="first")
    routed = _routed(dl, first, staging=staging)
    assert staging.hold_for_replay(routed.id_)
    held_before = staging.held(routed.id_)

    again = InlineObjectStaging(dl)
    _routed(dl, json.loads(json.dumps(first)), staging=again)

    assert again.hold_for_replay(routed.id_) is False
    held = staging.held(routed.id_)
    assert held == held_before
    assert held is not None and held.received_body is not None
    assert json.loads(held.received_body) == first


@pytest.mark.spec("IO-03-004", "CBT-03-003")
def test_a_released_activity_queued_again_is_held_as_first_held(dl):
    """A replay deferred again keeps the body it was first held with."""
    staging = InlineObjectStaging(dl)
    body = _add_note_body()
    routed = _routed(dl, body, staging=staging)
    assert staging.hold_for_replay(routed.id_)

    replaying = InlineObjectStaging(dl)
    assert replaying.rehydrate_deferred(routed.id_) is not None
    assert replaying.held(routed.id_) is None
    assert replaying.hold_for_replay(routed.id_)

    held = replaying.held(routed.id_)
    assert held is not None and held.received_body is not None
    assert json.loads(held.received_body) == body


@pytest.mark.spec("VM-08-002", "DL-06-006")
def test_an_activity_with_no_sealed_body_is_held_as_its_row(dl):
    """One this process built carries no evidence, held or replayed."""
    parsed = parse_activity(_add_note_body())
    built = parsed.model_copy(deep=True)
    built._received_evidence = None
    staging = InlineObjectStaging(dl)
    staging.rehydrate_parsed(built)
    assert staging.hold_for_replay(built.id_)

    held = staging.held(built.id_)
    assert held is not None
    assert held.received_body is None and held.activity_row_json is not None
    replayed = InlineObjectStaging(dl).rehydrate_deferred(built.id_)
    assert replayed is not None
    assert replayed.received_evidence is None
    assert getattr(getattr(replayed, "object_", None), "content", None) == (
        "staged"
    )


def test_a_stage_that_stages_no_activity_row_fails_loudly(dl):
    """A rebuild with no row for the activity itself is a wiring fault."""
    with pytest.raises(VultronWiringError, match="staged no row"):
        InlineObjectStaging(dl)._rehydrate(
            "urn:uuid:unstaged", lambda _store: None, received_body=None
        )
    assert _StagingStore(dl, "urn:uuid:next").read("urn:uuid:unstaged") is None


@pytest.mark.spec("DL-06-006")
def test_holding_what_was_never_staged_is_a_wiring_fault(dl):
    """A queue port with its own staging would queue an id holding nothing."""
    staging = InlineObjectStaging(dl)

    assert staging.can_hold("urn:uuid:x") is False
    with pytest.raises(VultronWiringError, match="share one"):
        staging.hold_for_replay("urn:uuid:x")
    assert sum(dl.count_all().values()) == 0


@pytest.mark.spec("DL-06-006")
def test_hold_again_holds_only_what_this_staging_released(dl):
    """A re-queue holds the released record again, and is a no-op for an id
    this staging never rebuilt."""
    parsed = parse_activity(_add_note_body())
    holder = InlineObjectStaging(dl)
    holder.rehydrate_parsed(parsed)
    holder.hold_for_replay(parsed.id_)
    staging = InlineObjectStaging(dl)

    assert staging.hold_again(parsed.id_) is False
    assert staging.rehydrate_deferred(parsed.id_) is not None
    assert staging.held(parsed.id_) is None, "precondition: released"

    assert staging.hold_again(parsed.id_) is True
    assert staging.held(parsed.id_) is not None


@pytest.mark.spec("DL-06-006", "CBT-03-001")
def test_a_failed_hold_queues_nothing(dl):
    """The record is held before the id is queued, so a hold that raises
    leaves no queued id with nothing behind it."""
    queue = FastAPIQueuePort(
        dl=dl,
        actor_dl=dl,
        actor_id=_RECEIVER_ID,
        staging=InlineObjectStaging(dl),
    )

    with pytest.raises(VultronWiringError):
        queue.queue(activity_id="urn:uuid:unstaged", case_id=_CASE_ID)

    assert dl.read(VultronPendingCaseInbox.build_id(_CASE_ID)) is None


def test_staging_store_of_a_file_deployment_is_in_memory():
    url = scratch_memory_url("sqlite:////data/mydb.sqlite", "inbox-staging")

    assert url == (
        "sqlite:///file:mydb-~inbox-staging?mode=memory&cache=shared&uri=true"
    )
