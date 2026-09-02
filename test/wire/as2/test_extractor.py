"""Tests for vultron.wire.as2.extractor."""

from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from vultron.core.models.events import MessageSemantics
from vultron.wire.as2.extractor import (
    ActivityPattern,
)
from vultron.semantic_registry import (
    SEMANTIC_REGISTRY,
    extract_event,
    find_matching_semantics,
)


@pytest.mark.spec("SE-02-003")
@pytest.mark.spec("VAM-01-007")
def test_find_matching_semantics_returns_unknown_for_unmatched_activity():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.base.objects.actors import as_Actor

    # Create + Actor has no matching pattern (conservative string matching
    # means only explicit typed objects trigger pattern skips)
    actor = as_Actor(name="test-actor")
    activity = as_Create(
        actor="https://example.org/alice",
        object_=actor,
    )
    result = find_matching_semantics(activity)
    assert result == MessageSemantics.UNKNOWN


@pytest.mark.spec("SE-02-001")
@pytest.mark.spec("SE-02-002")
@pytest.mark.spec("VAM-02-001")
def test_find_matching_semantics_returns_correct_semantics_for_create_report():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(name="VR-001", content="test report")
    activity = as_Create(
        actor="https://example.org/finder",
        object_=report,
    )
    result = find_matching_semantics(activity)
    assert result == MessageSemantics.CREATE_REPORT


@pytest.mark.spec("SE-03-001")
def test_all_message_semantics_except_unknown_have_patterns():
    _no_pattern_sentinels = {
        MessageSemantics.UNKNOWN,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
    }
    missing = [
        e.semantics
        for e in SEMANTIC_REGISTRY
        if e.semantics not in _no_pattern_sentinels and e.pattern is None
    ]
    assert not missing, f"Missing patterns for: {missing}"


@pytest.mark.spec("SE-01-001")
def test_activity_pattern_match_returns_false_for_wrong_activity_type():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.enums import (
        as_TransitiveActivityType as TAtype,
        as_ObjectType as AOtype,
    )

    pattern = ActivityPattern(activity_=TAtype.ADD, object_=AOtype.NOTE)
    activity = as_Create(
        actor="https://example.org/alice",
        object_="https://example.org/notes/1",
    )
    assert not pattern.match(activity)


# --- wire-to-domain round-trip tests for new fields ---


@pytest.mark.spec("VAM-02-001")
@pytest.mark.spec("SE-01-002")
def test_extract_intent_report_pass_through_fields():
    """New VultronReport fields (summary, url, media_type, published, updated) survive extraction."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    now = datetime.now(timezone.utc)
    report = as_VulnerabilityReport(
        name="VR-001",
        summary="Brief summary",
        content="Full content",
        url="https://example.org/reports/vr-001",
        media_type="text/plain",
        attributed_to="https://example.org/alice",
        context="https://example.org/cases/1",
        published=now,
        updated=now,
    )
    activity = as_Create(actor="https://example.org/alice", object_=report)
    event = extract_event(activity)

    r = cast(Any, event).report
    assert r is not None
    assert r.summary == "Brief summary"
    assert r.url == "https://example.org/reports/vr-001"
    assert r.media_type == "text/plain"
    assert r.published == now
    assert r.updated == now


@pytest.mark.spec("VAM-03-001")
def test_extract_intent_case_pass_through_fields():
    """New VultronCase fields (published, updated) survive extraction."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    now = datetime.now(timezone.utc)
    case = as_VulnerabilityCase(
        name="CASE-001",
        summary="Case summary",
        published=now,
        updated=now,
    )
    activity = as_Create(actor="https://example.org/alice", object_=case)
    event = extract_event(activity)

    c = cast(Any, event).case
    assert c is not None
    assert c.published == now
    assert c.updated == now


@pytest.mark.spec("VAM-05-001")
def test_extract_intent_embargo_pass_through_fields():
    """New VultronEmbargoEvent fields (published, updated) survive extraction."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    now = datetime.now(timezone.utc)
    embargo = as_EmbargoEvent(
        context="https://example.org/cases/1",
        published=now,
        updated=now,
    )
    # CreateEmbargoEvent pattern: Create + EVENT + context=VULNERABILITY_CASE
    activity = as_Create(
        actor="https://example.org/alice",
        object_=embargo,
        context="https://example.org/cases/1",
    )
    event = extract_event(activity)

    e = cast(Any, event).embargo
    assert e is not None
    assert e.published == now
    assert e.updated == now


@pytest.mark.spec("VAM-07-001")
def test_extract_intent_note_pass_through_fields():
    """New VultronNote fields (summary, url) survive extraction."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(
        name="Note title",
        summary="Note summary",
        content="Note body",
        url="https://example.org/notes/1",
        attributed_to="https://example.org/alice",
        context="https://example.org/cases/1",
    )
    activity = as_Create(actor="https://example.org/alice", object_=note)
    event = extract_event(activity)

    n = cast(Any, event).note
    assert n is not None
    assert n.summary == "Note summary"
    assert n.url == "https://example.org/notes/1"


