"""Tests for vultron.wire.as2.extractor."""

import pytest
from datetime import datetime, timezone

from vultron.core.models.events import MessageSemantics
from vultron.wire.as2.extractor import (
    SEMANTICS_ACTIVITY_PATTERNS,
    ActivityPattern,
    find_matching_semantics,
    extract_intent,
)


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
        object=actor,
    )
    result = find_matching_semantics(activity)
    assert result == MessageSemantics.UNKNOWN


def test_find_matching_semantics_returns_correct_semantics_for_create_report():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(name="VR-001", content="test report")
    activity = as_Create(
        actor="https://example.org/finder",
        object=report,
    )
    result = find_matching_semantics(activity)
    assert result == MessageSemantics.CREATE_REPORT


def test_all_message_semantics_except_unknown_have_patterns():
    missing = [
        m
        for m in MessageSemantics
        if m != MessageSemantics.UNKNOWN
        and m not in SEMANTICS_ACTIVITY_PATTERNS
    ]
    assert not missing, f"Missing patterns for: {missing}"


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
        object="https://example.org/notes/1",
    )
    assert not pattern.match(activity)


# --- wire-to-domain round-trip tests for new fields ---


def test_extract_intent_report_pass_through_fields():
    """New VultronReport fields (summary, url, media_type, published, updated) survive extraction."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    now = datetime.now(timezone.utc)
    report = VulnerabilityReport(
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
    activity = as_Create(actor="https://example.org/alice", object=report)
    event = extract_intent(activity)

    r = event.report
    assert r is not None
    assert r.summary == "Brief summary"
    assert r.url == "https://example.org/reports/vr-001"
    assert r.media_type == "text/plain"
    assert r.published == now
    assert r.updated == now


def test_extract_intent_case_pass_through_fields():
    """New VultronCase fields (published, updated) survive extraction."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )

    now = datetime.now(timezone.utc)
    case = VulnerabilityCase(
        name="CASE-001",
        summary="Case summary",
        published=now,
        updated=now,
    )
    activity = as_Create(actor="https://example.org/alice", object=case)
    event = extract_intent(activity)

    c = event.case
    assert c is not None
    assert c.published == now
    assert c.updated == now


def test_extract_intent_embargo_pass_through_fields():
    """New VultronEmbargoEvent fields (published, updated) survive extraction."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

    now = datetime.now(timezone.utc)
    embargo = EmbargoEvent(
        context="https://example.org/cases/1",
        published=now,
        updated=now,
    )
    # CreateEmbargoEvent pattern: Create + EVENT + context=VULNERABILITY_CASE
    activity = as_Create(
        actor="https://example.org/alice",
        object=embargo,
        context="https://example.org/cases/1",
    )
    event = extract_intent(activity)

    e = event.embargo
    assert e is not None
    assert e.published == now
    assert e.updated == now


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
    activity = as_Create(actor="https://example.org/alice", object=note)
    event = extract_intent(activity)

    n = event.note
    assert n is not None
    assert n.summary == "Note summary"
    assert n.url == "https://example.org/notes/1"


def test_extract_intent_activity_origin_field():
    """New VultronActivity.origin field is populated from the wire activity."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(name="VR-001", content="test")
    activity = as_Create(
        actor="https://example.org/alice",
        object=report,
        origin="https://example.org/cases/original",
    )
    event = extract_intent(activity)

    assert event.activity is not None
    assert event.activity.origin == "https://example.org/cases/original"


def test_extract_intent_participant_case_roles():
    """VultronParticipant.case_roles is populated from the wire CaseParticipant."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.case_participant import (
        CaseParticipant,
    )
    from vultron.bt.roles.states import CVDRoles

    participant = CaseParticipant(
        attributed_to="https://example.org/alice",
        context="https://example.org/cases/1",
    )
    participant.case_roles = [CVDRoles.VENDOR]
    # CreateCaseParticipant pattern: Create + CASE_PARTICIPANT + context=VULNERABILITY_CASE
    activity = as_Create(
        actor="https://example.org/alice",
        object=participant,
        context="https://example.org/cases/1",
    )
    event = extract_intent(activity)

    p = event.participant
    assert p is not None
    assert CVDRoles.VENDOR in p.case_roles


def test_extract_intent_case_status_name():
    """VultronCaseStatus.name is populated from the wire CaseStatus."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.case_status import CaseStatus

    cs = CaseStatus(context="https://example.org/cases/1")
    # CreateCaseStatusActivity pattern: Create + CASE_STATUS + context=VULNERABILITY_CASE
    activity = as_Create(
        actor="https://example.org/alice",
        object=cs,
        context="https://example.org/cases/1",
    )
    event = extract_intent(activity)

    s = event.status
    assert s is not None
    assert s.name == cs.name


def test_extract_intent_participant_status_vfd_state():
    """VultronParticipantStatus.vfd_state is populated from the wire ParticipantStatus."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus
    from vultron.case_states.states import CS_vfd

    ps = ParticipantStatus(
        context="https://example.org/cases/1",
        vfd_state=CS_vfd.Vfd,
    )
    activity = as_Create(
        actor="https://example.org/alice",
        object=ps,
    )
    event = extract_intent(activity)

    s = event.status
    assert s is not None
    assert s.vfd_state == CS_vfd.Vfd
