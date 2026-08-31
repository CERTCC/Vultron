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
def test_extract_intent_participant_status_vfd_state():
    """as_ParticipantStatus.vfd_state is populated from the wire as_ParticipantStatus."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
    from vultron.core.states.cs import CS_vfd

    ps = as_ParticipantStatus(
        context="https://example.org/cases/1",
        vfd_state=CS_vfd.Vfd,
    )
    activity = as_Create(
        actor="https://example.org/alice",
        object_=ps,
    )
    event = extract_event(activity)

    s = cast(Any, event).status
    assert s is not None
    assert s.vfd.state == CS_vfd.Vfd


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