@pytest.mark.spec("SE-01-002")
def test_extract_intent_activity_origin_field():
    """New VultronActivity.origin field is populated from the wire activity."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(name="VR-001", content="test")
    activity = as_Create(
        actor="https://example.org/alice",
        object_=report,
        origin="https://example.org/cases/original",
    )
    event = extract_event(activity)

    assert event.activity is not None
    assert event.activity.origin == "https://example.org/cases/original"


@pytest.mark.spec("VAM-06-001")
def test_extract_intent_participant_case_roles():
    """VultronParticipant.case_roles is populated from the wire as_CaseParticipant."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )
    from vultron.enums.roles import CVDRole

    participant = as_CaseParticipant(
        attributed_to="https://example.org/alice",
        context="https://example.org/cases/1",
    )
    object.__setattr__(participant, "case_roles", [CVDRole.VENDOR])
    # CreateCaseParticipant pattern: Create + CASE_PARTICIPANT + context=VULNERABILITY_CASE
    activity = as_Create(
        actor="https://example.org/alice",
        object_=participant,
        context="https://example.org/cases/1",
    )
    event = extract_event(activity)

    p = cast(Any, event).participant
    assert p is not None
    assert CVDRole.VENDOR in p.case_roles


@pytest.mark.spec("VAM-08-001")
def test_extract_intent_case_status_name():
    """as_CaseStatus.name is populated from the wire as_CaseStatus."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

    cs = as_CaseStatus(context="https://example.org/cases/1")
    # CreateCaseStatusActivity pattern: Create + CASE_STATUS + context=VULNERABILITY_CASE
    activity = as_Create(
        actor="https://example.org/alice",
        object_=cs,
        context="https://example.org/cases/1",
    )
    event = extract_event(activity)

    s = cast(Any, event).status
    assert s is not None
    assert s.name == cs.name


@pytest.mark.spec("VAM-08-003")
def test_extract_intent_participant_status_vf_state():
    """vf_state is extracted and populated on the core ParticipantStatus (ADR-0075)."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
    from vultron.core.states.cs import CS_vf

    ps = as_ParticipantStatus(
        context="https://example.org/cases/1",
        vf_state=CS_vf.Vf,
    )
    activity = as_Create(
        actor="https://example.org/alice",
        object_=ps,
    )
    event = extract_event(activity)

    s = cast(Any, event).status
    assert s is not None
    assert s.vf.state == CS_vf.Vf


# ---------------------------------------------------------------------------
# RSVP deadline extraction for InviteToEmbargoOnCase (issue #2211)
# ---------------------------------------------------------------------------


