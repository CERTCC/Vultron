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
"""Tests for ``make``, the one place a test states an object's time."""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from test.support.act_clock import ACT_AT, recorded_clock_reads
from test.support.objects import make, stamped_times
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_OWNER = "https://example.org/actors/owner"
_CASE = "https://example.org/cases/case-1"
_LATER = ACT_AT + timedelta(days=1)
_END = ACT_AT + timedelta(days=90)


def test_make_states_every_left_out_time_from_one_clock_reading() -> None:
    with recorded_clock_reads() as note_reads:
        note = make(as_Note, content="hello")
    with recorded_clock_reads() as embargo_reads:
        embargo = make(EmbargoEvent, context=_CASE, end_time=_END)

    assert len(note_reads) == len(embargo_reads) == 1
    assert (note.published, note.updated) == (note_reads[0],) * 2
    assert (embargo.published, embargo.updated, embargo.start_time) == (
        embargo_reads[0],
    ) * 3


def test_make_states_a_case_s_times_from_its_first_clock_reading() -> None:
    with recorded_clock_reads() as reads:
        case = make(VulnerabilityCase, attributed_to=_OWNER)

    assert (case.published, case.updated) == (reads[0],) * 2


def test_make_gives_a_case_status_no_updated() -> None:
    """A status is appended once and never changed (CM-29-006)."""
    with recorded_clock_reads() as reads:
        status = make(CaseStatus, context=_CASE)

    assert status.published == reads[0]
    assert status.updated is None


def test_make_keeps_a_time_the_caller_passes() -> None:
    participant = make(
        CaseParticipant,
        attributed_to=_OWNER,
        context=_CASE,
        published=_LATER,
        updated=None,
    )

    assert participant.published == _LATER
    assert participant.updated is None


def test_make_reads_a_time_passed_under_its_alias() -> None:
    embargo = make(
        EmbargoEvent, context=_CASE, end_time=_END, startTime=_LATER
    )

    assert embargo.start_time == _LATER


def test_make_leaves_a_model_with_no_author_time_alone() -> None:
    class Untimed(BaseModel):
        published: datetime | None = None

    assert stamped_times(Untimed) == ()
    assert make(Untimed).published is None


def test_make_leaves_a_time_that_is_absent_until_stated_alone() -> None:
    """A consent row carries no time of its own building (CM-18-005)."""
    consent = make(
        EmbargoConsent,
        context=_CASE,
        attributed_to=_OWNER,
        embargo_id="https://example.org/embargoes/e-1",
        state=EmbargoConsentState.UNINVITED,
    )

    assert stamped_times(EmbargoConsent) == ()
    assert (consent.published, consent.updated) == (None, None)


def test_make_builds_a_valid_object() -> None:
    case = make(VulnerabilityCase, attributed_to=_OWNER)

    assert case.published is not None
    assert case.published.tzinfo is UTC
    assert VulnerabilityCase.model_validate(case.model_dump()) == case
