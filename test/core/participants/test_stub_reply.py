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
"""A stub reply's consent is the row it states, written by copying (CM-23-016).

The invitee's ``Accept`` or ``Reject`` of the stub Invite is the entry for the
row it states (CLP-07-013), and the CASE_MANAGER and every replica write that
row through the one apply function (ADR-0124), never by running a consent
transition on their own copy.
"""

from datetime import UTC, datetime

import pytest

from test.support.embargo_register import activate
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.participants.stub_reply import (
    apply_stub_accept,
    apply_stub_reject,
    settle_stub_accept,
    stub_accept_consent,
    stub_reject_consent,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronEntryRefusedError

CASE_ID = "https://example.org/cases/stub-reply"
INVITEE = "https://example.org/actors/invitee"
EMBARGO = f"{CASE_ID}/embargoes/1"
#: Later than any record's own time, so the reply's time is the one kept.
PUBLISHED = datetime(2100, 1, 2, tzinfo=UTC)

_S = EmbargoConsentState


_RECORD_ID = f"{CASE_ID}/participants/invitee"


def _case(*, in_force: bool = True) -> VulnerabilityCase:
    """A case seating the invitee's record, as the stub Invite left it."""
    case = VulnerabilityCase(id_=CASE_ID, name="Stub reply")
    if in_force:
        activate(case, EMBARGO)
    case.actor_participant_index[INVITEE] = _RECORD_ID
    return case


def _record(state: EmbargoConsentState) -> CaseParticipant:
    return CaseParticipant(
        id_=_RECORD_ID,
        attributed_to=INVITEE,
        context=CASE_ID,
        embargo_consents=[EmbargoConsent(embargo_id=EMBARGO, state=state)],
    )


@pytest.mark.spec("CM-11-007")
@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("held", [_S.UNINVITED, _S.INVITED])
def test_a_reject_declines_the_embargo_in_force_on_a_copy(held):
    record = _record(held)

    declined = stub_reject_consent(_case(), record)

    assert declined is not record
    assert declined.consent_for(EMBARGO) is _S.DECLINED
    assert record.consent_for(EMBARGO) is held, "the input is not mutated"


def test_a_replica_takes_the_rejects_published_time():
    declined = apply_stub_reject(_case(), _record(_S.INVITED), PUBLISHED)

    assert declined is not None
    assert declined.updated == PUBLISHED


@pytest.mark.parametrize(
    "case, held",
    [(_case(in_force=False), _S.INVITED), (_case(), _S.DECLINED)],
    ids=["no-embargo-in-force", "already-declined"],
)
def test_a_reject_that_moves_no_row_changes_nothing(case, held):
    record = _record(held)

    assert stub_reject_consent(case, record) is record
    assert apply_stub_reject(case, record, PUBLISHED) is None


@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("joined", [False, True], ids=["inert", "seated"])
def test_the_case_manager_writes_the_record_a_replica_writes(joined):
    """The CASE_MANAGER's settle and a replica's apply leave one record.

    A seated record (already joined) keeps the signed row too (#5056).
    """
    stored = _record(_S.INVITED)
    stored.joined = joined
    case = _case()

    record = stub_accept_consent(case, stored)
    assert settle_stub_accept(stored, record, PUBLISHED) is True
    replica = apply_stub_accept(case, stored.model_copy(deep=True), PUBLISHED)

    assert replica is not None
    assert record == replica
    assert record.consent_for(EMBARGO) is _S.AGREED
    assert record.updated == PUBLISHED


def test_a_seated_accept_that_moves_nothing_is_not_saved():
    stored = _record(_S.AGREED)
    stored.joined = True
    case = _case()

    record = stub_accept_consent(case, stored)

    assert settle_stub_accept(stored, record, PUBLISHED) is False
    assert apply_stub_accept(case, stored, PUBLISHED) is None


_STATED = pytest.mark.parametrize(
    "stated",
    [stub_accept_consent, stub_reject_consent],
    ids=["accept", "reject"],
)


@_STATED
def test_a_reply_for_a_record_the_case_does_not_index_is_refused(stated):
    case = _case()
    case.actor_participant_index[INVITEE] = f"{CASE_ID}/participants/other"

    with pytest.raises(
        VultronEntryRefusedError, match="no participant record"
    ):
        stated(case, _record(_S.INVITED))


@_STATED
def test_a_reply_for_a_record_attributed_to_no_actor_moves_no_row(stated):
    record = _record(_S.INVITED).model_copy(update={"attributed_to": None})

    assert stated(_case(), record) is record