def _make_embargo_invite(end_time=None):
    """Build an as_Invite(as_EmbargoEvent) with optional activity-level end_time."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Invite,
    )
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    embargo = as_EmbargoEvent(
        context="https://example.org/cases/1",
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=90),
    )
    case = as_VulnerabilityCase(id_="https://example.org/cases/1")
    kwargs = {
        "object_": embargo,
        "context": case,
        "actor": "https://example.org/alice",
    }
    if end_time is not None:
        kwargs["end_time"] = end_time
    return as_Invite(**kwargs)


@pytest.mark.spec("CM-27-001")
def test_invite_rsvp_deadline_extracted_when_present():
    """AC-2: activity-level end_time is extracted as rsvp_deadline on the event."""
    deadline = datetime.now(tz=timezone.utc) + timedelta(days=5)
    invite = _make_embargo_invite(end_time=deadline)
    event = extract_event(invite)

    assert hasattr(event, "rsvp_deadline")
    ev = cast(Any, event)
    assert ev.rsvp_deadline is not None
    # rsvp_deadline carries the invite end_time, NOT the nested embargo end_time
    assert ev.rsvp_deadline == deadline.astimezone(timezone.utc)


@pytest.mark.spec("CM-27-001")
def test_invite_rsvp_deadline_absent_when_no_end_time():
    """AC-7 (absent): no end_time on invite → rsvp_deadline is None."""
    invite = _make_embargo_invite(end_time=None)
    event = extract_event(invite)

    assert hasattr(event, "rsvp_deadline")
    assert cast(Any, event).rsvp_deadline is None


@pytest.mark.spec("CM-27-001")
def test_invite_rsvp_deadline_distinct_from_embargo_end_time():
    """AC-2: invite.end_time and invite.object_.end_time are distinct fields."""
    rsvp = datetime.now(tz=timezone.utc) + timedelta(days=5)
    invite = _make_embargo_invite(end_time=rsvp)
    event = extract_event(invite)

    # The nested embargo's end_time is on the activity's object_, not rsvp_deadline
    ev = cast(Any, event)
    assert ev.rsvp_deadline == rsvp.astimezone(timezone.utc)
    # The embargo expiry is on event.activity.object_.end_time (90 days out)
    embargo_end_time = getattr(
        getattr(ev.activity, "object_", None), "end_time", None
    )
    assert embargo_end_time is not None
    assert embargo_end_time != ev.rsvp_deadline


@pytest.mark.spec("EP-07-003")
def test_invite_rsvp_deadline_clamped_when_below_floor():
    """AC-5: sub-floor rsvp_deadline is clamped up (not rejected)."""
    # end_time is in the past / far below the 72h floor
    past_deadline = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    invite = _make_embargo_invite(end_time=past_deadline)
    event = extract_event(invite)

    ev = cast(Any, event)
    assert ev.rsvp_deadline is not None
    # Clamped up: deadline is >= now (was in the past)
    assert ev.rsvp_deadline > datetime.now(tz=timezone.utc)


@pytest.mark.spec("EP-07-002")
def test_invite_rsvp_deadline_none_when_naive_end_time():
    """AC-7 (inbound naive): naive end_time on invite is ignored → rsvp_deadline is None."""
    naive_deadline = datetime.now() + timedelta(days=5)  # no tzinfo
    invite = _make_embargo_invite(end_time=naive_deadline)
    event = extract_event(invite)

    assert hasattr(event, "rsvp_deadline")
    assert cast(Any, event).rsvp_deadline is None


@pytest.mark.spec("CM-28-006")
def test_invite_rsvp_deadline_warns_when_naive_end_time(caplog):
    """CM-28-006: naive end_time MUST be logged as malformed, not silently dropped."""
    import logging

    naive_deadline = datetime.now() + timedelta(days=5)  # no tzinfo
    invite = _make_embargo_invite(end_time=naive_deadline)

    with caplog.at_level(
        logging.WARNING, logger="vultron.wire.as2.extractor._extract"
    ):
        caplog.clear()
        event = extract_event(invite)

    assert cast(Any, event).rsvp_deadline is None
    warning_msgs = [
        r.message for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert any(
        "naive" in msg.lower() or "malformed" in msg.lower()
        for msg in warning_msgs
    ), f"Expected a warning about naive/malformed end_time; got: {warning_msgs}"


@pytest.mark.spec("EP-07-003")
def test_invite_rsvp_deadline_clamped_uses_custom_min_rsvp_window():
    """EP-07-003: extract_intent uses the caller-supplied min_rsvp_window for clamping."""
    from vultron.wire.as2.extractor._extract import extract_intent
    from vultron.semantic_registry import find_matching_semantics, lookup_entry

    # deadline 5 days out: above 72 h default floor, but below 10-day custom floor
    deadline = datetime.now(tz=timezone.utc) + timedelta(days=5)
    invite = _make_embargo_invite(end_time=deadline)

    semantics = find_matching_semantics(invite)
    entry = lookup_entry(semantics)
    event = extract_intent(
        invite,
        semantics=semantics,
        event_class=entry.event_class,
        include_activity=entry.include_activity,
        min_rsvp_window=timedelta(days=10),
    )

    ev = cast(Any, event)
    assert ev.rsvp_deadline is not None
    # Clamped to 10-day floor — must be strictly greater than 5-day deadline
    assert ev.rsvp_deadline > deadline.astimezone(timezone.utc)


# --- discriminated-union return-type narrowing tests (issue #2491) ---


@pytest.mark.spec("CS-10-001")
def test_extract_event_return_type_narrows_via_isinstance():
    """extract_event() returns a discriminated union; isinstance narrows to the
    concrete subclass without any cast(Any, ...) workaround."""
    from vultron.core.models.events.report import CreateReportReceivedEvent
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(name="VR-001", content="test content")
    activity = as_Create(
        actor="https://example.org/finder",
        object_=report,
    )
    event = extract_event(activity)

    assert isinstance(event, CreateReportReceivedEvent)
    # After narrowing: access the concrete property directly — no cast needed.
    assert event.report_id == report.id_


@pytest.mark.spec("CS-10-001")
def test_extract_intent_return_type_narrows_via_isinstance():
    """extract_intent() return annotation is AnyReceivedEvent; isinstance
    dispatch on the concrete subclass works after the call."""
    from vultron.core.models.events.report import SubmitReportReceivedEvent
    from vultron.semantic_registry import find_matching_semantics, lookup_entry
    from vultron.wire.as2.extractor._extract import extract_intent
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Offer,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(name="VR-002", content="submission")
    activity = as_Offer(
        actor="https://example.org/reporter",
        object_=report,
    )
    semantics = find_matching_semantics(activity)
    entry = lookup_entry(semantics)
    event = extract_intent(
        activity,
        semantics=semantics,
        event_class=entry.event_class,
        include_activity=entry.include_activity,
    )

    assert isinstance(event, SubmitReportReceivedEvent)
    # Concrete-class property accessible without cast.
    assert event.report_id == report.id_


@pytest.mark.spec("CS-10-001")
def test_any_received_event_covers_all_registry_event_classes():
    """AnyReceivedEvent must include every event_class registered in SEMANTIC_REGISTRY.

    This locks in exhaustiveness: adding a new ReceivedEvent subclass without
    updating AnyReceivedEvent will fail here at test time, not only at static
    analysis time.
    """
    from typing import get_args

    from vultron.core.models.events import AnyReceivedEvent
    from vultron.semantic_registry import SEMANTIC_REGISTRY

    union_types = set(get_args(AnyReceivedEvent))
    for entry in SEMANTIC_REGISTRY:
        assert entry.event_class in union_types, (
            f"{entry.event_class.__name__} (semantics={entry.semantics.name}) "
            f"is in SEMANTIC_REGISTRY but not in AnyReceivedEvent"
        )


# ---------------------------------------------------------------------------
# `attributed_to` on the activity snapshot (CM-24-002, issue #3012)
# ---------------------------------------------------------------------------


def _ownership_offer(attributed_to: Any) -> Any:
    """Build a delegated ownership-transfer Offer carrying *attributed_to*.

    Goes through the factory (ARCH: tests must not reach into
    ``vultron.wire.as2.vocab.activities`` directly — see
    ``test_activity_factory_imports.py``).  ``as_Object.attributed_to`` is typed
    ``Any | None``, so the factory accepts the inline-object and array shapes
    AS2 permits, which is what lets this exercise a non-URI value.
    """
    from vultron.wire.as2.factories import (
        offer_case_ownership_transfer_activity,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    return offer_case_ownership_transfer_activity(
        as_VulnerabilityCase(id_="https://example.org/cases/c1", name="C1"),
        target={
            "id": "https://example.org/actors/coordinator",
            "type": "Organization",
        },
        actor="https://example.org/actors/case-actor",
        attributed_to=attributed_to,
    )


@pytest.mark.spec("CM-24-002")
def test_activity_snapshot_carries_attributed_to():
    """The delegated author must survive extraction into `event.activity`.

    CM-24-002 puts the requesting participant in `attributed_to` "so that
    receivers can recover the originating identity".  `_build_activity_snapshot`
    dropped the field, so no received-side use case could recover it and the
    CaseActor forwarded Offers attributing a participant's intent to itself
    (#3012).
    """
    vendor = "https://example.org/users/vendor"
    event = extract_event(_ownership_offer(vendor))

    assert event.activity is not None
    assert event.activity.attributed_to == vendor


@pytest.mark.spec("CLP-07-011")
@pytest.mark.parametrize(
    "raw, expected",
    [
        pytest.param(
            {"id": "https://example.org/users/vendor", "type": "Person"},
            "https://example.org/users/vendor",
            id="inline-object-resolves-to-its-id",
        ),
        pytest.param(
            [
                "https://example.org/users/vendor",
                "https://example.org/users/other",
            ],
            "https://example.org/users/vendor",
            id="array-resolves-to-first-id",
        ),
        pytest.param(
            {"type": "Person"},
            None,
            id="object-without-id-resolves-to-absent",
        ),
        pytest.param([], None, id="empty-array-resolves-to-absent"),
    ],
)
def test_activity_snapshot_never_reprs_a_non_uri_attributed_to(raw, expected):
    """A non-URI `attributedTo` resolves to its id or to ``None`` — never a repr.

    AS2 permits `attributedTo` to be an object or an array.  `_get_id` used to
    fall back to ``str(field)``, which put a Python repr such as
    ``"{'id': ..., 'type': 'Person'}"`` into the snapshot.  That value is hashed
    into `entry_hash` and replicated to every participant, where an absent field
    is recoverable and a garbage string is not (CLP-07-011, ARCH-15-001).
    """
    event = extract_event(_ownership_offer(raw))

    assert event.activity is not None
    assert event.activity.attributed_to == expected
    if event.activity.attributed_to is not None:
        assert not event.activity.attributed_to.startswith(("{", "["))
