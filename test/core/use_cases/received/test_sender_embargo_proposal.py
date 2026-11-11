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
"""The Reporter's proposed terms are measured from the act's instant.

``sender_embargo_proposal_inputs`` turns the embargo an Offer carries into
the duration left on it when the CASE_MANAGER receives the proposal
(EP-04-004).  It takes that instant from the act and reads no clock, so the
same instant gives the same verdict and reading the terms moves no
recording (ADR-0176).
"""

from datetime import UTC, datetime, timedelta

import pytest

from test.support.act_clock import recorded_clock_reads
from test.support.act_runner import in_act
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.base import CoreObject
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.case_proposal import (
    CreateCaseProposalReceivedEvent,
)
from vultron.core.use_cases.received._sender_embargo_proposal import (
    sender_embargo_proposal_inputs,
)
from vultron.errors import VultronMissingActInstantError

_REPORT = "https://example.org/reports/act-instant"
_REPORTER = "https://example.org/actors/act-instant-reporter"
# A fixed end time: the act's instant is pinned, so no wall clock is needed.
_END = datetime(2026, 6, 1, 12, tzinfo=UTC)


def _proposal() -> CreateCaseProposalReceivedEvent:
    """A received proposal whose Offer carries terms ending at ``_END``."""
    return CreateCaseProposalReceivedEvent(
        activity_id="https://example.org/activities/create-proposal",
        actor_id=_REPORTER,
        proposer_profile=VultronOrganization(id_=_REPORTER),
        inner_object=CoreObject(id_=_REPORT),
        proposed_embargo=EmbargoEvent(
            id_="https://example.org/embargoes/proposed",
            context=_REPORT,
            start_time=_END - timedelta(days=90),
            end_time=_END,
        ),
    )


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("EP-04-004")
@pytest.mark.parametrize(
    ("before_end", "kept"),
    [(timedelta(microseconds=1), True), (timedelta(0), False)],
    ids=["a-microsecond-left", "at-its-end"],
)
def test_the_terms_left_are_measured_at_the_acts_instant(
    before_end: timedelta, kept: bool
) -> None:
    """Terms with time left are kept, as the time left at the act's instant;
    terms at their end are read as no proposal."""
    request = _proposal()
    at = _END - before_end

    with recorded_clock_reads() as clock_reads, in_act(at):
        inputs = sender_embargo_proposal_inputs(request)

    assert clock_reads == []
    if kept:
        assert inputs["sender_proposed_embargo_duration"] == before_end
        assert inputs["sender_proposed_embargo"] == request.proposed_embargo
    else:
        assert inputs == {}


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("ARCH-10-001")
def test_outside_an_act_the_terms_are_not_measured() -> None:
    """No act, no instant: the read raises rather than reading the clock."""
    with pytest.raises(VultronMissingActInstantError):
        sender_embargo_proposal_inputs(_proposal())
