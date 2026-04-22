#!/usr/bin/env python

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

"""Regression tests for INLINE-OBJ-A: narrow object_ types in initiating
activity classes (MV-09-001).

Each initiating activity class must reject a bare string URI or an as_Link
as object_ and accept only the correct inline domain object type.

Spec: specs/message-validation.md MV-09-001
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.errors import VultronOutboxObjectIntegrityError
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

_STR_URI = "https://example.org/objects/123"
_LINK = as_Link(href="https://example.org/objects/123")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/alice"


def _make_activity(cls, object_):
    """Attempt to construct *cls* with the given object_, return the instance."""
    return cls(actor=ACTOR_ID, object_=object_)


def _assert_rejects_string(cls):
    with pytest.raises(ValidationError):
        _make_activity(cls, _STR_URI)


def _assert_rejects_link(cls):
    with pytest.raises(ValidationError):
        _make_activity(cls, _LINK)


def _assert_accepts_inline(cls, obj):
    instance = _make_activity(cls, obj)
    assert instance.object_ is obj or instance.object_ == obj


def _participant_status() -> ParticipantStatus:
    return ParticipantStatus(context="https://example.org/cases/c1")


# ---------------------------------------------------------------------------
# Report activities (report.py)
# ---------------------------------------------------------------------------


class TestRmCreateReportActivity:
    from vultron.wire.as2.vocab.activities.report import RmCreateReportActivity

    cls = RmCreateReportActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_report(self):
        _assert_accepts_inline(self.cls, VulnerabilityReport())


class TestRmSubmitReportActivity:
    from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity

    cls = RmSubmitReportActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_report(self):
        _assert_accepts_inline(self.cls, VulnerabilityReport())


class TestRmReadReportActivity:
    from vultron.wire.as2.vocab.activities.report import RmReadReportActivity

    cls = RmReadReportActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_report(self):
        _assert_accepts_inline(self.cls, VulnerabilityReport())


# ---------------------------------------------------------------------------
# Case activities (case.py)
# ---------------------------------------------------------------------------


class TestAddReportToCaseActivity:
    from vultron.wire.as2.vocab.activities.case import AddReportToCaseActivity

    cls = AddReportToCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_report(self):
        _assert_accepts_inline(self.cls, VulnerabilityReport())


class TestAddStatusToCaseActivity:
    from vultron.wire.as2.vocab.activities.case import AddStatusToCaseActivity

    cls = AddStatusToCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_case_status(self):
        _assert_accepts_inline(self.cls, CaseStatus())


class TestCreateCaseActivity:
    from vultron.wire.as2.vocab.activities.case import CreateCaseActivity

    cls = CreateCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_case(self):
        _assert_accepts_inline(self.cls, VulnerabilityCase())


class TestCreateCaseStatusActivity:
    from vultron.wire.as2.vocab.activities.case import CreateCaseStatusActivity

    cls = CreateCaseStatusActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_case_status(self):
        _assert_accepts_inline(self.cls, CaseStatus())


class TestAddNoteToCaseActivity:
    from vultron.wire.as2.vocab.activities.case import AddNoteToCaseActivity

    cls = AddNoteToCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_note(self):
        _assert_accepts_inline(self.cls, as_Note(content="hello"))


class TestUpdateCaseActivity:
    from vultron.wire.as2.vocab.activities.case import UpdateCaseActivity

    cls = UpdateCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_case(self):
        _assert_accepts_inline(self.cls, VulnerabilityCase())


class TestRmEngageCaseActivity:
    from vultron.wire.as2.vocab.activities.case import RmEngageCaseActivity

    cls = RmEngageCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_case(self):
        _assert_accepts_inline(self.cls, VulnerabilityCase())


class TestRmDeferCaseActivity:
    from vultron.wire.as2.vocab.activities.case import RmDeferCaseActivity

    cls = RmDeferCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_case(self):
        _assert_accepts_inline(self.cls, VulnerabilityCase())


class TestRmCloseCaseActivity:
    from vultron.wire.as2.vocab.activities.case import RmCloseCaseActivity

    cls = RmCloseCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_case(self):
        _assert_accepts_inline(self.cls, VulnerabilityCase())


class TestRmInviteToCaseActivity:
    from vultron.wire.as2.vocab.activities.case import RmInviteToCaseActivity

    cls = RmInviteToCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_actor(self):
        _assert_accepts_inline(self.cls, as_Actor())


# ---------------------------------------------------------------------------
# Embargo activities (embargo.py)
# ---------------------------------------------------------------------------


class TestEmProposeEmbargoActivity:
    from vultron.wire.as2.vocab.activities.embargo import (
        EmProposeEmbargoActivity,
    )

    cls = EmProposeEmbargoActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_embargo_event(self):
        _assert_accepts_inline(self.cls, EmbargoEvent())


class TestActivateEmbargoActivity:
    from vultron.wire.as2.vocab.activities.embargo import (
        ActivateEmbargoActivity,
    )

    cls = ActivateEmbargoActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_embargo_event(self):
        _assert_accepts_inline(self.cls, EmbargoEvent())


class TestAddEmbargoToCaseActivity:
    from vultron.wire.as2.vocab.activities.embargo import (
        AddEmbargoToCaseActivity,
    )

    cls = AddEmbargoToCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_embargo_event(self):
        _assert_accepts_inline(self.cls, EmbargoEvent())


class TestAnnounceEmbargoActivity:
    from vultron.wire.as2.vocab.activities.embargo import (
        AnnounceEmbargoActivity,
    )

    cls = AnnounceEmbargoActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_embargo_event(self):
        _assert_accepts_inline(self.cls, EmbargoEvent())


class TestRemoveEmbargoFromCaseActivity:
    from vultron.wire.as2.vocab.activities.embargo import (
        RemoveEmbargoFromCaseActivity,
    )

    cls = RemoveEmbargoFromCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_embargo_event(self):
        _assert_accepts_inline(self.cls, EmbargoEvent())


# ---------------------------------------------------------------------------
# Actor activities (actor.py)
# ---------------------------------------------------------------------------


class TestRecommendActorActivity:
    from vultron.wire.as2.vocab.activities.actor import RecommendActorActivity

    cls = RecommendActorActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_actor(self):
        _assert_accepts_inline(self.cls, as_Actor())


# ---------------------------------------------------------------------------
# CaseParticipant activities (case_participant.py)
# ---------------------------------------------------------------------------


class TestCreateParticipantActivity:
    from vultron.wire.as2.vocab.activities.case_participant import (
        CreateParticipantActivity,
    )

    cls = CreateParticipantActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_participant(self):
        _assert_accepts_inline(self.cls, CaseParticipant())


class TestCreateStatusForParticipantActivity:
    from vultron.wire.as2.vocab.activities.case_participant import (
        CreateStatusForParticipantActivity,
    )

    cls = CreateStatusForParticipantActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_participant_status(self):
        _assert_accepts_inline(self.cls, _participant_status())


class TestAddStatusToParticipantActivity:
    from vultron.wire.as2.vocab.activities.case_participant import (
        AddStatusToParticipantActivity,
    )

    cls = AddStatusToParticipantActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_participant_status(self):
        _assert_accepts_inline(self.cls, _participant_status())


class TestAddParticipantToCaseActivity:
    from vultron.wire.as2.vocab.activities.case_participant import (
        AddParticipantToCaseActivity,
    )

    cls = AddParticipantToCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_participant(self):
        _assert_accepts_inline(self.cls, CaseParticipant())


class TestRemoveParticipantFromCaseActivity:
    from vultron.wire.as2.vocab.activities.case_participant import (
        RemoveParticipantFromCaseActivity,
    )

    cls = RemoveParticipantFromCaseActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_participant(self):
        _assert_accepts_inline(self.cls, CaseParticipant())


# ---------------------------------------------------------------------------
# Sync activities (sync.py)
# ---------------------------------------------------------------------------


class TestAnnounceLogEntryActivity:
    from vultron.wire.as2.vocab.activities.sync import AnnounceLogEntryActivity
    from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry

    cls = AnnounceLogEntryActivity

    def test_rejects_string(self):
        _assert_rejects_string(self.cls)

    def test_rejects_link(self):
        _assert_rejects_link(self.cls)

    def test_accepts_inline_log_entry(self):
        from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry

        _assert_accepts_inline(
            self.cls,
            CaseLogEntry(
                case_id="https://example.org/cases/c1",
                log_object_id="https://example.org/cases/c1/events/e1",
                event_type="test_event",
            ),
        )


# ---------------------------------------------------------------------------
# Outbox handler integrity check (MV-09-002)
# ---------------------------------------------------------------------------


def _make_outbox_dl(activity) -> MagicMock:
    """Return a MagicMock DataLayer that returns *activity* for any read."""
    dl = MagicMock()
    dl.read.return_value = activity
    return dl


def test_handle_outbox_item_raises_on_bare_string_object(caplog):
    """handle_outbox_item MUST raise VultronOutboxObjectIntegrityError when
    object_ is a bare string that cannot be expanded from the DataLayer.

    Spec: MV-09-002
    """
    from vultron.core.models.activity import VultronActivity

    activity = VultronActivity(
        type_="Create",
        actor=ACTOR_ID,
        object_=_STR_URI,
    )

    dl = MagicMock()
    # First read returns the activity; second read (expansion attempt) returns None.
    dl.read.side_effect = [activity, None]

    emitter = AsyncMock()

    with pytest.raises(VultronOutboxObjectIntegrityError):
        asyncio.run(oh.handle_outbox_item(ACTOR_ID, activity.id_, dl, emitter))
