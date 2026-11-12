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
"""A seeded first status is authored with its object, at its own time.

A case's first ``CaseStatus`` and a participant's first ``ParticipantStatus``
are built by the model when the caller gives none.  The model reads no clock
(ADR-0176), so the seed takes the object's own ``published``; a blank one is
absence (CS-08-001).

Spec: CS-13-002, CS-08-001, EH-07-001.
"""

import pytest
from pydantic import ValidationError

from test.support.act_clock import ACT_AT, recorded_clock_reads
from test.support.objects import make
from vultron.core.models._helpers import INBOUND_CONTEXT_KEY
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import (
    CaseParticipant,
    ReporterParticipant,
)

_OWNER = "https://example.org/actors/owner"
_CASE = "https://example.org/cases/seeded"


@pytest.mark.spec("CS-13-002")
def test_a_cases_first_status_takes_the_cases_published() -> None:
    with recorded_clock_reads() as reads:
        case = make(
            VulnerabilityCase,
            attributed_to=_OWNER,
            published=ACT_AT,
            updated=ACT_AT,
        )
    assert case.current_status.published == ACT_AT
    assert reads == []


@pytest.mark.spec("EH-07-001")
def test_a_case_with_no_time_reports_both_missing_times() -> None:
    """No status is seeded from a missing time; the case's own fields say
    what is missing, every violation at once."""
    with pytest.raises(ValidationError) as caught:
        VulnerabilityCase.model_validate(
            {"attributed_to": _OWNER, "genesis_hash": "0" * 64}
        )
    missing = {
        e["loc"][0] for e in caught.value.errors() if e["type"] == "missing"
    }
    assert {"published", "updated"} <= missing


@pytest.mark.spec("CS-13-002")
@pytest.mark.parametrize("cls", [CaseParticipant, ReporterParticipant])
def test_a_participants_first_status_takes_its_published(cls) -> None:
    with recorded_clock_reads() as reads:
        participant = make(
            cls,
            attributed_to=_OWNER,
            context=_CASE,
            published=ACT_AT,
            updated=ACT_AT,
        )
    (status,) = participant.participant_statuses
    assert status.published == ACT_AT
    assert status.updated == ACT_AT
    assert reads == []


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("cls", [CaseParticipant, ReporterParticipant])
def test_a_blank_published_seeds_a_status_with_no_time(cls) -> None:
    """A received participant whose ``published`` is blank claimed no time,
    so its seeded status claims none either."""
    participant = cls.model_validate(
        {"attributedTo": _OWNER, "context": _CASE, "published": ""},
        context={INBOUND_CONTEXT_KEY: True},
    )
    (status,) = participant.participant_statuses
    assert participant.published is None
    assert status.published is None
    assert status.updated is None
